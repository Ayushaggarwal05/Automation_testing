"""
Feature flag management and evaluation service supporting percentage rollouts, user/role targeting, and telemetry.
"""

import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

try:
    from events import events
except ImportError:
    from src.events import events


@dataclass
class FeatureFlag:
    """Represents a feature toggle configuration."""
    name: str
    description: str = ""
    enabled: bool = False
    rollout_percentage: int = 100
    allowed_roles: List[str] = field(default_factory=list)
    allowed_users: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    evaluations_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeatureFlagManager:
    """Manages creation, evaluation, targeting rules, and lifecycle of feature flags."""

    def __init__(self):
        self._flags: Dict[str, FeatureFlag] = {}

    def create_flag(
        self,
        name: str,
        description: str = "",
        enabled: bool = False,
        rollout_percentage: int = 100,
        allowed_roles: Optional[List[str]] = None,
        allowed_users: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FeatureFlag:
        """Register a new feature flag with targeting constraints."""
        if not name or not name.strip():
            raise ValueError("Feature flag name cannot be empty.")

        clean_name = name.strip().lower()
        if clean_name in self._flags:
            raise ValueError(f"Feature flag '{clean_name}' already exists.")

        if not 0 <= rollout_percentage <= 100:
            raise ValueError(f"Rollout percentage must be between 0 and 100, got {rollout_percentage}.")

        now = time.time()
        flag = FeatureFlag(
            name=clean_name,
            description=description.strip(),
            enabled=enabled,
            rollout_percentage=rollout_percentage,
            allowed_roles=allowed_roles or [],
            allowed_users=allowed_users or [],
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self._flags[clean_name] = flag

        events.publish("flag_created", {"name": clean_name, "enabled": enabled, "rollout": rollout_percentage})
        return flag

    def get_flag(self, name: str) -> Optional[FeatureFlag]:
        """Retrieve a flag definition by name."""
        return self._flags.get(name.strip().lower())

    def list_flags(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List all registered feature flags."""
        flags = list(self._flags.values())
        if enabled_only:
            flags = [f for f in flags if f.enabled]
        flags.sort(key=lambda f: f.created_at)
        return [f.to_dict() for f in flags]

    def update_flag(
        self,
        name: str,
        enabled: Optional[bool] = None,
        rollout_percentage: Optional[int] = None,
        allowed_roles: Optional[List[str]] = None,
        allowed_users: Optional[List[str]] = None,
    ) -> Optional[FeatureFlag]:
        """Update existing flag configuration."""
        flag = self.get_flag(name)
        if not flag:
            return None

        if enabled is not None:
            flag.enabled = enabled
        if rollout_percentage is not None:
            if not 0 <= rollout_percentage <= 100:
                raise ValueError(f"Rollout percentage must be between 0 and 100, got {rollout_percentage}.")
            flag.rollout_percentage = rollout_percentage
        if allowed_roles is not None:
            flag.allowed_roles = allowed_roles
        if allowed_users is not None:
            flag.allowed_users = allowed_users

        flag.updated_at = time.time()
        events.publish("flag_updated", {"name": flag.name, "enabled": flag.enabled})
        return flag

    def toggle_flag(self, name: str, enabled: Optional[bool] = None) -> Optional[FeatureFlag]:
        """Toggle or explicitly set flag enabled status."""
        flag = self.get_flag(name)
        if not flag:
            return None

        flag.enabled = not flag.enabled if enabled is None else enabled
        flag.updated_at = time.time()
        events.publish("flag_toggled", {"name": flag.name, "enabled": flag.enabled})
        return flag

    def delete_flag(self, name: str) -> bool:
        """Remove a feature flag definition."""
        clean_name = name.strip().lower()
        if clean_name in self._flags:
            del self._flags[clean_name]
            events.publish("flag_deleted", {"name": clean_name})
            return True
        return False

    def evaluate(self, name: str, user_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Evaluate if a flag is active for a given context.
        Considers master switch, whitelist users, whitelist roles, and percentage rollout.
        """
        flag = self.get_flag(name)
        if not flag:
            return {"flag": name, "enabled": False, "reason": "FLAG_NOT_FOUND"}

        flag.evaluations_count += 1
        ctx = user_context or {}
        user = ctx.get("user") or ctx.get("username")
        role = ctx.get("role")

        # 1. Master kill-switch check
        if not flag.enabled:
            return {"flag": flag.name, "enabled": False, "reason": "FLAG_DISABLED"}

        # 2. Specific user whitelist check
        if user and user in flag.allowed_users:
            return {"flag": flag.name, "enabled": True, "reason": "USER_WHITELIST"}

        # 3. Role whitelist check
        if role and role in flag.allowed_roles:
            return {"flag": flag.name, "enabled": True, "reason": "ROLE_WHITELIST"}

        # 4. Percentage rollout evaluation
        if flag.rollout_percentage >= 100:
            return {"flag": flag.name, "enabled": True, "reason": "FULL_ROLLOUT"}
        if flag.rollout_percentage <= 0:
            return {"flag": flag.name, "enabled": False, "reason": "ZERO_ROLLOUT"}

        # Deterministic hashing if user is specified, otherwise default to enabled check
        if user:
            hash_key = f"{flag.name}:{user}".encode("utf-8")
            hash_val = int(hashlib.md5(hash_key).hexdigest(), 16) % 100
            is_enabled = hash_val < flag.rollout_percentage
            return {
                "flag": flag.name,
                "enabled": is_enabled,
                "reason": f"PERCENTAGE_ROLLOUT ({hash_val} < {flag.rollout_percentage})",
            }

        return {"flag": flag.name, "enabled": True, "reason": "DEFAULT_ACTIVE"}

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregate statistics across all flags."""
        total = len(self._flags)
        active_count = sum(1 for f in self._flags.values() if f.enabled)
        total_evals = sum(f.evaluations_count for f in self._flags.values())

        return {
            "total_flags": total,
            "active_flags": active_count,
            "disabled_flags": total - active_count,
            "total_evaluations": total_evals,
        }

    def clear(self) -> None:
        """Clear all registered feature flags."""
        self._flags.clear()


# Global feature flag instance
feature_flags = FeatureFlagManager()
