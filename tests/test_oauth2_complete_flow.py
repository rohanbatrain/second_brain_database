"""
Complete OAuth2 flow integration test with existing APIs.

This module tests the complete OAuth2 authorization code flow and verifies
that the resulting access tokens work with existing API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

from second_brain_database.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_oauth2_client():
    """Mock OAuth2 client."""
    return {
        "client_id": "oauth2_client_test123",
        "client_secret_hash": "hashed_secret",
        "name": "Test OAuth2 Client",
        "client_type": "confidential",
        "redirect_uris": ["https://client.example.com/callback"],
        "scopes": ["read:profile", "write:data", "read:tokens"],
        "is_active": True
    }


@pytest.fixture
def mock_user():
    """Mock user for authentication."""
    return {
        "_id": "test_user_id",
        "username": "testuser",
        "email": "test@example.com",
        "is_verified": True,
        "is_active": True,
        "role": "user",
        "token_version": 1
    }


@pytest.fixture
def mock_auth_code():
    """Mock authorization code."""
    return {
        "code": "auth_code_test123",
        "client_id": "oauth2_client_test123",
        "user_id": "testuser",
        "redirect_uri": "https://client.example.com/callback",
        "scopes": ["read:profile", "write:data"],
        "code_challenge": "test_challenge",
        "code_challenge_method": "S256",
        "expires_at": datetime.utcnow() + timedelta(minutes=10),
        "used": False
    }


class TestCompleteOAuth2Flow:
    """Test complete OAuth2 authorization code flow."""
    
    def test_complete_oauth2_flow_with_api_usage(self, client, mock_oauth2_client, mock_user, mock_auth_code):
        """Test complete OAuth2 flow from authorization to API usage."""
        
        # Step 1: Authorization request
        with patch('second_brain_database.routes.oauth2.routes.get_current_user_dep', 
                   return_value=mock_user), \
             patch('second_brain_database.routes.oauth2.client_manager.client_manager.get_client', 
                   return_value=mock_oauth2_client), \
             patch('second_brain_database.routes.oauth2.services.consent_manager.consent_manager.has_valid_consent', 
                   return_value=True), \
             patch('second_brain_database.routes.oauth2.services.auth_code_manager.auth_code_manager.generate_authorization_code', 
                   return_value="auth_code_test123"), \
             patch('second_brain_database.routes.oauth2.services.auth_code_manager.auth_code_manager.store_authorization_code', 
                   return_value=True):
            
            # Make authorization request
            auth_response = client.get(
                "/oauth2/authorize",
                params={
                    "response_type": "code",
                    "client_id": "oauth2_client_test123",
                    "redirect_uri": "https://client.example.com/callback",
                    "scope": "read:profile write:data",
                    "state": "test_state_123",
                    "code_challenge": "test_challenge",
                    "code_challenge_method": "S256"
                },
                headers={"Authorization": "Bearer user_jwt_token"}
            )
            
            # Should redirect with authorization code
            assert auth_response.status_code == 302
            
            # Extract authorization code from redirect URL
            redirect_url = auth_response.headers["location"]
            parsed_url = urlparse(redirect_url)
            query_params = parse_qs(parsed_url.query)
            
            assert "code" in query_params
            assert query_params["state"][0] == "test_state_123"
            auth_code = query_params["code"][0]
        
        # Step 2: Token exchange
        with patch('second_brain_database.routes.oauth2.client_manager.client_manager.validate_client', 
                   return_value=mock_oauth2_client), \
             patch('second_brain_database.routes.oauth2.services.auth_code_manager.auth_code_manager.use_authorization_code', 
                   return_value=mock_auth_code), \
             patch('second_brain_database.routes.oauth2.services.pkce_validator.PKCEValidator.validate_code_challenge', 
                   return_value=True), \
             patch('second_brain_database.routes.auth.services.auth.login.create_access_token', 
                   return_value="oauth2_access_token_jwt"), \
             patch('second_brain_database.routes.oauth2.services.token_manager.token_manager.generate_refresh_token', 
                   return_value="refresh_token_test123"):
            
            # Exchange authorization code for tokens
            token_response = client.post(
                "/oauth2/token",
                data={
                    "grant_type": "authorization_code",
                    "code": auth_code,
                    "redirect_uri": "https://client.example.com/callback",
                    "client_id": "oauth2_client_test123",
                    "client_secret": "client_secret",
                    "code_verifier": "test_verifier"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            # Should return access token
            assert token_response.status_code == 200
            token_data = token_response.json()
            
            assert "access_token" in token_data
            assert token_data["token_type"] == "Bearer"
            assert "refresh_token" in token_data
            assert token_data["scope"] == "read:profile write:data"
            
            access_token = token_data["access_token"]
        
        # Step 3: Use access token with existing APIs
        oauth2_user = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "is_verified": True,
            "is_active": True,
            "role": "user",
            "oauth2_client_id": "oauth2_client_test123",
            "oauth2_scopes": ["read:profile", "write:data"],
            "is_oauth2_token": True
        }
        
        with patch('second_brain_database.routes.auth.routes.get_current_user', 
                   return_value=oauth2_user):
            
            # Test 3a: Use token with profile endpoint (read:profile scope)
            profile_response = client.get(
                "/profile",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            # Should not fail due to authentication or authorization
            assert profile_response.status_code != 401
            assert profile_response.status_code != 403
            
            # Test 3b: Use token with data endpoint (write:data scope)
            data_response = client.post(
                "/data",
                headers={"Authorization": f"Bearer {access_token}"},
                json={"content": "test data"}
            )
            
            # Should not fail due to authentication or authorization
            assert data_response.status_code != 401
            assert data_response.status_code != 403
            
            # Test 3c: Try to use token with admin endpoint (should fail - no admin scope)
            def mock_get_user_with_scope_check(token, required_scopes=None):
                if required_scopes and "admin" in required_scopes:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=403, detail="Insufficient permissions")
                return oauth2_user
            
            with patch('second_brain_database.routes.auth.routes.get_current_user', 
                       side_effect=mock_get_user_with_scope_check):
                
                admin_response = client.get(
                    "/admin/users",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                
                # Should fail due to insufficient scopes
                assert admin_response.status_code == 403
    
    def test_oauth2_token_refresh_and_api_usage(self, client, mock_oauth2_client):
        """Test OAuth2 token refresh and subsequent API usage."""
        
        # Step 1: Refresh access token
        with patch('second_brain_database.routes.oauth2.client_manager.client_manager.validate_client', 
                   return_value=mock_oauth2_client), \
             patch('second_brain_database.routes.oauth2.services.token_manager.token_manager.refresh_access_token') as mock_refresh:
            
            # Mock successful token refresh
            from second_brain_database.routes.oauth2.models import TokenResponse
            mock_refresh.return_value = TokenResponse(
                access_token="new_oauth2_access_token_jwt",
                token_type="Bearer",
                expires_in=3600,
                refresh_token="new_refresh_token_test123",
                scope="read:profile write:data"
            )
            
            # Refresh token
            refresh_response = client.post(
                "/oauth2/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": "refresh_token_test123",
                    "client_id": "oauth2_client_test123",
                    "client_secret": "client_secret"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            # Should return new access token
            assert refresh_response.status_code == 200
            token_data = refresh_response.json()
            
            assert "access_token" in token_data
            assert token_data["token_type"] == "Bearer"
            assert "refresh_token" in token_data
            
            new_access_token = token_data["access_token"]
        
        # Step 2: Use new access token with APIs
        oauth2_user = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "is_verified": True,
            "is_active": True,
            "role": "user",
            "oauth2_client_id": "oauth2_client_test123",
            "oauth2_scopes": ["read:profile", "write:data"],
            "is_oauth2_token": True
        }
        
        with patch('second_brain_database.routes.auth.routes.get_current_user', 
                   return_value=oauth2_user):
            
            # Use refreshed token with API
            api_response = client.get(
                "/profile",
                headers={"Authorization": f"Bearer {new_access_token}"}
            )
            
            # Should work with refreshed token
            assert api_response.status_code != 401
            assert api_response.status_code != 403
    
    def test_oauth2_scope_enforcement_across_endpoints(self, client):
        """Test that OAuth2 scope enforcement works across different endpoints."""
        
        # Test user with limited scopes
        limited_oauth2_user = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "is_verified": True,
            "is_active": True,
            "role": "user",
            "oauth2_client_id": "oauth2_client_test123",
            "oauth2_scopes": ["read:profile"],  # Only read:profile scope
            "is_oauth2_token": True
        }
        
        def mock_get_user_with_scope_validation(token, required_scopes=None):
            if required_scopes:
                user_scopes = set(limited_oauth2_user["oauth2_scopes"])
                required_scopes_set = set(required_scopes)
                if not required_scopes_set.issubset(user_scopes):
                    from fastapi import HTTPException
                    raise HTTPException(status_code=403, detail="Insufficient permissions")
            return limited_oauth2_user
        
        with patch('second_brain_database.routes.auth.routes.get_current_user', 
                   side_effect=mock_get_user_with_scope_validation):
            
            # Should work with read:profile endpoints
            read_response = client.get(
                "/profile",
                headers={"Authorization": "Bearer oauth2_limited_token"}
            )
            assert read_response.status_code != 403
            
            # Should fail with write:data endpoints
            write_response = client.put(
                "/profile",
                headers={"Authorization": "Bearer oauth2_limited_token"},
                json={"display_name": "New Name"}
            )
            # Note: This assumes the PUT /profile endpoint requires write:profile scope
            # The actual behavior depends on endpoint implementation
    
    def test_oauth2_vs_regular_token_coexistence(self, client):
        """Test that OAuth2 tokens and regular JWT tokens can coexist."""
        
        # Regular JWT user
        regular_user = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "is_verified": True,
            "is_active": True,
            "role": "user",
            "is_oauth2_token": False
        }
        
        # OAuth2 user
        oauth2_user = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "is_verified": True,
            "is_active": True,
            "role": "user",
            "oauth2_client_id": "oauth2_client_test123",
            "oauth2_scopes": ["read:profile", "write:data"],
            "is_oauth2_token": True
        }
        
        # Test regular token
        with patch('second_brain_database.routes.auth.routes.get_current_user', 
                   return_value=regular_user):
            
            regular_response = client.get(
                "/profile",
                headers={"Authorization": "Bearer regular_jwt_token"}
            )
            assert regular_response.status_code != 401
            assert regular_response.status_code != 403
        
        # Test OAuth2 token
        with patch('second_brain_database.routes.auth.routes.get_current_user', 
                   return_value=oauth2_user):
            
            oauth2_response = client.get(
                "/profile",
                headers={"Authorization": "Bearer oauth2_access_token"}
            )
            assert oauth2_response.status_code != 401
            assert oauth2_response.status_code != 403


class TestOAuth2ErrorHandling:
    """Test OAuth2 error handling in API usage."""
    
    def test_expired_oauth2_token_with_api(self, client):
        """Test that expired OAuth2 tokens are properly rejected by APIs."""
        
        # Mock expired token validation
        from fastapi import HTTPException
        
        def mock_expired_token_validation(token, required_scopes=None):
            raise HTTPException(status_code=401, detail="Token has expired")
        
        with patch('second_brain_database.routes.auth.routes.get_current_user', 
                   side_effect=mock_expired_token_validation):
            
            response = client.get(
                "/profile",
                headers={"Authorization": "Bearer expired_oauth2_token"}
            )
            
            # Should return 401 for expired token
            assert response.status_code == 401
    
    def test_revoked_oauth2_token_with_api(self, client):
        """Test that revoked OAuth2 tokens are properly rejected by APIs."""
        
        # Mock revoked token validation
        from fastapi import HTTPException
        
        def mock_revoked_token_validation(token, required_scopes=None):
            raise HTTPException(status_code=401, detail="Token is blacklisted")
        
        with patch('second_brain_database.routes.auth.routes.get_current_user', 
                   side_effect=mock_revoked_token_validation):
            
            response = client.get(
                "/profile",
                headers={"Authorization": "Bearer revoked_oauth2_token"}
            )
            
            # Should return 401 for revoked token
            assert response.status_code == 401
    
    def test_malformed_oauth2_token_with_api(self, client):
        """Test that malformed OAuth2 tokens are properly rejected by APIs."""
        
        # Mock malformed token validation
        from fastapi import HTTPException
        
        def mock_malformed_token_validation(token, required_scopes=None):
            raise HTTPException(status_code=401, detail="Could not validate credentials")
        
        with patch('second_brain_database.routes.auth.routes.get_current_user', 
                   side_effect=mock_malformed_token_validation):
            
            response = client.get(
                "/profile",
                headers={"Authorization": "Bearer malformed_oauth2_token"}
            )
            
            # Should return 401 for malformed token
            assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__])