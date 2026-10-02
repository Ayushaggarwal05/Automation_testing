"""
Unit tests for TrafficThrottler module.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.throttler import TrafficThrottler, ThrottleRule, ThrottleDecision


class TestTrafficThrottler(unittest.TestCase):
    def setUp(self):
        self.throttler = TrafficThrottler(default_capacity=5, default_refill_rate=1.0)

    def test_default_tiers_initialization(self):
        rule = self.throttler.get_rule("standard")
        self.assertIsNotNone(rule)
        self.assertEqual(rule.capacity, 100)

        premium = self.throttler.get_rule("premium")
        self.assertIsNotNone(premium)
        self.assertEqual(premium.capacity, 1000)

    def test_token_bucket_evaluation_and_throttling(self):
        self.throttler.register_rule("burst_test", capacity=3, refill_rate=0.1, algorithm="token_bucket")

        # 3 requests allowed
        d1 = self.throttler.evaluate("user_123", rule_name="burst_test", cost=1)
        self.assertTrue(d1.allowed)
        self.assertEqual(d1.remaining_tokens, 2)

        d2 = self.throttler.evaluate("user_123", rule_name="burst_test", cost=1)
        self.assertTrue(d2.allowed)
        self.assertEqual(d2.remaining_tokens, 1)

        d3 = self.throttler.evaluate("user_123", rule_name="burst_test", cost=1)
        self.assertTrue(d3.allowed)
        self.assertEqual(d3.remaining_tokens, 0)

        # 4th request throttled
        d4 = self.throttler.evaluate("user_123", rule_name="burst_test", cost=1)
        self.assertFalse(d4.allowed)
        self.assertGreater(d4.retry_after, 0)

    def test_sliding_window_evaluation(self):
        self.throttler.register_rule("window_test", capacity=2, window_seconds=10.0, algorithm="sliding_window")

        d1 = self.throttler.evaluate("client_a", rule_name="window_test", cost=1)
        self.assertTrue(d1.allowed)
        self.assertEqual(d1.remaining_tokens, 1)

        d2 = self.throttler.evaluate("client_a", rule_name="window_test", cost=1)
        self.assertTrue(d2.allowed)
        self.assertEqual(d2.remaining_tokens, 0)

        d3 = self.throttler.evaluate("client_a", rule_name="window_test", cost=1)
        self.assertFalse(d3.allowed)

    def test_client_blacklist(self):
        self.throttler.blacklist_client("spammer_ip", duration_seconds=60.0, reason="DDoS pattern")

        decision = self.throttler.evaluate("spammer_ip", rule_name="standard")
        self.assertFalse(decision.allowed)
        self.assertTrue(decision.is_blacklisted)

        # Unblacklist
        unblocked = self.throttler.unblacklist_client("spammer_ip")
        self.assertTrue(unblocked)

        decision_after = self.throttler.evaluate("spammer_ip", rule_name="standard")
        self.assertTrue(decision_after.allowed)

    def test_reset_client(self):
        self.throttler.register_rule("small_cap", capacity=1, refill_rate=0.01)

        d1 = self.throttler.evaluate("user_xyz", rule_name="small_cap")
        self.assertTrue(d1.allowed)

        d2 = self.throttler.evaluate("user_xyz", rule_name="small_cap")
        self.assertFalse(d2.allowed)

        self.throttler.reset_client("user_xyz", rule_name="small_cap")
        d3 = self.throttler.evaluate("user_xyz", rule_name="small_cap")
        self.assertTrue(d3.allowed)

    def test_throttler_stats(self):
        self.throttler.register_rule("stats_rule", capacity=1, refill_rate=0.01)
        self.throttler.evaluate("client_1", rule_name="stats_rule")
        self.throttler.evaluate("client_1", rule_name="stats_rule")  # Throttled

        stats = self.throttler.get_stats()
        self.assertEqual(stats["total_checks"], 2)
        self.assertEqual(stats["throttled_checks"], 1)
        self.assertEqual(stats["pass_rate_percent"], 50.0)


if __name__ == "__main__":
    unittest.main()
