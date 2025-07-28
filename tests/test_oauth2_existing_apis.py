"""
Test OAuth2 token integration with existing API endpoints.

This module tests that OAuth2 access tokens work correctly with existing
protected API endpoints, ensuring backward compatibility and proper scope validation.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime, timedelta

from second_brain_database.main import app
from second_brain_database.routes.auth.services.auth.login import create_access_token


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock user document."""
    return {
        "_id": "test_user_id",
        "username": "testuser",
        "email": "test@example.com",
        "is_verified": True,
        "is_active": True,
        "role": "user",
        "token_version": 1,
        "hashed_password": "hashed_password_here"
    }


@pytest.fixture
def mock_admin_user():
    """Mock admin user document."""
    return {
        "_id": "admin_user_id",
        "username": "adminuser",
        "email": "admin@example.com",
        "is_verified": True,
        "is_active": True,
        "role": "admin",
        "token_version": 1,
        "hashed_password": "hashed_password_here"
    }


class TestOAuth2TokenWithAuthEndpoints:
    """Test OAuth2 tokens with authentication-related endpoints."""
    
    def test_oauth2_token_refresh_endpoint(self, client, mock_user):
        """Test OAuth2 token with token refresh endpoint."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["read:profile"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            with patch("second_brain_database.routes.auth.services.auth.login.create_access_token") as mock_create:
                mock_create.return_value = "new_access_token"
                
                # Test refresh endpoint with OAuth2 token
                response = client.post(
                    "/auth/refresh",
                    headers={"Authorization": "Bearer oauth2_access_token"}
                )
                
                # Should work - OAuth2 tokens can be refreshed
                assert response.status_code == 200
                data = response.json()
                assert "access_token" in data
    
    def test_oauth2_token_logout_endpoint(self, client, mock_user):
        """Test OAuth2 token with logout endpoint."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["read:profile"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            with patch("second_brain_database.routes.auth.services.security.tokens.blacklist_token") as mock_blacklist:
                mock_blacklist.return_value = True
                
                # Test logout endpoint with OAuth2 token
                response = client.post(
                    "/auth/logout",
                    headers={"Authorization": "Bearer oauth2_access_token"}
                )
                
                # Should work - OAuth2 tokens can be logged out
                assert response.status_code == 200
    
    def test_oauth2_token_validate_endpoint(self, client, mock_user):
        """Test OAuth2 token with token validation endpoint."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["read:profile"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            # Test validate token endpoint with OAuth2 token
            response = client.get(
                "/auth/validate-token",
                headers={"Authorization": "Bearer oauth2_access_token"}
            )
            
            # Should work - OAuth2 tokens can be validated
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert data["username"] == "testuser"


class TestOAuth2TokenWithProfileEndpoints:
    """Test OAuth2 tokens with profile-related endpoints."""
    
    def test_oauth2_token_with_profile_read_scope(self, client, mock_user):
        """Test OAuth2 token with read:profile scope accessing profile endpoints."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["read:profile"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            # Test profile endpoints that should work with read:profile scope
            endpoints_to_test = [
                "/profile/me",
                "/profile/settings",
                "/profile/preferences"
            ]
            
            for endpoint in endpoints_to_test:
                response = client.get(
                    endpoint,
                    headers={"Authorization": "Bearer oauth2_access_token"}
                )
                
                # Should either work (200) or endpoint doesn't exist (404)
                # Should not be forbidden (403) with proper scope
                assert response.status_code in [200, 404], f"Endpoint {endpoint} failed with {response.status_code}"
    
    def test_oauth2_token_insufficient_scope_profile_write(self, client, mock_user):
        """Test OAuth2 token with insufficient scope for profile write operations."""
        # Create a dependency that requires write:profile scope
        from second_brain_database.routes.auth.routes import require_oauth2_scopes
        
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            # Mock get_current_user to simulate scope validation failure
            from fastapi import HTTPException
            mock_get_user.side_effect = HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            )
            
            # Test profile write endpoints that should fail with read-only scope
            response = client.put(
                "/profile/me",
                headers={"Authorization": "Bearer oauth2_access_token_read_only"},
                json={"display_name": "New Name"}
            )
            
            assert response.status_code == 403


class TestOAuth2TokenWithDataEndpoints:
    """Test OAuth2 tokens with data-related endpoints."""
    
    def test_oauth2_token_with_data_read_scope(self, client, mock_user):
        """Test OAuth2 token with read:data scope."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["read:data"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            # Test data read endpoints
            endpoints_to_test = [
                "/data/documents",
                "/data/search",
                "/data/export"
            ]
            
            for endpoint in endpoints_to_test:
                response = client.get(
                    endpoint,
                    headers={"Authorization": "Bearer oauth2_access_token"}
                )
                
                # Should either work (200) or endpoint doesn't exist (404)
                assert response.status_code in [200, 404], f"Endpoint {endpoint} failed with {response.status_code}"
    
    def test_oauth2_token_with_data_write_scope(self, client, mock_user):
        """Test OAuth2 token with write:data scope."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["write:data"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            # Test data write endpoints
            test_data = {"title": "Test Document", "content": "Test content"}
            
            response = client.post(
                "/data/documents",
                headers={"Authorization": "Bearer oauth2_access_token"},
                json=test_data
            )
            
            # Should either work (200/201) or endpoint doesn't exist (404)
            assert response.status_code in [200, 201, 404]


