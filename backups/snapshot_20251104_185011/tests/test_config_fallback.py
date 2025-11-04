"""
Test configuration fallback mechanism.

This module tests that the application properly falls back to environment variables
when no configuration file is found.
"""

import os
from pathlib import Path
import shutil
import sys

import pytest


@pytest.fixture
def required_env_vars():
    """Fixture providing required environment variables for testing."""
    return {
        "SECRET_KEY": "test-secret-key-for-testing-12345",
        "MONGODB_URL": "mongodb://localhost:27017",
        "MONGODB_DATABASE": "test_db",
        "REDIS_URL": "redis://localhost:6379",
        "FERNET_KEY": "test-fernet-key-32-chars-long-123=",
        "TURNSTILE_SITEKEY": "test-turnstile-sitekey",
        "TURNSTILE_SECRET": "test-turnstile-secret",
        "DEBUG": "true",
        "HOST": "0.0.0.0",
        "PORT": "9000",
    }


def test_environment_variable_fallback(required_env_vars):
    """Test that configuration loads from environment variables when no config file exists."""

    # Set required environment variables
    original_env = dict(os.environ)

    try:
        for key, value in required_env_vars.items():
            os.environ[key] = value

        # Clear config path to force environment fallback
        if "SECOND_BRAIN_DATABASE_CONFIG_PATH" in os.environ:
            del os.environ["SECOND_BRAIN_DATABASE_CONFIG_PATH"]

        # Backup config files temporarily
        project_root = Path(__file__).parent.parent
        config_backups = []

        for config_file in [".sbd", ".env"]:
            config_path = project_root / config_file
            if config_path.exists():
                backup_path = project_root / f"{config_file}.pytest_backup"
                shutil.move(str(config_path), str(backup_path))
                config_backups.append((config_path, backup_path))

        try:
            # Import configuration (should work with environment variables only)
            from src.second_brain_database.config import CONFIG_PATH, settings

            # Verify fallback is working
            assert CONFIG_PATH is None, f"Expected CONFIG_PATH to be None, got: {CONFIG_PATH}"

            # Verify settings are loaded from environment
            assert settings.MONGODB_DATABASE == "test_db"
            assert settings.HOST == "0.0.0.0"
            assert settings.PORT == 9000
            assert settings.DEBUG == True

            # Verify required secret fields are accessible
            assert bool(settings.SECRET_KEY)
            assert bool(settings.MONGODB_URL)
            assert bool(settings.REDIS_URL)

        finally:
            # Restore backed up config files
            for original_path, backup_path in config_backups:
                if backup_path.exists():
                    shutil.move(str(backup_path), str(original_path))

    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


if __name__ == "__main__":
    # Run tests directly if executed as script
    pytest.main([__file__, "-v"])
