"""
Middleware pipeline architecture for request processing, rate limiting, and logging.
"""

import time
from typing import Dict, Any, Callable, List, Optional


class RequestContext:
    """Holds request-scoped state across middleware chain."""

    def __init__(self, endpoint: str, token: Optional[str] = None, params: Optional[Dict[str, Any]] = None):
        self.endpoint = endpoint
        self.token = token
        self.params = params or {}
        self.start_time = time.time()
        self.metadata: Dict[str, Any] = {}


class RateLimiter:
    """Sliding window rate limiter per client token/IP."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, identifier: str) -> bool:
        now = time.time()
        if identifier not in self._history:
            self._history[identifier] = []

        # Filter out timestamps older than window
        self._history[identifier] = [
            t for t in self._history[identifier] if now - t < self.window_seconds
        ]

        if len(self._history[identifier]) >= self.max_requests:
            return False

        self._history[identifier].append(now)
        return True

    def configure(self, max_requests: int, window_seconds: int) -> None:
        """Update rate limit threshold and window configuration."""
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def reset(self, identifier: Optional[str] = None) -> bool:
        """Clear rate limit history for a specific identifier or all clients."""
        if identifier:
            if identifier in self._history:
                del self._history[identifier]
                return True
            return False
        self._history.clear()
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Return rate limiter operational metrics."""
        now = time.time()
        active_clients = sum(
            1 for stamps in self._history.values()
            if any(now - t < self.window_seconds for t in stamps)
        )
        total_tracked = sum(len(stamps) for stamps in self._history.values())
        return {
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "active_clients_count": active_clients,
            "total_tracked_requests": total_tracked,
        }


class MiddlewarePipeline:
    """Executes pre- and post-processing middleware hooks."""

    def __init__(self):
        self.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

    def process_request(self, context: RequestContext) -> Optional[Dict[str, Any]]:
        """Pre-processing hook. Returns error dict if request is blocked."""
        client_id = context.token or "anonymous"
        if not self.rate_limiter.is_allowed(client_id):
            return {
                "error": "Rate limit exceeded. Too many requests.",
                "status_code": 429,
            }
        return None

    def get_pipeline_info(self) -> Dict[str, Any]:
        """Return pipeline state and configured middleware handlers."""
        return {
            "rate_limiter": self.rate_limiter.get_stats(),
            "pipeline_enabled": True,
        }
