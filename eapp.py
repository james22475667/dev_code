"""LogExporter"""
import time
import os
import csv
# from datetime import datetime
import logging
import logging.config
from typing import Dict, Tuple, Iterable
import shutil
from http.server import HTTPServer
from threading import Lock
import threading
from prometheus_client.metrics_core import Metric
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client.registry import Collector
from prometheus_client.exposition import MetricsHandler, generate_latest
from tsre.common.settings.base_config import Config
from tsre.common.settings.log import get_logger
from src.setting.config import get_settings

settings = get_settings()
Config.load_yaml(path="src/setting/logging.yaml")
logger: logging.Logger = get_logger()

class LogExporter(Collector):
    def __init__(self, log_file: str) -> None:
        self.log_file = log_file
        self.tmp_log_file = TMPLOGFILE
        self.metric_cache: Dict[Tuple[str, str], int] = {}
        self.lock_file = f"{log_file}.lock"
        self.cache_lock = Lock()
        self.update_timestamp = 0.0
        self.scraper_access_record: Dict[str, float] = {}  # 記錄 Scraper 是否已抓取
        self.scraper_id = ""  # 用於保存 scraper_id
        self.scraper_ip = ""  # 用於保存 scraper_ip

    def set_scraper_id(self, scraper_id: str) -> None:
        self.scraper_id = scraper_id

    def set_scraper_ip(self, scraper_ip: str) -> None:
        self.scraper_ip = scraper_ip

    def collect(self) -> Iterable[Metric]:
        # 確保 Scraper 在 `metric` 更新週期內只能抓取一次
        scraper_id = self.scraper_id
        scraper_ip = self.scraper_ip
        # 變成 IP + User-Agent
        scraper_version = f"{scraper_ip}_{scraper_id}"

        with self.cache_lock:
            # 如果 Scraper 已經抓取過這個 round 的 `metric` 週期，則拒絕
            if scraper_version in self.scraper_access_record:
                logger.warning(
                    f"Scraper {scraper_version} already accessed metrics in this cycle."
                )
                return

            # 記錄 Scraper 這次抓取的時間
            self.scraper_access_record[scraper_version] = time.time()

        metric = GaugeMetricFamily(
            "log_host_job_count",
            "Count of occurrences of host and job_name in log",
            labels=["host", "job_name"]
        )
        for (host, job_name), count in self.metric_cache.items():
            metric.add_metric([host, job_name], count)

        yield metric  # 返回 metric 指標

    def update_metrics(self) -> None:
        # 從最新的 tmp_log_<timestamp>.csv 更新 metric
        if not self.tmp_log_file or not os.path.exists(self.tmp_log_file):
            logger.warning(
                f"Temporary log file {self.tmp_log_file} does not exist."
            )
            return

        counts = self._count_host_job(self.tmp_log_file)

        with self.cache_lock:
            self.metric_cache = counts
            self.update_timestamp = time.time()
            # 清空 Scraper 記錄，允許 Scraper 再次抓取
            self.scraper_access_record.clear()
        logger.info("Metrics updated successfully.")

    def _count_host_job(self, tmp_log_file: str) -> Dict[Tuple[str, str], int]:
        # 計算 data_collect_tmp.csv 中 host 和 job_name 的出現次數
        counts: Dict[Tuple[str, str], int] = {}
        try:
            with open(tmp_log_file, 'r', encoding='utf-8') as temp_file:
                reader = csv.reader(temp_file)
                for row in reader:
                    host, job_name = row[0], row[1]
                    key = (host, job_name)
                    counts[key] = counts.get(key, 0) + 1
        except Exception as read_error:
            logger.error(f"Error reading file {tmp_log_file}: {read_error}")
        return counts

# 自定義 HTTP 請求處理程序
class CustomMetricsHandler(MetricsHandler):
    def do_GET(self) -> None:
        # 擷取 Scraper 的請求；獲取 Scraper IP 和 User-Agent
        # 取得 Scraper IP
        scraper_ip = self.headers.get("X-Forwarded-For")
        if scraper_ip:
            # X-Forwarded-For 可能包含多個 IP 地址，取第一個
            scraper_ip = scraper_ip.split(',')[0].strip()
        else:
            scraper_ip = self.client_address[0]
            logger.info(
                "can not find X-Forwarded-For IP use non-X-Forwarded-For IP"
            )

        # 取得 Scraper User-Agent
        scraper_user_agent = self.headers.get("User-Agent", "unknown")

        # 設定 scraper_id
        exporter.set_scraper_id(scraper_user_agent)
        # 設定 scraper_ip
        exporter.set_scraper_ip(scraper_ip)

        # 擷取 metrics
        metrics_data = generate_latest(REGISTRY)

        # 設置 HTTP 狀態碼
        self.send_response(200)
        self.send_header(
            'Content-Type', 'text/plain; version=0.0.4; charset=utf-8'
        )
        self.end_headers()

        # 寫入 metrics 返回給 Prometheus
        self.wfile.write(metrics_data)

# 啟動 HTTP 服務器
def start_custom_http_server(port: int) -> None:
    server = HTTPServer(('0.0.0.0', port), CustomMetricsHandler)
    logger.info(f"Starting HTTP server on port {port}")
    server.serve_forever()

def print_csv_contents(file_path: str) -> None:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                logger.info(row)
    except Exception as p_error:
        logger.error(f"Error reading file {file_path}: {p_error}")

if __name__ == "__main__":
    LOGFILE = "logs/data_collect.csv"
    TMPLOGFILE = "logs/data_collect_tmp.csv"
    PORT = 6379
    FREQUENCY = 80
    exporter = LogExporter(LOGFILE)

    try:
        shutil.copyfile(LOGFILE, TMPLOGFILE)
        logger.warning(
            f"Copy {LOGFILE} to {TMPLOGFILE} success"
        )
    except Exception as cpoy_event:
        logger.error(
            f"Copy {LOGFILE} to {TMPLOGFILE} fail: {cpoy_event}"
        )

    # 註冊 Prometheus 指標
    REGISTRY.register(exporter)

    # 啟動自訂 HTTP Server（取代 start_http_server()）
    threading.Thread(
        target=start_custom_http_server, args=(PORT,), daemon=True
    ).start()

    logger.info(
        "Prometheus exporter running on "
        f"http://localhost:{PORT}/metrics"
    )

    # 監控迴圈
    while True:
        try:
            shutil.copyfile(LOGFILE, TMPLOGFILE)
            logger.warning(
                f"Copy {LOGFILE} to {TMPLOGFILE} success"
            )
            # 打印TMPLOGFILE內容
            print_csv_contents(TMPLOGFILE)
        except Exception as cpoy_e:
            logger.error(
                f"Copy {LOGFILE} to {TMPLOGFILE} fail: {cpoy_e}"
            )

        # 更新指標快取
        exporter.update_metrics()

        try:
            with open(
                LOGFILE, 'w', encoding='utf-8'
            ) as f_file:
                f_file.truncate(0)
            logger.info(
                f"Cleared contents of file {LOGFILE}"
            )
            # os.remove(tmp_log_file)
            # logger.info(f"Removed temporary file {tmp_log_file}")
        except Exception as e_event:
            logger.error(
                f"Error cleaning file {LOGFILE}: {e_event}"
            )

        # 等待 Prometheus 抓取指標
        time.sleep(FREQUENCY)
