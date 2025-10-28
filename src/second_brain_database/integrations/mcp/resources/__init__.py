"""
MCP Resources

This package contains all MCP resource implementations that provide
comprehensive information resources for major entities with real-time data.
Resources are automatically discovered and registered with the FastMCP server.
"""

# Resource modules - import to register with FastMCP
from . import family_resources
from . import user_resources
from . import workspace_resources
from . import system_resources
from . import shop_resources

__all__ = [
    "family_resources",
    "user_resources", 
    "workspace_resources",
    "system_resources",
    "shop_resources"
]