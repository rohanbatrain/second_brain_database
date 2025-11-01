"""
Working test tools using native FastMCP 2.x patterns
"""

from typing import Dict, Any
from ..modern_server import mcp

@mcp.tool(name="test_working_tool", description="A working test tool")
async def test_working_tool() -> Dict[str, Any]:
    """Test tool that should definitely work."""
    return {
        "status": "success",
        "message": "Working test tool executed successfully",
        "timestamp": "2025-11-01"
    }

@mcp.tool(name="test_family_balance", description="Test family token balance")
async def test_family_balance() -> Dict[str, Any]:
    """Test family balance tool."""
    return {
        "status": "success",
        "balance": 1000,
        "currency": "SBD",
        "families": [
            {"id": "test_family_1", "name": "Test Family", "balance": 1000}
        ]
    }

@mcp.tool(name="test_create_family", description="Test family creation")
async def test_create_family(name: str = "Test Family") -> Dict[str, Any]:
    """Test family creation tool."""
    return {
        "status": "success",
        "family_id": "test_family_123",
        "name": name,
        "created": True
    }
