"""
Unit tests for NotificationManager module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from notifications import NotificationManager, Notification


class TestNotificationManager(unittest.TestCase):
    def setUp(self):
        self.manager = NotificationManager()

    def test_send_valid_notification(self):
        notif = self.manager.send(
            recipient="user@example.com",
            message="Your order has been shipped.",
            channel="email",
            priority="high",
            subject="Order Shipped",
        )
        self.assertIsInstance(notif, Notification)
        self.assertEqual(notif.recipient, "user@example.com")
        self.assertEqual(notif.channel, "email")
        self.assertEqual(notif.priority, "high")
        self.assertEqual(notif.status, "delivered")
        self.assertEqual(notif.subject, "Order Shipped")

    def test_send_invalid_channel(self):
        with self.assertRaises(ValueError):
            self.manager.send("user@example.com", "Hello", channel="invalid_channel")

    def test_send_invalid_priority(self):
        with self.assertRaises(ValueError):
            self.manager.send("user@example.com", "Hello", priority="super_urgent")

    def test_send_empty_recipient_or_message(self):
        with self.assertRaises(ValueError):
            self.manager.send("", "Hello")
        with self.assertRaises(ValueError):
            self.manager.send("user@example.com", "   ")

    def test_list_and_filter_notifications(self):
        self.manager.send("alice@example.com", "Msg 1", channel="slack")
        self.manager.send("bob@example.com", "Msg 2", channel="email")
        self.manager.send("alice@example.com", "Msg 3", channel="sms")

        all_notifs = self.manager.list_notifications()
        self.assertEqual(len(all_notifs), 3)

        slack_notifs = self.manager.list_notifications(channel="slack")
        self.assertEqual(len(slack_notifs), 1)
        self.assertEqual(slack_notifs[0]["recipient"], "alice@example.com")

        alice_notifs = self.manager.list_notifications(recipient="alice")
        self.assertEqual(len(alice_notifs), 2)

    def test_cancel_notification(self):
        notif = self.manager.send("carol@example.com", "Pending alert", channel="email")
        self.assertTrue(self.manager.cancel_notification(notif.id))
        self.assertFalse(self.manager.cancel_notification(notif.id))  # Already cancelled
        self.assertFalse(self.manager.cancel_notification("non_existent_id"))

        retrieved = self.manager.get_notification(notif.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.status, "cancelled")

    def test_retry_notification(self):
        notif = self.manager.send("dave@example.com", "Alert", channel="webhook")
        notif.status = "failed"
        self.assertTrue(self.manager.retry_notification(notif.id))
        self.assertEqual(notif.status, "delivered")
        self.assertEqual(notif.retries, 1)

    def test_get_stats(self):
        self.manager.send("user1@example.com", "Email 1", channel="email", priority="normal")
        self.manager.send("user2@example.com", "Email 2", channel="email", priority="high")
        self.manager.send("user3@example.com", "Slack 1", channel="slack", priority="low")

        stats = self.manager.get_stats()
        self.assertEqual(stats["total_notifications"], 3)
        self.assertEqual(stats["by_channel"]["email"], 2)
        self.assertEqual(stats["by_channel"]["slack"], 1)
        self.assertEqual(stats["by_priority"]["high"], 1)
        self.assertEqual(stats["by_priority"]["normal"], 1)
        self.assertEqual(stats["by_priority"]["low"], 1)

    def test_clear(self):
        self.manager.send("user@example.com", "Hello", channel="email")
        self.assertEqual(len(self.manager.list_notifications()), 1)
        self.manager.clear()
        self.assertEqual(len(self.manager.list_notifications()), 0)


if __name__ == "__main__":
    unittest.main()
