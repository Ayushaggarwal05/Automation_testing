"""
Message Bus and Event Stream Routing Subsystem.
Provides topic-based publish/subscribe streaming, consumer group partitioning,
payload filtering, message acknowledgment, Dead-Letter Queue (DLQ), and replay capabilities.
"""

import time
import uuid
import fnmatch
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Set

try:
    from events import events
except ImportError:
    from src.events import events


MESSAGE_STATUSES = {"PENDING", "DELIVERED", "ACKNOWLEDGED", "DEAD_LETTER"}


@dataclass
class StreamMessage:
    """Represents an asynchronous streaming message envelope."""
    id: str
    topic: str
    payload: Dict[str, Any]
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    status: str = "PENDING"
    retry_count: int = 0
    max_retries: int = 3
    acknowledged_by: Set[str] = field(default_factory=set)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "payload": self.payload,
            "headers": self.headers,
            "timestamp": self.timestamp,
            "status": self.status,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "acknowledged_by": list(self.acknowledged_by),
        }


@dataclass
class Subscription:
    """Represents a consumer group topic subscription with optional filtering."""
    id: str
    topic_pattern: str  # e.g., "orders.*", "telemetry.#", "user.created"
    consumer_group: str
    filter_expression: Optional[Dict[str, Any]] = None  # Key-value match on payload
    active: bool = True
    created_at: float = field(default_factory=time.time)

    def matches(self, topic: str, payload: Dict[str, Any]) -> bool:
        """Check if message topic and payload match subscription criteria."""
        if not self.active:
            return False
        # Wildcard matching
        if not fnmatch.fnmatch(topic, self.topic_pattern):
            return False
        # Payload filtering
        if self.filter_expression:
            for k, v in self.filter_expression.items():
                if payload.get(k) != v:
                    return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeadLetterEntry:
    """Represents a failed unacknowledged message routed to the Dead Letter Queue."""
    id: str
    message_id: str
    topic: str
    payload: Dict[str, Any]
    reason: str
    failed_at: float = field(default_factory=time.time)
    replayed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StreamRouterEngine:
    """Decentralized in-memory stream router with consumer group partitioning and DLQ."""

    def __init__(self, default_max_retries: int = 3, retention_limit: int = 1000):
        self.default_max_retries = default_max_retries
        self.retention_limit = retention_limit
        self._messages: Dict[str, StreamMessage] = {}
        self._topic_index: Dict[str, List[str]] = {}  # topic -> list of message IDs
        self._subscriptions: Dict[str, Subscription] = {}  # subscription_id -> Subscription
        self._dead_letter_queue: Dict[str, DeadLetterEntry] = {}  # message_id -> DeadLetterEntry
        self._group_offsets: Dict[str, Dict[str, int]] = {}  # group -> {topic: last_read_index}
        self._stats = {
            "published": 0,
            "delivered": 0,
            "acknowledged": 0,
            "dead_lettered": 0,
            "replayed": 0,
        }

    def publish(
        self,
        topic: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        max_retries: Optional[int] = None,
    ) -> StreamMessage:
        """Publish a message to a stream topic."""
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")
        if not isinstance(payload, dict):
            raise ValueError("Payload must be a dictionary.")

        topic = topic.strip()
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        retries = self.default_max_retries if max_retries is None else max_retries

        msg = StreamMessage(
            id=msg_id,
            topic=topic,
            payload=payload,
            headers=headers or {},
            timestamp=time.time(),
            status="PENDING",
            retry_count=0,
            max_retries=retries,
        )

        self._messages[msg_id] = msg
        if topic not in self._topic_index:
            self._topic_index[topic] = []
        self._topic_index[topic].append(msg_id)

        # Enforce retention limit
        if len(self._topic_index[topic]) > self.retention_limit:
            oldest_id = self._topic_index[topic].pop(0)
            self._messages.pop(oldest_id, None)

        self._stats["published"] += 1
        events.publish("stream_message_published", {"id": msg_id, "topic": topic})
        return msg

    def subscribe(
        self,
        topic_pattern: str,
        consumer_group: str,
        filter_expression: Optional[Dict[str, Any]] = None,
    ) -> Subscription:
        """Subscribe a consumer group to a topic pattern."""
        if not topic_pattern or not topic_pattern.strip():
            raise ValueError("Topic pattern cannot be empty.")
        if not consumer_group or not consumer_group.strip():
            raise ValueError("Consumer group cannot be empty.")

        sub_id = f"sub_{uuid.uuid4().hex[:10]}"
        sub = Subscription(
            id=sub_id,
            topic_pattern=topic_pattern.strip(),
            consumer_group=consumer_group.strip(),
            filter_expression=filter_expression,
            active=True,
            created_at=time.time(),
        )

        self._subscriptions[sub_id] = sub
        events.publish("stream_subscription_created", {"id": sub_id, "consumer_group": consumer_group})
        return sub

    def poll(self, consumer_group: str, topic: str, limit: int = 10) -> List[StreamMessage]:
        """Poll unacknowledged matching messages for a consumer group."""
        if not consumer_group or not consumer_group.strip():
            raise ValueError("Consumer group cannot be empty.")
        if not topic or not topic.strip():
            raise ValueError("Topic cannot be empty.")

        matching_subs = [
            s for s in self._subscriptions.values()
            if s.consumer_group == consumer_group and s.active
        ]

        if not matching_subs:
            # Create ad-hoc subscription if none exists
            self.subscribe(topic, consumer_group)
            matching_subs = [
                s for s in self._subscriptions.values()
                if s.consumer_group == consumer_group and s.active
            ]

        msg_ids = self._topic_index.get(topic, [])
        delivered: List[StreamMessage] = []

        for mid in msg_ids:
            if len(delivered) >= limit:
                break
            msg = self._messages.get(mid)
            if not msg or msg.status == "DEAD_LETTER":
                continue

            if consumer_group in msg.acknowledged_by:
                continue

            # Check if any group subscription matches
            if any(s.matches(topic, msg.payload) for s in matching_subs):
                msg.status = "DELIVERED"
                delivered.append(msg)
                self._stats["delivered"] += 1

        return delivered

    def acknowledge(self, message_id: str, consumer_group: str) -> bool:
        """Acknowledge receipt and processing of a message by a consumer group."""
        msg = self._messages.get(message_id)
        if not msg:
            return False

        msg.acknowledged_by.add(consumer_group)
        msg.status = "ACKNOWLEDGED"
        self._stats["acknowledged"] += 1
        events.publish("stream_message_acknowledged", {"id": message_id, "consumer_group": consumer_group})
        return True

    def nack(self, message_id: str, consumer_group: str, reason: str = "") -> bool:
        """Negative acknowledgment. Increments retry or moves message to DLQ."""
        msg = self._messages.get(message_id)
        if not msg:
            return False

        msg.retry_count += 1
        if msg.retry_count >= msg.max_retries:
            msg.status = "DEAD_LETTER"
            dlq_entry = DeadLetterEntry(
                id=f"dlq_{uuid.uuid4().hex[:10]}",
                message_id=msg.id,
                topic=msg.topic,
                payload=msg.payload,
                reason=reason or f"Exceeded max retries ({msg.max_retries}) by {consumer_group}",
                failed_at=time.time(),
                replayed=False,
            )
            self._dead_letter_queue[msg.id] = dlq_entry
            self._stats["dead_lettered"] += 1
            events.publish("stream_message_dead_lettered", {"id": msg.id, "reason": dlq_entry.reason})
        else:
            msg.status = "PENDING"
            events.publish("stream_message_retry", {"id": msg.id, "retry_count": msg.retry_count})

        return True

    def get_dead_letter_queue(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List messages in the Dead Letter Queue."""
        entries = list(self._dead_letter_queue.values())
        entries.sort(key=lambda e: e.failed_at, reverse=True)
        return [e.to_dict() for e in entries[:limit]]

    def replay_dead_letter(self, message_id: str) -> bool:
        """Replay a message from the Dead Letter Queue back into active stream routing."""
        dlq_entry = self._dead_letter_queue.get(message_id)
        if not dlq_entry or dlq_entry.replayed:
            return False

        msg = self._messages.get(message_id)
        if msg:
            msg.status = "PENDING"
            msg.retry_count = 0
            msg.acknowledged_by.clear()
        else:
            # Recreate envelope if purged
            msg = StreamMessage(
                id=message_id,
                topic=dlq_entry.topic,
                payload=dlq_entry.payload,
                status="PENDING",
                retry_count=0,
                max_retries=self.default_max_retries,
            )
            self._messages[message_id] = msg
            if dlq_entry.topic not in self._topic_index:
                self._topic_index[dlq_entry.topic] = []
            self._topic_index[dlq_entry.topic].append(message_id)

        dlq_entry.replayed = True
        self._stats["replayed"] += 1
        events.publish("stream_dead_letter_replayed", {"id": message_id, "topic": dlq_entry.topic})
        return True

    def list_subscriptions(self, consumer_group: Optional[str] = None) -> List[Dict[str, Any]]:
        """List active topic subscriptions."""
        subs = list(self._subscriptions.values())
        if consumer_group:
            subs = [s for s in subs if s.consumer_group == consumer_group]
        subs.sort(key=lambda s: s.created_at)
        return [s.to_dict() for s in subs]

    def unsubscribe(self, subscription_id: str) -> bool:
        """Cancel an active topic subscription."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            events.publish("stream_unsubscribed", {"id": subscription_id})
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Retrieve aggregated message bus streaming telemetry."""
        return {
            "total_messages": len(self._messages),
            "total_topics": len(self._topic_index),
            "active_subscriptions": len([s for s in self._subscriptions.values() if s.active]),
            "dead_letter_count": len(self._dead_letter_queue),
            "published_count": self._stats["published"],
            "delivered_count": self._stats["delivered"],
            "acknowledged_count": self._stats["acknowledged"],
            "dead_lettered_count": self._stats["dead_lettered"],
            "replayed_count": self._stats["replayed"],
            "default_max_retries": self.default_max_retries,
            "retention_limit": self.retention_limit,
        }

    def clear(self):
        """Reset internal engine state."""
        self._messages.clear()
        self._topic_index.clear()
        self._subscriptions.clear()
        self._dead_letter_queue.clear()
        self._group_offsets.clear()
        for k in self._stats:
            self._stats[k] = 0


# Singleton instance for system-wide access
stream_router = StreamRouterEngine()
