"""
Configuration management module.
Loads settings from environment variables with sensible defaults.
"""

import os
from typing import Dict, Any


class AppConfig:
    """Application configuration container."""

    def __init__(self):
        self.app_name: str = os.getenv("APP_NAME", "AutomationTestingApp")
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.debug: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
        self.port: int = int(os.getenv("PORT", "8000"))
        self.secret_key: str = os.getenv("SECRET_KEY", "default-insecure-secret-key")
        self.token_expiry_seconds: int = int(os.getenv("TOKEN_EXPIRY_SECONDS", "3600"))
        self.default_notification_channel: str = os.getenv("DEFAULT_NOTIFICATION_CHANNEL", "email")
        self.notification_retry_limit: int = int(os.getenv("NOTIFICATION_RETRY_LIMIT", "3"))
        self.workflow_max_steps: int = int(os.getenv("WORKFLOW_MAX_STEPS", "20"))
        self.workflow_execution_timeout_seconds: int = int(os.getenv("WORKFLOW_EXECUTION_TIMEOUT_SECONDS", "300"))
        self.audit_retention_days: int = int(os.getenv("AUDIT_RETENTION_DAYS", "90"))
        self.audit_tamper_protection_enabled: bool = os.getenv("AUDIT_TAMPER_PROTECTION_ENABLED", "true").lower() in ("true", "1", "yes")
        self.feature_flags_default_enabled: bool = os.getenv("FEATURE_FLAGS_DEFAULT_ENABLED", "false").lower() in ("true", "1", "yes")
        self.feature_flags_eval_cache_ttl: int = int(os.getenv("FEATURE_FLAGS_EVAL_CACHE_TTL", "60"))
        self.circuit_breaker_failure_threshold: int = int(os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "5"))
        self.circuit_breaker_recovery_timeout_seconds: float = float(os.getenv("CIRCUIT_BREAKER_RECOVERY_TIMEOUT_SECONDS", "30.0"))
        self.vault_encryption_algorithm: str = os.getenv("VAULT_ENCRYPTION_ALGORITHM", "AES-256-GCM")
        self.vault_default_ttl_seconds: int = int(os.getenv("VAULT_DEFAULT_TTL_SECONDS", "86400"))
        self.scheduler_max_concurrent_jobs: int = int(os.getenv("SCHEDULER_MAX_CONCURRENT_JOBS", "10"))
        self.scheduler_tick_interval_seconds: int = int(os.getenv("SCHEDULER_TICK_INTERVAL_SECONDS", "1"))
        self.analytics_max_points: int = int(os.getenv("ANALYTICS_MAX_POINTS", "10000"))
        self.analytics_default_aggregation: str = os.getenv("ANALYTICS_DEFAULT_AGGREGATION", "avg")

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary (masks sensitive keys)."""
        return {
            "app_name": self.app_name,
            "app_env": self.app_env,
            "debug": self.debug,
            "port": self.port,
            "token_expiry_seconds": self.token_expiry_seconds,
            "default_notification_channel": self.default_notification_channel,
            "notification_retry_limit": self.notification_retry_limit,
            "workflow_max_steps": self.workflow_max_steps,
            "workflow_execution_timeout_seconds": self.workflow_execution_timeout_seconds,
            "audit_retention_days": self.audit_retention_days,
            "audit_tamper_protection_enabled": self.audit_tamper_protection_enabled,
            "feature_flags_default_enabled": self.feature_flags_default_enabled,
            "feature_flags_eval_cache_ttl": self.feature_flags_eval_cache_ttl,
            "circuit_breaker_failure_threshold": self.circuit_breaker_failure_threshold,
            "circuit_breaker_recovery_timeout_seconds": self.circuit_breaker_recovery_timeout_seconds,
            "vault_encryption_algorithm": self.vault_encryption_algorithm,
            "vault_default_ttl_seconds": self.vault_default_ttl_seconds,
            "scheduler_max_concurrent_jobs": self.scheduler_max_concurrent_jobs,
            "scheduler_tick_interval_seconds": self.scheduler_tick_interval_seconds,
            "analytics_max_points": self.analytics_max_points,
            "analytics_default_aggregation": self.analytics_default_aggregation,
            "secret_key_configured": bool(self.secret_key),
        }

    def is_production(self) -> bool:
        """Check if environment is set to production."""
        return self.app_env.lower() == "production"


# Singleton instance for application-wide access
config = AppConfig()
