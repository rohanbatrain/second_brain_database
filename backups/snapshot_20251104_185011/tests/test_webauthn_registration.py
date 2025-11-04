#!/usr/bin/env python3
"""
Test script to verify WebAuthn registration begin endpoint works correctly.
"""

import sys
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append('src')

from second_brain_database.routes.auth.services.webauthn.registration import begin_registration

async def test_begin_registration():
    """Test the begin_registration service function."""
    
    # Mock user data
    mock_user = {
        "_id": "507f1f77bcf86cd799439011",
        "username": "testuser",
        "email": "test@example.com",
        "is_active": True,
        "is_verified": True
    }
    
    # Mock device name
    device_name = "Test Device"
    
    print("Testing WebAuthn registration begin service...")
    
    try:
        # Mock the dependencies
        with patch('second_brain_database.routes.auth.services.webauthn.registration.get_user_credentials') as mock_get_creds, \
             patch('second_brain_database.routes.auth.services.webauthn.registration.store_challenge') as mock_store_challenge, \
             patch('second_brain_database.routes.auth.services.webauthn.registration.generate_secure_challenge') as mock_gen_challenge:
            
            # Setup mocks
            mock_get_creds.return_value = []  # No existing credentials
            mock_store_challenge.return_value = True
            mock_gen_challenge.return_value = "test-challenge-12345"
            
            # Call the service
            result = await begin_registration(mock_user, device_name)
            
            # Verify the result structure
            assert isinstance(result, dict), "Result should be a dictionary"
            assert "challenge" in result, "Result should contain challenge"
            assert "rp" in result, "Result should contain rp (relying party)"
            assert "user" in result, "Result should contain user info"
            assert "pubKeyCredParams" in result, "Result should contain pubKeyCredParams"
            assert "authenticatorSelection" in result, "Result should contain authenticatorSelection"
            assert "attestation" in result, "Result should contain attestation"
            assert "excludeCredentials" in result, "Result should contain excludeCredentials"
            assert "timeout" in result, "Result should contain timeout"
            
            # Verify specific values
            assert result["challenge"] == "test-challenge-12345", "Challenge should match generated value"
            assert result["rp"]["name"] == "Second Brain Database", "RP name should be correct"
            assert result["user"]["displayName"] == "testuser", "User display name should match"
            assert result["timeout"] == 300000, "Timeout should be 5 minutes"
            assert len(result["pubKeyCredParams"]) == 2, "Should support 2 key algorithms"
            assert result["authenticatorSelection"]["authenticatorAttachment"] == "platform", "Should prefer platform authenticators"
            
            print("✓ Service function works correctly")
            print(f"✓ Generated challenge: {result['challenge']}")
            print(f"✓ RP ID: {result['rp']['id']}")
            print(f"✓ User ID: {result['user']['id']}")
            print(f"✓ Supported algorithms: {len(result['pubKeyCredParams'])}")
            print(f"✓ Excluded credentials: {len(result['excludeCredentials'])}")
            
            # Verify mocks were called correctly
            mock_gen_challenge.assert_called_once()
            mock_store_challenge.assert_called_once_with("test-challenge-12345", "507f1f77bcf86cd799439011", "registration")
            mock_get_creds.assert_called_once_with("507f1f77bcf86cd799439011", active_only=True)
            
            print("✓ All service dependencies called correctly")
            
            return True
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run the test."""
    print("=== WebAuthn Registration Begin Test ===\n")
    
    success = await test_begin_registration()
    
    if success:
        print("\n✓ All tests passed! WebAuthn registration begin service is working correctly.")
    else:
        print("\n✗ Tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())