"""
Unit tests for AnalyticsEngine module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from analytics import AnalyticsEngine, MetricDataPoint


class TestAnalyticsEngine(unittest.TestCase):
    def setUp(self):
        self.engine = AnalyticsEngine()

    def test_record_and_get_metric_series(self):
        self.engine.record_metric("api_latency_ms", 120.5, unit="ms", tags={"env": "prod"})
        self.engine.record_metric("api_latency_ms", 80.5, unit="ms", tags={"env": "prod"})
        self.engine.record_metric("api_latency_ms", 99.0, unit="ms", tags={"env": "prod"})

        # Test avg aggregation
        avg_res = self.engine.get_metric_series("api_latency_ms", aggregation="avg")
        self.assertEqual(avg_res["count"], 3)
        self.assertEqual(avg_res["aggregate_value"], 100.0)
        self.assertEqual(avg_res["unit"], "ms")

        # Test sum aggregation
        sum_res = self.engine.get_metric_series("api_latency_ms", aggregation="sum")
        self.assertEqual(sum_res["aggregate_value"], 300.0)

        # Test min and max
        min_res = self.engine.get_metric_series("api_latency_ms", aggregation="min")
        self.assertEqual(min_res["aggregate_value"], 80.5)

        max_res = self.engine.get_metric_series("api_latency_ms", aggregation="max")
        self.assertEqual(max_res["aggregate_value"], 120.5)

    def test_record_validation(self):
        with self.assertRaises(ValueError):
            self.engine.record_metric("", 10)
        with self.assertRaises(ValueError):
            self.engine.get_metric_series("metric", aggregation="invalid_agg")

    def test_funnel_tracking_and_report(self):
        # User 1 completes all steps
        self.engine.track_funnel_step("signup_funnel", "landing_page", "user_1")
        self.engine.track_funnel_step("signup_funnel", "signup_form", "user_1")
        self.engine.track_funnel_step("signup_funnel", "welcome_page", "user_1")

        # User 2 drops off after form
        self.engine.track_funnel_step("signup_funnel", "landing_page", "user_2")
        self.engine.track_funnel_step("signup_funnel", "signup_form", "user_2")

        # User 3 only lands
        self.engine.track_funnel_step("signup_funnel", "landing_page", "user_3")

        report = self.engine.get_funnel_report("signup_funnel")
        self.assertEqual(report["funnel_name"], "signup_funnel")
        self.assertEqual(len(report["steps"]), 3)

        landing_step = report["steps"][0]
        self.assertEqual(landing_step["step"], "landing_page")
        self.assertEqual(landing_step["unique_users"], 3)
        self.assertEqual(landing_step["conversion_rate_pct"], 100.0)

        welcome_step = report["steps"][2]
        self.assertEqual(welcome_step["step"], "welcome_page")
        self.assertEqual(welcome_step["unique_users"], 1)
        self.assertEqual(welcome_step["conversion_rate_pct"], 33.33)

    def test_list_and_stats(self):
        self.engine.record_metric("cpu_usage", 45.0)
        self.engine.record_metric("memory_usage", 62.0)
        self.engine.track_funnel_step("onboarding", "step_1", "u1")

        metric_names = self.engine.list_metric_names()
        self.assertEqual(len(metric_names), 2)
        self.assertIn("cpu_usage", metric_names)

        stats = self.engine.get_stats()
        self.assertEqual(stats["total_data_points"], 2)
        self.assertEqual(stats["distinct_metrics_count"], 2)
        self.assertEqual(stats["active_funnels_count"], 1)

        self.engine.clear()
        self.assertEqual(len(self.engine.list_metric_names()), 0)


if __name__ == "__main__":
    unittest.main()
