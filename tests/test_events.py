"""
Unit tests for EventDispatcher module.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from events import EventDispatcher


class TestEventDispatcher(unittest.TestCase):
    def setUp(self):
        self.dispatcher = EventDispatcher()

    def test_publish_and_audit_log(self):
        record = self.dispatcher.publish("item_created", {"id": 1, "name": "Item A"})
        self.assertEqual(record["event"], "item_created")
        self.assertEqual(record["payload"]["name"], "Item A")

        log = self.dispatcher.get_audit_log()
        self.assertEqual(len(log), 1)

    def test_subscribe_listener(self):
        received = []

        def sample_listener(evt):
            received.append(evt["payload"]["status"])

        self.dispatcher.subscribe("item_updated", sample_listener)
        self.dispatcher.publish("item_updated", {"id": 1, "status": "completed"})

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], "completed")

    def test_filter_and_clear(self):
        self.dispatcher.publish("event_a", {})
        self.dispatcher.publish("event_b", {})
        self.assertEqual(len(self.dispatcher.get_audit_log("event_a")), 1)
        self.assertEqual(self.dispatcher.count("event_a"), 1)
        self.assertEqual(self.dispatcher.count(), 2)

        self.dispatcher.clear_logs()
        self.assertEqual(len(self.dispatcher.get_audit_log()), 0)
        self.assertEqual(self.dispatcher.count(), 0)

    def test_unsubscribe_and_listener_count(self):
        def listener_one(evt): pass
        def listener_two(evt): pass

        self.assertEqual(self.dispatcher.listener_count(), 0)

        self.dispatcher.subscribe("event_x", listener_one)
        self.dispatcher.subscribe("event_x", listener_two)
        self.dispatcher.subscribe("event_y", listener_one)

        self.assertEqual(self.dispatcher.listener_count(), 3)
        self.assertEqual(self.dispatcher.listener_count("event_x"), 2)
        self.assertEqual(self.dispatcher.listener_count("event_y"), 1)

        self.assertTrue(self.dispatcher.unsubscribe("event_x", listener_one))
        self.assertEqual(self.dispatcher.listener_count("event_x"), 1)

        # Unsubscribing non-existent listener returns False
        self.assertFalse(self.dispatcher.unsubscribe("event_x", listener_one))
        self.assertFalse(self.dispatcher.unsubscribe("non_existent_event", listener_one))


if __name__ == "__main__":
    unittest.main()

