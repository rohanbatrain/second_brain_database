"""
FastMCP 2.x Resource Registration

DEPRECATED: This module contains old resource registrations that have been replaced
by the production-ready resources in resources/ directory.

The resources below are commented out to prevent duplicates. The new resources include:
- Production tags for filtering
- Database-driven data
- User context integration
- Proper security controls

DO NOT RE-ENABLE THESE RESOURCES. Use resources/user_resources.py and resources/system_resources.py instead.
"""

from datetime import datetime
from typing import Any, Dict, List

from ...config import settings
from ...managers.logging_manager import get_logger
from .modern_server import mcp

logger = get_logger(prefix="[MCP_Resources_DEPRECATED]")


# DEPRECATED: Basic resources replaced by production versions in resources/ directory
# Kept here for reference only - DO NOT UNCOMMENT

# @mcp.resource("server://status")
# def server_status_resource() -> dict:
#     """Get current server status as a resource."""
#     ...


# @mcp.resource(
#     uri="server://config",
#     name="ServerConfiguration",
#     description="Provides server configuration details",
#     mime_type="application/json"
# )
# def server_config_resource() -> dict:
#     """Get server configuration as a resource."""
#     ...


# @mcp.resource("server://health")
# def server_health_resource() -> dict:
#     """Get server health information as a resource."""
#     ...


# DEPRECATED: Replaced by resources/user_resources.py user://{user_id}/profile with production tags
# @mcp.resource("user://{user_id}/profile")
# def user_profile_resource(user_id: str) -> dict:
#     """Get user profile information as a templated resource."""
#     ...


# DEPRECATED: Replaced by resources/system_resources.py system://metrics with production tags
# @mcp.resource("system://metrics")
# async def system_metrics_resource() -> str:
#     """Get system metrics as a resource."""
#     ...


# DEPRECATED: Replaced by production resources
# @mcp.resource("api://endpoints")
# async def api_endpoints_resource() -> str:
#     """Get API endpoints as a resource."""
#     ...


def register_example_resources():
    """
    DEPRECATED: Resources are no longer registered from this module.

    All production resources are now registered from:
    - resources/user_resources.py (user-specific resources)
    - resources/system_resources.py (system-wide resources)

    These include production tags, database integration, and proper security.

    This function is kept for backwards compatibility but does nothing.
    """
    logger.warning("resources_registration.py is DEPRECATED - use resources/ directory instead")
    logger.info(
        "Production resources are registered from resources/user_resources.py and resources/system_resources.py"
    )


# Auto-register resources when module is imported (DEPRECATED - does nothing now)
register_example_resources()
