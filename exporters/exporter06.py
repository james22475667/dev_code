import csv
import os
import time
import logging
from datetime import datetime
from prometheus_client import Gauge, start_http_server
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

def update_metrics():
    """讀取 log.csv 並更新指標"""
    log_file = "log.csv"

    if not os.path.exists(log_file):
        logging.warning(f"Log file {log_file} does not exist.")
        return

    counts = {}
    try:
        with open(log_file, 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                host, job_name = row[0], row[1]
                key = (host, job_name)
                counts[key] = counts.get(key, 0) + 1
    except Exception as e:
        logging.error(f"Error reading log file {log_file}: {e}")
        return

    # 更新 `Gauge`
    total_count = sum(counts.values())  # 計算所有 host/job_name 出現的總數
    log_host_job_count.set(total_count)

    logging.info(f"Updated metrics: log_host_job_count = {total_count}")

if __name__ == "__main__":
    # 啟動 Prometheus HTTP 伺服器
    start_http_server(8080)
    logging.info("Prometheus exporter running on http://localhost:8080/metrics")

    # 監控迴圈
    while True:
        update_metrics()
        time.sleep(10)
