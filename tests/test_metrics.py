"""
Unit tests for MetricsCollector.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from metrics import MetricsCollector


class TestMetricsCollector(unittest.TestCase):
    def setUp(self):
        self.collector = MetricsCollector()

    def test_record_and_summary(self):
        self.collector.record_request("/items", 12.5, 200)
        self.collector.record_request("/items", 17.5, 200)
        self.collector.record_request("/items", 20.0, 500)

        summary = self.collector.get_summary()
        self.assertEqual(summary["total_requests"], 3)
        self.assertEqual(summary["total_errors"], 1)
        self.assertEqual(summary["endpoints"]["/items"]["requests"], 3)
        self.assertEqual(summary["endpoints"]["/items"]["errors"], 1)
        self.assertEqual(summary["endpoints"]["/items"]["avg_latency_ms"], 16.67)

    def test_reset(self):
        self.collector.record_request("/health", 2.0, 200)
        self.assertEqual(self.collector.get_summary()["total_requests"], 1)
        self.collector.reset()
        self.assertEqual(self.collector.get_summary()["total_requests"], 0)


if __name__ == "__main__":
    unittest.main()
