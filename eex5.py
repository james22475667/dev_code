# src/exporter1-3-2-2.py
import csv
import os
import time
import logging
import shutil
from prometheus_client import start_http_server, REGISTRY
from prometheus_client.core import GaugeMetricFamily

# === Custom CustomGauge class ===
class CustomGauge:
    """
    Custom Gauge to allow dynamic label keys (omit empty labels).
    """
    def __init__(self, name, documentation):
        self.name = name
        self.documentation = documentation
        self.metrics = {}

    def set(self, labels, value):
        filtered_labels = {k: v for k, v in labels.items() if v}
        key = tuple(sorted(filtered_labels.items()))
        self.metrics[key] = (filtered_labels, value)

    def collect(self):
        group = {}
        for label_tuple, (labels, value) in self.metrics.items():
            label_keys = tuple(labels.keys())
            if label_keys not in group:
                group[label_keys] = []
            group[label_keys].append((labels, value))

        for label_keys, series in group.items():
            gauge = GaugeMetricFamily(self.name, self.documentation, labels=label_keys)
            for labels, value in series:
                gauge.add_metric([labels[k] for k in label_keys], value)
            yield gauge

# === Logging configuration ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# === Read CSV and parse labels ===
CSV_FILE = "logs/data_collect.csv"
log_host_job_count = CustomGauge("log_host_job_count", "Count of host and job_name with optional labels")
REGISTRY.register(log_host_job_count)

def parse_csv():
    counts = {}
    if not os.path.exists(CSV_FILE):
        logging.error(f"CSV file [{CSV_FILE}] does not exist!")
        return counts

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue

            host = row[0].strip()
            job_name = row[1].strip()
            log_count = int(row[2].strip())
            extra_labels = {}

            for col in row[3:]:
                col = col.strip()
                if col.startswith("{") and col.endswith("}"):
                    col = col[1:-1].strip()
                pair = col.split(",")
                for p in pair:
                    if ":" in p:
                        k, v = map(str.strip, p.split(":", 1))
                        k = k.strip('"').strip("'").strip()
                        v = v.strip('"').strip("'").strip()
                        if k and v:
                            extra_labels[k] = v

            full_label_dict = {**extra_labels, "host": host, "job_name": job_name}
            key = frozenset(full_label_dict.items())
            counts[key] = counts.get(key, 0) + log_count
    return counts

def update_metrics():
    log_host_job_count.metrics.clear()
    counts = parse_csv()
    for key, count in counts.items():
        labels_dict = dict(key)
        log_host_job_count.set(labels_dict, count)
        logging.info(f"[metric] {labels_dict} => {count}")

def print_csv_contents(file_path: str) -> None:
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                logging.info(row)
    except Exception as p_error:
        logging.error(f"Error reading file {file_path}: {p_error}")

if __name__ == "__main__":
    LOGFILE = "logs/data_collect.csv"
    TMPLOGFILE = "logs/data_collect_tmp.csv"
    PORT = 6379
    FREQUENCY = 80

    start_http_server(PORT)
    logging.info("Exporter is running at http://localhost:8000/metrics ...")

    while True:
        # 監控迴圈
        try:
            shutil.copyfile(LOGFILE, TMPLOGFILE)
            logging.warning(
                f"Copy {LOGFILE} to {TMPLOGFILE} success"
            )
            # 打印TMPLOGFILE內容
            print_csv_contents(TMPLOGFILE)
        except Exception as cpoy_e:
            logging.error(
                f"Copy {LOGFILE} to {TMPLOGFILE} fail: {cpoy_e}"
            )

        update_metrics()

        try:
            with open(
                LOGFILE, 'w', encoding='utf-8'
            ) as f_file:
                f_file.truncate(0)
            logging.info(
                f"Cleared contents of file {LOGFILE}"
            )
            # os.remove(tmp_log_file)
            # logger.info(f"Removed temporary file {tmp_log_file}")
        except Exception as e_event:
            logging.error(
                f"Error cleaning file {LOGFILE}: {e_event}"
            )

        time.sleep(60)
