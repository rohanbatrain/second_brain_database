#!/usr/bin/env python3
"""
Test script to verify the enforce_all_lockdowns dependency function.
"""

import asyncio
import sys

sys.path.append("src")

from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException, Request

from second_brain_database.routes.auth.dependencies import enforce_all_lockdowns


async def test_enforce_all_lockdowns():
    """Test the enforce_all_lockdowns dependency function."""

    # Mock request object
    mock_request = Mock(spec=Request)
    mock_request.method = "GET"
    mock_request.url.path = "/test-endpoint"

    # Mock user document
    mock_user = {
        "_id": "test_user_id",
        "username": "testuser",
        "email": "test@example.com",
        "trusted_ip_lockdown": False,
        "trusted_user_agent_lockdown": False,
    }

    print("Testing enforce_all_lockdowns function...")

    # Test 1: Both lockdowns disabled (should pass)
    print("\n1. Testing with both lockdowns disabled...")
    with (
        patch("second_brain_database.routes.auth.dependencies.enforce_ip_lockdown") as mock_ip_lockdown,
        patch("second_brain_database.routes.auth.dependencies.enforce_user_agent_lockdown") as mock_ua_lockdown,
    ):

        mock_ip_lockdown.return_value = mock_user
        mock_ua_lockdown.return_value = mock_user

        result = await enforce_all_lockdowns(mock_request, mock_user)

        assert result == mock_user
        assert mock_ip_lockdown.called
        assert mock_ua_lockdown.called
        print("✅ Both lockdowns disabled - PASSED")

    # Test 2: IP lockdown blocks request
    print("\n2. Testing IP lockdown blocking request...")
    with (
        patch("second_brain_database.routes.auth.dependencies.enforce_ip_lockdown") as mock_ip_lockdown,
        patch("second_brain_database.routes.auth.dependencies.enforce_user_agent_lockdown") as mock_ua_lockdown,
    ):

        mock_ip_lockdown.side_effect = HTTPException(status_code=403, detail="IP blocked")

        try:
            await enforce_all_lockdowns(mock_request, mock_user)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
            assert "IP blocked" in e.detail
            assert mock_ip_lockdown.called
            assert not mock_ua_lockdown.called  # Should not reach User Agent check
            print("✅ IP lockdown blocking - PASSED")

    # Test 3: User Agent lockdown blocks request
    print("\n3. Testing User Agent lockdown blocking request...")
    with (
        patch("second_brain_database.routes.auth.dependencies.enforce_ip_lockdown") as mock_ip_lockdown,
        patch("second_brain_database.routes.auth.dependencies.enforce_user_agent_lockdown") as mock_ua_lockdown,
    ):

        mock_ip_lockdown.return_value = mock_user  # IP check passes
        mock_ua_lockdown.side_effect = HTTPException(status_code=403, detail="User Agent blocked")

        try:
            await enforce_all_lockdowns(mock_request, mock_user)
            assert False, "Should have raised HTTPException"
        except HTTPException as e:
            assert e.status_code == 403
            assert "User Agent blocked" in e.detail
            assert mock_ip_lockdown.called
            assert mock_ua_lockdown.called
            print("✅ User Agent lockdown blocking - PASSED")

    print("\n🎉 All tests passed! The enforce_all_lockdowns function works correctly.")


if __name__ == "__main__":
    asyncio.run(test_enforce_all_lockdowns())
