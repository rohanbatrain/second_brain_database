"""
Simple test for OAuth2 state management functionality.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_state_manager_import():
    """Test that we can import the state manager module."""
    try:
        # Mock the dependencies
        from unittest.mock import MagicMock, patch
        
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
            mock_redis_manager.get_redis.return_value = MagicMock()
            
            # Create mock logger
            mock_get_logger = MagicMock()
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            # Set up the mocked modules
            sys.modules['second_brain_database.config'].settings = mock_settings
            sys.modules['second_brain_database.managers.redis_manager'].redis_manager = mock_redis_manager
            sys.modules['second_brain_database.managers.logging_manager'].get_logger = mock_get_logger
            
            # Import the state manager
            from src.second_brain_database.routes.oauth2.state_manager import OAuth2StateManager
            
            # Create an instance
            state_manager = OAuth2StateManager()
            
            # Test basic functionality
            assert state_manager is not None
            assert hasattr(state_manager, 'generate_state_key')
            assert hasattr(state_manager, 'store_authorization_state')
            assert hasattr(state_manager, 'retrieve_authorization_state')
            
            # Test state key generation
            client_id = "test_client"
            original_state = "test_state"
            state_key = state_manager.generate_state_key(client_id, original_state)
            
            assert state_key.startswith("oauth2_state:")
            assert len(state_key.split(":")) == 4
            
            print("✓ OAuth2StateManager import and basic functionality test passed")
            return True
            
    except Exception as e:
        print(f"✗ OAuth2StateManager test failed: {e}")
        return False


def test_cleanup_tasks_import():
    """Test that we can import the cleanup tasks module."""
    try:
        # Mock the dependencies
        from unittest.mock import MagicMock, patch
        
        with patch.dict('sys.modules', {
            'second_brain_database.managers.logging_manager': MagicMock(),
        }):
            # Create mock logger
            mock_get_logger = MagicMock()
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            # Set up the mocked modules
            sys.modules['second_brain_database.managers.logging_manager'].get_logger = mock_get_logger
            
            # Import the cleanup tasks
            from src.second_brain_database.routes.oauth2.cleanup_tasks import OAuth2CleanupTasks
            
            # Create an instance
            cleanup_tasks = OAuth2CleanupTasks()
            
            # Test basic functionality
            assert cleanup_tasks is not None
            assert hasattr(cleanup_tasks, 'start_cleanup_tasks')
            assert hasattr(cleanup_tasks, 'stop_cleanup_tasks')
            assert hasattr(cleanup_tasks, 'manual_cleanup')
            assert hasattr(cleanup_tasks, 'get_cleanup_status')
            
            print("✓ OAuth2CleanupTasks import and basic functionality test passed")
            return True
            
    except Exception as e:
        print(f"✗ OAuth2CleanupTasks test failed: {e}")
        return False


if __name__ == "__main__":
    print("Running OAuth2 state management tests...")
    
    success = True
    success &= test_state_manager_import()
    success &= test_cleanup_tasks_import()
    
    if success:
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed!")
        sys.exit(1)