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

    def test_to_dict_keys(self):
        cfg = AppConfig()
        d = cfg.to_dict()
        self.assertIn("app_name", d)
        self.assertIn("app_env", d)
        self.assertIn("default_notification_channel", d)
        self.assertIn("notification_retry_limit", d)
        self.assertIn("workflow_max_steps", d)
        self.assertIn("workflow_execution_timeout_seconds", d)
        self.assertIn("secret_key_configured", d)


if __name__ == "__main__":
    unittest.main()