class TestOAuth2TokenWithAdminEndpoints:
    """Test OAuth2 tokens with admin endpoints."""
    
    def test_oauth2_token_with_admin_scope(self, client, mock_admin_user):
        """Test OAuth2 token with admin scope."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_admin_with_oauth2 = mock_admin_user.copy()
            mock_admin_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["admin"]
            })
            mock_get_user.return_value = mock_admin_with_oauth2
            
            # Test admin endpoints
            endpoints_to_test = [
                "/admin/users",
                "/admin/clients",
                "/admin/system"
            ]
            
            for endpoint in endpoints_to_test:
                response = client.get(
                    endpoint,
                    headers={"Authorization": "Bearer oauth2_admin_token"}
                )
                
                # Should either work (200) or endpoint doesn't exist (404)
                assert response.status_code in [200, 404], f"Admin endpoint {endpoint} failed with {response.status_code}"
    
    def test_oauth2_token_without_admin_scope_admin_endpoint(self, client, mock_user):
        """Test OAuth2 token without admin scope accessing admin endpoints."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            # Mock require_admin dependency to raise 403
            from fastapi import HTTPException
            mock_get_user.side_effect = HTTPException(
                status_code=403,
                detail="Admin privileges required."
            )
            
            # Test admin endpoint with non-admin OAuth2 token
            response = client.get(
                "/admin/users",
                headers={"Authorization": "Bearer oauth2_user_token"}
            )
            
            assert response.status_code == 403


class TestOAuth2TokenWithTokenEndpoints:
    """Test OAuth2 tokens with token management endpoints."""
    
    def test_oauth2_token_with_tokens_read_scope(self, client, mock_user):
        """Test OAuth2 token with read:tokens scope."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["read:tokens"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            with patch("second_brain_database.database.db_manager") as mock_db:
                mock_collection = MagicMock()
                mock_collection.find.return_value.to_list = AsyncMock(return_value=[])
                mock_db.get_collection.return_value = mock_collection
                
                # Test token list endpoint
                response = client.get(
                    "/auth/permanent-tokens",
                    headers={"Authorization": "Bearer oauth2_access_token"}
                )
                
                # Should work with read:tokens scope
                assert response.status_code == 200
    
    def test_oauth2_token_with_tokens_write_scope(self, client, mock_user):
        """Test OAuth2 token with write:tokens scope."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["write:tokens"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            with patch("second_brain_database.database.db_manager") as mock_db:
                mock_collection = MagicMock()
                mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="token_id"))
                mock_db.get_collection.return_value = mock_collection
                
                # Test token creation endpoint
                response = client.post(
                    "/auth/permanent-tokens",
                    headers={"Authorization": "Bearer oauth2_access_token"},
                    json={"name": "Test Token", "description": "Test token description"}
                )
                
                # Should work with write:tokens scope
                assert response.status_code in [200, 201]


class TestOAuth2TokenCompatibility:
    """Test OAuth2 token compatibility with existing authentication flows."""
    
    def test_mixed_token_types_same_user(self, client, mock_user):
        """Test that both regular JWT and OAuth2 tokens work for the same user."""
        # Test regular JWT token
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_regular = mock_user.copy()
            mock_user_regular["is_oauth2_token"] = False
            mock_get_user.return_value = mock_user_regular
            
            response = client.get(
                "/auth/validate-token",
                headers={"Authorization": "Bearer regular_jwt_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
        
        # Test OAuth2 token for same user
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_oauth2 = mock_user.copy()
            mock_user_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["read:profile"]
            })
            mock_get_user.return_value = mock_user_oauth2
            
            response = client.get(
                "/auth/validate-token",
                headers={"Authorization": "Bearer oauth2_access_token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
    
    def test_oauth2_token_with_existing_middleware(self, client, mock_user):
        """Test OAuth2 tokens work with existing authentication middleware."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            mock_user_with_oauth2 = mock_user.copy()
            mock_user_with_oauth2.update({
                "is_oauth2_token": True,
                "oauth2_client_id": "test_client_123",
                "oauth2_scopes": ["read:profile"]
            })
            mock_get_user.return_value = mock_user_with_oauth2
            
            # Test that OAuth2 tokens work with rate limiting and other middleware
            response = client.get(
                "/auth/validate-token",
                headers={"Authorization": "Bearer oauth2_access_token"}
            )
            
            assert response.status_code == 200


class TestOAuth2TokenErrorHandling:
    """Test error handling for OAuth2 tokens."""
    
    def test_malformed_oauth2_token(self, client):
        """Test handling of malformed OAuth2 tokens."""
        response = client.get(
            "/auth/validate-token",
            headers={"Authorization": "Bearer malformed.oauth2.token"}
        )
        
        assert response.status_code == 401
    
    def test_expired_oauth2_token(self, client):
        """Test handling of expired OAuth2 tokens."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            from fastapi import HTTPException
            mock_get_user.side_effect = HTTPException(
                status_code=401,
                detail="Token has expired"
            )
            
            response = client.get(
                "/auth/validate-token",
                headers={"Authorization": "Bearer expired_oauth2_token"}
            )
            
            assert response.status_code == 401
    
    def test_oauth2_token_user_not_found(self, client):
        """Test handling when OAuth2 token user is not found."""
        with patch("second_brain_database.routes.auth.services.auth.login.get_current_user") as mock_get_user:
            from fastapi import HTTPException
            mock_get_user.side_effect = HTTPException(
                status_code=401,
                detail="Could not validate credentials"
            )
            
            response = client.get(
                "/auth/validate-token",
                headers={"Authorization": "Bearer oauth2_token_invalid_user"}
            )
            
            assert response.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])