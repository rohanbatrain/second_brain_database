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

from .modern_server import mcp, create_modern_mcp_server
from .exceptions import (
    MCPSecurityError,
    MCPAuthenticationError,
    MCPAuthorizationError,
    MCPValidationError,
    MCPRateLimitError,
    MCPToolError,
)

# Import modules to register tools, resources, and prompts
# This follows FastMCP 2.x patterns where decorators are executed on import
from . import tools_registration
from . import resources_registration
from . import prompts_registration

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