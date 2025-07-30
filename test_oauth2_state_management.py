"""
Test OAuth2 state management implementation.

This test file verifies the OAuth2 state management system including:
- State creation and storage
- State retrieval and validation
- State expiration and cleanup
- Security features and validation
"""

import asyncio
import pytest
import time
import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Mock the dependencies before importing the modules
with patch.dict('sys.modules', {
    'second_brain_database.config': MagicMock(),
    'second_brain_database.managers.redis_manager': MagicMock(),
    'second_brain_database.managers.logging_manager': MagicMock(),
}):
    # Create mock settings
    mock_settings = MagicMock()
    mock_fernet_key = MagicMock()
    mock_fernet_key.get_secret_value.return_value = "test_key_that_needs_to_be_32_bytes_long_for_fernet_encryption"
    mock_settings.FERNET_KEY = mock_fernet_key
    
    # Create mock Redis manager
    mock_redis_manager = MagicMock()
    mock_redis = AsyncMock()
    mock_redis_manager.get_redis.return_value = mock_redis
    
    # Create mock logger
    mock_get_logger = MagicMock()
    mock_logger = MagicMock()
    mock_get_logger.return_value = mock_logger
    
    # Set up the mocked modules
    sys.modules['second_brain_database.config'].settings = mock_settings
    sys.modules['second_brain_database.managers.redis_manager'].redis_manager = mock_redis_manager
    sys.modules['second_brain_database.managers.logging_manager'].get_logger = mock_get_logger
    
    # Now import the modules
    from src.second_brain_database.routes.oauth2.state_manager import OAuth2StateManager
    from src.second_brain_database.routes.oauth2.cleanup_tasks import OAuth2CleanupTasks


