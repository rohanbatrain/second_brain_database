"""
MCP Tools

This package contains all MCP tool implementations organized by functionality.
Tools are automatically discovered and registered with the FastMCP server
through decorator-based registration.
"""

# from . import auth_tools
# from . import profile_tools
# Tool modules will be imported here when implemented
from . import admin_tools, document_tools, family_tools, rag_tools, shop_tools, test_tools, workspace_tools

__all__ = ["family_tools", "shop_tools", "workspace_tools", "admin_tools", "test_tools", "document_tools", "rag_tools"]
