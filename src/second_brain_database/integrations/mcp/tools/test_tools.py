"""
Test MCP Tools for FastMCP 2.0

Simple test tools to validate FastMCP 2.0 integration and functionality.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..mcp_instance import get_mcp_server
from ..modern_server import mcp
from ..security import get_mcp_user_context

logger = get_logger(prefix="[MCP_TestTools]")

# Get the shared MCP server instance
mcp_server = get_mcp_server()

if mcp_server is not None:

    @mcp_server.tool("test_echo")
    async def test_echo_tool(message: str = "Hello, FastMCP 2.0!") -> str:
        """
        Simple echo tool for testing FastMCP 2.0 integration.

        Args:
            message: Message to echo back

        Returns:
            The echoed message with timestamp
        """
        try:
            user_context = get_mcp_user_context()

            # Create audit trail
            await create_mcp_audit_trail(
                operation="test_echo",
                user_context=user_context,
                resource_type="tool",
                resource_id="test_echo",
                metadata={"message": message},
            )

            timestamp = datetime.now(timezone.utc).isoformat()
            response = f"Echo: {message} (at {timestamp})"

            logger.info("Test echo tool called by user %s: %s", user_context.user_id, message)
            return response

        except Exception as e:
            logger.error("Test echo tool failed: %s", e)
            return f"Error: {str(e)}"

    @mcp_server.tool("test_health")
    async def test_health_tool() -> Dict[str, Any]:
        """
        Health check tool for testing FastMCP 2.0 integration.

        Returns:
            Health status information
        """
        try:
            user_context = get_mcp_user_context()

            # Create audit trail
            await create_mcp_audit_trail(
                operation="test_health",
                user_context=user_context,
                resource_type="tool",
                resource_id="test_health",
                metadata={"check_type": "health"},
            )

            health_info = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "fastmcp_version": "2.0",
                "user_id": user_context.user_id,
                "user_role": user_context.role,
            }

            logger.info("Test health tool called by user %s", user_context.user_id)
            return health_info

        except Exception as e:
            logger.error("Test health tool failed: %s", e)
            return {"status": "error", "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}

else:
    logger.warning("FastMCP 2.0 not available - test tools will not be registered")
