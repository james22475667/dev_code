from prometheus_client import Gauge, start_http_server
import time

# **模擬的日誌數據**
log_data = [
    ("host_1", "job_A", {"service_name": "aaa", "container_name": "bbbb"}),
    ("host_1", "job_A", {}),
    ("host_1", "job_B", {}),
    ("host_2", "job_A", {}),
    ("host_2", "job_C", {}),
    ("host_3", "job_B", {"module_name": "cbbb"}),
    ("host_3", "job_B", {}),
    ("host_3", "job_B", {})
]

# **收集所有出現的 `labels`，確保 `Gauge` 內只有真實出現的 labels**
dynamic_labels = {"host", "job_name"}
for _, _, extra_labels in log_data:
    dynamic_labels.update(extra_labels.keys())

labels_list = sorted(list(dynamic_labels))  # **確保 labels 順序固定**

print(f"[DEBUG] 設定 Prometheus 指標，Labels: {labels_list}")  # 🔍 Debug

# **建立 `Gauge`**
log_host_job_count = Gauge("log_host_job_count", "Count of occurrences of host and job_name in log", labels_list)

def update_metrics():
    """更新 Prometheus 指標"""
    log_host_job_count._metrics.clear()  # **清除舊數據**
    counts = {}

    for host, job, extra_labels in log_data:
        key = (host, job, frozenset(extra_labels.items()))  # **用 frozenset 確保 key 唯一**
        counts[key] = counts.get(key, 0) + 1

    print("\n[DEBUG] 更新 metrics:")
    for (host, job, extra_labels_tuple), count in counts.items():
        # **還原 `extra_labels` 回 `dict`**
        extra_labels = dict(extra_labels_tuple)

        # **只包含 `log_data` 內真正出現的 `labels`，不加空值**
        labels_dict = {"host": host, "job_name": job}
        labels_dict.update(extra_labels)  # 只加入 `log_data` 內有的 `labels`

        print(f"[DEBUG] 設定 `metrics` => {labels_dict} : {count}")  # 🔍 Debug
        log_host_job_count.labels(**labels_dict).set(count)

if __name__ == "__main__":
    # 啟動 Prometheus HTTP 伺服器
    start_http_server(8080)
    print("Prometheus exporter running on http://localhost:8080/metrics")  # 🔍 Debug

    while True:
        update_metrics()
        time.sleep(10)
