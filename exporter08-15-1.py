import csv
import os
import time
import logging
from prometheus_client import Gauge, start_http_server

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# **設定 CSV 檔案來源**
CSV_FILE = "bak-data_collect.csv"

def parse_csv():
    """從 `bak-data_collect.csv` 讀取資料，並動態解析標籤"""
    counts_basic = {}
    counts_extended = {}
    dynamic_labels = set()  # **動態標籤**

    if not os.path.exists(CSV_FILE):
        logging.error(f"CSV 檔案 `{CSV_FILE}` 不存在！")
        return counts_basic, counts_extended, sorted(["host", "job_name"])

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue  # **至少要有 `host` 和 `job_name`**

            host = row[0].strip()
            job_name = row[1].strip()
            extra_labels = {}

            # **解析 `{}` 內的標籤**
            for col in row[2:]:
                col = col.strip()

                # **移除 `{}` 大括號**
                if col.startswith("{") and col.endswith("}"):
                    col = col[1:-1].strip()  

                # **解析 `key=value` 格式**
                key_value_pairs = col.split(",")
                for pair in key_value_pairs:
                    pair = pair.strip()
                    if "=" in pair:
                        key, value = map(str.strip, pair.split("=", 1))
                        key = key.replace("{", "").replace("}", "").strip()  # **確保 `key` 沒有 `{}`**
                        if key and value:
                            extra_labels[key] = value

            # **更新動態 Labels**
            dynamic_labels.update(extra_labels.keys())

            # **記錄基本計數**
            basic_key = (host, job_name)
            counts_basic[basic_key] = counts_basic.get(basic_key, 0) + 1

            # **記錄擴展計數（包含額外標籤）**
            if extra_labels:
                extended_key = (host, job_name, frozenset(extra_labels.items()))
                counts_extended[extended_key] = counts_extended.get(extended_key, 0) + 1

    # **確保 `dynamic_labels` 只包含有效的 key**
    labels_list_extended = sorted(["host", "job_name"] + list(dynamic_labels))

    logging.info(f"Final dynamic_labels: {labels_list_extended}")
    return counts_basic, counts_extended, labels_list_extended

# **初始化 Prometheus 指標**
counts_basic, counts_extended, labels_list_extended = parse_csv()

# **Metric 1：只包含基本 labels**
log_host_job_basic = Gauge(
    "log_host_job_basic",
    "Basic count of occurrences of host and job_name in log",
    ["host", "job_name"]
)

# **Metric 2：包含所有可能出現的 labels（動態偵測）**
log_host_job_extended = Gauge(
    "log_host_job_extended",
    "Extended count of occurrences with additional labels",
    labels_list_extended
)

logging.info(f"[DEBUG] 設定 Prometheus 指標")
logging.info(f" - log_host_job_basic Labels: ['host', 'job_name']")
logging.info(f" - log_host_job_extended Labels: {labels_list_extended}")  # 🔍 Debug

def update_metrics():
    """更新 Prometheus 指標"""
    log_host_job_basic._metrics.clear()  # **清除舊數據**
    log_host_job_extended._metrics.clear()

    counts_basic, counts_extended, labels_list_extended = parse_csv()

    logging.info("\n[DEBUG] 更新 metrics:")

    # **填充 `log_host_job_basic`**
    for (host, job), count in counts_basic.items():
        labels_dict = {"host": host, "job_name": job}
        logging.info(f"[DEBUG] 設定 `log_host_job_basic` => {labels_dict} : {count}")  # 🔍 Debug
        log_host_job_basic.labels(**labels_dict).set(count)  # ✅ 確保有數據

    # **填充 `log_host_job_extended`**
    for (host, job, extra_labels_tuple), count in counts_extended.items():
        extra_labels = dict(extra_labels_tuple)

        # **確保 `labels_dict` 內的 `keys` 與 `labels_list_extended` 一致**
        labels_dict = {label: extra_labels.get(label, "") for label in labels_list_extended}
        labels_dict["host"] = host
        labels_dict["job_name"] = job

        # **確保 `labels_dict` 的 `keys` 順序與 `labels_list_extended` 一致**
        sorted_labels_dict = {key: labels_dict[key] for key in labels_list_extended}

        logging.info(f"[DEBUG] 設定 `log_host_job_extended` => {sorted_labels_dict} : {count}")  # 🔍 Debug
        log_host_job_extended.labels(**sorted_labels_dict).set(count)  # ✅ 確保有數據

if __name__ == "__main__":
    # **啟動 Prometheus HTTP 伺服器**
    start_http_server(8080)
    logging.info("Prometheus exporter running on http://localhost:8080/metrics")  # 🔍 Debug

    # **定期更新 metrics**
    while True:
        update_metrics()
        time.sleep(10)
