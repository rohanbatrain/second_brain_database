#!/usr/bin/env python3
"""
Verification script for OAuth2 comprehensive error handling implementation.
"""

import sys
import traceback

def test_error_handler():
    """Test OAuth2 error handler functionality."""
    try:
        from src.second_brain_database.routes.oauth2.error_handler import (
            OAuth2ErrorHandler, OAuth2ErrorCode, OAuth2ErrorSeverity
        )
        
        handler = OAuth2ErrorHandler()
        print("✓ OAuth2ErrorHandler imported successfully")
        
        # Test error codes
        assert OAuth2ErrorCode.INVALID_REQUEST == "invalid_request"
        assert OAuth2ErrorCode.ACCESS_DENIED == "access_denied"
        print("✓ OAuth2ErrorCode enum working correctly")
        
        # Test severity levels
        assert OAuth2ErrorSeverity.LOW == "low"
        assert OAuth2ErrorSeverity.HIGH == "high"
        print("✓ OAuth2ErrorSeverity enum working correctly")
        
        return True
    except Exception as e:
        print(f"✗ Error handler test failed: {e}")
        traceback.print_exc()
        return False

def test_browser_logger():
    """Test browser error logger functionality."""
    try:
        from src.second_brain_database.routes.oauth2.browser_error_logger import (
            BrowserErrorLogger, browser_error_logger
        )
        
        logger = BrowserErrorLogger()
        print("✓ BrowserErrorLogger imported successfully")
        
        # Test user agent parsing
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15"
        parsed = logger._parse_user_agent(ua)
        assert parsed["mobile"] == True
        print("✓ User agent parsing working correctly")
        
        return True
    except Exception as e:
        print(f"✗ Browser logger test failed: {e}")
        traceback.print_exc()
        return False

def test_templates():
    """Test error template functionality."""
    try:
        from src.second_brain_database.routes.oauth2.templates import (
            render_generic_oauth2_error,
            render_oauth2_authorization_error,
            render_session_expired_error
        )
        
        # Test generic error template
        html = render_generic_oauth2_error("Test Error", "Test message")
        assert "Test Error" in html
        assert "Test message" in html
        print("✓ Generic error template working correctly")
        
        # Test authorization error template
        html = render_oauth2_authorization_error("Auth error", "Details", "Test App")
        assert "Auth error" in html
        assert "Test App" in html
        print("✓ Authorization error template working correctly")
        
        # Test session expired template
        html = render_session_expired_error("Session expired")
        assert "Session expired" in html
        print("✓ Session expired template working correctly")
        
        return True
    except Exception as e:
        print(f"✗ Templates test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all verification tests."""
    print("🔍 Verifying OAuth2 comprehensive error handling implementation...")
    print()
    
    tests = [
        ("Error Handler", test_error_handler),
        ("Browser Logger", test_browser_logger),
        ("Templates", test_templates),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Testing {test_name}:")
        if test_func():
            passed += 1
            print(f"✅ {test_name} tests passed")
        else:
            print(f"❌ {test_name} tests failed")
        print()
    
    print(f"📊 Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("🎉 All comprehensive error handling components are working correctly!")
        return 0
    else:
        print("⚠️  Some components need attention")
        return 1

if __name__ == "__main__":
    sys.exit(main())