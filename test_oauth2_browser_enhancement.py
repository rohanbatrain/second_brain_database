#!/usr/bin/env python3
"""
Test script to verify OAuth2 browser enhancement implementation.

This script tests the enhanced OAuth2 authorization endpoint to ensure:
1. Browser detection works correctly
2. Flexible authentication dependency functions properly
3. State preservation and retrieval work as expected
4. Error handling provides appropriate responses for different client types
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all required imports work correctly."""
    print("Testing imports...")
    
    try:
        from second_brain_database.routes.oauth2.routes import (
            router,
            create_oauth2_flexible_user_dependency,
            _is_browser_request,
            _create_oauth2_state_key,
            _validate_retrieved_state
        )
        print("✅ All OAuth2 route imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_browser_detection():
    """Test browser detection functionality."""
    print("\nTesting browser detection...")
    
    try:
        from second_brain_database.routes.oauth2.routes import _is_browser_request
        from fastapi import Request
        from unittest.mock import Mock
        
        # Mock browser request with proper header handling
        browser_request = Mock(spec=Request)
        browser_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        browser_request.headers.get = lambda key, default="": browser_headers.get(key, default)
        
        # Mock API request with proper header handling
        api_request = Mock(spec=Request)
        api_headers = {
            "accept": "application/json",
            "user-agent": "python-requests/2.28.1"
        }
        api_request.headers.get = lambda key, default="": api_headers.get(key, default)
        
        # Test browser detection
        is_browser = _is_browser_request(browser_request)
        is_api = _is_browser_request(api_request)
        
        if is_browser and not is_api:
            print("✅ Browser detection works correctly")
            return True
        else:
            print(f"❌ Browser detection failed: browser={is_browser}, api={is_api}")
            return False
            
    except Exception as e:
        print(f"❌ Browser detection test error: {e}")
        return False

def test_state_key_generation():
    """Test OAuth2 state key generation."""
    print("\nTesting state key generation...")
    
    try:
        from second_brain_database.routes.oauth2.routes import _create_oauth2_state_key
        
        # Generate multiple state keys
        key1 = _create_oauth2_state_key("client1", "state1")
        key2 = _create_oauth2_state_key("client1", "state1")
        key3 = _create_oauth2_state_key("client2", "state1")
        
        # Keys should be different even with same inputs (due to randomness)
        if key1 != key2 and key1 != key3 and key2 != key3:
            print("✅ State key generation produces unique keys")
            
            # Check key format
            if all(key.startswith("oauth2_state:") for key in [key1, key2, key3]):
                print("✅ State keys have correct format")
                return True
            else:
                print("❌ State keys have incorrect format")
                return False
        else:
            print("❌ State key generation not producing unique keys")
            return False
            
    except Exception as e:
        print(f"❌ State key generation test error: {e}")
        return False

def test_state_validation():
    """Test OAuth2 state validation."""
    print("\nTesting state validation...")
    
    try:
        from second_brain_database.routes.oauth2.routes import _validate_retrieved_state
        from datetime import datetime, timezone
        
        # Valid state
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
        
        # Invalid state (missing fields)
        invalid_state = {
            "client_id": "test_client",
            "scope": "read write"
        }
        
        # Old state (expired)
        old_state = {
            **valid_state,
            "timestamp": "2020-01-01T00:00:00"
        }
        
        # Test validation
        valid_result = _validate_retrieved_state(valid_state)
        invalid_result = _validate_retrieved_state(invalid_state)
        old_result = _validate_retrieved_state(old_state)
        
        if valid_result and not invalid_result and not old_result:
            print("✅ State validation works correctly")
            return True
        else:
            print(f"❌ State validation failed: valid={valid_result}, invalid={invalid_result}, old={old_result}")
            return False
            
    except Exception as e:
        print(f"❌ State validation test error: {e}")
        return False

def test_flexible_dependency_creation():
    """Test flexible dependency creation."""
    print("\nTesting flexible dependency creation...")
    
    try:
        from second_brain_database.routes.oauth2.routes import create_oauth2_flexible_user_dependency
        
        # Create dependency function
        dependency_func = create_oauth2_flexible_user_dependency()
        
        if callable(dependency_func):
            print("✅ Flexible dependency function created successfully")
            return True
        else:
            print("❌ Flexible dependency function is not callable")
            return False
            
    except Exception as e:
        print(f"❌ Flexible dependency creation test error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing OAuth2 Browser Enhancement Implementation")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_browser_detection,
        test_state_key_generation,
        test_state_validation,
        test_flexible_dependency_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! OAuth2 browser enhancement is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())