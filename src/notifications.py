"""
Notification service managing multi-channel message dispatch and lifecycle tracking.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

try:
    from events import events
except ImportError:
    from src.events import events


VALID_CHANNELS = {"email", "slack", "sms", "webhook", "in_app"}
VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
VALID_STATUSES = {"pending", "delivered", "failed", "cancelled"}


@dataclass
class Notification:
    """Represents a notification dispatch entity."""
    id: str
    recipient: str
    message: str
    channel: str = "email"
    priority: str = "normal"
    status: str = "delivered"
    subject: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    delivered_at: Optional[float] = None
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert notification model to dictionary."""
        return asdict(self)


class NotificationManager:
    """Manages dispatching, tracking, filtering, and lifecycle of notifications."""

    def __init__(self):
        self._notifications: Dict[str, Notification] = {}

    def send(
        self,
        recipient: str,
        message: str,
        channel: str = "email",
        priority: str = "normal",
        subject: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Send or dispatch a notification across supported communication channels."""
        if channel not in VALID_CHANNELS:
            raise ValueError(f"Invalid notification channel '{channel}'. Supported channels: {sorted(VALID_CHANNELS)}")
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}'. Supported priorities: {sorted(VALID_PRIORITIES)}")
        if not recipient or not recipient.strip():
            raise ValueError("Recipient cannot be empty.")
        if not message or not message.strip():
            raise ValueError("Message cannot be empty.")

        notif_id = f"notif_{uuid.uuid4().hex[:10]}"
        now = time.time()
        notification = Notification(
            id=notif_id,
            recipient=recipient.strip(),
            message=message.strip(),
            channel=channel,
            priority=priority,
            status="delivered",
            subject=subject.strip() if subject else None,
            created_at=now,
            delivered_at=now,
            retries=0,
            metadata=metadata or {},
        )
        self._notifications[notif_id] = notification

        events.publish(
            "notification_sent",
            {
                "id": notif_id,
                "recipient": recipient,
                "channel": channel,
                "priority": priority,
            },
        )
        return notification

    def get_notification(self, notification_id: str) -> Optional[Notification]:
        """Retrieve a notification by ID."""
        return self._notifications.get(notification_id)

    def list_notifications(
        self,
        channel: Optional[str] = None,
        status: Optional[str] = None,
        recipient: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List notifications with optional filtering by channel, status, recipient, and limit."""
        results = list(self._notifications.values())

        if channel:
            results = [n for n in results if n.channel == channel]
        if status:
            results = [n for n in results if n.status == status]
        if recipient:
            results = [n for n in results if recipient.lower() in n.recipient.lower()]

        # Sort newest first
        results.sort(key=lambda n: n.created_at, reverse=True)

        if limit is not None and limit > 0:
            results = results[:limit]

        return [n.to_dict() for n in results]

    def cancel_notification(self, notification_id: str) -> bool:
        """Cancel a notification if it exists and is not already cancelled."""
        notification = self._notifications.get(notification_id)
        if not notification or notification.status == "cancelled":
            return False

        notification.status = "cancelled"
        events.publish("notification_cancelled", {"id": notification_id, "recipient": notification.recipient})
        return True

    def retry_notification(self, notification_id: str) -> bool:
        """Retry a failed or pending notification."""
        notification = self._notifications.get(notification_id)
        if not notification:
            return False

        notification.retries += 1
        notification.status = "delivered"
        notification.delivered_at = time.time()
        events.publish("notification_retried", {"id": notification_id, "retries": notification.retries})
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Retrieve aggregated notification delivery metrics."""
        total = len(self._notifications)
        by_channel: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        by_priority: Dict[str, int] = {}

        for n in self._notifications.values():
            by_channel[n.channel] = by_channel.get(n.channel, 0) + 1
            by_status[n.status] = by_status.get(n.status, 0) + 1
            by_priority[n.priority] = by_priority.get(n.priority, 0) + 1

        return {
            "total_notifications": total,
            "by_channel": by_channel,
            "by_status": by_status,
            "by_priority": by_priority,
        }

    def clear(self) -> None:
        """Clear all notifications."""
        self._notifications.clear()


# Global notifications instance
notifications = NotificationManager()
