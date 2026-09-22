"""
Audit logging engine supporting tamper-evident cryptographic hash chaining, compliance categorization, and trail integrity verification.
"""

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

try:
    from events import events
except ImportError:
    from src.events import events


VALID_SEVERITIES = {"INFO", "WARNING", "CRITICAL"}
VALID_CATEGORIES = {"AUTH", "DATA_MUTATION", "SYSTEM", "ADMIN", "POLICY_VIOLATION"}


@dataclass
class AuditRecord:
    """Represents an immutable, cryptographically chained audit log entry."""
    id: str
    actor: str
    action: str
    category: str
    severity: str
    details: Dict[str, Any]
    timestamp: float
    previous_hash: str
    record_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditLogManager:
    """Manages recording, searching, exporting, and cryptographic verification of audit records."""

    def __init__(self):
        self._records: List[AuditRecord] = []
        self._last_hash: str = "0" * 64

    def record_event(
        self,
        actor: str,
        action: str,
        category: str = "DATA_MUTATION",
        severity: str = "INFO",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Append an immutable audit entry with SHA-256 hash chaining."""
        if not actor or not actor.strip():
            raise ValueError("Actor cannot be empty.")
        if not action or not action.strip():
            raise ValueError("Action cannot be empty.")
        if category not in VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Valid categories: {sorted(VALID_CATEGORIES)}")
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity '{severity}'. Valid severities: {sorted(VALID_SEVERITIES)}")

        now = time.time()
        record_id = f"aud_{uuid.uuid4().hex[:10]}"
        payload_to_hash = {
            "id": record_id,
            "actor": actor.strip(),
            "action": action.strip(),
            "category": category,
            "severity": severity,
            "details": details or {},
            "timestamp": now,
            "previous_hash": self._last_hash,
        }

        canonical_str = json.dumps(payload_to_hash, sort_keys=True)
        record_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        record = AuditRecord(
            id=record_id,
            actor=actor.strip(),
            action=action.strip(),
            category=category,
            severity=severity,
            details=details or {},
            timestamp=now,
            previous_hash=self._last_hash,
            record_hash=record_hash,
        )

        self._records.append(record)
        self._last_hash = record_hash

        events.publish(
            "audit_event_logged",
            {
                "id": record_id,
                "actor": actor,
                "action": action,
                "category": category,
                "severity": severity,
            },
        )
        return record

    def query_logs(
        self,
        actor: Optional[str] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query audit log entries with optional filters."""
        results = list(self._records)

        if actor:
            results = [r for r in results if actor.lower() in r.actor.lower()]
        if category:
            results = [r for r in results if r.category == category]
        if severity:
            results = [r for r in results if r.severity == severity]

        # Return latest entries first
        results.sort(key=lambda r: r.timestamp, reverse=True)

        if limit is not None and limit > 0:
            results = results[:limit]

        return [r.to_dict() for r in results]

    def verify_integrity(self) -> Dict[str, Any]:
        """Verify cryptographic hash chaining across the entire audit log."""
        expected_prev_hash = "0" * 64
        for idx, record in enumerate(self._records):
            if record.previous_hash != expected_prev_hash:
                return {
                    "valid": False,
                    "error": f"Broken chain at record index {idx} (ID: {record.id})",
                    "verified_records": idx,
                }

            payload_to_hash = {
                "id": record.id,
                "actor": record.actor,
                "action": record.action,
                "category": record.category,
                "severity": record.severity,
                "details": record.details,
                "timestamp": record.timestamp,
                "previous_hash": record.previous_hash,
            }
            canonical_str = json.dumps(payload_to_hash, sort_keys=True)
            recalculated_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

            if recalculated_hash != record.record_hash:
                return {
                    "valid": False,
                    "error": f"Tampered hash at record index {idx} (ID: {record.id})",
                    "verified_records": idx,
                }

            expected_prev_hash = record.record_hash

        return {
            "valid": True,
            "total_verified": len(self._records),
            "latest_root_hash": self._last_hash,
        }

    def export_logs(self, format_type: str = "json") -> Dict[str, Any]:
        """Export audit trail in JSON or CSV format."""
        if format_type.lower() == "csv":
            lines = ["id,timestamp,actor,action,category,severity,record_hash"]
            for r in self._records:
                lines.append(f"{r.id},{r.timestamp},{r.actor},{r.action},{r.category},{r.severity},{r.record_hash}")
            return {"format": "csv", "count": len(self._records), "data": "\n".join(lines)}

        return {
            "format": "json",
            "count": len(self._records),
            "data": [r.to_dict() for r in self._records],
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics of logged audit records."""
        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}

        for r in self._records:
            by_category[r.category] = by_category.get(r.category, 0) + 1
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1

        return {
            "total_records": len(self._records),
            "by_category": by_category,
            "by_severity": by_severity,
            "latest_root_hash": self._last_hash,
        }

    def clear(self) -> None:
        """Clear all audit logs and reset the root hash."""
        self._records.clear()
        self._last_hash = "0" * 64


# Global audit manager instance
audit_logger = AuditLogManager()
