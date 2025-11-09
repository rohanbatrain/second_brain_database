"""
Test family security integration with existing SecurityManager.

This test verifies that family operations correctly use the existing
SecurityManager instead of a redundant FamilySecurityManager.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, Request
import pytest

from second_brain_database.routes.family.dependencies import (
    _get_family_rate_limits,
    enforce_family_security,
    get_current_family_user,
)


class TestFamilySecurityIntegration:
    """Test family security integration with existing SecurityManager."""

    def test_get_family_rate_limits(self):
        """Test that family rate limits are properly configured."""
        # Test specific operations
        create_limits = _get_family_rate_limits("create_family")
        assert create_limits["requests"] == 2
        assert create_limits["period"] == 3600

        invite_limits = _get_family_rate_limits("invite_member")
        assert invite_limits["requests"] == 10
        assert invite_limits["period"] == 3600

        # Test default limits
        default_limits = _get_family_rate_limits("unknown_operation")
        assert default_limits["requests"] == 20
        assert default_limits["period"] == 3600

    @pytest.mark.asyncio
    async def test_enforce_family_security_uses_existing_security_manager(self):
        """Test that enforce_family_security uses the existing SecurityManager."""
        # Mock request and user
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/family/create"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {"user-agent": "test-agent"}

        mock_user = {"_id": "test_user_id", "username": "testuser", "is_verified": True}

        # Mock the security manager methods
        with patch("second_brain_database.routes.family.dependencies.security_manager") as mock_security_manager:
            mock_security_manager.check_ip_lockdown = AsyncMock()
            mock_security_manager.check_user_agent_lockdown = AsyncMock()
            mock_security_manager.check_rate_limit = AsyncMock()
            mock_security_manager.get_client_ip.return_value = "127.0.0.1"
            mock_security_manager.get_client_user_agent.return_value = "test-agent"

            # Mock log_security_event
            with patch("second_brain_database.routes.family.dependencies.log_security_event") as mock_log:
                # Call the function
                result = await enforce_family_security(
                    request=mock_request,
                    operation="create_family",
                    require_2fa=False,
                    x_temp_token=None,
                    current_user=mock_user,
                )

                # Verify SecurityManager methods were called
                mock_security_manager.check_ip_lockdown.assert_called_once_with(mock_request, mock_user)
                mock_security_manager.check_user_agent_lockdown.assert_called_once_with(mock_request, mock_user)
                mock_security_manager.check_rate_limit.assert_called_once_with(
                    request=mock_request,
                    action="family_create_family",
                    rate_limit_requests=2,  # create_family specific limit
                    rate_limit_period=3600,
                )

                # Verify security event was logged
                mock_log.assert_called_once()
                log_call_args = mock_log.call_args[1]
                assert log_call_args["event_type"] == "family_security_check_create_family"
                assert log_call_args["user_id"] == "test_user_id"
                assert log_call_args["success"] is True

                # Verify result structure
                assert result["security_validated"] is True
                assert result["operation"] == "create_family"
                assert result["2fa_required"] is True  # create_family is in SENSITIVE_FAMILY_OPERATIONS

    @pytest.mark.asyncio
    async def test_enforce_family_security_handles_rate_limit_exception(self):
        """Test that rate limit exceptions are properly handled."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "POST"
        mock_request.url.path = "/family/invite"
        mock_request.client.host = "192.168.1.1"

        mock_user = {"_id": "test_user_id", "username": "testuser"}

        # Mock security manager to raise rate limit exception
        with patch("second_brain_database.routes.family.dependencies.security_manager") as mock_security_manager:
            mock_security_manager.check_ip_lockdown = AsyncMock()
            mock_security_manager.check_user_agent_lockdown = AsyncMock()
            mock_security_manager.check_rate_limit = AsyncMock(
                side_effect=HTTPException(status_code=429, detail="Rate limit exceeded")
            )

            # Should re-raise the HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await enforce_family_security(
                    request=mock_request,
                    operation="invite_member",
                    require_2fa=False,
                    x_temp_token=None,
                    current_user=mock_user,
                )

            assert exc_info.value.status_code == 429
            assert "Rate limit exceeded" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_family_user_logs_security_event(self):
        """Test that get_current_family_user logs security events."""
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.url.path = "/family/list"
        mock_request.client.host = "127.0.0.1"

        mock_user = {"_id": "test_user_id", "username": "testuser", "role": "user", "is_verified": True}

        with patch("second_brain_database.routes.family.dependencies.log_security_event") as mock_log:
            result = await get_current_family_user(request=mock_request, current_user=mock_user)

            # Verify security event was logged
            mock_log.assert_called_once()
            log_call_args = mock_log.call_args[1]
            assert log_call_args["event_type"] == "family_access"
            assert log_call_args["user_id"] == "test_user_id"
            assert log_call_args["success"] is True

            # Verify user is returned unchanged
            assert result == mock_user


if __name__ == "__main__":
    pytest.main([__file__])
