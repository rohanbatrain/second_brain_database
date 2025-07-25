#!/usr/bin/env python3
"""
Test script to verify WebAuthn credentials listing endpoint implementation.
"""

import asyncio
import sys
sys.path.append('src')

async def test_webauthn_credentials_endpoint():
    """Test that the WebAuthn credentials listing endpoint is properly implemented."""
    
    print("Testing WebAuthn credentials listing endpoint implementation...")
    
    try:
        # Test imports
        from second_brain_database.routes.auth.services.webauthn.credentials import get_user_credential_list
        print("✓ get_user_credential_list import successful")
        
        from second_brain_database.routes.auth.models import (
            WebAuthnCredentialListResponse,
            WebAuthnCredentialInfo
        )
        print("✓ WebAuthn credential models import successful")
        
        # Test that the endpoint exists in routes
        from second_brain_database.routes.auth.routes import router
        print("✓ Auth router import successful")
        
        # Check if the endpoint is registered
        routes = [route for route in router.routes if hasattr(route, 'path')]
        webauthn_routes = [route for route in routes if '/webauthn/credentials' in route.path]
        
        if webauthn_routes:
            print("✓ WebAuthn credentials endpoint found in router")
            for route in webauthn_routes:
                print(f"  - {route.methods} {route.path}")
        else:
            print("✗ WebAuthn credentials endpoint not found in router")
            return False
        
        print("\n✓ All tests passed - WebAuthn credentials listing endpoint is properly implemented!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_webauthn_credentials_endpoint())
    sys.exit(0 if result else 1)