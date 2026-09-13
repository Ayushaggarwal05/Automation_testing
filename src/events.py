"""
Event dispatcher and audit logger for tracking application events.
"""

import time
from typing import List, Dict, Any, Callable


class EventDispatcher:
    """Manages application-wide event publishing and subscriptions."""

    def __init__(self):
        self._listeners: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._audit_log: List[Dict[str, Any]] = []

    def subscribe(self, event_name: str, listener: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback listener for a specific event type."""
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(listener)

    def publish(self, event_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Broadcast an event to all subscribers and append to audit log."""
        event_record = {
            "event": event_name,
            "timestamp": time.time(),
            "payload": payload,
        }
        self._audit_log.append(event_record)

        if event_name in self._listeners:
            for listener in self._listeners[event_name]:
                listener(event_record)

        return event_record

    def get_audit_log(self, event_filter: str = "") -> List[Dict[str, Any]]:
        """Retrieve historical audit log records."""
        if not event_filter:
            return list(self._audit_log)
        return [entry for entry in self._audit_log if entry["event"] == event_filter]

    def clear_logs(self) -> None:
        """Clear all historical audit log records."""
        self._audit_log.clear()


# Global event dispatcher instance
events = EventDispatcher()
