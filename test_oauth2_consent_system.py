#!/usr/bin/env python3
"""
Test script for OAuth2 consent system functionality.

This script tests the basic functionality of the OAuth2 consent system
including consent screen rendering and consent decision handling.
"""

import asyncio
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_consent_imports():
    """Test that all consent system imports work correctly."""
    try:
        print("Testing consent system imports...")
        
        # Test consent module import
        from second_brain_database.routes.oauth2.consent import router
        print("✓ Consent router imported successfully")
        
        # Test template functions
        from second_brain_database.routes.oauth2.templates import render_consent_screen, render_consent_error
        print("✓ Template functions imported successfully")
        
        # Test consent manager
        from second_brain_database.routes.oauth2.services.consent_manager import consent_manager
        print("✓ Consent manager imported successfully")
        
        # Test models
        from second_brain_database.routes.oauth2.models import ConsentRequest, get_scope_descriptions
        print("✓ Consent models imported successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

async def test_consent_screen_rendering():
    """Test consent screen HTML rendering."""
    try:
        print("\nTesting consent screen rendering...")
        
        from second_brain_database.routes.oauth2.templates import render_consent_screen
        from second_brain_database.routes.oauth2.models import get_scope_descriptions
        
        # Test scope descriptions
        test_scopes = ["read:profile", "write:data"]
        scope_descriptions = get_scope_descriptions(test_scopes)
        print(f"✓ Generated scope descriptions: {len(scope_descriptions)} scopes")
        
        # Test consent screen rendering
        html = render_consent_screen(
            client_name="Test Application",
            client_description="A test OAuth2 application",
            website_url="https://example.com",
            requested_scopes=scope_descriptions,
            client_id="test_client_123",
            state="test_state_456",
            existing_consent=False
        )
        
        # Basic HTML validation
        assert "<html" in html
        assert "Test Application" in html
        assert "read:profile" in html
        assert "write:data" in html
        assert 'name="client_id"' in html
        assert 'name="state"' in html
        assert 'name="approved"' in html
        
        print("✓ Consent screen HTML rendered successfully")
        print(f"✓ HTML length: {len(html)} characters")
        
        return True
        
    except Exception as e:
        print(f"✗ Consent screen rendering error: {e}")
        return False

async def test_consent_error_rendering():
    """Test consent error screen HTML rendering."""
    try:
        print("\nTesting consent error screen rendering...")
        
        from second_brain_database.routes.oauth2.templates import render_consent_error
        
        # Test error screen rendering
        html = render_consent_error(
            error_message="Test error message",
            client_name="Test Application"
        )
        
        # Basic HTML validation
        assert "<html" in html
        assert "Test error message" in html
        assert "Test Application" in html
        assert "Authorization Error" in html
        
        print("✓ Consent error screen HTML rendered successfully")
        print(f"✓ HTML length: {len(html)} characters")
        
        return True
        
    except Exception as e:
        print(f"✗ Consent error screen rendering error: {e}")
        return False

async def test_consent_request_model():
    """Test ConsentRequest model validation."""
    try:
        print("\nTesting ConsentRequest model...")
        
        from second_brain_database.routes.oauth2.models import ConsentRequest
        
        # Test valid consent request
        consent_request = ConsentRequest(
            client_id="test_client_123",
            scopes=["read:profile", "write:data"],
            approved=True,
            state="test_state_456"
        )
        
        assert consent_request.client_id == "test_client_123"
        assert consent_request.scopes == ["read:profile", "write:data"]
        assert consent_request.approved is True
        assert consent_request.state == "test_state_456"
        
        print("✓ ConsentRequest model validation successful")
        
        # Test denial
        denial_request = ConsentRequest(
            client_id="test_client_123",
            scopes=["read:profile"],
            approved=False,
            state="test_state_456"
        )
        
        assert denial_request.approved is False
        print("✓ ConsentRequest denial model validation successful")
        
        return True
        
    except Exception as e:
        print(f"✗ ConsentRequest model error: {e}")
        return False

async def test_scope_validation():
    """Test scope validation functionality."""
    try:
        print("\nTesting scope validation...")
        
        from second_brain_database.routes.oauth2.models import validate_scopes, get_scope_descriptions
        
        # Test valid scopes
        valid_scopes = ["read:profile", "write:data", "read:tokens"]
        validated = validate_scopes(valid_scopes)
        assert validated == valid_scopes
        print("✓ Valid scopes validation successful")
        
        # Test scope descriptions
        descriptions = get_scope_descriptions(valid_scopes)
        assert len(descriptions) == len(valid_scopes)
        assert all("scope" in desc and "description" in desc for desc in descriptions)
        print("✓ Scope descriptions generation successful")
        
        # Test invalid scope
        try:
            invalid_scopes = ["read:profile", "invalid:scope"]
            validate_scopes(invalid_scopes)
            print("✗ Invalid scope validation should have failed")
            return False
        except ValueError:
            print("✓ Invalid scope validation correctly failed")
        
        return True
        
    except Exception as e:
        print(f"✗ Scope validation error: {e}")
        return False

async def main():
    """Run all consent system tests."""
    print("OAuth2 Consent System Test Suite")
    print("=" * 50)
    
    tests = [
        test_consent_imports,
        test_consent_screen_rendering,
        test_consent_error_rendering,
        test_consent_request_model,
        test_scope_validation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = await test()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All consent system tests passed!")
        return True
    else:
        print("❌ Some consent system tests failed!")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)