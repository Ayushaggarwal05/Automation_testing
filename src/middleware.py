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
