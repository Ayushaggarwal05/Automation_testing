"""
Standalone health check and status report script for automations.
"""

import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api import APIService
from config.settings import config


def run_diagnostics() -> int:
    """Run diagnostics on core services."""
    print("=" * 50)
    print(f"Starting diagnostics for {config.app_name} [{config.app_env}]")
    print("=" * 50)

    # Check API health
    api = APIService()
    health = api.health_check()
    print(f"[Health Check] Status: {health.get('status')} | Version: {health.get('version')}")

    if health.get("status") != "ok":
        print("[ERROR] Health check failed!")
        return 1

    # Test Auth flow
    auth_token = api.auth_service.generate_token("health_checker", role="system")
    is_valid = api.auth_service.validate_token(auth_token)
    print(f"[Auth Check] Token generated and validated: {is_valid}")

    if not is_valid:
        print("[ERROR] Auth validation check failed!")
        return 1

    # Check Storage & Middleware Pipeline
    storage_stats = api.get_storage_stats(auth_token)
    print(f"[Storage Check] Type: {storage_stats.get('storage_type')} | Total Items: {storage_stats.get('total_items')}")

    middleware_status = api.get_middleware_status(auth_token)
    print(f"[Middleware Check] Pipeline Status: {middleware_status.get('status_code')}")

    print("=" * 50)
    print("All diagnostic checks PASSED successfully.")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    exit_code = run_diagnostics()
    sys.exit(exit_code)
