#!/usr/bin/env python3
"""
Test MCP Authentication Fix

This script tests the MCP authentication system to ensure it works
properly in both development and production modes.
"""

import asyncio
import json
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.config import settings
from second_brain_database.integrations.mcp.context import clear_mcp_context, get_mcp_user_context, set_mcp_user_context
from second_brain_database.integrations.mcp.security import _create_default_user_context
from second_brain_database.integrations.mcp.server_factory import (
    create_mcp_server,
    get_mcp_server_info,
    mcp_health_check,
    validate_mcp_configuration,
)
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MCP_Auth_Test]")


async def test_default_user_context():
    """Test creating default user context."""
    print("\n🧪 Testing default user context creation...")

    try:
        # Clear any existing context
        clear_mcp_context()

        # Create default user context
        user_context = await _create_default_user_context()

        print(f"✅ Default user context created:")
        print(f"  - User ID: {user_context.user_id}")
        print(f"  - Username: {user_context.username}")
        print(f"  - Role: {user_context.role}")
        print(f"  - Permissions: {user_context.permissions}")
        print(f"  - Token Type: {user_context.token_type}")

        # Set context and try to retrieve it
        set_mcp_user_context(user_context)
        retrieved_context = get_mcp_user_context()

        if retrieved_context.user_id == user_context.user_id:
            print("✅ Context set and retrieved successfully")
        else:
            print("❌ Context retrieval failed")
            return False

        return True

    except Exception as e:
        print(f"❌ Default user context test failed: {e}")
        logger.error("Default user context test failed: %s", e)
        return False
    finally:
        clear_mcp_context()


async def test_server_creation():
    """Test MCP server creation."""
    print("\n🧪 Testing MCP server creation...")

    try:
        # Create server
        server = create_mcp_server("http")

        if server:
            print("✅ MCP server created successfully")

            # Get server info
            info = get_mcp_server_info()
            print(f"  - Name: {info.get('name', 'Unknown')}")
            print(f"  - Version: {info.get('version', 'Unknown')}")
            print(f"  - Transport: {info.get('transport', 'Unknown')}")
            print(f"  - Auth Enabled: {info.get('auth_enabled', False)}")
            print(f"  - Tools: {info.get('tool_count', 0)}")

            return True
        else:
            print("❌ Server creation returned None")
            return False

    except Exception as e:
        print(f"❌ Server creation test failed: {e}")
        logger.error("Server creation test failed: %s", e)
        return False


async def test_configuration_validation():
    """Test configuration validation."""
    print("\n🧪 Testing configuration validation...")

    try:
        validation = validate_mcp_configuration()

        print(f"✅ Configuration validation completed:")
        print(f"  - Valid: {validation['valid']}")
        print(f"  - Issues: {len(validation['issues'])}")
        print(f"  - Warnings: {len(validation['warnings'])}")

        if validation["issues"]:
            print("  Issues found:")
            for issue in validation["issues"]:
                print(f"    - {issue}")

        if validation["warnings"]:
            print("  Warnings found:")
            for warning in validation["warnings"]:
                print(f"    - {warning}")

        return validation["valid"]

    except Exception as e:
        print(f"❌ Configuration validation test failed: {e}")
        logger.error("Configuration validation test failed: %s", e)
        return False


async def test_health_check():
    """Test health check functionality."""
    print("\n🧪 Testing health check...")

    try:
        health = await mcp_health_check()

        print(f"✅ Health check completed:")
        print(f"  - Healthy: {health['healthy']}")
        print(f"  - Components: {len(health.get('components', {}))}")

        for component, status in health.get("components", {}).items():
            status_icon = "✅" if status["status"] == "healthy" else "⚠️" if status["status"] == "warning" else "❌"
            print(f"  - {component}: {status_icon} {status['status']} - {status['details']}")

        return health["healthy"]

    except Exception as e:
        print(f"❌ Health check test failed: {e}")
        logger.error("Health check test failed: %s", e)
        return False


async def test_tool_execution_simulation():
    """Test simulated tool execution with authentication."""
    print("\n🧪 Testing simulated tool execution...")

    try:
        # Clear context
        clear_mcp_context()

        # Create and set default user context
        user_context = await _create_default_user_context()
        set_mcp_user_context(user_context)

        # Simulate tool execution by checking context
        retrieved_context = get_mcp_user_context()

        if retrieved_context and retrieved_context.user_id:
            print("✅ Tool execution simulation successful:")
            print(f"  - User authenticated: {retrieved_context.user_id}")
            print(f"  - Role: {retrieved_context.role}")
            print(f"  - Has admin permission: {'admin' in retrieved_context.permissions}")
            return True
        else:
            print("❌ Tool execution simulation failed - no user context")
            return False

    except Exception as e:
        print(f"❌ Tool execution simulation failed: {e}")
        logger.error("Tool execution simulation failed: %s", e)
        return False
    finally:
        clear_mcp_context()


async def main():
    """Main test function."""
    print("🚀 MCP Authentication Fix Test Suite")
    print("=" * 50)

    print(f"\n📊 Current Configuration:")
    print(f"  - MCP_TRANSPORT: {settings.MCP_TRANSPORT}")
    print(f"  - MCP_SECURITY_ENABLED: {settings.MCP_SECURITY_ENABLED}")
    print(f"  - MCP_REQUIRE_AUTH: {settings.MCP_REQUIRE_AUTH}")
    print(f"  - Environment: {settings.ENVIRONMENT}")
    print(f"  - Debug Mode: {settings.MCP_DEBUG_MODE}")

    # Run tests
    tests = [
        ("Default User Context", test_default_user_context),
        ("Server Creation", test_server_creation),
        ("Configuration Validation", test_configuration_validation),
        ("Health Check", test_health_check),
        ("Tool Execution Simulation", test_tool_execution_simulation),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  - {test_name}: {status}")
        if result:
            passed += 1

    print(f"\n🎯 Overall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! MCP authentication fix is working correctly.")
        print("\n💡 Next steps:")
        print("  1. Restart your MCP server: python start_mcp_server.py --transport http")
        print("  2. Test with a real MCP client")
        print("  3. Try the create_family tool that was failing before")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        print("\n🔧 Troubleshooting:")
        print("  1. Check your .sbd configuration file")
        print("  2. Ensure MongoDB and Redis are running")
        print("  3. Check the logs for detailed error messages")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
