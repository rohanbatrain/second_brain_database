"""
MCP Tools

This package contains all MCP tool implementations organized by functionality.
Tools are automatically discovered and registered with the FastMCP server
through decorator-based registration.
"""

# Tool modules will be imported here when implemented
from . import family_tools
# from . import auth_tools
# from . import profile_tools
from . import shop_tools
from . import workspace_tools
from . import admin_tools
from . import test_tools

__all__ = [
    "family_tools",
    "shop_tools",
    "workspace_tools",
    "admin_tools",
    "test_tools"
]
