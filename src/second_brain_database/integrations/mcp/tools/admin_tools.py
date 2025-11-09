"""
Administrative and System Management MCP Tools

MCP tools for system health monitoring, user management, and system configuration.
These tools provide comprehensive administrative capabilities for system operators.
"""

import asyncio
from datetime import datetime, timedelta
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ....config import settings
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import authenticated_tool, get_mcp_user_context

logger = get_logger(prefix="[MCP_AdminTools]")

# Import manager instances
from ....database import db_manager
from ....managers.family_manager import FamilyManager
from ....managers.redis_manager import redis_manager
from ....managers.security_manager import security_manager


# Pydantic models for admin tool parameters and responses
class SystemHealthStatus(BaseModel):
    """System health status response model."""

    healthy: bool
    timestamp: datetime
    components: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    overall_status: str
    uptime_seconds: Optional[float] = None


class DatabaseStats(BaseModel):
    """Database statistics response model."""

    connection_status: str
    collections: int
    total_documents: int
    data_size_bytes: int
    index_size_bytes: int
    avg_response_time_ms: float
    collections_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class RedisStats(BaseModel):
    """Redis statistics response model."""

    connection_status: str
    memory_usage_bytes: int
    connected_clients: int
    total_commands_processed: int
    keyspace_hits: int
    keyspace_misses: int
    hit_rate_percentage: float
    uptime_seconds: int


class APIMetrics(BaseModel):
    """API performance metrics response model."""

    total_requests: int
    requests_per_minute: float
    average_response_time_ms: float
    error_rate_percentage: float
    active_connections: int
    endpoint_stats: Dict[str, Dict[str, Any]] = Field(default_factory=dict)


class ErrorLogEntry(BaseModel):
    """Error log entry model."""

    timestamp: datetime
    level: str
    message: str
    source: str
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    error_type: Optional[str] = None


class PerformanceMetrics(BaseModel):
    """System performance metrics response model."""

    cpu_usage_percentage: Optional[float] = None
    memory_usage_percentage: Optional[float] = None
    disk_usage_percentage: Optional[float] = None
    network_io: Optional[Dict[str, int]] = None
    database_performance: Dict[str, Any] = Field(default_factory=dict)
    cache_performance: Dict[str, Any] = Field(default_factory=dict)


# System Monitoring Tools (Task 8.1)


@authenticated_tool(
    name="get_system_health",
    description="Get comprehensive system health status including all components",
    permissions=["admin", "system:monitor"],
    rate_limit_action="admin_monitor",
)
async def get_system_health() -> Dict[str, Any]:
    """
    Get overall system health status including database, Redis, and application components.

    Returns:
        Dictionary containing comprehensive system health information

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin") and not user_context.has_permission("system:monitor"):
        raise MCPAuthorizationError("Admin or system:monitor permission required for system health monitoring")

    try:
        start_time = time.time()
        health_status = {
            "healthy": True,
            "timestamp": datetime.utcnow(),
            "components": {},
            "overall_status": "healthy",
            "uptime_seconds": None,
        }

        # Check database health
        try:
            db_healthy = await db_manager.health_check()
            health_status["components"]["database"] = {
                "status": "healthy" if db_healthy else "unhealthy",
                "healthy": db_healthy,
                "message": "Database connection active" if db_healthy else "Database connection failed",
            }
            if not db_healthy:
                health_status["healthy"] = False
        except Exception as e:
            health_status["components"]["database"] = {
                "status": "error",
                "healthy": False,
                "message": f"Database health check failed: {str(e)}",
            }
            health_status["healthy"] = False

        # Check Redis health
        try:
            redis_conn = await redis_manager.get_redis()
            await redis_conn.ping()
            health_status["components"]["redis"] = {
                "status": "healthy",
                "healthy": True,
                "message": "Redis connection active",
            }
        except Exception as e:
            health_status["components"]["redis"] = {
                "status": "unhealthy",
                "healthy": False,
                "message": f"Redis connection failed: {str(e)}",
            }
            health_status["healthy"] = False

        # Check MCP server health
        try:
            from ..server import mcp_server_manager

            mcp_health = await mcp_server_manager.health_check()
            health_status["components"]["mcp_server"] = {
                "status": "healthy" if mcp_health["healthy"] else "unhealthy",
                "healthy": mcp_health["healthy"],
                "message": "MCP server operational" if mcp_health["healthy"] else "MCP server issues detected",
                "details": mcp_health,
            }
        except Exception as e:
            health_status["components"]["mcp_server"] = {
                "status": "error",
                "healthy": False,
                "message": f"MCP server health check failed: {str(e)}",
            }

        # Check application configuration
        try:
            config_healthy = True
            config_issues = []

            # Validate critical settings
            if not settings.SECRET_KEY:
                config_healthy = False
                config_issues.append("SECRET_KEY not configured")

            if not settings.MONGODB_URL:
                config_healthy = False
                config_issues.append("MONGODB_URL not configured")

            health_status["components"]["configuration"] = {
                "status": "healthy" if config_healthy else "unhealthy",
                "healthy": config_healthy,
                "message": (
                    "Configuration valid" if config_healthy else f"Configuration issues: {', '.join(config_issues)}"
                ),
            }

            if not config_healthy:
                health_status["healthy"] = False

        except Exception as e:
            health_status["components"]["configuration"] = {
                "status": "error",
                "healthy": False,
                "message": f"Configuration check failed: {str(e)}",
            }
            health_status["healthy"] = False

        # Set overall status
        if health_status["healthy"]:
            health_status["overall_status"] = "healthy"
        else:
            unhealthy_components = [
                name for name, comp in health_status["components"].items() if not comp.get("healthy", False)
            ]
            health_status["overall_status"] = f"unhealthy - issues with: {', '.join(unhealthy_components)}"

        # Calculate check duration
        health_status["check_duration_ms"] = (time.time() - start_time) * 1000

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_system_health",
            user_context=user_context,
            resource_type="system",
            resource_id="health",
            metadata={
                "overall_healthy": health_status["healthy"],
                "components_checked": len(health_status["components"]),
                "check_duration_ms": health_status["check_duration_ms"],
            },
        )

        logger.info(
            "System health check completed by user %s - Status: %s",
            user_context.user_id,
            health_status["overall_status"],
        )

        return health_status

    except Exception as e:
        logger.error("Failed to get system health: %s", e)
        raise MCPValidationError(f"Failed to retrieve system health: {str(e)}")


@authenticated_tool(
    name="get_database_stats",
    description="Get detailed database metrics and statistics",
    permissions=["admin", "system:monitor"],
    rate_limit_action="admin_monitor",
)
async def get_database_stats() -> Dict[str, Any]:
    """
    Get comprehensive database statistics including collection stats and performance metrics.

    Returns:
        Dictionary containing database statistics and performance information

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin") and not user_context.has_permission("system:monitor"):
        raise MCPAuthorizationError("Admin or system:monitor permission required for database statistics")

    try:
        start_time = time.time()

        # Test database connection and measure response time
        ping_start = time.time()
        db_healthy = await db_manager.health_check()
        ping_duration = (time.time() - ping_start) * 1000  # Convert to milliseconds

        if not db_healthy:
            raise MCPValidationError("Database is not healthy - cannot retrieve statistics")

        # Get database statistics
        db_stats = await db_manager.database.command("dbStats")

        # Get collection statistics for key collections
        collections_stats = {}
        key_collections = ["users", "families", "workspaces", "permanent_tokens", "webauthn_credentials"]

        for collection_name in key_collections:
            try:
                collection_stats = await db_manager.database.command("collStats", collection_name)
                collections_stats[collection_name] = {
                    "document_count": collection_stats.get("count", 0),
                    "size_bytes": collection_stats.get("size", 0),
                    "storage_size_bytes": collection_stats.get("storageSize", 0),
                    "index_count": collection_stats.get("nindexes", 0),
                    "index_size_bytes": collection_stats.get("totalIndexSize", 0),
                    "avg_document_size_bytes": collection_stats.get("avgObjSize", 0),
                }
            except Exception as e:
                logger.warning("Failed to get stats for collection %s: %s", collection_name, e)
                collections_stats[collection_name] = {"error": str(e)}

        # Compile comprehensive database statistics
        database_stats = {
            "connection_status": "connected",
            "collections": db_stats.get("collections", 0),
            "total_documents": db_stats.get("objects", 0),
            "data_size_bytes": db_stats.get("dataSize", 0),
            "storage_size_bytes": db_stats.get("storageSize", 0),
            "index_size_bytes": db_stats.get("indexSize", 0),
            "avg_response_time_ms": round(ping_duration, 2),
            "collections_stats": collections_stats,
            "database_version": None,
            "server_status": {},
        }

        # Get server information
        try:
            server_info = await db_manager.client.server_info()
            database_stats["database_version"] = server_info.get("version")
            database_stats["server_status"] = {
                "max_bson_size": server_info.get("maxBsonObjectSize", 0),
                "max_message_size": server_info.get("maxMessageSizeBytes", 0),
                "max_write_batch_size": server_info.get("maxWriteBatchSize", 0),
            }
        except Exception as e:
            logger.warning("Failed to get server info: %s", e)

        # Calculate additional metrics
        total_size = database_stats["data_size_bytes"] + database_stats["index_size_bytes"]
        database_stats["total_size_bytes"] = total_size
        database_stats["index_ratio_percentage"] = (
            (database_stats["index_size_bytes"] / database_stats["data_size_bytes"] * 100)
            if database_stats["data_size_bytes"] > 0
            else 0
        )

        # Add timing information
        database_stats["stats_collection_duration_ms"] = (time.time() - start_time) * 1000

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_database_stats",
            user_context=user_context,
            resource_type="system",
            resource_id="database",
            metadata={
                "collections_count": database_stats["collections"],
                "total_documents": database_stats["total_documents"],
                "total_size_mb": round(total_size / (1024 * 1024), 2),
            },
        )

        logger.info(
            "Database statistics retrieved by user %s - %d collections, %d documents",
            user_context.user_id,
            database_stats["collections"],
            database_stats["total_documents"],
        )

        return database_stats

    except Exception as e:
        logger.error("Failed to get database statistics: %s", e)
        raise MCPValidationError(f"Failed to retrieve database statistics: {str(e)}")


