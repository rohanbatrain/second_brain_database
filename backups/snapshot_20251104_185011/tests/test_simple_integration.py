#!/usr/bin/env python3
"""
Simple integration test for permanent tokens with existing authentication flows.
Tests compatibility without complex async/sync mixing.
"""

import os
import sys
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from fastapi.testclient import TestClient

from second_brain_database.config import settings
from second_brain_database.main import app


def test_permanent_token_integration():
    """Test permanent token integration with existing authentication flows."""
    print("🚀 Starting Simple Permanent Token Integration Test")
    print("=" * 60)

    # Check if permanent tokens are enabled
    if not settings.PERMANENT_TOKENS_ENABLED:
        print("❌ Permanent tokens are disabled in configuration")
        print("   Set PERMANENT_TOKENS_ENABLED=true to run tests")
        return False

    client = TestClient(app)

    test_user = {"username": "testuser_simple", "email": "test_simple@example.com", "password": "TestPassword123!"}

    session_token = None
    permanent_token = None
    permanent_token_id = None

    try:
        # Test 1: User Registration and Login
        print("\n📝 Testing user registration and login...")

        # Try to register user (might already exist)
        response = client.post("/auth/register", json=test_user)
        if response.status_code not in [200, 201]:
            print("ℹ️ User might already exist, attempting login...")
        else:
            print("✅ User registered successfully")

        # Login to get session token
        login_data = {"username": test_user["username"], "password": test_user["password"]}
        response = client.post("/auth/login", data=login_data)

        if response.status_code != 200:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return False

        token_data = response.json()
        session_token = token_data["access_token"]
        print("✅ Login successful, session token obtained")

        # Test 2: Permanent Token Creation
        print("\n🔑 Testing permanent token creation...")

        headers = {"Authorization": f"Bearer {session_token}"}
        token_request = {"description": "Simple Integration Test Token"}

        response = client.post("/auth/permanent-tokens", json=token_request, headers=headers)

        if response.status_code != 200:
            print(f"❌ Permanent token creation failed: {response.status_code} - {response.text}")
            return False

        token_data = response.json()
        permanent_token = token_data["token"]
        permanent_token_id = token_data["token_id"]

        print("✅ Permanent token created successfully")
        print(f"   Token ID: {permanent_token_id}")

        # Test 3: Permanent Token Authentication
        print("\n🔐 Testing permanent token authentication...")

        headers = {"Authorization": f"Bearer {permanent_token}"}

        # Test token validation endpoint
        response = client.get("/auth/validate-token", headers=headers)

        if response.status_code != 200:
            print(f"❌ Permanent token validation failed: {response.status_code} - {response.text}")
            return False

        user_data = response.json()
        if user_data["username"] != test_user["username"]:
            print(f"❌ Token validation returned wrong user: {user_data['username']}")
            return False

        print("✅ Permanent token authentication successful")

        # Test 4: Protected Endpoint Access
        print("\n🛡️ Testing protected endpoint access...")

        headers = {"Authorization": f"Bearer {permanent_token}"}

        # Test accessing permanent token list (protected endpoint)
        response = client.get("/auth/permanent-tokens", headers=headers)

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
            if token["token_id"] == permanent_token_id:
                found_token = True
                break

        if not found_token:
            print("❌ Created token not found in list")
            return False

        print("✅ Protected endpoint access successful")

        # Test 5: Session vs Permanent Token Compatibility
        print("\n🔄 Testing session vs permanent token compatibility...")

        # Test session token still works
        session_headers = {"Authorization": f"Bearer {session_token}"}
        response = client.get("/auth/validate-token", headers=session_headers)

        if response.status_code != 200:
            print(f"❌ Session token validation failed: {response.status_code}")
            return False

        # Test permanent token still works
        permanent_headers = {"Authorization": f"Bearer {permanent_token}"}
        response = client.get("/auth/validate-token", headers=permanent_headers)

        if response.status_code != 200:
            print(f"❌ Permanent token validation failed: {response.status_code}")
            return False

        print("✅ Both token types work together")

        # Test 6: Rate Limiting Compatibility
        print("\n⏱️ Testing rate limiting compatibility...")

        headers = {"Authorization": f"Bearer {permanent_token}"}

        # Make multiple requests to test rate limiting
        success_count = 0
        rate_limited_count = 0

        for i in range(5):  # Reduced number for simpler test
            response = client.get("/auth/validate-token", headers=headers)
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:  # Too Many Requests
                rate_limited_count += 1
            time.sleep(0.1)  # Small delay between requests

        print(f"   Successful requests: {success_count}")
        print(f"   Rate limited requests: {rate_limited_count}")

        if success_count == 0:
            print("❌ No successful requests - rate limiting too aggressive")
            return False

        print("✅ Rate limiting compatibility verified")

        # Test 7: Token Revocation
        print("\n🗑️ Testing permanent token revocation...")

        # Use session token to revoke permanent token
        headers = {"Authorization": f"Bearer {session_token}"}
        response = client.delete(f"/auth/permanent-tokens/{permanent_token_id}", headers=headers)

        if response.status_code != 200:
            print(f"❌ Token revocation failed: {response.status_code} - {response.text}")
            return False

        # Verify token is no longer valid
        permanent_headers = {"Authorization": f"Bearer {permanent_token}"}
        response = client.get("/auth/validate-token", headers=permanent_headers)

        if response.status_code == 200:
            print("❌ Revoked token still works")
            return False

        print("✅ Token revocation successful")

        # All tests passed
        print("\n" + "=" * 60)
        print("🏁 Integration Test Summary")
        print("✅ Passed: 7")
        print("❌ Failed: 0")
        print("📊 Success Rate: 100.0%")
        print("\n🎉 All integration tests passed!")
        print("✅ Permanent tokens are fully compatible with existing authentication flows")

        return True

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_permanent_token_integration()
    sys.exit(0 if success else 1)
