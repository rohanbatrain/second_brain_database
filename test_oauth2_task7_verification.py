#!/usr/bin/env python3
"""
Verification test for OAuth2 Task 7: Create HTML templates for OAuth2 flows.

This test verifies that all requirements for task 7 have been implemented:
- Login page template with responsive design and accessibility
- Consent screen template showing client info and requested permissions  
- OAuth2 error page templates with user-friendly messages
- CSRF token fields in all forms
- Mobile responsiveness and proper styling
"""

import sys
import os
import re

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


def test_login_page_template():
    """Test that login page template exists and has required features."""
    print("Testing login page template...")
    
    # Check that browser_auth.py contains the login template
    try:
        with open('src/second_brain_database/routes/auth/browser_auth.py', 'r') as f:
            content = f.read()
            
        # Check for responsive design
        assert 'viewport' in content
        assert '@media (max-width: 480px)' in content
        
        # Check for accessibility features
        assert 'aria-label' in content
        assert 'autocomplete' in content
        
        # Check for CSRF token
        assert 'csrf_token' in content
        
        # Check for proper form structure
        assert 'method="post"' in content
        assert 'type="hidden"' in content
        
        print("✓ Login page template has all required features")
        
    except FileNotFoundError:
        print("❌ Login page template file not found")
        return False
    
    return True