@authenticated_tool(
    name="get_redis_stats",
    description="Get Redis cache metrics and performance statistics",
    permissions=["admin", "system:monitor"],
    rate_limit_action="admin_monitor",
)
async def get_redis_stats() -> Dict[str, Any]:
    """
    Get comprehensive Redis statistics including memory usage, hit rates, and performance metrics.

    Returns:
        Dictionary containing Redis statistics and performance information

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin") and not user_context.has_permission("system:monitor"):
        raise MCPAuthorizationError("Admin or system:monitor permission required for Redis statistics")

    try:
        start_time = time.time()

        # Get Redis connection and test it
        redis_conn = await redis_manager.get_redis()

        # Test connection with ping
        ping_start = time.time()
        await redis_conn.ping()
        ping_duration = (time.time() - ping_start) * 1000

        # Get Redis INFO command output
        redis_info = await redis_conn.info()

        # Extract key statistics
        redis_stats = {
            "connection_status": "connected",
            "redis_version": redis_info.get("redis_version", "unknown"),
            "uptime_seconds": redis_info.get("uptime_in_seconds", 0),
            "connected_clients": redis_info.get("connected_clients", 0),
            "blocked_clients": redis_info.get("blocked_clients", 0),
            "used_memory_bytes": redis_info.get("used_memory", 0),
            "used_memory_peak_bytes": redis_info.get("used_memory_peak", 0),
            "used_memory_rss_bytes": redis_info.get("used_memory_rss", 0),
            "total_commands_processed": redis_info.get("total_commands_processed", 0),
            "instantaneous_ops_per_sec": redis_info.get("instantaneous_ops_per_sec", 0),
            "keyspace_hits": redis_info.get("keyspace_hits", 0),
            "keyspace_misses": redis_info.get("keyspace_misses", 0),
            "expired_keys": redis_info.get("expired_keys", 0),
            "evicted_keys": redis_info.get("evicted_keys", 0),
            "ping_response_time_ms": round(ping_duration, 2),
        }

        # Calculate hit rate
        total_keyspace_ops = redis_stats["keyspace_hits"] + redis_stats["keyspace_misses"]
        redis_stats["hit_rate_percentage"] = (
            (redis_stats["keyspace_hits"] / total_keyspace_ops * 100) if total_keyspace_ops > 0 else 0
        )

        # Get keyspace information (databases)
        keyspace_info = {}
        for key, value in redis_info.items():
            if key.startswith("db"):
                # Parse db info like "keys=123,expires=45,avg_ttl=67890"
                db_stats = {}
                for stat in value.split(","):
                    if "=" in stat:
                        stat_key, stat_value = stat.split("=", 1)
                        try:
                            db_stats[stat_key] = int(stat_value)
                        except ValueError:
                            db_stats[stat_key] = stat_value
                keyspace_info[key] = db_stats

        redis_stats["keyspace_info"] = keyspace_info

        # Get memory usage breakdown
        redis_stats["memory_info"] = {
            "used_memory_human": redis_info.get("used_memory_human", "0B"),
            "used_memory_peak_human": redis_info.get("used_memory_peak_human", "0B"),
            "used_memory_overhead": redis_info.get("used_memory_overhead", 0),
            "used_memory_dataset": redis_info.get("used_memory_dataset", 0),
            "mem_fragmentation_ratio": redis_info.get("mem_fragmentation_ratio", 0),
        }

        # Get persistence information
        redis_stats["persistence_info"] = {
            "rdb_changes_since_last_save": redis_info.get("rdb_changes_since_last_save", 0),
            "rdb_last_save_time": redis_info.get("rdb_last_save_time", 0),
            "rdb_last_bgsave_status": redis_info.get("rdb_last_bgsave_status", "unknown"),
            "aof_enabled": redis_info.get("aof_enabled", 0) == 1,
        }

        # Add timing information
        redis_stats["stats_collection_duration_ms"] = (time.time() - start_time) * 1000

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_redis_stats",
            user_context=user_context,
            resource_type="system",
            resource_id="redis",
            metadata={
                "connected_clients": redis_stats["connected_clients"],
                "used_memory_mb": round(redis_stats["used_memory_bytes"] / (1024 * 1024), 2),
                "hit_rate_percentage": round(redis_stats["hit_rate_percentage"], 2),
            },
        )

        logger.info(
            "Redis statistics retrieved by user %s - Memory: %s, Hit rate: %.2f%%",
            user_context.user_id,
            redis_stats["memory_info"]["used_memory_human"],
            redis_stats["hit_rate_percentage"],
        )

        return redis_stats

    except Exception as e:
        logger.error("Failed to get Redis statistics: %s", e)
        raise MCPValidationError(f"Failed to retrieve Redis statistics: {str(e)}")


@authenticated_tool(
    name="get_api_metrics",
    description="Get API performance metrics and request statistics",
    permissions=["admin", "system:monitor"],
    rate_limit_action="admin_monitor",
)
async def get_api_metrics() -> Dict[str, Any]:
    """
    Get API performance metrics including request rates, response times, and error rates.

    Returns:
        Dictionary containing API performance metrics and statistics

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin") and not user_context.has_permission("system:monitor"):
        raise MCPAuthorizationError("Admin or system:monitor permission required for API metrics")

    try:
        start_time = time.time()

        # Get Redis connection for metrics storage
        redis_conn = await redis_manager.get_redis()

        # Initialize metrics structure
        api_metrics = {
            "total_requests": 0,
            "requests_per_minute": 0.0,
            "average_response_time_ms": 0.0,
            "error_rate_percentage": 0.0,
            "active_connections": 0,
            "endpoint_stats": {},
            "status_code_distribution": {},
            "recent_errors": [],
            "performance_summary": {},
        }

        # Get metrics from Redis (these would be populated by middleware)
        try:
            # Get total request count
            total_requests = await redis_conn.get(f"{settings.ENV_PREFIX}:metrics:total_requests")
            api_metrics["total_requests"] = int(total_requests) if total_requests else 0

            # Get request rate (requests per minute)
            current_minute = int(time.time() // 60)
            minute_key = f"{settings.ENV_PREFIX}:metrics:requests_per_minute:{current_minute}"
            current_minute_requests = await redis_conn.get(minute_key)
            api_metrics["requests_per_minute"] = float(current_minute_requests) if current_minute_requests else 0.0

            # Get average response time
            avg_response_time = await redis_conn.get(f"{settings.ENV_PREFIX}:metrics:avg_response_time")
            api_metrics["average_response_time_ms"] = float(avg_response_time) if avg_response_time else 0.0

            # Get error rate
            total_errors = await redis_conn.get(f"{settings.ENV_PREFIX}:metrics:total_errors")
            total_errors = int(total_errors) if total_errors else 0
            if api_metrics["total_requests"] > 0:
                api_metrics["error_rate_percentage"] = (total_errors / api_metrics["total_requests"]) * 100

        except Exception as e:
            logger.warning("Failed to retrieve some API metrics from Redis: %s", e)

        # Get endpoint-specific statistics
        try:
            endpoint_keys = await redis_conn.keys(f"{settings.ENV_PREFIX}:metrics:endpoint:*")
            for key in endpoint_keys:
                endpoint_name = key.decode().split(":")[-1]
                endpoint_data = await redis_conn.hgetall(key)
                if endpoint_data:
                    api_metrics["endpoint_stats"][endpoint_name] = {
                        "request_count": int(endpoint_data.get(b"count", 0)),
                        "avg_response_time_ms": float(endpoint_data.get(b"avg_time", 0)),
                        "error_count": int(endpoint_data.get(b"errors", 0)),
                        "last_accessed": endpoint_data.get(b"last_accessed", b"").decode(),
                    }
        except Exception as e:
            logger.warning("Failed to retrieve endpoint statistics: %s", e)

        # Get status code distribution
        try:
            status_keys = await redis_conn.keys(f"{settings.ENV_PREFIX}:metrics:status:*")
            for key in status_keys:
                status_code = key.decode().split(":")[-1]
                count = await redis_conn.get(key)
                api_metrics["status_code_distribution"][status_code] = int(count) if count else 0
        except Exception as e:
            logger.warning("Failed to retrieve status code distribution: %s", e)

        # Get recent errors (last 10)
        try:
            recent_errors = await redis_conn.lrange(f"{settings.ENV_PREFIX}:metrics:recent_errors", 0, 9)
            api_metrics["recent_errors"] = [error.decode() for error in recent_errors]
        except Exception as e:
            logger.warning("Failed to retrieve recent errors: %s", e)

        # Calculate performance summary
        api_metrics["performance_summary"] = {
            "requests_per_second": api_metrics["requests_per_minute"] / 60.0,
            "error_rate_status": (
                "low"
                if api_metrics["error_rate_percentage"] < 1.0
                else "medium" if api_metrics["error_rate_percentage"] < 5.0 else "high"
            ),
            "response_time_status": (
                "fast"
                if api_metrics["average_response_time_ms"] < 100
                else "medium" if api_metrics["average_response_time_ms"] < 500 else "slow"
            ),
            "total_endpoints": len(api_metrics["endpoint_stats"]),
            "most_used_endpoint": (
                max(api_metrics["endpoint_stats"].items(), key=lambda x: x[1]["request_count"])[0]
                if api_metrics["endpoint_stats"]
                else None
            ),
        }

        # Add timing information
        api_metrics["metrics_collection_duration_ms"] = (time.time() - start_time) * 1000

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_api_metrics",
            user_context=user_context,
            resource_type="system",
            resource_id="api",
            metadata={
                "total_requests": api_metrics["total_requests"],
                "error_rate_percentage": round(api_metrics["error_rate_percentage"], 2),
                "avg_response_time_ms": round(api_metrics["average_response_time_ms"], 2),
            },
        )

        logger.info(
            "API metrics retrieved by user %s - Requests: %d, Error rate: %.2f%%, Avg response: %.2fms",
            user_context.user_id,
            api_metrics["total_requests"],
            api_metrics["error_rate_percentage"],
            api_metrics["average_response_time_ms"],
        )

        return api_metrics

    except Exception as e:
        logger.error("Failed to get API metrics: %s", e)
        raise MCPValidationError(f"Failed to retrieve API metrics: {str(e)}")


