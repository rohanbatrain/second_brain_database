"""
Integration tests for OAuth2 token endpoint.

Tests the complete OAuth2 token endpoint functionality including:
- Authorization code exchange for tokens
- Refresh token flows
- Error handling and validation
- PKCE validation
- Client authentication
"""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from second_brain_database.main import app
from second_brain_database.routes.oauth2.services.pkce_validator import PKCEValidator
from second_brain_database.routes.oauth2.models import ClientType, OAuthClient


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_oauth2_client():
    """Mock OAuth2 client for testing."""
    return OAuthClient(
        client_id="test_client_123",
        client_secret_hash="$2b$12$test_hash",
        name="Test Client",
        client_type=ClientType.CONFIDENTIAL,
        redirect_uris=["https://example.com/callback"],
        scopes=["read:profile", "write:data"],
        is_active=True
    )


@pytest.fixture
def mock_auth_code():
    """Mock authorization code for testing."""
    from second_brain_database.routes.oauth2.models import AuthorizationCode, PKCEMethod
    
    return AuthorizationCode(
        code="auth_code_test123",
        client_id="test_client_123",
        user_id="test_user",
        redirect_uri="https://example.com/callback",
        scopes=["read:profile", "write:data"],
        code_challenge="dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
        code_challenge_method=PKCEMethod.S256,
        expires_at=datetime.utcnow() + timedelta(minutes=10),
        used=False
    )


