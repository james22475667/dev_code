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
        self.tmp_log_file = None
        self.metric_cache = {}
        self.lock_file = f"{log_file}.lock"
        self.cache_lock = Lock()
        self.update_timestamp = None
        self.scraper_access_record = {}  # 記錄 Scraper 是否已抓取

    def collect(self, scraper_id):
        """確保 Scraper 在 `metric` 更新週期內只能抓取一次"""

        with self.cache_lock:
            # 如果 Scraper 已經抓取過這個 `metric` 週期，則拒絕
            if scraper_id in self.scraper_access_record:
                logging.warning(f"Scraper {scraper_id} already accessed metrics in this cycle.")
                return

            # 記錄 Scraper 這次抓取的時間
            self.scraper_access_record[scraper_id] = time.time()

            metric = GaugeMetricFamily(
                "log_host_job_count",
                "Count of occurrences of host and job_name in log",
                labels=["host", "job_name"]
            )
            for (host, job_name), count in self.metric_cache.items():
                metric.add_metric([host, job_name], count)

        yield metric  # 返回 metric 指標

    def update_metrics(self):
        """從最新的 tmp_log_<timestamp>.csv 更新 metric"""
        if not self.tmp_log_file or not os.path.exists(self.tmp_log_file):
            logging.warning(f"Temporary log file {self.tmp_log_file} does not exist.")
            return
        
        counts = self._count_host_job(self.tmp_log_file)

        with self.cache_lock:
            self.metric_cache = counts
            self.update_timestamp = time.time()
            self.scraper_access_record.clear()  # 清空 Scraper 記錄，允許 Scraper 再次抓取

        logging.info("Metrics updated successfully.")

    def _count_host_job(self, tmp_log_file):
        """計算 tmp_log_<timestamp>.csv 中 host 和 job_name 的出現次數"""
        counts = {}
        try:
            with open(tmp_log_file, 'r') as f:
                reader = csv.reader(f)
                for row in reader:
                    host, job_name = row[0], row[1]
                    key = (host, job_name)
                    counts[key] = counts.get(key, 0) + 1
        except Exception as e:
            logging.error(f"Error reading log file {tmp_log_file}: {e}")
        return counts


# 自訂 HTTP Handler 來處理 `User-Agent`
class CustomMetricsHandler(MetricsHandler):
    def do_GET(self):
        """攔截 Scraper 的請求，獲取 `User-Agent`"""
        scraper_id = self.headers.get("User-Agent", "unknown")  # 取得 Scraper 的 User-Agent
        logging.info(f"Scraper {scraper_id} is requesting metrics.")

        # 調用 LogExporter 的 `collect()`，傳入 Scraper ID
        for metric in exporter.collect(scraper_id):
            self.wfile.write(metric.serialize())

# 讓 HTTP 伺服器支援多線程，避免 Scraper 互相影響
class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    """支援多線程的 HTTP Server"""

if __name__ == "__main__":
    log_file = "log.csv"
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