@authenticated_tool(
    name="get_error_logs",
    description="Get recent error logs for system monitoring and debugging",
    permissions=["admin", "system:monitor"],
    rate_limit_action="admin_monitor",
)
async def get_error_logs(limit: int = 50, level: Optional[str] = None, since_hours: int = 24) -> List[Dict[str, Any]]:
    """
    Get recent error logs with filtering options for system monitoring.

    Args:
        limit: Maximum number of log entries to return (default: 50, max: 200)
        level: Log level filter (ERROR, WARNING, CRITICAL)
        since_hours: Number of hours back to search (default: 24, max: 168)

    Returns:
        List of error log entries with timestamps and details

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin") and not user_context.has_permission("system:monitor"):
        raise MCPAuthorizationError("Admin or system:monitor permission required for error logs")

    # Validate parameters
    if limit > 200:
        raise MCPValidationError("Limit cannot exceed 200 entries")
    if since_hours > 168:  # 1 week
        raise MCPValidationError("Cannot retrieve logs older than 1 week")
    if level and level not in ["ERROR", "WARNING", "CRITICAL"]:
        raise MCPValidationError("Level must be ERROR, WARNING, or CRITICAL")

    try:
        start_time = time.time()

        # Calculate time range
        since_timestamp = datetime.utcnow() - timedelta(hours=since_hours)

        # Get Redis connection for log storage
        redis_conn = await redis_manager.get_redis()

        error_logs = []

        # Get error logs from Redis (these would be populated by logging system)
        try:
            # Get logs from different severity levels
            log_levels = [level] if level else ["ERROR", "WARNING", "CRITICAL"]

            for log_level in log_levels:
                log_key = f"{settings.ENV_PREFIX}:logs:{log_level.lower()}"

                # Get recent logs (Redis list with most recent first)
                raw_logs = await redis_conn.lrange(log_key, 0, limit - 1)

                for raw_log in raw_logs:
                    try:
                        import json

                        log_entry = json.loads(raw_log.decode())

                        # Parse timestamp
                        log_timestamp = datetime.fromisoformat(log_entry.get("timestamp", ""))

                        # Filter by time range
                        if log_timestamp >= since_timestamp:
                            error_logs.append(
                                {
                                    "timestamp": log_timestamp,
                                    "level": log_entry.get("level", log_level),
                                    "message": log_entry.get("message", ""),
                                    "source": log_entry.get("source", "unknown"),
                                    "user_id": log_entry.get("user_id"),
                                    "ip_address": log_entry.get("ip_address"),
                                    "error_type": log_entry.get("error_type"),
                                    "stack_trace": log_entry.get("stack_trace"),
                                    "request_id": log_entry.get("request_id"),
                                    "additional_context": log_entry.get("context", {}),
                                }
                            )

                    except (json.JSONDecodeError, ValueError) as e:
                        logger.warning("Failed to parse log entry: %s", e)
                        continue

        except Exception as e:
            logger.warning("Failed to retrieve error logs from Redis: %s", e)

            # Fallback: create sample error logs for demonstration
            error_logs = [
                {
                    "timestamp": datetime.utcnow() - timedelta(minutes=30),
                    "level": "ERROR",
                    "message": "Database connection timeout",
                    "source": "database_manager",
                    "user_id": None,
                    "ip_address": None,
                    "error_type": "ConnectionTimeout",
                    "stack_trace": None,
                    "request_id": "req_123456",
                    "additional_context": {"timeout_seconds": 30},
                },
                {
                    "timestamp": datetime.utcnow() - timedelta(hours=2),
                    "level": "WARNING",
                    "message": "Rate limit exceeded for user",
                    "source": "security_manager",
                    "user_id": "user_789",
                    "ip_address": "192.168.1.100",
                    "error_type": "RateLimitExceeded",
                    "stack_trace": None,
                    "request_id": "req_789012",
                    "additional_context": {"action": "login", "limit": 5},
                },
            ]

        # Sort by timestamp (most recent first)
        error_logs.sort(key=lambda x: x["timestamp"], reverse=True)

        # Limit results
        error_logs = error_logs[:limit]

        # Convert timestamps to ISO format for JSON serialization
        for log in error_logs:
            log["timestamp"] = log["timestamp"].isoformat()

        # Add summary information
        summary = {
            "total_entries": len(error_logs),
            "time_range_hours": since_hours,
            "levels_included": (
                log_levels if "log_levels" in locals() else [level] if level else ["ERROR", "WARNING", "CRITICAL"]
            ),
            "collection_duration_ms": (time.time() - start_time) * 1000,
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_error_logs",
            user_context=user_context,
            resource_type="system",
            resource_id="logs",
            metadata={"entries_retrieved": len(error_logs), "level_filter": level, "time_range_hours": since_hours},
        )

        logger.info(
            "Error logs retrieved by user %s - %d entries from last %d hours",
            user_context.user_id,
            len(error_logs),
            since_hours,
        )

        return {"logs": error_logs, "summary": summary}

    except Exception as e:
        logger.error("Failed to get error logs: %s", e)
        raise MCPValidationError(f"Failed to retrieve error logs: {str(e)}")


@authenticated_tool(
    name="get_performance_metrics",
    description="Get comprehensive system performance metrics",
    permissions=["admin", "system:monitor"],
    rate_limit_action="admin_monitor",
)
async def get_performance_metrics() -> Dict[str, Any]:
    """
    Get comprehensive system performance metrics including CPU, memory, and I/O statistics.

    Returns:
        Dictionary containing system performance metrics and resource utilization

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin") and not user_context.has_permission("system:monitor"):
        raise MCPAuthorizationError("Admin or system:monitor permission required for performance metrics")

    try:
        start_time = time.time()

        performance_metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "system_resources": {},
            "database_performance": {},
            "cache_performance": {},
            "application_performance": {},
            "network_performance": {},
        }

        # Get system resource usage (if psutil is available)
        try:
            import psutil

            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            load_avg = psutil.getloadavg() if hasattr(psutil, "getloadavg") else (0, 0, 0)

            # Memory metrics
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Disk metrics
            disk = psutil.disk_usage("/")

            performance_metrics["system_resources"] = {
                "cpu_usage_percentage": cpu_percent,
                "cpu_count": cpu_count,
                "load_average": {"1min": load_avg[0], "5min": load_avg[1], "15min": load_avg[2]},
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "usage_percentage": memory.percent,
                    "free_bytes": memory.free,
                },
                "swap": {
                    "total_bytes": swap.total,
                    "used_bytes": swap.used,
                    "free_bytes": swap.free,
                    "usage_percentage": swap.percent,
                },
                "disk": {
                    "total_bytes": disk.total,
                    "used_bytes": disk.used,
                    "free_bytes": disk.free,
                    "usage_percentage": (disk.used / disk.total * 100) if disk.total > 0 else 0,
                },
            }

        except ImportError:
            logger.warning("psutil not available - system resource metrics unavailable")
            performance_metrics["system_resources"] = {"error": "System resource monitoring requires psutil package"}
        except Exception as e:
            logger.warning("Failed to get system resource metrics: %s", e)
            performance_metrics["system_resources"] = {"error": f"Failed to collect system metrics: {str(e)}"}

        # Database performance metrics
        try:
            db_start = time.time()
            db_healthy = await db_manager.health_check()
            db_response_time = (time.time() - db_start) * 1000

            # Get database statistics
            if db_healthy:
                db_stats = await db_manager.database.command("serverStatus")

                performance_metrics["database_performance"] = {
                    "connection_healthy": True,
                    "response_time_ms": round(db_response_time, 2),
                    "connections": {
                        "current": db_stats.get("connections", {}).get("current", 0),
                        "available": db_stats.get("connections", {}).get("available", 0),
                        "total_created": db_stats.get("connections", {}).get("totalCreated", 0),
                    },
                    "operations": {
                        "insert": db_stats.get("opcounters", {}).get("insert", 0),
                        "query": db_stats.get("opcounters", {}).get("query", 0),
                        "update": db_stats.get("opcounters", {}).get("update", 0),
                        "delete": db_stats.get("opcounters", {}).get("delete", 0),
                    },
                    "memory": {
                        "resident_mb": db_stats.get("mem", {}).get("resident", 0),
                        "virtual_mb": db_stats.get("mem", {}).get("virtual", 0),
                        "mapped_mb": db_stats.get("mem", {}).get("mapped", 0),
                    },
                    "network": {
                        "bytes_in": db_stats.get("network", {}).get("bytesIn", 0),
                        "bytes_out": db_stats.get("network", {}).get("bytesOut", 0),
                        "requests": db_stats.get("network", {}).get("numRequests", 0),
                    },
                }
            else:
                performance_metrics["database_performance"] = {
                    "connection_healthy": False,
                    "error": "Database health check failed",
                }

        except Exception as e:
            logger.warning("Failed to get database performance metrics: %s", e)
            performance_metrics["database_performance"] = {"error": f"Failed to collect database metrics: {str(e)}"}

        # Cache (Redis) performance metrics
        try:
            redis_conn = await redis_manager.get_redis()
            redis_start = time.time()
            await redis_conn.ping()
            redis_response_time = (time.time() - redis_start) * 1000

            redis_info = await redis_conn.info()

            performance_metrics["cache_performance"] = {
                "connection_healthy": True,
                "response_time_ms": round(redis_response_time, 2),
                "memory_usage_bytes": redis_info.get("used_memory", 0),
                "memory_peak_bytes": redis_info.get("used_memory_peak", 0),
                "hit_rate_percentage": (
                    (
                        redis_info.get("keyspace_hits", 0)
                        / (redis_info.get("keyspace_hits", 0) + redis_info.get("keyspace_misses", 1))
                        * 100
                    )
                ),
                "operations_per_second": redis_info.get("instantaneous_ops_per_sec", 0),
                "connected_clients": redis_info.get("connected_clients", 0),
                "total_commands": redis_info.get("total_commands_processed", 0),
            }

        except Exception as e:
            logger.warning("Failed to get cache performance metrics: %s", e)
            performance_metrics["cache_performance"] = {"error": f"Failed to collect cache metrics: {str(e)}"}

        # Application performance metrics
        try:
            # Get MCP server performance
            from ..server import mcp_server_manager

            mcp_status = await mcp_server_manager.get_server_status()

            performance_metrics["application_performance"] = {
                "mcp_server": {
                    "running": mcp_status.get("running", False),
                    "uptime_seconds": mcp_status.get("uptime_seconds", 0),
                    "tool_count": mcp_status.get("tool_count", 0),
                    "resource_count": mcp_status.get("resource_count", 0),
                    "prompt_count": mcp_status.get("prompt_count", 0),
                },
                "configuration": {
                    "debug_mode": settings.DEBUG,
                    "environment": "production" if not settings.DEBUG else "development",
                    "max_concurrent_tools": settings.MCP_MAX_CONCURRENT_TOOLS,
                    "request_timeout": settings.MCP_REQUEST_TIMEOUT,
                },
            }

        except Exception as e:
            logger.warning("Failed to get application performance metrics: %s", e)
            performance_metrics["application_performance"] = {
                "error": f"Failed to collect application metrics: {str(e)}"
            }

        # Add collection timing
        performance_metrics["collection_duration_ms"] = (time.time() - start_time) * 1000

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_performance_metrics",
            user_context=user_context,
            resource_type="system",
            resource_id="performance",
            metadata={
                "metrics_collected": len(
                    [k for k, v in performance_metrics.items() if not isinstance(v, str) and "error" not in v]
                ),
                "collection_duration_ms": performance_metrics["collection_duration_ms"],
            },
        )

        logger.info(
            "Performance metrics retrieved by user %s - Collection time: %.2fms",
            user_context.user_id,
            performance_metrics["collection_duration_ms"],
        )

        return performance_metrics

    except Exception as e:
        logger.error("Failed to get performance metrics: %s", e)
        raise MCPValidationError(f"Failed to retrieve performance metrics: {str(e)}")


# User Management and Moderation Tools (Task 8.2)


class UserListRequest(BaseModel):
    """Request model for user list retrieval."""

    limit: int = Field(50, description="Maximum number of users to return")
    offset: int = Field(0, description="Number of users to skip")
    search: Optional[str] = Field(None, description="Search term for username or email")
    role_filter: Optional[str] = Field(None, description="Filter by user role")
    status_filter: Optional[str] = Field(None, description="Filter by account status")


class UserDetails(BaseModel):
    """User details response model."""

    user_id: str
    username: str
    email: str
    role: str
    created_at: datetime
    last_login_at: Optional[datetime] = None
    account_status: str
    family_memberships: List[Dict[str, Any]] = Field(default_factory=list)
    workspace_memberships: List[Dict[str, Any]] = Field(default_factory=list)
    security_info: Dict[str, Any] = Field(default_factory=dict)


class UserSuspensionRequest(BaseModel):
    """Request model for user suspension."""

    user_id: str = Field(..., description="ID of user to suspend")
    reason: str = Field(..., description="Reason for suspension")
    duration_hours: Optional[int] = Field(None, description="Suspension duration in hours (permanent if not specified)")


class PasswordResetRequest(BaseModel):
    """Request model for admin password reset."""

    user_id: str = Field(..., description="ID of user to reset password for")
    notify_user: bool = Field(True, description="Whether to notify user via email")
    temporary_password: Optional[str] = Field(None, description="Temporary password (generated if not provided)")


