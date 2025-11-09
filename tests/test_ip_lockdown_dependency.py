#!/usr/bin/env python3
"""
Test script for IP lockdown dependency functionality.
"""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

# Add the src directory to the path
sys.path.insert(0, "src")

from fastapi import HTTPException, Request

from second_brain_database.routes.auth.dependencies import enforce_ip_lockdown


async def test_ip_lockdown_dependency():
    """Test the IP lockdown dependency function."""
    print("Testing IP lockdown dependency...")

    # Mock request object
    mock_request = MagicMock(spec=Request)
    mock_request.client.host = "192.168.1.100"
    mock_request.headers = {"user-agent": "test-browser"}
    mock_request.method = "GET"
    mock_request.url.path = "/test/endpoint"

    # Test case 1: User without IP lockdown enabled
    print("\n1. Testing user without IP lockdown enabled...")
    user_no_lockdown = {
        "_id": "test_user_1",
        "username": "testuser1",
        "email": "test1@example.com",
        "trusted_ip_lockdown": False,
        "trusted_ips": [],
    }

    try:
        result = await enforce_ip_lockdown(mock_request, user_no_lockdown)
        print("✓ User without IP lockdown passed through successfully")
        assert result == user_no_lockdown
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

    # Test case 2: User with IP lockdown enabled and trusted IP
    print("\n2. Testing user with IP lockdown enabled and trusted IP...")
    user_trusted_ip = {
        "_id": "test_user_2",
        "username": "testuser2",
        "email": "test2@example.com",
        "trusted_ip_lockdown": True,
        "trusted_ips": ["192.168.1.100", "10.0.0.1"],
    }

    try:
        result = await enforce_ip_lockdown(mock_request, user_trusted_ip)
        print("✓ User with trusted IP passed through successfully")
        assert result == user_trusted_ip
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

    # Test case 3: User with IP lockdown enabled and untrusted IP
    print("\n3. Testing user with IP lockdown enabled and untrusted IP...")
    user_untrusted_ip = {
        "_id": "test_user_3",
        "username": "testuser3",
        "email": "test3@example.com",
        "trusted_ip_lockdown": True,
        "trusted_ips": ["10.0.0.1", "172.16.0.1"],  # Different IPs
    }

    try:
        result = await enforce_ip_lockdown(mock_request, user_untrusted_ip)
        print("✗ Expected HTTPException but function returned successfully")
        return False
    except HTTPException as e:
        if e.status_code == 403:
            print("✓ Correctly blocked untrusted IP with 403 status")
        else:
            print(f"✗ Wrong status code: {e.status_code}, expected 403")
            return False
    except Exception as e:
        print(f"✗ Unexpected error type: {e}")
        return False

    print("\n✓ All IP lockdown dependency tests passed!")
    return True


async def main():
    """Run the test."""
    try:
        success = await test_ip_lockdown_dependency()
        if success:
            print("\n🎉 All tests passed!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
