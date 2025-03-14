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
CSV_FILE = "bak-data_collect-1.csv"

def parse_csv():
    """從 `bak-data_collect-1.csv` 讀取資料，並動態解析標籤"""
    counts_basic = {}
    counts_service = {}
    counts_module = {}
    dynamic_labels_service = set()
    dynamic_labels_module = set()

    if not os.path.exists(CSV_FILE):
        logging.error(f"CSV 檔案 `{CSV_FILE}` 不存在！")
        return counts_basic, counts_service, counts_module, ["host", "job_name"], ["host", "job_name"]

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
                        value = value.replace("”", "\"").replace("“", "\"")  # 修正全形引號
                        if key and value:
                            extra_labels[key] = value

            # **記錄基本計數**
            basic_key = (host, job_name)
            counts_basic[basic_key] = counts_basic.get(basic_key, 0) + 1

            # **根據標籤分類到不同 metric**
            if "service_name" in extra_labels or "container_name" in extra_labels:
                service_key = (host, job_name, frozenset({k: v for k, v in extra_labels.items() if k in ["service_name", "container_name"]}.items()))
                counts_service[service_key] = counts_service.get(service_key, 0) + 1
                dynamic_labels_service.update(["service_name", "container_name"])

            if "module_name" in extra_labels:
                module_key = (host, job_name, frozenset({k: v for k, v in extra_labels.items() if k == "module_name"}.items()))
                counts_module[module_key] = counts_module.get(module_key, 0) + 1
                dynamic_labels_module.add("module_name")

    # **動態標籤**
    labels_list_service = sorted(["host", "job_name"] + list(dynamic_labels_service))
    labels_list_module = sorted(["host", "job_name"] + list(dynamic_labels_module))

    logging.info(f"Final dynamic_labels_service: {labels_list_service}")
    logging.info(f"Final dynamic_labels_module: {labels_list_module}")

    return counts_basic, counts_service, counts_module, labels_list_service, labels_list_module

# **初始化 Prometheus 指標**
counts_basic, counts_service, counts_module, labels_list_service, labels_list_module = parse_csv()

# **Metric 1：只包含基本 labels**
log_host_job_basic = Gauge(
    "log_host_job_basic",
    "Basic count of occurrences of host and job_name in log",
    ["host", "job_name"]
)

# **Metric 2：包含 `service_name, container_name`**
log_host_job_service = Gauge(
    "log_host_job_service",
    "Count of occurrences with service-related labels",
    labels_list_service
)

# **Metric 3：包含 `module_name`**
log_host_job_module = Gauge(
    "log_host_job_module",
    "Count of occurrences with module-related labels",
    labels_list_module
)

logging.info(f"[DEBUG] 設定 Prometheus 指標")
logging.info(f" - log_host_job_basic Labels: ['host', 'job_name']")
logging.info(f" - log_host_job_service Labels: {labels_list_service}")
logging.info(f" - log_host_job_module Labels: {labels_list_module}")  # 🔍 Debug

def update_metrics():
    """更新 Prometheus 指標"""
    log_host_job_basic._metrics.clear()
    log_host_job_service._metrics.clear()
    log_host_job_module._metrics.clear()

    counts_basic, counts_service, counts_module, labels_list_service, labels_list_module = parse_csv()

    logging.info("\n[DEBUG] 更新 metrics:")

    # **填充 `log_host_job_basic`**
    for (host, job), count in counts_basic.items():
        labels_dict = {"host": host, "job_name": job}
        logging.info(f"[DEBUG] 設定 `log_host_job_basic` => {labels_dict} : {count}")  # 🔍 Debug
        log_host_job_basic.labels(**labels_dict).set(count)

    # **填充 `log_host_job_service`**
    for (host, job, extra_labels_tuple), count in counts_service.items():
        extra_labels = dict(extra_labels_tuple)
        labels_dict = {label: extra_labels.get(label, "") for label in labels_list_service}
        labels_dict["host"] = host
        labels_dict["job_name"] = job
        sorted_labels_dict = {key: labels_dict[key] for key in labels_list_service}
        logging.info(f"[DEBUG] 設定 `log_host_job_service` => {sorted_labels_dict} : {count}")
        log_host_job_service.labels(**sorted_labels_dict).set(count)

    # **填充 `log_host_job_module`**
    for (host, job, extra_labels_tuple), count in counts_module.items():
        extra_labels = dict(extra_labels_tuple)
        labels_dict = {label: extra_labels.get(label, "") for label in labels_list_module}
        labels_dict["host"] = host
        labels_dict["job_name"] = job
        sorted_labels_dict = {key: labels_dict[key] for key in labels_list_module}
        logging.info(f"[DEBUG] 設定 `log_host_job_module` => {sorted_labels_dict} : {count}")
        log_host_job_module.labels(**sorted_labels_dict).set(count)

if __name__ == "__main__":
    # **啟動 Prometheus HTTP 伺服器**
    start_http_server(8080)
    logging.info("Prometheus exporter running on http://localhost:8080/metrics")

    # **定期更新 metrics**
    while True:
        update_metrics()
        time.sleep(10)
