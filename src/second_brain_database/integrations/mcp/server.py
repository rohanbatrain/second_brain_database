"""
MCP Server Manager

Provides a high-level interface for managing MCP server operations,
authentication, and lifecycle management.
"""

import asyncio
from typing import Any, Dict, List, Optional

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MCP_Server_Manager]")


class MCPServerManager:
    """
    Manager for MCP server operations and lifecycle management.

    This class provides a high-level interface for managing MCP server
    instances, authentication, and operational tasks.
    """

    def __init__(self):
        """Initialize the MCP server manager."""
        self.logger = logger
        self._server = None
        self._initialized = False
        self._running = False

    async def initialize(self) -> None:
        """
        Initialize the MCP server manager.

        This method sets up the server instance and prepares it for operation.
        """
        if self._initialized:
            return

        try:
            # Import the modern MCP server
            from second_brain_database.integrations.mcp.modern_server import mcp

            self._server = mcp
            self._initialized = True
            self.logger.info("MCP server manager initialized successfully")

        except ImportError as e:
            self.logger.warning("Failed to import MCP server: %s", e)
            self._server = None
        except Exception as e:
            self.logger.error("Error initializing MCP server manager: %s", e)
            raise

    async def start_server(self) -> None:
        """
        Start the MCP server.

        This method starts the MCP server and begins accepting connections.
        """
        if not self._initialized:
            await self.initialize()

        if self._server is None:
            raise RuntimeError("MCP server not available")

        # The server is already created and configured in modern_server.py
        # Additional startup logic can be added here if needed
        self._running = True
        self.logger.info("MCP server started")

    async def stop_server(self) -> None:
        """
        Stop the MCP server.

        This method gracefully shuts down the MCP server.
        """
        if self._server:
            # Cleanup logic can be added here if needed
            self.logger.info("MCP server stopped")
            self._server = None
            self._initialized = False
            self._running = False

    def get_server(self) -> Any:
        """
        Get the underlying MCP server instance.

        Returns:
            The MCP server instance, or None if not initialized
        """
        return self._server

    @property
    def is_initialized(self) -> bool:
        """
        Check if the server manager is initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    @property
    def is_running(self) -> bool:
        """
        Check if the server is running.

        Returns:
            True if running, False otherwise
        """
        return self._running

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on the MCP server.

        Returns:
            Dictionary containing health check results
        """
        health_status = {
            "status": "healthy" if self._initialized and self._server else "unhealthy",
            "initialized": self._initialized,
            "server_available": self._server is not None,
            "timestamp": asyncio.get_event_loop().time(),
        }

        if self._server:
            health_status.update({
                "server_name": getattr(self._server, 'name', 'unknown'),
                "server_version": getattr(self._server, 'version', 'unknown'),
            })

        return health_status

    async def get_server_info(self) -> Dict[str, Any]:
        """
        Get information about the MCP server.

        Returns:
            Dictionary containing server information
        """
        if not self._server:
            return {"error": "Server not initialized"}

        return {
            "name": getattr(self._server, 'name', 'unknown'),
            "version": getattr(self._server, 'version', 'unknown'),
            "transport": settings.MCP_TRANSPORT,
            "security_enabled": settings.MCP_SECURITY_ENABLED,
            "tools_enabled": settings.MCP_TOOLS_ENABLED,
            "resources_enabled": settings.MCP_RESOURCES_ENABLED,
            "prompts_enabled": settings.MCP_PROMPTS_ENABLED,
        }


# Global server manager instance
server_manager = MCPServerManager()

__all__ = ["MCPServerManager", "server_manager"]