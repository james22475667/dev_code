# 將 CustomGauge 整合進 LogExporter 類別中，讓其支援動態 label 並自動忽略空值。

import csv
import os
import time
import logging
import shutil
from typing import Dict, Tuple, Iterable
from threading import Lock, Thread
from http.server import HTTPServer
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client.registry import Collector
from prometheus_client.exposition import MetricsHandler, generate_latest

# === 自定義 CustomGauge 類別 ===
class CustomGauge:
    def __init__(self, name, documentation):
        self.name = name
        self.documentation = documentation
        self.metrics = {}

    def set(self, labels, value):
        filtered_labels = {k: v for k, v in labels.items() if v}
        key = tuple(sorted(filtered_labels.items()))
        self.metrics[key] = (filtered_labels, value)

    def collect(self):
        group = {}
        for label_tuple, (labels, value) in self.metrics.items():
            label_keys = tuple(labels.keys())
            if label_keys not in group:
                group[label_keys] = []
            group[label_keys].append((labels, value))

        for label_keys, series in group.items():
            gauge = GaugeMetricFamily(self.name, self.documentation, labels=label_keys)
            for labels, value in series:
                gauge.add_metric([labels[k] for k in label_keys], value)
            yield gauge

# === 整合 CustomGauge 的 LogExporter 類別 ===
class LogExporter(Collector):
    def __init__(self, log_file: str) -> None:
        self.log_file = log_file
        self.tmp_log_file = "logs/data_collect_tmp.csv"
        self.metric = CustomGauge("log_host_job_count", "Count of host and job_name with optional labels")
        self.cache_lock = Lock()
        self.scraper_access_record: Dict[str, float] = {}
        self.scraper_id = ""
        self.scraper_ip = ""

    def set_scraper_id(self, scraper_id: str) -> None:
        self.scraper_id = scraper_id

    def set_scraper_ip(self, scraper_ip: str) -> None:
        self.scraper_ip = scraper_ip

    def collect(self) -> Iterable[GaugeMetricFamily]:
        scraper_version = f"{self.scraper_ip}_{self.scraper_id}"
        with self.cache_lock:
            if scraper_version in self.scraper_access_record:
                return
            self.scraper_access_record[scraper_version] = time.time()
        yield from self.metric.collect()

    def update_metrics(self):
        if not os.path.exists(self.tmp_log_file):
            return
        counts = self._count_host_job(self.tmp_log_file)
        with self.cache_lock:
            self.metric.metrics.clear()
            for labels_dict, value in counts:
                self.metric.set(labels_dict, value)
            self.scraper_access_record.clear()

    def _count_host_job(self, file_path: str):
        results = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 3:
                    continue
                host = row[0].strip()
                job_name = row[1].strip()
                log_count = int(row[2].strip())
                extra_labels = {}
                for col in row[3:]:
                    col = col.strip().strip('{}')
                    for pair in col.split(','):
                        if ':' in pair:
                            k, v = map(str.strip, pair.split(':', 1))
                            k = k.strip("'").strip('"')
                            v = v.strip("'").strip('"')
                            if k and v:
                                extra_labels[k] = v
                labels_dict = {**extra_labels, "host": host, "job_name": job_name}
                results.append((labels_dict, log_count))
        return results

# === 自訂 Metrics Handler，支援 IP 與 UA 辨識 ===
class CustomMetricsHandler(MetricsHandler):
    def do_GET(self) -> None:
        scraper_ip = self.headers.get("X-Forwarded-For") or self.client_address[0]
        scraper_ip = scraper_ip.split(',')[0].strip()
        scraper_user_agent = self.headers.get("User-Agent", "unknown")
        exporter.set_scraper_id(scraper_user_agent)
        exporter.set_scraper_ip(scraper_ip)
        metrics_data = generate_latest(REGISTRY)
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; version=0.0.4; charset=utf-8')
        self.end_headers()
        self.wfile.write(metrics_data)

# === HTTP Server 啟動函式 ===
def start_custom_http_server(port: int) -> None:
    server = HTTPServer(('0.0.0.0', port), CustomMetricsHandler)
    server.serve_forever()

# === 主程式 ===
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    LOGFILE = "logs/data_collect.csv"
    TMPLOGFILE = "logs/data_collect_tmp.csv"
    PORT = 6379
    FREQUENCY = 80

    exporter = LogExporter(LOGFILE)
    REGISTRY.register(exporter)

    try:
        shutil.copyfile(LOGFILE, TMPLOGFILE)
        logging.info(f"Copy {LOGFILE} to {TMPLOGFILE} success")
    except Exception as e:
        logging.error(f"Initial copy failed: {e}")

    Thread(target=start_custom_http_server, args=(PORT,), daemon=True).start()
    logging.info(f"Prometheus exporter running on http://localhost:{PORT}/metrics")

    while True:
        try:
            shutil.copyfile(LOGFILE, TMPLOGFILE)
            logging.info(f"Copied {LOGFILE} to {TMPLOGFILE}")
        except Exception as e:
            logging.error(f"Copy failed: {e}")

        exporter.update_metrics()

        try:
            with open(LOGFILE, 'w', encoding='utf-8') as f:
                f.truncate(0)
            logging.info(f"Cleared contents of {LOGFILE}")
        except Exception as e:
            logging.error(f"File clear failed: {e}")

        time.sleep(FREQUENCY)
