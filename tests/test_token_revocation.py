"""
Unit tests for OAuth2 Token Revocation Endpoint.

Tests the token revocation functionality including refresh token revocation,
access token revocation attempts, and error handling.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import status

from src.second_brain_database.main import app
from src.second_brain_database.routes.oauth2.models import RefreshTokenData
from datetime import datetime, timedelta


class TestTokenRevocationEndpoint:
    """Test cases for the OAuth2 token revocation endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return {"username": "test_user", "user_id": "test_user"}
    
    @pytest.fixture
    def mock_client_data(self):
        """Mock OAuth2 client data."""
        return MagicMock(
            client_id="test_client",
            client_secret_hash="hashed_secret",
            name="Test Client",
            client_type="confidential",
            is_active=True
        )
    
    @pytest.fixture
    def sample_token_info(self):
        """Sample token info for testing."""
        return {
            "client_id": "test_client",
            "user_id": "test_user",
            "scopes": ["read:profile"],
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True
        }
    
    @pytest.mark.asyncio
    async def test_revoke_refresh_token_success(self, client, mock_client_data, sample_token_info):
        """Test successful refresh token revocation."""
        with patch('src.second_brain_database.routes.oauth2.routes.oauth2_security_manager') as mock_security, \
             patch('src.second_brain_database.routes.oauth2.routes.client_manager') as mock_client_mgr, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock security and client validation
            mock_security.rate_limit_client = AsyncMock()
            mock_client_mgr.validate_client = AsyncMock(return_value=mock_client_data)
            
            # Mock token operations
            mock_token_mgr.get_token_info = AsyncMock(return_value=sample_token_info)
            mock_token_mgr.revoke_refresh_token = AsyncMock(return_value=True)
            mock_security.log_oauth2_security_event = AsyncMock()
            
            response = client.post(
                "/oauth2/revoke",
                data={
                    "token": "rt_test_refresh_token",
                    "token_type_hint": "refresh_token",
                    "client_id": "test_client",
                    "client_secret": "test_secret"
                }
            )
            
            assert response.status_code == 200
            assert response.json()["revoked"] is True
            
            # Verify token manager was called
            mock_token_mgr.get_token_info.assert_called_once_with("rt_test_refresh_token")
            mock_token_mgr.revoke_refresh_token.assert_called_once_with("rt_test_refresh_token")
            
            # Verify security event was logged
            mock_security.log_oauth2_security_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_revoke_access_token_attempt(self, client, mock_client_data):
        """Test access token revocation attempt (should log but not actually revoke JWT)."""
        with patch('src.second_brain_database.routes.oauth2.routes.oauth2_security_manager') as mock_security, \
             patch('src.second_brain_database.routes.oauth2.routes.client_manager') as mock_client_mgr, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock security and client validation
            mock_security.rate_limit_client = AsyncMock()
            mock_client_mgr.validate_client = AsyncMock(return_value=mock_client_data)
            
            # Mock token operations - token not found as refresh token
            mock_token_mgr.get_token_info = AsyncMock(return_value=None)
            mock_security.log_oauth2_security_event = AsyncMock()
            
            response = client.post(
                "/oauth2/revoke",
                data={
                    "token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.test.jwt",
                    "token_type_hint": "access_token",
                    "client_id": "test_client",
                    "client_secret": "test_secret"
                }
            )
            
            assert response.status_code == 200
            assert response.json()["revoked"] is True
            
            # Verify security event was logged for access token attempt
            mock_security.log_oauth2_security_event.assert_called_once()
            call_args = mock_security.log_oauth2_security_event.call_args[1]
            assert call_args["event_type"] == "token_revocation_attempted"
    
    @pytest.mark.asyncio
    async def test_revoke_token_invalid_client(self, client):
        """Test token revocation with invalid client credentials."""
        with patch('src.second_brain_database.routes.oauth2.routes.oauth2_security_manager') as mock_security, \
             patch('src.second_brain_database.routes.oauth2.routes.client_manager') as mock_client_mgr:
            
            # Mock security and client validation
            mock_security.rate_limit_client = AsyncMock()
            mock_client_mgr.validate_client = AsyncMock(return_value=None)  # Invalid client
            
            response = client.post(
                "/oauth2/revoke",
                data={
                    "token": "rt_test_refresh_token",
                    "client_id": "invalid_client",
                    "client_secret": "wrong_secret"
                }
            )
            
            assert response.status_code == 400
            assert "invalid_client" in response.json()["error"]
    
    @pytest.mark.asyncio
    async def test_revoke_token_client_mismatch(self, client, mock_client_data):
        """Test token revocation when token belongs to different client."""
        with patch('src.second_brain_database.routes.oauth2.routes.oauth2_security_manager') as mock_security, \
             patch('src.second_brain_database.routes.oauth2.routes.client_manager') as mock_client_mgr, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock security and client validation
            mock_security.rate_limit_client = AsyncMock()
            mock_client_mgr.validate_client = AsyncMock(return_value=mock_client_data)
            
            # Mock token info for different client
            token_info = {
                "client_id": "different_client",
                "user_id": "test_user",
                "scopes": ["read:profile"],
                "is_active": True
            }
            mock_token_mgr.get_token_info = AsyncMock(return_value=token_info)
            mock_security.log_oauth2_security_event = AsyncMock()
            
            response = client.post(
                "/oauth2/revoke",
                data={
                    "token": "rt_test_refresh_token",
                    "client_id": "test_client",
                    "client_secret": "test_secret"
                }
            )
            
            # Should still return 200 per RFC 7009 (don't reveal token existence)
            assert response.status_code == 200
            assert response.json()["revoked"] is True
            
            # Should not actually revoke the token
            mock_token_mgr.revoke_refresh_token.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_revoke_token_rate_limited(self, client):
        """Test token revocation when rate limited."""
        from fastapi import HTTPException
        
        with patch('src.second_brain_database.routes.oauth2.routes.oauth2_security_manager') as mock_security:
            # Mock rate limiting to raise exception
            mock_security.rate_limit_client = AsyncMock(
                side_effect=HTTPException(status_code=429, detail="Rate limit exceeded")
            )
            
            response = client.post(
                "/oauth2/revoke",
                data={
                    "token": "rt_test_refresh_token",
                    "client_id": "test_client",
                    "client_secret": "test_secret"
                }
            )
            
            assert response.status_code == 429
    
    @pytest.mark.asyncio
    async def test_revoke_token_missing_parameters(self, client):
        """Test token revocation with missing required parameters."""
        # Missing token parameter
        response = client.post(
            "/oauth2/revoke",
            data={
                "client_id": "test_client",
                "client_secret": "test_secret"
            }
        )
        
        assert response.status_code == 422  # Validation error
        
        # Missing client_id parameter
        response = client.post(
            "/oauth2/revoke",
            data={
                "token": "rt_test_refresh_token",
                "client_secret": "test_secret"
            }
        )
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_revoke_token_server_error(self, client, mock_client_data):
        """Test token revocation with server error."""
        with patch('src.second_brain_database.routes.oauth2.routes.oauth2_security_manager') as mock_security, \
             patch('src.second_brain_database.routes.oauth2.routes.client_manager') as mock_client_mgr, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock security and client validation
            mock_security.rate_limit_client = AsyncMock()
            mock_client_mgr.validate_client = AsyncMock(return_value=mock_client_data)
            
            # Mock token manager to raise exception
            mock_token_mgr.get_token_info = AsyncMock(side_effect=Exception("Database error"))
            mock_security.log_oauth2_security_event = AsyncMock()
            
            response = client.post(
                "/oauth2/revoke",
                data={
                    "token": "rt_test_refresh_token",
                    "client_id": "test_client",
                    "client_secret": "test_secret"
                }
            )
            
            # Should still return 200 per RFC 7009 (don't reveal internal errors)
            assert response.status_code == 200
            assert response.json()["revoked"] is False
            assert "server_error" in response.json()
            
            # Should log security event for error
            mock_security.log_oauth2_security_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_revoke_token_without_type_hint(self, client, mock_client_data, sample_token_info):
        """Test token revocation without token_type_hint (should try refresh token first)."""
        with patch('src.second_brain_database.routes.oauth2.routes.oauth2_security_manager') as mock_security, \
             patch('src.second_brain_database.routes.oauth2.routes.client_manager') as mock_client_mgr, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock security and client validation
            mock_security.rate_limit_client = AsyncMock()
            mock_client_mgr.validate_client = AsyncMock(return_value=mock_client_data)
            
            # Mock token operations
            mock_token_mgr.get_token_info = AsyncMock(return_value=sample_token_info)
            mock_token_mgr.revoke_refresh_token = AsyncMock(return_value=True)
            mock_security.log_oauth2_security_event = AsyncMock()
            
            response = client.post(
                "/oauth2/revoke",
                data={
                    "token": "rt_test_refresh_token",
                    # No token_type_hint provided
                    "client_id": "test_client",
                    "client_secret": "test_secret"
                }
            )
            
            assert response.status_code == 200
            assert response.json()["revoked"] is True
            
            # Should try as refresh token first
            mock_token_mgr.get_token_info.assert_called_once_with("rt_test_refresh_token")
            mock_token_mgr.revoke_refresh_token.assert_called_once_with("rt_test_refresh_token")