def test_consent_screen_template():
    """Test consent screen template with all required features."""
    print("Testing consent screen template...")
    
    # Test data
    client_name = "Test Application"
    client_description = "A comprehensive test OAuth2 application"
    website_url = "https://example.com"
    requested_scopes = [
        {"scope": "read:profile", "description": "Read your profile information"},
        {"scope": "write:data", "description": "Write data to your account"},
        {"scope": "admin:settings", "description": "Manage application settings"}
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
    
    # Test client info display
    assert client_name in html
    assert client_description in html
    assert website_url in html
    
    # Test requested permissions display
    for scope in requested_scopes:
        assert scope['scope'] in html
        assert scope['description'] in html
    
    # Test CSRF token field
    assert f'name="csrf_token" value="{csrf_token}"' in html
    
    # Test responsive design
    assert '@media (max-width: 480px)' in html
    assert 'flex-direction: column' in html
    
    # Test accessibility features
    assert 'role="main"' in html
    assert 'aria-label' in html
    assert 'aria-describedby' in html
    assert 'role="list"' in html
    assert 'role="listitem"' in html
    
    # Test proper styling
    assert 'background: linear-gradient' in html
    assert 'border-radius' in html
    assert 'box-shadow' in html
    
    # Test high contrast and reduced motion support
    assert 'prefers-contrast: high' in html
    assert 'prefers-reduced-motion: reduce' in html
    
    # Test focus styles
    assert ':focus' in html
    assert 'outline:' in html
    
    print("✓ Consent screen template has all required features")
    return True


def test_oauth2_error_templates():
    """Test all OAuth2 error page templates."""
    print("Testing OAuth2 error page templates...")
    
    error_templates = [
        ("consent_error", render_consent_error, ["Test error message", "Test Client"]),
        ("authorization_error", render_oauth2_authorization_error, ["Authorization failed", "Invalid credentials", "Test App"]),
        ("session_expired", render_session_expired_error, ["Session expired message"]),
        ("authorization_failed", render_authorization_failed_error, ["Authorization process failed"]),
        ("generic_error", render_generic_oauth2_error, ["Custom Error", "Custom message", "🚫"])
    ]
    
    for template_name, template_func, args in error_templates:
        print(f"  Testing {template_name} template...")
        
        # Render template
        if template_name == "generic_error":
            html = template_func(*args)
        else:
            html = template_func(*args)
        
        # Test user-friendly messages
        assert any(arg in html for arg in args if isinstance(arg, str))
        
        # Test responsive design
        assert '@media (max-width: 480px)' in html
        
        # Test accessibility features
        assert 'role="main"' in html
        assert 'role="alert"' in html
        
        # Test proper styling
        assert 'background: linear-gradient' in html
        assert 'border-radius' in html
        
        # Test high contrast and reduced motion support
        assert 'prefers-contrast: high' in html
        assert 'prefers-reduced-motion: reduce' in html
        
        # Test focus styles
        assert ':focus' in html
        
        print(f"    ✓ {template_name} template passed")
    
    print("✓ All OAuth2 error templates have required features")
    return True


def test_mobile_responsiveness():
    """Test mobile responsiveness across all templates."""
    print("Testing mobile responsiveness...")
    
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
    
    # Check for mobile-specific CSS
    mobile_patterns = [
        r'@media \(max-width: 480px\)',
        r'flex-direction: column',
        r'width: 100%',
        r'padding: \d+px \d+px'
    ]
    
    for pattern in mobile_patterns:
        assert re.search(pattern, html), f"Mobile pattern not found: {pattern}"
    
    # Test error templates for mobile responsiveness
    error_html = render_oauth2_authorization_error("Test error", "Test details")
    
    for pattern in mobile_patterns:
        assert re.search(pattern, error_html), f"Mobile pattern not found in error template: {pattern}"
    
    print("✓ All templates are mobile responsive")
    return True


def test_accessibility_compliance():
    """Test accessibility compliance across all templates."""
    print("Testing accessibility compliance...")
    
    # Test consent screen accessibility
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
    accessibility_patterns = [
        r'role="main"',
        r'role="list"',
        r'role="listitem"',
        r'role="group"',
        r'aria-label="[^"]*"',
        r'aria-describedby="[^"]*"',
        r'aria-labelledby="[^"]*"',
        r'class="sr-only"',
        r':focus\s*{[^}]*outline:',
        r'prefers-contrast: high',
        r'prefers-reduced-motion: reduce'
    ]
    
    for pattern in accessibility_patterns:
        assert re.search(pattern, html), f"Accessibility pattern not found: {pattern}"
    
    # Test error template accessibility
    error_html = render_consent_error("Test error", "Test Client")
    
    error_accessibility_patterns = [
        r'role="main"',
        r'role="alert"',
        r'role="complementary"',
        r'aria-label="[^"]*"',
        r':focus\s*{[^}]*outline:'
    ]
    
    for pattern in error_accessibility_patterns:
        assert re.search(pattern, error_html), f"Error template accessibility pattern not found: {pattern}"
    
    print("✓ All templates are accessibility compliant")
    return True


def test_csrf_protection():
    """Test CSRF protection in all forms."""
    print("Testing CSRF protection...")
    
    # Test consent screen CSRF token
    csrf_token = "test_csrf_token_12345"
    html = render_consent_screen(
        client_name="Test App",
        client_description="Test Description",
        website_url="https://example.com",
        requested_scopes=[{"scope": "read", "description": "Read access"}],
        client_id="test",
        state="test",
        csrf_token=csrf_token
    )
    
    # Check for CSRF token field
    assert f'name="csrf_token" value="{csrf_token}"' in html
    assert 'type="hidden"' in html
    
    # Check that login template has CSRF protection
    try:
        with open('src/second_brain_database/routes/auth/browser_auth.py', 'r') as f:
            login_content = f.read()
            
        assert 'csrf_token' in login_content
        assert 'type="hidden"' in login_content
        
    except FileNotFoundError:
        print("❌ Login template file not found for CSRF check")
        return False
    
    print("✓ All forms have CSRF protection")
    return True


def test_proper_styling():
    """Test that all templates have proper styling."""
    print("Testing proper styling...")
    
    html = render_consent_screen(
        client_name="Test App",
        client_description="Test Description",
        website_url="https://example.com",
        requested_scopes=[{"scope": "read", "description": "Read access"}],
        client_id="test",
        state="test",
        csrf_token="test"
    )
    
    # Check for modern styling features
    styling_patterns = [
        r'background: linear-gradient',
        r'border-radius: \d+px',
        r'box-shadow: [^;]+',
        r'transition: [^;]+',
        r'font-family: [^;]+',
        r'transform: translateY',
        r'animation: [^;]+',
        r'@keyframes [^{]+{'
    ]
    
    for pattern in styling_patterns:
        assert re.search(pattern, html), f"Styling pattern not found: {pattern}"
    
    print("✓ All templates have proper styling")
    return True


def main():
    """Run all verification tests."""
    print("Running OAuth2 Task 7 verification tests...\n")
    
    tests = [
        test_login_page_template,
        test_consent_screen_template,
        test_oauth2_error_templates,
        test_mobile_responsiveness,
        test_accessibility_compliance,
        test_csrf_protection,
        test_proper_styling
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All Task 7 requirements have been successfully implemented!")
        print("\nTask 7 Summary:")
        print("- ✓ Login page template with responsive design and accessibility")
        print("- ✓ Consent screen template showing client info and requested permissions")
        print("- ✓ OAuth2 error page templates with user-friendly messages")
        print("- ✓ CSRF token fields in all forms")
        print("- ✓ Mobile responsiveness and proper styling")
        return 0
    else:
        print("❌ Some Task 7 requirements are not fully implemented")
        return 1


if __name__ == "__main__":
    sys.exit(main())