"""
Policy enforcement engine supporting Attribute-Based (ABAC) and Role-Based (RBAC) access control evaluation.
"""

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

try:
    from events import events
except ImportError:
    from src.events import events


VALID_EFFECTS = {"ALLOW", "DENY"}


@dataclass
class PolicyRule:
    """Represents a fine-grained access policy rule."""
    id: str
    name: str
    description: str = ""
    effect: str = "ALLOW"  # ALLOW or DENY
    actions: List[str] = field(default_factory=list)  # e.g., ["read", "write", "*"]
    resources: List[str] = field(default_factory=list)  # e.g., ["items", "webhooks", "*"]
    roles: List[str] = field(default_factory=list)  # e.g., ["admin", "user", "*"]
    conditions: Dict[str, Any] = field(default_factory=dict)  # e.g., {"env": "prod", "department": "engineering"}
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    evaluations_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolicyEngine:
    """Evaluates dynamic authorization policies using Deny-Overrides precedence."""

    def __init__(self, default_effect: str = "DENY"):
        self._policies: Dict[str, PolicyRule] = {}
        self.default_effect = default_effect if default_effect in VALID_EFFECTS else "DENY"

    def create_policy(
        self,
        name: str,
        effect: str = "ALLOW",
        actions: Optional[List[str]] = None,
        resources: Optional[List[str]] = None,
        roles: Optional[List[str]] = None,
        conditions: Optional[Dict[str, Any]] = None,
        description: str = "",
    ) -> PolicyRule:
        """Register a new policy rule."""
        if not name or not name.strip():
            raise ValueError("Policy name cannot be empty.")
        if effect not in VALID_EFFECTS:
            raise ValueError(f"Invalid effect '{effect}'. Must be one of {sorted(VALID_EFFECTS)}.")

        policy_id = f"pol_{uuid.uuid4().hex[:10]}"
        policy = PolicyRule(
            id=policy_id,
            name=name.strip(),
            description=description.strip(),
            effect=effect,
            actions=actions or ["*"],
            resources=resources or ["*"],
            roles=roles or ["*"],
            conditions=conditions or {},
            enabled=True,
            created_at=time.time(),
        )
        self._policies[policy_id] = policy

        events.publish("policy_created", {"id": policy_id, "name": name, "effect": effect})
        return policy

    def get_policy(self, policy_id: str) -> Optional[PolicyRule]:
        """Retrieve policy rule by ID."""
        return self._policies.get(policy_id)

    def list_policies(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """List registered access policies."""
        policies = list(self._policies.values())
        if enabled_only:
            policies = [p for p in policies if p.enabled]
        policies.sort(key=lambda p: p.created_at)
        return [p.to_dict() for p in policies]

    def delete_policy(self, policy_id: str) -> bool:
        """Delete an access policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            events.publish("policy_deleted", {"id": policy_id})
            return True
        return False

    def evaluate(
        self,
        subject_role: str,
        action: str,
        resource: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate access decision using Deny-Overrides precedence.
        Returns evaluation result with matched policy IDs and decision (ALLOW/DENY).
        """
        ctx = context or {}
        matched_allow: List[str] = []
        matched_deny: List[str] = []

        for p in self._policies.values():
            if not p.enabled:
                continue

            # Role match
            if "*" not in p.roles and subject_role not in p.roles:
                continue

            # Action match
            if "*" not in p.actions and action not in p.actions:
                continue

            # Resource match
            if "*" not in p.resources and resource not in p.resources:
                continue

            # Conditions match (ABAC)
            condition_met = True
            for k, v in p.conditions.items():
                if ctx.get(k) != v:
                    condition_met = False
                    break

            if not condition_met:
                continue

            p.evaluations_count += 1
            if p.effect == "DENY":
                matched_deny.append(p.id)
            else:
                matched_allow.append(p.id)

        # Deny overrides allow
        if matched_deny:
            decision = "DENY"
            reason = f"Explicit DENY matched policy IDs: {matched_deny}"
        elif matched_allow:
            decision = "ALLOW"
            reason = f"Explicit ALLOW matched policy IDs: {matched_allow}"
        else:
            decision = self.default_effect
            reason = f"Default fallback decision: {self.default_effect}"

        events.publish(
            "policy_evaluated",
            {
                "subject_role": subject_role,
                "action": action,
                "resource": resource,
                "decision": decision,
            },
        )

        return {
            "decision": decision,
            "allowed": decision == "ALLOW",
            "reason": reason,
            "matched_allow": matched_allow,
            "matched_deny": matched_deny,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate policy metrics."""
        total = len(self._policies)
        allow_count = sum(1 for p in self._policies.values() if p.effect == "ALLOW")
        deny_count = sum(1 for p in self._policies.values() if p.effect == "DENY")
        total_evals = sum(p.evaluations_count for p in self._policies.values())

        return {
            "total_policies": total,
            "allow_policies": allow_count,
            "deny_policies": deny_count,
            "total_evaluations": total_evals,
            "default_effect": self.default_effect,
        }

    def clear(self) -> None:
        """Clear all registered policies."""
        self._policies.clear()


# Global policy engine instance
policies = PolicyEngine()
