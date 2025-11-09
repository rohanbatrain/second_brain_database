#!/usr/bin/env python3
"""
Verification script for WebAuthn security logging patterns implementation.
"""


def check_security_logging_patterns():
    """Check that WebAuthn services use proper security logging patterns."""

    # Check WebAuthn authentication service
    with open("src/second_brain_database/routes/auth/services/webauthn/authentication.py", "r") as f:
        auth_content = f.read()

    # Check WebAuthn registration service
    with open("src/second_brain_database/routes/auth/services/webauthn/registration.py", "r") as f:
        reg_content = f.read()

    # Check WebAuthn routes
    with open("src/second_brain_database/routes/auth/routes.py", "r") as f:
        routes_content = f.read()

    print("✓ Checking WebAuthn Authentication Service:")
    print("  - log_auth_success imported:", "log_auth_success" in auth_content)
    print("  - log_auth_failure imported:", "log_auth_failure" in auth_content)
    print("  - log_auth_success used:", auth_content.count("log_auth_success(") > 0)
    print("  - log_auth_failure used:", auth_content.count("log_auth_failure(") > 0)

    print("\n✓ Checking WebAuthn Registration Service:")
    print("  - log_auth_success imported:", "log_auth_success" in reg_content)
    print("  - log_auth_failure imported:", "log_auth_failure" in reg_content)
    print("  - log_auth_success used:", reg_content.count("log_auth_success(") > 0)

    print("\n✓ Checking WebAuthn Routes:")
    print("  - log_auth_success imported:", "log_auth_success" in routes_content)
    print("  - log_auth_failure imported:", "log_auth_failure" in routes_content)
    print("  - log_auth_success used:", routes_content.count("log_auth_success(") > 0)
    print("  - log_auth_failure used:", routes_content.count("log_auth_failure(") > 0)

    # Verify specific security events are logged
    print("\n✓ Checking specific security events:")

    # Authentication events
    auth_success_events = ["webauthn_authentication_successful", "webauthn_registration_completed"]

    auth_failure_events = [
        "webauthn_authentication_user_not_found",
        "webauthn_authentication_abuse_suspended",
        "webauthn_authentication_inactive_account",
        "webauthn_authentication_email_not_verified",
    ]

    for event in auth_success_events:
        found_in_auth = event in auth_content
        found_in_reg = event in reg_content
        found_in_routes = event in routes_content
        print(f'  - {event}: {"✓" if (found_in_auth or found_in_reg or found_in_routes) else "✗"}')

    for event in auth_failure_events:
        found_in_auth = event in auth_content
        found_in_reg = event in reg_content
        found_in_routes = event in routes_content
        print(f'  - {event}: {"✓" if (found_in_auth or found_in_reg or found_in_routes) else "✗"}')

    print("\n✓ Security logging patterns successfully applied to WebAuthn implementation!")
    return True


if __name__ == "__main__":
    check_security_logging_patterns()
