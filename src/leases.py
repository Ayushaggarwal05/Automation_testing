"""
Distributed Lease and Resource Locking Subsystem.
Implements mutual exclusion, fencing tokens, lease heartbeat renewals,
graceful expiry, forced break overrides, and concurrency telemetry.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

try:
    from events import events
except ImportError:
    from src.events import events


@dataclass
class LeaseLock:
    """Represents an active or historical distributed lease on a named resource."""
    id: str
    resource_key: str
    holder: str
    fencing_token: int
    lease_duration_seconds: float
    acquired_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    active: bool = True
    renewal_count: int = 0

    def is_expired(self, now: Optional[float] = None) -> bool:
        current_time = now if now is not None else time.time()
        return current_time >= self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LockAcquireResult:
    """Outcome of a lease acquisition request."""
    acquired: bool
    resource_key: str
    holder: str
    fencing_token: Optional[int] = None
    lock: Optional[Dict[str, Any]] = None
    current_holder: Optional[str] = None
    retry_after: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LeaseManager:
    """Manages distributed mutex locks and lease agreements with monotonically increasing fencing tokens."""

    def __init__(
        self,
        default_duration: float = 30.0,
        max_duration: float = 300.0,
        fencing_token_start: int = 1000,
    ):
        self.default_duration = default_duration
        self.max_duration = max_duration
        self._fencing_counter = fencing_token_start
        self._locks: Dict[str, LeaseLock] = {}  # resource_key -> LeaseLock
        self._stats = {
            "acquisitions": 0,
            "renewals": 0,
            "releases": 0,
            "expirations": 0,
            "conflicts": 0,
            "forced_breaks": 0,
        }

    def _next_fencing_token(self) -> int:
        self._fencing_counter += 1
        return self._fencing_counter

    def _clean_expired(self, resource_key: str, now: float) -> None:
        if resource_key in self._locks:
            lock = self._locks[resource_key]
            if lock.active and lock.is_expired(now):
                lock.active = False
                self._stats["expirations"] += 1
                events.publish("lock_expired", {"resource_key": resource_key, "holder": lock.holder})

    def acquire(
        self,
        resource_key: str,
        holder: str,
        duration_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LockAcquireResult:
        """Attempt to acquire an exclusive distributed lease lock on resource_key."""
        if not resource_key or not resource_key.strip():
            raise ValueError("Resource key cannot be empty.")
        if not holder or not holder.strip():
            raise ValueError("Holder identifier cannot be empty.")

        resource_key = resource_key.strip()
        holder = holder.strip()
        now = time.time()

        self._clean_expired(resource_key, now)

        requested_duration = duration_seconds if duration_seconds is not None else self.default_duration
        duration = min(max(0.01, requested_duration), self.max_duration)

        existing = self._locks.get(resource_key)
        if existing and existing.active and not existing.is_expired(now):
            if existing.holder == holder:
                # Re-entrant acquisition treated as renewal
                return self.renew(resource_key, holder, existing.fencing_token, duration)

            self._stats["conflicts"] += 1
            retry_after = round(max(0.01, existing.expires_at - now), 2)
            events.publish("lock_conflict", {"resource_key": resource_key, "requested_by": holder, "held_by": existing.holder})
            return LockAcquireResult(
                acquired=False,
                resource_key=resource_key,
                holder=holder,
                current_holder=existing.holder,
                retry_after=retry_after,
            )

        # Acquire lock
        fencing_token = self._next_fencing_token()
        lock_id = f"lock_{uuid.uuid4().hex[:10]}"
        lock = LeaseLock(
            id=lock_id,
            resource_key=resource_key,
            holder=holder,
            fencing_token=fencing_token,
            lease_duration_seconds=duration,
            acquired_at=now,
            expires_at=now + duration,
            metadata=metadata or {},
            active=True,
            renewal_count=0,
        )

        self._locks[resource_key] = lock
        self._stats["acquisitions"] += 1
        events.publish("lock_acquired", {"resource_key": resource_key, "holder": holder, "fencing_token": fencing_token})

        return LockAcquireResult(
            acquired=True,
            resource_key=resource_key,
            holder=holder,
            fencing_token=fencing_token,
            lock=lock.to_dict(),
        )

    def renew(
        self,
        resource_key: str,
        holder: str,
        fencing_token: int,
        extension_seconds: Optional[float] = None,
    ) -> LockAcquireResult:
        """Renew an active lease before expiration."""
        resource_key = resource_key.strip()
        holder = holder.strip()
        now = time.time()

        self._clean_expired(resource_key, now)

        lock = self._locks.get(resource_key)
        if not lock or not lock.active or lock.is_expired(now):
            return LockAcquireResult(acquired=False, resource_key=resource_key, holder=holder)

        if lock.holder != holder or lock.fencing_token != fencing_token:
            return LockAcquireResult(
                acquired=False,
                resource_key=resource_key,
                holder=holder,
                current_holder=lock.holder,
            )

        ext = extension_seconds if extension_seconds is not None else self.default_duration
        extension = min(max(0.01, ext), self.max_duration)

        lock.expires_at = now + extension
        lock.renewal_count += 1
        self._stats["renewals"] += 1

        events.publish("lease_renewed", {"resource_key": resource_key, "holder": holder, "expires_at": lock.expires_at})
        return LockAcquireResult(
            acquired=True,
            resource_key=resource_key,
            holder=holder,
            fencing_token=lock.fencing_token,
            lock=lock.to_dict(),
        )

    def release(self, resource_key: str, holder: str, fencing_token: int) -> bool:
        """Release a held distributed lease."""
        resource_key = resource_key.strip()
        holder = holder.strip()
        now = time.time()

        lock = self._locks.get(resource_key)
        if not lock or not lock.active:
            return False

        if lock.holder != holder or lock.fencing_token != fencing_token:
            return False

        lock.active = False
        self._stats["releases"] += 1
        events.publish("lock_released", {"resource_key": resource_key, "holder": holder})
        return True

    def inspect(self, resource_key: str) -> Optional[Dict[str, Any]]:
        """Inspect the current lock state of a resource."""
        resource_key = resource_key.strip()
        now = time.time()
        self._clean_expired(resource_key, now)

        lock = self._locks.get(resource_key)
        if not lock:
            return None
        return lock.to_dict()

    def force_break(self, resource_key: str, reason: str = "Admin override") -> bool:
        """Forcefully revoke an active lease on a resource."""
        resource_key = resource_key.strip()
        lock = self._locks.get(resource_key)
        if not lock or not lock.active:
            return False

        lock.active = False
        self._stats["forced_breaks"] += 1
        events.publish("lock_broken", {"resource_key": resource_key, "previous_holder": lock.holder, "reason": reason})
        return True

    def list_active(self) -> List[Dict[str, Any]]:
        """List all currently active leases."""
        now = time.time()
        active_list: List[Dict[str, Any]] = []
        for rk in list(self._locks.keys()):
            self._clean_expired(rk, now)
            lock = self._locks[rk]
            if lock.active and not lock.is_expired(now):
                active_list.append(lock.to_dict())
        active_list.sort(key=lambda l: l["acquired_at"])
        return active_list

    def get_stats(self) -> Dict[str, Any]:
        """Retrieve aggregated distributed lease manager telemetry."""
        now = time.time()
        active_count = len([l for l in self._locks.values() if l.active and not l.is_expired(now)])
        return {
            "active_leases": active_count,
            "total_tracked_resources": len(self._locks),
            "fencing_counter": self._fencing_counter,
            "acquisitions_count": self._stats["acquisitions"],
            "renewals_count": self._stats["renewals"],
            "releases_count": self._stats["releases"],
            "expirations_count": self._stats["expirations"],
            "conflicts_count": self._stats["conflicts"],
            "forced_breaks_count": self._stats["forced_breaks"],
            "default_duration_seconds": self.default_duration,
            "max_duration_seconds": self.max_duration,
        }

    def clear(self):
        """Reset internal lease manager state."""
        self._locks.clear()
        self._fencing_counter = 1000
        for k in self._stats:
            self._stats[k] = 0


# Singleton instance for system-wide access
leases = LeaseManager()