class TestTokenCleanupEndpoint:
    """Test cases for the OAuth2 token cleanup endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens_success(self, client):
        """Test successful token cleanup."""
        with patch('src.second_brain_database.routes.oauth2.routes.get_current_user_dep') as mock_auth, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock authentication
            mock_auth.return_value = {"username": "admin_user"}
            
            # Mock token cleanup
            mock_token_mgr.cleanup_expired_tokens = AsyncMock(return_value=5)
            
            response = client.post("/oauth2/cleanup")
            
            assert response.status_code == 200
            response_data = response.json()
            assert "Cleaned up 5 expired tokens" in response_data["message"]
            assert response_data["data"]["cleaned_tokens"] == 5
            
            mock_token_mgr.cleanup_expired_tokens.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens_unauthorized(self, client):
        """Test token cleanup without authentication."""
        response = client.post("/oauth2/cleanup")
        
        assert response.status_code == 401  # Unauthorized
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens_error(self, client):
        """Test token cleanup with error."""
        with patch('src.second_brain_database.routes.oauth2.routes.get_current_user_dep') as mock_auth, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock authentication
            mock_auth.return_value = {"username": "admin_user"}
            
            # Mock token cleanup error
            mock_token_mgr.cleanup_expired_tokens = AsyncMock(side_effect=Exception("Redis error"))
            
            response = client.post("/oauth2/cleanup")
            
            assert response.status_code == 500
            assert "Failed to cleanup expired tokens" in response.json()["detail"]


class TestTokenStatisticsEndpoint:
    """Test cases for the OAuth2 token statistics endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_stats(self):
        """Sample token statistics."""
        return {
            "total_tokens": 10,
            "active_tokens": 8,
            "expired_tokens": 2,
            "unique_clients": 3,
            "unique_users": 5
        }
    
    @pytest.mark.asyncio
    async def test_get_token_statistics_success(self, client, sample_stats):
        """Test successful token statistics retrieval."""
        with patch('src.second_brain_database.routes.oauth2.routes.get_current_user_dep') as mock_auth, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock authentication
            mock_auth.return_value = {"username": "admin_user"}
            
            # Mock token statistics
            mock_token_mgr.get_token_statistics = AsyncMock(return_value=sample_stats)
            
            response = client.get("/oauth2/tokens/stats")
            
            assert response.status_code == 200
            response_data = response.json()
            assert response_data["message"] == "Token statistics retrieved successfully"
            assert response_data["data"] == sample_stats
            
            mock_token_mgr.get_token_statistics.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_token_statistics_unauthorized(self, client):
        """Test token statistics without authentication."""
        response = client.get("/oauth2/tokens/stats")
        
        assert response.status_code == 401  # Unauthorized
    
    @pytest.mark.asyncio
    async def test_get_token_statistics_error(self, client):
        """Test token statistics with error."""
        with patch('src.second_brain_database.routes.oauth2.routes.get_current_user_dep') as mock_auth, \
             patch('src.second_brain_database.routes.oauth2.routes.token_manager') as mock_token_mgr:
            
            # Mock authentication
            mock_auth.return_value = {"username": "admin_user"}
            
            # Mock token statistics error
            mock_token_mgr.get_token_statistics = AsyncMock(side_effect=Exception("Redis error"))
            
            response = client.get("/oauth2/tokens/stats")
            
            assert response.status_code == 500
            assert "Failed to retrieve token statistics" in response.json()["detail"]