"""
Webhook notification and event dispatching manager with HMAC signature verification.
"""

import hmac
import hashlib
import json
import time
import uuid
from typing import Dict, Any, List, Optional


class WebhookSubscription:
    """Represents a webhook endpoint subscription."""

    def __init__(self, event_name: str, target_url: str, secret: str = "webhook-secret"):
        self.id = str(uuid.uuid4())
        self.event_name = event_name
        self.target_url = target_url
        self.secret = secret
        self.created_at = time.time()
        self.active = True

    def sign_payload(self, payload: Dict[str, Any]) -> str:
        """Generate HMAC-SHA256 signature for the JSON payload."""
        data = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hmac.new(self.secret.encode("utf-8"), data, hashlib.sha256).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "event_name": self.event_name,
            "target_url": self.target_url,
            "active": self.active,
            "created_at": self.created_at,
        }


class WebhookManager:
    """Manages webhook subscriptions and dispatches delivery events."""

    def __init__(self):
        self._subscriptions: Dict[str, WebhookSubscription] = {}
        self._delivery_log: List[Dict[str, Any]] = []

    def register(self, event_name: str, target_url: str, secret: str = "webhook-secret") -> WebhookSubscription:
        """Register a new webhook subscriber."""
        sub = WebhookSubscription(event_name, target_url, secret)
        self._subscriptions[sub.id] = sub
        return sub

    def unregister(self, subscription_id: str) -> bool:
        """Remove a webhook subscription."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return True
        return False

    def list_subscriptions(self, event_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List active webhook subscriptions."""
        subs = self._subscriptions.values()
        if event_filter:
            subs = [s for s in subs if s.event_name == event_filter]
        return [s.to_dict() for s in subs]

    def dispatch(self, event_name: str, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Dispatch event payload to all matching subscribers (mock delivery)."""
        dispatched = []
        matching = [s for s in self._subscriptions.values() if s.active and s.event_name == event_name]

        for sub in matching:
            signature = sub.sign_payload(payload)
            delivery_record = {
                "delivery_id": str(uuid.uuid4()),
                "subscription_id": sub.id,
                "target_url": sub.target_url,
                "event": event_name,
                "signature": signature,
                "timestamp": time.time(),
                "status": "DELIVERED",
            }
            self._delivery_log.append(delivery_record)
            dispatched.append(delivery_record)

        return dispatched

    def get_delivery_history(self) -> List[Dict[str, Any]]:
        """Retrieve delivery log records."""
        return list(self._delivery_log)


# Global webhook manager instance
webhooks = WebhookManager()
