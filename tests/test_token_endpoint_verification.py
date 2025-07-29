#!/usr/bin/env python3

"""
Verification test for OAuth2 token endpoint implementation.
Tests the endpoint with mocked dependencies to verify the logic works correctly.
"""

from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from second_brain_database.main import app
from second_brain_database.routes.oauth2.models import ClientType, OAuthClient, AuthorizationCode, PKCEMethod
from second_brain_database.routes.oauth2.services.pkce_validator import PKCEValidator
from datetime import datetime, timedelta

def test_token_endpoint_authorization_code_flow():
    """Test the authorization code flow with mocked dependencies."""
    
    client = TestClient(app)
    
    # Create mock OAuth2 client
    mock_oauth2_client = OAuthClient(
        client_id="test_client_123",
        client_secret_hash="$2b$12$test_hash",
        name="Test Client",
        client_type=ClientType.CONFIDENTIAL,
        redirect_uris=["https://example.com/callback"],
        scopes=["read:profile", "write:data"],
        is_active=True
    )
    
    # Generate valid PKCE verifier and challenge
    verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
    
    # Create mock authorization code
    mock_auth_code = AuthorizationCode(
        code="auth_code_test123",
        client_id="test_client_123",
        user_id="test_user",
        redirect_uri="https://example.com/callback",
        scopes=["read:profile", "write:data"],
        code_challenge=challenge,
        code_challenge_method=PKCEMethod.S256,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        used=False
    )
    
    # Mock all dependencies
    with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit, \
         patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client') as mock_validate_client, \
         patch('second_brain_database.routes.oauth2.routes.auth_code_manager.use_authorization_code') as mock_use_code, \
         patch('second_brain_database.routes.oauth2.routes.create_access_token') as mock_create_token, \
         patch('second_brain_database.routes.oauth2.routes._generate_refresh_token') as mock_generate_refresh, \
         patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.log_oauth2_security_event') as mock_log_event:
        
        # Setup mocks
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        mock_use_code.return_value = mock_auth_code
        mock_create_token.return_value = "access_token_123"
        mock_generate_refresh.return_value = "refresh_token_123"
        mock_log_event.return_value = None
        
        # Make token request
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": "auth_code_test123",
            "redirect_uri": "https://example.com/callback",
            "client_id": "test_client_123",
            "client_secret": "test_secret",
            "code_verifier": verifier
        })
        
        print(f"Authorization Code Flow Test:")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            print(f"✅ Success! Token response:")
            print(f"  - Access Token: {token_data.get('access_token', 'MISSING')}")
            print(f"  - Token Type: {token_data.get('token_type', 'MISSING')}")
            print(f"  - Expires In: {token_data.get('expires_in', 'MISSING')}")
            print(f"  - Refresh Token: {token_data.get('refresh_token', 'MISSING')}")
            print(f"  - Scope: {token_data.get('scope', 'MISSING')}")
            
            # Verify all expected fields are present
            expected_fields = ['access_token', 'token_type', 'expires_in', 'refresh_token', 'scope']
            missing_fields = [field for field in expected_fields if field not in token_data]
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
            else:
                print("✅ All expected fields present")
                
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(f"Response: {response.json()}")


def test_token_endpoint_refresh_flow():
    """Test the refresh token flow with mocked dependencies."""
    
    client = TestClient(app)
    
    # Create mock OAuth2 client
    mock_oauth2_client = OAuthClient(
        client_id="test_client_123",
        client_secret_hash="$2b$12$test_hash",
        name="Test Client",
        client_type=ClientType.CONFIDENTIAL,
        redirect_uris=["https://example.com/callback"],
        scopes=["read:profile", "write:data"],
        is_active=True
    )
    
    # Mock refresh token data
    mock_refresh_data = {
        "user_id": "test_user",
        "scopes": ["read:profile", "write:data"]
    }
    
    # Mock all dependencies
    with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit, \
         patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client') as mock_validate_client, \
         patch('second_brain_database.routes.oauth2.routes._validate_refresh_token') as mock_validate_refresh, \
         patch('second_brain_database.routes.oauth2.routes.create_access_token') as mock_create_token, \
         patch('second_brain_database.routes.oauth2.routes._rotate_refresh_token') as mock_rotate_token, \
         patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.log_oauth2_security_event') as mock_log_event:
        
        # Setup mocks
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        mock_validate_refresh.return_value = mock_refresh_data
        mock_create_token.return_value = "new_access_token_123"
        mock_rotate_token.return_value = "new_refresh_token_123"
        mock_log_event.return_value = None
        
        # Make refresh token request
        response = client.post("/oauth2/token", data={
            "grant_type": "refresh_token",
            "refresh_token": "refresh_token_123",
            "client_id": "test_client_123",
            "client_secret": "test_secret"
        })
        
        print(f"\nRefresh Token Flow Test:")
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            print(f"✅ Success! Token response:")
            print(f"  - Access Token: {token_data.get('access_token', 'MISSING')}")
            print(f"  - Token Type: {token_data.get('token_type', 'MISSING')}")
            print(f"  - Expires In: {token_data.get('expires_in', 'MISSING')}")
            print(f"  - Refresh Token: {token_data.get('refresh_token', 'MISSING')}")
            print(f"  - Scope: {token_data.get('scope', 'MISSING')}")
            
            # Verify all expected fields are present
            expected_fields = ['access_token', 'token_type', 'expires_in', 'refresh_token', 'scope']
            missing_fields = [field for field in expected_fields if field not in token_data]
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
            else:
                print("✅ All expected fields present")
                
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(f"Response: {response.json()}")


def test_token_endpoint_error_cases():
    """Test various error cases."""
    
    client = TestClient(app)
    
    print(f"\nError Cases Test:")
    
    # Test 1: Invalid grant type
    response = client.post("/oauth2/token", data={
        "grant_type": "invalid_grant",
        "client_id": "test_client_123",
        "client_secret": "test_secret"
    })
    
    with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit, \
         patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client') as mock_validate_client:
        
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = MagicMock()
        
        response = client.post("/oauth2/token", data={
            "grant_type": "invalid_grant",
            "client_id": "test_client_123",
            "client_secret": "test_secret"
        })
        
        if response.status_code == 400:
            error_data = response.json()
            if error_data.get("error") == "unsupported_grant_type":
                print("✅ Invalid grant type error handled correctly")
            else:
                print(f"❌ Unexpected error response: {error_data}")
        else:
            print(f"❌ Expected 400, got {response.status_code}")
    
    # Test 2: Missing required parameters
    response = client.post("/oauth2/token", data={
        "client_id": "test_client_123"
        # Missing grant_type
    })
    
    if response.status_code == 422:
        print("✅ Missing required parameter validation works")
    else:
        print(f"❌ Expected 422 for missing parameter, got {response.status_code}")


if __name__ == "__main__":
    print("Testing OAuth2 Token Endpoint Implementation")
    print("=" * 50)
    
    test_token_endpoint_authorization_code_flow()
    test_token_endpoint_refresh_flow()
    test_token_endpoint_error_cases()
    
    print("\n" + "=" * 50)
    print("Token endpoint verification complete!")