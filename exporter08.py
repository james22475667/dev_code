from prometheus_client import Gauge, start_http_server
import time

# **定義基本 `labels`**
dynamic_labels = {"host", "job_name"}

# **初始化 Prometheus 指標**
log_host_job_count = Gauge("log_host_job_count", "Count of occurrences", labels=list(dynamic_labels))

# **模擬 `log.csv` 數據**
log_data = [
    {"host": "host_1", "job_name": "job_A"},
    {"host": "host_1", "job_name": "job_A", "service_name": "aaa", "container_name": "bbbb"},
    {"host": "host_1", "job_name": "job_B"},
    {"host": "host_2", "job_name": "job_A"},
    {"host": "host_2", "job_name": "job_C"},
    {"host": "host_3", "job_name": "job_B", "module_name": "cbbb"},
    {"host": "host_3", "job_name": "job_B"},
    {"host": "host_3", "job_name": "job_B"},
]
host_1,job_A, {"service_name": "aaa", "container_name": "bbbb"}
host_1,job_A
host_1,job_B
host_2,job_A
host_2,job_C
host_3,job_B, {"module_name": "cbbb"}
host_3,job_B
host_3,job_B

# **解析數據並更新 `labels`**
metric_cache = {}

for entry in log_data:
    host = entry["host"]
    job_name = entry["job_name"]
    
    # **提取額外 `labels`**
    extra_labels = {k: v for k, v in entry.items() if k not in ["host", "job_name"]}
    
    # **更新 `dynamic_labels`**
    for label in extra_labels.keys():
        dynamic_labels.add(label)

    # **建立唯一 key**
    key = (host, job_name, frozenset(extra_labels.items()))
    metric_cache[key] = metric_cache.get(key, 0) + 1

    # **Print debug log**
    print(f"[DEBUG] Key: {key}, Count: {metric_cache[key]}")

# **更新 Prometheus 指標**
def update_metrics():
    """更新 Prometheus `metrics`"""
    log_host_job_count._metrics.clear()  # **清除舊數據**
    print("\n[DEBUG] 更新 Prometheus 指標：")

    for (host, job_name, extra_labels), count in metric_cache.items():
        labels_dict = {"host": host, "job_name": job_name, **dict(extra_labels)}
        log_host_job_count.labels(**labels_dict).set(count)
        print(f"[DEBUG] 設定 `metrics` => {labels_dict} : {count}")

# **啟動 HTTP 伺服器**
start_http_server(8080)
print("Exporter running on http://localhost:8080/metrics")

while True:
    update_metrics()
    time.sleep(10)