class TestOAuth2TokenEndpoint:
    """Test OAuth2 token endpoint functionality."""
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    @patch('second_brain_database.routes.oauth2.routes.auth_code_manager.use_authorization_code')
    @patch('second_brain_database.routes.oauth2.routes.create_access_token')
    @patch('second_brain_database.routes.oauth2.routes._generate_refresh_token')
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.log_oauth2_security_event')
    async def test_authorization_code_grant_success(
        self,
        mock_log_event,
        mock_generate_refresh,
        mock_create_token,
        mock_use_code,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client,
        mock_auth_code
    ):
        """Test successful authorization code grant."""
        # Setup mocks
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        mock_use_code.return_value = mock_auth_code
        mock_create_token.return_value = "access_token_123"
        mock_generate_refresh.return_value = "refresh_token_123"
        mock_log_event.return_value = None
        
        # Generate valid PKCE verifier and challenge
        verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        mock_auth_code.code_challenge = challenge
        
        # Make token request
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": "auth_code_test123",
            "redirect_uri": "https://example.com/callback",
            "client_id": "test_client_123",
            "client_secret": "test_secret",
            "code_verifier": verifier
        })
        
        # Verify response
        assert response.status_code == 200
        token_data = response.json()
        
        assert token_data["access_token"] == "access_token_123"
        assert token_data["token_type"] == "Bearer"
        assert token_data["expires_in"] == 1800  # 30 minutes from settings
        assert token_data["refresh_token"] == "refresh_token_123"
        assert token_data["scope"] == "read:profile write:data"
        
        # Verify mocks were called correctly
        mock_validate_client.assert_called_once_with("test_client_123", "test_secret")
        mock_use_code.assert_called_once_with("auth_code_test123")
        mock_create_token.assert_called_once_with({"sub": "test_user"})
        mock_generate_refresh.assert_called_once_with(
            client_id="test_client_123",
            user_id="test_user",
            scopes=["read:profile", "write:data"]
        )
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    async def test_invalid_grant_type(
        self,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client
    ):
        """Test invalid grant type error."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        
        response = client.post("/oauth2/token", data={
            "grant_type": "invalid_grant",
            "client_id": "test_client_123",
            "client_secret": "test_secret"
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "unsupported_grant_type"
        assert "not supported" in error_data["error_description"]
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    async def test_invalid_client_credentials(
        self,
        mock_validate_client,
        mock_rate_limit,
        client
    ):
        """Test invalid client credentials error."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = None  # Invalid client
        
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": "auth_code_test123",
            "client_id": "invalid_client",
            "client_secret": "invalid_secret"
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "invalid_client"
        assert "authentication failed" in error_data["error_description"]
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    @patch('second_brain_database.routes.oauth2.routes.auth_code_manager.use_authorization_code')
    async def test_invalid_authorization_code(
        self,
        mock_use_code,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client
    ):
        """Test invalid authorization code error."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        mock_use_code.return_value = None  # Invalid code
        
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": "invalid_code",
            "redirect_uri": "https://example.com/callback",
            "client_id": "test_client_123",
            "client_secret": "test_secret",
            "code_verifier": "test_verifier"
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "invalid_grant"
        assert "Invalid or expired authorization code" in error_data["error_description"]
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    @patch('second_brain_database.routes.oauth2.routes.auth_code_manager.use_authorization_code')
    async def test_client_mismatch(
        self,
        mock_use_code,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client,
        mock_auth_code
    ):
        """Test client mismatch error."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        
        # Set different client ID in auth code
        mock_auth_code.client_id = "different_client"
        mock_use_code.return_value = mock_auth_code
        
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": "auth_code_test123",
            "redirect_uri": "https://example.com/callback",
            "client_id": "test_client_123",
            "client_secret": "test_secret",
            "code_verifier": "test_verifier"
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "invalid_grant"
        assert "different client" in error_data["error_description"]
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    @patch('second_brain_database.routes.oauth2.routes.auth_code_manager.use_authorization_code')
    async def test_redirect_uri_mismatch(
        self,
        mock_use_code,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client,
        mock_auth_code
    ):
        """Test redirect URI mismatch error."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        mock_use_code.return_value = mock_auth_code
        
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": "auth_code_test123",
            "redirect_uri": "https://different.com/callback",  # Different URI
            "client_id": "test_client_123",
            "client_secret": "test_secret",
            "code_verifier": "test_verifier"
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "invalid_grant"
        assert "does not match" in error_data["error_description"]
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    @patch('second_brain_database.routes.oauth2.routes.auth_code_manager.use_authorization_code')
    async def test_pkce_validation_failure(
        self,
        mock_use_code,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client,
        mock_auth_code
    ):
        """Test PKCE validation failure."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        mock_use_code.return_value = mock_auth_code
        
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code",
            "code": "auth_code_test123",
            "redirect_uri": "https://example.com/callback",
            "client_id": "test_client_123",
            "client_secret": "test_secret",
            "code_verifier": "wrong_verifier"  # Wrong verifier
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "invalid_grant"
        assert "PKCE" in error_data["error_description"]
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    @patch('second_brain_database.routes.oauth2.routes._validate_refresh_token')
    @patch('second_brain_database.routes.oauth2.routes.create_access_token')
    @patch('second_brain_database.routes.oauth2.routes._rotate_refresh_token')
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.log_oauth2_security_event')
    async def test_refresh_token_grant_success(
        self,
        mock_log_event,
        mock_rotate_token,
        mock_create_token,
        mock_validate_refresh,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client
    ):
        """Test successful refresh token grant."""
        # Setup mocks
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        mock_validate_refresh.return_value = {
            "user_id": "test_user",
            "scopes": ["read:profile", "write:data"]
        }
        mock_create_token.return_value = "new_access_token_123"
        mock_rotate_token.return_value = "new_refresh_token_123"
        mock_log_event.return_value = None
        
        response = client.post("/oauth2/token", data={
            "grant_type": "refresh_token",
            "refresh_token": "refresh_token_123",
            "client_id": "test_client_123",
            "client_secret": "test_secret"
        })
        
        assert response.status_code == 200
        token_data = response.json()
        
        assert token_data["access_token"] == "new_access_token_123"
        assert token_data["token_type"] == "Bearer"
        assert token_data["refresh_token"] == "new_refresh_token_123"
        assert token_data["scope"] == "read:profile write:data"
        
        # Verify mocks were called correctly
        mock_validate_refresh.assert_called_once_with("refresh_token_123", "test_client_123")
        mock_create_token.assert_called_once_with({"sub": "test_user"})
        mock_rotate_token.assert_called_once_with(
            old_refresh_token="refresh_token_123",
            client_id="test_client_123",
            user_id="test_user",
            scopes=["read:profile", "write:data"]
        )
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    @patch('second_brain_database.routes.oauth2.routes._validate_refresh_token')
    async def test_invalid_refresh_token(
        self,
        mock_validate_refresh,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client
    ):
        """Test invalid refresh token error."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        mock_validate_refresh.return_value = None  # Invalid refresh token
        
        response = client.post("/oauth2/token", data={
            "grant_type": "refresh_token",
            "refresh_token": "invalid_refresh_token",
            "client_id": "test_client_123",
            "client_secret": "test_secret"
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "invalid_grant"
        assert "Invalid refresh token" in error_data["error_description"]
    
    async def test_missing_required_parameters(self, client):
        """Test missing required parameters."""
        # Missing grant_type
        response = client.post("/oauth2/token", data={
            "client_id": "test_client_123"
        })
        assert response.status_code == 422  # Validation error
        
        # Missing client_id
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code"
        })
        assert response.status_code == 422  # Validation error
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    async def test_missing_authorization_code(
        self,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client
    ):
        """Test missing authorization code parameter."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code",
            "client_id": "test_client_123",
            "client_secret": "test_secret"
            # Missing code parameter
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "invalid_request"
        assert "Authorization code is required" in error_data["error_description"]
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.client_manager.validate_client')
    async def test_missing_refresh_token(
        self,
        mock_validate_client,
        mock_rate_limit,
        client,
        mock_oauth2_client
    ):
        """Test missing refresh token parameter."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = mock_oauth2_client
        
        response = client.post("/oauth2/token", data={
            "grant_type": "refresh_token",
            "client_id": "test_client_123",
            "client_secret": "test_secret"
            # Missing refresh_token parameter
        })
        
        assert response.status_code == 400
        error_data = response.json()
        assert error_data["error"] == "invalid_request"
        assert "Refresh token is required" in error_data["error_description"]


class TestRefreshTokenManagement:
    """Test refresh token management functions."""
    
    @patch('second_brain_database.routes.oauth2.routes.redis_manager.setex')
    async def test_generate_refresh_token_success(self, mock_setex):
        """Test successful refresh token generation."""
        from second_brain_database.routes.oauth2.routes import _generate_refresh_token
        
        mock_setex.return_value = True
        
        token = await _generate_refresh_token(
            client_id="test_client",
            user_id="test_user",
            scopes=["read:profile"]
        )
        
        assert token is not None
        assert token.startswith("rt_")
        assert len(token) == 35  # rt_ + 32 chars
        
        # Verify Redis call
        mock_setex.assert_called_once()
        args = mock_setex.call_args
        assert args[0][1] == 30 * 24 * 60 * 60  # 30 days TTL
    
    @patch('second_brain_database.routes.oauth2.routes.redis_manager.get')
    async def test_validate_refresh_token_success(self, mock_get):
        """Test successful refresh token validation."""
        from second_brain_database.routes.oauth2.routes import _validate_refresh_token
        
        token_data = {
            "client_id": "test_client",
            "user_id": "test_user",
            "scopes": ["read:profile"],
            "is_active": True
        }
        mock_get.return_value = json.dumps(token_data)
        
        result = await _validate_refresh_token("rt_test123", "test_client")
        
        assert result is not None
        assert result["client_id"] == "test_client"
        assert result["user_id"] == "test_user"
        assert result["scopes"] == ["read:profile"]
    
    @patch('second_brain_database.routes.oauth2.routes.redis_manager.get')
    async def test_validate_refresh_token_not_found(self, mock_get):
        """Test refresh token not found."""
        from second_brain_database.routes.oauth2.routes import _validate_refresh_token
        
        mock_get.return_value = None
        
        result = await _validate_refresh_token("rt_invalid", "test_client")
        
        assert result is None
    
    @patch('second_brain_database.routes.oauth2.routes.redis_manager.delete')
    @patch('second_brain_database.routes.oauth2.routes._generate_refresh_token')
    async def test_rotate_refresh_token_success(self, mock_generate, mock_delete):
        """Test successful refresh token rotation."""
        from second_brain_database.routes.oauth2.routes import _rotate_refresh_token
        
        mock_delete.return_value = 1
        mock_generate.return_value = "rt_new123"
        
        new_token = await _rotate_refresh_token(
            old_refresh_token="rt_old123",
            client_id="test_client",
            user_id="test_user",
            scopes=["read:profile"]
        )
        
        assert new_token == "rt_new123"
        mock_delete.assert_called_once()
        mock_generate.assert_called_once_with("test_client", "test_user", ["read:profile"])
    
    @patch('second_brain_database.routes.oauth2.routes.redis_manager.delete')
    async def test_revoke_refresh_token_success(self, mock_delete):
        """Test successful refresh token revocation."""
        from second_brain_database.routes.oauth2.routes import _revoke_refresh_token
        
        mock_delete.return_value = 1
        
        result = await _revoke_refresh_token("rt_test123")
        
        assert result is True
        mock_delete.assert_called_once()
    
    @patch('second_brain_database.routes.oauth2.routes.redis_manager.delete')
    async def test_revoke_refresh_token_not_found(self, mock_delete):
        """Test refresh token revocation when token not found."""
        from second_brain_database.routes.oauth2.routes import _revoke_refresh_token
        
        mock_delete.return_value = 0
        
        result = await _revoke_refresh_token("rt_invalid")
        
        assert result is False