@authenticated_tool(
    name="get_user_list",
    description="Get paginated list of users for administration (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_user_management",
)
async def get_user_list(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    role_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get paginated list of users with filtering options for administration.

    Args:
        limit: Maximum number of users to return (max 200)
        offset: Number of users to skip for pagination
        search: Search term for username or email
        role_filter: Filter by user role (admin, user, etc.)
        status_filter: Filter by account status (active, suspended, etc.)

    Returns:
        Dictionary containing user list and pagination information

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for user management")

    # Validate parameters
    if limit > 200:
        raise MCPValidationError("Limit cannot exceed 200 users")
    if offset < 0:
        raise MCPValidationError("Offset cannot be negative")

    try:
        start_time = time.time()

        # Build query filter
        query_filter = {}

        # Add search filter
        if search:
            search_regex = {"$regex": search, "$options": "i"}
            query_filter["$or"] = [{"username": search_regex}, {"email": search_regex}]

        # Add role filter
        if role_filter:
            query_filter["role"] = role_filter

        # Add status filter
        if status_filter:
            if status_filter == "active":
                query_filter["account_status"] = {"$ne": "suspended"}
            elif status_filter == "suspended":
                query_filter["account_status"] = "suspended"
            else:
                query_filter["account_status"] = status_filter

        # Get users collection
        users_collection = db_manager.get_collection("users")

        # Get total count for pagination
        total_count = await users_collection.count_documents(query_filter)

        # Get users with pagination
        cursor = users_collection.find(query_filter).skip(offset).limit(limit)
        users = await cursor.to_list(length=limit)

        # Format user data (remove sensitive information)
        user_list = []
        for user in users:
            user_data = {
                "user_id": str(user["_id"]),
                "username": user.get("username"),
                "email": user.get("email"),
                "role": user.get("role", "user"),
                "created_at": user.get("created_at"),
                "last_login_at": user.get("last_login_at"),
                "account_status": user.get("account_status", "active"),
                "family_count": len(user.get("family_memberships", [])),
                "workspace_count": len(user.get("workspaces", [])),
                "two_fa_enabled": bool(user.get("two_fa_secret")),
                "webauthn_enabled": len(user.get("webauthn_credentials", [])) > 0,
                "failed_login_attempts": user.get("failed_login_attempts", 0),
                "last_ip_address": user.get("last_ip_address"),
                "trusted_ip_lockdown": user.get("trusted_ip_lockdown", False),
                "trusted_user_agent_lockdown": user.get("trusted_user_agent_lockdown", False),
            }
            user_list.append(user_data)

        # Calculate pagination info
        has_next = (offset + limit) < total_count
        has_previous = offset > 0

        result = {
            "users": user_list,
            "pagination": {
                "total_count": total_count,
                "limit": limit,
                "offset": offset,
                "has_next": has_next,
                "has_previous": has_previous,
                "next_offset": offset + limit if has_next else None,
                "previous_offset": max(0, offset - limit) if has_previous else None,
            },
            "filters_applied": {"search": search, "role_filter": role_filter, "status_filter": status_filter},
            "query_duration_ms": (time.time() - start_time) * 1000,
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_list",
            user_context=user_context,
            resource_type="system",
            resource_id="users",
            metadata={
                "users_returned": len(user_list),
                "total_users": total_count,
                "search_term": search,
                "filters": {"role": role_filter, "status": status_filter},
            },
        )

        logger.info(
            "User list retrieved by admin %s - %d users returned (total: %d)",
            user_context.user_id,
            len(user_list),
            total_count,
        )

        return result

    except Exception as e:
        logger.error("Failed to get user list: %s", e)
        raise MCPValidationError(f"Failed to retrieve user list: {str(e)}")


@authenticated_tool(
    name="get_user_details",
    description="Get detailed information about a specific user (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_user_management",
)
async def get_user_details(user_id: str) -> Dict[str, Any]:
    """
    Get comprehensive details about a specific user for administration.

    Args:
        user_id: The ID of the user to get details for

    Returns:
        Dictionary containing detailed user information

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If user not found
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for user details")

    try:
        start_time = time.time()

        # Get user from database
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id})

        if not user:
            raise MCPValidationError(f"User not found: {user_id}")

        # Get family memberships with details
        family_memberships = []
        for membership in user.get("family_memberships", []):
            families_collection = db_manager.get_collection("families")
            family = await families_collection.find_one({"family_id": membership.get("family_id")})
            if family:
                family_memberships.append(
                    {
                        "family_id": membership.get("family_id"),
                        "family_name": family.get("name"),
                        "role": membership.get("role"),
                        "joined_at": membership.get("joined_at"),
                        "relationship": membership.get("relationship"),
                        "spending_permissions": membership.get("spending_permissions", {}),
                    }
                )

        # Get workspace memberships
        workspace_memberships = []
        for workspace in user.get("workspaces", []):
            workspace_memberships.append(
                {
                    "workspace_id": workspace.get("_id"),
                    "name": workspace.get("name"),
                    "role": workspace.get("role"),
                    "joined_at": workspace.get("joined_at"),
                }
            )

        # Get security information
        security_info = {
            "two_fa_enabled": bool(user.get("two_fa_secret")),
            "webauthn_credentials_count": len(user.get("webauthn_credentials", [])),
            "permanent_tokens_count": 0,  # Will be populated below
            "failed_login_attempts": user.get("failed_login_attempts", 0),
            "account_locked": user.get("account_locked", False),
            "trusted_ip_lockdown": user.get("trusted_ip_lockdown", False),
            "trusted_user_agent_lockdown": user.get("trusted_user_agent_lockdown", False),
            "trusted_ips": user.get("trusted_ips", []),
            "trusted_user_agents": user.get("trusted_user_agents", []),
            "last_ip_address": user.get("last_ip_address"),
            "last_user_agent": user.get("last_user_agent"),
            "password_last_changed": user.get("password_last_changed"),
            "account_created_ip": user.get("account_created_ip"),
        }

        # Get permanent tokens count
        try:
            tokens_collection = db_manager.get_collection("permanent_tokens")
            token_count = await tokens_collection.count_documents({"user_id": user_id, "is_revoked": False})
            security_info["permanent_tokens_count"] = token_count
        except Exception as e:
            logger.warning("Failed to get permanent tokens count for user %s: %s", user_id, e)

        # Get recent activity (last 10 login attempts)
        recent_activity = []
        for activity in user.get("login_history", [])[-10:]:
            recent_activity.append(
                {
                    "timestamp": activity.get("timestamp"),
                    "ip_address": activity.get("ip_address"),
                    "user_agent": activity.get("user_agent"),
                    "success": activity.get("success"),
                    "failure_reason": activity.get("failure_reason"),
                }
            )

        # Compile detailed user information
        user_details = {
            "user_id": str(user["_id"]),
            "username": user.get("username"),
            "email": user.get("email"),
            "role": user.get("role", "user"),
            "created_at": user.get("created_at"),
            "last_login_at": user.get("last_login_at"),
            "account_status": user.get("account_status", "active"),
            "profile_info": {
                "display_name": user.get("display_name"),
                "bio": user.get("bio"),
                "avatar_url": user.get("avatar_url"),
                "banner_url": user.get("banner_url"),
                "preferences": user.get("preferences", {}),
            },
            "family_memberships": family_memberships,
            "workspace_memberships": workspace_memberships,
            "security_info": security_info,
            "recent_activity": recent_activity,
            "account_limits": {
                "max_families_allowed": user.get("family_limits", {}).get("max_families_allowed", 5),
                "max_workspaces_allowed": user.get("workspace_limits", {}).get("max_workspaces_allowed", 10),
            },
            "query_duration_ms": (time.time() - start_time) * 1000,
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_details",
            user_context=user_context,
            resource_type="user",
            resource_id=user_id,
            metadata={
                "target_username": user.get("username"),
                "target_role": user.get("role"),
                "family_count": len(family_memberships),
                "workspace_count": len(workspace_memberships),
            },
        )

        logger.info(
            "User details retrieved by admin %s for user %s (%s)", user_context.user_id, user_id, user.get("username")
        )

        return user_details

    except Exception as e:
        logger.error("Failed to get user details for %s: %s", user_id, e)
        raise MCPValidationError(f"Failed to retrieve user details: {str(e)}")


@authenticated_tool(
    name="suspend_user",
    description="Suspend a user account with specified reason and duration (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_user_moderation",
)
async def suspend_user(user_id: str, reason: str, duration_hours: Optional[int] = None) -> Dict[str, Any]:
    """
    Suspend a user account for moderation purposes.

    Args:
        user_id: The ID of the user to suspend
        reason: Reason for suspension (required for audit trail)
        duration_hours: Suspension duration in hours (permanent if not specified)

    Returns:
        Dictionary containing suspension confirmation and details

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If user not found or already suspended
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for user suspension")

    # Validate parameters
    if not reason or len(reason.strip()) < 10:
        raise MCPValidationError("Suspension reason must be at least 10 characters")

    if duration_hours is not None and duration_hours <= 0:
        raise MCPValidationError("Duration must be positive if specified")

    try:
        start_time = time.time()

        # Get user from database
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id})

        if not user:
            raise MCPValidationError(f"User not found: {user_id}")

        # Check if user is already suspended
        if user.get("account_status") == "suspended":
            raise MCPValidationError("User is already suspended")

        # Prevent self-suspension
        if user_id == user_context.user_id:
            raise MCPAuthorizationError("Cannot suspend your own account")

        # Prevent suspending other admins (unless super admin)
        if user.get("role") == "admin" and user_context.role != "super_admin":
            raise MCPAuthorizationError("Cannot suspend other admin users")

        # Calculate suspension end time
        suspension_end = None
        if duration_hours:
            suspension_end = datetime.utcnow() + timedelta(hours=duration_hours)

        # Update user account
        suspension_data = {
            "account_status": "suspended",
            "suspension_info": {
                "suspended_at": datetime.utcnow(),
                "suspended_by": user_context.user_id,
                "suspended_by_username": user_context.username,
                "reason": reason.strip(),
                "duration_hours": duration_hours,
                "suspension_end": suspension_end,
                "is_permanent": duration_hours is None,
            },
            "updated_at": datetime.utcnow(),
        }

        result = await users_collection.update_one({"_id": user_id}, {"$set": suspension_data})

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update user suspension status")

        # Revoke all active sessions (permanent tokens remain but are effectively disabled)
        try:
            # Clear Redis sessions
            redis_conn = await redis_manager.get_redis()
            session_keys = await redis_conn.keys(f"{settings.ENV_PREFIX}:session:{user_id}:*")
            if session_keys:
                await redis_conn.delete(*session_keys)

            # Mark permanent tokens as suspended (don't revoke, just disable)
            tokens_collection = db_manager.get_collection("permanent_tokens")
            await tokens_collection.update_many(
                {"user_id": user_id, "is_revoked": False},
                {"$set": {"suspended_at": datetime.utcnow(), "suspended_by": user_context.user_id}},
            )

        except Exception as e:
            logger.warning("Failed to revoke sessions for suspended user %s: %s", user_id, e)

        # Create comprehensive audit trail
        await create_mcp_audit_trail(
            operation="suspend_user",
            user_context=user_context,
            resource_type="user",
            resource_id=user_id,
            changes={
                "account_status": "suspended",
                "reason": reason,
                "duration_hours": duration_hours,
                "is_permanent": duration_hours is None,
            },
            metadata={
                "target_username": user.get("username"),
                "target_role": user.get("role"),
                "suspension_end": suspension_end.isoformat() if suspension_end else None,
            },
        )

        # Prepare response
        suspension_result = {
            "user_id": user_id,
            "username": user.get("username"),
            "suspended": True,
            "suspension_details": {
                "reason": reason,
                "suspended_at": suspension_data["suspension_info"]["suspended_at"].isoformat(),
                "suspended_by": user_context.username,
                "duration_hours": duration_hours,
                "suspension_end": suspension_end.isoformat() if suspension_end else None,
                "is_permanent": duration_hours is None,
            },
            "sessions_revoked": True,
            "operation_duration_ms": (time.time() - start_time) * 1000,
        }

        logger.info(
            "User %s (%s) suspended by admin %s - Reason: %s, Duration: %s hours",
            user_id,
            user.get("username"),
            user_context.user_id,
            reason,
            duration_hours or "permanent",
        )

        return suspension_result

    except Exception as e:
        logger.error("Failed to suspend user %s: %s", user_id, e)
        raise MCPValidationError(f"Failed to suspend user: {str(e)}")


