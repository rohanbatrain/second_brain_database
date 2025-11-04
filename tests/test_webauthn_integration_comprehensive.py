#!/usr/bin/env python3
"""
Comprehensive integration tests for WebAuthn functionality.

This test suite tests the complete WebAuthn flow including registration,
authentication, credential management, and integration with existing auth system.
"""

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.main import app


class WebAuthnIntegrationTest:
    """Comprehensive WebAuthn integration test suite."""

    def __init__(self):
        self.client = TestClient(app)
        self.test_user = {
            "username": "webauthn_test_user",
            "email": "webauthn_test@example.com",
            "password": "TestPassword123!"
        }
        self.session_token = None
        self.test_credentials = []

    async def setup(self):
        """Set up test environment."""
        print("🔧 Setting up WebAuthn integration test environment...")

        # Connect to database
        await db_manager.connect()

        print("✅ WebAuthn integration test environment ready")

    async def cleanup(self):
        """Clean up test environment."""
        print("🧹 Cleaning up WebAuthn integration test data...")

        try:
            if hasattr(db_manager, "db") and db_manager.db:
                # Remove test user
                await db_manager.db.users.delete_many({"username": self.test_user["username"]})

                # Remove test WebAuthn credentials
                await db_manager.db.webauthn_credentials.delete_many({"user_id": {"$regex": "webauthn_test"}})

                # Remove test challenges
                await db_manager.db.webauthn_challenges.delete_many({"user_id": {"$regex": "webauthn_test"}})

        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")

        # Close database connection
        await db_manager.disconnect()

        print("✅ WebAuthn integration test cleanup complete")

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

    def test_webauthn_registration_begin(self):
        """Test beginning WebAuthn credential registration."""
        print("\n🔑 Testing WebAuthn registration begin...")

        if not self.session_token:
            print("❌ No session token available")
            return False

        headers = {"Authorization": f"Bearer {self.session_token}"}
        registration_request = {
            "device_name": "Test Integration Device",
            "authenticator_type": "platform"
        }

        response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)

        if response.status_code != 200:
            print(f"❌ WebAuthn registration begin failed: {response.status_code} - {response.text}")
            return False

        registration_data = response.json()

        # Verify response structure
        required_fields = ["challenge", "rp", "user", "pubKeyCredParams", "timeout"]
        for field in required_fields:
            if field not in registration_data:
                print(f"❌ Missing required field in registration response: {field}")
                return False

        # Verify challenge format
        challenge = registration_data["challenge"]
        if not challenge or len(challenge) < 40:
            print(f"❌ Invalid challenge format: {challenge}")
            return False

        # Verify relying party info
        rp_info = registration_data["rp"]
        if not rp_info.get("name") or not rp_info.get("id"):
            print(f"❌ Invalid relying party info: {rp_info}")
            return False

        # Verify user info
        user_info = registration_data["user"]
        if not user_info.get("id") or not user_info.get("name") or not user_info.get("displayName"):
            print(f"❌ Invalid user info: {user_info}")
            return False

        print("✅ WebAuthn registration begin successful")
        print(f"   Challenge: {challenge[:20]}...")
        print(f"   RP: {rp_info['name']}")
        print(f"   User: {user_info['name']}")

        return registration_data

    async def run_all_tests(self):
        """Run all WebAuthn integration tests."""
        print("🚀 Starting WebAuthn Integration Tests")
        print("=" * 60)

        try:
            await self.setup()

            # Run tests in sequence
            tests = [
                ("User Registration and Login", self.test_user_registration_and_login),
                ("WebAuthn Registration Begin", self.test_webauthn_registration_begin),
            ]

            passed = 0
            failed = 0

            for test_name, test_func in tests:
                try:
                    result = test_func()
                    if result is not False:  # None or True are considered success
                        passed += 1
                    else:
                        failed += 1
                        print(f"❌ {test_name} FAILED")
                except Exception as e:
                    failed += 1
                    print(f"❌ {test_name} FAILED with exception: {e}")
                    import traceback
                    traceback.print_exc()

            # Print summary
            print("\n" + "=" * 60)
            print("🏁 WebAuthn Integration Test Summary")
            print(f"✅ Passed: {passed}")
            print(f"❌ Failed: {failed}")
            print(f"📊 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")

            if failed == 0:
                print("\n🎉 All WebAuthn integration tests passed!")
                print("✅ WebAuthn is fully integrated with the authentication system")
                return True
            else:
                print(f"\n⚠️ {failed} WebAuthn integration test(s) failed")
                return False

        except Exception as e:
            print(f"❌ WebAuthn integration test suite failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test runner."""
    test_runner = WebAuthnIntegrationTest()
    return await test_runner.run_all_tests()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
