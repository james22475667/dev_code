from prometheus_client import Gauge, start_http_server
import time
import csv
import os

# **設定 CSV 檔案來源**
CSV_FILE = "bak-data_collect.csv"

def parse_csv():
    """從 `data.collect.csv` 讀取資料，並動態解析標籤"""
    counts = {}
    dynamic_labels = {"host", "job_name"}  # **初始標籤**
    
    if not os.path.exists(CSV_FILE):
        print(f"[ERROR] CSV 檔案 `{CSV_FILE}` 不存在！")
        return counts, dynamic_labels

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
                if col.startswith("{") and col.endswith("}"):
                    col = col[1:-1]  # **移除 `{}` 大括號**
                
                # **解析 `key=value` 格式**
                key_value_pairs = col.split(",")
                for pair in key_value_pairs:
                    pair = pair.strip()
                    if "=" in pair:
                        key, value = map(str.strip, pair.split("=", 1))
                        if key and value:
                            extra_labels[key] = value

            # **更新 Labels**
            dynamic_labels.update(extra_labels.keys())

            # **建立 Key**
            key = frozenset({**extra_labels, "host": host, "job_name": job_name}.items())
            counts[key] = counts.get(key, 0) + 1

    return counts, sorted(list(dynamic_labels))

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

        # **確保 `labels_dict` 內的 `keys` 只包含 `CSV` 內的標籤**
        labels_dict = {key: labels_dict.get(key, "") for key in labels_list}

        print(f"[DEBUG] 設定 `metrics` => {labels_dict} : {count}")  # 🔍 Debug
        log_host_job_count.labels(**labels_dict).set(count)

if __name__ == "__main__":
    # **啟動 Prometheus HTTP 伺服器**
    start_http_server(8080)
    print("Prometheus exporter running on http://localhost:8080/metrics")  # 🔍 Debug

    # **定期更新 metrics**
    while True:
        update_metrics()
        time.sleep(10)
