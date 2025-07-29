"""
Unit tests for OAuth2 authorization code management.

Tests cover authorization code generation, storage, retrieval, usage tracking,
expiration handling, and cleanup mechanisms.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from second_brain_database.routes.oauth2.models import AuthorizationCode, PKCEMethod
from second_brain_database.routes.oauth2.services.auth_code_manager import (
    AuthorizationCodeManager,
    DEFAULT_AUTH_CODE_TTL,
    OAUTH2_AUTH_CODE_PREFIX,
    OAUTH2_AUTH_CODE_USAGE_PREFIX,
)


class TestAuthorizationCodeManager:
    """Test suite for AuthorizationCodeManager."""
    
    @pytest.fixture
    def auth_code_manager(self):
        """Create AuthorizationCodeManager instance for testing."""
        return AuthorizationCodeManager()
    
    @pytest.fixture
    def sample_auth_code_data(self):
        """Sample authorization code data for testing."""
        return {
            "client_id": "oauth2_client_test123",
            "user_id": "user_test456",
            "redirect_uri": "https://example.com/callback",
            "scopes": ["read:profile", "write:data"],
            "code_challenge": "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk",
            "code_challenge_method": PKCEMethod.S256,
        }
    
    def test_generate_authorization_code(self, auth_code_manager):
        """Test secure authorization code generation."""
        # Generate multiple codes to test uniqueness
        codes = [auth_code_manager.generate_authorization_code() for _ in range(10)]
        
        # Check format
        for code in codes:
            assert code.startswith("auth_code_")
            assert len(code) == len("auth_code_") + 32
            # Check only alphanumeric characters after prefix
            assert code[10:].isalnum()
        
        # Check uniqueness
        assert len(set(codes)) == len(codes)
    
    @pytest.mark.asyncio
    async def test_store_authorization_code_success(self, auth_code_manager, sample_auth_code_data):
        """Test successful authorization code storage."""
        code = "auth_code_test123456789012345678901234"
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            mock_redis.setex = AsyncMock(return_value=True)
            
            result = await auth_code_manager.store_authorization_code(
                code=code,
                ttl_seconds=600,
                **sample_auth_code_data
            )
            
            assert result is True
            
            # Verify Redis calls
            assert mock_redis.setex.call_count == 2  # Code data + usage tracking
            
            # Check code storage call
            code_call = mock_redis.setex.call_args_list[0]
            assert code_call[0][0] == f"{OAUTH2_AUTH_CODE_PREFIX}{code}"
            assert code_call[0][1] == 600
            
            # Check usage tracking call
            usage_call = mock_redis.setex.call_args_list[1]
            assert usage_call[0][0] == f"{OAUTH2_AUTH_CODE_USAGE_PREFIX}{code}"
            assert usage_call[0][1] == 600
            assert usage_call[0][2] == "0"
    
    @pytest.mark.asyncio
    async def test_store_authorization_code_failure(self, auth_code_manager, sample_auth_code_data):
        """Test authorization code storage failure."""
        code = "auth_code_test123456789012345678901234"
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            mock_redis.setex = AsyncMock(return_value=False)
            
            result = await auth_code_manager.store_authorization_code(
                code=code,
                **sample_auth_code_data
            )
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_authorization_code_success(self, auth_code_manager, sample_auth_code_data):
        """Test successful authorization code retrieval."""
        code = "auth_code_test123456789012345678901234"
        
        # Create mock authorization code data
        auth_code_data = AuthorizationCode(
            code=code,
            expires_at=datetime.utcnow() + timedelta(seconds=300),  # Valid for 5 minutes
            used=False,
            **sample_auth_code_data
        )
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            mock_redis.get = AsyncMock(return_value=auth_code_data.model_dump_json())
            
            result = await auth_code_manager.get_authorization_code(code)
            
            assert result is not None
            assert result.code == code
            assert result.client_id == sample_auth_code_data["client_id"]
            assert result.used is False
            
            # Verify Redis call
            mock_redis.get.assert_called_once_with(f"{OAUTH2_AUTH_CODE_PREFIX}{code}")
    
    @pytest.mark.asyncio
    async def test_get_authorization_code_not_found(self, auth_code_manager):
        """Test authorization code retrieval when code doesn't exist."""
        code = "auth_code_nonexistent"
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            
            result = await auth_code_manager.get_authorization_code(code)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_authorization_code_expired(self, auth_code_manager, sample_auth_code_data):
        """Test authorization code retrieval when code is expired."""
        code = "auth_code_expired"
        
        # Create expired authorization code
        auth_code_data = AuthorizationCode(
            code=code,
            expires_at=datetime.utcnow() - timedelta(seconds=60),  # Expired 1 minute ago
            used=False,
            **sample_auth_code_data
        )
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            mock_redis.get = AsyncMock(return_value=auth_code_data.model_dump_json())
            mock_redis.delete = AsyncMock(return_value=1)
            
            result = await auth_code_manager.get_authorization_code(code)
            
            assert result is None
            # Verify cleanup was called
            assert mock_redis.delete.call_count == 2  # Code + usage tracking
    
    @pytest.mark.asyncio
    async def test_get_authorization_code_already_used(self, auth_code_manager, sample_auth_code_data):
        """Test authorization code retrieval when code is already used."""
        code = "auth_code_used"
        
        # Create used authorization code
        auth_code_data = AuthorizationCode(
            code=code,
            expires_at=datetime.utcnow() + timedelta(seconds=300),
            used=True,  # Already used
            **sample_auth_code_data
        )
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            mock_redis.get = AsyncMock(return_value=auth_code_data.model_dump_json())
            
            result = await auth_code_manager.get_authorization_code(code)
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_use_authorization_code_success(self, auth_code_manager, sample_auth_code_data):
        """Test successful authorization code usage."""
        code = "auth_code_test123456789012345678901234"
        
        # Create valid authorization code
        auth_code_data = AuthorizationCode(
            code=code,
            expires_at=datetime.utcnow() + timedelta(seconds=300),
            used=False,
            **sample_auth_code_data
        )
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            # Mock get_authorization_code flow - need to handle multiple get calls
            mock_redis.get = AsyncMock(side_effect=[
                auth_code_data.model_dump_json(),  # First call in get_authorization_code
                "0"  # Second call for usage count check
            ])
            
            # Mock usage tracking
            mock_redis_conn = AsyncMock()
            mock_redis_conn.incr = AsyncMock(return_value=1)  # First usage
            mock_redis.get_redis = AsyncMock(return_value=mock_redis_conn)
            
            # Mock cleanup
            mock_redis.delete = AsyncMock(return_value=1)
            
            result = await auth_code_manager.use_authorization_code(code)
            
            assert result is not None
            assert result.code == code
            assert result.used is True
            
            # Verify usage tracking
            mock_redis_conn.incr.assert_called_once_with(f"{OAUTH2_AUTH_CODE_USAGE_PREFIX}{code}")
            
            # Verify cleanup (single use)
            assert mock_redis.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_use_authorization_code_replay_attack(self, auth_code_manager, sample_auth_code_data):
        """Test authorization code usage with replay attack detection."""
        code = "auth_code_replay"
        
        # Create valid authorization code
        auth_code_data = AuthorizationCode(
            code=code,
            expires_at=datetime.utcnow() + timedelta(seconds=300),
            used=False,
            **sample_auth_code_data
        )
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            # Mock get_authorization_code flow
            mock_redis.get = AsyncMock(side_effect=[
                auth_code_data.model_dump_json(),  # First call for get_authorization_code
                "1"  # Second call for usage count (already used)
            ])
            
            # Mock cleanup
            mock_redis.delete = AsyncMock(return_value=1)
            
            result = await auth_code_manager.use_authorization_code(code)
            
            assert result is None
            # Verify cleanup was called (code revoked due to replay attack)
            assert mock_redis.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_use_authorization_code_concurrent_usage(self, auth_code_manager, sample_auth_code_data):
        """Test authorization code usage with concurrent usage detection."""
        code = "auth_code_concurrent"
        
        # Create valid authorization code
        auth_code_data = AuthorizationCode(
            code=code,
            expires_at=datetime.utcnow() + timedelta(seconds=300),
            used=False,
            **sample_auth_code_data
        )
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            # Mock get_authorization_code flow
            mock_redis.get = AsyncMock(side_effect=[
                auth_code_data.model_dump_json(),  # First call for get_authorization_code
                "0"  # Usage count is 0
            ])
            
            # Mock concurrent usage (incr returns > 1)
            mock_redis_conn = AsyncMock()
            mock_redis_conn.incr = AsyncMock(return_value=2)  # Concurrent usage detected
            mock_redis.get_redis = AsyncMock(return_value=mock_redis_conn)
            
            # Mock cleanup
            mock_redis.delete = AsyncMock(return_value=1)
            
            result = await auth_code_manager.use_authorization_code(code)
            
            assert result is None
            # Verify cleanup was called (code revoked due to concurrent usage)
            assert mock_redis.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_revoke_authorization_code(self, auth_code_manager):
        """Test authorization code revocation."""
        code = "auth_code_revoke"
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            mock_redis.delete = AsyncMock(return_value=1)
            
            result = await auth_code_manager.revoke_authorization_code(code)
            
            assert result is True
            # Verify both code and usage tracking were deleted
            assert mock_redis.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_codes(self, auth_code_manager, sample_auth_code_data):
        """Test cleanup of expired authorization codes."""
        # Create test data with expired and valid codes
        expired_code = AuthorizationCode(
            code="auth_code_expired",
            expires_at=datetime.utcnow() - timedelta(seconds=60),  # Expired
            used=False,
            **sample_auth_code_data
        )
        
        valid_code = AuthorizationCode(
            code="auth_code_valid",
            expires_at=datetime.utcnow() + timedelta(seconds=300),  # Valid
            used=False,
            **sample_auth_code_data
        )
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            # Mock keys discovery
            mock_redis.keys = AsyncMock(return_value=[
                f"{OAUTH2_AUTH_CODE_PREFIX}auth_code_expired",
                f"{OAUTH2_AUTH_CODE_PREFIX}auth_code_valid"
            ])
            
            # Mock get calls for each key
            mock_redis.get = AsyncMock(side_effect=[
                expired_code.model_dump_json(),
                valid_code.model_dump_json()
            ])
            
            # Mock delete calls
            mock_redis.delete = AsyncMock(return_value=1)
            
            result = await auth_code_manager.cleanup_expired_codes()
            
            assert result == 1  # Only expired code should be cleaned up
            # Verify delete was called for expired code (code + usage tracking)
            assert mock_redis.delete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_get_code_statistics(self, auth_code_manager, sample_auth_code_data):
        """Test authorization code statistics retrieval."""
        # Create test codes with different states
        expired_code = AuthorizationCode(
            code="auth_code_expired",
            expires_at=datetime.utcnow() - timedelta(seconds=60),
            used=False,
            **sample_auth_code_data
        )
        
        used_code = AuthorizationCode(
            code="auth_code_used",
            expires_at=datetime.utcnow() + timedelta(seconds=300),
            used=True,
            **sample_auth_code_data
        )
        
        active_code = AuthorizationCode(
            code="auth_code_active",
            expires_at=datetime.utcnow() + timedelta(seconds=300),
            used=False,
            **sample_auth_code_data
        )
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            # Mock keys discovery
            mock_redis.keys = AsyncMock(return_value=[
                f"{OAUTH2_AUTH_CODE_PREFIX}auth_code_expired",
                f"{OAUTH2_AUTH_CODE_PREFIX}auth_code_used",
                f"{OAUTH2_AUTH_CODE_PREFIX}auth_code_active"
            ])
            
            # Mock get calls for each key
            mock_redis.get = AsyncMock(side_effect=[
                expired_code.model_dump_json(),
                used_code.model_dump_json(),
                active_code.model_dump_json()
            ])
            
            result = await auth_code_manager.get_code_statistics()
            
            assert result["total_codes"] == 3
            assert result["expired_codes"] == 1
            assert result["used_codes"] == 1
            assert result["active_codes"] == 1
    
    @pytest.mark.asyncio
    async def test_error_handling(self, auth_code_manager):
        """Test error handling in various scenarios."""
        code = "auth_code_error"
        
        with patch('second_brain_database.routes.oauth2.services.auth_code_manager.redis_manager') as mock_redis:
            # Test Redis connection error
            mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))
            
            result = await auth_code_manager.get_authorization_code(code)
            assert result is None
            
            # Test storage error
            mock_redis.setex = AsyncMock(side_effect=Exception("Redis storage error"))
            
            result = await auth_code_manager.store_authorization_code(
                code=code,
                client_id="test_client",
                user_id="test_user",
                redirect_uri="https://example.com/callback",
                scopes=["read:profile"],
                code_challenge="test_challenge",
                code_challenge_method=PKCEMethod.S256
            )
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__])