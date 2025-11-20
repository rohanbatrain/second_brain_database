#!/usr/bin/env python3
"""
Basic validation tests for MCP components.

Simple tests that validate MCP components can be imported and basic
functionality works without requiring full dependency setup.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_mcp_context_classes():
    """Test that MCP context classes can be imported and instantiated."""
    from second_brain_database.integrations.mcp.context import MCPRequestContext, MCPUserContext

    # Test MCPUserContext
    user_context = MCPUserContext(user_id="test_user", username="test", permissions=["test:read"])

    assert user_context.user_id == "test_user"
    assert user_context.has_permission("test:read") is True
    assert user_context.has_permission("admin") is False

    # Test MCPRequestContext
    request_context = MCPRequestContext(request_id="test_request_123", tool_name="test_tool", operation_type="tool")

    assert request_context.request_id == "test_request_123"
    assert request_context.tool_name == "test_tool"


def test_mcp_exceptions():
    """Test that MCP exception classes can be imported and used."""
    from second_brain_database.integrations.mcp.exceptions import (
        MCPAuthenticationError,
        MCPAuthorizationError,
        MCPRateLimitError,
    )

    # Test exception creation
    auth_error = MCPAuthenticationError("Test auth error")
    assert str(auth_error) == "MCPAuthenticationError: Test auth error"
    assert auth_error.message == "Test auth error"

    authz_error = MCPAuthorizationError("Test authz error")
    assert str(authz_error) == "MCPAuthorizationError: Test authz error"
    assert authz_error.message == "Test authz error"

    rate_error = MCPRateLimitError("Test rate limit error")
    assert str(rate_error) == "MCPRateLimitError: Test rate limit error"
    assert rate_error.message == "Test rate limit error"


def test_mcp_security_classes():
    """Test that MCP security classes can be imported."""
    # Test basic imports without full initialization
    from second_brain_database.integrations.mcp.security import authenticated_tool, mcp_context_manager, secure_mcp_tool

    # Test that decorators are callable
    assert callable(secure_mcp_tool)
    assert callable(authenticated_tool)
    assert callable(mcp_context_manager)


def test_mcp_server_manager():
    """Test that MCP server manager can be imported."""
    from second_brain_database.integrations.mcp.server import MCPServerManager

    # Test basic instantiation
    server_manager = MCPServerManager()
    assert server_manager is not None
    assert server_manager.is_initialized is False
    assert server_manager.is_running is False


def test_mcp_file_structure():
    """Test that MCP integration files exist and are structured correctly."""
    mcp_dir = "src/second_brain_database/integrations/mcp"

    required_files = ["__init__.py", "server.py", "security.py", "context.py", "exceptions.py", "config.py"]

    missing_files = []
    for file in required_files:
        file_path = os.path.join(mcp_dir, file)
        if not os.path.exists(file_path):
            missing_files.append(file)

    assert not missing_files, f"Missing MCP files: {missing_files}"
