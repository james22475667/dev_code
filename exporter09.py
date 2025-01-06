import csv
import os
import time
import logging
import ast
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

# 全局變數
metric_cache = {}
cache_lock = Lock()
scraper_access_record = {}  # 記錄 Scraper 是否已抓取

# 記錄所有出現過的 Labels，確保 Prometheus 可動態適應
dynamic_labels = {"host", "job_name"}

# 定義 Prometheus 指標，這裡先不指定 labels，後面根據 `dynamic_labels` 重新建立
log_host_job_count = None

def update_metrics():
    """從最新的 log.csv 解析數據，並更新 Prometheus 指標"""
    global log_host_job_count, dynamic_labels
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
                extra_labels = {}

                # 如果有第三欄，解析 JSON 格式的 label
                if len(row) > 2 and row[2].strip():
                    try:
                        extra_labels = ast.literal_eval(row[2].strip())  # 解析 JSON 物件
                        if not isinstance(extra_labels, dict):
                            raise ValueError
                    except (SyntaxError, ValueError):
                        logging.warning(f"Invalid label format in log: {row[2]}")
                        continue

                # 更新 `dynamic_labels`
                for key in extra_labels.keys():
                    dynamic_labels.add(key)

                # 產生唯一 key (包含 `host`, `job_name` 和額外 labels)
                key = (host, job_name, frozenset(extra_labels.items()))
                counts[key] = counts.get(key, 0) + 1

    except Exception as e:
        logging.error(f"Error reading log file {log_file}: {e}")
        return

    with cache_lock:
        global metric_cache
        metric_cache = counts
        scraper_access_record.clear()  # 清空 Scraper 記錄，允許 Scraper 再次抓取

        # **更新 Prometheus 指標**
        labels_list = list(dynamic_labels)  # 轉換成 list（確保 Prometheus 指標 labels 可動態適應）
        log_host_job_count = Gauge("log_host_job_count", "Count of occurrences of host and job_name in log", labels=labels_list)

    logging.info("Metrics updated successfully.")


def collect(scraper_ip):
    """確保 Scraper 在 `metric` 更新週期內只能抓取一次"""
    with cache_lock:
        if scraper_ip in scraper_access_record:
            logging.warning(f"Scraper {scraper_ip} 已經抓取過，拒絕提供數據")
            return

        scraper_access_record[scraper_ip] = time.time()

        # 清空舊的 `metrics`
        log_host_job_count._metrics.clear()

        # 重新加入 `metric` 數據
        for (host, job_name, extra_labels), count in metric_cache.items():
            labels_dict = {"host": host, "job_name": job_name, **dict(extra_labels)}
            log_host_job_count.labels(**labels_dict).set(count)

        logging.info(f"Updated metrics for Scraper {scraper_ip}")


if __name__ == "__main__":
    # 啟動 Prometheus HTTP 伺服器
    start_http_server(8080)
    logging.info("Prometheus exporter running on http://localhost:8080/metrics")

    # 監控迴圈
    while True:
        update_metrics()
        time.sleep(10)