class TestOAuth2StateManager:
    """Test cases for OAuth2StateManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.state_manager = OAuth2StateManager()
        self.mock_request = MagicMock()
        self.mock_request.client.host = "127.0.0.1"
        self.mock_request.headers = {
            "user-agent": "test-browser",
            "accept-language": "en-US",
            "accept-encoding": "gzip, deflate",
            "connection": "keep-alive"
        }
        self.mock_request.method = "GET"
        self.mock_request.url.path = "/oauth2/authorize"
        self.mock_request.query_params.items.return_value = [("client_id", "test_client")]
        self.mock_request.state = MagicMock()
        self.mock_request.state.request_id = "test_request_id"
    
    def test_generate_state_key(self):
        """Test state key generation."""
        client_id = "test_client_123"
        original_state = "test_state_456"
        
        # Generate state key
        state_key = self.state_manager.generate_state_key(client_id, original_state)
        
        # Verify state key format
        assert state_key.startswith("oauth2_state:")
        assert len(state_key.split(":")) == 4
        assert client_id not in state_key  # Should be hashed
        assert original_state not in state_key  # Should be hashed
        
        # Generate another key with same inputs - should be different (due to randomness)
        state_key2 = self.state_manager.generate_state_key(client_id, original_state)
        assert state_key != state_key2
    
    @pytest.mark.asyncio
    async def test_store_authorization_state(self):
        """Test storing OAuth2 authorization state."""
        # Mock Redis operations
        mock_redis = AsyncMock()
        with patch.object(self.state_manager.redis_manager, 'get_redis', return_value=mock_redis):
            # Test parameters
            client_id = "test_client"
            redirect_uri = "https://example.com/callback"
            scope = "read write"
            state = "test_state"
            code_challenge = "test_challenge"
            code_challenge_method = "S256"
            response_type = "code"
            
            # Store state
            state_key = await self.state_manager.store_authorization_state(
                request=self.mock_request,
                client_id=client_id,
                redirect_uri=redirect_uri,
                scope=scope,
                state=state,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                response_type=response_type
            )
            
            # Verify state key format
            assert state_key.startswith("oauth2_state:")
            
            # Verify Redis operations
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            
            # Check Redis key format
            redis_key = call_args[0][0]
            assert redis_key == f"oauth2:state:{state_key}"
            
            # Check TTL
            ttl = call_args[0][1]
            assert ttl == 1800  # Default TTL
            
            # Check encrypted data was stored
            encrypted_data = call_args[0][2]
            assert isinstance(encrypted_data, str)
            assert len(encrypted_data) > 0
    
    @pytest.mark.asyncio
    async def test_retrieve_authorization_state(self):
        """Test retrieving OAuth2 authorization state."""
        # Mock Redis operations
        mock_redis = AsyncMock()
        
        # Create test state data
        test_state_data = {
            "client_id": "test_client",
            "redirect_uri": "https://example.com/callback",
            "scope": "read write",
            "state": "test_state",
            "code_challenge": "test_challenge",
            "code_challenge_method": "S256",
            "response_type": "code",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client_ip": "127.0.0.1",
            "user_agent": "test-browser",
            "storage_version": "1.0",
            "ttl_seconds": 1800
        }
        
        # Encrypt the test data
        encrypted_data = await self.state_manager._encrypt_state_data(test_state_data)
        
        # Mock Redis to return encrypted data
        mock_redis.get.return_value = encrypted_data
        
        with patch.object(self.state_manager.redis_manager, 'get_redis', return_value=mock_redis):
            # Retrieve state
            state_key = "oauth2_state:test_key:123456:random"
            retrieved_state = await self.state_manager.retrieve_authorization_state(state_key)
            
            # Verify retrieved data
            assert retrieved_state is not None
            assert retrieved_state["client_id"] == "test_client"
            assert retrieved_state["redirect_uri"] == "https://example.com/callback"
            assert retrieved_state["scope"] == "read write"
            assert retrieved_state["state"] == "test_state"
            assert retrieved_state["code_challenge"] == "test_challenge"
            assert retrieved_state["code_challenge_method"] == "S256"
            assert retrieved_state["response_type"] == "code"
            
            # Verify Redis operations
            mock_redis.get.assert_called_once_with(f"oauth2:state:{state_key}")
            mock_redis.delete.assert_called_once_with(f"oauth2:state:{state_key}")
    
    @pytest.mark.asyncio
    async def test_retrieve_nonexistent_state(self):
        """Test retrieving non-existent OAuth2 state."""
        # Mock Redis operations
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        
        with patch.object(self.state_manager.redis_manager, 'get_redis', return_value=mock_redis):
            # Try to retrieve non-existent state
            state_key = "oauth2_state:nonexistent:123456:random"
            retrieved_state = await self.state_manager.retrieve_authorization_state(state_key)
            
            # Verify no state returned
            assert retrieved_state is None
            
            # Verify Redis operations
            mock_redis.get.assert_called_once_with(f"oauth2:state:{state_key}")
            mock_redis.delete.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_validate_state_parameters(self):
        """Test state parameter validation."""
        # Mock Redis operations
        mock_redis = AsyncMock()
        
        # Create test state data
        test_state_data = {
            "client_id": "test_client",
            "state": "test_state",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "response_type": "code",
            "code_challenge_method": "S256"
        }
        
        # Encrypt the test data
        encrypted_data = await self.state_manager._encrypt_state_data(test_state_data)
        mock_redis.get.return_value = encrypted_data
        
        with patch.object(self.state_manager.redis_manager, 'get_redis', return_value=mock_redis):
            state_key = "oauth2_state:test_key:123456:random"
            
            # Test valid parameters
            is_valid = await self.state_manager.validate_state_parameters(
                state_key=state_key,
                expected_client_id="test_client",
                expected_state="test_state"
            )
            assert is_valid is True
            
            # Test invalid client_id
            is_valid = await self.state_manager.validate_state_parameters(
                state_key=state_key,
                expected_client_id="wrong_client",
                expected_state="test_state"
            )
            assert is_valid is False
            
            # Test invalid state
            is_valid = await self.state_manager.validate_state_parameters(
                state_key=state_key,
                expected_client_id="test_client",
                expected_state="wrong_state"
            )
            assert is_valid is False
    
    def test_validate_state_integrity_valid(self):
        """Test state integrity validation with valid data."""
        valid_state = {
            "client_id": "test_client",
            "redirect_uri": "https://example.com/callback",
            "scope": "read write",
            "state": "test_state",
            "code_challenge": "test_challenge",
            "code_challenge_method": "S256",
            "response_type": "code",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        is_valid = self.state_manager._validate_state_integrity(valid_state)
        assert is_valid is True
    
    def test_validate_state_integrity_missing_fields(self):
        """Test state integrity validation with missing fields."""
        invalid_state = {
            "client_id": "test_client",
            "redirect_uri": "https://example.com/callback",
            # Missing required fields
        }
        
        is_valid = self.state_manager._validate_state_integrity(invalid_state)
        assert is_valid is False
    
    def test_validate_state_integrity_invalid_response_type(self):
        """Test state integrity validation with invalid response type."""
        invalid_state = {
            "client_id": "test_client",
            "redirect_uri": "https://example.com/callback",
            "scope": "read write",
            "state": "test_state",
            "code_challenge": "test_challenge",
            "code_challenge_method": "S256",
            "response_type": "token",  # Invalid
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        is_valid = self.state_manager._validate_state_integrity(invalid_state)
        assert is_valid is False
    
    def test_validate_state_integrity_invalid_challenge_method(self):
        """Test state integrity validation with invalid challenge method."""
        invalid_state = {
            "client_id": "test_client",
            "redirect_uri": "https://example.com/callback",
            "scope": "read write",
            "state": "test_state",
            "code_challenge": "test_challenge",
            "code_challenge_method": "MD5",  # Invalid
            "response_type": "code",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        is_valid = self.state_manager._validate_state_integrity(invalid_state)
        assert is_valid is False
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_states(self):
        """Test cleanup of expired states."""
        # Mock Redis operations
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = [
            "oauth2:state:key1",
            "oauth2:state:key2",
            "oauth2:state:key3"
        ]
        mock_redis.ttl.side_effect = [300, -2, -1]  # Active, expired, no TTL
        
        with patch.object(self.state_manager.redis_manager, 'get_redis', return_value=mock_redis):
            # Perform cleanup
            cleaned_count = await self.state_manager.cleanup_expired_states()
            
            # Verify cleanup results
            assert cleaned_count == 1  # One expired key
            
            # Verify Redis operations
            mock_redis.keys.assert_called_once_with("oauth2:state:*")
            assert mock_redis.ttl.call_count == 3
            mock_redis.expire.assert_called_once_with("oauth2:state:key3", 1800)
    
    @pytest.mark.asyncio
    async def test_get_state_statistics(self):
        """Test getting state statistics."""
        # Mock Redis operations
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = [
            "oauth2:state:key1",
            "oauth2:state:key2",
            "oauth2:state:key3",
            "oauth2:state:key4"
        ]
        mock_redis.ttl.side_effect = [200, 600, 2000, -1]  # Various TTL values
        
        with patch.object(self.state_manager.redis_manager, 'get_redis', return_value=mock_redis):
            # Get statistics
            stats = await self.state_manager.get_state_statistics()
            
            # Verify statistics
            assert stats["total_states"] == 4
            assert stats["expiring_soon"] == 1  # TTL < 300
            assert stats["normal_ttl"] == 1     # 300 <= TTL <= 1800
            assert stats["long_ttl"] == 1       # TTL > 1800
            # One with TTL -1 is not counted in any category


class TestOAuth2CleanupTasks:
    """Test cases for OAuth2CleanupTasks."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.cleanup_tasks = OAuth2CleanupTasks()
    
    @pytest.mark.asyncio
    async def test_manual_cleanup(self):
        """Test manual cleanup operation."""
        # Create a mock state manager for testing
        mock_state_manager = MagicMock()
        mock_state_manager.cleanup_expired_states = AsyncMock(return_value=5)
        mock_state_manager.get_state_statistics = AsyncMock()
        
        with patch('src.second_brain_database.routes.oauth2.cleanup_tasks.oauth2_state_manager', mock_state_manager):
            
            # Mock statistics before and after cleanup
            mock_state_manager.get_state_statistics.side_effect = [
                {"total_states": 10, "expiring_soon": 2, "normal_ttl": 6, "long_ttl": 2},
                {"total_states": 5, "expiring_soon": 1, "normal_ttl": 3, "long_ttl": 1}
            ]
            
            # Perform manual cleanup
            results = await self.cleanup_tasks.manual_cleanup()
            
            # Verify results
            assert results["cleaned_states"] == 5
            assert results["states_removed"] == 5  # 10 - 5
            assert "cleanup_timestamp" in results
            assert "stats_before" in results
            assert "stats_after" in results
    
    @pytest.mark.asyncio
    async def test_get_cleanup_status(self):
        """Test getting cleanup status."""
        # Create a mock state manager for testing
        mock_state_manager = MagicMock()
        mock_state_manager.get_state_statistics = AsyncMock(return_value={
            "total_states": 8,
            "expiring_soon": 1,
            "normal_ttl": 5,
            "long_ttl": 2
        })
        
        with patch('src.second_brain_database.routes.oauth2.cleanup_tasks.oauth2_state_manager', mock_state_manager):
            
            # Get cleanup status
            status = await self.cleanup_tasks.get_cleanup_status()
            
            # Verify status
            assert "cleanup_running" in status
            assert status["cleanup_interval_seconds"] == 300
            assert "current_timestamp" in status
            assert "state_statistics" in status
            assert status["state_statistics"]["total_states"] == 8


def test_oauth2_state_manager_creation():
    """Test that OAuth2StateManager can be created."""
    state_manager = OAuth2StateManager()
    assert state_manager is not None
    assert isinstance(state_manager, OAuth2StateManager)


def test_oauth2_cleanup_tasks_creation():
    """Test that OAuth2CleanupTasks can be created."""
    cleanup_tasks = OAuth2CleanupTasks()
    assert cleanup_tasks is not None
    assert isinstance(cleanup_tasks, OAuth2CleanupTasks)


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])