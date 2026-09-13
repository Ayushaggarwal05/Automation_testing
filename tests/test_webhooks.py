"""
Unit tests for WebhookManager module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from webhooks import WebhookManager, WebhookSubscription


class TestWebhookManager(unittest.TestCase):
    def setUp(self):
        self.manager = WebhookManager()

    def test_register_and_list(self):
        sub = self.manager.register("item_created", "https://example.com/webhook")
        self.assertEqual(sub.event_name, "item_created")
        self.assertEqual(sub.target_url, "https://example.com/webhook")

        subs = self.manager.list_subscriptions()
        self.assertEqual(len(subs), 1)

    def test_hmac_signing(self):
        sub = WebhookSubscription("item_created", "https://example.com/webhook", secret="test-secret")
        payload = {"id": 1, "name": "Widget"}
        sig1 = sub.sign_payload(payload)
        sig2 = sub.sign_payload(payload)
        self.assertEqual(sig1, sig2)
        self.assertIsInstance(sig1, str)
        self.assertEqual(len(sig1), 64)  # SHA-256 hex length

    def test_dispatch(self):
        self.manager.register("item_created", "https://service1.com/hook")
        self.manager.register("item_created", "https://service2.com/hook")
        self.manager.register("item_deleted", "https://service3.com/hook")

        deliveries = self.manager.dispatch("item_created", {"id": 10})
        self.assertEqual(len(deliveries), 2)
        self.assertTrue(all(d["status"] == "DELIVERED" for d in deliveries))

        history = self.manager.get_delivery_history()
        self.assertEqual(len(history), 2)

    def test_unregister(self):
        sub = self.manager.register("item_updated", "https://example.com/hook")
        self.assertTrue(self.manager.unregister(sub.id))
        self.assertFalse(self.manager.unregister("invalid-id"))
        self.assertEqual(len(self.manager.list_subscriptions()), 0)


if __name__ == "__main__":
    unittest.main()
