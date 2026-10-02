"""
Dynamic Traffic Throttling and Multi-Tier Rate Limiting Subsystem.
Implements Token Bucket and Sliding Window rate limiting algorithms,
client key tracking, tier quotas, temporary blacklisting, and traffic telemetry.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple

try:
    from events import events
except ImportError:
    from src.events import events


SUPPORTED_ALGORITHMS = {"token_bucket", "sliding_window"}
DEFAULT_TIERS = {"anonymous": 20, "standard": 100, "premium": 1000, "internal": 10000}


@dataclass
class ThrottleRule:
    """Represents a rate-limiting rule specification."""
    id: str
    name: str
    capacity: int  # Max burst tokens or max requests per window
    refill_rate: float  # Tokens per second (for token_bucket)
    window_seconds: float = 60.0  # Time window for sliding_window
    algorithm: str = "token_bucket"  # token_bucket or sliding_window
    tier: str = "standard"
    description: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TokenBucketState:
    """Internal state for a client's token bucket."""
    tokens: float
    last_refill: float


@dataclass
class ThrottleDecision:
    """Outcome of a rate-limit evaluation."""
    allowed: bool
    client_key: str
    rule_name: str
    remaining_tokens: int
    reset_in_seconds: float
    is_blacklisted: bool = False
    retry_after: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class TrafficThrottler:
    """Evaluates request rate limits and enforces bandwidth thresholds across client identities."""

    def __init__(
        self,
        default_algorithm: str = "token_bucket",
        default_capacity: int = 100,
        default_refill_rate: float = 10.0,
    ):
        self.default_algorithm = default_algorithm if default_algorithm in SUPPORTED_ALGORITHMS else "token_bucket"
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate

        self._rules: Dict[str, ThrottleRule] = {}
        self._buckets: Dict[str, Dict[str, TokenBucketState]] = {}  # rule_name -> {client_key: TokenBucketState}
        self._sliding_logs: Dict[str, Dict[str, List[float]]] = {}  # rule_name -> {client_key: list of timestamps}
        self._blacklist: Dict[str, Tuple[float, str]] = {}  # client_key -> (expires_at, reason)
        self._total_checks = 0
        self._total_throttled = 0

        # Initialize default rules for standard tiers
        for tier, cap in DEFAULT_TIERS.items():
            rule_id = f"rule_{tier}"
            refill = max(1.0, cap / 60.0)
            self._rules[tier] = ThrottleRule(
                id=rule_id,
                name=tier,
                capacity=cap,
                refill_rate=round(refill, 2),
                window_seconds=60.0,
                algorithm=self.default_algorithm,
                tier=tier,
                description=f"Default {tier} tier throttle rule",
            )

    def register_rule(
        self,
        name: str,
        capacity: int,
        refill_rate: Optional[float] = None,
        window_seconds: float = 60.0,
        algorithm: Optional[str] = None,
        tier: str = "custom",
        description: str = "",
    ) -> ThrottleRule:
        """Register a custom rate-limiting rule."""
        if not name or not name.strip():
            raise ValueError("Rule name cannot be empty.")
        if capacity <= 0:
            raise ValueError("Capacity must be greater than 0.")

        name = name.strip()
        algo = algorithm or self.default_algorithm
        if algo not in SUPPORTED_ALGORITHMS:
            raise ValueError(f"Invalid algorithm '{algo}'. Supported: {sorted(SUPPORTED_ALGORITHMS)}")

        rate = refill_rate if refill_rate is not None else max(0.1, capacity / window_seconds)
        rule_id = f"rule_{uuid.uuid4().hex[:10]}"

        rule = ThrottleRule(
            id=rule_id,
            name=name,
            capacity=capacity,
            refill_rate=round(rate, 2),
            window_seconds=window_seconds,
            algorithm=algo,
            tier=tier,
            description=description.strip(),
            created_at=time.time(),
        )

        self._rules[name] = rule
        events.publish("ratelimit_rule_created", {"id": rule_id, "name": name, "capacity": capacity})
        return rule

    def get_rule(self, rule_name: str) -> Optional[ThrottleRule]:
        """Retrieve rate-limiting rule by name."""
        return self._rules.get(rule_name)

    def list_rules(self) -> List[Dict[str, Any]]:
        """List all registered rate limit rules."""
        rules = list(self._rules.values())
        rules.sort(key=lambda r: r.created_at)
        return [r.to_dict() for r in rules]

    def blacklist_client(self, client_key: str, duration_seconds: float = 300.0, reason: str = "Excessive traffic") -> bool:
        """Place a client identity on the temporary blacklist."""
        if not client_key or not client_key.strip():
            raise ValueError("Client key cannot be empty.")

        client_key = client_key.strip()
        expires_at = time.time() + duration_seconds
        self._blacklist[client_key] = (expires_at, reason)
        events.publish("client_blacklisted", {"client_key": client_key, "duration": duration_seconds, "reason": reason})
        return True

    def unblacklist_client(self, client_key: str) -> bool:
        """Remove a client identity from the temporary blacklist."""
        if client_key in self._blacklist:
            del self._blacklist[client_key]
            events.publish("client_unblacklisted", {"client_key": client_key})
            return True
        return False

    def is_client_blacklisted(self, client_key: str) -> Tuple[bool, Optional[str], float]:
        """Check if client is blacklisted. Returns (is_blacklisted, reason, remaining_ban_time)."""
        if client_key in self._blacklist:
            expires_at, reason = self._blacklist[client_key]
            now = time.time()
            if now < expires_at:
                return True, reason, round(expires_at - now, 2)
            else:
                del self._blacklist[client_key]
        return False, None, 0.0

    def evaluate(self, client_key: str, rule_name: str = "standard", cost: int = 1) -> ThrottleDecision:
        """Evaluate whether a request from client_key is allowed under rule_name."""
        if not client_key or not client_key.strip():
            raise ValueError("Client key cannot be empty.")
        if cost <= 0:
            raise ValueError("Cost must be at least 1.")

        client_key = client_key.strip()
        self._total_checks += 1
        now = time.time()

        # Check blacklist
        blacklisted, reason, remaining_ban = self.is_client_blacklisted(client_key)
        if blacklisted:
            self._total_throttled += 1
            events.publish("ratelimit_exceeded", {"client_key": client_key, "reason": "blacklisted"})
            return ThrottleDecision(
                allowed=False,
                client_key=client_key,
                rule_name=rule_name,
                remaining_tokens=0,
                reset_in_seconds=remaining_ban,
                is_blacklisted=True,
                retry_after=remaining_ban,
            )

        rule = self._rules.get(rule_name)
        if not rule:
            rule = self._rules.get("standard")
            if not rule:
                # Fallback rule
                rule = ThrottleRule(
                    id="fallback",
                    name="fallback",
                    capacity=self.default_capacity,
                    refill_rate=self.default_refill_rate,
                    algorithm=self.default_algorithm,
                )

        if rule.algorithm == "token_bucket":
            return self._evaluate_token_bucket(client_key, rule, cost, now)
        else:
            return self._evaluate_sliding_window(client_key, rule, cost, now)

    def _evaluate_token_bucket(self, client_key: str, rule: ThrottleRule, cost: int, now: float) -> ThrottleDecision:
        if rule.name not in self._buckets:
            self._buckets[rule.name] = {}

        if client_key not in self._buckets[rule.name]:
            self._buckets[rule.name][client_key] = TokenBucketState(tokens=float(rule.capacity), last_refill=now)

        state = self._buckets[rule.name][client_key]

        # Calculate refilled tokens
        elapsed = max(0.0, now - state.last_refill)
        refilled = elapsed * rule.refill_rate
        state.tokens = min(float(rule.capacity), state.tokens + refilled)
        state.last_refill = now

        if state.tokens >= cost:
            state.tokens -= cost
            remaining = int(state.tokens)
            reset_in = round((rule.capacity - state.tokens) / max(0.1, rule.refill_rate), 2)
            return ThrottleDecision(
                allowed=True,
                client_key=client_key,
                rule_name=rule.name,
                remaining_tokens=remaining,
                reset_in_seconds=reset_in,
            )
        else:
            self._total_throttled += 1
            deficit = cost - state.tokens
            retry_after = round(deficit / max(0.1, rule.refill_rate), 2)
            events.publish("ratelimit_exceeded", {"client_key": client_key, "rule": rule.name, "retry_after": retry_after})
            return ThrottleDecision(
                allowed=False,
                client_key=client_key,
                rule_name=rule.name,
                remaining_tokens=int(state.tokens),
                reset_in_seconds=retry_after,
                retry_after=retry_after,
            )

    def _evaluate_sliding_window(self, client_key: str, rule: ThrottleRule, cost: int, now: float) -> ThrottleDecision:
        if rule.name not in self._sliding_logs:
            self._sliding_logs[rule.name] = {}

        if client_key not in self._sliding_logs[rule.name]:
            self._sliding_logs[rule.name][client_key] = []

        timestamps = self._sliding_logs[rule.name][client_key]
        window_start = now - rule.window_seconds

        # Evict timestamps older than the sliding window
        timestamps = [t for t in timestamps if t > window_start]
        self._sliding_logs[rule.name][client_key] = timestamps

        if len(timestamps) + cost <= rule.capacity:
            for _ in range(cost):
                timestamps.append(now)
            remaining = rule.capacity - len(timestamps)
            reset_in = round(rule.window_seconds - (now - timestamps[0]), 2) if timestamps else 0.0
            return ThrottleDecision(
                allowed=True,
                client_key=client_key,
                rule_name=rule.name,
                remaining_tokens=remaining,
                reset_in_seconds=max(0.0, reset_in),
            )
        else:
            self._total_throttled += 1
            oldest = timestamps[0] if timestamps else now
            retry_after = round(rule.window_seconds - (now - oldest), 2)
            events.publish("ratelimit_exceeded", {"client_key": client_key, "rule": rule.name, "retry_after": retry_after})
            return ThrottleDecision(
                allowed=False,
                client_key=client_key,
                rule_name=rule.name,
                remaining_tokens=max(0, rule.capacity - len(timestamps)),
                reset_in_seconds=max(0.0, retry_after),
                retry_after=max(0.1, retry_after),
            )

    def reset_client(self, client_key: str, rule_name: Optional[str] = None) -> bool:
        """Reset rate limit usage for a client."""
        client_key = client_key.strip()
        if rule_name:
            if rule_name in self._buckets and client_key in self._buckets[rule_name]:
                del self._buckets[rule_name][client_key]
            if rule_name in self._sliding_logs and client_key in self._sliding_logs[rule_name]:
                del self._sliding_logs[rule_name][client_key]
        else:
            for rname in self._buckets:
                self._buckets[rname].pop(client_key, None)
            for rname in self._sliding_logs:
                self._sliding_logs[rname].pop(client_key, None)
        events.publish("ratelimit_reset", {"client_key": client_key})
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Retrieve aggregated rate limiting telemetry."""
        allowed_count = self._total_checks - self._total_throttled
        pass_rate = round((allowed_count / max(1, self._total_checks)) * 100, 2)

        return {
            "total_rules": len(self._rules),
            "total_checks": self._total_checks,
            "throttled_checks": self._total_throttled,
            "pass_rate_percent": pass_rate,
            "active_blacklists": len(self._blacklist),
            "default_algorithm": self.default_algorithm,
            "default_capacity": self.default_capacity,
            "default_refill_rate": self.default_refill_rate,
        }

    def clear(self):
        """Reset internal throttler state."""
        self._rules.clear()
        self._buckets.clear()
        self._sliding_logs.clear()
        self._blacklist.clear()
        self._total_checks = 0
        self._total_throttled = 0


# Singleton instance for system-wide access
throttler = TrafficThrottler()
