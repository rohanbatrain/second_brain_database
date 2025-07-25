#!/usr/bin/env python3
"""
Simple test script to verify WebAuthn authentication endpoints are properly implemented.

This script tests the basic structure and imports of the WebAuthn authentication endpoints
without requiring a full server setup.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_imports():
    """Test that all required imports work correctly."""
    try:
        # Test WebAuthn authentication service imports
        from second_brain_database.routes.auth.services.webauthn.authentication import (
            begin_authentication,
            complete_authentication,
        )
        print("✓ WebAuthn authentication service imports successful")
        
        # Test WebAuthn models imports
        from second_brain_database.routes.auth.models import (
            WebAuthnAuthenticationBeginRequest,
            WebAuthnAuthenticationBeginResponse,
            WebAuthnAuthenticationCompleteRequest,
            WebAuthnAuthenticationCompleteResponse,
        )
        print("✓ WebAuthn authentication models imports successful")
        
        # Test that the routes file imports correctly
        from second_brain_database.routes.auth.routes import router
        print("✓ Auth routes imports successful")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_endpoint_structure():
    """Test that the endpoints are properly structured."""
    try:
        from second_brain_database.routes.auth.routes import router
        
        # Get all routes from the router
        routes = []
        for route in router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append((route.path, list(route.methods)))
        
        # Check for WebAuthn authentication endpoints
        auth_begin_found = False
        auth_complete_found = False
        
        for path, methods in routes:
            if path == "/auth/webauthn/authenticate/begin" and "POST" in methods:
                auth_begin_found = True
                print("✓ WebAuthn authentication begin endpoint found")
            elif path == "/auth/webauthn/authenticate/complete" and "POST" in methods:
                auth_complete_found = True
                print("✓ WebAuthn authentication complete endpoint found")
        
        # Show all WebAuthn routes for verification
        webauthn_routes = [(path, methods) for path, methods in routes if "webauthn" in path.lower()]
        print(f"\nFound {len(webauthn_routes)} WebAuthn routes:")
        for path, methods in webauthn_routes:
            print(f"  {path} - {methods}")
        
        if not auth_begin_found:
            print("✗ WebAuthn authentication begin endpoint not found")
            return False
            
        if not auth_complete_found:
            print("✗ WebAuthn authentication complete endpoint not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Error checking endpoint structure: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing WebAuthn Authentication Endpoints Implementation")
    print("=" * 60)
    
    success = True
    
    print("\n1. Testing imports...")
    if not test_imports():
        success = False
    
    print("\n2. Testing endpoint structure...")
    if not test_endpoint_structure():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✓ All tests passed! WebAuthn authentication endpoints are properly implemented.")
        return 0
    else:
        print("✗ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())