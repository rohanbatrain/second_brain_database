#!/usr/bin/env python3
"""
Test to verify that the new "allow once" endpoints are properly registered in the FastAPI app.
"""

import sys

# Add src to path for imports
sys.path.insert(0, "src")

from second_brain_database.main import app


def test_route_registration():
    """Test that the new endpoints are properly registered."""
    print("Testing route registration...")

    # Get all routes from the FastAPI app
    routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            for method in route.methods:
                if method != "HEAD":  # Skip HEAD methods
                    routes.append(f"{method} {route.path}")

    # Check for our new endpoints
    expected_routes = ["POST /auth/lockdown/allow-once/ip", "POST /auth/lockdown/allow-once/user-agent"]

    print("Looking for expected routes:")
    for expected_route in expected_routes:
        print(f"  - {expected_route}")

    print("\nAll registered routes:")
    auth_routes = [route for route in routes if "/auth/" in route]
    for route in sorted(auth_routes):
        print(f"  - {route}")

    print("\nChecking if our endpoints are registered:")
    all_found = True
    for expected_route in expected_routes:
        if expected_route in routes:
            print(f"  ✅ {expected_route} - FOUND")
        else:
            print(f"  ❌ {expected_route} - NOT FOUND")
            all_found = False

    if all_found:
        print("\n✅ All expected routes are properly registered!")
        return True
    else:
        print("\n❌ Some routes are missing!")
        return False


def test_endpoint_functions():
    """Test that the endpoint functions exist and are callable."""
    print("\nTesting endpoint functions...")

    try:
        from second_brain_database.routes.auth.routes import allow_once_ip_access, allow_once_user_agent_access

        print("  ✅ allow_once_ip_access function - FOUND")
        print("  ✅ allow_once_user_agent_access function - FOUND")

        # Check if they're callable
        if callable(allow_once_ip_access):
            print("  ✅ allow_once_ip_access is callable")
        else:
            print("  ❌ allow_once_ip_access is not callable")
            return False

        if callable(allow_once_user_agent_access):
            print("  ✅ allow_once_user_agent_access is callable")
        else:
            print("  ❌ allow_once_user_agent_access is not callable")
            return False

        print("\n✅ All endpoint functions are properly defined!")
        return True

    except ImportError as e:
        print(f"  ❌ Failed to import endpoint functions: {e}")
        return False


def main():
    """Run all tests."""
    print("Starting route registration tests...\n")

    tests = [test_route_registration, test_endpoint_functions]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if test():
                passed += 1
            print()  # Add spacing between tests
        except Exception as e:
            print(f"Test {test.__name__} failed with exception: {e}")
            print()

    print(f"Route Registration Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("All route registration tests PASSED! ✅")
        return 0
    else:
        print("Some route registration tests FAILED! ❌")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
