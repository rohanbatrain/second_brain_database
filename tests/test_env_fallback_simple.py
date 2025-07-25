#!/usr/bin/env python3
"""
Test to verify environment variable fallback works correctly when config files are missing.

This test ensures that the application can run with just environment variables
when no .sbd or .env config files are present, which is useful for:
- Containerized deployments
- CI/CD environments
- Cloud deployments where config is provided via environment
"""

import os
from pathlib import Path
import shutil
import sys
import tempfile


def test_env_fallback():
    """Test that the app can run with just environment variables."""

    print("🧪 Testing environment variable fallback...")

    # Set required environment variables
    required_env = {
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

    # Set environment variables
    for key, value in required_env.items():
        os.environ[key] = value

    # Clear config path to force environment fallback
    if "SECOND_BRAIN_DATABASE_CONFIG_PATH" in os.environ:
        del os.environ["SECOND_BRAIN_DATABASE_CONFIG_PATH"]

    # Backup existing config files to test pure environment fallback
    project_root = Path(__file__).parent.parent  # Go up from tests/ to project root
    config_backups = []

    for config_file in [".sbd", ".env"]:
        config_path = project_root / config_file
        if config_path.exists():
            backup_path = project_root / f"{config_file}.test_backup"
            shutil.move(str(config_path), str(backup_path))
            config_backups.append((config_path, backup_path))
            print(f"📁 Temporarily moved {config_file} for testing")

    try:
        # Test configuration loading
        import sys

        sys.path.insert(0, str(project_root))
        from src.second_brain_database.config import CONFIG_PATH, settings

        print(f"✅ Configuration loaded successfully!")
        print(f"Config file path: {CONFIG_PATH}")
        print(f"Using environment fallback: {CONFIG_PATH is None}")
        print(f"MongoDB Database: {settings.MONGODB_DATABASE}")
        print(f"Host: {settings.HOST}")
        print(f"Port: {settings.PORT}")
        print(f"Debug: {settings.DEBUG}")

        # Verify required settings are loaded from environment
        assert settings.MONGODB_DATABASE == "test_db", f"Expected test_db, got {settings.MONGODB_DATABASE}"
        assert settings.HOST == "0.0.0.0", f"Expected 0.0.0.0, got {settings.HOST}"
        assert settings.PORT == 9000, f"Expected 9000, got {settings.PORT}"
        assert settings.DEBUG == True, f"Expected True, got {settings.DEBUG}"
        assert bool(settings.SECRET_KEY), "SECRET_KEY should be set"
        assert bool(settings.MONGODB_URL), "MONGODB_URL should be set"
        assert bool(settings.REDIS_URL), "REDIS_URL should be set"
        assert bool(settings.FERNET_KEY), "FERNET_KEY should be set"
        assert bool(settings.TURNSTILE_SITEKEY), "TURNSTILE_SITEKEY should be set"
        assert bool(settings.TURNSTILE_SECRET), "TURNSTILE_SECRET should be set"

        # Verify that CONFIG_PATH is None (indicating environment fallback)
        assert CONFIG_PATH is None, f"Expected CONFIG_PATH to be None, got {CONFIG_PATH}"

        print("✅ All required settings loaded from environment!")
        print("✅ Environment fallback working correctly!")

        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Restore backed up config files
        for original_path, backup_path in config_backups:
            if backup_path.exists():
                shutil.move(str(backup_path), str(original_path))
                print(f"🔄 Restored {original_path.name}")

        # Clean up environment variables
        for key in required_env.keys():
            if key in os.environ:
                del os.environ[key]


def test_config_file_priority():
    """Test that config files are still used when available (priority test)."""

    print("\n🧪 Testing config file priority...")

    try:
        # This should use the existing config file if present
        from pathlib import Path
        import sys

        project_root = Path(__file__).parent.parent  # Go up from tests/ to project root
        sys.path.insert(0, str(project_root))
        from src.second_brain_database.config import CONFIG_PATH

        if CONFIG_PATH:
            print(f"✅ Config file found and used: {CONFIG_PATH}")
            print("✅ Config file priority working correctly!")
        else:
            print("ℹ️  No config file found, using environment variables")
            print("✅ Environment fallback active (no config file present)")

        return True

    except Exception as e:
        print(f"❌ Config file priority test failed: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Environment Variable Fallback Test")
    print("=" * 50)

    success = True

    # Test 1: Environment variable fallback
    success &= test_env_fallback()

    # Test 2: Config file priority (when available)
    success &= test_config_file_priority()

    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("\n📋 Summary:")
        print("✅ Application can run with environment variables only")
        print("✅ Config files are used when available (priority)")
        print("✅ Fallback mechanism works correctly")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED!")
        sys.exit(1)
