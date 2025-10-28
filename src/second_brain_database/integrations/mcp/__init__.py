"""
FastMCP Gateway Integration

This module provides a production-ready, security-first FastMCP integration
that exposes selected backend functionality through the Model Context Protocol (MCP).
"""

from .server import mcp_server_manager
from .exceptions import (
    MCPSecurityError,
    MCPAuthenticationError,
    MCPAuthorizationError,
    MCPValidationError,
    MCPRateLimitError,
    MCPToolError,
)

__all__ = [
    "mcp_server_manager",
    "MCPSecurityError",
    "MCPAuthenticationError", 
    "MCPAuthorizationError",
    "MCPValidationError",
    "MCPRateLimitError",
    "MCPToolError",
]