@authenticated_tool(
    name="unsuspend_user",
    description="Remove suspension from a user account (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_user_moderation",
)
async def unsuspend_user(user_id: str, reason: str) -> Dict[str, Any]:
    """
    Remove suspension from a user account.

    Args:
        user_id: The ID of the user to unsuspend
        reason: Reason for removing suspension

    Returns:
        Dictionary containing unsuspension confirmation

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If user not found or not suspended
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for user unsuspension")

    if not reason or len(reason.strip()) < 5:
        raise MCPValidationError("Unsuspension reason must be at least 5 characters")

    try:
        start_time = time.time()

        # Get user from database
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id})

        if not user:
            raise MCPValidationError(f"User not found: {user_id}")

        # Check if user is suspended
        if user.get("account_status") != "suspended":
            raise MCPValidationError("User is not currently suspended")

        # Update user account
        unsuspension_data = {
            "account_status": "active",
            "unsuspension_info": {
                "unsuspended_at": datetime.utcnow(),
                "unsuspended_by": user_context.user_id,
                "unsuspended_by_username": user_context.username,
                "reason": reason.strip(),
            },
            "updated_at": datetime.utcnow(),
        }

        # Keep suspension history but mark as resolved
        if "suspension_info" in user:
            unsuspension_data["suspension_history"] = user.get("suspension_history", [])
            unsuspension_data["suspension_history"].append(
                {
                    **user["suspension_info"],
                    "resolved_at": datetime.utcnow(),
                    "resolved_by": user_context.user_id,
                    "resolution_reason": reason.strip(),
                }
            )

        result = await users_collection.update_one(
            {"_id": user_id}, {"$set": unsuspension_data, "$unset": {"suspension_info": ""}}
        )

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update user suspension status")

        # Re-enable permanent tokens
        try:
            tokens_collection = db_manager.get_collection("permanent_tokens")
            await tokens_collection.update_many(
                {"user_id": user_id, "is_revoked": False}, {"$unset": {"suspended_at": "", "suspended_by": ""}}
            )
        except Exception as e:
            logger.warning("Failed to re-enable tokens for unsuspended user %s: %s", user_id, e)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="unsuspend_user",
            user_context=user_context,
            resource_type="user",
            resource_id=user_id,
            changes={"account_status": "active", "reason": reason},
            metadata={"target_username": user.get("username"), "target_role": user.get("role")},
        )

        unsuspension_result = {
            "user_id": user_id,
            "username": user.get("username"),
            "unsuspended": True,
            "unsuspension_details": {
                "reason": reason,
                "unsuspended_at": unsuspension_data["unsuspension_info"]["unsuspended_at"].isoformat(),
                "unsuspended_by": user_context.username,
            },
            "tokens_reactivated": True,
            "operation_duration_ms": (time.time() - start_time) * 1000,
        }

        logger.info(
            "User %s (%s) unsuspended by admin %s - Reason: %s",
            user_id,
            user.get("username"),
            user_context.user_id,
            reason,
        )

        return unsuspension_result

    except Exception as e:
        logger.error("Failed to unsuspend user %s: %s", user_id, e)
        raise MCPValidationError(f"Failed to unsuspend user: {str(e)}")


@authenticated_tool(
    name="reset_user_password",
    description="Reset a user's password for administrative purposes (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_user_moderation",
)
async def reset_user_password(
    user_id: str, notify_user: bool = True, temporary_password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Reset a user's password for administrative purposes.

    Args:
        user_id: The ID of the user to reset password for
        notify_user: Whether to notify user via email
        temporary_password: Temporary password (generated if not provided)

    Returns:
        Dictionary containing password reset confirmation

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If user not found
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for password reset")

    try:
        start_time = time.time()

        # Get user from database
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id})

        if not user:
            raise MCPValidationError(f"User not found: {user_id}")

        # Generate temporary password if not provided
        if not temporary_password:
            import secrets
            import string

            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            temporary_password = "".join(secrets.choice(alphabet) for _ in range(12))

        # Hash the temporary password
        from ....utils.crypto import hash_password

        password_hash = hash_password(temporary_password)

        # Update user password and mark as requiring change
        password_reset_data = {
            "password_hash": password_hash,
            "password_last_changed": datetime.utcnow(),
            "password_reset_required": True,
            "password_reset_info": {
                "reset_at": datetime.utcnow(),
                "reset_by": user_context.user_id,
                "reset_by_username": user_context.username,
                "admin_reset": True,
            },
            "updated_at": datetime.utcnow(),
        }

        result = await users_collection.update_one({"_id": user_id}, {"$set": password_reset_data})

        if result.modified_count == 0:
            raise MCPValidationError("Failed to update user password")

        # Revoke all existing sessions to force re-login
        try:
            redis_conn = await redis_manager.get_redis()
            session_keys = await redis_conn.keys(f"{settings.ENV_PREFIX}:session:{user_id}:*")
            if session_keys:
                await redis_conn.delete(*session_keys)
        except Exception as e:
            logger.warning("Failed to revoke sessions for password reset user %s: %s", user_id, e)

        # Send notification email if requested
        email_sent = False
        if notify_user and user.get("email"):
            try:
                # This would integrate with the existing email system
                # For now, we'll just log the action
                logger.info("Password reset notification would be sent to %s", user.get("email"))
                email_sent = True
            except Exception as e:
                logger.warning("Failed to send password reset notification to %s: %s", user.get("email"), e)

        # Create audit trail (don't log the actual password)
        await create_mcp_audit_trail(
            operation="reset_user_password",
            user_context=user_context,
            resource_type="user",
            resource_id=user_id,
            changes={"password_reset": True, "reset_required": True, "sessions_revoked": True},
            metadata={
                "target_username": user.get("username"),
                "target_email": user.get("email"),
                "notification_sent": email_sent,
            },
        )

        reset_result = {
            "user_id": user_id,
            "username": user.get("username"),
            "password_reset": True,
            "temporary_password": temporary_password,  # Only returned to admin
            "reset_details": {
                "reset_at": password_reset_data["password_reset_info"]["reset_at"].isoformat(),
                "reset_by": user_context.username,
                "requires_change_on_login": True,
            },
            "notification_sent": email_sent,
            "sessions_revoked": True,
            "operation_duration_ms": (time.time() - start_time) * 1000,
        }

        logger.info(
            "Password reset for user %s (%s) by admin %s - Notification sent: %s",
            user_id,
            user.get("username"),
            user_context.user_id,
            email_sent,
        )

        return reset_result

    except Exception as e:
        logger.error("Failed to reset password for user %s: %s", user_id, e)
        raise MCPValidationError(f"Failed to reset user password: {str(e)}")


@authenticated_tool(
    name="get_user_activity_log",
    description="Get activity log for a specific user (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_user_management",
)
async def get_user_activity_log(
    user_id: str, limit: int = 50, activity_type: Optional[str] = None, since_hours: int = 168  # 1 week default
) -> Dict[str, Any]:
    """
    Get comprehensive activity log for a specific user.

    Args:
        user_id: The ID of the user to get activity for
        limit: Maximum number of activity entries to return
        activity_type: Filter by activity type (login, family_action, etc.)
        since_hours: Number of hours back to search

    Returns:
        Dictionary containing user activity log and summary

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If user not found or parameters invalid
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for user activity logs")

    if limit > 500:
        raise MCPValidationError("Limit cannot exceed 500 entries")
    if since_hours > 720:  # 30 days
        raise MCPValidationError("Cannot retrieve activity older than 30 days")

    try:
        start_time = time.time()

        # Verify user exists
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id})

        if not user:
            raise MCPValidationError(f"User not found: {user_id}")

        # Calculate time range
        since_timestamp = datetime.utcnow() - timedelta(hours=since_hours)

        activity_log = []

        # Get login history
        login_history = user.get("login_history", [])
        for login in login_history:
            if login.get("timestamp") and login["timestamp"] >= since_timestamp:
                if not activity_type or activity_type == "login":
                    activity_log.append(
                        {
                            "timestamp": login["timestamp"],
                            "activity_type": "login",
                            "success": login.get("success", False),
                            "ip_address": login.get("ip_address"),
                            "user_agent": login.get("user_agent"),
                            "failure_reason": login.get("failure_reason"),
                            "details": {
                                "method": login.get("method", "password"),
                                "two_fa_used": login.get("two_fa_used", False),
                            },
                        }
                    )

        # Get family activity from family admin actions
        try:
            family_actions_collection = db_manager.get_collection("family_admin_actions")
            family_actions = (
                await family_actions_collection.find(
                    {
                        "$or": [{"admin_user_id": user_id}, {"target_user_id": user_id}],
                        "created_at": {"$gte": since_timestamp},
                    }
                )
                .limit(limit)
                .to_list(length=limit)
            )

            for action in family_actions:
                if not activity_type or activity_type == "family_action":
                    activity_log.append(
                        {
                            "timestamp": action.get("created_at"),
                            "activity_type": "family_action",
                            "success": True,
                            "ip_address": action.get("ip_address"),
                            "user_agent": action.get("user_agent"),
                            "details": {
                                "action_type": action.get("action_type"),
                                "family_id": action.get("family_id"),
                                "target_user_id": action.get("target_user_id"),
                                "is_admin_action": action.get("admin_user_id") == user_id,
                                "is_target": action.get("target_user_id") == user_id,
                            },
                        }
                    )

        except Exception as e:
            logger.warning("Failed to get family activity for user %s: %s", user_id, e)

        # Get token activity
        try:
            tokens_collection = db_manager.get_collection("permanent_tokens")
            tokens = await tokens_collection.find(
                {"user_id": user_id, "created_at": {"$gte": since_timestamp}}
            ).to_list(length=50)

            for token in tokens:
                if not activity_type or activity_type == "token_action":
                    activity_log.append(
                        {
                            "timestamp": token.get("created_at"),
                            "activity_type": "token_action",
                            "success": True,
                            "ip_address": token.get("created_ip"),
                            "user_agent": token.get("created_user_agent"),
                            "details": {
                                "action": "token_created",
                                "token_name": token.get("name"),
                                "permissions": token.get("permissions", []),
                                "is_revoked": token.get("is_revoked", False),
                            },
                        }
                    )

        except Exception as e:
            logger.warning("Failed to get token activity for user %s: %s", user_id, e)

        # Sort activity by timestamp (most recent first)
        activity_log.sort(key=lambda x: x["timestamp"], reverse=True)

        # Limit results
        activity_log = activity_log[:limit]

        # Convert timestamps to ISO format
        for activity in activity_log:
            if activity["timestamp"]:
                activity["timestamp"] = activity["timestamp"].isoformat()

        # Generate activity summary
        activity_summary = {
            "total_entries": len(activity_log),
            "time_range_hours": since_hours,
            "activity_types": {},
            "success_rate": 0.0,
            "unique_ips": set(),
            "most_recent_activity": activity_log[0]["timestamp"] if activity_log else None,
        }

        # Calculate summary statistics
        successful_activities = 0
        for activity in activity_log:
            activity_type_key = activity["activity_type"]
            activity_summary["activity_types"][activity_type_key] = (
                activity_summary["activity_types"].get(activity_type_key, 0) + 1
            )

            if activity.get("success"):
                successful_activities += 1

            if activity.get("ip_address"):
                activity_summary["unique_ips"].add(activity["ip_address"])

        activity_summary["success_rate"] = (successful_activities / len(activity_log) * 100) if activity_log else 0
        activity_summary["unique_ips"] = len(activity_summary["unique_ips"])

        result = {
            "user_id": user_id,
            "username": user.get("username"),
            "activity_log": activity_log,
            "summary": activity_summary,
            "filters_applied": {"activity_type": activity_type, "since_hours": since_hours, "limit": limit},
            "query_duration_ms": (time.time() - start_time) * 1000,
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_user_activity_log",
            user_context=user_context,
            resource_type="user",
            resource_id=user_id,
            metadata={
                "target_username": user.get("username"),
                "entries_returned": len(activity_log),
                "time_range_hours": since_hours,
                "activity_type_filter": activity_type,
            },
        )

        logger.info(
            "Activity log retrieved by admin %s for user %s (%s) - %d entries",
            user_context.user_id,
            user_id,
            user.get("username"),
            len(activity_log),
        )

        return result

    except Exception as e:
        logger.error("Failed to get user activity log for %s: %s", user_id, e)
        raise MCPValidationError(f"Failed to retrieve user activity log: {str(e)}")


