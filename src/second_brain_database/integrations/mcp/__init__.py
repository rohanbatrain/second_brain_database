"""
Modern FastMCP 2.x Integration

This module provides a modern FastMCP 2.x integration using STDIO transport
for local AI clients and HTTP transport for remote connections.

Following FastMCP 2.x patterns:
- Tools, resources, and prompts are registered via decorators
- Server uses native FastMCP HTTP app
- Authentication follows FastMCP patterns
- Production-ready ASGI application
"""

# Import modules to register tools, resources, and prompts
# This follows FastMCP 2.x patterns where decorators are executed on import
from . import tools_registration
from .exceptions import (
    MCPAuthenticationError,
    MCPAuthorizationError,
    MCPRateLimitError,
    MCPSecurityError,
    MCPToolError,
    MCPValidationError,
)
from .modern_server import create_modern_mcp_server, mcp

# DEPRECATED: Old registration files replaced by organized modules in prompts/ and resources/
# from . import resources_registration  # Replaced by resources/user_resources.py, resources/system_resources.py
# from . import prompts_registration    # Replaced by prompts/guidance_prompts.py

__all__ = [
    "mcp",
    "create_modern_mcp_server",
    "MCPSecurityError",
    "MCPAuthenticationError",
    "MCPAuthorizationError",
    "MCPValidationError",
    "MCPRateLimitError",
    "MCPToolError",
]
