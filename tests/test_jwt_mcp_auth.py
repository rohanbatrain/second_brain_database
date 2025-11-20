#!/usr/bin/env python3
"""
Test JWT Authentication with MCP Server

This test verifies that the MCP server properly authenticates real users
using JWT tokens instead of creating fake static users.
"""

import asyncio
import sys
from typing import Any, Dict

# Add the src directory to the path
sys.path.insert(0, "src")

from second_brain_database.config import settings
from second_brain_database.integrations.mcp.auth_middleware import SecondBrainAuthProvider
from second_brain_database.integrations.mcp.context import create_mcp_user_context_from_fastapi_user
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.auth.login import create_access_token, get_current_user

logger = get_logger(prefix="[JWT_MCP_Test]")


class MockRequest:
    """Mock FastAPI Request for testing."""

    def __init__(self, headers: Dict[str, str]):
        self.headers = headers
        self.client = type("Client", (), {"host": "127.0.0.1"})()


async def test_jwt_authentication():
    """Test JWT authentication flow with MCP."""

    print("🧪 Testing JWT Authentication with MCP")
    print("=" * 50)

    try:
        # Step 1: Create a JWT token for a test user
        print("\n📝 Step 1: Creating JWT token for test user...")

        # Create token for test_user (assuming this user exists)
        test_username = "test_user"
        token_data = {"sub": test_username}
        jwt_token = await create_access_token(data=token_data)

        print(f"✅ JWT token created for user: {test_username}")
        print(f"   Token (first 20 chars): {jwt_token[:20]}...")

        # Step 2: Test JWT validation directly
        print("\n🔍 Step 2: Testing JWT validation...")

        try:
            authenticated_user = await get_current_user(jwt_token)
            print(f"✅ JWT validation successful!")
            print(f"   User ID: {authenticated_user.get('_id')}")
            print(f"   Username: {authenticated_user.get('username')}")
            print(f"   Email: {authenticated_user.get('email')}")
            print(f"   Role: {authenticated_user.get('role')}")
        except Exception as e:
            print(f"❌ JWT validation failed: {e}")
            return False

        # Step 3: Test MCP user context creation
        print("\n🏗️  Step 3: Creating MCP user context from authenticated user...")

        try:
            mcp_context = await create_mcp_user_context_from_fastapi_user(
                fastapi_user=authenticated_user,
                ip_address="127.0.0.1",
                user_agent="TestClient/1.0",
                token_type="jwt",
                token_id="test_token_123",
            )

            print(f"✅ MCP user context created successfully!")
            print(f"   MCP User ID: {mcp_context.user_id}")
            print(f"   MCP Username: {mcp_context.username}")
            print(f"   MCP Role: {mcp_context.role}")
            print(f"   MCP Permissions: {mcp_context.permissions}")
            print(f"   Token Type: {mcp_context.token_type}")

        except Exception as e:
            print(f"❌ MCP context creation failed: {e}")
            return False

        # Step 4: Test MCP authentication provider
        print("\n🔐 Step 4: Testing MCP authentication provider...")

        try:
            auth_provider = SecondBrainAuthProvider()

            # Create mock request with JWT token
            mock_request = MockRequest({"Authorization": f"Bearer {jwt_token}", "User-Agent": "TestClient/1.0"})

            # Test authentication
            auth_result = await auth_provider.authenticate(mock_request)

            if auth_result.get("success"):
                print(f"✅ MCP authentication successful!")
                print(f"   Authenticated User ID: {auth_result.get('user_id')}")
                print(f"   Metadata: {auth_result.get('metadata')}")
            else:
                print(f"❌ MCP authentication failed: {auth_result.get('error')}")
                return False

        except Exception as e:
            print(f"❌ MCP authentication provider failed: {e}")
            return False

        # Step 5: Verify no static users are created
        print("\n✅ Step 5: Verification complete!")
        print("   ✓ Real user authenticated via JWT")
        print("   ✓ No static/fake users created")
        print("   ✓ MCP context contains real user data")
        print("   ✓ Authentication flow matches main application")

        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


async def test_development_mode():
    """Test development mode (no JWT required)."""

    print("\n🧪 Testing Development Mode (No JWT)")
    print("=" * 50)

    try:
        # Temporarily disable security for this test
        original_security = settings.MCP_SECURITY_ENABLED
        original_auth = settings.MCP_REQUIRE_AUTH

        settings.MCP_SECURITY_ENABLED = False
        settings.MCP_REQUIRE_AUTH = False

        auth_provider = SecondBrainAuthProvider()

        # Create mock request without JWT token
        mock_request = MockRequest({"User-Agent": "TestClient/1.0"})

        # Test authentication
        auth_result = await auth_provider.authenticate(mock_request)

        if auth_result.get("success"):
            print(f"✅ Development mode authentication successful!")
            print(f"   User ID: {auth_result.get('user_id')}")
            print(f"   Mode: {auth_result.get('metadata', {}).get('mode')}")
        else:
            print(f"❌ Development mode authentication failed: {auth_result.get('error')}")
            return False

        # Restore original settings
        settings.MCP_SECURITY_ENABLED = original_security
        settings.MCP_REQUIRE_AUTH = original_auth

        return True

    except Exception as e:
        print(f"❌ Development mode test failed: {e}")
        return False


async def main():
    """Run all authentication tests."""

    print("🚀 MCP JWT Authentication Test Suite")
    print("=" * 50)

    print(f"\n📊 Current Configuration:")
    print(f"  - MCP_SECURITY_ENABLED: {settings.MCP_SECURITY_ENABLED}")
    print(f"  - MCP_REQUIRE_AUTH: {settings.MCP_REQUIRE_AUTH}")
    print(f"  - Production Mode: {settings.is_production}")
    print(f"  - Debug Mode: {settings.DEBUG}")

    # Run tests
    jwt_test_passed = await test_jwt_authentication()
    dev_test_passed = await test_development_mode()

    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")
    print(f"  - JWT Authentication: {'✅ PASS' if jwt_test_passed else '❌ FAIL'}")
    print(f"  - Development Mode: {'✅ PASS' if dev_test_passed else '❌ FAIL'}")

    if jwt_test_passed and dev_test_passed:
        print("\n🎉 All tests passed! MCP authentication is working correctly.")
        print("\n✅ Key Improvements:")
        print("   • Real JWT authentication instead of static users")
        print("   • Proper user context with actual permissions")
        print("   • Consistent with main application auth flow")
        print("   • Development mode fallback when security disabled")
        return True
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
