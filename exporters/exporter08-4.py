###不可用
from prometheus_client import Gauge, start_http_server
import time

# **動態標籤**
dynamic_labels = {"host", "job_name"}  # 先定義基本標籤

# **定義 Prometheus 指標（之後會重新建立，包含新標籤）**
log_host_job_count = None

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

def update_metrics():
    """動態解析 `labels`，並更新 Prometheus 指標"""
    global log_host_job_count, dynamic_labels

    # **掃描所有日誌，找出所有不同的 `label`**
    for _, _, extra_labels in log_data:
        for key in extra_labels.keys():
            dynamic_labels.add(key)

    # **更新 Prometheus 指標**
    labels_list = list(dynamic_labels)  # 轉換成列表
    print(f"[DEBUG] 更新 Prometheus 指標，Labels: {labels_list}")  # 🔍 Debug

    log_host_job_count = Gauge("log_host_job_count", "Count of occurrences of host and job_name in log", labels_list)

    # **統計計數**
    counts = {}
    for host, job, extra_labels in log_data:
        key = (host, job, frozenset(extra_labels.items()))
        counts[key] = counts.get(key, 0) + 1

    # **填充 `metrics`**
    log_host_job_count._metrics.clear()  # 清除舊數據
    print("\n[DEBUG] 更新 metrics:")
    for (host, job, extra_labels), count in counts.items():
        # **只使用真實存在的 `labels`**
        labels_dict = {"host": host, "job_name": job, **dict(extra_labels)}

        print(f"[DEBUG] 設定 `metrics` => {labels_dict} : {count}")  # 🔍 Debug
        log_host_job_count.labels(**labels_dict).set(count)

if __name__ == "__main__":
    # 啟動 Prometheus HTTP 伺服器
    start_http_server(8080)
    print("Prometheus exporter running on http://localhost:8080/metrics")  # 🔍 Debug

    while True:
        update_metrics()
        time.sleep(10)
