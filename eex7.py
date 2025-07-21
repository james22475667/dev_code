import unittest
import tempfile
import os
from exporter import CustomGauge, LogExporter

class TestCustomGauge(unittest.TestCase):
    def test_set_ignores_empty_labels(self):
        gauge = CustomGauge("test_metric", "test")
        gauge.set({"a": "1", "b": "", "c": "3"}, 5)
        self.assertEqual(len(gauge.metrics), 1)
        key = list(gauge.metrics.keys())[0]
        self.assertNotIn(("b", ""), key)

class TestLogExporter(unittest.TestCase):
    def setUp(self):
        # 建立暫存 CSV 檔案
        self.tmpfile = tempfile.NamedTemporaryFile(mode='w+', delete=False)
        self.tmpfile.write(
            'aaa,job1,2,"{\'k1\': \'v1\', \'k2\': \'v2\'}"\n'
            'bbb,job2,1,"{\'k1\': \'v1\'}"\n'
            'ccc,job3,3,""\n'
        )
        self.tmpfile.close()
        self.exporter = LogExporter(log_file="not_used.csv")
        self.exporter.tmp_log_file = self.tmpfile.name

    def tearDown(self):
        os.unlink(self.tmpfile.name)

    def test_count_host_job(self):
        results = self.exporter._count_host_job(self.tmpfile.name)
        self.assertEqual(len(results), 3)
        labels, value = results[0]
        self.assertEqual(labels["host"], "aaa")
        self.assertEqual(value, 2)
        self.assertIn("job_name", labels)
        self.assertIn("k1", labels)

    def test_update_metrics(self):
        self.exporter.update_metrics()
        self.assertGreater(len(self.exporter.metric.metrics), 0)
        found = any(
            "host" in dict(k) and dict(k)["host"] == "aaa"
            for k in self.exporter.metric.metrics
        )
        self.assertTrue(found)

    def test_scraper_limit(self):
        self.exporter.set_scraper_id("UA-TEST")
        self.exporter.set_scraper_ip("127.0.0.1")
        self.exporter.update_metrics()
        collected = list(self.exporter.collect())
        self.assertGreater(len(collected), 0)

        # 第二次呼叫 collect，應該因為已抓過而不再回傳資料
        collected_again = list(self.exporter.collect())
        self.assertEqual(len(collected_again), 0)

if __name__ == '__main__':
    unittest.main()
