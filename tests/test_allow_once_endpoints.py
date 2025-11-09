#!/usr/bin/env python3
"""
Test script for the new "allow once" API endpoints.

This script tests the /lockdown/allow-once/ip and /lockdown/allow-once/user-agent endpoints
to ensure they work correctly with token validation and single-use enforcement.
"""

import asyncio
from datetime import datetime, timedelta
import json
import sys

# Add src to path for imports
sys.path.insert(0, "src")

from second_brain_database.routes.auth.services.temporary_access import (
    execute_allow_once_ip_access,
    execute_allow_once_user_agent_access,
    generate_temporary_ip_access_token,
    generate_temporary_user_agent_access_token,
    validate_and_use_temporary_ip_token,
    validate_and_use_temporary_user_agent_token,
)


async def test_ip_allow_once_flow():
    """Test the complete IP allow-once flow."""
    print("Testing IP allow-once flow...")

    # Test data
    user_email = "test@example.com"
    ip_address = "192.168.1.100"
    endpoint = "/api/test"

    try:
        # 1. Generate token
        print("1. Generating temporary IP access token...")
        token = await generate_temporary_ip_access_token(
            user_email=user_email, ip_address=ip_address, action="allow_once", endpoint=endpoint
        )
        print(f"   Generated token: {token[:20]}...")

        # 2. Validate and use token
        print("2. Validating and using token...")
        token_data = await validate_and_use_temporary_ip_token(token)
        if not token_data:
            print("   ERROR: Token validation failed")
            return False

        print(f"   Token data: {json.dumps(token_data, indent=2)}")

        # 3. Verify token data
        if token_data.get("user_email") != user_email:
            print(f"   ERROR: Wrong user email: {token_data.get('user_email')}")
            return False

        if token_data.get("ip_address") != ip_address:
            print(f"   ERROR: Wrong IP address: {token_data.get('ip_address')}")
            return False

        if token_data.get("action") != "allow_once":
            print(f"   ERROR: Wrong action: {token_data.get('action')}")
            return False

        print("   Token validation successful!")

        # 4. Try to use token again (should fail - single use)
        print("3. Testing single-use enforcement...")
        token_data_2 = await validate_and_use_temporary_ip_token(token)
        if token_data_2 is not None:
            print("   ERROR: Token was used twice (should be single-use)")
            return False

        print("   Single-use enforcement working correctly!")

        print("IP allow-once flow test: PASSED\n")
        return True

    except Exception as e:
        print(f"   ERROR: Exception during IP test: {e}")
        return False


async def test_user_agent_allow_once_flow():
    """Test the complete User Agent allow-once flow."""
    print("Testing User Agent allow-once flow...")

    # Test data
    user_email = "test@example.com"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    endpoint = "/api/test"

    try:
        # 1. Generate token
        print("1. Generating temporary User Agent access token...")
        token = await generate_temporary_user_agent_access_token(
            user_email=user_email, user_agent=user_agent, action="allow_once", endpoint=endpoint
        )
        print(f"   Generated token: {token[:20]}...")

        # 2. Validate and use token
        print("2. Validating and using token...")
        token_data = await validate_and_use_temporary_user_agent_token(token)
        if not token_data:
            print("   ERROR: Token validation failed")
            return False

        print(f"   Token data: {json.dumps(token_data, indent=2)}")

        # 3. Verify token data
        if token_data.get("user_email") != user_email:
            print(f"   ERROR: Wrong user email: {token_data.get('user_email')}")
            return False

        if token_data.get("user_agent") != user_agent:
            print(f"   ERROR: Wrong User Agent: {token_data.get('user_agent')}")
            return False

        if token_data.get("action") != "allow_once":
            print(f"   ERROR: Wrong action: {token_data.get('action')}")
            return False

        print("   Token validation successful!")

        # 4. Try to use token again (should fail - single use)
        print("3. Testing single-use enforcement...")
        token_data_2 = await validate_and_use_temporary_user_agent_token(token)
        if token_data_2 is not None:
            print("   ERROR: Token was used twice (should be single-use)")
            return False

        print("   Single-use enforcement working correctly!")

        print("User Agent allow-once flow test: PASSED\n")
        return True

    except Exception as e:
        print(f"   ERROR: Exception during User Agent test: {e}")
        return False


async def test_invalid_token_handling():
    """Test handling of invalid tokens."""
    print("Testing invalid token handling...")

    try:
        # Test invalid IP token
        print("1. Testing invalid IP token...")
        result = await validate_and_use_temporary_ip_token("invalid_token_123")
        if result is not None:
            print("   ERROR: Invalid token should return None")
            return False
        print("   Invalid IP token handled correctly!")

        # Test invalid User Agent token
        print("2. Testing invalid User Agent token...")
        result = await validate_and_use_temporary_user_agent_token("invalid_token_456")
        if result is not None:
            print("   ERROR: Invalid token should return None")
            return False
        print("   Invalid User Agent token handled correctly!")

        print("Invalid token handling test: PASSED\n")
        return True

    except Exception as e:
        print(f"   ERROR: Exception during invalid token test: {e}")
        return False


async def main():
    """Run all tests."""
    print("Starting allow-once endpoints tests...\n")

    tests = [test_ip_allow_once_flow, test_user_agent_allow_once_flow, test_invalid_token_handling]

    passed = 0
    total = len(tests)

    for test in tests:
        try:
            if await test():
                passed += 1
        except Exception as e:
            print(f"Test {test.__name__} failed with exception: {e}")

    print(f"Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("All tests PASSED! ✅")
        return 0
    else:
        print("Some tests FAILED! ❌")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
