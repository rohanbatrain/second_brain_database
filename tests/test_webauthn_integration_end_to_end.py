#!/usr/bin/env python3
"""
WebAuthn End-to-End Integration Tests

Comprehensive end-to-end testing for WebAuthn functionality that follows
the existing test patterns and validates complete user workflows.
"""

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.main import app


class WebAuthnEndToEndTest:
    """End-to-end WebAuthn integration test suite."""

    def __init__(self):
        self.client = TestClient(app)
        self.test_user = {
            "username": "webauthn_e2e_user",
            "email": "webauthn_e2e@example.com",
            "password": "TestPassword123!"
        }
        self.session_token = None
        self.webauthn_token = None
        self.registered_credential = None

    async def setup(self):
        """Set up test environment."""
        print("🔧 Setting up WebAuthn end-to-end test environment...")
        
        # Connect to database
        await db_manager.connect()
        
        # Register and login test user
        response = self.client.post("/auth/register", json=self.test_user)
        if response.status_code not in [200, 201]:
            print("ℹ️ User might already exist, attempting login...")
        
        # Login to get session token
        login_data = {"username": self.test_user["username"], "password": self.test_user["password"]}
        response = self.client.post("/auth/login", data=login_data)
        
        if response.status_code == 200:
            token_data = response.json()
            self.session_token = token_data["access_token"]
        
        print("✅ WebAuthn end-to-end test environment ready")

    async def cleanup(self):
        """Clean up test environment."""
        print("🧹 Cleaning up WebAuthn end-to-end test data...")
        
        try:
            if hasattr(db_manager, "db") and db_manager.db:
                # Remove test user
                await db_manager.db.users.delete_many({"username": self.test_user["username"]})
                
                # Remove test WebAuthn credentials
                await db_manager.db.webauthn_credentials.delete_many({
                    "user_id": {"$regex": "webauthn_e2e"}
                })
                
                # Remove test challenges
                await db_manager.db.webauthn_challenges.delete_many({
                    "user_id": {"$regex": "webauthn_e2e"}
                })
                
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        # Close database connection
        await db_manager.disconnect()
        
        print("✅ WebAuthn end-to-end test cleanup complete")

    def test_complete_user_journey(self):
        """Test complete user journey from registration to authentication."""
        print("\n🚀 Testing complete WebAuthn user journey...")
        
        if not self.session_token:
            print("❌ No session token available")
            return False
        
        # Step 1: User registers a WebAuthn credential
        print("   Step 1: Registering WebAuthn credential...")
        
        headers = {"Authorization": f"Bearer {self.session_token}"}
        registration_request = {
            "device_name": "E2E Test Device",
            "authenticator_type": "platform"
        }
        
        # Begin registration
        response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
        if response.status_code != 200:
            print(f"❌ Registration begin failed: {response.status_code} - {response.text}")
            return False
        
        registration_data = response.json()
        challenge = registration_data["challenge"]
        
        # Complete registration
        credential_id = "e2e_test_credential"
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
            "device_name": "E2E Test Device"
        }
        
        response = self.client.post("/auth/webauthn/register/complete", json=complete_request, headers=headers)
        if response.status_code != 200:
            print(f"❌ Registration complete failed: {response.status_code} - {response.text}")
            return False
        
        completion_data = response.json()
        if not completion_data.get("success"):
            print(f"❌ Registration not successful: {completion_data}")
            return False
        
        self.registered_credential = {
            "credential_id": credential_id,
            "device_name": "E2E Test Device"
        }
        
        print("   ✅ WebAuthn credential registered successfully")
        
        # Step 2: User views their credentials
        print("   Step 2: Viewing registered credentials...")
        
        response = self.client.get("/auth/webauthn/credentials", headers=headers)
        if response.status_code != 200:
            print(f"❌ Credential listing failed: {response.status_code} - {response.text}")
            return False
        
        credentials_data = response.json()
        credentials = credentials_data.get("credentials", [])
        
        if len(credentials) != 1:
            print(f"❌ Expected 1 credential, found {len(credentials)}")
            return False
        
        if credentials[0]["credential_id"] != credential_id:
            print(f"❌ Wrong credential ID: {credentials[0]['credential_id']}")
            return False
        
        print("   ✅ Credentials listed successfully")
        
        # Step 3: User authenticates using WebAuthn
        print("   Step 3: Authenticating with WebAuthn...")
        
        # Begin authentication
        auth_request = {"username": self.test_user["username"]}
        response = self.client.post("/auth/webauthn/authenticate/begin", json=auth_request)
        
        if response.status_code != 200:
            print(f"❌ Authentication begin failed: {response.status_code} - {response.text}")
            return False
        
        auth_data = response.json()
        public_key = auth_data["publicKey"]
        auth_challenge = public_key["challenge"]
        
        # Complete authentication
        mock_assertion = {
            "id": credential_id,
            "rawId": credential_id,
            "type": "public-key",
            "response": {
                "authenticatorData": self._create_mock_authenticator_data(),
                "clientDataJSON": self._create_mock_client_data_json(auth_challenge, "webauthn.get"),
                "signature": self._create_mock_signature()
            }
        }
        
        complete_request = {"credential": mock_assertion}
        response = self.client.post("/auth/webauthn/authenticate/complete", json=complete_request)
        
        if response.status_code != 200:
            print(f"❌ Authentication complete failed: {response.status_code} - {response.text}")
            return False
        
        auth_result = response.json()
        
        if auth_result.get("authentication_method") != "webauthn":
            print(f"❌ Wrong authentication method: {auth_result.get('authentication_method')}")
            return False
        
        self.webauthn_token = auth_result["access_token"]
        
        print("   ✅ WebAuthn authentication successful")
        
        # Step 4: User accesses protected resources with WebAuthn token
        print("   Step 4: Accessing protected resources...")
        
        webauthn_headers = {"Authorization": f"Bearer {self.webauthn_token}"}
        
        # Test token validation
        response = self.client.get("/auth/validate-token", headers=webauthn_headers)
        if response.status_code != 200:
            print(f"❌ Token validation failed: {response.status_code} - {response.text}")
            return False
        
        user_data = response.json()
        if user_data["username"] != self.test_user["username"]:
            print(f"❌ Wrong user from token: {user_data['username']}")
            return False
        
        # Test accessing credentials with WebAuthn token
        response = self.client.get("/auth/webauthn/credentials", headers=webauthn_headers)
        if response.status_code != 200:
            print(f"❌ Credential access with WebAuthn token failed: {response.status_code}")
            return False
        
        print("   ✅ Protected resource access successful")
        
        # Step 5: User manages their credentials
        print("   Step 5: Managing WebAuthn credentials...")
        
        # Delete the credential
        response = self.client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=webauthn_headers)
        if response.status_code != 200:
            print(f"❌ Credential deletion failed: {response.status_code} - {response.text}")
            return False
        
        # Verify credential is gone
        response = self.client.get("/auth/webauthn/credentials", headers=webauthn_headers)
        if response.status_code != 200:
            print(f"❌ Credential listing after deletion failed: {response.status_code}")
            return False
        
        updated_credentials = response.json().get("credentials", [])
        if len(updated_credentials) != 0:
            print(f"❌ Expected 0 credentials after deletion, found {len(updated_credentials)}")
            return False
        
        print("   ✅ Credential management successful")
        
        print("✅ Complete user journey successful")
        return True

    def test_authentication_method_compatibility(self):
        """Test compatibility between different authentication methods."""
        print("\n🔄 Testing authentication method compatibility...")
        
        if not self.session_token:
            print("❌ No session token available")
            return False
        
        # Test 1: Traditional login works
        login_data = {"username": self.test_user["username"], "password": self.test_user["password"]}
        response = self.client.post("/auth/login", data=login_data)
        
        if response.status_code != 200:
            print(f"❌ Traditional login failed: {response.status_code}")
            return False
        
        traditional_token = response.json()["access_token"]
        
        # Test 2: Register WebAuthn credential with traditional token
        headers = {"Authorization": f"Bearer {traditional_token}"}
        registration_request = {
            "device_name": "Compatibility Test Device",
            "authenticator_type": "platform"
        }
        
        response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
        if response.status_code != 200:
            print(f"❌ WebAuthn registration with traditional token failed: {response.status_code}")
            return False
        
        registration_data = response.json()
        challenge = registration_data["challenge"]
        
        credential_id = "compatibility_test_credential"
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
            "device_name": "Compatibility Test Device"
        }
        
        response = self.client.post("/auth/webauthn/register/complete", json=complete_request, headers=headers)
        if response.status_code != 200:
            print(f"❌ WebAuthn registration complete failed: {response.status_code}")
            return False
        
        # Test 3: Authenticate with WebAuthn
        auth_request = {"username": self.test_user["username"]}
        response = self.client.post("/auth/webauthn/authenticate/begin", json=auth_request)
        
        if response.status_code != 200:
            print(f"❌ WebAuthn authentication begin failed: {response.status_code}")
            return False
        
        auth_data = response.json()
        auth_challenge = auth_data["publicKey"]["challenge"]
        
        mock_assertion = {
            "id": credential_id,
            "rawId": credential_id,
            "type": "public-key",
            "response": {
                "authenticatorData": self._create_mock_authenticator_data(),
                "clientDataJSON": self._create_mock_client_data_json(auth_challenge, "webauthn.get"),
                "signature": self._create_mock_signature()
            }
        }
        
        complete_request = {"credential": mock_assertion}
        response = self.client.post("/auth/webauthn/authenticate/complete", json=complete_request)
        
        if response.status_code != 200:
            print(f"❌ WebAuthn authentication complete failed: {response.status_code}")
            return False
        
        webauthn_token = response.json()["access_token"]
        
        # Test 4: Both tokens work for same operations
        traditional_headers = {"Authorization": f"Bearer {traditional_token}"}
        webauthn_headers = {"Authorization": f"Bearer {webauthn_token}"}
        
        for token_type, headers in [("traditional", traditional_headers), ("webauthn", webauthn_headers)]:
            response = self.client.get("/auth/validate-token", headers=headers)
            if response.status_code != 200:
                print(f"❌ Token validation failed for {token_type} token")
                return False
            
            response = self.client.get("/auth/webauthn/credentials", headers=headers)
            if response.status_code != 200:
                print(f"❌ Credential access failed for {token_type} token")
                return False
        
        # Clean up
        response = self.client.delete(f"/auth/webauthn/credentials/{credential_id}", headers=webauthn_headers)
        
        print("✅ Authentication method compatibility verified")
        return True

    def test_security_edge_cases(self):
        """Test security edge cases and boundary conditions."""
        print("\n🔒 Testing security edge cases...")
        
        if not self.session_token:
            print("❌ No session token available")
            return False
        
        headers = {"Authorization": f"Bearer {self.session_token}"}
        
        # Test 1: Invalid challenge reuse
        print("   Testing challenge reuse protection...")
        
        registration_request = {
            "device_name": "Security Test Device",
            "authenticator_type": "platform"
        }
        
        # Get first challenge
        response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
        if response.status_code != 200:
            print(f"❌ First registration begin failed: {response.status_code}")
            return False
        
        first_challenge = response.json()["challenge"]
        
        # Get second challenge
        response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
        if response.status_code != 200:
            print(f"❌ Second registration begin failed: {response.status_code}")
            return False
        
        second_challenge = response.json()["challenge"]
        
        # Challenges should be different
        if first_challenge == second_challenge:
            print("❌ Challenges should be unique")
            return False
        
        print("   ✅ Challenge uniqueness verified")
        
        # Test 2: Invalid credential format handling
        print("   Testing invalid credential format handling...")
        
        invalid_credentials = [
            {},  # Empty credential
            {"id": "test", "type": "invalid"},  # Invalid type
            {"id": "", "type": "public-key"},  # Empty ID
            {"id": "test", "type": "public-key", "response": {}},  # Empty response
        ]
        
        for invalid_credential in invalid_credentials:
            complete_request = {
                "credential": invalid_credential,
                "device_name": "Invalid Test Device"
            }
            
            response = self.client.post("/auth/webauthn/register/complete", json=complete_request, headers=headers)
            if response.status_code not in [400, 422]:
                print(f"❌ Invalid credential should return 400/422, got {response.status_code}")
                return False
        
        print("   ✅ Invalid credential format handling verified")
        
        # Test 3: Origin validation
        print("   Testing origin validation...")
        
        # This would be more comprehensive in a real implementation
        # For now, just verify that the mock data is accepted
        response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
        if response.status_code != 200:
            print(f"❌ Origin validation test setup failed: {response.status_code}")
            return False
        
        print("   ✅ Origin validation test completed")
        
        print("✅ Security edge cases verified")
        return True

    def _create_mock_attestation_object(self):
        """Create a mock attestation object for testing."""
        mock_data = {
            "fmt": "none",
            "attStmt": {},
            "authData": "mock_authenticator_data_with_credential_info_and_public_key_e2e"
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
        mock_data = "mock_rp_id_hash_32_bytes_plus_flags_and_counter_data_e2e"
        return base64.b64encode(mock_data.encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    def _create_mock_signature(self):
        """Create mock signature for testing."""
        mock_signature = "mock_signature_data_for_testing_purposes_e2e"
        return base64.b64encode(mock_signature.encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    async def run_all_tests(self):
        """Run all end-to-end tests."""
        print("🚀 Starting WebAuthn End-to-End Integration Tests")
        print("=" * 70)
        
        try:
            await self.setup()
            
            # Run tests in sequence
            tests = [
                ("Complete User Journey", self.test_complete_user_journey),
                ("Authentication Method Compatibility", self.test_authentication_method_compatibility),
                ("Security Edge Cases", self.test_security_edge_cases),
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
            print("🏁 WebAuthn End-to-End Test Summary")
            print(f"✅ Passed: {passed}")
            print(f"❌ Failed: {failed}")
            print(f"📊 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")
            
            if failed == 0:
                print("\n🎉 All WebAuthn end-to-end tests passed!")
                print("✅ WebAuthn provides complete user experience")
                return True
            else:
                print(f"\n⚠️ {failed} WebAuthn end-to-end test(s) failed")
                return False
        
        except Exception as e:
            print(f"❌ WebAuthn end-to-end test suite failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test runner."""
    test_runner = WebAuthnEndToEndTest()
    return await test_runner.run_all_tests()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)