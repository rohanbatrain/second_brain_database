#!/usr/bin/env python3
"""
Simple test script for the OAuth2 session manager.

This script tests the basic functionality of the session manager
to ensure it works correctly with Redis and handles sessions properly.
"""

import asyncio
import sys
from datetime import datetime
from unittest.mock import Mock

# Add the src directory to the path
sys.path.insert(0, 'src')

from second_brain_database.routes.oauth2.session_manager import session_manager, SESSION_COOKIE_NAME, CSRF_COOKIE_NAME


async def test_session_manager():
    """Test basic session manager functionality."""
    print("Testing OAuth2 Session Manager...")
    
    # Mock request and response objects
    mock_request = Mock()
    mock_request.cookies = {}
    mock_request.headers = {"user-agent": "test-agent"}
    mock_request.client = Mock()
    mock_request.client.host = "127.0.0.1"
    
    mock_response = Mock()
    mock_response.set_cookie = Mock()
    mock_response.delete_cookie = Mock()
    
    # Mock user data
    mock_user = {
        "_id": "test_user_123",
        "username": "testuser"
    }
    
    try:
        print("1. Testing session creation...")
        session = await session_manager.create_session(
            user=mock_user,
            request=mock_request,
            response=mock_response
        )
        print(f"   ✓ Session created: {session.session_id}")
        print(f"   ✓ User ID: {session.user_id}")
        print(f"   ✓ CSRF token: {session.csrf_token}")
        
        print("2. Testing session validation...")
        # Add session cookie to mock request
        mock_request.cookies[SESSION_COOKIE_NAME] = session.session_id
        
        user_data = await session_manager.validate_session(mock_request)
        if user_data:
            print(f"   ✓ Session validated for user: {user_data['username']}")
        else:
            print("   ✗ Session validation failed")
            return False
        
        print("3. Testing session destruction...")
        destroyed = await session_manager.destroy_session(mock_request, mock_response)
        if destroyed:
            print("   ✓ Session destroyed successfully")
        else:
            print("   ✗ Session destruction failed")
            return False
        
        print("4. Testing validation after destruction...")
        user_data = await session_manager.validate_session(mock_request)
        if user_data is None:
            print("   ✓ Session correctly invalidated after destruction")
        else:
            print("   ✗ Session still valid after destruction")
            return False
        
        print("\n✅ All session manager tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Session manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function."""
    print("OAuth2 Session Manager Test")
    print("=" * 40)
    
    success = await test_session_manager()
    
    if success:
        print("\n🎉 Session manager is working correctly!")
        sys.exit(0)
    else:
        print("\n💥 Session manager tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())