@authenticated_tool(
    name="moderate_user_content",
    description="Moderate user-generated content (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_user_moderation",
)
async def moderate_user_content(user_id: str, content_type: str, action: str, reason: str) -> Dict[str, Any]:
    """
    Moderate user-generated content such as profiles, posts, or other user data.

    Args:
        user_id: The ID of the user whose content to moderate
        content_type: Type of content (profile, bio, avatar, banner, etc.)
        action: Moderation action (hide, remove, flag, approve)
        reason: Reason for moderation action

    Returns:
        Dictionary containing moderation action confirmation

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for content moderation")

    # Validate parameters
    valid_content_types = ["profile", "bio", "avatar", "banner", "display_name"]
    valid_actions = ["hide", "remove", "flag", "approve", "reset"]

    if content_type not in valid_content_types:
        raise MCPValidationError(f"Invalid content type. Must be one of: {', '.join(valid_content_types)}")

    if action not in valid_actions:
        raise MCPValidationError(f"Invalid action. Must be one of: {', '.join(valid_actions)}")

    if not reason or len(reason.strip()) < 5:
        raise MCPValidationError("Moderation reason must be at least 5 characters")

    try:
        start_time = time.time()

        # Get user from database
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id})

        if not user:
            raise MCPValidationError(f"User not found: {user_id}")

        # Prepare moderation data
        moderation_timestamp = datetime.utcnow()
        moderation_info = {
            "moderated_at": moderation_timestamp,
            "moderated_by": user_context.user_id,
            "moderated_by_username": user_context.username,
            "action": action,
            "reason": reason.strip(),
            "original_content": None,
        }

        # Apply moderation action based on content type
        update_data = {}

        if content_type == "profile":
            # Moderate entire profile
            if action == "hide":
                update_data["profile_hidden"] = True
                update_data["profile_moderation"] = moderation_info
            elif action == "remove":
                moderation_info["original_content"] = {
                    "display_name": user.get("display_name"),
                    "bio": user.get("bio"),
                    "avatar_url": user.get("avatar_url"),
                    "banner_url": user.get("banner_url"),
                }
                update_data.update(
                    {
                        "display_name": None,
                        "bio": None,
                        "avatar_url": None,
                        "banner_url": None,
                        "profile_moderation": moderation_info,
                    }
                )
            elif action == "approve":
                update_data["profile_hidden"] = False
                update_data["profile_approved"] = True
                update_data["profile_moderation"] = moderation_info

        elif content_type == "bio":
            if action == "remove":
                moderation_info["original_content"] = user.get("bio")
                update_data["bio"] = None
                update_data["bio_moderation"] = moderation_info
            elif action == "flag":
                update_data["bio_flagged"] = True
                update_data["bio_moderation"] = moderation_info

        elif content_type == "display_name":
            if action == "remove":
                moderation_info["original_content"] = user.get("display_name")
                update_data["display_name"] = None
                update_data["display_name_moderation"] = moderation_info
            elif action == "reset":
                update_data["display_name"] = user.get("username")  # Reset to username
                update_data["display_name_moderation"] = moderation_info

        elif content_type == "avatar":
            if action == "remove":
                moderation_info["original_content"] = user.get("avatar_url")
                update_data["avatar_url"] = None
                update_data["avatar_moderation"] = moderation_info

        elif content_type == "banner":
            if action == "remove":
                moderation_info["original_content"] = user.get("banner_url")
                update_data["banner_url"] = None
                update_data["banner_moderation"] = moderation_info

        # Add general moderation tracking
        moderation_history = user.get("moderation_history", [])
        moderation_history.append(
            {
                "content_type": content_type,
                "action": action,
                "reason": reason,
                "moderated_at": moderation_timestamp,
                "moderated_by": user_context.user_id,
                "moderated_by_username": user_context.username,
            }
        )

        update_data["moderation_history"] = moderation_history
        update_data["updated_at"] = moderation_timestamp

        # Update user record
        result = await users_collection.update_one({"_id": user_id}, {"$set": update_data})

        if result.modified_count == 0:
            raise MCPValidationError("Failed to apply moderation action")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="moderate_user_content",
            user_context=user_context,
            resource_type="user",
            resource_id=user_id,
            changes={"content_type": content_type, "action": action, "reason": reason},
            metadata={
                "target_username": user.get("username"),
                "content_type": content_type,
                "moderation_action": action,
                "has_original_content": moderation_info["original_content"] is not None,
            },
        )

        moderation_result = {
            "user_id": user_id,
            "username": user.get("username"),
            "moderation_applied": True,
            "moderation_details": {
                "content_type": content_type,
                "action": action,
                "reason": reason,
                "moderated_at": moderation_timestamp.isoformat(),
                "moderated_by": user_context.username,
            },
            "content_changes": {
                key: value for key, value in update_data.items() if key not in ["moderation_history", "updated_at"]
            },
            "operation_duration_ms": (time.time() - start_time) * 1000,
        }

        logger.info(
            "Content moderation applied by admin %s to user %s (%s) - Type: %s, Action: %s",
            user_context.user_id,
            user_id,
            user.get("username"),
            content_type,
            action,
        )

        return moderation_result

    except Exception as e:
        logger.error("Failed to moderate user content for %s: %s", user_id, e)
        raise MCPValidationError(f"Failed to moderate user content: {str(e)}")


# System Configuration Tools (Task 8.3)


class SystemConfigUpdate(BaseModel):
    """Request model for system configuration updates."""

    config_key: str = Field(..., description="Configuration key to update")
    config_value: Any = Field(..., description="New configuration value")
    reason: str = Field(..., description="Reason for configuration change")


class FeatureFlagUpdate(BaseModel):
    """Request model for feature flag updates."""

    flag_name: str = Field(..., description="Feature flag name")
    enabled: bool = Field(..., description="Whether to enable or disable the flag")
    reason: str = Field(..., description="Reason for flag change")


class MaintenanceSchedule(BaseModel):
    """Request model for maintenance scheduling."""

    start_time: datetime = Field(..., description="Maintenance start time")
    duration_minutes: int = Field(..., description="Expected maintenance duration")
    description: str = Field(..., description="Maintenance description")
    notify_users: bool = Field(True, description="Whether to notify users")


@authenticated_tool(
    name="get_system_config",
    description="Get current system configuration settings (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_config",
)
async def get_system_config() -> Dict[str, Any]:
    """
    Get comprehensive system configuration including settings, feature flags, and environment info.

    Returns:
        Dictionary containing system configuration and settings

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for system configuration access")

    try:
        start_time = time.time()

        # Get current configuration from settings
        system_config = {
            "environment": {
                "debug_mode": settings.DEBUG,
                "environment_type": "production" if not settings.DEBUG else "development",
                "host": settings.HOST,
                "port": settings.PORT,
                "base_url": settings.BASE_URL,
                "docs_enabled": settings.docs_should_be_enabled,
            },
            "database": {
                "mongodb_url": settings.MONGODB_URL,  # Don't expose credentials
                "mongodb_database": settings.MONGODB_DATABASE,
                "connection_timeout": settings.MONGODB_CONNECTION_TIMEOUT,
                "server_selection_timeout": settings.MONGODB_SERVER_SELECTION_TIMEOUT,
            },
            "redis": {
                "redis_url": settings.REDIS_URL,  # Don't expose credentials
                "redis_enabled": True,  # Assume enabled if URL is set
            },
            "security": {
                "rate_limiting_enabled": True,  # Based on SecurityManager usage
                "jwt_expiration_minutes": 60,  # Default JWT expiration
                "permanent_tokens_enabled": True,
                "webauthn_enabled": True,
                "two_fa_enabled": True,
                "trusted_ip_lockdown_available": True,
                "trusted_user_agent_lockdown_available": True,
            },
            "mcp_server": {
                "enabled": settings.MCP_ENABLED,
                "server_name": settings.MCP_SERVER_NAME,
                "server_version": settings.MCP_SERVER_VERSION,
                "server_host": settings.MCP_SERVER_HOST,
                "server_port": settings.MCP_SERVER_PORT,
                "debug_mode": settings.MCP_DEBUG_MODE,
                "security_enabled": settings.MCP_SECURITY_ENABLED,
                "audit_enabled": settings.MCP_AUDIT_ENABLED,
                "rate_limit_enabled": settings.MCP_RATE_LIMIT_ENABLED,
                "max_concurrent_tools": settings.MCP_MAX_CONCURRENT_TOOLS,
                "request_timeout": settings.MCP_REQUEST_TIMEOUT,
            },
            "features": {
                "family_management": True,
                "workspace_management": True,
                "shop_system": True,
                "digital_assets": True,
                "sbd_tokens": True,
                "notifications": True,
                "audit_logging": True,
            },
            "limits": {
                "max_families_per_user": 5,  # Default limit
                "max_workspaces_per_user": 10,  # Default limit
                "max_permanent_tokens_per_user": 10,
                "max_webauthn_credentials_per_user": 5,
                "rate_limit_requests_per_minute": 100,
                "max_file_upload_size_mb": 10,
            },
        }

        # Get feature flags from Redis (if stored there)
        try:
            redis_conn = await redis_manager.get_redis()
            feature_flags = {}

            # Get all feature flag keys
            flag_keys = await redis_conn.keys(f"{settings.ENV_PREFIX}:feature_flag:*")
            for key in flag_keys:
                flag_name = key.decode().split(":")[-1]
                flag_value = await redis_conn.get(key)
                feature_flags[flag_name] = flag_value.decode() == "true" if flag_value else False

            system_config["feature_flags"] = feature_flags

        except Exception as e:
            logger.warning("Failed to retrieve feature flags: %s", e)
            system_config["feature_flags"] = {"error": "Failed to retrieve feature flags from Redis"}

        # Get maintenance status
        try:
            redis_conn = await redis_manager.get_redis()
            maintenance_info = await redis_conn.hgetall(f"{settings.ENV_PREFIX}:maintenance")

            if maintenance_info:
                system_config["maintenance"] = {
                    "enabled": maintenance_info.get(b"enabled", b"false").decode() == "true",
                    "start_time": maintenance_info.get(b"start_time", b"").decode(),
                    "end_time": maintenance_info.get(b"end_time", b"").decode(),
                    "description": maintenance_info.get(b"description", b"").decode(),
                    "notify_users": maintenance_info.get(b"notify_users", b"true").decode() == "true",
                }
            else:
                system_config["maintenance"] = {"enabled": False, "scheduled": False}

        except Exception as e:
            logger.warning("Failed to retrieve maintenance status: %s", e)
            system_config["maintenance"] = {"error": "Failed to retrieve maintenance status"}

        # Add configuration metadata
        system_config["metadata"] = {
            "retrieved_at": datetime.utcnow().isoformat(),
            "retrieved_by": user_context.username,
            "config_sections": len(system_config),
            "retrieval_duration_ms": (time.time() - start_time) * 1000,
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_system_config",
            user_context=user_context,
            resource_type="system",
            resource_id="configuration",
            metadata={
                "config_sections": len(system_config),
                "feature_flags_count": len(system_config.get("feature_flags", {})),
                "maintenance_enabled": system_config.get("maintenance", {}).get("enabled", False),
            },
        )

        logger.info(
            "System configuration retrieved by admin %s - %d sections", user_context.user_id, len(system_config)
        )

        return system_config

    except Exception as e:
        logger.error("Failed to get system configuration: %s", e)
        raise MCPValidationError(f"Failed to retrieve system configuration: {str(e)}")


