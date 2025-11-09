"""
System MCP Resources

Comprehensive information resources for system status and health monitoring.
Provides system information, health status, and performance metrics through MCP resources.
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from ....config import settings
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import get_mcp_user_context

logger = get_logger(prefix="[MCP_SystemResources]")


@mcp.resource("system://health", tags={"production", "resources", "secure", "system"})
async def get_system_health_resource() -> str:
    """
    Get system health information as a resource.

    Returns:
        JSON string containing system health status
    """
    try:
        user_context = get_mcp_user_context()

        # Only allow admin users to access system health
        if user_context.role != "admin":
            raise MCPAuthorizationError("Access denied to system health information")

        # Mock system health data - replace with actual health monitoring
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "database": {"status": "healthy", "response_time_ms": 15},
                "redis": {"status": "healthy", "response_time_ms": 5},
                "mcp_server": {"status": "healthy", "response_time_ms": 10},
                "ai_orchestration": {"status": "removed", "response_time_ms": 0},
            },
            "metrics": {
                "uptime_seconds": 86400,
                "memory_usage_percent": 65,
                "cpu_usage_percent": 45,
                "active_sessions": 12,
            },
        }

        result = {
            "health": health_status,
            "resource_type": "system_health",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        await create_mcp_audit_trail(
            operation="get_system_health_resource",
            user_context=user_context,
            resource_type="system",
            resource_id="health",
            metadata={"health_status": health_status["status"]},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get system health resource: %s", e)
        return json.dumps({"error": f"Failed to retrieve system health: {str(e)}"}, indent=2)


@mcp.resource("system://metrics", tags={"production", "resources", "secure", "system"})
async def get_system_metrics_resource() -> str:
    """
    Get system performance metrics as a resource.

    Returns:
        JSON string containing system metrics
    """
    try:
        user_context = get_mcp_user_context()

        # Only allow admin users to access system metrics
        if user_context.role != "admin":
            raise MCPAuthorizationError("Access denied to system metrics")

        # Mock metrics data - replace with actual metrics collection
        metrics = {
            "performance": {
                "requests_per_second": 150,
                "average_response_time_ms": 45,
                "error_rate_percent": 0.5,
                "throughput_mbps": 25.5,
            },
            "resources": {
                "memory_total_gb": 16,
                "memory_used_gb": 10.4,
                "cpu_cores": 8,
                "cpu_usage_percent": 45,
                "disk_total_gb": 500,
                "disk_used_gb": 250,
            },
            "database": {
                "connections_active": 25,
                "connections_max": 100,
                "query_avg_time_ms": 12,
                "cache_hit_rate_percent": 85,
            },
        }

        result = {
            "metrics": metrics,
            "resource_type": "system_metrics",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        await create_mcp_audit_trail(
            operation="get_system_metrics_resource",
            user_context=user_context,
            resource_type="system",
            resource_id="metrics",
            metadata={"metrics_accessed": True},
        )

        return json.dumps(result, indent=2, default=str)

    except Exception as e:
        logger.error("Failed to get system metrics resource: %s", e)
        return json.dumps({"error": f"Failed to retrieve system metrics: {str(e)}"}, indent=2)
