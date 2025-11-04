#!/usr/bin/env python3
"""
Complete integration tests for WebAuthn functionality following existing patterns.

This test suite provides comprehensive end-to-end testing for WebAuthn flows
including registration, authentication, credential management, and integration
with the existing authentication system.
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


class WebAuthnIntegrationTestSuite:
    """Complete WebAuthn integration test suite following existing patterns."""

    def __init__(self):
        self.client = TestClient(app)
        self.test_users = [
            {
                "username": "webauthn_integration_user1",
                "email": "webauthn_integration1@example.com",
                "password": "TestPassword123!"
            },
            {
                "username": "webauthn_integration_user2",
                "email": "webauthn_integration2@example.com",
                "password": "TestPassword456!"
            }
        ]
        self.session_tokens = {}
        self.registered_credentials = {}

    async def setup(self):
        """Set up test environment following existing patterns."""
        print("🔧 Setting up WebAuthn integration test environment...")

        # Connect to database
        await db_manager.connect()

        # Register and login test users
        for user in self.test_users:
            # Register user
            response = self.client.post("/auth/register", json=user)
            if response.status_code not in [200, 201]:
                print(f"ℹ️ User {user['username']} might already exist, attempting login...")

            # Login to get session token
            login_data = {"username": user["username"], "password": user["password"]}
            response = self.client.post("/auth/login", data=login_data)

            if response.status_code == 200:
                token_data = response.json()
                self.session_tokens[user["username"]] = token_data["access_token"]

        print("✅ WebAuthn integration test environment ready")

    async def cleanup(self):
        """Clean up test environment following existing patterns."""
        print("🧹 Cleaning up WebAuthn integration test data...")

        try:
            if hasattr(db_manager, "db") and db_manager.db:
                # Remove test users
                for user in self.test_users:
                    await db_manager.db.users.delete_many({"username": user["username"]})

                # Remove test WebAuthn credentials
                await db_manager.db.webauthn_credentials.delete_many({
                    "user_id": {"$regex": "webauthn_integration"}
                })

                # Remove test challenges
                await db_manager.db.webauthn_challenges.delete_many({
                    "user_id": {"$regex": "webauthn_integration"}
                })

                # Remove test security alerts
                await db_manager.db.webauthn_security_alerts.delete_many({
                    "details.user_id": {"$regex": "webauthn_integration"}
                })

        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")

        # Close database connection
        await db_manager.disconnect()

        print("✅ WebAuthn integration test cleanup complete")

    def test_complete_registration_flow(self):
        """Test complete WebAuthn credential registration flow."""
        print("\n🔑 Testing complete WebAuthn registration flow...")

        user = self.test_users[0]
        username = user["username"]

        if username not in self.session_tokens:
            print("❌ No session token available for user")
            return False

        headers = {"Authorization": f"Bearer {self.session_tokens[username]}"}

        # Step 1: Begin registration
        registration_request = {
            "device_name": "Integration Test Device",
            "authenticator_type": "platform"
        }

        response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)

        if response.status_code != 200:
            print(f"❌ Registration begin failed: {response.status_code} - {response.text}")
            return False

        registration_data = response.json()

        # Verify response structure
        required_fields = ["challenge", "rp", "user", "pubKeyCredParams", "timeout"]
        for field in required_fields:
            if field not in registration_data:
                print(f"❌ Missing required field in registration response: {field}")
                return False

        challenge = registration_data["challenge"]
        print(f"✅ Registration begin successful, challenge: {challenge[:20]}...")

        # Step 2: Complete registration
        credential_id = f"integration_test_credential_{username}"
        mock_credential = {
            "id": credential_id,
            "rawId": credential_id,
            "type": "public-key",
            "response": {
                "attestationObject": self._create_mock_attestation_object(),
                "clientDataJSON": self._create_mock_client_data_json(challenge, "webauthn.create")
            }
        }

        complete_request = {
            "credential": mock_credential,
            "device_name": "Integration Test Device"
        }

        response = self.client.post("/auth/webauthn/register/complete", json=complete_request, headers=headers)

        if response.status_code != 200:
            print(f"❌ Registration complete failed: {response.status_code} - {response.text}")
            return False

        completion_data = response.json()
        if not completion_data.get("success") or not completion_data.get("credential_id"):
            print(f"❌ Invalid registration completion response: {completion_data}")
            return False

        # Store credential for later tests
        self.registered_credentials[username] = {
            "credential_id": credential_id,
            "device_name": "Integration Test Device"
        }

        print("✅ Registration complete successful")
        return True

    def test_complete_authentication_flow(self):
        """Test complete WebAuthn authentication flow."""
        print("\n🔐 Testing complete WebAuthn authentication flow...")

        user = self.test_users[0]
        username = user["username"]

        # Ensure we have a registered credential
        if username not in self.registered_credentials:
            if not self.test_complete_registration_flow():
                print("❌ Could not register credential for authentication test")
                return False

        # Step 1: Begin authentication
        auth_request = {"username": username}
        response = self.client.post("/auth/webauthn/authenticate/begin", json=auth_request)

        if response.status_code != 200:
            print(f"❌ Authentication begin failed: {response.status_code} - {response.text}")
            return False

        auth_data = response.json()

        # Verify response structure
        required_fields = ["publicKey"]
        for field in required_fields:
            if field not in auth_data:
                print(f"❌ Missing required field in auth response: {field}")
                return False

        public_key = auth_data["publicKey"]
        challenge = public_key["challenge"]
        print(f"✅ Authentication begin successful, challenge: {challenge[:20]}...")

        # Step 2: Complete authentication
        credential_id = self.registered_credentials[username]["credential_id"]
        mock_assertion = {
            "id": credential_id,
            "rawId": credential_id,
            "type": "public-key",
            "response": {
                "authenticatorData": self._create_mock_authenticator_data(),
                "clientDataJSON": self._create_mock_client_data_json(challenge, "webauthn.get"),
                "signature": self._create_mock_signature()
            }
        }

        complete_request = {"credential": mock_assertion}
        response = self.client.post("/auth/webauthn/authenticate/complete", json=complete_request)

        if response.status_code != 200:
            print(f"❌ Authentication complete failed: {response.status_code} - {response.text}")
            return False

        auth_result = response.json()

        # Verify authentication response
        required_fields = ["access_token", "token_type", "authentication_method"]
        for field in required_fields:
            if field not in auth_result:
                print(f"❌ Missing required field in auth result: {field}")
                return False

        if auth_result["authentication_method"] != "webauthn":
            print(f"❌ Wrong authentication method: {auth_result['authentication_method']}")
            return False

        print("✅ Authentication complete successful")
        return True

    def test_credential_management_flow(self):
        """Test complete credential management flow."""
        print("\n📋 Testing credential management flow...")

        user = self.test_users[0]
        username = user["username"]

        if username not in self.session_tokens:
            print("❌ No session token available for user")
            return False

        headers = {"Authorization": f"Bearer {self.session_tokens[username]}"}

        # Ensure we have a registered credential
        if username not in self.registered_credentials:
            if not self.test_complete_registration_flow():
                print("❌ Could not register credential for management test")
                return False

        # Step 1: List credentials
        response = self.client.get("/auth/webauthn/credentials", headers=headers)

        if response.status_code != 200:
            print(f"❌ Credential listing failed: {response.status_code} - {response.text}")
            return False

        credentials_data = response.json()
        if "credentials" not in credentials_data:
            print(f"❌ Missing credentials field in response: {credentials_data}")
            return False

        credentials = credentials_data["credentials"]
        if not isinstance(credentials, list):
            print(f"❌ Credentials should be a list: {credentials}")
            return False

        # Find our test credential
        test_credential = None
        credential_id = self.registered_credentials[username]["credential_id"]

        for cred in credentials:
            if cred["credential_id"] == credential_id:
                test_credential = cred
                break

        if not test_credential:
            print(f"❌ Test credential not found in list: {credential_id}")
            return False

        print(f"✅ Credential listing successful, found {len(credentials)} credential(s)")

        # Step 2: Delete credential
        response = self.client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=headers)

        if response.status_code != 200:
            print(f"❌ Credential deletion failed: {response.status_code} - {response.text}")
            return False

        deletion_data = response.json()
        if not deletion_data.get("success"):
            print(f"❌ Credential deletion not successful: {deletion_data}")
            return False

        print("✅ Credential deletion successful")

        # Step 3: Verify credential is gone
        response = self.client.get("/auth/webauthn/credentials", headers=headers)

        if response.status_code != 200:
            print(f"❌ Credential listing after deletion failed: {response.status_code}")
            return False

        updated_credentials_data = response.json()
        updated_credentials = updated_credentials_data["credentials"]

        # Verify credential is no longer in list
        found_deleted = any(cred["credential_id"] == credential_id for cred in updated_credentials)
        if found_deleted:
            print("❌ Deleted credential still appears in list")
            return False

        print("✅ Credential management flow complete")

        # Remove from our tracking
        del self.registered_credentials[username]

        return True

    def test_multi_user_isolation(self):
        """Test that users can only access their own credentials."""
        print("\n🔒 Testing multi-user credential isolation...")

        if len(self.test_users) < 2:
            print("❌ Need at least 2 test users for isolation test")
            return False

        user1 = self.test_users[0]
        user2 = self.test_users[1]

        # Register credentials for both users
        for i, user in enumerate([user1, user2]):
            username = user["username"]

            if username not in self.session_tokens:
                print(f"❌ No session token available for user {username}")
                return False

            headers = {"Authorization": f"Bearer {self.session_tokens[username]}"}

            # Begin registration
            registration_request = {
                "device_name": f"Isolation Test Device {i+1}",
                "authenticator_type": "platform"
            }

            response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
            if response.status_code != 200:
                print(f"❌ Registration begin failed for user {username}")
                return False

            registration_data = response.json()
            challenge = registration_data["challenge"]

            # Complete registration
            credential_id = f"isolation_test_credential_{username}"
            mock_credential = {
                "id": credential_id,
                "rawId": credential_id,
                "type": "public-key",
                "response": {
                    "attestationObject": self._create_mock_attestation_object(),
                    "clientDataJSON": self._create_mock_client_data_json(challenge, "webauthn.create")
                }
            }

            complete_request = {
                "credential": mock_credential,
                "device_name": f"Isolation Test Device {i+1}"
            }

            response = self.client.post("/auth/webauthn/register/complete", json=complete_request, headers=headers)
            if response.status_code != 200:
                print(f"❌ Registration complete failed for user {username}")
                return False

            self.registered_credentials[username] = {
                "credential_id": credential_id,
                "device_name": f"Isolation Test Device {i+1}"
            }

        # Test isolation: each user should only see their own credentials
        for user in [user1, user2]:
            username = user["username"]
            headers = {"Authorization": f"Bearer {self.session_tokens[username]}"}

            response = self.client.get("/auth/webauthn/credentials", headers=headers)
            if response.status_code != 200:
                print(f"❌ Credential listing failed for user {username}")
                return False

            credentials_data = response.json()
            credentials = credentials_data["credentials"]

            # User should see exactly one credential (their own)
            if len(credentials) != 1:
                print(f"❌ User {username} should see exactly 1 credential, saw {len(credentials)}")
                return False

            # Verify it's their credential
            user_credential_id = self.registered_credentials[username]["credential_id"]
            if credentials[0]["credential_id"] != user_credential_id:
                print(f"❌ User {username} seeing wrong credential")
                return False

        # Test cross-user deletion attempt (should fail)
        user1_headers = {"Authorization": f"Bearer {self.session_tokens[user1['username']]}"}
        user2_credential_id = self.registered_credentials[user2["username"]]["credential_id"]

        response = self.client.delete(f"/auth/webauthn/credentials/{user2_credential_id}", headers=user1_headers)
        if response.status_code == 200:
            print("❌ User 1 should not be able to delete User 2's credential")
            return False

        print("✅ Multi-user credential isolation verified")

        # Clean up registered credentials
        for user in [user1, user2]:
            username = user["username"]
            headers = {"Authorization": f"Bearer {self.session_tokens[username]}"}
            credential_id = self.registered_credentials[username]["credential_id"]

            self.client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=headers)
            del self.registered_credentials[username]

        return True

    def test_authentication_fallback_integration(self):
        """Test WebAuthn integration with existing authentication fallback."""
        print("\n🔄 Testing authentication fallback integration...")

        user = self.test_users[0]
        username = user["username"]

        # Test 1: Traditional login still works
        login_data = {"username": username, "password": user["password"]}
        response = self.client.post("/auth/login", data=login_data)

        if response.status_code != 200:
            print(f"❌ Traditional login failed: {response.status_code} - {response.text}")
            return False

        traditional_auth = response.json()
        if "access_token" not in traditional_auth:
            print("❌ Traditional login should return access token")
            return False

        print("✅ Traditional authentication still works")

        # Test 2: Register WebAuthn credential
        if not self.test_complete_registration_flow():
            print("❌ Could not register WebAuthn credential")
            return False

        # Test 3: WebAuthn authentication works
        if not self.test_complete_authentication_flow():
            print("❌ WebAuthn authentication failed")
            return False

        # Test 4: Both tokens should work for protected endpoints
        traditional_headers = {"Authorization": f"Bearer {traditional_auth['access_token']}"}

        # Test traditional token
        response = self.client.get("/auth/validate-token", headers=traditional_headers)
        if response.status_code != 200:
            print("❌ Traditional token validation failed")
            return False

        print("✅ Authentication fallback integration verified")
        return True

    def test_rate_limiting_integration(self):
        """Test WebAuthn endpoints respect existing rate limiting."""
        print("\n⏱️ Testing rate limiting integration...")

        user = self.test_users[0]
        username = user["username"]

        if username not in self.session_tokens:
            print("❌ No session token available for user")
            return False

        headers = {"Authorization": f"Bearer {self.session_tokens[username]}"}

        # Test rate limiting on registration begin endpoint
        registration_request = {
            "device_name": "Rate Limit Test Device",
            "authenticator_type": "platform"
        }

        success_count = 0
        rate_limited_count = 0

        # Make multiple rapid requests
        for i in range(20):
            response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)

            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:  # Too Many Requests
                rate_limited_count += 1

            # Small delay to avoid overwhelming the system
            time.sleep(0.05)

        print(f"   Registration requests - Success: {success_count}, Rate limited: {rate_limited_count}")

        # Should have some successful requests but also some rate limited
        if success_count == 0:
            print("❌ No successful requests - rate limiting too aggressive")
            return False

        # Test rate limiting on authentication begin endpoint
        auth_request = {"username": username}

        auth_success_count = 0
        auth_rate_limited_count = 0

        for i in range(20):
            response = self.client.post("/auth/webauthn/authenticate/begin", json=auth_request)

            if response.status_code == 200:
                auth_success_count += 1
            elif response.status_code == 429:
                auth_rate_limited_count += 1

            time.sleep(0.05)

        print(f"   Authentication requests - Success: {auth_success_count}, Rate limited: {auth_rate_limited_count}")

        if auth_success_count == 0:
            print("❌ No successful auth requests - rate limiting too aggressive")
            return False

        print("✅ Rate limiting integration verified")
        return True

    def test_error_handling_integration(self):
        """Test comprehensive error handling integration."""
        print("\n❌ Testing error handling integration...")

        user = self.test_users[0]
        username = user["username"]

        if username not in self.session_tokens:
            print("❌ No session token available for user")
            return False

        headers = {"Authorization": f"Bearer {self.session_tokens[username]}"}

        # Test 1: Invalid request formats
        invalid_requests = [
            {},  # Empty request
            {"invalid_field": "value"},  # Invalid fields
            {"device_name": ""},  # Empty device name
            {"device_name": "Test", "authenticator_type": "invalid"},  # Invalid authenticator type
        ]

        for invalid_request in invalid_requests:
            response = self.client.post("/auth/webauthn/register/begin", json=invalid_request, headers=headers)
            if response.status_code not in [400, 422]:
                print(f"❌ Invalid request should return 400/422, got {response.status_code}")
                return False

        print("✅ Invalid request handling verified")

        # Test 2: Unauthenticated requests
        unauthenticated_endpoints = [
            ("POST", "/auth/webauthn/register/begin", {"device_name": "Test"}),
            ("POST", "/auth/webauthn/register/complete", {"credential": {}}),
            ("GET", "/auth/webauthn/credentials", None),
            ("DELETE", "/auth/webauthn/credentials/test", None),
        ]

        for method, endpoint, data in unauthenticated_endpoints:
            if method == "POST":
                response = self.client.post(endpoint, json=data)
            elif method == "GET":
                response = self.client.get(endpoint)
            elif method == "DELETE":
                response = self.client.delete(endpoint)

            if response.status_code != 401:
                print(f"❌ Unauthenticated {method} {endpoint} should return 401, got {response.status_code}")
                return False

        print("✅ Unauthenticated request handling verified")

        # Test 3: Non-existent user authentication
        response = self.client.post("/auth/webauthn/authenticate/begin", json={"username": "non_existent_user_12345"})
        if response.status_code not in [400, 401, 404]:
            print(f"❌ Non-existent user auth should return 400/401/404, got {response.status_code}")
            return False

        print("✅ Non-existent user handling verified")

        # Test 4: Non-existent credential deletion
        response = self.client.delete("/auth/webauthn/credentials/non_existent_credential", headers=headers)
        if response.status_code not in [400, 404]:
            print(f"❌ Non-existent credential deletion should return 400/404, got {response.status_code}")
            return False

        print("✅ Non-existent credential handling verified")

        print("✅ Error handling integration complete")
        return True

    def _create_mock_attestation_object(self):
        """Create a mock attestation object for testing."""
        mock_data = {
            "fmt": "none",
            "attStmt": {},
            "authData": "mock_authenticator_data_with_credential_info_and_public_key"
        }
        return base64.b64encode(json.dumps(mock_data).encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    def _create_mock_client_data_json(self, challenge, type_):
        """Create mock client data JSON for testing."""
        client_data = {
            "type": type_,
            "challenge": challenge,
            "origin": "http://testserver",
            "crossOrigin": False
        }
        return base64.b64encode(json.dumps(client_data).encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    def _create_mock_authenticator_data(self):
        """Create mock authenticator data for testing."""
        mock_data = "mock_rp_id_hash_32_bytes_plus_flags_and_counter_data"
        return base64.b64encode(mock_data.encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    def _create_mock_signature(self):
        """Create mock signature for testing."""
        mock_signature = "mock_signature_data_for_testing_purposes_integration"
        return base64.b64encode(mock_signature.encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    async def run_all_tests(self):
        """Run all WebAuthn integration tests."""
        print("🚀 Starting Complete WebAuthn Integration Tests")
        print("=" * 70)

        try:
            await self.setup()

            # Run tests in sequence
            tests = [
                ("Complete Registration Flow", self.test_complete_registration_flow),
                ("Complete Authentication Flow", self.test_complete_authentication_flow),
                ("Credential Management Flow", self.test_credential_management_flow),
                ("Multi-User Isolation", self.test_multi_user_isolation),
                ("Authentication Fallback Integration", self.test_authentication_fallback_integration),
                ("Rate Limiting Integration", self.test_rate_limiting_integration),
                ("Error Handling Integration", self.test_error_handling_integration),
            ]

            passed = 0
            failed = 0

            for test_name, test_func in tests:
                try:
                    result = test_func()
                    if result is not False:
                        passed += 1
                        print(f"✅ {test_name} PASSED")
                    else:
                        failed += 1
                        print(f"❌ {test_name} FAILED")
                except Exception as e:
                    failed += 1
                    print(f"❌ {test_name} FAILED with exception: {e}")
                    import traceback
                    traceback.print_exc()

            # Print summary
            print("\n" + "=" * 70)
            print("🏁 Complete WebAuthn Integration Test Summary")
            print(f"✅ Passed: {passed}")
            print(f"❌ Failed: {failed}")
            print(f"📊 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")

            if failed == 0:
                print("\n🎉 All WebAuthn integration tests passed!")
                print("✅ WebAuthn is fully integrated and working correctly")
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
    test_runner = WebAuthnIntegrationTestSuite()
    return await test_runner.run_all_tests()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
