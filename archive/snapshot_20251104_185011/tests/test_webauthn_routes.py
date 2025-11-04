#!/usr/bin/env python3
"""
Simple test to verify WebAuthn routes are properly defined.
"""

import sys
sys.path.append('src')

from second_brain_database.routes.auth.routes import router

def test_routes():
    """Test that WebAuthn routes are defined."""
    routes = [route.path for route in router.routes]
    
    webauthn_routes = [route for route in routes if 'webauthn' in route]
    
    print("WebAuthn routes found:")
    for route in webauthn_routes:
        print(f"  ✓ {route}")
    
    expected_routes = [
        "/auth/webauthn/credentials",
        "/auth/webauthn/credentials/{credential_id}"
    ]
    
    for expected in expected_routes:
        if expected in routes:
            print(f"✓ {expected} route is properly defined")
        else:
            print(f"✗ {expected} route is missing")
    
    print(f"\nTotal WebAuthn routes: {len(webauthn_routes)}")

if __name__ == "__main__":
    test_routes()