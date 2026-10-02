"""
Unit tests for StreamRouterEngine module.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.stream_router import StreamRouterEngine, StreamMessage, Subscription


class TestStreamRouterEngine(unittest.TestCase):
    def setUp(self):
        self.router = StreamRouterEngine(default_max_retries=2, retention_limit=50)

    def test_publish_and_poll(self):
        sub = self.router.subscribe(topic_pattern="orders.*", consumer_group="order_processors")
        self.assertEqual(sub.consumer_group, "order_processors")

        msg = self.router.publish(
            topic="orders.created",
            payload={"order_id": "ORD-1", "amount": 100},
            headers={"source": "checkout"},
        )
        self.assertEqual(msg.topic, "orders.created")
        self.assertEqual(msg.status, "PENDING")

        polled = self.router.poll(consumer_group="order_processors", topic="orders.created")
        self.assertEqual(len(polled), 1)
        self.assertEqual(polled[0].id, msg.id)
        self.assertEqual(polled[0].status, "DELIVERED")

    def test_payload_filtering(self):
        self.router.subscribe(
            topic_pattern="events.user",
            consumer_group="vip_group",
            filter_expression={"tier": "VIP"},
        )

        msg1 = self.router.publish("events.user", {"user": "alice", "tier": "VIP"})
        msg2 = self.router.publish("events.user", {"user": "bob", "tier": "REGULAR"})

        vip_polled = self.router.poll(consumer_group="vip_group", topic="events.user")
        self.assertEqual(len(vip_polled), 1)
        self.assertEqual(vip_polled[0].id, msg1.id)

    def test_acknowledgment(self):
        self.router.subscribe(topic_pattern="telemetry", consumer_group="collector")
        msg = self.router.publish("telemetry", {"temp": 22})

        polled = self.router.poll(consumer_group="collector", topic="telemetry")
        self.assertEqual(len(polled), 1)

        ack = self.router.acknowledge(msg.id, "collector")
        self.assertTrue(ack)

        # Polling again should return no unacknowledged messages
        polled_again = self.router.poll(consumer_group="collector", topic="telemetry")
        self.assertEqual(len(polled_again), 0)

    def test_nack_and_dead_letter_queue(self):
        self.router.subscribe(topic_pattern="jobs", consumer_group="workers")
        msg = self.router.publish("jobs", {"task": "heavy_compute"}, max_retries=2)

        # First failure -> retry count 1, status PENDING
        self.router.nack(msg.id, "workers", reason="Temporary timeout")
        self.assertEqual(msg.retry_count, 1)
        self.assertEqual(msg.status, "PENDING")

        # Second failure -> retry count 2 >= max_retries -> DEAD_LETTER
        self.router.nack(msg.id, "workers", reason="Fatal crash")
        self.assertEqual(msg.status, "DEAD_LETTER")

        dlq = self.router.get_dead_letter_queue()
        self.assertEqual(len(dlq), 1)
        self.assertEqual(dlq[0]["message_id"], msg.id)

        # Replay DLQ message
        replayed = self.router.replay_dead_letter(msg.id)
        self.assertTrue(replayed)
        self.assertEqual(msg.status, "PENDING")
        self.assertEqual(msg.retry_count, 0)

    def test_stream_stats(self):
        self.router.subscribe("test.topic", "grp")
        msg = self.router.publish("test.topic", {"data": 123})
        self.router.poll("grp", "test.topic")
        self.router.acknowledge(msg.id, "grp")

        stats = self.router.get_stats()
        self.assertEqual(stats["published_count"], 1)
        self.assertEqual(stats["delivered_count"], 1)
        self.assertEqual(stats["acknowledged_count"], 1)
        self.assertEqual(stats["active_subscriptions"], 1)


if __name__ == "__main__":
    unittest.main()
