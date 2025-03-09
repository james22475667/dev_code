import csv
import os
import time
import logging
from datetime import datetime
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client.exposition import MetricsHandler
from http.server import HTTPServer
from socketserver import ThreadingMixIn
from logging.handlers import RotatingFileHandler
from threading import Lock

# 設置日誌輪替
log_handler = RotatingFileHandler(
    "exporter.log", maxBytes=5 * 1024 * 1024, backupCount=3
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[log_handler]
)

class LogExporter:
    def __init__(self, log_file):
        self.log_file = log_file
        self.tmp_log_file = "data_collect.csv"
        self.metric_cache = {}
        self.labels_list = ["host", "job_name"]  # 初始 Labels，稍後會動態更新
        self.lock_file = f"{log_file}.lock"
        self.cache_lock = Lock()
        self.update_timestamp = None
        self.scraper_access_record = {}  # 記錄 Scraper 是否已抓取

    def collect(self, scraper_ip="unknown", scraper_user_agent="unknown"):
        """確保 Scraper 在 `metric` 更新週期內只能抓取一次"""
        scraper_version = f"{scraper_ip}_{scraper_user_agent}"

        with self.cache_lock:
            metric = GaugeMetricFamily(
                "log_host_job_count",
                "Count of occurrences of host and job_name in log",
                labels=self.labels_list + ["scraper_version"]
            )
            for key, count in self.metric_cache.items():
                labels_dict = dict(key)  # 將 key 轉回字典
                labels_dict["scraper_version"] = scraper_version
                metric.add_metric([labels_dict[label] for label in self.labels_list + ["scraper_version"]], count)

        yield metric  # 返回 metric 指標

    def update_metrics(self):
        """從最新的 tmp_log_<timestamp>.csv 更新 metric"""
        if not self.tmp_log_file or not os.path.exists(self.tmp_log_file):
            logging.warning(f"Temporary log file {self.tmp_log_file} does not exist.")
            return
        
        counts, dynamic_labels = self._count_host_job(self.tmp_log_file)

        with self.cache_lock:
            self.metric_cache = counts
            self.labels_list = sorted(list(dynamic_labels))  # 更新 Labels
            self.update_timestamp = time.time()
            self.scraper_access_record.clear()  # 清空 Scraper 記錄，允許 Scraper 再次抓取

        logging.info(f"Metrics updated successfully. Labels: {self.labels_list}")

    def _count_host_job(self, tmp_log_file):
        """計算 tmp_log_<timestamp>.csv 中 host 和 job_name 的出現次數"""
        counts = {}
        dynamic_labels = {"host", "job_name"}  # 確保 labels 只包含正確的 key

        try:
            with open(tmp_log_file, 'r') as f:
                reader = csv.reader(f)  # 使用 CSV 讀取器
                for row in reader:
                    # **確保至少有兩列 (host, job_name)**
                    if len(row) < 2:
                        continue

                    host, job_name = row[0].strip(), row[1].strip()
                    extra_labels = {}

                    # **解析額外標籤，處理 `{}` 大括號**
                    for col in row[2:]:
                        col = col.strip()
                        if col.startswith("{") and col.endswith("}"):
                            col = col[1:-1]  # 移除大括號
                        if "=" in col:  # 只允許 `key=value` 格式
                            key, value = map(str.strip, col.split("=", 1))
                            extra_labels[key] = value

                    # **更新 Labels**
                    dynamic_labels.update(extra_labels.keys())

                    # **建立 Key**
                    key = frozenset({**extra_labels, "host": host, "job_name": job_name}.items())

                    counts[key] = counts.get(key, 0) + 1
        except Exception as e:
            logging.error(f"Error reading log file {tmp_log_file}: {e}")

        # Debug: 確保 dynamic_labels 正確
        logging.info(f"Final dynamic_labels: {sorted(list(dynamic_labels))}")

        return counts, dynamic_labels





# 自訂 HTTP Handler 來處理 `User-Agent`
class CustomMetricsHandler(MetricsHandler):
    def do_GET(self):
        """攔截 Scraper 的請求，獲取 Scraper IP 和 User-Agent"""
        
        # 獲取 Scraper IP
        scraper_ip = self.client_address[0]

        # 獲取 Scraper User-Agent
        scraper_user_agent = self.headers.get("User-Agent", "unknown")

        # 獲取全部 Headers
        headers = dict(self.headers)

        logging.info(f"Scraper IP: {scraper_ip}, User-Agent: {scraper_user_agent}")
        logging.info(f"Scraper Headers: {headers}")

        for metric in exporter.collect(scraper_ip, scraper_user_agent):
            self.wfile.write(metric.serialize())


# 讓 HTTP 伺服器支援多線程，避免 Scraper 互相影響
class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    """支援多線程的 HTTP Server"""

if __name__ == "__main__":
    log_file = "data_collect.csv"
    exporter = LogExporter(log_file)

    # 註冊 Prometheus 指標
    REGISTRY.register(exporter)

    # 啟動自訂 HTTP Server (取代 `start_http_server()`)
    server = ThreadingSimpleServer(("0.0.0.0", 8000), CustomMetricsHandler)
    logging.info("Prometheus exporter running on http://localhost:8000/metrics")

    # 監控迴圈
    while True:
        # 更新指標快取
        exporter.update_metrics()

        # 等待 Prometheus 抓取指標
        time.sleep(10)
