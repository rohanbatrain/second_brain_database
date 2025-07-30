#!/usr/bin/env python3
"""
Test script for OAuth2 HTML templates.

This script tests the OAuth2 template rendering functions to ensure they
generate valid HTML with proper accessibility features and CSRF protection.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from second_brain_database.routes.oauth2.templates import (
    render_consent_screen,
    render_consent_error,
    render_oauth2_authorization_error,
    render_session_expired_error,
    render_authorization_failed_error,
    render_generic_oauth2_error
)


def test_consent_screen():
    """Test the consent screen template."""
    print("Testing consent screen template...")
    
    # Test data
    client_name = "Test Application"
    client_description = "A test OAuth2 application"
    website_url = "https://example.com"
    requested_scopes = [
        {"scope": "read:profile", "description": "Read your profile information"},
        {"scope": "write:data", "description": "Write data to your account"}
    ]
    client_id = "test_client_123"
    state = "test_state_456"
    csrf_token = "test_csrf_token_789"
    
    # Render template
    html = render_consent_screen(
        client_name=client_name,
        client_description=client_description,
        website_url=website_url,
        requested_scopes=requested_scopes,
        client_id=client_id,
        state=state,
        csrf_token=csrf_token,
        existing_consent=False
    )
    
    # Basic checks
    assert "Test Application" in html
    assert "csrf_token" in html
    assert "test_csrf_token_789" in html
    assert "read:profile" in html
    assert "write:data" in html
    assert 'role="main"' in html
    assert 'aria-label' in html
    
    print("✓ Consent screen template test passed")


def test_consent_error():
    """Test the consent error template."""
    print("Testing consent error template...")
    
    html = render_consent_error(
        error_message="Test error message",
        client_name="Test Client"
    )
    
    # Basic checks
    assert "Test error message" in html
    assert "Test Client" in html
    assert 'role="main"' in html
    assert 'role="alert"' in html
    
    print("✓ Consent error template test passed")


def test_oauth2_authorization_error():
    """Test the OAuth2 authorization error template."""
    print("Testing OAuth2 authorization error template...")
    
    html = render_oauth2_authorization_error(
        error_message="Authorization failed",
        error_details="Invalid client credentials",
        client_name="Test App"
    )
    
    # Basic checks
    assert "Authorization failed" in html
    assert "Invalid client credentials" in html
    assert "Test App" in html
    assert 'role="main"' in html
    assert 'role="alert"' in html
    
    print("✓ OAuth2 authorization error template test passed")


def test_session_expired_error():
    """Test the session expired error template."""
    print("Testing session expired error template...")
    
    html = render_session_expired_error(
        message="Your session has expired",
        show_login_button=True
    )
    
    # Basic checks
    assert "Your session has expired" in html
    assert "Login Again" in html
    assert 'role="main"' in html
    assert 'role="alert"' in html
    
    print("✓ Session expired error template test passed")


def test_authorization_failed_error():
    """Test the authorization failed error template."""
    print("Testing authorization failed error template...")
    
    html = render_authorization_failed_error(
        message="Authorization process failed",
        show_retry_button=True
    )
    
    # Basic checks
    assert "Authorization process failed" in html
    assert "Try Again" in html
    assert 'role="main"' in html
    assert 'role="alert"' in html
    
    print("✓ Authorization failed error template test passed")


def test_generic_oauth2_error():
    """Test the generic OAuth2 error template."""
    print("Testing generic OAuth2 error template...")
    
    html = render_generic_oauth2_error(
        title="Custom Error",
        message="This is a custom error message",
        icon="🚫",
        show_login_button=True,
        show_back_button=True,
        additional_info="Additional information about the error"
    )
    
    # Basic checks
    assert "Custom Error" in html
    assert "This is a custom error message" in html
    assert "🚫" in html
    assert "Additional information about the error" in html
    assert 'role="main"' in html
    assert 'role="alert"' in html
    
    print("✓ Generic OAuth2 error template test passed")


def test_accessibility_features():
    """Test that all templates include proper accessibility features."""
    print("Testing accessibility features...")
    
    # Test consent screen
    html = render_consent_screen(
        client_name="Test App",
        client_description="Test Description",
        website_url="https://example.com",
        requested_scopes=[{"scope": "read", "description": "Read access"}],
        client_id="test",
        state="test",
        csrf_token="test"
    )
    
    # Check for accessibility features
    assert 'role="main"' in html
    assert 'aria-label' in html
    assert 'aria-describedby' in html
    assert 'role="list"' in html
    assert 'role="listitem"' in html
    assert '.sr-only' in html  # Screen reader only class
    assert 'prefers-reduced-motion' in html
    assert 'prefers-contrast' in html
    assert ':focus' in html
    
    print("✓ Accessibility features test passed")


def test_mobile_responsiveness():
    """Test that all templates include mobile responsive CSS."""
    print("Testing mobile responsiveness...")
    
    html = render_consent_screen(
        client_name="Test App",
        client_description="Test Description", 
        website_url="https://example.com",
        requested_scopes=[{"scope": "read", "description": "Read access"}],
        client_id="test",
        state="test",
        csrf_token="test"
    )
    
    # Check for mobile responsive CSS
    assert '@media (max-width: 480px)' in html
    assert 'flex-direction: column' in html
    assert 'width: 100%' in html
    
    print("✓ Mobile responsiveness test passed")


def main():
    """Run all template tests."""
    print("Running OAuth2 template tests...\n")
    
    try:
        test_consent_screen()
        test_consent_error()
        test_oauth2_authorization_error()
        test_session_expired_error()
        test_authorization_failed_error()
        test_generic_oauth2_error()
        test_accessibility_features()
        test_mobile_responsiveness()
        
        print("\n✅ All template tests passed!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Template test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())