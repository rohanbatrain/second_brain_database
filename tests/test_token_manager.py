"""
Unit tests for OAuth2 Token Manager.

Tests the token lifecycle management including refresh token validation,
rotation, revocation, and cleanup functionality.
"""

import hashlib
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.second_brain_database.routes.oauth2.services.token_manager import TokenManager, token_manager
from src.second_brain_database.routes.oauth2.models import RefreshTokenData, TokenResponse, TokenType


# Patch path for redis_manager in token_manager module
REDIS_MANAGER_PATCH = 'src.second_brain_database.routes.oauth2.services.token_manager.redis_manager'


class TestTokenManager:
    """Test cases for TokenManager class."""
    
    @pytest.fixture
    def token_mgr(self):
        """Create a TokenManager instance for testing."""
        return TokenManager()
    
    def setup_redis_mock(self, mock_redis, **kwargs):
        """Helper to set up redis mock with async methods."""
        mock_redis.get = AsyncMock(return_value=kwargs.get('get_return', None))
        mock_redis.setex = AsyncMock(return_value=kwargs.get('setex_return', True))
        mock_redis.delete = AsyncMock(return_value=kwargs.get('delete_return', 1))
        mock_redis.keys = AsyncMock(return_value=kwargs.get('keys_return', []))
        
        # Handle side_effect for get method
        if 'get_side_effect' in kwargs:
            mock_redis.get.side_effect = kwargs['get_side_effect']
            
        return mock_redis
    
    @pytest.fixture
    def sample_refresh_data(self):
        """Sample refresh token data for testing."""
        return RefreshTokenData(
            token_hash="test_hash",
            client_id="test_client",
            user_id="test_user",
            scopes=["read:profile", "write:data"],
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            created_at=datetime.now(timezone.utc),
            is_active=True
        )
    
    @pytest.mark.asyncio
    async def test_generate_refresh_token_success(self, token_mgr):
        """Test successful refresh token generation."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, setex_return=True)
            
            token = await token_mgr.generate_refresh_token(
                client_id="test_client",
                user_id="test_user",
                scopes=["read:profile"]
            )
            
            assert token is not None
            assert token.startswith("rt_")
            assert len(token) == 35  # "rt_" + 32 characters
            mock_redis.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_refresh_token_redis_failure(self, token_mgr):
        """Test refresh token generation when Redis fails."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, setex_return=False)
            
            token = await token_mgr.generate_refresh_token(
                client_id="test_client",
                user_id="test_user",
                scopes=["read:profile"]
            )
            
            assert token is None
    
    @pytest.mark.asyncio
    async def test_validate_refresh_token_success(self, token_mgr, sample_refresh_data):
        """Test successful refresh token validation."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=sample_refresh_data.model_dump_json())
            
            result = await token_mgr.validate_refresh_token("rt_test_token", "test_client")
            
            assert result is not None
            assert result.client_id == "test_client"
            assert result.user_id == "test_user"
            assert result.scopes == ["read:profile", "write:data"]
            assert result.is_active is True
    
    @pytest.mark.asyncio
    async def test_validate_refresh_token_not_found(self, token_mgr):
        """Test refresh token validation when token not found."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=None)
            
            result = await token_mgr.validate_refresh_token("rt_test_token", "test_client")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_refresh_token_client_mismatch(self, token_mgr, sample_refresh_data):
        """Test refresh token validation with client mismatch."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=sample_refresh_data.model_dump_json())
            
            result = await token_mgr.validate_refresh_token("rt_test_token", "wrong_client")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_refresh_token_inactive(self, token_mgr, sample_refresh_data):
        """Test refresh token validation when token is inactive."""
        sample_refresh_data.is_active = False
        
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=sample_refresh_data.model_dump_json())
            
            result = await token_mgr.validate_refresh_token("rt_test_token", "test_client")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_refresh_token_expired(self, token_mgr, sample_refresh_data):
        """Test refresh token validation when token is expired."""
        sample_refresh_data.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=sample_refresh_data.model_dump_json())
            
            result = await token_mgr.validate_refresh_token("rt_test_token", "test_client")
            
            assert result is None
            # Should also cleanup expired token
            mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_rotate_refresh_token_success(self, token_mgr, sample_refresh_data):
        """Test successful refresh token rotation."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(
                mock_redis, 
                get_return=sample_refresh_data.model_dump_json(),
                delete_return=1,
                setex_return=True
            )
            
            new_token = await token_mgr.rotate_refresh_token(
                old_refresh_token="rt_old_token",
                client_id="test_client",
                user_id="test_user",
                scopes=["read:profile"]
            )
            
            assert new_token is not None
            assert new_token.startswith("rt_")
            assert new_token != "rt_old_token"
            
            # Should delete old token and create new one
            assert mock_redis.delete.call_count == 1
            assert mock_redis.setex.call_count == 1
    
    @pytest.mark.asyncio
    async def test_rotate_refresh_token_invalid_old_token(self, token_mgr):
        """Test refresh token rotation with invalid old token."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=None)
            
            new_token = await token_mgr.rotate_refresh_token(
                old_refresh_token="rt_invalid_token",
                client_id="test_client",
                user_id="test_user",
                scopes=["read:profile"]
            )
            
            assert new_token is None
    
    @pytest.mark.asyncio
    async def test_revoke_refresh_token_success(self, token_mgr):
        """Test successful refresh token revocation."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, delete_return=1)
            
            result = await token_mgr.revoke_refresh_token("rt_test_token")
            
            assert result is True
            mock_redis.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_revoke_refresh_token_not_found(self, token_mgr):
        """Test refresh token revocation when token not found."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, delete_return=0)
            
            result = await token_mgr.revoke_refresh_token("rt_test_token")
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, token_mgr, sample_refresh_data):
        """Test revoking all tokens for a user."""
        # Create multiple token data for different clients
        token_data_1 = sample_refresh_data.model_copy()
        token_data_1.client_id = "client_1"
        
        token_data_2 = sample_refresh_data.model_copy()
        token_data_2.client_id = "client_2"
        
        token_data_3 = sample_refresh_data.model_copy()
        token_data_3.user_id = "other_user"  # Different user
        
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(
                mock_redis,
                keys_return=[
                    "oauth2:refresh_token:hash1",
                    "oauth2:refresh_token:hash2",
                    "oauth2:refresh_token:hash3"
                ],
                get_side_effect=[
                    token_data_1.model_dump_json(),
                    token_data_2.model_dump_json(),
                    token_data_3.model_dump_json()
                ],
                delete_return=1
            )
            
            revoked_count = await token_mgr.revoke_all_user_tokens("test_user")
            
            # Should revoke 2 tokens (client_1 and client_2) but not the other user's token
            assert revoked_count == 2
            assert mock_redis.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens_with_client_filter(self, token_mgr, sample_refresh_data):
        """Test revoking all tokens for a user filtered by client."""
        token_data_1 = sample_refresh_data.model_copy()
        token_data_1.client_id = "target_client"
        
        token_data_2 = sample_refresh_data.model_copy()
        token_data_2.client_id = "other_client"
        
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(
                mock_redis,
                keys_return=[
                    "oauth2:refresh_token:hash1",
                    "oauth2:refresh_token:hash2"
                ],
                get_side_effect=[
                    token_data_1.model_dump_json(),
                    token_data_2.model_dump_json()
                ],
                delete_return=1
            )
            
            revoked_count = await token_mgr.revoke_all_user_tokens("test_user", "target_client")
            
            # Should only revoke 1 token (target_client)
            assert revoked_count == 1
            assert mock_redis.delete.call_count == 1
    
    @pytest.mark.asyncio
    async def test_revoke_all_client_tokens(self, token_mgr, sample_refresh_data):
        """Test revoking all tokens for a client."""
        token_data_1 = sample_refresh_data.model_copy()
        token_data_1.user_id = "user_1"
        
        token_data_2 = sample_refresh_data.model_copy()
        token_data_2.user_id = "user_2"
        
        token_data_3 = sample_refresh_data.model_copy()
        token_data_3.client_id = "other_client"
        
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(
                mock_redis,
                keys_return=[
                    "oauth2:refresh_token:hash1",
                    "oauth2:refresh_token:hash2",
                    "oauth2:refresh_token:hash3"
                ],
                get_side_effect=[
                    token_data_1.model_dump_json(),
                    token_data_2.model_dump_json(),
                    token_data_3.model_dump_json()
                ],
                delete_return=1
            )
            
            revoked_count = await token_mgr.revoke_all_client_tokens("test_client")
            
            # Should revoke 2 tokens (user_1 and user_2) but not the other client's token
            assert revoked_count == 2
            assert mock_redis.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self, token_mgr, sample_refresh_data):
        """Test cleanup of expired tokens."""
        # Create expired and active tokens
        expired_token = sample_refresh_data.model_copy()
        expired_token.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        
        active_token = sample_refresh_data.model_copy()
        active_token.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(
                mock_redis,
                keys_return=[
                    "oauth2:refresh_token:expired_hash",
                    "oauth2:refresh_token:active_hash"
                ],
                get_side_effect=[
                    expired_token.model_dump_json(),
                    active_token.model_dump_json()
                ],
                delete_return=1
            )
            
            cleaned_count = await token_mgr.cleanup_expired_tokens()
            
            # Should only clean up 1 expired token
            assert cleaned_count == 1
            assert mock_redis.delete.call_count == 1
    
    @pytest.mark.asyncio
    async def test_get_token_info(self, token_mgr, sample_refresh_data):
        """Test getting token information."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=sample_refresh_data.model_dump_json())
            
            info = await token_mgr.get_token_info("rt_test_token")
            
            assert info is not None
            assert info["client_id"] == "test_client"
            assert info["user_id"] == "test_user"
            assert info["scopes"] == ["read:profile", "write:data"]
            assert info["is_active"] is True
    
    @pytest.mark.asyncio
    async def test_get_token_info_not_found(self, token_mgr):
        """Test getting token information when token not found."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=None)
            
            info = await token_mgr.get_token_info("rt_test_token")
            
            assert info is None
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, token_mgr, sample_refresh_data):
        """Test successful access token refresh."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(
                mock_redis,
                get_return=sample_refresh_data.model_dump_json(),
                delete_return=1,
                setex_return=True
            )
            
            with patch('src.second_brain_database.routes.oauth2.services.token_manager.create_access_token', new_callable=AsyncMock) as mock_create_token:
                mock_create_token.return_value = "new_access_token"
                
                response = await token_mgr.refresh_access_token("rt_test_token", "test_client")
                
                assert response is not None
                assert isinstance(response, TokenResponse)
                assert response.access_token == "new_access_token"
                assert response.token_type == TokenType.BEARER
                assert response.refresh_token.startswith("rt_")
                assert response.scope == "read:profile write:data"
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_invalid_token(self, token_mgr):
        """Test access token refresh with invalid refresh token."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(mock_redis, get_return=None)
            
            response = await token_mgr.refresh_access_token("rt_invalid_token", "test_client")
            
            assert response is None
    
    @pytest.mark.asyncio
    async def test_get_token_statistics(self, token_mgr, sample_refresh_data):
        """Test getting token statistics."""
        # Create expired and active tokens for different clients/users
        expired_token = sample_refresh_data.model_copy()
        expired_token.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        expired_token.client_id = "client_1"
        expired_token.user_id = "user_1"
        
        active_token_1 = sample_refresh_data.model_copy()
        active_token_1.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        active_token_1.client_id = "client_1"
        active_token_1.user_id = "user_1"
        
        active_token_2 = sample_refresh_data.model_copy()
        active_token_2.expires_at = datetime.now(timezone.utc) + timedelta(days=1)
        active_token_2.client_id = "client_2"
        active_token_2.user_id = "user_2"
        
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            self.setup_redis_mock(
                mock_redis,
                keys_return=[
                    "oauth2:refresh_token:hash1",
                    "oauth2:refresh_token:hash2",
                    "oauth2:refresh_token:hash3"
                ],
                get_side_effect=[
                    expired_token.model_dump_json(),
                    active_token_1.model_dump_json(),
                    active_token_2.model_dump_json()
                ]
            )
            
            stats = await token_mgr.get_token_statistics()
            
            assert stats["total_tokens"] == 3
            assert stats["active_tokens"] == 2
            assert stats["expired_tokens"] == 1
            assert stats["unique_clients"] == 2
            assert stats["unique_users"] == 2
    
    @pytest.mark.asyncio
    async def test_get_token_statistics_error(self, token_mgr):
        """Test getting token statistics when Redis fails."""
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            mock_redis.keys = AsyncMock(side_effect=Exception("Redis error"))
            
            stats = await token_mgr.get_token_statistics()
            
            assert stats["total_tokens"] == 0
            assert stats["active_tokens"] == 0
            assert stats["expired_tokens"] == 0
            assert stats["unique_clients"] == 0
            assert stats["unique_users"] == 0
            assert "error" in stats


class TestTokenManagerIntegration:
    """Integration tests for token manager with other components."""
    
    @pytest.mark.asyncio
    async def test_token_lifecycle_integration(self):
        """Test complete token lifecycle: generate -> validate -> rotate -> revoke."""
        token_mgr = TokenManager()
        
        with patch(REDIS_MANAGER_PATCH) as mock_redis:
            sample_data = RefreshTokenData(
                token_hash="test_hash",
                client_id="test_client",
                user_id="test_user",
                scopes=["read:profile"],
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
                created_at=datetime.now(timezone.utc),
                is_active=True
            )
            
            # Use the helper method to set up mocks properly
            TestTokenManager().setup_redis_mock(
                mock_redis,
                setex_return=True,
                get_return=sample_data.model_dump_json(),
                delete_return=1
            )
            
            # 1. Generate token
            token = await token_mgr.generate_refresh_token("test_client", "test_user", ["read:profile"])
            assert token is not None
            
            # 2. Validate token
            token_data = await token_mgr.validate_refresh_token(token, "test_client")
            assert token_data is not None
            
            # 3. Rotate token
            new_token = await token_mgr.rotate_refresh_token(token, "test_client", "test_user", ["read:profile"])
            assert new_token is not None
            assert new_token != token
            
            # 4. Revoke token
            revoked = await token_mgr.revoke_refresh_token(new_token)
            assert revoked is True


# Test the global instance
def test_global_token_manager_instance():
    """Test that the global token manager instance is properly initialized."""
    assert token_manager is not None
    assert isinstance(token_manager, TokenManager)
    assert token_manager.refresh_token_ttl == 30 * 24 * 60 * 60  # 30 days
