"""
Unit tests for AppConfig module.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.settings import AppConfig


class TestAppConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = AppConfig()
        self.assertEqual(cfg.app_name, "AutomationTestingApp")
        self.assertEqual(cfg.app_env, "development")
        self.assertFalse(cfg.is_production())
        self.assertEqual(cfg.port, 8000)
        self.assertEqual(cfg.default_notification_channel, "email")
        self.assertEqual(cfg.notification_retry_limit, 3)
        self.assertEqual(cfg.workflow_max_steps, 20)
        self.assertEqual(cfg.workflow_execution_timeout_seconds, 300)
        self.assertEqual(cfg.audit_retention_days, 90)
        self.assertTrue(cfg.audit_tamper_protection_enabled)
        self.assertFalse(cfg.feature_flags_default_enabled)
        self.assertEqual(cfg.feature_flags_eval_cache_ttl, 60)
        self.assertEqual(cfg.circuit_breaker_failure_threshold, 5)
        self.assertEqual(cfg.circuit_breaker_recovery_timeout_seconds, 30.0)
        self.assertEqual(cfg.vault_encryption_algorithm, "AES-256-GCM")
        self.assertEqual(cfg.vault_default_ttl_seconds, 86400)
        self.assertEqual(cfg.scheduler_max_concurrent_jobs, 10)
        self.assertEqual(cfg.scheduler_tick_interval_seconds, 1)
        self.assertEqual(cfg.analytics_max_points, 10000)
        self.assertEqual(cfg.analytics_default_aggregation, "avg")

    def test_to_dict_keys(self):
        cfg = AppConfig()
        d = cfg.to_dict()
        self.assertIn("app_name", d)
        self.assertIn("app_env", d)
        self.assertIn("default_notification_channel", d)
        self.assertIn("notification_retry_limit", d)
        self.assertIn("workflow_max_steps", d)
        self.assertIn("workflow_execution_timeout_seconds", d)
        self.assertIn("audit_retention_days", d)
        self.assertIn("audit_tamper_protection_enabled", d)
        self.assertIn("feature_flags_default_enabled", d)
        self.assertIn("feature_flags_eval_cache_ttl", d)
        self.assertIn("circuit_breaker_failure_threshold", d)
        self.assertIn("circuit_breaker_recovery_timeout_seconds", d)
        self.assertIn("vault_encryption_algorithm", d)
        self.assertIn("vault_default_ttl_seconds", d)
        self.assertIn("scheduler_max_concurrent_jobs", d)
        self.assertIn("scheduler_tick_interval_seconds", d)
        self.assertIn("analytics_max_points", d)
        self.assertIn("analytics_default_aggregation", d)
        self.assertIn("secret_key_configured", d)


if __name__ == "__main__":
    unittest.main()
