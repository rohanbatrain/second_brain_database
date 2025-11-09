#!/usr/bin/env python3
"""
Integration test for User Agent lockdown confirmation endpoint.
"""

import asyncio
from datetime import datetime, timedelta
import sys
from unittest.mock import AsyncMock, MagicMock, patch


async def test_confirmation_endpoint():
    """Test the User Agent lockdown confirmation endpoint."""

    print("Running User Agent lockdown confirmation endpoint integration test...")

    try:
        # Import the endpoint function
        from src.second_brain_database.routes.auth.routes import trusted_user_agents_lockdown_confirm

        print("✅ Successfully imported User Agent lockdown confirmation endpoint")

        # Mock dependencies
        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "Mozilla/5.0 (Test Browser)"}

        test_code = "test_code_123"
        test_user_agents = ["Mozilla/5.0 (Test Browser)", "Chrome/91.0"]

        # Test enable confirmation
        print("\n--- Testing enable confirmation ---")

        mock_current_user = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "trusted_user_agent_lockdown": False,
            "trusted_user_agents": [],
            "trusted_user_agent_lockdown_codes": [
                {
                    "code": test_code,
                    "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
                    "action": "enable",
                    "allowed_user_agents": test_user_agents,
                }
            ],
        }

        with patch("src.second_brain_database.routes.auth.routes.security_manager") as mock_security_manager:
            mock_security_manager.check_rate_limit = AsyncMock()
            mock_security_manager.get_client_user_agent.return_value = "Mozilla/5.0 (Test Browser)"

            with patch("src.second_brain_database.routes.auth.routes.db_manager") as mock_db_manager:
                mock_collection = AsyncMock()
                mock_collection.find_one = AsyncMock(return_value=mock_current_user)
                mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
                mock_db_manager.get_collection.return_value = mock_collection

                result = await trusted_user_agents_lockdown_confirm(
                    request=mock_request, code=test_code, current_user=mock_current_user
                )

                print("✅ Enable confirmation completed successfully")
                print(f"Result: {result}")

                # Verify database update was called
                assert mock_collection.update_one.called
                update_call = mock_collection.update_one.call_args
                update_data = update_call[0][1]["$set"]

                # Check that lockdown was enabled and trusted User Agents were set
                assert update_data["trusted_user_agent_lockdown"] == True
                assert update_data["trusted_user_agents"] == test_user_agents

                print("✅ Database update verified for enable action")

        # Test disable confirmation
        print("\n--- Testing disable confirmation ---")

        mock_current_user_with_lockdown = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "trusted_user_agent_lockdown": True,
            "trusted_user_agents": test_user_agents,
            "trusted_user_agent_lockdown_codes": [
                {
                    "code": test_code,
                    "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat(),
                    "action": "disable",
                    "allowed_user_agents": test_user_agents,
                }
            ],
        }

        with patch("src.second_brain_database.routes.auth.routes.security_manager") as mock_security_manager:
            mock_security_manager.check_rate_limit = AsyncMock()
            mock_security_manager.get_client_user_agent.return_value = "Mozilla/5.0 (Test Browser)"

            with patch("src.second_brain_database.routes.auth.routes.db_manager") as mock_db_manager:
                mock_collection = AsyncMock()
                mock_collection.find_one = AsyncMock(return_value=mock_current_user_with_lockdown)
                mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
                mock_db_manager.get_collection.return_value = mock_collection

                result = await trusted_user_agents_lockdown_confirm(
                    request=mock_request, code=test_code, current_user=mock_current_user_with_lockdown
                )

                print("✅ Disable confirmation completed successfully")
                print(f"Result: {result}")

                # Verify database update was called
                assert mock_collection.update_one.called
                update_call = mock_collection.update_one.call_args
                update_data = update_call[0][1]["$set"]

                # Check that lockdown was disabled
                assert update_data["trusted_user_agent_lockdown"] == False

                print("✅ Database update verified for disable action")

        print("\n✅ All User Agent lockdown confirmation tests passed!")
        return True

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_error_cases():
    """Test error cases for the confirmation endpoint."""

    print("\n--- Testing error cases ---")

    try:
        from fastapi import HTTPException
        from src.second_brain_database.routes.auth.routes import trusted_user_agents_lockdown_confirm

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "Mozilla/5.0 (Test Browser)"}

        # Test no pending codes
        print("Testing no pending codes...")
        mock_current_user = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "trusted_user_agent_lockdown": False,
            "trusted_user_agents": [],
        }

        with patch("src.second_brain_database.routes.auth.routes.security_manager") as mock_security_manager:
            mock_security_manager.check_rate_limit = AsyncMock()
            mock_security_manager.get_client_user_agent.return_value = "Mozilla/5.0 (Test Browser)"

            with patch("src.second_brain_database.routes.auth.routes.db_manager") as mock_db_manager:
                mock_collection = AsyncMock()
                mock_collection.find_one = AsyncMock(return_value=mock_current_user)
                mock_db_manager.get_collection.return_value = mock_collection

                try:
                    await trusted_user_agents_lockdown_confirm(
                        request=mock_request, code="invalid_code", current_user=mock_current_user
                    )
                    assert False, "Should have raised HTTPException"
                except HTTPException as e:
                    assert e.status_code == 400
                    assert "No pending User Agent lockdown action" in str(e.detail)
                    print("✅ No pending codes error handled correctly")

        # Test expired code
        print("Testing expired code...")
        mock_current_user_expired = {
            "_id": "test_user_id",
            "username": "testuser",
            "email": "test@example.com",
            "trusted_user_agent_lockdown": False,
            "trusted_user_agents": [],
            "trusted_user_agent_lockdown_codes": [
                {
                    "code": "test_code",
                    "expires_at": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),  # Expired
                    "action": "enable",
                    "allowed_user_agents": ["Mozilla/5.0 (Test Browser)"],
                }
            ],
        }

        with patch("src.second_brain_database.routes.auth.routes.security_manager") as mock_security_manager:
            mock_security_manager.check_rate_limit = AsyncMock()
            mock_security_manager.get_client_user_agent.return_value = "Mozilla/5.0 (Test Browser)"

            with patch("src.second_brain_database.routes.auth.routes.db_manager") as mock_db_manager:
                mock_collection = AsyncMock()
                mock_collection.find_one = AsyncMock(return_value=mock_current_user_expired)
                mock_db_manager.get_collection.return_value = mock_collection

                try:
                    await trusted_user_agents_lockdown_confirm(
                        request=mock_request, code="test_code", current_user=mock_current_user_expired
                    )
                    assert False, "Should have raised HTTPException"
                except HTTPException as e:
                    assert e.status_code == 400
                    assert "Code expired" in str(e.detail)
                    print("✅ Expired code error handled correctly")

        print("✅ All error cases handled correctly!")
        return True

    except Exception as e:
        print(f"❌ Error case test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 60)
    print("User Agent Lockdown Confirmation Endpoint Test Suite")
    print("=" * 60)

    success1 = await test_confirmation_endpoint()
    success2 = await test_error_cases()

    if success1 and success2:
        print("\n🎉 All tests passed successfully!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
