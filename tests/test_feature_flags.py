"""
Unit tests for FeatureFlagManager module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from feature_flags import FeatureFlagManager, FeatureFlag


class TestFeatureFlagManager(unittest.TestCase):
    def setUp(self):
        self.manager = FeatureFlagManager()

    def test_create_and_get_flag(self):
        flag = self.manager.create_flag(
            name="dark_mode",
            description="Enable dark theme",
            enabled=True,
            rollout_percentage=50,
            allowed_roles=["beta_tester"],
        )
        self.assertIsInstance(flag, FeatureFlag)
        self.assertEqual(flag.name, "dark_mode")
        self.assertTrue(flag.enabled)

        retrieved = self.manager.get_flag("dark_mode")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.description, "Enable dark theme")

    def test_create_duplicate_flag_fails(self):
        self.manager.create_flag(name="new_ui")
        with self.assertRaises(ValueError):
            self.manager.create_flag(name="new_ui")

    def test_create_invalid_rollout(self):
        with self.assertRaises(ValueError):
            self.manager.create_flag(name="bad_rollout", rollout_percentage=150)

    def test_toggle_flag(self):
        flag = self.manager.create_flag(name="feature_x", enabled=False)
        self.assertFalse(flag.enabled)

        toggled = self.manager.toggle_flag("feature_x")
        self.assertTrue(toggled.enabled)

        explicit_toggle = self.manager.toggle_flag("feature_x", enabled=False)
        self.assertFalse(explicit_toggle.enabled)

    def test_evaluation_rules(self):
        # 1. Disabled flag
        self.manager.create_flag(name="disabled_feature", enabled=False)
        eval_res = self.manager.evaluate("disabled_feature", {"user": "alice"})
        self.assertFalse(eval_res["enabled"])
        self.assertEqual(eval_res["reason"], "FLAG_DISABLED")

        # 2. Whitelisted user
        self.manager.create_flag(name="vip_feature", enabled=True, allowed_users=["vip_bob"])
        eval_bob = self.manager.evaluate("vip_feature", {"user": "vip_bob"})
        self.assertTrue(eval_bob["enabled"])
        self.assertEqual(eval_bob["reason"], "USER_WHITELIST")

        # 3. Whitelisted role
        self.manager.create_flag(name="admin_feature", enabled=True, allowed_roles=["admin"])
        eval_admin = self.manager.evaluate("admin_feature", {"role": "admin"})
        self.assertTrue(eval_admin["enabled"])
        self.assertEqual(eval_admin["reason"], "ROLE_WHITELIST")

        # 4. 100% Rollout
        self.manager.create_flag(name="public_feature", enabled=True, rollout_percentage=100)
        eval_public = self.manager.evaluate("public_feature", {"user": "anyone"})
        self.assertTrue(eval_public["enabled"])
        self.assertEqual(eval_public["reason"], "FULL_ROLLOUT")

        # 5. Non-existent flag
        eval_missing = self.manager.evaluate("ghost_flag")
        self.assertFalse(eval_missing["enabled"])
        self.assertEqual(eval_missing["reason"], "FLAG_NOT_FOUND")

    def test_list_and_delete_flags(self):
        self.manager.create_flag(name="flag_a", enabled=True)
        self.manager.create_flag(name="flag_b", enabled=False)

        all_flags = self.manager.list_flags()
        self.assertEqual(len(all_flags), 2)

        enabled_flags = self.manager.list_flags(enabled_only=True)
        self.assertEqual(len(enabled_flags), 1)

        self.assertTrue(self.manager.delete_flag("flag_a"))
        self.assertFalse(self.manager.delete_flag("non_existent"))
        self.assertEqual(len(self.manager.list_flags()), 1)

    def test_stats_and_clear(self):
        self.manager.create_flag(name="f1", enabled=True)
        self.manager.create_flag(name="f2", enabled=False)
        self.manager.evaluate("f1")

        stats = self.manager.get_stats()
        self.assertEqual(stats["total_flags"], 2)
        self.assertEqual(stats["active_flags"], 1)
        self.assertEqual(stats["disabled_flags"], 1)
        self.assertEqual(stats["total_evaluations"], 1)

        self.manager.clear()
        self.assertEqual(len(self.manager.list_flags()), 0)


if __name__ == "__main__":
    unittest.main()
