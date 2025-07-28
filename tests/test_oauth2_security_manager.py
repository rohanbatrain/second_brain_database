"""
Unit tests for OAuth2SecurityManager.

Tests comprehensive OAuth2 security functionality including:
- Redirect URI validation against registered client URIs
- State parameter generation and validation for CSRF protection
- Integration with existing security_manager for rate limiting
- OAuth2-specific security validations and protections
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

# Mock the database connection before importing the modules
with patch('second_brain_database.database.db_manager') as mock_db_manager:
    mock_db_manager.get_collection.return_value = MagicMock()
    from second_brain_database.routes.oauth2.security_manager import OAuth2SecurityManager, oauth2_security_manager
    from second_brain_database.routes.oauth2.models import OAuthClient, ClientType


# Global fixtures accessible to all test classes
@pytest.fixture
def security_manager():
    """Create OAuth2SecurityManager instance for testing."""
    return OAuth2SecurityManager()

@pytest.fixture
def mock_request():
    """Create mock FastAPI request."""
    request = MagicMock(spec=Request)
    request.client.host = "127.0.0.1"
    request.headers = {}
    return request

@pytest.fixture
def sample_client():
    """Create sample OAuth2 client for testing."""
    return OAuthClient(
        client_id="test_client_123",
        client_secret_hash="hashed_secret",
        name="Test Client",
        client_type=ClientType.CONFIDENTIAL,
        redirect_uris=[
            "https://example.com/callback",
            "https://app.example.com/oauth/callback",
            "http://localhost:3000/callback"
        ],
        scopes=["read:profile", "write:data"],
        is_active=True
    )


class TestOAuth2SecurityManager:
    """Test cases for OAuth2SecurityManager."""


class TestRedirectURIValidation:
    """Test redirect URI validation functionality."""
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_success(self, security_manager, sample_client):
        """Test successful redirect URI validation."""
        with patch.object(security_manager.client_manager, 'validate_redirect_uri', return_value=True):
            result = await security_manager.validate_redirect_uri(
                "test_client_123",
                "https://example.com/callback"
            )
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_not_registered(self, security_manager):
        """Test redirect URI validation with unregistered URI."""
        with patch.object(security_manager.client_manager, 'validate_redirect_uri', return_value=False):
            result = await security_manager.validate_redirect_uri(
                "test_client_123",
                "https://malicious.com/callback"
            )
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_invalid_format(self, security_manager):
        """Test redirect URI validation with invalid format."""
        result = await security_manager.validate_redirect_uri(
            "test_client_123",
            "not-a-valid-uri"
        )
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_insecure_scheme(self, security_manager):
        """Test redirect URI validation with insecure scheme."""
        result = await security_manager.validate_redirect_uri(
            "test_client_123",
            "http://example.com/callback"  # HTTP not allowed for non-localhost
        )
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_dangerous_scheme(self, security_manager):
        """Test redirect URI validation with dangerous scheme."""
        dangerous_uris = [
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "vbscript:msgbox('xss')"
        ]
        
        for uri in dangerous_uris:
            result = await security_manager.validate_redirect_uri("test_client_123", uri)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_localhost_http_allowed(self, security_manager):
        """Test that HTTP is allowed for localhost."""
        localhost_uris = [
            "http://localhost:3000/callback",
            "http://127.0.0.1:8080/callback"
        ]
        
        with patch.object(security_manager.client_manager, 'validate_redirect_uri', return_value=True):
            for uri in localhost_uris:
                result = await security_manager.validate_redirect_uri("test_client_123", uri)
                assert result is True


class TestStateParameterHandling:
    """Test state parameter generation and validation."""
    
    def test_generate_secure_state_default_length(self, security_manager):
        """Test secure state generation with default length."""
        state = security_manager.generate_secure_state()
        assert len(state) == 32
        assert all(c.isalnum() or c in '-_' for c in state)
    
    def test_generate_secure_state_custom_length(self, security_manager):
        """Test secure state generation with custom length."""
        state = security_manager.generate_secure_state(length=16)
        assert len(state) == 16
        assert all(c.isalnum() or c in '-_' for c in state)
    
    def test_generate_secure_state_uniqueness(self, security_manager):
        """Test that generated states are unique."""
        states = [security_manager.generate_secure_state() for _ in range(100)]
        assert len(set(states)) == 100  # All should be unique
    
    @pytest.mark.asyncio
    async def test_store_state_success(self, security_manager):
        """Test successful state storage."""
        mock_redis = AsyncMock()
        
        with patch.object(security_manager.redis_manager, 'get_redis', return_value=mock_redis):
            result = await security_manager.store_state(
                "test_state_123",
                "client_123",
                "user_456"
            )
            
            assert result is True
            mock_redis.hset.assert_called_once()
            mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_store_state_redis_error(self, security_manager):
        """Test state storage with Redis error."""
        mock_redis = AsyncMock()
        mock_redis.hset.side_effect = Exception("Redis error")
        
        with patch.object(security_manager.redis_manager, 'get_redis', return_value=mock_redis):
            result = await security_manager.store_state(
                "test_state_123",
                "client_123",
                "user_456"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_state_success(self, security_manager):
        """Test successful state validation."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "client_id": "client_123",
            "user_id": "user_456",
            "created_at": "1234567890"
        }
        
        with patch.object(security_manager.redis_manager, 'get_redis', return_value=mock_redis):
            result = await security_manager.validate_state(
                "test_state_123",
                "client_123",
                "user_456"
            )
            
            assert result is True
            mock_redis.delete.assert_called_once_with("oauth2:state:test_state_123")
    
    @pytest.mark.asyncio
    async def test_validate_state_not_found(self, security_manager):
        """Test state validation with state not found."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {}
        
        with patch.object(security_manager.redis_manager, 'get_redis', return_value=mock_redis):
            result = await security_manager.validate_state(
                "nonexistent_state",
                "client_123",
                "user_456"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_state_client_mismatch(self, security_manager):
        """Test state validation with client ID mismatch."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "client_id": "different_client",
            "user_id": "user_456",
            "created_at": "1234567890"
        }
        
        with patch.object(security_manager.redis_manager, 'get_redis', return_value=mock_redis):
            result = await security_manager.validate_state(
                "test_state_123",
                "client_123",
                "user_456"
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_state_user_mismatch(self, security_manager):
        """Test state validation with user ID mismatch."""
        mock_redis = AsyncMock()
        mock_redis.hgetall.return_value = {
            "client_id": "client_123",
            "user_id": "different_user",
            "created_at": "1234567890"
        }
        
        with patch.object(security_manager.redis_manager, 'get_redis', return_value=mock_redis):
            result = await security_manager.validate_state(
                "test_state_123",
                "client_123",
                "user_456"
            )
            
            assert result is False


class TestRateLimiting:
    """Test OAuth2 rate limiting integration."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_client_success(self, security_manager, mock_request):
        """Test successful rate limiting check."""
        with patch.object(security_manager.security_manager, 'check_rate_limit') as mock_check:
            await security_manager.rate_limit_client(
                mock_request,
                "client_123",
                "authorize"
            )
            
            mock_check.assert_called_once_with(
                request=mock_request,
                action="oauth2_authorize_client_123",
                rate_limit_requests=None,
                rate_limit_period=None
            )
    
    @pytest.mark.asyncio
    async def test_rate_limit_client_exceeded(self, security_manager, mock_request):
        """Test rate limit exceeded."""
        with patch.object(security_manager.security_manager, 'check_rate_limit') as mock_check:
            mock_check.side_effect = HTTPException(status_code=429, detail="Rate limit exceeded")
            
            with pytest.raises(HTTPException) as exc_info:
                await security_manager.rate_limit_client(
                    mock_request,
                    "client_123",
                    "token"
                )
            
            assert exc_info.value.status_code == 429
    
    @pytest.mark.asyncio
    async def test_rate_limit_client_custom_limits(self, security_manager, mock_request):
        """Test rate limiting with custom limits."""
        with patch.object(security_manager.security_manager, 'check_rate_limit') as mock_check:
            await security_manager.rate_limit_client(
                mock_request,
                "client_123",
                "authorize",
                rate_limit_requests=10,
                rate_limit_period=60
            )
            
            mock_check.assert_called_once_with(
                request=mock_request,
                action="oauth2_authorize_client_123",
                rate_limit_requests=10,
                rate_limit_period=60
            )


class TestClientRequestSecurity:
    """Test comprehensive client request security validation."""
    
    @pytest.mark.asyncio
    async def test_validate_client_request_security_success(self, security_manager, mock_request, sample_client):
        """Test successful client request security validation."""
        with patch.object(security_manager.client_manager, 'get_client', return_value=sample_client), \
             patch.object(security_manager, 'validate_redirect_uri', return_value=True):
            
            await security_manager.validate_client_request_security(
                mock_request,
                "test_client_123",
                redirect_uri="https://example.com/callback",
                state="valid_state_123"
            )
            # Should not raise any exception
    
    @pytest.mark.asyncio
    async def test_validate_client_request_security_invalid_client(self, security_manager, mock_request):
        """Test client request security validation with invalid client."""
        with patch.object(security_manager.client_manager, 'get_client', return_value=None):
            
            with pytest.raises(HTTPException) as exc_info:
                await security_manager.validate_client_request_security(
                    mock_request,
                    "invalid_client"
                )
            
            assert exc_info.value.status_code == 400
            assert "Invalid client_id" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validate_client_request_security_inactive_client(self, security_manager, mock_request, sample_client):
        """Test client request security validation with inactive client."""
        sample_client.is_active = False
        
        with patch.object(security_manager.client_manager, 'get_client', return_value=sample_client):
            
            with pytest.raises(HTTPException) as exc_info:
                await security_manager.validate_client_request_security(
                    mock_request,
                    "test_client_123"
                )
            
            assert exc_info.value.status_code == 400
            assert "Client is inactive" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validate_client_request_security_invalid_redirect_uri(self, security_manager, mock_request, sample_client):
        """Test client request security validation with invalid redirect URI."""
        with patch.object(security_manager.client_manager, 'get_client', return_value=sample_client), \
             patch.object(security_manager, 'validate_redirect_uri', return_value=False):
            
            with pytest.raises(HTTPException) as exc_info:
                await security_manager.validate_client_request_security(
                    mock_request,
                    "test_client_123",
                    redirect_uri="https://malicious.com/callback"
                )
            
            assert exc_info.value.status_code == 400
            assert "Invalid redirect_uri" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_validate_client_request_security_invalid_state_format(self, security_manager, mock_request, sample_client):
        """Test client request security validation with invalid state format."""
        with patch.object(security_manager.client_manager, 'get_client', return_value=sample_client):
            
            with pytest.raises(HTTPException) as exc_info:
                await security_manager.validate_client_request_security(
                    mock_request,
                    "test_client_123",
                    state="<script>alert('xss')</script>"
                )
            
            assert exc_info.value.status_code == 400
            assert "Invalid state parameter format" in str(exc_info.value.detail)


class TestSecurityValidationHelpers:
    """Test security validation helper methods."""
    
    def test_is_valid_uri_format_valid_uris(self, security_manager):
        """Test URI format validation with valid URIs."""
        valid_uris = [
            "https://example.com/callback",
            "http://localhost:3000/callback",
            "https://app.example.com/oauth/callback?param=value"
        ]
        
        for uri in valid_uris:
            assert security_manager._is_valid_uri_format(uri) is True
    
    def test_is_valid_uri_format_invalid_uris(self, security_manager):
        """Test URI format validation with invalid URIs."""
        invalid_uris = [
            "not-a-uri",
            "://missing-scheme",
            "https://",
            ""
        ]
        
        for uri in invalid_uris:
            assert security_manager._is_valid_uri_format(uri) is False
    
    def test_is_secure_redirect_uri_secure_uris(self, security_manager):
        """Test secure redirect URI validation with secure URIs."""
        secure_uris = [
            "https://example.com/callback",
            "http://localhost:3000/callback",
            "http://127.0.0.1:8080/callback"
        ]
        
        for uri in secure_uris:
            assert security_manager._is_secure_redirect_uri(uri) is True
    
    def test_is_secure_redirect_uri_insecure_uris(self, security_manager):
        """Test secure redirect URI validation with insecure URIs."""
        insecure_uris = [
            "http://example.com/callback",  # HTTP not allowed for non-localhost
            "javascript:alert('xss')",
            "data:text/html,<script>alert('xss')</script>",
            "vbscript:msgbox('xss')",
            "https://example.com/callback<script>alert('xss')</script>"
        ]
        
        for uri in insecure_uris:
            assert security_manager._is_secure_redirect_uri(uri) is False
    
    def test_is_valid_state_format_valid_states(self, security_manager):
        """Test state format validation with valid states."""
        valid_states = [
            "abc123def456",
            "state-with-hyphens",
            "state_with_underscores",
            "state.with.dots",
            "a" * 32,  # 32 characters
            "a" * 128  # 128 characters (max)
        ]
        
        for state in valid_states:
            assert security_manager._is_valid_state_format(state) is True
    
    def test_is_valid_state_format_invalid_states(self, security_manager):
        """Test state format validation with invalid states."""
        invalid_states = [
            "",  # Empty
            "short",  # Too short (< 8 chars)
            "a" * 129,  # Too long (> 128 chars)
            "state with spaces",  # Contains spaces
            "state@with#special!chars",  # Contains special chars
            "state<script>alert('xss')</script>"  # Contains dangerous chars
        ]
        
        for state in invalid_states:
            assert security_manager._is_valid_state_format(state) is False


class TestPKCESecurity:
    """Test PKCE security validation."""
    
    @pytest.mark.asyncio
    async def test_validate_pkce_security_valid_s256(self, security_manager):
        """Test PKCE validation with valid S256 parameters."""
        result = await security_manager.validate_pkce_security(
            "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            "S256"
        )
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_pkce_security_valid_plain(self, security_manager):
        """Test PKCE validation with valid plain parameters."""
        result = await security_manager.validate_pkce_security(
            "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            "plain"
        )
        assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_pkce_security_invalid_method(self, security_manager):
        """Test PKCE validation with invalid method."""
        result = await security_manager.validate_pkce_security(
            "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            "invalid_method"
        )
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_pkce_security_invalid_challenge_length(self, security_manager):
        """Test PKCE validation with invalid challenge length."""
        # Too short
        result = await security_manager.validate_pkce_security("short", "S256")
        assert result is False
        
        # Too long
        result = await security_manager.validate_pkce_security("a" * 129, "S256")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_pkce_security_invalid_s256_format(self, security_manager):
        """Test PKCE validation with invalid S256 format."""
        result = await security_manager.validate_pkce_security(
            "invalid@challenge#with$special%chars",
            "S256"
        )
        assert result is False


class TestSecurityLogging:
    """Test OAuth2 security event logging."""
    
    @pytest.mark.asyncio
    async def test_log_oauth2_security_event(self, security_manager):
        """Test OAuth2 security event logging."""
        with patch('second_brain_database.routes.oauth2.security_manager.logger') as mock_logger:
            await security_manager.log_oauth2_security_event(
                "authorization_attempt",
                "client_123",
                user_id="user_456",
                details={"ip": "127.0.0.1", "user_agent": "test"}
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            assert "OAuth2 security event: authorization_attempt" in call_args[0][0]
            assert call_args[1]['extra']['client_id'] == "client_123"
            assert call_args[1]['extra']['user_id'] == "user_456"


class TestGlobalInstance:
    """Test global OAuth2SecurityManager instance."""
    
    def test_global_instance_exists(self):
        """Test that global oauth2_security_manager instance exists."""
        assert oauth2_security_manager is not None
        assert isinstance(oauth2_security_manager, OAuth2SecurityManager)
    
    def test_global_instance_initialization(self):
        """Test that global instance is properly initialized."""
        assert hasattr(oauth2_security_manager, 'redis_manager')
        assert hasattr(oauth2_security_manager, 'security_manager')
        assert hasattr(oauth2_security_manager, 'client_manager')