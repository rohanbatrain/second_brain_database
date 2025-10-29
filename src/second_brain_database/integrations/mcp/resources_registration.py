"""
FastMCP 2.x Resource Registration

This module demonstrates proper resource registration following FastMCP 2.x patterns.
Resources are registered using the @mcp.resource decorator directly on the server instance.
"""

from typing import Dict, Any, List
from datetime import datetime

from ...managers.logging_manager import get_logger
from ...config import settings
from .modern_server import mcp

logger = get_logger(prefix="[MCP_Resources]")


# FastMCP 2.x compliant resource registration following documentation patterns
@mcp.resource("server://status")
def server_status_resource() -> dict:
    """Get current server status as a resource."""
    return {
        "server_name": mcp.name,
        "server_version": mcp.version,
        "timestamp": datetime.now().isoformat(),
        "transport": settings.MCP_TRANSPORT,
        "auth_enabled": mcp.auth is not None,
        "status": "operational"
    }


@mcp.resource(
    uri="server://config",
    name="ServerConfiguration", 
    description="Provides server configuration details",
    mime_type="application/json"
)
def server_config_resource() -> dict:
    """Get server configuration as a resource."""
    return {
        "server_name": settings.MCP_SERVER_NAME,
        "server_version": settings.MCP_SERVER_VERSION,
        "transport": settings.MCP_TRANSPORT,
        "security_enabled": settings.MCP_SECURITY_ENABLED,
        "cors_enabled": settings.MCP_HTTP_CORS_ENABLED,
        "tools_enabled": settings.MCP_TOOLS_ENABLED,
        "resources_enabled": settings.MCP_RESOURCES_ENABLED,
        "prompts_enabled": settings.MCP_PROMPTS_ENABLED
    }


@mcp.resource("server://health")
def server_health_resource() -> dict:
    """Get server health information as a resource."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "server": mcp.name,
        "version": mcp.version,
        "uptime": "N/A",  # Would be calculated in real implementation
        "memory_usage": "N/A",  # Would be calculated in real implementation
        "cpu_usage": "N/A"  # Would be calculated in real implementation
    }


# Example of a templated resource following FastMCP patterns
@mcp.resource("user://{user_id}/profile")
def user_profile_resource(user_id: str) -> dict:
    """Get user profile information as a templated resource.
    
    Args:
        user_id: The ID of the user to get profile for
        
    Returns:
        User profile information
    """
    # In a real implementation, this would fetch from database
    return {
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "note": "This is a templated resource example",
        "profile_type": "basic"
    }


@mcp.resource("system://metrics")
async def system_metrics_resource() -> str:
    """Get system metrics as a resource."""
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "server": mcp.name,
        "version": mcp.version,
        "auth_enabled": mcp.auth is not None,
        "transport": settings.MCP_TRANSPORT,
        "note": "System metrics would be collected here in real implementation"
    }
    return f"System Metrics:\n{metrics}"


@mcp.resource("api://endpoints")
async def api_endpoints_resource() -> str:
    """Get available API endpoints as a resource."""
    endpoints = {
        "mcp_protocol": "/mcp",
        "health_check": "/health",
        "metrics": "/metrics",
        "status": "/status",
        "websocket": "/mcp/ws" if hasattr(settings, 'MCP_WEBSOCKET_ENABLED') else None
    }
    # Filter out None values
    endpoints = {k: v for k, v in endpoints.items() if v is not None}
    return f"Available Endpoints:\n{endpoints}"


def register_example_resources():
    """
    Register example resources with the MCP server.
    
    Note: In FastMCP 2.x, resources are automatically registered when the module
    is imported and the @mcp.resource decorators are executed. This function
    is provided for explicit registration if needed.
    """
    logger.info("Example resources registered with FastMCP 2.x server")
    logger.info("Resources available: server://status, server://config, server://health, user://{user_id}/profile, system://metrics, api://endpoints")


# Auto-register resources when module is imported
register_example_resources()