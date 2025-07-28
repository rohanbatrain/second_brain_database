"""
Unit tests for OAuth2 Authorization Code Manager.

Tests authorization code generation, storage, retrieval, validation, and cleanup.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from src.second_brain_database.routes.oauth2.services.auth_code_manager import (
    AuthorizationCodeManager,
    auth_code_manager,
    OAUTH2_AUTH_CODE_PREFIX,
    OAUTH2_AUTH_CODE_USAGE_PREFIX,
    DEFAULT_AUTH_CODE_TTL
)
from src.second_brain_database.routes.oauth2.models import AuthorizationCode, PKCEMethod


class TestAuthorizationCodeManager:
    """Test suite for AuthorizationCodeManager."""
    
    @pytest.fixture
    def manager(self):
        """Create a fresh AuthorizationCodeManager instance."""
        return AuthorizationCodeManager()
    
    @pytest.fixture
    def sample_auth_code_data(self):
        """Sample authorization code data for testing."""
        return {
            "client_id": "test_client_123",
            "user_id": "user_456",
            "redirect_uri": "https://example.com/callback",
            "scopes": ["read:profile", "write:data"],
            "code_challenge": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            "code_challenge_method": PKCEMethod.S256
        }
    
    def test_generate_authorization_code(self, manager):
        """Test authorization code generation."""
        code1 = manager.generate_authorization_code()
        code2 = manager.generate_authorization_code()
        
        # Codes should be different
        assert code1 != code2
        
        # Codes should have correct format
        assert code1.startswith("auth_code_")
        assert code2.startswith("auth_code_")
        
        # Codes should be 32 characters after prefix (not 64)
        code_part = code1[10:]  # Remove "auth_code_" prefix
        assert len(code_part) == 32  # 32 random characters
        
        # Should contain only alphanumeric characters
        assert code_part.isalnum()
    
    @pytest.mark.asyncio
    async def test_store_authorization_code_success(self, manager, sample_auth_code_data):
        """Test successful authorization code storage."""
        test_code = "auth_code_test123456789012345678901234"
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.setex = AsyncMock(return_value=True)
            
            result = await manager.store_authorization_code(
                code=test_code,
                **sample_auth_code_data
            )
            
            assert result is True
            
            # Should have called Redis setex twice (code + usage tracking)
            assert mock_redis_manager.setex.call_count == 2
            
            # Check first call (authorization code storage)
            first_call = mock_redis_manager.setex.call_args_list[0]
            assert first_call[0][0] == f"{OAUTH2_AUTH_CODE_PREFIX}{test_code}"
            assert first_call[0][1] == DEFAULT_AUTH_CODE_TTL
            
            # Check second call (usage tracking)
            second_call = mock_redis_manager.setex.call_args_list[1]
            assert second_call[0][0] == f"{OAUTH2_AUTH_CODE_USAGE_PREFIX}{test_code}"
            assert second_call[0][2] == "0"
    
    @pytest.mark.asyncio
    async def test_store_authorization_code_custom_ttl(self, manager, sample_auth_code_data):
        """Test authorization code storage with custom TTL."""
        test_code = "auth_code_test123456789012345678901234"
        custom_ttl = 300
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.setex = AsyncMock(return_value=True)
            
            result = await manager.store_authorization_code(
                code=test_code,
                ttl_seconds=custom_ttl,
                **sample_auth_code_data
            )
            
            assert result is True
            
            # Should use custom TTL
            first_call = mock_redis_manager.setex.call_args_list[0]
            assert first_call[0][1] == custom_ttl
    
    @pytest.mark.asyncio
    async def test_store_authorization_code_redis_failure(self, manager, sample_auth_code_data):
        """Test authorization code storage when Redis fails."""
        test_code = "auth_code_test123456789012345678901234"
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.setex = AsyncMock(return_value=False)
            
            result = await manager.store_authorization_code(
                code=test_code,
                **sample_auth_code_data
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_authorization_code_success(self, manager):
        """Test successful authorization code retrieval."""
        test_code = "auth_code_test123"
        auth_code_data = AuthorizationCode(
            code=test_code,
            client_id="test_client",
            user_id="test_user",
            redirect_uri="https://example.com/callback",
            scopes=["read:profile"],
            code_challenge="test_challenge",
            code_challenge_method=PKCEMethod.S256,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            used=False
        )
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.get = AsyncMock(return_value=auth_code_data.model_dump_json())
            
            result = await manager.get_authorization_code(test_code)
            
            assert result is not None
            assert result.code == test_code
            assert result.client_id == "test_client"
            assert not result.used
            
            # Should have called Redis get with correct key
            mock_redis_manager.get.assert_called_once_with(f"{OAUTH2_AUTH_CODE_PREFIX}{test_code}")
    
    @pytest.mark.asyncio
    async def test_get_authorization_code_not_found(self, manager):
        """Test authorization code retrieval when code doesn't exist."""
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.get = AsyncMock(return_value=None)
            
            result = await manager.get_authorization_code("nonexistent_code")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_authorization_code_expired(self, manager):
        """Test authorization code retrieval when code has expired."""
        test_code = "auth_code_expired"
        expired_auth_code = AuthorizationCode(
            code=test_code,
            client_id="test_client",
            user_id="test_user",
            redirect_uri="https://example.com/callback",
            scopes=["read:profile"],
            code_challenge="test_challenge",
            code_challenge_method=PKCEMethod.S256,
            expires_at=datetime.utcnow() - timedelta(minutes=1),  # Expired
            used=False
        )
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.get = AsyncMock(return_value=expired_auth_code.model_dump_json())
            mock_redis_manager.delete = AsyncMock(return_value=1)
            
            result = await manager.get_authorization_code(test_code)
            
            assert result is None
            # Should have cleaned up expired code
            assert mock_redis_manager.delete.call_count == 2  # Code and usage tracking
    
    @pytest.mark.asyncio
    async def test_get_authorization_code_already_used(self, manager):
        """Test authorization code retrieval when code has been used."""
        test_code = "auth_code_used"
        used_auth_code = AuthorizationCode(
            code=test_code,
            client_id="test_client",
            user_id="test_user",
            redirect_uri="https://example.com/callback",
            scopes=["read:profile"],
            code_challenge="test_challenge",
            code_challenge_method=PKCEMethod.S256,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            used=True  # Already used
        )
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.get = AsyncMock(return_value=used_auth_code.model_dump_json())
            
            result = await manager.get_authorization_code(test_code)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_use_authorization_code_success(self, manager):
        """Test successful authorization code usage."""
        test_code = "auth_code_valid"
        
        auth_code_data = AuthorizationCode(
            code=test_code,
            client_id="test_client",
            user_id="test_user",
            redirect_uri="https://example.com/callback",
            scopes=["read:profile"],
            code_challenge="test_challenge",
            code_challenge_method=PKCEMethod.S256,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            used=False
        )
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            # Mock the get_authorization_code flow
            mock_redis_manager.get = AsyncMock(return_value=auth_code_data.model_dump_json())
            
            # Mock usage tracking
            mock_redis_manager.get = AsyncMock(side_effect=[
                auth_code_data.model_dump_json(),  # First call for get_authorization_code
                "0"  # Second call for usage count
            ])
            
            # Mock Redis connection for incr
            mock_redis_conn = AsyncMock()
            mock_redis_conn.incr = AsyncMock(return_value=1)
            mock_redis_manager.get_redis = AsyncMock(return_value=mock_redis_conn)
            
            # Mock cleanup
            mock_redis_manager.delete = AsyncMock(return_value=1)
            
            result = await manager.use_authorization_code(test_code)
            
            assert result is not None
            assert result.code == test_code
            assert result.client_id == "test_client"
            assert result.used == True
    
    @pytest.mark.asyncio
    async def test_use_authorization_code_replay_attack(self, manager):
        """Test authorization code usage with replay attack detection."""
        test_code = "auth_code_replay"
        
        auth_code_data = AuthorizationCode(
            code=test_code,
            client_id="test_client",
            user_id="test_user",
            redirect_uri="https://example.com/callback",
            scopes=["read:profile"],
            code_challenge="test_challenge",
            code_challenge_method=PKCEMethod.S256,
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            used=False
        )
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            # Mock the get_authorization_code flow first, then usage count > 0 (already used)
            mock_redis_manager.get = AsyncMock(side_effect=[
                auth_code_data.model_dump_json(),  # First call for get_authorization_code
                "1"  # Second call for usage count (already used)
            ])
            mock_redis_manager.delete = AsyncMock(return_value=1)
            
            result = await manager.use_authorization_code(test_code)
            
            assert result is None
            # Should have cleaned up the code
            assert mock_redis_manager.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_revoke_authorization_code(self, manager):
        """Test authorization code revocation."""
        test_code = "auth_code_to_revoke"
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.delete = AsyncMock(return_value=1)
            
            result = await manager.revoke_authorization_code(test_code)
            
            assert result is True
            # Should delete both code and usage tracking
            assert mock_redis_manager.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_revoke_authorization_code_not_found(self, manager):
        """Test authorization code revocation when code doesn't exist."""
        test_code = "nonexistent_code"
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.delete = AsyncMock(return_value=0)  # No keys deleted
            
            result = await manager.revoke_authorization_code(test_code)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_codes(self, manager):
        """Test cleanup of expired authorization codes."""
        expired_code = AuthorizationCode(
            code="expired_code",
            client_id="test_client",
            user_id="test_user",
            redirect_uri="https://example.com/callback",
            scopes=["read:profile"],
            code_challenge="test_challenge",
            code_challenge_method=PKCEMethod.S256,
            expires_at=datetime.utcnow() - timedelta(minutes=1),  # Expired
            used=False
        )
        
        valid_code = AuthorizationCode(
            code="valid_code",
            client_id="test_client",
            user_id="test_user",
            redirect_uri="https://example.com/callback",
            scopes=["read:profile"],
            code_challenge="test_challenge",
            code_challenge_method=PKCEMethod.S256,
            expires_at=datetime.utcnow() + timedelta(minutes=10),  # Valid
            used=False
        )
        
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            # Mock keys method
            mock_redis_manager.keys = AsyncMock(return_value=[
                f"{OAUTH2_AUTH_CODE_PREFIX}expired_code",
                f"{OAUTH2_AUTH_CODE_PREFIX}valid_code",
                f"{OAUTH2_AUTH_CODE_PREFIX}invalid_data"
            ])
            
            # Mock get responses
            mock_redis_manager.get = AsyncMock(side_effect=[
                expired_code.model_dump_json(),  # Expired code
                valid_code.model_dump_json(),    # Valid code
                "invalid_json_data"              # Invalid data
            ])
            
            mock_redis_manager.delete = AsyncMock(return_value=1)
            
            cleaned_count = await manager.cleanup_expired_codes()
            
            # Should clean up expired code and invalid data
            assert cleaned_count == 2
    
    @pytest.mark.asyncio
    async def test_get_code_statistics(self, manager):
        """Test getting authorization code statistics."""
        with patch('src.second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis_manager:
            # Mock keys method
            mock_redis_manager.keys = AsyncMock(return_value=[
                f"{OAUTH2_AUTH_CODE_PREFIX}code1",
                f"{OAUTH2_AUTH_CODE_PREFIX}code2"
            ])
            
            # Mock get responses
            expired_code = AuthorizationCode(
                code="code1",
                client_id="test_client",
                user_id="test_user",
                redirect_uri="https://example.com/callback",
                scopes=["read:profile"],
                code_challenge="test_challenge",
                code_challenge_method=PKCEMethod.S256,
                expires_at=datetime.utcnow() - timedelta(minutes=1),  # Expired
                used=False
            )
            
            active_code = AuthorizationCode(
                code="code2",
                client_id="test_client",
                user_id="test_user",
                redirect_uri="https://example.com/callback",
                scopes=["read:profile"],
                code_challenge="test_challenge",
                code_challenge_method=PKCEMethod.S256,
                expires_at=datetime.utcnow() + timedelta(minutes=10),  # Active
                used=False
            )
            
            mock_redis_manager.get = AsyncMock(side_effect=[
                expired_code.model_dump_json(),
                active_code.model_dump_json()
            ])
            
            stats = await manager.get_code_statistics()
            
            assert stats["total_codes"] == 2
            assert stats["expired_codes"] == 1
            assert stats["used_codes"] == 0
            assert stats["active_codes"] == 1
    
    def test_global_instance_exists(self):
        """Test that global auth_code_manager instance exists."""
        assert auth_code_manager is not None
        assert isinstance(auth_code_manager, AuthorizationCodeManager)


if __name__ == "__main__":
    pytest.main([__file__])