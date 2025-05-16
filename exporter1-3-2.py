import csv
import os
import time
import logging
from prometheus_client import start_http_server, REGISTRY
from prometheus_client.core import GaugeMetricFamily

# === 自定義 CustomGauge 類別 ===
class CustomGauge:
    """
    Custom Gauge to allow dynamic label keys (omit empty labels).
    """
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

# === Logging 設定 ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# === 讀 CSV 並解析 labels ===
CSV_FILE = "bak-data_collect.csv"
log_host_job_count = CustomGauge("log_host_job_count", "Count of host/job_name with optional labels")
REGISTRY.register(log_host_job_count)

def parse_csv():
    counts = {}
    if not os.path.exists(CSV_FILE):
        logging.error(f"CSV 檔案 `{CSV_FILE}` 不存在！")
        return counts

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue

            host = row[0].strip()
            job_name = row[1].strip()
            extra_labels = {}

            for col in row[2:]:
                col = col.strip()
                if col.startswith("{") and col.endswith("}"):
                    col = col[1:-1].strip()
                for pair in col.split(","):
                    if "=" in pair:
                        k, v = map(str.strip, pair.split("=", 1))
                        k = k.strip("{}").strip()
                        v = v.replace("”", "").replace("“", "").strip("\"")
                        if k and v:
                            extra_labels[k] = v

            full_label_dict = {**extra_labels, "host": host, "job_name": job_name}
            key = frozenset(full_label_dict.items())
            counts[key] = counts.get(key, 0) + 1

    return counts

def update_metrics():
    log_host_job_count.metrics.clear()
    counts = parse_csv()
    for key, count in counts.items():
        labels_dict = dict(key)
        log_host_job_count.set(labels_dict, count)
        logging.info(f"[metric] {labels_dict} => {count}")

if __name__ == "__main__":
    start_http_server(8080)
    logging.info("Exporter 正在 http://localhost:8080/metrics 執行...")

    while True:
        update_metrics()
        time.sleep(10)
