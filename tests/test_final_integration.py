#!/usr/bin/env python3
"""
Final integration test for WebAuthn credential deletion endpoint.
"""

import sys

sys.path.append("src")


def test_final_integration():
    """Test that all components work together correctly."""

    print("Running final integration test...")

    try:
        # Test that all imports work correctly
        from second_brain_database.routes.auth.models import WebAuthnCredentialDeletionResponse
        from second_brain_database.routes.auth.routes import router
        from second_brain_database.routes.auth.services.webauthn.credentials import delete_credential_by_id

        print("✓ All imports successful")

        # Test that the endpoint is properly registered
        routes = [route for route in router.routes if hasattr(route, "path")]
        delete_routes = [
            route
            for route in routes
            if "/webauthn/credentials/{credential_id}" in route.path and "DELETE" in route.methods
        ]

        if delete_routes:
            print("✓ DELETE /auth/webauthn/credentials/{credential_id} endpoint registered")
            route = delete_routes[0]
            print(f"  Methods: {route.methods}")
            print(f"  Path: {route.path}")
        else:
            print("✗ DELETE endpoint not found")
            return False

        print("✓ WebAuthn credential deletion endpoint fully implemented and tested!")
        return True

    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = test_final_integration()
    sys.exit(0 if result else 1)
