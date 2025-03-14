import csv
import os
import time
import logging
from datetime import datetime
from prometheus_client import Gauge, start_http_server
from threading import Lock
from logging.handlers import RotatingFileHandler

# 設置日誌輪替
log_handler = RotatingFileHandler(
    "exporter.log", maxBytes=5 * 1024 * 1024, backupCount=3
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[log_handler]
)

# 定義 Prometheus 指標
log_host_job_count = Gauge("log_host_job_count", "Count of occurrences of host and job_name in log")

# 資料快取與 Scraper 記錄
metric_cache = {}
cache_lock = Lock()
scraper_access_record = {}  # 記錄 Scraper 是否已抓取


def collect(scraper_ip):
    """確保 Scraper 在 `metric` 更新週期內只能抓取一次"""
    with cache_lock:
        if scraper_ip in scraper_access_record:
            logging.warning(f"Scraper {scraper_ip} 已經抓取過，拒絕提供數據")
            return

        scraper_access_record[scraper_ip] = time.time()

        # 更新 Prometheus 指標
        total_count = sum(metric_cache.values())  # 計算所有 host/job_name 出現的總數
        log_host_job_count.set(total_count)

        logging.info(f"Updated metrics: log_host_job_count = {total_count}")
        print(f"[DEBUG] Updated metrics: log_host_job_count = {total_count}")  # 🔍 Debug


def update_metrics():
    """從最新的 data_collect.csv 更新 metric"""
    log_file = "data_collect.csv"

    if not os.path.exists(log_file):
        logging.warning(f"Log file {log_file} does not exist.")
        print("[DEBUG] Log file does not exist.")  # 🔍 Debug
        return

    counts = {}
    try:
        with open(log_file, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:  # 確保至少有 `host, job_name`
                    logging.warning(f"Invalid row format: {row}")
                    print(f"[DEBUG] Invalid row format: {row}")  # 🔍 Debug
                    continue

                host, job_name = row[0].strip(), row[1].strip()
                key = (host, job_name)
                counts[key] = counts.get(key, 0) + 1

    except Exception as e:
        logging.error(f"Error reading log file {log_file}: {e}")
        print(f"[DEBUG] Error reading log file {log_file}: {e}")  # 🔍 Debug
        return

    with cache_lock:
        global metric_cache
        metric_cache = counts
        scraper_access_record.clear()

        # 打印 metrics 計算結果
        print("\n[DEBUG] Updated metric_cache:")
        for key, value in metric_cache.items():
            print(f"[DEBUG] {key} : {value}")

    logging.info("Metrics updated successfully.")
    print("[DEBUG] Metrics updated successfully.")  # 🔍 Debug


if __name__ == "__main__":
    # 啟動 Prometheus HTTP 伺服器
    start_http_server(8080)
    logging.info("Prometheus exporter running on http://localhost:8080/metrics")
    print("Prometheus exporter running on http://localhost:8080/metrics")  # 🔍 Debug

    # 監控迴圈
    while True:
        update_metrics()
        time.sleep(10)
