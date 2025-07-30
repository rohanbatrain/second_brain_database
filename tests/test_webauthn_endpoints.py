#!/usr/bin/env python3
"""
WebAuthn endpoint tests following existing patterns.

Tests all WebAuthn API endpoints including registration, authentication,
and credential management with proper error handling and security validation.
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


class WebAuthnEndpointTest:
    """Test WebAuthn API endpoints."""

    def __init__(self):
        self.client = TestClient(app)
        self.test_user = {
            "username": "webauthn_endpoint_test",
            "email": "webauthn_endpoint@example.com",
            "password": "TestPassword123!"
        }
        self.session_token = None

    async def setup(self):
        """Set up test environment."""
        print("🔧 Setting up WebAuthn endpoint test environment...")
        
        # Connect to database
        await db_manager.connect()
        
        # Register and login test user
        self.client.post("/auth/register", json=self.test_user)
        login_data = {"username": self.test_user["username"], "password": self.test_user["password"]}
        response = self.client.post("/auth/login", data=login_data)
        
        if response.status_code == 200:
            token_data = response.json()
            self.session_token = token_data["access_token"]
        
        print("✅ WebAuthn endpoint test environment ready")

    async def cleanup(self):
        """Clean up test environment."""
        print("🧹 Cleaning up WebAuthn endpoint test data...")
        
        try:
            if hasattr(db_manager, "db") and db_manager.db:
                # Remove test user and related data
                await db_manager.db.users.delete_many({"username": self.test_user["username"]})
                await db_manager.db.webauthn_credentials.delete_many({"user_id": {"$regex": "webauthn_endpoint"}})
                await db_manager.db.webauthn_challenges.delete_many({"user_id": {"$regex": "webauthn_endpoint"}})
                
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        await db_manager.disconnect()
        print("✅ WebAuthn endpoint test cleanup complete")

    def test_webauthn_register_begin_endpoint(self):
        """Test /auth/webauthn/register/begin endpoint."""
        print("\n🔑 Testing WebAuthn register begin endpoint...")
        
        if not self.session_token:
            print("❌ No session token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # Test valid request
        valid_request = {
            "device_name": "Test Device",
            "authenticator_type": "platform"
        }
        
        response = self.client.post("/auth/webauthn/register/begin", json=valid_request, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Valid request failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        required_fields = ["challenge", "rp", "user", "pubKeyCredParams", "timeout"]
        for field in required_fields:
            if field not in data:
                print(f"❌ Missing field {field} in response")
                return False
        
        print("✅ Valid request successful")
        
        # Test without authentication
        response = self.client.post("/auth/webauthn/register/begin", json=valid_request)
        if response.status_code != 401:
            print(f"❌ Unauthenticated request should return 401, got {response.status_code}")
            return False
        
        print("✅ Unauthenticated request properly rejected")
        
        # Test invalid request body
        invalid_request = {"invalid_field": "value"}
        response = self.client.post("/auth/webauthn/register/begin", json=invalid_request, headers=headers)
        if response.status_code not in [400, 422]:
            print(f"❌ Invalid request should return 400/422, got {response.status_code}")
            return False
        
        print("✅ Invalid request properly rejected")
        
        # Test rate limiting (make multiple requests quickly)
        for i in range(10):
            response = self.client.post("/auth/webauthn/register/begin", json=valid_request, headers=headers)
            if response.status_code == 429:
                print("✅ Rate limiting working")
                break
        else:
            print("⚠️ Rate limiting not triggered (may be expected in test environment)")
        
        return True

    def test_webauthn_register_complete_endpoint(self):
        """Test /auth/webauthn/register/complete endpoint."""
        print("\n🔐 Testing WebAuthn register complete endpoint...")
        
        if not self.session_token:
            print("❌ No session token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # First get registration options
        begin_request = {"device_name": "Test Device", "authenticator_type": "platform"}
        begin_response = self.client.post("/auth/webauthn/register/begin", json=begin_request, headers=headers)
        
        if begin_response.status_code != 200:
            print("❌ Could not get registration options")
            return False
        
        begin_data = begin_response.json()
        challenge = begin_data["challenge"]
        
        # Test valid completion request
        valid_credential = {
            "id": "test_credential_endpoint_123",
            "rawId": "test_credential_endpoint_123",
            "type": "public-key",
            "response": {
                "attestationObject": self._create_mock_attestation_object(),
                "clientDataJSON": self._create_mock_client_data_json(challenge, "webauthn.create")
            }
        }
        
        complete_request = {
            "credential": valid_credential,
            "device_name": "Test Device"
        }
        
        response = self.client.post("/auth/webauthn/register/complete", json=complete_request, headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Valid completion failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        if not data.get("success") or not data.get("credential_id"):
            print(f"❌ Invalid completion response: {data}")
            return False
        
        print("✅ Valid completion successful")
        
        # Test without authentication
        response = self.client.post("/auth/webauthn/register/complete", json=complete_request)
        if response.status_code != 401:
            print(f"❌ Unauthenticated completion should return 401, got {response.status_code}")
            return False
        
        print("✅ Unauthenticated completion properly rejected")
        
        # Test invalid credential format
        invalid_request = {"credential": {"invalid": "format"}}
        response = self.client.post("/auth/webauthn/register/complete", json=invalid_request, headers=headers)
        if response.status_code not in [400, 422]:
            print(f"❌ Invalid credential should return 400/422, got {response.status_code}")
            return False
        
        print("✅ Invalid credential format properly rejected")
        
        return True

    def test_webauthn_authenticate_begin_endpoint(self):
        """Test /auth/webauthn/authenticate/begin endpoint."""
        print("\n🔓 Testing WebAuthn authenticate begin endpoint...")
        
        # Test valid request (no authentication required)
        valid_request = {"username": self.test_user["username"]}
        response = self.client.post("/auth/webauthn/authenticate/begin", json=valid_request)
        
        if response.status_code != 200:
            print(f"❌ Valid auth begin failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        required_fields = ["challenge", "timeout", "rpId"]
        for field in required_fields:
            if field not in data:
                print(f"❌ Missing field {field} in auth begin response")
                return False
        
        print("✅ Valid auth begin successful")
        
        # Test with non-existent user
        invalid_request = {"username": "non_existent_user_12345"}
        response = self.client.post("/auth/webauthn/authenticate/begin", json=invalid_request)
        if response.status_code not in [400, 404]:
            print(f"❌ Non-existent user should return 400/404, got {response.status_code}")
            return False
        
        print("✅ Non-existent user properly rejected")
        
        # Test invalid request format
        invalid_request = {"invalid_field": "value"}
        response = self.client.post("/auth/webauthn/authenticate/begin", json=invalid_request)
        if response.status_code not in [400, 422]:
            print(f"❌ Invalid request should return 400/422, got {response.status_code}")
            return False
        
        print("✅ Invalid request format properly rejected")
        
        return True

    def test_webauthn_authenticate_complete_endpoint(self):
        """Test /auth/webauthn/authenticate/complete endpoint."""
        print("\n🔑 Testing WebAuthn authenticate complete endpoint...")
        
        # First register a credential
        if not self._register_test_credential():
            print("❌ Could not register test credential")
            return False
        
        # Begin authentication
        begin_request = {"username": self.test_user["username"]}
        begin_response = self.client.post("/auth/webauthn/authenticate/begin", json=begin_request)
        
        if begin_response.status_code != 200:
            print("❌ Could not begin authentication")
            return False
        
        begin_data = begin_response.json()
        challenge = begin_data["challenge"]
        
        # Test valid authentication completion
        valid_assertion = {
            "id": "test_credential_endpoint_123",
            "rawId": "test_credential_endpoint_123",
            "type": "public-key",
            "response": {
                "authenticatorData": self._create_mock_authenticator_data(),
                "clientDataJSON": self._create_mock_client_data_json(challenge, "webauthn.get"),
                "signature": self._create_mock_signature()
            }
        }
        
        complete_request = {"credential": valid_assertion}
        response = self.client.post("/auth/webauthn/authenticate/complete", json=complete_request)
        
        if response.status_code != 200:
            print(f"❌ Valid auth completion failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        required_fields = ["access_token", "token_type"]
        for field in required_fields:
            if field not in data:
                print(f"❌ Missing field {field} in auth completion response")
                return False
        
        print("✅ Valid auth completion successful")
        
        # Test invalid assertion format
        invalid_request = {"credential": {"invalid": "format"}}
        response = self.client.post("/auth/webauthn/authenticate/complete", json=invalid_request)
        if response.status_code not in [400, 422]:
            print(f"❌ Invalid assertion should return 400/422, got {response.status_code}")
            return False
        
        print("✅ Invalid assertion format properly rejected")
        
        return True

    def test_webauthn_credentials_list_endpoint(self):
        """Test /auth/webauthn/credentials endpoint (GET)."""
        print("\n📋 Testing WebAuthn credentials list endpoint...")
        
        if not self.session_token:
            print("❌ No session token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # Test valid request
        response = self.client.get("/auth/webauthn/credentials", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Valid credentials list failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        if "credentials" not in data:
            print(f"❌ Missing credentials field in response: {data}")
            return False
        
        credentials = data["credentials"]
        if not isinstance(credentials, list):
            print(f"❌ Credentials should be a list: {credentials}")
            return False
        
        print("✅ Valid credentials list successful")
        print(f"   Found {len(credentials)} credential(s)")
        
        # Test without authentication
        response = self.client.get("/auth/webauthn/credentials")
        if response.status_code != 401:
            print(f"❌ Unauthenticated request should return 401, got {response.status_code}")
            return False
        
        print("✅ Unauthenticated request properly rejected")
        
        return True

    def test_webauthn_credentials_delete_endpoint(self):
        """Test /auth/webauthn/credentials/{credential_id} endpoint (DELETE)."""
        print("\n🗑️ Testing WebAuthn credentials delete endpoint...")
        
        if not self.session_token:
            print("❌ No session token available")
            return False
        
        # First register a credential to delete
        if not self._register_test_credential():
            print("❌ Could not register test credential")
            return False
        
        headers = {"Authorization": f"Bearer {self.session_token}"}
        credential_id = "test_credential_endpoint_123"
        
        # Test valid deletion
        response = self.client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=headers)
        
        if response.status_code != 200:
            print(f"❌ Valid deletion failed: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        if not data.get("success"):
            print(f"❌ Deletion not successful: {data}")
            return False
        
        print("✅ Valid deletion successful")
        
        # Test without authentication
        response = self.client.delete(f"/auth/webauthn/credentials/{credential_id}")
        if response.status_code != 401:
            print(f"❌ Unauthenticated deletion should return 401, got {response.status_code}")
            return False
        
        print("✅ Unauthenticated deletion properly rejected")
        
        # Test deleting non-existent credential
        response = self.client.delete("/auth/webauthn/credentials/non_existent_credential", headers=headers)
        if response.status_code not in [404, 400]:
            print(f"❌ Non-existent credential deletion should return 404/400, got {response.status_code}")
            return False
        
        print("✅ Non-existent credential deletion properly rejected")
        
        return True

    def _register_test_credential(self):
        """Helper method to register a test credential."""
        if not self.session_token:
            return False
        
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # Begin registration
        begin_request = {"device_name": "Test Device", "authenticator_type": "platform"}
        begin_response = self.client.post("/auth/webauthn/register/begin", json=begin_request, headers=headers)
        
        if begin_response.status_code != 200:
            return False
        
        begin_data = begin_response.json()
        challenge = begin_data["challenge"]
        
        # Complete registration
        credential = {
            "id": "test_credential_endpoint_123",
            "rawId": "test_credential_endpoint_123",
            "type": "public-key",
            "response": {
                "attestationObject": self._create_mock_attestation_object(),
                "clientDataJSON": self._create_mock_client_data_json(challenge, "webauthn.create")
            }
        }
        
        complete_request = {"credential": credential, "device_name": "Test Device"}
        complete_response = self.client.post("/auth/webauthn/register/complete", json=complete_request, headers=headers)
        
        return complete_response.status_code == 200

    def _create_mock_attestation_object(self):
        """Create a mock attestation object for testing."""
        mock_data = {
            "fmt": "none",
            "attStmt": {},
            "authData": "mock_authenticator_data_with_credential_info"
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
        mock_data = "mock_rp_id_hash_32_bytes_plus_flags_and_counter"
        return base64.b64encode(mock_data.encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    def _create_mock_signature(self):
        """Create mock signature for testing."""
        mock_signature = "mock_signature_data_for_testing_purposes"
        return base64.b64encode(mock_signature.encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    async def run_all_tests(self):
        """Run all WebAuthn endpoint tests."""
        print("🚀 Starting WebAuthn Endpoint Tests")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # Run tests in sequence
            tests = [
                ("WebAuthn Register Begin Endpoint", self.test_webauthn_register_begin_endpoint),
                ("WebAuthn Register Complete Endpoint", self.test_webauthn_register_complete_endpoint),
                ("WebAuthn Authenticate Begin Endpoint", self.test_webauthn_authenticate_begin_endpoint),
                ("WebAuthn Authenticate Complete Endpoint", self.test_webauthn_authenticate_complete_endpoint),
                ("WebAuthn Credentials List Endpoint", self.test_webauthn_credentials_list_endpoint),
                ("WebAuthn Credentials Delete Endpoint", self.test_webauthn_credentials_delete_endpoint),
            ]
            
            passed = 0
            failed = 0
            
            for test_name, test_func in tests:
                try:
                    result = test_func()
                    if result is not False:
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
            print("🏁 WebAuthn Endpoint Test Summary")
            print(f"✅ Passed: {passed}")
            print(f"❌ Failed: {failed}")
            print(f"📊 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")
            
            if failed == 0:
                print("\n🎉 All WebAuthn endpoint tests passed!")
                print("✅ WebAuthn endpoints are working correctly")
                return True
            else:
                print(f"\n⚠️ {failed} WebAuthn endpoint test(s) failed")
                return False
        
        except Exception as e:
            print(f"❌ WebAuthn endpoint test suite failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test runner."""
    test_runner = WebAuthnEndpointTest()
    return await test_runner.run_all_tests()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)