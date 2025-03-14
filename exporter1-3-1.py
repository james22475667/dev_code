import csv
import os
import time
import logging
from prometheus_client import Gauge, start_http_server

# === [1] 設定 log 紀錄格式，方便我們觀察 metrics 的更新狀況 ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# === [2] 設定要讀取的 CSV 檔案 ===
CSV_FILE = "bak-data_collect.csv"

# === [3] 初始化 Prometheus 的 Gauge（我們稍後會根據 labels 來建立） ===
log_host_job_count = None  # 先留空，等 labels 決定好再建立


def parse_csv():
    """解析 CSV，動態收集所有出現過的 labels，並統計每組 labels 的出現次數"""
    counts = {}  # key = frozenset(labels)，value = 次數
    dynamic_labels = {"host", "job_name"}  # 初始固定兩個 labels

    if not os.path.exists(CSV_FILE):
        logging.error(f"CSV 檔案 `{CSV_FILE}` 不存在！")
        return counts, sorted(list(dynamic_labels))

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue  # 至少要有 host 和 job_name

            host = row[0].strip()
            job_name = row[1].strip()
            extra_labels = {}  # 額外的 labels

            # === 處理第三欄之後的欄位：包含額外 labels ===
            for col in row[2:]:
                col = col.strip()

                if col.startswith("{") and col.endswith("}"):
                    col = col[1:-1].strip()  # 拿掉大括號

                # 拆解 key=value
                key_value_pairs = col.split(",")
                for pair in key_value_pairs:
                    pair = pair.strip()
                    if "=" in pair:
                        key, value = map(str.strip, pair.split("=", 1))
                        key = key.replace("{", "").replace("}", "").strip()
                        value = value.replace("”", "").replace("“", "").strip("\"")

                        if key and value:
                            extra_labels[key] = value  # 收集有效 label

            # 更新動態 labels（只加入 key，不重複）
            dynamic_labels.update(extra_labels.keys())

            # 組合完整的 labels
            full_label_dict = {**extra_labels, "host": host, "job_name": job_name}
            key = frozenset(full_label_dict.items())
            counts[key] = counts.get(key, 0) + 1

    logging.info(f"[parse_csv] 最終 labels: {sorted(dynamic_labels)}")
    return counts, sorted(dynamic_labels)


def update_metrics():
    """每次更新 metrics（Prometheus 會來抓），我們就重建一次"""
    global log_host_job_count
    counts, labels_list = parse_csv()

    # 初始化或重新初始化 Gauge
    log_host_job_count = Gauge("log_host_job_count", "Count of host/job_name with optional labels", labels_list)

    log_host_job_count._metrics.clear()  # 清掉舊資料
    logging.info("[update_metrics] 開始設定 metrics...")

    for key, count in counts.items():
        labels_dict = dict(key)
        complete_labels = {k: labels_dict.get(k, "") for k in labels_list}  # 確保所有 label key 都存在
        logging.info(f"[metric] {complete_labels} => {count}")
        log_host_job_count.labels(**complete_labels).set(count)


if __name__ == "__main__":
    start_http_server(8080)
    logging.info("Exporter 正在 http://localhost:8080/metrics 執行...")

    while True:
        update_metrics()
        time.sleep(10)  # 每 10 秒更新一次
