"""
Secrets Vault management subsystem providing encrypted credential storage, secret versioning, rotation policies, and access control.
"""

import base64
import hashlib
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

try:
    from events import events
except ImportError:
    from src.events import events


@dataclass
class SecretVersion:
    """Represents a specific revision of a secret."""
    version: int
    encrypted_value: str
    created_at: float = field(default_factory=time.time)
    created_by: str = "system"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SecretEntry:
    """Represents a managed secret with versioning and lifecycle controls."""
    name: str
    description: str = ""
    current_version: int = 1
    versions: List[SecretVersion] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    expires_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    access_count: int = 0
    is_revoked: bool = False

    def to_dict(self, mask_value: bool = True) -> Dict[str, Any]:
        data = asdict(self)
        if mask_value:
            data["versions"] = [
                {"version": v["version"], "encrypted_value": "********", "created_at": v["created_at"], "created_by": v["created_by"]}
                for v in data["versions"]
            ]
        return data


class VaultManager:
    """Manages secret lifecycle, encryption simulation, version history, and rotation."""

    def __init__(self, master_key: str = "default-vault-master-key"):
        self._secrets: Dict[str, SecretEntry] = {}
        self._master_key = master_key

    def _encrypt(self, raw_value: str) -> str:
        """Simulate reversible encryption using base64 with cryptographic HMAC envelope."""
        combined = f"{self._master_key}:{raw_value}".encode("utf-8")
        token = base64.b64encode(raw_value.encode("utf-8")).decode("utf-8")
        digest = hashlib.sha256(combined).hexdigest()[:12]
        return f"enc_v1:{digest}:{token}"

    def _decrypt(self, encrypted_value: str) -> str:
        """Decrypt a stored envelope back into plaintext."""
        parts = encrypted_value.split(":")
        if len(parts) != 3 or parts[0] != "enc_v1":
            raise ValueError("Malformed or corrupted secret envelope.")
        raw_b64 = parts[2]
        return base64.b64decode(raw_b64.encode("utf-8")).decode("utf-8")

    def store_secret(
        self,
        name: str,
        value: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        ttl_seconds: Optional[int] = None,
        actor: str = "system",
    ) -> SecretEntry:
        """Store a new secret or create initial version."""
        if not name or not name.strip():
            raise ValueError("Secret name cannot be empty.")
        if not value:
            raise ValueError("Secret value cannot be empty.")

        clean_name = name.strip().lower()
        if clean_name in self._secrets and not self._secrets[clean_name].is_revoked:
            raise ValueError(f"Secret '{clean_name}' already exists. Use rotate_secret instead.")

        now = time.time()
        expires_at = now + ttl_seconds if ttl_seconds else None
        enc_val = self._encrypt(value)
        version_entry = SecretVersion(version=1, encrypted_value=enc_val, created_at=now, created_by=actor)

        entry = SecretEntry(
            name=clean_name,
            description=description.strip(),
            current_version=1,
            versions=[version_entry],
            tags=tags or [],
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        self._secrets[clean_name] = entry

        events.publish("secret_stored", {"name": clean_name, "version": 1, "actor": actor})
        return entry

    def get_secret(
        self, name: str, reveal: bool = False, version: Optional[int] = None
    ) -> Dict[str, Any]:
        """Retrieve a secret, optionally revealing plaintext value."""
        clean_name = name.strip().lower()
        entry = self._secrets.get(clean_name)
        if not entry or entry.is_revoked:
            return {"found": False, "error": f"Secret '{clean_name}' not found or revoked."}

        # Check expiration
        if entry.expires_at and time.time() > entry.expires_at:
            return {"found": False, "error": f"Secret '{clean_name}' has expired."}

        entry.access_count += 1
        target_version = version or entry.current_version
        v_match = next((v for v in entry.versions if v.version == target_version), None)
        if not v_match:
            return {"found": False, "error": f"Version {target_version} not found for secret '{clean_name}'."}

        plaintext = self._decrypt(v_match.encrypted_value) if reveal else "********"
        events.publish("secret_accessed", {"name": clean_name, "version": target_version, "revealed": reveal})

        return {
            "found": True,
            "name": entry.name,
            "version": target_version,
            "value": plaintext,
            "description": entry.description,
            "tags": entry.tags,
            "expires_at": entry.expires_at,
            "is_revoked": entry.is_revoked,
            "created_at": entry.created_at,
        }

    def rotate_secret(
        self, name: str, new_value: str, actor: str = "system"
    ) -> SecretEntry:
        """Rotate secret by creating a new incremented revision."""
        clean_name = name.strip().lower()
        entry = self._secrets.get(clean_name)
        if not entry or entry.is_revoked:
            raise ValueError(f"Cannot rotate non-existent or revoked secret '{clean_name}'.")
        if not new_value:
            raise ValueError("New secret value cannot be empty.")

        now = time.time()
        new_version_num = entry.current_version + 1
        enc_val = self._encrypt(new_value)
        version_entry = SecretVersion(version=new_version_num, encrypted_value=enc_val, created_at=now, created_by=actor)

        entry.versions.append(version_entry)
        entry.current_version = new_version_num
        entry.updated_at = now

        events.publish("secret_rotated", {"name": clean_name, "new_version": new_version_num, "actor": actor})
        return entry

    def revoke_secret(self, name: str, actor: str = "system") -> bool:
        """Revoke and invalidate a secret."""
        clean_name = name.strip().lower()
        entry = self._secrets.get(clean_name)
        if not entry or entry.is_revoked:
            return False

        entry.is_revoked = True
        entry.updated_at = time.time()
        events.publish("secret_revoked", {"name": clean_name, "actor": actor})
        return True

    def list_secrets(self, tag_filter: Optional[str] = None, include_revoked: bool = False) -> List[Dict[str, Any]]:
        """List managed secrets with metadata (values masked)."""
        results = list(self._secrets.values())
        if not include_revoked:
            results = [s for s in results if not s.is_revoked]
        if tag_filter:
            results = [s for s in results if tag_filter in s.tags]
        results.sort(key=lambda s: s.name)
        return [s.to_dict(mask_value=True) for s in results]

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate statistics on stored secrets."""
        total = len(self._secrets)
        active = sum(1 for s in self._secrets.values() if not s.is_revoked)
        revoked = total - active
        total_accesses = sum(s.access_count for s in self._secrets.values())

        return {
            "total_secrets": total,
            "active_secrets": active,
            "revoked_secrets": revoked,
            "total_access_events": total_accesses,
        }

    def clear(self) -> None:
        """Clear all vault secrets."""
        self._secrets.clear()


# Global vault manager instance
vault = VaultManager()
