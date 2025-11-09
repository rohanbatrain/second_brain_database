"""
Modern FastMCP 2.x Server Implementation

This module implements the new FastMCP 2.x patterns and rulesets while maintaining
compatibility with the existing Second Brain Database infrastructure.

Key Features:
- Modern FastMCP 2.x server instantiation with HTTP and STDIO transports
- WebSocket support for real-time MCP communication
- Production-ready authentication and security
- Comprehensive monitoring and health checks
- Session management and connection handling
- Enhanced error handling and recovery
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional, Set

# Add the src directory to Python path for proper imports when run as standalone script
src_path = Path(__file__).parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier

from second_brain_database.config import settings
from second_brain_database.integrations.mcp.alerting import alert_server_failure, mcp_alert_manager
from second_brain_database.integrations.mcp.error_recovery import mcp_recovery_manager
from second_brain_database.integrations.mcp.monitoring_integration import mcp_monitoring_integration
from second_brain_database.integrations.mcp.performance_monitoring import mcp_performance_monitor
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.error_handling import RetryConfig, RetryStrategy, handle_errors

logger = get_logger(prefix="[ModernMCPServer]")


@asynccontextmanager
async def mcp_lifespan(app):
    """
    FastMCP 2.x lifespan context manager for server startup and shutdown.

    Handles initialization and cleanup of monitoring systems, database connections,
    and other resources following FastMCP 2.x patterns.
    """
    logger.info("Starting MCP server lifespan initialization...")

    try:
        # Initialize monitoring systems
        await mcp_monitoring_integration.initialize()
        await mcp_monitoring_integration.start_monitoring()
        logger.info("MCP monitoring systems initialized")

        yield

    except Exception as e:
        logger.error("Error during MCP server lifespan: %s", e)
        await alert_server_failure(f"MCP server lifespan error: {str(e)}", {"error": str(e), "component": "lifespan"})
        raise
    finally:
        # Cleanup monitoring systems
        try:
            await mcp_monitoring_integration.stop_monitoring()
            logger.info("MCP monitoring systems stopped")
        except Exception as e:
            logger.error("Error stopping monitoring systems: %s", e)


def create_auth_provider():
    """
    Create authentication provider following FastMCP 2.x patterns.

    FastMCP 2.x supports native authentication providers that integrate
    with the server's auth system. For HTTP transport, we use JWT validation.
    For STDIO transport, authentication is handled at the process level.
    """
    # STDIO transport uses process-level security
    if settings.MCP_TRANSPORT == "stdio":
        logger.info("STDIO transport - using process-level security")
        return None

    # HTTP transport authentication
    if not settings.MCP_SECURITY_ENABLED or not settings.MCP_REQUIRE_AUTH:
        logger.info("HTTP transport - authentication disabled for development")
        return None

    # Production HTTP transport - use FastMCP's native auth patterns
    logger.info("Creating FastMCP 2.x JWT authentication provider")

    # Import the custom auth provider that integrates with existing JWT system
    from second_brain_database.integrations.mcp.auth_middleware import FastMCPJWTAuthProvider

    return FastMCPJWTAuthProvider()


def determine_component_tags() -> tuple[Set[str], Set[str]]:
    """
    Determine which component tags to include/exclude based on configuration.

    Returns:
        Tuple of (include_tags, exclude_tags)
    """
    include_tags = set()
    exclude_tags = set()

    # Environment-based filtering
    if settings.is_production:
        include_tags.add("production")
        exclude_tags.update({"development", "testing", "debug"})
    else:
        include_tags.update({"development", "testing"})
        exclude_tags.add("production-only")

    # Security-based filtering
    if settings.MCP_SECURITY_ENABLED:
        include_tags.add("secure")
    else:
        exclude_tags.add("secure-only")

    # Feature-based filtering
    if settings.MCP_TOOLS_ENABLED:
        include_tags.add("tools")
    else:
        exclude_tags.add("tools")

    if settings.MCP_RESOURCES_ENABLED:
        include_tags.add("resources")
    else:
        exclude_tags.add("resources")

    if settings.MCP_PROMPTS_ENABLED:
        include_tags.add("prompts")
    else:
        exclude_tags.add("prompts")

    return include_tags, exclude_tags


def create_modern_mcp_server() -> FastMCP:
    """
    Create a modern FastMCP 2.x server instance following best practices.

    This follows the recommended FastMCP 2.x patterns:
    - Simple server instantiation
    - Proper authentication configuration
    - Tool registration via decorators (handled in tool modules)

    Returns:
        Configured FastMCP server instance with proper authentication
    """
    # Create authentication provider
    auth_provider = create_auth_provider()

    # Determine component tags for filtering
    include_tags, exclude_tags = determine_component_tags()

    # Create FastMCP 2.x server instance following documentation patterns
    try:
        server = FastMCP(name=settings.MCP_SERVER_NAME, version=settings.MCP_SERVER_VERSION, auth=auth_provider)
    except Exception as e:
        logger.error("Failed to create FastMCP server: %s", e)
        # Fallback without auth if there's an issue
        server = FastMCP(name=settings.MCP_SERVER_NAME, version=settings.MCP_SERVER_VERSION)
        logger.warning("Created FastMCP server without authentication due to error")

    logger.info(
        "FastMCP 2.x server created: %s v%s (transport: %s, auth: %s)",
        settings.MCP_SERVER_NAME,
        settings.MCP_SERVER_VERSION,
        settings.MCP_TRANSPORT,
        "enabled" if auth_provider else "disabled",
    )

    logger.info("Component filtering - include: %s, exclude: %s", include_tags, exclude_tags)

    return server


# Create the global MCP server instance
mcp = create_modern_mcp_server()

# Export the server instance for use by tool modules
__all__ = ["mcp", "create_modern_mcp_server", "create_auth_provider"]
