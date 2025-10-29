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
import time
import json
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.server.auth import StaticTokenVerifier

from ...config import settings
from ...managers.logging_manager import get_logger
from ...utils.error_handling import handle_errors, RetryConfig, RetryStrategy
from .monitoring_integration import mcp_monitoring_integration
from .error_recovery import mcp_recovery_manager
from .performance_monitoring import mcp_performance_monitor
from .alerting import mcp_alert_manager, alert_server_failure

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
        await alert_server_failure(
            f"MCP server lifespan error: {str(e)}",
            {"error": str(e), "component": "lifespan"}
        )
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
    Create authentication provider based on configuration.
    
    FastMCP 2.x supports Bearer token authentication for HTTP transport.
    Returns None for STDIO transport (process-level security).
    """
    # STDIO transport doesn't need authentication (process-level security)
    if settings.MCP_TRANSPORT == "stdio":
        logger.info("MCP STDIO transport - using process-level security")
        return None
    
    # HTTP transport security configuration
    if not settings.MCP_SECURITY_ENABLED:
        logger.warning("MCP security disabled for HTTP transport - not recommended for production")
        return None
    
    if not settings.MCP_REQUIRE_AUTH:
        logger.info("MCP authentication disabled by configuration")
        return None
    
    # Create static token authentication for HTTP transport
    if hasattr(settings, 'MCP_AUTH_TOKEN') and settings.MCP_AUTH_TOKEN:
        logger.info("MCP static token authentication enabled for HTTP transport")
        # For development/testing - in production use JWTVerifier or OAuth providers
        token_value = settings.MCP_AUTH_TOKEN.get_secret_value() if hasattr(settings.MCP_AUTH_TOKEN, 'get_secret_value') else str(settings.MCP_AUTH_TOKEN)
        return StaticTokenVerifier(tokens={
            token_value: {
                "sub": "mcp-client",
                "aud": "second-brain-mcp",
                "scope": "mcp:tools mcp:resources mcp:prompts"
            }
        })
    
    # For production, require explicit authentication
    if settings.is_production:
        logger.error("Production deployment requires MCP_AUTH_TOKEN for HTTP transport")
        raise ValueError("MCP_AUTH_TOKEN required for production HTTP transport")
    
    logger.info("MCP authentication not configured - development mode only")
    return None


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
    server = FastMCP(
        name=settings.MCP_SERVER_NAME,
        version=settings.MCP_SERVER_VERSION,
        auth=auth_provider
    )
    
    logger.info(
        "FastMCP 2.x server created: %s v%s (transport: %s, auth: %s)",
        settings.MCP_SERVER_NAME,
        settings.MCP_SERVER_VERSION,
        settings.MCP_TRANSPORT,
        "enabled" if auth_provider else "disabled"
    )
    
    logger.info(
        "Component filtering - include: %s, exclude: %s",
        include_tags,
        exclude_tags
    )
    
    return server


# Create the global MCP server instance
mcp = create_modern_mcp_server()

# Export the server instance for use by tool modules
__all__ = ["mcp", "create_modern_mcp_server", "create_auth_provider"]