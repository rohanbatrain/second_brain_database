#!/usr/bin/env python3
"""
MCP Authentication Setup Script

This script helps set up proper authentication for the MCP server
in both development and production environments.
"""

import os
import sys
import secrets
import argparse
from pathlib import Path
from typing import Dict, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MCP_Auth_Setup]")


def generate_secure_token(length: int = 64) -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def generate_fernet_key() -> str:
    """Generate a Fernet encryption key."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def generate_jwt_secret(length: int = 64) -> str:
    """Generate a JWT secret key."""
    return secrets.token_urlsafe(length)


def create_development_config() -> Dict[str, Any]:
    """Create development configuration."""
    return {
        "MCP_TRANSPORT": "http",
        "MCP_HTTP_HOST": "0.0.0.0",
        "MCP_HTTP_PORT": "8001",
        "MCP_SECURITY_ENABLED": "false",
        "MCP_REQUIRE_AUTH": "false",
        "MCP_AUDIT_ENABLED": "true",
        "MCP_RATE_LIMIT_ENABLED": "false",
        "MCP_DEBUG_MODE": "true",
        "MCP_AUTH_TOKEN": "dev-mcp-token-12345",
        "ENVIRONMENT": "development",
        "LOG_LEVEL": "DEBUG"
    }


def create_production_config() -> Dict[str, Any]:
    """Create production configuration with secure tokens."""
    return {
        "MCP_TRANSPORT": "http",
        "MCP_HTTP_HOST": "0.0.0.0",
        "MCP_HTTP_PORT": "8001",
        "MCP_SECURITY_ENABLED": "true",
        "MCP_REQUIRE_AUTH": "true",
        "MCP_AUDIT_ENABLED": "true",
        "MCP_RATE_LIMIT_ENABLED": "true",
        "MCP_DEBUG_MODE": "false",
        "MCP_AUTH_TOKEN": generate_secure_token(),
        "SECRET_KEY": generate_jwt_secret(),
        "FERNET_KEY": generate_fernet_key(),
        "ENVIRONMENT": "production",
        "LOG_LEVEL": "INFO"
    }


def update_config_file(config_path: Path, updates: Dict[str, Any]) -> None:
    """Update configuration file with new values."""
    if not config_path.exists():
        logger.error("Configuration file not found: %s", config_path)
        return

    # Read existing config
    lines = []
    with open(config_path, 'r') as f:
        lines = f.readlines()

    # Update or add configuration values
    updated_keys = set()
    for i, line in enumerate(lines):
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key = line.split('=')[0].strip()
            if key in updates:
                lines[i] = f"{key}={updates[key]}\n"
                updated_keys.add(key)

    # Add new keys that weren't found
    for key, value in updates.items():
        if key not in updated_keys:
            lines.append(f"{key}={value}\n")

    # Write updated config
    with open(config_path, 'w') as f:
        f.writelines(lines)

    logger.info("Updated configuration file: %s", config_path)


def setup_development_auth():
    """Set up development authentication."""
    print("🔧 Setting up MCP authentication for development...")

    config_path = Path(".sbd")
    if not config_path.exists():
        config_path = Path(".env")

    if not config_path.exists():
        print("❌ No configuration file found (.sbd or .env)")
        print("Creating .sbd file...")
        config_path = Path(".sbd")

    config = create_development_config()
    update_config_file(config_path, config)

    print("✅ Development authentication configured!")
    print("\n📋 Development Configuration:")
    print("  - Authentication: Disabled")
    print("  - Security: Disabled")
    print("  - Rate Limiting: Disabled")
    print("  - Debug Mode: Enabled")
    print("\n🚀 Start server with: python start_mcp_server.py --transport http")
    print("\n💡 MCP Client Configuration (no auth required):")
    print('  {"mcpServers": {"second-brain": {"url": "http://0.0.0.0:8001/mcp"}}}')


def setup_production_auth():
    """Set up production authentication."""
    print("🔒 Setting up MCP authentication for production...")

    config_path = Path(".sbd")
    if not config_path.exists():
        config_path = Path(".env")

    if not config_path.exists():
        print("❌ No configuration file found (.sbd or .env)")
        print("Creating .sbd file...")
        config_path = Path(".sbd")

    config = create_production_config()
    update_config_file(config_path, config)

    print("✅ Production authentication configured!")
    print("\n📋 Production Configuration:")
    print("  - Authentication: Enabled")
    print("  - Security: Enabled")
    print("  - Rate Limiting: Enabled")
    print("  - Debug Mode: Disabled")
    print(f"\n🔑 Generated MCP Auth Token: {config['MCP_AUTH_TOKEN']}")
    print(f"🔐 Generated JWT Secret: {config['SECRET_KEY']}")
    print(f"🔒 Generated Fernet Key: {config['FERNET_KEY']}")
    print("\n⚠️  IMPORTANT: Save these tokens securely!")
    print("\n🚀 Start server with: python start_mcp_server.py --transport http")
    print("\n💡 MCP Client Configuration (with auth):")
    print(f'  {{"mcpServers": {{"second-brain": {{"url": "http://0.0.0.0:8001/mcp", "headers": {{"Authorization": "Bearer {config["MCP_AUTH_TOKEN"]}"}}}}}}}}')


def test_authentication():
    """Test current authentication configuration."""
    print("🧪 Testing MCP authentication configuration...")

    try:
        from second_brain_database.integrations.mcp.auth_middleware import create_mcp_auth_provider

        auth_provider = create_mcp_auth_provider()

        if auth_provider is None:
            print("✅ Authentication provider: None (development mode)")
            print("  - Transport: STDIO or HTTP with auth disabled")
            print("  - Security: Disabled")
        else:
            print("✅ Authentication provider: Enabled")
            print(f"  - Provider: {auth_provider.name}")
            print("  - Security: Enabled")

        print(f"\n📊 Current Configuration:")
        print(f"  - MCP_TRANSPORT: {settings.MCP_TRANSPORT}")
        print(f"  - MCP_SECURITY_ENABLED: {settings.MCP_SECURITY_ENABLED}")
        print(f"  - MCP_REQUIRE_AUTH: {settings.MCP_REQUIRE_AUTH}")
        print(f"  - Environment: {settings.ENVIRONMENT}")

    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        logger.error("Authentication test failed: %s", e)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Set up MCP authentication for Second Brain Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/setup_mcp_auth.py --development    # Set up for development
  python scripts/setup_mcp_auth.py --production     # Set up for production
  python scripts/setup_mcp_auth.py --test           # Test current configuration
        """
    )

    parser.add_argument(
        "--development",
        action="store_true",
        help="Set up development authentication (disabled)"
    )

    parser.add_argument(
        "--production",
        action="store_true",
        help="Set up production authentication (enabled with secure tokens)"
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Test current authentication configuration"
    )

    args = parser.parse_args()

    if args.development:
        setup_development_auth()
    elif args.production:
        setup_production_auth()
    elif args.test:
        test_authentication()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
