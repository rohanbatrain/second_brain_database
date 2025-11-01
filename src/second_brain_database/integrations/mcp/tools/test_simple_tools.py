"""
Simple test tools to verify MCP registration works
"""

from typing import Dict, Any
from ..security import authenticated_tool, get_mcp_user_context

@authenticated_tool(
    name="test_simple_tool",
    description="A simple test tool to verify MCP registration",
    permissions=["test:read"]
)
async def test_simple_tool() -> Dict[str, Any]:
    """Simple test tool that should be registered."""
    user_context = get_mcp_user_context()
    return {
        "status": "success",
        "message": "Test tool executed successfully",
        "user_id": user_context.user_id if user_context else "unknown"
    }

@authenticated_tool(
    name="test_family_info",
    description="Test tool for family information",
    permissions=["family:read"]
)
async def test_family_info() -> Dict[str, Any]:
    """Test tool for family operations."""
    return {
        "status": "success",
        "message": "Test family tool executed",
        "families": []
    }
