import csv
import os
import time
from datetime import datetime
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from prometheus_client import start_http_server
import logging
from filelock import FileLock, Timeout
from logging.handlers import RotatingFileHandler

# 设置日志轮换
log_handler = RotatingFileHandler(
    "exporter.log", maxBytes=5 * 1024 * 1024, backupCount=3  # 5MB 大小，最多保留 3 个旧日志文件
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[log_handler]
)

class LogExporter:
    def __init__(self, log_file):
        self.log_file = log_file
        self.lock_file = f"{log_file}.lock"  # 文件锁路径

    def collect(self):
        # 创建时间戳并生成临时文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        tmp_log_file = f"tmp_log_{timestamp}.csv"

        # 检查并清理过期的锁文件
        self._cleanup_lock()

        # 使用文件锁确保安全操作
        with FileLock(self.lock_file, timeout=5):  # 锁超时时间 5 秒
            if not os.path.exists(self.log_file):
                logging.warning(f"Log file {self.log_file} does not exist.")
                return

            try:
                # 重命名 log.csv 为 tmp_log_<时间戳>.csv
                os.rename(self.log_file, tmp_log_file)
                logging.info(f"Renamed {self.log_file} to {tmp_log_file}")
            except Exception as e:
                logging.error(f"Error renaming file: {e}")
                return

        # 定义 GaugeMetricFamily 指标
        metric = GaugeMetricFamily(
            "log_host_job_count",
            "Count of occurrences of host and job_name in log",
            labels=["host", "job_name"]
        )

        # 读取 tmp_log_<时间戳>.csv 并统计 host, job_name 的出现次数
        counts = self._count_host_job(tmp_log_file)

        # 将统计结果加入指标
        for (host, job_name), count in counts.items():
            metric.add_metric([host, job_name], count)

        # 清空并删除临时文件
        try:
            self._clear_and_remove_file(tmp_log_file)
        except Exception as e:
            logging.error(f"Error clearing and removing file {tmp_log_file}: {e}")

        yield metric

    def _count_host_job(self, tmp_log_file):
        """统计 tmp_log_<时间戳>.csv 中 host 和 job_name 的出现次数"""
        counts = {}
        try:
            with open(tmp_log_file, 'r') as f:
                reader = csv.reader(f)  # 无标题文件，使用 csv.reader
                for row in reader:
                    host, job_name = row[0], row[1]  # 按列取值
                    key = (host, job_name)
                    counts[key] = counts.get(key, 0) + 1
        except Exception as e:
            logging.error(f"Error reading log file {tmp_log_file}: {e}")

        return counts

    def _clear_and_remove_file(self, file_path):
        """清空文件内容并删除文件"""
        try:
            # 清空文件内容
            with open(file_path, 'w') as f:
                f.truncate(0)
            logging.info(f"Cleared contents of file {file_path}")

            # 删除文件
            os.remove(file_path)
            logging.info(f"Removed file {file_path}")
        except Exception as e:
            logging.error(f"Error clearing or removing file {file_path}: {e}")
            raise e

    def _cleanup_lock(self):
        """检查并清理过期的锁文件"""
        if os.path.exists(self.lock_file):
            try:
                with FileLock(self.lock_file, timeout=1):  # 尝试获取锁
                    logging.info("Lock file is valid, no need to clean up.")
            except Timeout:
                # 如果超时，说明锁文件是过期的，可以删除
                try:
                    os.remove(self.lock_file)
                    logging.warning(f"Removed stale lock file {self.lock_file}")
                except Exception as e:
                    logging.error(f"Error removing stale lock file {self.lock_file}: {e}")

if __name__ == "__main__":
    # 指定 log.csv 文件路径
    log_file = "log.csv"

    # 注册自定义收集器
    REGISTRY.register(LogExporter(log_file))

    # 启动 HTTP 服务，默认端口 8000
    start_http_server(8000)
    logging.info("Prometheus exporter running on http://localhost:8000/metrics")

    # 保持运行
    while True:
        time.sleep(10)
