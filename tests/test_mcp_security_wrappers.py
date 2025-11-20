#!/usr/bin/env python3
"""
Unit tests for MCP security wrappers.

Tests authentication, authorization, rate limiting, and audit logging
functionality in the MCP security system.
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from second_brain_database.integrations.mcp.context import (
    MCPRequestContext,
    MCPUserContext,
    clear_mcp_context,
    create_mcp_request_context,
    create_mcp_user_context_from_fastapi_user,
    get_mcp_request_context,
    get_mcp_user_context,
    set_mcp_request_context,
    set_mcp_user_context,
)
from second_brain_database.integrations.mcp.exceptions import (
    MCPAuthenticationError,
    MCPAuthorizationError,
    MCPRateLimitError,
)

# Test imports
from second_brain_database.integrations.mcp.security import (
    MCPRateLimitInfo,
    authenticated_tool,
    check_mcp_rate_limit_status,
    log_mcp_authentication_event,
    log_mcp_authorization_event,
    log_mcp_security_event,
    mcp_audit_logger,
    mcp_context_manager,
    reset_mcp_rate_limit,
    secure_mcp_tool,
)


class TestMCPSecurityWrappers:
    """Test MCP security wrapper functionality."""

    @pytest.fixture
    def mock_user_context(self):
        """Create a mock user context for testing."""
        return MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            email="test@example.com",
            role="user",
            permissions=["family:read", "profile:read"],
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
            token_type="jwt",
            token_id="token_123",
        )

    @pytest.fixture
    def mock_request_context(self):
        """Create a mock request context for testing."""
        return create_mcp_request_context(operation_type="tool", tool_name="test_tool", parameters={"param1": "value1"})

    @pytest.fixture
    def mock_admin_context(self):
        """Create a mock admin user context for testing."""
        return MCPUserContext(
            user_id="admin_user_123",
            username="admin_user",
            email="admin@example.com",
            role="admin",
            permissions=["admin", "family:read", "family:write"],
            ip_address="127.0.0.1",
            user_agent="AdminClient/1.0",
            token_type="jwt",
            token_id="admin_token_123",
        )

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_secure_mcp_tool_with_valid_user(self, mock_user_context):
        """Test secure_mcp_tool decorator with valid authenticated user."""
        set_mcp_user_context(mock_user_context)

        @secure_mcp_tool(permissions=["family:read"], audit=True)
        async def test_tool():
            return {"result": "success"}

        result = await test_tool()
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_secure_mcp_tool_without_authentication(self):
        """Test secure_mcp_tool decorator without authentication."""

        @secure_mcp_tool(permissions=["family:read"])
        async def test_tool():
            return {"result": "success"}

        with pytest.raises(MCPAuthenticationError) as exc_info:
            await test_tool()

        assert "authentication required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_secure_mcp_tool_insufficient_permissions(self, mock_user_context):
        """Test secure_mcp_tool decorator with insufficient permissions."""
        set_mcp_user_context(mock_user_context)

        @secure_mcp_tool(permissions=["admin", "family:write"])
        async def test_tool():
            return {"result": "success"}

        with pytest.raises(MCPAuthorizationError) as exc_info:
            await test_tool()

        assert "Missing required permissions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_secure_mcp_tool_admin_bypass(self, mock_admin_context):
        """Test that admin users can bypass permission checks."""
        set_mcp_user_context(mock_admin_context)

        @secure_mcp_tool(permissions=["any:permission"])
        async def test_tool():
            return {"result": "admin_success"}

        result = await test_tool()
        assert result == {"result": "admin_success"}

    @pytest.mark.asyncio
    async def test_authenticated_tool_decorator(self, mock_user_context):
        """Test authenticated_tool decorator functionality."""
        set_mcp_user_context(mock_user_context)

        @authenticated_tool(
            name="test_authenticated_tool", description="Test tool with authentication", permissions=["family:read"]
        )
        async def test_tool():
            return {"authenticated": True}

        # Check that metadata is set correctly
        assert test_tool._mcp_tool_name == "test_authenticated_tool"
        assert test_tool._mcp_tool_description == "Test tool with authentication"
        assert test_tool._mcp_tool_permissions == ["family:read"]

        result = await test_tool()
        assert result == {"authenticated": True}

    @pytest.mark.asyncio
    async def test_mcp_context_manager_decorator(self, mock_user_context, mock_request_context):
        """Test mcp_context_manager decorator."""
        set_mcp_user_context(mock_user_context)
        set_mcp_request_context(mock_request_context)

        @mcp_context_manager(operation_type="tool")
        async def test_operation():
            return {"context_managed": True}

        result = await test_operation()
        assert result == {"context_managed": True}

        # Check that request context was updated
        request_context = get_mcp_request_context()
        assert request_context.security_checks_passed is True

    @pytest.mark.asyncio
    async def test_mcp_context_manager_with_error(self, mock_user_context):
        """Test mcp_context_manager decorator with error handling."""
        set_mcp_user_context(mock_user_context)

        request_context = create_mcp_request_context(operation_type="tool", tool_name="error_tool")
        set_mcp_request_context(request_context)

        @mcp_context_manager(operation_type="tool")
        async def error_operation():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await error_operation()

        # Check that error was recorded in context
        updated_context = get_mcp_request_context()
        assert updated_context.error_occurred is True
        assert updated_context.error_type == "ValueError"
        assert updated_context.error_message == "Test error"

    @pytest.mark.asyncio
    @patch("src.second_brain_database.integrations.mcp.security.security_manager")
    async def test_rate_limiting_success(self, mock_security_manager, mock_user_context):
        """Test successful rate limiting check."""
        set_mcp_user_context(mock_user_context)

        # Mock successful rate limit check
        mock_security_manager.check_rate_limit = AsyncMock()

        @secure_mcp_tool(rate_limit_action="test_action")
        async def test_tool():
            return {"rate_limited": False}

        result = await test_tool()
        assert result == {"rate_limited": False}

        # Verify rate limit was checked
        mock_security_manager.check_rate_limit.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.second_brain_database.integrations.mcp.security.security_manager")
    async def test_rate_limiting_exceeded(self, mock_security_manager, mock_user_context):
        """Test rate limiting when limit is exceeded."""
        from fastapi import HTTPException

        set_mcp_user_context(mock_user_context)

        # Mock rate limit exceeded
        mock_security_manager.check_rate_limit = AsyncMock(
            side_effect=HTTPException(status_code=429, detail="Rate limit exceeded")
        )

        @secure_mcp_tool(rate_limit_action="test_action")
        async def test_tool():
            return {"should_not_reach": True}

        with pytest.raises(MCPRateLimitError) as exc_info:
            await test_tool()

        assert "Rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_check_mcp_rate_limit_status(self, mock_user_context, mock_settings):
        """Test checking MCP rate limit status."""
        with (
            patch("src.second_brain_database.managers.redis_manager.redis_manager") as mock_redis,
            patch("src.second_brain_database.integrations.mcp.security.settings", mock_settings),
        ):
            mock_redis_conn = AsyncMock()
            mock_redis.get_redis = AsyncMock(return_value=mock_redis_conn)
            mock_redis_conn.get = AsyncMock(return_value="5")  # Current count
            mock_redis_conn.ttl = AsyncMock(return_value=30)  # TTL in seconds

            status = await check_mcp_rate_limit_status(mock_user_context, "test_action")

            assert status["action"] == "test_action"
            assert status["current_count"] == 5
            assert status["reset_in_seconds"] == 30
            assert "remaining" in status
            assert "limit" in status

    @pytest.mark.asyncio
    async def test_reset_mcp_rate_limit_admin(self, mock_admin_context, mock_settings):
        """Test resetting rate limit as admin."""
        with (
            patch("src.second_brain_database.managers.redis_manager.redis_manager") as mock_redis,
            patch("src.second_brain_database.integrations.mcp.security.settings", mock_settings),
        ):
            mock_redis_conn = AsyncMock()
            mock_redis.get_redis = AsyncMock(return_value=mock_redis_conn)
            mock_redis_conn.delete = AsyncMock(return_value=2)  # Deleted keys count

            result = await reset_mcp_rate_limit(mock_admin_context, "test_action")

            assert result is True
            mock_redis_conn.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_mcp_rate_limit_non_admin(self, mock_user_context):
        """Test resetting rate limit as non-admin user."""
        result = await reset_mcp_rate_limit(mock_user_context, "test_action")
        assert result is False

    def test_mcp_rate_limit_info_class(self):
        """Test MCPRateLimitInfo class functionality."""
        rate_info = MCPRateLimitInfo(
            action="test_action", limit=100, remaining=25, reset_time=1234567890, current_count=75
        )

        assert rate_info.action == "test_action"
        assert rate_info.limit == 100
        assert rate_info.remaining == 25
        assert rate_info.current_count == 75
        assert rate_info.is_exceeded is False
        assert rate_info.usage_percentage == 0.75

        # Test exceeded state
        rate_info.remaining = 0
        assert rate_info.is_exceeded is True

        # Test dictionary conversion
        rate_dict = rate_info.to_dict()
        assert rate_dict["action"] == "test_action"
        assert rate_dict["is_exceeded"] is True
        assert rate_dict["usage_percentage"] == 0.75

    @pytest.mark.asyncio
    async def test_log_mcp_security_event(self, mock_user_context):
        """Test MCP security event logging."""
        with patch("src.second_brain_database.utils.logging_utils.log_security_event") as mock_log:
            await log_mcp_security_event(
                event_type="test_event",
                user_context=mock_user_context,
                success=True,
                additional_details={"test": "data"},
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]["event_type"] == "test_event"
            assert call_args[1]["user_id"] == mock_user_context.user_id
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_log_mcp_authentication_event(self, mock_user_context):
        """Test MCP authentication event logging."""
        with patch("src.second_brain_database.integrations.mcp.security.log_mcp_security_event") as mock_log:
            await log_mcp_authentication_event(
                user_context=mock_user_context, success=True, authentication_method="jwt"
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]["event_type"] == "mcp_authentication"
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_log_mcp_authorization_event(self, mock_user_context):
        """Test MCP authorization event logging."""
        with patch("src.second_brain_database.integrations.mcp.security.log_mcp_security_event") as mock_log:
            await log_mcp_authorization_event(
                user_context=mock_user_context, required_permissions=["family:read"], success=True, resource="test_tool"
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]["event_type"] == "mcp_authorization"
            assert call_args[1]["success"] is True

    @pytest.mark.asyncio
    async def test_mcp_audit_logger_tool_execution(self, mock_user_context):
        """Test MCP audit logger tool execution logging."""
        with patch("src.second_brain_database.integrations.mcp.security._log_mcp_tool_execution") as mock_log:
            await mcp_audit_logger.log_tool_execution(
                tool_name="test_tool",
                user_context=mock_user_context,
                parameters={"param1": "value1"},
                result={"success": True},
                duration_ms=150.5,
            )

            mock_log.assert_called_once()

    @pytest.mark.asyncio
    async def test_mcp_audit_logger_resource_access(self, mock_user_context):
        """Test MCP audit logger resource access logging."""
        with patch("src.second_brain_database.integrations.mcp.security.log_mcp_security_event") as mock_log:
            await mcp_audit_logger.log_resource_access(
                resource_uri="family://123/info", user_context=mock_user_context, access_type="read", success=True
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]["event_type"] == "mcp_resource_access"

    @pytest.mark.asyncio
    async def test_mcp_audit_logger_prompt_generation(self, mock_user_context):
        """Test MCP audit logger prompt generation logging."""
        with patch("src.second_brain_database.integrations.mcp.security.log_mcp_security_event") as mock_log:
            await mcp_audit_logger.log_prompt_generation(
                prompt_name="family_management_guide",
                user_context=mock_user_context,
                parameters={"context": "help"},
                success=True,
            )

            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]["event_type"] == "mcp_prompt_generation"

    @pytest.mark.asyncio
    async def test_security_wrapper_with_tool_execution_error(self, mock_user_context):
        """Test security wrapper behavior when tool execution fails."""
        set_mcp_user_context(mock_user_context)

        @secure_mcp_tool(permissions=["family:read"], audit=True)
        async def failing_tool():
            raise ValueError("Tool execution failed")

        with pytest.raises(ValueError) as exc_info:
            await failing_tool()

        assert "Tool execution failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_permission_validation_edge_cases(self, mock_user_context):
        """Test permission validation edge cases."""
        # Test with empty permissions list
        set_mcp_user_context(mock_user_context)

        @secure_mcp_tool(permissions=[])
        async def no_permissions_tool():
            return {"no_permissions": True}

        result = await no_permissions_tool()
        assert result == {"no_permissions": True}

        # Test with None permissions
        @secure_mcp_tool(permissions=None)
        async def none_permissions_tool():
            return {"none_permissions": True}

        result = await none_permissions_tool()
        assert result == {"none_permissions": True}

    @pytest.mark.asyncio
    async def test_audit_disabled(self, mock_user_context):
        """Test security wrapper with audit disabled."""
        set_mcp_user_context(mock_user_context)

        @secure_mcp_tool(audit=False)
        async def no_audit_tool():
            return {"audit_disabled": True}

        with patch("src.second_brain_database.integrations.mcp.security._log_mcp_tool_execution") as mock_log:
            result = await no_audit_tool()
            assert result == {"audit_disabled": True}
            mock_log.assert_not_called()


class TestMCPSecurityIntegration:
    """Integration tests for MCP security components."""

    @pytest.mark.asyncio
    async def test_full_security_flow(self):
        """Test complete security flow from authentication to audit."""
        # Create user context
        fastapi_user = {
            "_id": "test_user_123",
            "username": "test_user",
            "email": "test@example.com",
            "role": "user",
            "permissions": ["family:read", "profile:read"],
        }

        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=fastapi_user, ip_address="127.0.0.1", user_agent="TestClient/1.0", token_type="jwt"
        )

        # Create request context
        request_context = create_mcp_request_context(operation_type="tool", tool_name="integration_test_tool")

        # Set contexts
        set_mcp_user_context(user_context)
        set_mcp_request_context(request_context)

        # Test secured tool execution
        @secure_mcp_tool(permissions=["family:read"], audit=True)
        async def integration_tool():
            return {"integration": "success"}

        result = await integration_tool()
        assert result == {"integration": "success"}

        # Verify context was properly maintained
        final_user_context = get_mcp_user_context()
        final_request_context = get_mcp_request_context()

        assert final_user_context.user_id == "test_user_123"
        assert final_request_context.tool_name == "integration_test_tool"
        # Note: security_checks_passed is set by mcp_context_manager, not secure_mcp_tool

    @pytest.mark.asyncio
    async def test_concurrent_security_operations(self):
        """Test security wrappers under concurrent execution."""

        async def create_and_execute_tool(user_id: str, permissions: List[str]):
            # Create unique context for each concurrent operation
            user_context = MCPUserContext(
                user_id=user_id,
                username=f"user_{user_id}",
                permissions=permissions,
                ip_address="127.0.0.1",
                user_agent="ConcurrentClient/1.0",
            )

            request_context = create_mcp_request_context(operation_type="tool", tool_name=f"concurrent_tool_{user_id}")

            set_mcp_user_context(user_context)
            set_mcp_request_context(request_context)

            @secure_mcp_tool(permissions=permissions[:1] if permissions else [])
            async def concurrent_tool():
                # Simulate some work
                await asyncio.sleep(0.01)
                return {"user_id": user_id, "success": True}

            return await concurrent_tool()

        # Execute multiple concurrent operations
        tasks = [
            create_and_execute_tool("user_1", ["family:read"]),
            create_and_execute_tool("user_2", ["profile:read"]),
            create_and_execute_tool("user_3", ["family:read", "family:write"]),
        ]

        results = await asyncio.gather(*tasks)

        # Verify all operations completed successfully
        assert len(results) == 3
        for i, result in enumerate(results, 1):
            assert result["user_id"] == f"user_{i}"
            assert result["success"] is True


class TestMCPSecurityEdgeCases:
    """Test edge cases and error scenarios for MCP security."""

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_secure_tool_with_malformed_context(self):
        """Test secure tool behavior with malformed user context."""
        # Create a malformed context (missing required fields)
        malformed_context = MCPUserContext(
            user_id="",  # Empty user ID
            username="test_user",
            permissions=["family:read"],
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )
        set_mcp_user_context(malformed_context)

        @secure_mcp_tool(permissions=["family:read"])
        async def test_tool():
            return {"result": "success"}

        with pytest.raises(MCPAuthenticationError):
            await test_tool()

    @pytest.mark.asyncio
    async def test_secure_tool_with_none_permissions(self):
        """Test secure tool with None permissions in user context."""
        context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=None,  # None permissions
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )
        set_mcp_user_context(context)

        @secure_mcp_tool(permissions=["family:read"])
        async def test_tool():
            return {"result": "success"}

        with pytest.raises(MCPAuthorizationError):
            await test_tool()

    @pytest.mark.asyncio
    async def test_rate_limiting_with_invalid_ip(self):
        """Test rate limiting with invalid IP address."""
        context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=["family:read"],
            ip_address=None,  # No IP address
            user_agent="TestClient/1.0",
        )
        set_mcp_user_context(context)

        # Test that tool executes successfully even with None IP
        @secure_mcp_tool(rate_limit_action="test_action")
        async def test_tool():
            return {"result": "success"}

        result = await test_tool()
        assert result == {"result": "success"}

        # Verify context has None IP but tool still works
        current_context = get_mcp_user_context()
        assert current_context.ip_address is None

    @pytest.mark.asyncio
    async def test_audit_logging_with_sensitive_data(self):
        """Test audit logging properly sanitizes sensitive data."""
        context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=["family:read"],
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )
        set_mcp_user_context(context)

        # Test the sanitization function directly
        from src.second_brain_database.integrations.mcp.security import _sanitize_arguments_for_logging

        test_data = {
            "password": "secret123",
            "token": "jwt_token",
            "normal_param": "value",
            "nested": {"secret": "hidden_value", "public": "visible_value"},
        }

        sanitized = _sanitize_arguments_for_logging(test_data)

        # Sensitive fields should be redacted
        assert sanitized["password"] == "<REDACTED>"
        assert sanitized["token"] == "<REDACTED>"
        assert sanitized["nested"]["secret"] == "<REDACTED>"

        # Normal fields should be preserved
        assert sanitized["normal_param"] == "value"
        assert sanitized["nested"]["public"] == "visible_value"

    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(self):
        """Test concurrent tool execution with security wrappers."""
        context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=["family:read"],
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )

        async def create_concurrent_tool(tool_id: int):
            set_mcp_user_context(context)

            @secure_mcp_tool(permissions=["family:read"])
            async def concurrent_tool():
                await asyncio.sleep(0.01)  # Simulate work
                return {"tool_id": tool_id, "success": True}

            return await concurrent_tool()

        # Execute multiple tools concurrently
        tasks = [create_concurrent_tool(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result["tool_id"] == i
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_error_handling_in_security_wrapper(self):
        """Test error handling within security wrapper itself."""
        context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=["family:read"],
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )
        set_mcp_user_context(context)

        # Mock rate limiting to raise an unexpected error
        with patch("src.second_brain_database.managers.security_manager.security_manager") as mock_security:
            mock_security.check_rate_limit = AsyncMock(side_effect=Exception("Unexpected error"))

            @secure_mcp_tool(rate_limit_action="error_test")
            async def test_tool():
                return {"result": "success"}

            # Should still execute the tool (rate limiting errors are logged but don't block)
            result = await test_tool()
            assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_permission_validation_with_complex_permissions(self):
        """Test permission validation with complex permission structures."""
        context = MCPUserContext(
            user_id="test_user_123",
            username="test_user",
            permissions=["family:read", "family:write", "profile:read", "workspace:member"],
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )
        set_mcp_user_context(context)

        # Test with multiple required permissions
        @secure_mcp_tool(permissions=["family:read", "profile:read"])
        async def multi_permission_tool():
            return {"multi_permissions": True}

        result = await multi_permission_tool()
        assert result == {"multi_permissions": True}

        # Test with missing one of multiple permissions
        @secure_mcp_tool(permissions=["family:read", "admin"])
        async def missing_permission_tool():
            return {"should_not_reach": True}

        with pytest.raises(MCPAuthorizationError):
            await missing_permission_tool()

    @pytest.mark.asyncio
    async def test_context_isolation_between_tools(self):
        """Test that context is properly isolated between different tool executions."""
        # Create two different contexts
        context1 = MCPUserContext(
            user_id="user_1",
            username="user_one",
            permissions=["family:read"],
            ip_address="127.0.0.1",
            user_agent="Client1/1.0",
        )

        context2 = MCPUserContext(
            user_id="user_2",
            username="user_two",
            permissions=["profile:read"],
            ip_address="192.168.1.1",
            user_agent="Client2/1.0",
        )

        async def tool_with_context1():
            set_mcp_user_context(context1)

            @secure_mcp_tool(permissions=["family:read"])
            async def tool1():
                current_context = get_mcp_user_context()
                return {"user_id": current_context.user_id, "username": current_context.username}

            return await tool1()

        async def tool_with_context2():
            set_mcp_user_context(context2)

            @secure_mcp_tool(permissions=["profile:read"])
            async def tool2():
                current_context = get_mcp_user_context()
                return {"user_id": current_context.user_id, "username": current_context.username}

            return await tool2()

        # Execute tools with different contexts
        result1 = await tool_with_context1()
        result2 = await tool_with_context2()

        # Verify contexts were isolated
        assert result1["user_id"] == "user_1"
        assert result1["username"] == "user_one"
        assert result2["user_id"] == "user_2"
        assert result2["username"] == "user_two"


class TestMCPSecurityIntegrationAdvanced:
    """Advanced integration tests for MCP security components."""

    @pytest.mark.asyncio
    async def test_security_with_fastapi_integration(self):
        """Test security integration with FastAPI patterns."""
        # Simulate FastAPI user object
        fastapi_user = {
            "_id": "integration_user_123",
            "username": "integration_user",
            "email": "integration@example.com",
            "role": "user",
            "permissions": ["family:read", "family:write"],
            "workspaces": [],
            "family_memberships": [{"family_id": "family_1", "role": "admin"}],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
        }

        # Create context from FastAPI user
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=fastapi_user,
            ip_address="10.0.0.1",
            user_agent="IntegrationClient/2.0",
            token_type="jwt",
            token_id="integration_token_123",
        )

        set_mcp_user_context(user_context)

        # Test tool execution with FastAPI-derived context
        @secure_mcp_tool(permissions=["family:write"], audit=True)
        async def fastapi_integration_tool():
            context = get_mcp_user_context()
            return {
                "user_id": context.user_id,
                "family_memberships": len(context.family_memberships),
                "has_admin_role": any(fm.get("role") == "admin" for fm in context.family_memberships),
            }

        result = await fastapi_integration_tool()

        assert result["user_id"] == "integration_user_123"
        assert result["family_memberships"] == 1
        assert result["has_admin_role"] is True

    @pytest.mark.asyncio
    async def test_security_performance_under_load(self):
        """Test security wrapper performance under simulated load."""
        context = MCPUserContext(
            user_id="load_test_user",
            username="load_user",
            permissions=["family:read"],
            ip_address="127.0.0.1",
            user_agent="LoadTestClient/1.0",
        )

        async def load_test_tool(iteration: int):
            set_mcp_user_context(context)

            @secure_mcp_tool(permissions=["family:read"], audit=True)
            async def high_load_tool():
                # Simulate minimal work
                return {"iteration": iteration, "timestamp": asyncio.get_event_loop().time()}

            return await high_load_tool()

        # Execute many tools rapidly
        start_time = asyncio.get_event_loop().time()
        tasks = [load_test_tool(i) for i in range(50)]
        results = await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        # Verify all completed successfully
        assert len(results) == 50
        for i, result in enumerate(results):
            assert result["iteration"] == i

        # Performance check - should complete within reasonable time
        execution_time = end_time - start_time
        assert execution_time < 5.0  # Should complete within 5 seconds

        # Average time per tool should be reasonable
        avg_time_per_tool = execution_time / 50
        assert avg_time_per_tool < 0.1  # Less than 100ms per tool on average


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