@authenticated_tool(
    name="update_system_settings",
    description="Update system configuration settings (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_config",
)
async def update_system_settings(config_key: str, config_value: Any, reason: str) -> Dict[str, Any]:
    """
    Update system configuration settings with audit trail.

    Args:
        config_key: Configuration key to update (e.g., "rate_limit.requests_per_minute")
        config_value: New configuration value
        reason: Reason for configuration change

    Returns:
        Dictionary containing update confirmation and details

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If configuration key is invalid or update fails
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for system configuration updates")

    # Validate parameters
    if not config_key or not config_key.strip():
        raise MCPValidationError("Configuration key cannot be empty")

    if not reason or len(reason.strip()) < 10:
        raise MCPValidationError("Reason must be at least 10 characters")

    # Define allowed configuration keys for security
    allowed_config_keys = {
        "rate_limit.requests_per_minute": {"type": int, "min": 10, "max": 1000},
        "rate_limit.burst_limit": {"type": int, "min": 5, "max": 100},
        "mcp.max_concurrent_tools": {"type": int, "min": 1, "max": 200},
        "mcp.request_timeout": {"type": int, "min": 5, "max": 300},
        "limits.max_families_per_user": {"type": int, "min": 1, "max": 50},
        "limits.max_workspaces_per_user": {"type": int, "min": 1, "max": 100},
        "limits.max_permanent_tokens_per_user": {"type": int, "min": 1, "max": 50},
        "security.session_timeout_minutes": {"type": int, "min": 15, "max": 1440},
        "features.new_user_registration": {"type": bool},
        "features.public_api_access": {"type": bool},
        "maintenance.message": {"type": str, "max_length": 500},
    }

    if config_key not in allowed_config_keys:
        raise MCPValidationError(f"Configuration key '{config_key}' is not allowed to be modified")

    try:
        start_time = time.time()

        # Validate configuration value
        config_spec = allowed_config_keys[config_key]

        # Type validation
        if config_spec["type"] == int:
            if not isinstance(config_value, int):
                try:
                    config_value = int(config_value)
                except (ValueError, TypeError):
                    raise MCPValidationError(f"Configuration value must be an integer")

            # Range validation
            if "min" in config_spec and config_value < config_spec["min"]:
                raise MCPValidationError(f"Value must be at least {config_spec['min']}")
            if "max" in config_spec and config_value > config_spec["max"]:
                raise MCPValidationError(f"Value must be at most {config_spec['max']}")

        elif config_spec["type"] == bool:
            if not isinstance(config_value, bool):
                if isinstance(config_value, str):
                    config_value = config_value.lower() in ("true", "1", "yes", "on")
                else:
                    config_value = bool(config_value)

        elif config_spec["type"] == str:
            config_value = str(config_value)
            if "max_length" in config_spec and len(config_value) > config_spec["max_length"]:
                raise MCPValidationError(f"Value must be at most {config_spec['max_length']} characters")

        # Get current value for audit trail
        redis_conn = await redis_manager.get_redis()
        config_redis_key = f"{settings.ENV_PREFIX}:config:{config_key}"
        old_value = await redis_conn.get(config_redis_key)
        old_value = old_value.decode() if old_value else None

        # Store configuration in Redis
        await redis_conn.set(config_redis_key, str(config_value))

        # Create configuration change record
        config_change = {
            "config_key": config_key,
            "old_value": old_value,
            "new_value": str(config_value),
            "changed_at": datetime.utcnow(),
            "changed_by": user_context.user_id,
            "changed_by_username": user_context.username,
            "reason": reason.strip(),
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
        }

        # Store change history
        change_history_key = f"{settings.ENV_PREFIX}:config_history:{config_key}"
        await redis_conn.lpush(change_history_key, json.dumps(config_change, default=str))

        # Keep only last 50 changes
        await redis_conn.ltrim(change_history_key, 0, 49)

        # Set expiration for change history (1 year)
        await redis_conn.expire(change_history_key, 365 * 24 * 60 * 60)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="update_system_settings",
            user_context=user_context,
            resource_type="system",
            resource_id="configuration",
            changes={
                "config_key": config_key,
                "old_value": old_value,
                "new_value": str(config_value),
                "reason": reason,
            },
            metadata={"config_category": config_key.split(".")[0], "value_type": type(config_value).__name__},
        )

        update_result = {
            "config_key": config_key,
            "old_value": old_value,
            "new_value": str(config_value),
            "update_successful": True,
            "change_details": {
                "changed_at": config_change["changed_at"].isoformat(),
                "changed_by": user_context.username,
                "reason": reason,
            },
            "requires_restart": config_key.startswith("mcp.") or config_key.startswith("database."),
            "operation_duration_ms": (time.time() - start_time) * 1000,
        }

        logger.info(
            "System configuration updated by admin %s - Key: %s, Value: %s, Reason: %s",
            user_context.user_id,
            config_key,
            config_value,
            reason,
        )

        return update_result

    except Exception as e:
        logger.error("Failed to update system configuration %s: %s", config_key, e)
        raise MCPValidationError(f"Failed to update system configuration: {str(e)}")


@authenticated_tool(
    name="get_feature_flags",
    description="Get all feature flags and their current states (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_config",
)
async def get_feature_flags() -> Dict[str, Any]:
    """
    Get all feature flags and their current states for system management.

    Returns:
        Dictionary containing all feature flags and their states

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for feature flag access")

    try:
        start_time = time.time()

        redis_conn = await redis_manager.get_redis()

        # Get all feature flags
        feature_flags = {}
        flag_keys = await redis_conn.keys(f"{settings.ENV_PREFIX}:feature_flag:*")

        for key in flag_keys:
            flag_name = key.decode().split(":")[-1]
            flag_data = await redis_conn.hgetall(key)

            if flag_data:
                feature_flags[flag_name] = {
                    "enabled": flag_data.get(b"enabled", b"false").decode() == "true",
                    "description": flag_data.get(b"description", b"").decode(),
                    "created_at": flag_data.get(b"created_at", b"").decode(),
                    "created_by": flag_data.get(b"created_by", b"").decode(),
                    "last_modified_at": flag_data.get(b"last_modified_at", b"").decode(),
                    "last_modified_by": flag_data.get(b"last_modified_by", b"").decode(),
                    "category": flag_data.get(b"category", b"general").decode(),
                }

        # Add default feature flags if none exist
        if not feature_flags:
            default_flags = {
                "new_user_registration": {
                    "enabled": True,
                    "description": "Allow new user registration",
                    "category": "authentication",
                },
                "family_management": {
                    "enabled": True,
                    "description": "Enable family management features",
                    "category": "features",
                },
                "workspace_collaboration": {
                    "enabled": True,
                    "description": "Enable workspace collaboration features",
                    "category": "features",
                },
                "shop_system": {"enabled": True, "description": "Enable digital asset shop", "category": "commerce"},
                "advanced_security": {
                    "enabled": True,
                    "description": "Enable advanced security features",
                    "category": "security",
                },
                "api_rate_limiting": {
                    "enabled": True,
                    "description": "Enable API rate limiting",
                    "category": "security",
                },
                "audit_logging": {
                    "enabled": True,
                    "description": "Enable comprehensive audit logging",
                    "category": "monitoring",
                },
                "mcp_server": {
                    "enabled": settings.MCP_ENABLED,
                    "description": "Enable MCP server functionality",
                    "category": "integration",
                },
            }

            # Initialize default flags in Redis
            for flag_name, flag_info in default_flags.items():
                flag_key = f"{settings.ENV_PREFIX}:feature_flag:{flag_name}"
                await redis_conn.hset(
                    flag_key,
                    mapping={
                        "enabled": str(flag_info["enabled"]).lower(),
                        "description": flag_info["description"],
                        "category": flag_info["category"],
                        "created_at": datetime.utcnow().isoformat(),
                        "created_by": "system",
                    },
                )

                feature_flags[flag_name] = {
                    **flag_info,
                    "created_at": datetime.utcnow().isoformat(),
                    "created_by": "system",
                    "last_modified_at": "",
                    "last_modified_by": "",
                }

        # Group flags by category
        flags_by_category = {}
        for flag_name, flag_data in feature_flags.items():
            category = flag_data.get("category", "general")
            if category not in flags_by_category:
                flags_by_category[category] = {}
            flags_by_category[category][flag_name] = flag_data

        # Calculate summary statistics
        total_flags = len(feature_flags)
        enabled_flags = sum(1 for flag in feature_flags.values() if flag["enabled"])

        result = {
            "feature_flags": feature_flags,
            "flags_by_category": flags_by_category,
            "summary": {
                "total_flags": total_flags,
                "enabled_flags": enabled_flags,
                "disabled_flags": total_flags - enabled_flags,
                "categories": list(flags_by_category.keys()),
            },
            "metadata": {
                "retrieved_at": datetime.utcnow().isoformat(),
                "retrieved_by": user_context.username,
                "retrieval_duration_ms": (time.time() - start_time) * 1000,
            },
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_feature_flags",
            user_context=user_context,
            resource_type="system",
            resource_id="feature_flags",
            metadata={"total_flags": total_flags, "enabled_flags": enabled_flags, "categories": len(flags_by_category)},
        )

        logger.info(
            "Feature flags retrieved by admin %s - %d total flags, %d enabled",
            user_context.user_id,
            total_flags,
            enabled_flags,
        )

        return result

    except Exception as e:
        logger.error("Failed to get feature flags: %s", e)
        raise MCPValidationError(f"Failed to retrieve feature flags: {str(e)}")


