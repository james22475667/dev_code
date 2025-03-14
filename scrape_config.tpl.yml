from prometheus_client import Gauge, start_http_server
import time
import csv
import os

# **設定 CSV 檔案來源**
CSV_FILE = "data_collect.csv"

# **讀取 CSV 並解析 `labels`**
def parse_csv():
    """從 `data_collect.csv` 讀取資料，並動態解析標籤"""
    counts = {}
    dynamic_labels = {"host", "job_name"}  # **初始標籤**
    
    if not os.path.exists(CSV_FILE):
        print(f"[ERROR] CSV 檔案 `{CSV_FILE}` 不存在！")
        return counts, dynamic_labels

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)  # 解析 CSV，第一行作為標題
        for row in reader:
            host = row.get("host", "").strip()
            job_name = row.get("job_name", "").strip()
            if not host or not job_name:
                continue  # **跳過無效資料**

            # **提取額外標籤**
            extra_labels = {k.strip(): v.strip() for k, v in row.items() if k not in ["host", "job_name"] and v.strip()}
            
            # **更新 labels 清單**
            dynamic_labels.update(extra_labels.keys())

            # **確保 key 唯一**
            key = frozenset({**extra_labels, "host": host, "job_name": job_name}.items())
            counts[key] = counts.get(key, 0) + 1

    return counts, sorted(list(dynamic_labels))  # **確保 labels 順序固定**

# **初始化 Prometheus 指標**
counts, labels_list = parse_csv()
print(f"[DEBUG] 設定 Prometheus 指標，Labels: {labels_list}")  # 🔍 Debug
log_host_job_count = Gauge("log_host_job_count", "Count of occurrences of host and job_name in log", labels_list)

def update_metrics():
    """更新 Prometheus 指標，從 CSV 讀取資料"""
    log_host_job_count._metrics.clear()  # **清除舊數據**
    counts, labels_list = parse_csv()

    print("\n[DEBUG] 更新 metrics:")
    for key, count in counts.items():
        labels_dict = dict(key)  # **還原 Key 為字典**

        # **確保 `labels_dict` 的 keys 與 `labels_list` 完全匹配**
        labels_dict = {key: labels_dict.get(key, "") for key in labels_list}

        print(f"[DEBUG] 設定 `metrics` => {labels_dict} : {count}")  # 🔍 Debug
        log_host_job_count.labels(**labels_dict).set(count)


if __name__ == "__main__":
    # **啟動 Prometheus HTTP 伺服器**
    start_http_server(8000)
    print("Prometheus exporter running on http://localhost:8080/metrics")  # 🔍 Debug

    # **定期更新 metrics**
    while True:
        update_metrics()
        time.sleep(10)
