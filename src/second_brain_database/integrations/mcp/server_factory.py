"""
MCP Server Factory

Production-ready factory for creating MCP servers with proper authentication,
monitoring, and error handling.
"""

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ...config import settings
from ...managers.logging_manager import get_logger
from .exceptions import MCPServerError
from .modern_server import create_modern_mcp_server
from .simple_auth import authenticate_mcp_request, create_mcp_context_middleware

logger = get_logger(prefix="[MCP_Factory]")


class MCPServerFactory:
    """
    Factory for creating production-ready MCP servers.

    This factory handles the complexity of setting up MCP servers with proper
    authentication, middleware, monitoring, and error handling.
    """

    def __init__(self):
        self.logger = logger
        self._server_instance = None
        self._auth_provider = None
        self._middleware_stack = []

    def create_server(self, transport: str = "http") -> Any:
        """
        Create a production-ready MCP server.

        Args:
            transport: Transport type ("stdio" or "http")

        Returns:
            Configured MCP server instance

        Raises:
            MCPServerError: If server creation fails
        """
        try:
            self.logger.info("Creating MCP server with %s transport", transport)

            # Update transport in settings if needed
            if hasattr(settings, "MCP_TRANSPORT"):
                settings.MCP_TRANSPORT = transport

            # Create authentication provider
            self._auth_provider = self._create_auth_provider()

            # Create server instance
            self._server_instance = create_modern_mcp_server()

            # Configure authentication if available
            if self._auth_provider:
                self._server_instance.auth = self._auth_provider
                self.logger.info("Authentication provider configured: %s", self._auth_provider.name)
            else:
                self.logger.info("No authentication provider - development mode")

            # Set up middleware for HTTP transport
            if transport == "http":
                self._setup_http_middleware()

            self.logger.info("MCP server created successfully")
            return self._server_instance

        except Exception as e:
            self.logger.error("Failed to create MCP server: %s", e)
            raise MCPServerError(f"Server creation failed: {e}") from e

    def _create_auth_provider(self) -> Optional[Any]:
        """
        Create authentication provider based on configuration.

        Returns:
            Authentication provider or None (simplified for FastMCP 2.x)
        """
        # FastMCP 2.x doesn't have a built-in auth system like we tried to use
        # Authentication is handled at the tool level via decorators
        self.logger.info("Using tool-level authentication (FastMCP 2.x pattern)")
        return None

    def _setup_http_middleware(self) -> None:
        """
        Set up middleware stack for HTTP transport.
        """
        try:
            # Context cleanup middleware
            context_middleware = create_mcp_context_middleware()
            self._middleware_stack.append(context_middleware)

            # CORS middleware if enabled
            if settings.MCP_HTTP_CORS_ENABLED:
                self._setup_cors_middleware()

            self.logger.info("HTTP middleware configured: %d middleware(s)", len(self._middleware_stack))

        except Exception as e:
            self.logger.warning("Failed to set up HTTP middleware: %s", e)

    def _setup_cors_middleware(self) -> None:
        """
        Set up CORS middleware for HTTP transport.
        """
        try:
            origins = [origin.strip() for origin in settings.MCP_HTTP_CORS_ORIGINS.split(",") if origin.strip()]

            if not origins:
                origins = ["*"]

            self.logger.info("CORS configured for origins: %s", origins)

        except Exception as e:
            self.logger.warning("Failed to set up CORS middleware: %s", e)

    def get_server_info(self) -> Dict[str, Any]:
        """
        Get information about the created server.

        Returns:
            Dictionary with server information
        """
        if not self._server_instance:
            return {"available": False, "error": "No server instance"}

        try:
            # Get tool count
            tool_count = len(getattr(self._server_instance, "_tools", {}))

            # Get resource count
            resource_count = len(getattr(self._server_instance, "_resources", {}))

            # Get prompt count
            prompt_count = len(getattr(self._server_instance, "_prompts", {}))

            return {
                "available": True,
                "name": settings.MCP_SERVER_NAME,
                "version": settings.MCP_SERVER_VERSION,
                "transport": settings.MCP_TRANSPORT,
                "tool_count": tool_count,
                "resource_count": resource_count,
                "prompt_count": prompt_count,
                "auth_enabled": self._auth_provider is not None,
                "auth_provider": self._auth_provider.name if self._auth_provider else None,
                "middleware_count": len(self._middleware_stack),
                "security_enabled": settings.MCP_SECURITY_ENABLED,
                "debug_mode": settings.MCP_DEBUG_MODE,
            }

        except Exception as e:
            self.logger.error("Failed to get server info: %s", e)
            return {"available": False, "error": str(e)}

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate MCP server configuration.

        Returns:
            Dictionary with validation results
        """
        issues = []
        warnings = []

        # Check transport configuration
        if settings.MCP_TRANSPORT not in ["stdio", "http"]:
            issues.append(f"Invalid transport: {settings.MCP_TRANSPORT}")

        # Check HTTP configuration
        if settings.MCP_TRANSPORT == "http":
            if settings.MCP_HTTP_PORT < 1024 or settings.MCP_HTTP_PORT > 65535:
                issues.append(f"Invalid HTTP port: {settings.MCP_HTTP_PORT}")

            if settings.MCP_SECURITY_ENABLED and not settings.MCP_REQUIRE_AUTH:
                warnings.append("Security enabled but authentication not required")

            if settings.MCP_REQUIRE_AUTH and not hasattr(settings, "MCP_AUTH_TOKEN"):
                issues.append("Authentication required but no MCP_AUTH_TOKEN configured")

        # Check database configuration
        if not settings.MONGODB_URL:
            issues.append("MONGODB_URL not configured")

        if not settings.REDIS_URL:
            warnings.append("REDIS_URL not configured - some features may not work")

        # Check security configuration
        if settings.is_production and not settings.MCP_SECURITY_ENABLED:
            warnings.append("Production environment with security disabled")

        if settings.MCP_SECURITY_ENABLED and not settings.SECRET_KEY:
            issues.append("Security enabled but SECRET_KEY not configured")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "configuration": {
                "transport": settings.MCP_TRANSPORT,
                "security_enabled": settings.MCP_SECURITY_ENABLED,
                "auth_required": settings.MCP_REQUIRE_AUTH,
                "environment": settings.ENVIRONMENT,
                "debug_mode": settings.MCP_DEBUG_MODE,
            },
        }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the MCP server.

        Returns:
            Dictionary with health check results
        """
        health = {"healthy": True, "components": {}, "timestamp": None}

        try:
            from datetime import datetime, timezone

            health["timestamp"] = datetime.now(timezone.utc).isoformat()

            # Check server instance
            if self._server_instance:
                health["components"]["server"] = {"status": "healthy", "details": "Server instance available"}
            else:
                health["components"]["server"] = {"status": "unhealthy", "details": "No server instance"}
                health["healthy"] = False

            # Check authentication
            if self._auth_provider:
                health["components"]["auth"] = {
                    "status": "healthy",
                    "details": f"Auth provider: {self._auth_provider.name}",
                }
            else:
                health["components"]["auth"] = {"status": "info", "details": "No authentication (development mode)"}

            # Check database connectivity
            try:
                from ...managers.database_manager import database_manager

                await database_manager.health_check()
                health["components"]["database"] = {"status": "healthy", "details": "MongoDB connection OK"}
            except Exception as e:
                health["components"]["database"] = {"status": "unhealthy", "details": f"Database error: {e}"}
                health["healthy"] = False

            # Check Redis connectivity
            try:
                from ...managers.redis_manager import redis_manager

                redis_conn = await redis_manager.get_redis()
                await redis_conn.ping()
                health["components"]["redis"] = {"status": "healthy", "details": "Redis connection OK"}
            except Exception as e:
                health["components"]["redis"] = {"status": "warning", "details": f"Redis error: {e}"}

            return health

        except Exception as e:
            self.logger.error("Health check failed: %s", e)
            return {"healthy": False, "error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}


# Global factory instance
mcp_server_factory = MCPServerFactory()


def create_mcp_server(transport: str = "http") -> Any:
    """
    Create MCP server using the factory.

    Args:
        transport: Transport type ("stdio" or "http")

    Returns:
        Configured MCP server instance
    """
    return mcp_server_factory.create_server(transport)


def get_mcp_server_info() -> Dict[str, Any]:
    """
    Get information about the current MCP server.

    Returns:
        Dictionary with server information
    """
    return mcp_server_factory.get_server_info()


def validate_mcp_configuration() -> Dict[str, Any]:
    """
    Validate MCP server configuration.

    Returns:
        Dictionary with validation results
    """
    return mcp_server_factory.validate_configuration()


async def mcp_health_check() -> Dict[str, Any]:
    """
    Perform health check on the MCP server.

    Returns:
        Dictionary with health check results
    """
    return await mcp_server_factory.health_check()