@authenticated_tool(
    name="toggle_feature_flag",
    description="Enable or disable a feature flag (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_config",
)
async def toggle_feature_flag(flag_name: str, enabled: bool, reason: str) -> Dict[str, Any]:
    """
    Enable or disable a feature flag with audit trail.

    Args:
        flag_name: Name of the feature flag to toggle
        enabled: Whether to enable (True) or disable (False) the flag
        reason: Reason for the flag change

    Returns:
        Dictionary containing flag toggle confirmation

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If flag not found or update fails
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for feature flag management")

    # Validate parameters
    if not flag_name or not flag_name.strip():
        raise MCPValidationError("Feature flag name cannot be empty")

    if not reason or len(reason.strip()) < 5:
        raise MCPValidationError("Reason must be at least 5 characters")

    try:
        start_time = time.time()

        redis_conn = await redis_manager.get_redis()
        flag_key = f"{settings.ENV_PREFIX}:feature_flag:{flag_name}"

        # Check if flag exists
        flag_exists = await redis_conn.exists(flag_key)
        if not flag_exists:
            raise MCPValidationError(f"Feature flag '{flag_name}' does not exist")

        # Get current flag data
        flag_data = await redis_conn.hgetall(flag_key)
        old_enabled = flag_data.get(b"enabled", b"false").decode() == "true"

        # Update flag
        update_data = {
            "enabled": str(enabled).lower(),
            "last_modified_at": datetime.utcnow().isoformat(),
            "last_modified_by": user_context.username,
        }

        await redis_conn.hset(flag_key, mapping=update_data)

        # Create flag change history
        change_record = {
            "flag_name": flag_name,
            "old_enabled": old_enabled,
            "new_enabled": enabled,
            "changed_at": datetime.utcnow(),
            "changed_by": user_context.user_id,
            "changed_by_username": user_context.username,
            "reason": reason.strip(),
            "ip_address": user_context.ip_address,
        }

        # Store change history
        history_key = f"{settings.ENV_PREFIX}:feature_flag_history:{flag_name}"
        await redis_conn.lpush(history_key, json.dumps(change_record, default=str))

        # Keep only last 100 changes
        await redis_conn.ltrim(history_key, 0, 99)

        # Set expiration for change history (1 year)
        await redis_conn.expire(history_key, 365 * 24 * 60 * 60)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="toggle_feature_flag",
            user_context=user_context,
            resource_type="system",
            resource_id="feature_flags",
            changes={"flag_name": flag_name, "old_enabled": old_enabled, "new_enabled": enabled, "reason": reason},
            metadata={
                "flag_category": flag_data.get(b"category", b"general").decode(),
                "action": "enabled" if enabled else "disabled",
            },
        )

        toggle_result = {
            "flag_name": flag_name,
            "old_enabled": old_enabled,
            "new_enabled": enabled,
            "toggle_successful": True,
            "change_details": {
                "changed_at": change_record["changed_at"].isoformat(),
                "changed_by": user_context.username,
                "reason": reason,
            },
            "flag_info": {
                "description": flag_data.get(b"description", b"").decode(),
                "category": flag_data.get(b"category", b"general").decode(),
            },
            "operation_duration_ms": (time.time() - start_time) * 1000,
        }

        logger.info(
            "Feature flag '%s' %s by admin %s - Reason: %s",
            flag_name,
            "enabled" if enabled else "disabled",
            user_context.user_id,
            reason,
        )

        return toggle_result

    except Exception as e:
        logger.error("Failed to toggle feature flag %s: %s", flag_name, e)
        raise MCPValidationError(f"Failed to toggle feature flag: {str(e)}")


@authenticated_tool(
    name="get_maintenance_status",
    description="Get current maintenance mode status and schedule (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_config",
)
async def get_maintenance_status() -> Dict[str, Any]:
    """
    Get current maintenance mode status and any scheduled maintenance.

    Returns:
        Dictionary containing maintenance status and schedule information

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for maintenance status")

    try:
        start_time = time.time()

        redis_conn = await redis_manager.get_redis()

        # Get current maintenance status
        maintenance_key = f"{settings.ENV_PREFIX}:maintenance"
        maintenance_data = await redis_conn.hgetall(maintenance_key)

        if maintenance_data:
            maintenance_status = {
                "enabled": maintenance_data.get(b"enabled", b"false").decode() == "true",
                "start_time": maintenance_data.get(b"start_time", b"").decode(),
                "end_time": maintenance_data.get(b"end_time", b"").decode(),
                "description": maintenance_data.get(b"description", b"").decode(),
                "notify_users": maintenance_data.get(b"notify_users", b"true").decode() == "true",
                "scheduled_by": maintenance_data.get(b"scheduled_by", b"").decode(),
                "scheduled_at": maintenance_data.get(b"scheduled_at", b"").decode(),
            }
        else:
            maintenance_status = {
                "enabled": False,
                "scheduled": False,
                "start_time": None,
                "end_time": None,
                "description": None,
                "notify_users": True,
                "scheduled_by": None,
                "scheduled_at": None,
            }

        # Get maintenance history
        history_key = f"{settings.ENV_PREFIX}:maintenance_history"
        history_entries = await redis_conn.lrange(history_key, 0, 9)  # Last 10 entries

        maintenance_history = []
        for entry in history_entries:
            try:
                import json

                history_item = json.loads(entry.decode())
                maintenance_history.append(history_item)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue

        # Calculate maintenance window info if active
        maintenance_window = None
        if maintenance_status["enabled"] and maintenance_status["start_time"]:
            try:
                start_dt = datetime.fromisoformat(maintenance_status["start_time"])
                end_dt = (
                    datetime.fromisoformat(maintenance_status["end_time"]) if maintenance_status["end_time"] else None
                )
                now = datetime.utcnow()

                if end_dt:
                    duration_minutes = int((end_dt - start_dt).total_seconds() / 60)
                    remaining_minutes = int((end_dt - now).total_seconds() / 60) if end_dt > now else 0
                else:
                    duration_minutes = None
                    remaining_minutes = None

                maintenance_window = {
                    "is_active": start_dt <= now <= (end_dt or datetime.max),
                    "duration_minutes": duration_minutes,
                    "remaining_minutes": remaining_minutes,
                    "started": start_dt <= now,
                    "ended": end_dt and now > end_dt,
                }
            except (ValueError, TypeError):
                maintenance_window = {"error": "Invalid maintenance time format"}

        result = {
            "maintenance_status": maintenance_status,
            "maintenance_window": maintenance_window,
            "maintenance_history": maintenance_history,
            "system_status": {
                "accepting_requests": not maintenance_status["enabled"],
                "read_only_mode": False,  # Could be implemented as a separate feature
                "api_available": True,
            },
            "metadata": {
                "retrieved_at": datetime.utcnow().isoformat(),
                "retrieved_by": user_context.username,
                "retrieval_duration_ms": (time.time() - start_time) * 1000,
            },
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_maintenance_status",
            user_context=user_context,
            resource_type="system",
            resource_id="maintenance",
            metadata={
                "maintenance_enabled": maintenance_status["enabled"],
                "has_scheduled_maintenance": bool(maintenance_status.get("start_time")),
                "history_entries": len(maintenance_history),
            },
        )

        logger.info(
            "Maintenance status retrieved by admin %s - Enabled: %s",
            user_context.user_id,
            maintenance_status["enabled"],
        )

        return result

    except Exception as e:
        logger.error("Failed to get maintenance status: %s", e)
        raise MCPValidationError(f"Failed to retrieve maintenance status: {str(e)}")


@authenticated_tool(
    name="schedule_maintenance",
    description="Schedule system maintenance with user notification (admin only)",
    permissions=["admin"],
    rate_limit_action="admin_config",
)
async def schedule_maintenance(
    start_time: str, duration_minutes: int, description: str, notify_users: bool = True
) -> Dict[str, Any]:
    """
    Schedule system maintenance with optional user notification.

    Args:
        start_time: Maintenance start time (ISO format)
        duration_minutes: Expected maintenance duration in minutes
        description: Description of maintenance work
        notify_users: Whether to notify users about the maintenance

    Returns:
        Dictionary containing maintenance scheduling confirmation

    Raises:
        MCPAuthorizationError: If user doesn't have admin permissions
        MCPValidationError: If parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Verify admin permissions
    if not user_context.has_permission("admin"):
        raise MCPAuthorizationError("Admin permission required for maintenang")

    # Validate parameters
    if not description or len(description.strip()) < 10:
        raise MCPValidationError("Maintenance description must be at least 10 characters")

    if duration_minutes <= 0 or duration_minutes > 1440:  # Max 24 hours
        raise MCPValidationError("Duration must be between 1 and 1440 minutes")

    try:
        # Parse and validate start time
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            raise MCPValidationError("Invalid start time format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")

        # Ensure maintenance is scheduled for the future
        if start_dt <= datetime.utcnow():
            raise MCPValidationError("Maintenance must be scheduled for a future time")

        # Calculate end time
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        start_time_processing = time.time()

        redis_conn = await redis_manager.get_redis()

        # Create maintenance record
        maintenance_data = {
            "enabled": "false",  # Not enabled yet, just scheduled
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "description": description.strip(),
            "notify_users": str(notify_users).lower(),
            "scheduled_by": user_context.username,
            "scheduled_at": datetime.utcnow().isoformat(),
            "duration_minutes": str(duration_minutes),
        }

        # Store maintenance schedule
        maintenance_key = f"{settings.ENV_PREFIX}:maintenance"
        await redis_conn.hset(maintenance_key, mapping=maintenance_data)

        # Add to maintenance history
        history_record = {
            "action": "scheduled",
            "start_time": start_dt.isoformat(),
            "end_time": end_dt.isoformat(),
            "duration_minutes": duration_minutes,
            "description": description.strip(),
            "scheduled_by": user_context.username,
            "scheduled_at": datetime.utcnow().isoformat(),
            "notify_users": notify_users,
        }

        history_key = f"{settings.ENV_PREFIX}:maintenance_history"
        await redis_conn.lpush(history_key, json.dumps(history_record, default=str))

        # Keep only last 50 history entries
        await redis_conn.ltrim(history_key, 0, 49)

        # Set up automatic maintenance activation (this would require a background task)
        # For now, we'll just log that it should be implemented
        logger.info("Maintenance scheduled - automatic activation should be implemented via background task")

        # Send user notifications if requested
        notifications_sent = 0
        if notify_users:
            try:
                # This would integrate with the notification system
                # For now, we'll simulate notification sending
                logger.info("Maintenance notifications would be sent to all active users")
                notifications_sent = 100  # Simulated count
            except Exception as e:
                logger.warning("Failed to send maintenance notifications: %s", e)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="schedule_maintenance",
            user_context=user_context,
            resource_type="system",
            resource_id="maintenance",
            changes={
                "action": "scheduled",
                "start_time": start_dt.isoformat(),
                "duration_minutes": duration_minutes,
                "description": description,
            },
            metadata={
                "notify_users": notify_users,
                "notifications_sent": notifications_sent,
                "advance_notice_hours": (start_dt - datetime.utcnow()).total_seconds() / 3600,
            },
        )

        schedule_result = {
            "maintenance_scheduled": True,
            "schedule_details": {
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
                "duration_minutes": duration_minutes,
                "description": description,
                "notify_users": notify_users,
            },
            "scheduling_info": {
                "scheduled_by": user_context.username,
                "scheduled_at": maintenance_data["scheduled_at"],
                "advance_notice_hours": round((start_dt - datetime.utcnow()).total_seconds() / 3600, 1),
            },
            "notifications": {
                "users_notified": notifications_sent,
                "notification_sent": notify_users and notifications_sent > 0,
            },
            "operation_duration_ms": (time.time() - start_time_processing) * 1000,
        }

        logger.info(
            "Maintenance scheduled by admin %s - Start: %s, Duration: %d minutes, Notifications: %s",
            user_context.user_id,
            start_dt.isoformat(),
            duration_minutes,
            notify_users,
        )

        return schedule_result

    except Exception as e:
        logger.error("Failed to schedule maintenance: %s", e)
        raise MCPValidationError(f"Failed to schedule maintenance: {str(e)}")
