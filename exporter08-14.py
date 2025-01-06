from prometheus_client import Gauge, start_http_server
import time

# **模擬的日誌數據**
log_data = [
    ("host_1", "job_A", {"service_name": "aaa", "container_name": "bbbb"}),  # 有額外 labels
    ("host_1", "job_A", {}),  # 沒有額外 labels
    ("host_1", "job_B", {}),
    ("host_2", "job_A", {}),
    ("host_2", "job_C", {}),
    ("host_3", "job_B", {"module_name": "cbbb"}),  # 有額外 labels
    ("host_3", "job_B", {}),
    ("host_3", "job_B", {})
]

# **Metric 1：只包含基本 labels**
log_host_job_basic = Gauge(
    "log_host_job_basic",
    "Basic count of occurrences of host and job_name in log",
    ["host", "job_name"]
)

# **Metric 2：包含所有可能出現的 labels（動態偵測）**
extra_labels_set = set()
for _, _, extra_labels in log_data:
    extra_labels_set.update(extra_labels.keys())

labels_list_extended = sorted(["host", "job_name"] + list(extra_labels_set))

log_host_job_extended = Gauge(
    "log_host_job_extended",
    "Extended count of occurrences with additional labels",
    labels_list_extended
)

print(f"[DEBUG] 設定 Prometheus 指標")
print(f" - log_host_job_basic Labels: ['host', 'job_name']")
print(f" - log_host_job_extended Labels: {labels_list_extended}")  # 🔍 Debug

def update_metrics():
    """更新 Prometheus 指標"""
    log_host_job_basic._metrics.clear()
    log_host_job_extended._metrics.clear()
    
    counts_basic = {}
    counts_extended = {}

    for host, job, extra_labels in log_data:
        if extra_labels:  # **如果有額外 labels，就加入 `log_host_job_extended`**
            key = (host, job, frozenset(extra_labels.items()))
            counts_extended[key] = counts_extended.get(key, 0) + 1
        else:  # **如果沒有額外 labels，就加入 `log_host_job_basic`**
            key = (host, job)
            counts_basic[key] = counts_basic.get(key, 0) + 1

    print("\n[DEBUG] 更新 metrics:")

    # **填充 `log_host_job_basic`**
    for (host, job), count in counts_basic.items():
        labels_dict = {"host": host, "job_name": job}
        print(f"[DEBUG] 設定 `log_host_job_basic` => {labels_dict} : {count}")  # 🔍 Debug
        log_host_job_basic.labels(**labels_dict).set(count)

    # **填充 `log_host_job_extended`**
    for (host, job, extra_labels_tuple), count in counts_extended.items():
        extra_labels = dict(extra_labels_tuple)

        # **確保 `labels_dict` 內的 `keys` 與 `labels_list_extended` 一致**
        labels_dict = {label: extra_labels.get(label, "") for label in labels_list_extended}
        labels_dict["host"] = host
        labels_dict["job_name"] = job

        # **確保 `labels_dict` 的 `keys` 順序與 `labels_list_extended` 一致**
        sorted_labels_dict = {key: labels_dict[key] for key in labels_list_extended}

        print(f"[DEBUG] 設定 `log_host_job_extended` => {sorted_labels_dict} : {count}")  # 🔍 Debug
        log_host_job_extended.labels(**sorted_labels_dict).set(count)

if __name__ == "__main__":
    # 啟動 Prometheus HTTP 伺服器
    start_http_server(8080)
    print("Prometheus exporter running on http://localhost:8080/metrics")  # 🔍 Debug

    while True:
        update_metrics()
        time.sleep(10)
