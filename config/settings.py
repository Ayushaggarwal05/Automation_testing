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

    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary (masks sensitive keys)."""
        return {
            "app_name": self.app_name,
            "app_env": self.app_env,
            "debug": self.debug,
            "port": self.port,
            "token_expiry_seconds": self.token_expiry_seconds,
            "secret_key_configured": bool(self.secret_key),
        }

    def is_production(self) -> bool:
        """Check if environment is set to production."""
        return self.app_env.lower() == "production"


# Singleton instance for application-wide access
config = AppConfig()
