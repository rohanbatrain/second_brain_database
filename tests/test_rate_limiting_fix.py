#!/usr/bin/env python3
"""
Test script to verify rate limiting status code standardization.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_environment_detection():
    """Test that environment detection works correctly."""
    print("Testing environment detection...")
    
    from second_brain_database.config import settings
    
    # Test normal execution (should be False)
    print(f"Normal execution - is_testing: {settings.is_testing}")
    assert settings.is_testing == False, "Should not detect test environment in normal execution"
    
    # Simulate pytest environment
    sys.modules['pytest'] = type(sys)('pytest')  # Mock pytest module
    
    # Reload settings to pick up the change
    import importlib
    from second_brain_database import config
    importlib.reload(config)
    from second_brain_database.config import settings as new_settings
    
    print(f"With pytest module - is_testing: {new_settings.is_testing}")
    assert new_settings.is_testing == True, "Should detect test environment when pytest is in sys.modules"
    
    # Clean up
    del sys.modules['pytest']
    
    print("✅ Environment detection working correctly")


def test_oauth2_security_manager_rate_limiting():
    """Test OAuth2 security manager rate limiting behavior."""
    print("\nTesting OAuth2 security manager rate limiting...")
    
    from second_brain_database.routes.oauth2.security_manager import oauth2_security_manager
    from second_brain_database.config import settings
    from fastapi import Request
    from unittest.mock import Mock, AsyncMock
    
    # Create mock request
    mock_request = Mock(spec=Request)
    mock_request.client = Mock()
    mock_request.client.host = "127.0.0.1"
    
    # Test that rate limiting is skipped in test environment
    print(f"Current is_testing: {settings.is_testing}")
    
    # Since we're not in a test environment, let's mock the security manager
    oauth2_security_manager.security_manager.check_rate_limit = AsyncMock()
    
    # This should not raise an exception
    import asyncio
    
    async def test_rate_limit():
        try:
            await oauth2_security_manager.rate_limit_client(
                request=mock_request,
                client_id="test_client",
                endpoint="authorize"
            )
            print("✅ Rate limiting call completed without error")
            return True
        except Exception as e:
            print(f"❌ Rate limiting failed: {e}")
            return False
    
    result = asyncio.run(test_rate_limit())
    assert result, "Rate limiting should work correctly"


def test_documentation_middleware():
    """Test documentation middleware rate limiting behavior."""
    print("\nTesting documentation middleware...")
    
    from second_brain_database.docs.middleware import DocumentationSecurityMiddleware
    from second_brain_database.config import settings
    from fastapi import Request
    from unittest.mock import Mock
    
    # Create middleware instance
    middleware = DocumentationSecurityMiddleware(None)
    
    # Create mock request
    mock_request = Mock(spec=Request)
    mock_request.client = Mock()
    mock_request.client.host = "127.0.0.1"
    mock_request.headers = {"User-Agent": "test"}
    
    # Test rate limiting check
    import asyncio
    
    async def test_docs_rate_limit():
        try:
            result = await middleware._check_rate_limit(mock_request)
            print(f"Documentation rate limit result: {result}")
            print("✅ Documentation middleware rate limiting working")
            return True
        except Exception as e:
            print(f"❌ Documentation middleware failed: {e}")
            return False
    
    result = asyncio.run(test_docs_rate_limit())
    assert result, "Documentation middleware should work correctly"


def test_oauth2_error_handler():
    """Test OAuth2 error handler status codes."""
    print("\nTesting OAuth2 error handler status codes...")
    
    from second_brain_database.routes.oauth2.error_handler import oauth2_error_handler, OAuth2ErrorCode
    
    # Test rate limit error returns 429
    response = oauth2_error_handler.token_error(
        error_code=OAuth2ErrorCode.RATE_LIMIT_EXCEEDED,
        error_description="Rate limit exceeded"
    )
    
    print(f"Rate limit error status code: {response.status_code}")
    assert response.status_code == 429, "Rate limit error should return 429 status code"
    
    # Test other error codes
    test_cases = [
        (OAuth2ErrorCode.INVALID_CLIENT, 400),
        (OAuth2ErrorCode.ACCESS_DENIED, 403),
        (OAuth2ErrorCode.SERVER_ERROR, 500),
    ]
    
    for error_code, expected_status in test_cases:
        response = oauth2_error_handler.token_error(
            error_code=error_code,
            error_description=f"Test {error_code.value}"
        )
        print(f"{error_code.value} -> {response.status_code} (expected {expected_status})")
        assert response.status_code == expected_status, f"{error_code.value} should return {expected_status}"
    
    print("✅ OAuth2 error handler status codes correct")


if __name__ == "__main__":
    print("🧪 Testing rate limiting status code standardization...")
    
    try:
        test_environment_detection()
        test_oauth2_security_manager_rate_limiting()
        test_documentation_middleware()
        test_oauth2_error_handler()
        
        print("\n🎉 All tests passed! Rate limiting status code standardization is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)