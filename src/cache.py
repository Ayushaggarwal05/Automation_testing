"""
In-memory caching layer with TTL expiration and cache invalidation.
"""

import time
from typing import Dict, Any, Optional, Callable, List


class CacheEntry:
    """Represents a cached entry with expiration timestamp."""

    def __init__(self, value: Any, ttl_seconds: int = 300):
        self.value = value
        self.expires_at = time.time() + ttl_seconds

    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class CacheManager:
    """Thread-safe in-memory cache store."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if present and not expired."""
        entry = self._store.get(key)
        if not entry:
            return None
        if entry.is_expired():
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value with specified or default TTL."""
        ttl_seconds = ttl if ttl is not None else self.default_ttl
        self._store[key] = CacheEntry(value, ttl_seconds)

    def has(self, key: str) -> bool:
        """Check if unexpired key exists in cache."""
        return self.get(key) is not None

    def get_or_set(self, key: str, default_factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """Get existing cached value or compute and store new value."""
        value = self.get(key)
        if value is not None:
            return value
        new_val = default_factory()
        self.set(key, new_val, ttl=ttl)
        return new_val

    def keys(self) -> List[str]:
        """Return all active, non-expired keys."""
        self.cleanup_expired()
        return list(self._store.keys())

    def cleanup_expired(self) -> int:
        """Evict all expired keys and return count of evicted entries."""
        now = time.time()
        expired_keys = [k for k, v in self._store.items() if now > v.expires_at]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)

    def delete(self, key: str) -> bool:
        """Explicitly invalidate a cache key."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        """Flush all cache entries."""
        self._store.clear()

    def size(self) -> int:
        """Count non-expired cache entries."""
        self.cleanup_expired()
        return len(self._store)

