#!/usr/bin/env python3
"""
Integration test for permanent tokens with existing authentication flows.
Tests compatibility with all existing protected endpoints and rate limiting.
"""

import asyncio
from datetime import datetime, timedelta
import json
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import httpx

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.main import app as main_app


class PermanentTokenIntegrationTest:
    """Test permanent token integration with existing authentication flows."""

    def __init__(self):
        self.app = None
        self.client = None
        self.base_url = "http://testserver"
        self.test_user = {
            "username": "testuser_permanent",
            "email": "test_permanent@example.com",
            "password": "TestPassword123!",
        }
        self.session_token = None
        self.permanent_token = None
        self.permanent_token_id = None

    async def setup(self):
        """Set up test environment."""
        print("🔧 Setting up test environment...")

        # Use the main app
        self.app = main_app

        # Create async client using TestClient approach
        from fastapi.testclient import TestClient

        self.client = TestClient(self.app)

        # Connect to database
        await db_manager.connect()

        print("✅ Test environment ready")

    async def cleanup(self):
        """Clean up test environment."""
        print("🧹 Cleaning up test environment...")

        # Clean up test user and tokens
        try:
            if hasattr(db_manager, "db") and db_manager.db:
                # Remove test user
                await db_manager.db.users.delete_many({"username": self.test_user["username"]})

                # Remove test permanent tokens
                await db_manager.db.permanent_tokens.delete_many({"username": self.test_user["username"]})

                # Remove test audit logs
                await db_manager.db.permanent_token_audit.delete_many({"username": self.test_user["username"]})
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")

        # Close database connection
        await db_manager.disconnect()

        print("✅ Cleanup complete")

    def test_user_registration_and_login(self):
        """Test user registration and login to get session token."""
        print("\n📝 Testing user registration and login...")

        # Register test user
        response = self.client.post("/auth/register", json=self.test_user)
        if response.status_code not in [200, 201]:
            # User might already exist, try to login
            print("ℹ️ User might already exist, attempting login...")
        else:
            print("✅ User registered successfully")

        # Login to get session token
        login_data = {"username": self.test_user["username"], "password": self.test_user["password"]}
        response = self.client.post("/auth/login", data=login_data)

        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return False

        token_data = response.json()
        self.session_token = token_data["access_token"]
        print("✅ Login successful, session token obtained")
        return True

    def test_permanent_token_creation(self):
        """Test permanent token creation using session token."""
        print("\n🔑 Testing permanent token creation...")

        if not self.session_token:
            print("❌ No session token available")
            return False

        headers = {"Authorization": f"Bearer {self.session_token}"}
        token_request = {"description": "Integration Test Token"}

        response = self.client.post("/auth/permanent-tokens", json=token_request, headers=headers)

        if response.status_code != 200:
            print(f"❌ Permanent token creation failed: {response.status_code} - {response.text}")
            return False

        token_data = response.json()
        self.permanent_token = token_data["token"]
        self.permanent_token_id = token_data["token_id"]

        print("✅ Permanent token created successfully")
        print(f"   Token ID: {self.permanent_token_id}")
        return True

    def test_permanent_token_authentication(self):
        """Test using permanent token for authentication."""
        print("\n🔐 Testing permanent token authentication...")

        if not self.permanent_token:
            print("❌ No permanent token available")
            return False

        headers = {"Authorization": f"Bearer {self.permanent_token}"}

        # Test token validation endpoint
        response = self.client.get("/auth/validate-token", headers=headers)

        if response.status_code != 200:
            print(f"❌ Permanent token validation failed: {response.status_code} - {response.text}")
            return False

        user_data = response.json()
        if user_data["username"] != self.test_user["username"]:
            print(f"❌ Token validation returned wrong user: {user_data['username']}")
            return False

        print("✅ Permanent token authentication successful")
        return True

    def test_protected_endpoint_access(self):
        """Test accessing protected endpoints with permanent token."""
        print("\n🛡️ Testing protected endpoint access...")

        if not self.permanent_token:
            print("❌ No permanent token available")
            return False

        headers = {"Authorization": f"Bearer {self.permanent_token}"}

        # Test accessing permanent token list (protected endpoint)
        response = self.client.get("/auth/permanent-tokens", headers=headers)

        if response.status_code != 200:
            print(f"❌ Protected endpoint access failed: {response.status_code} - {response.text}")
            return False

        tokens_data = response.json()
        if not tokens_data.get("tokens"):
            print("❌ No tokens returned from list endpoint")
            return False

        # Verify our token is in the list
        found_token = False
        for token in tokens_data["tokens"]:
            if token["token_id"] == self.permanent_token_id:
                found_token = True
                break

        if not found_token:
            print("❌ Created token not found in list")
            return False

        print("✅ Protected endpoint access successful")
        return True

    def test_rate_limiting_compatibility(self):
        """Test permanent token compatibility with rate limiting."""
        print("\n⏱️ Testing rate limiting compatibility...")

        if not self.permanent_token:
            print("❌ No permanent token available")
            return False

        headers = {"Authorization": f"Bearer {self.permanent_token}"}

        # Make multiple requests to test rate limiting
        success_count = 0
        rate_limited_count = 0

        for i in range(10):
            response = self.client.get("/auth/validate-token", headers=headers)
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:  # Too Many Requests
                rate_limited_count += 1
            import time

            time.sleep(0.1)  # Small delay between requests

        print(f"   Successful requests: {success_count}")
        print(f"   Rate limited requests: {rate_limited_count}")

        if success_count == 0:
            print("❌ No successful requests - rate limiting too aggressive")
            return False

        print("✅ Rate limiting compatibility verified")
        return True

    def test_session_vs_permanent_token_compatibility(self):
        """Test that session tokens and permanent tokens work together."""
        print("\n🔄 Testing session vs permanent token compatibility...")

        if not self.session_token or not self.permanent_token:
            print("❌ Missing required tokens")
            return False

        # Test session token still works
        session_headers = {"Authorization": f"Bearer {self.session_token}"}
        response = self.client.get("/auth/validate-token", headers=session_headers)

        if response.status_code != 200:
            print(f"❌ Session token validation failed: {response.status_code}")
            return False

        # Test permanent token still works
        permanent_headers = {"Authorization": f"Bearer {self.permanent_token}"}
        response = self.client.get("/auth/validate-token", headers=permanent_headers)

        if response.status_code != 200:
            print(f"❌ Permanent token validation failed: {response.status_code}")
            return False

        print("✅ Both token types work together")
        return True

    def test_token_revocation(self):
        """Test permanent token revocation."""
        print("\n🗑️ Testing permanent token revocation...")

        if not self.permanent_token or not self.permanent_token_id:
            print("❌ No permanent token to revoke")
            return False

        # Use session token to revoke permanent token
        headers = {"Authorization": f"Bearer {self.session_token}"}
        response = self.client.delete(f"/auth/permanent-tokens/{self.permanent_token_id}", headers=headers)

        if response.status_code != 200:
            print(f"❌ Token revocation failed: {response.status_code} - {response.text}")
            return False

        # Verify token is no longer valid
        permanent_headers = {"Authorization": f"Bearer {self.permanent_token}"}
        response = self.client.get("/auth/validate-token", headers=permanent_headers)

        if response.status_code == 200:
            print("❌ Revoked token still works")
            return False

        print("✅ Token revocation successful")
        return True

    async def run_all_tests(self):
        """Run all integration tests."""
        print("🚀 Starting Permanent Token Integration Tests")
        print("=" * 60)

        try:
            await self.setup()

            # Run tests in sequence
            tests = [
                ("User Registration and Login", self.test_user_registration_and_login),
                ("Permanent Token Creation", self.test_permanent_token_creation),
                ("Permanent Token Authentication", self.test_permanent_token_authentication),
                ("Protected Endpoint Access", self.test_protected_endpoint_access),
                ("Rate Limiting Compatibility", self.test_rate_limiting_compatibility),
                ("Session vs Permanent Token Compatibility", self.test_session_vs_permanent_token_compatibility),
                ("Token Revocation", self.test_token_revocation),
            ]

            passed = 0
            failed = 0

            for test_name, test_func in tests:
                try:
                    result = test_func()  # Remove await since methods are now synchronous
                    if result:
                        passed += 1
                    else:
                        failed += 1
                        print(f"❌ {test_name} FAILED")
                except Exception as e:
                    failed += 1
                    print(f"❌ {test_name} FAILED with exception: {e}")

            # Print summary
            print("\n" + "=" * 60)
            print("🏁 Integration Test Summary")
            print(f"✅ Passed: {passed}")
            print(f"❌ Failed: {failed}")
            print(f"📊 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")

            if failed == 0:
                print("\n🎉 All integration tests passed!")
                print("✅ Permanent tokens are fully compatible with existing authentication flows")
                return True
            else:
                print(f"\n⚠️ {failed} test(s) failed - review issues above")
                return False

        except Exception as e:
            print(f"❌ Test suite failed with exception: {e}")
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test runner."""
    # Check if permanent tokens are enabled
    if not settings.PERMANENT_TOKENS_ENABLED:
        print("❌ Permanent tokens are disabled in configuration")
        print("   Set PERMANENT_TOKENS_ENABLED=true to run tests")
        return False

    test_runner = PermanentTokenIntegrationTest()
    return await test_runner.run_all_tests()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
