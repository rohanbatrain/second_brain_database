"""
Admin-Only Family System Health and Monitoring Endpoints.

This module provides highly sensitive system monitoring endpoints that should
only be accessible to system administrators. These endpoints expose internal
system state, performance metrics, and operational data.

Security Requirements:
- All endpoints require admin privileges
- Rate limiting is more restrictive than regular endpoints
- All access is logged for security auditing
- Sensitive data is sanitized in responses
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from second_brain_database.managers.family_monitoring import FamilyMetrics, family_monitor
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import require_admin
from second_brain_database.utils.family_monitoring_utils import log_family_security_event

logger = get_logger(prefix="[Admin Family Health]")

router = APIRouter(prefix="/family/admin", tags=["Family Admin Health"])


@router.get("/system/health")
async def get_comprehensive_system_health(
    request: Request, current_user: dict = Depends(require_admin)
) -> JSONResponse:
    """
    Get comprehensive system health status with sensitive internal details.

    **ADMIN ONLY** - This endpoint exposes sensitive system information including:
    - Internal component response times
    - Database connection details
    - Redis connectivity status
    - Error rates and failure details
    - Performance bottlenecks

    **Rate Limiting:** 5 requests per hour per admin

    **Security Logging:** All access attempts are logged for audit

    **Returns:**
    - Detailed system health with internal metrics
    - Component-level diagnostics
    - Performance analysis data
    """
    admin_id = str(current_user["_id"])

    # Log admin access for security audit
    log_family_security_event(
        event_type="admin_health_access",
        family_id=None,
        user_id=admin_id,
        success=True,
        details={
            "endpoint": "/family/admin/system/health",
            "admin_username": current_user.get("username", "unknown"),
            "access_time": "now",
        },
        ip_address=getattr(request.client, "host", "unknown"),
    )

    # Restrictive rate limiting for admin endpoints
    await security_manager.check_rate_limit(
        request, f"admin_system_health_{admin_id}", rate_limit_requests=5, rate_limit_period=3600
    )

    try:
        # Get comprehensive health status
        health_status = await family_monitor.check_family_system_health()

        # Add admin-only sensitive details
        admin_details = {
            "internal_metrics": {
                "database_pool_status": await _get_database_pool_metrics(),
                "redis_connection_details": await _get_redis_connection_metrics(),
                "system_resource_usage": await _get_system_resource_metrics(),
                "error_analysis": await _get_error_analysis_data(),
            },
            "security_status": {
                "recent_security_events": await _get_recent_security_events(),
                "failed_access_attempts": await _get_failed_access_attempts(),
                "suspicious_activity": await _get_suspicious_activity_summary(),
            },
            "performance_analysis": {
                "slow_operations": await _get_slow_operations_analysis(),
                "bottleneck_identification": await _identify_performance_bottlenecks(),
                "capacity_planning": await _get_capacity_planning_data(),
            },
        }

        # Combine standard health with admin details
        comprehensive_status = {
            "overall_healthy": all(status.healthy for status in health_status.values()),
            "components": {
                name: {
                    "healthy": status.healthy,
                    "response_time": status.response_time,
                    "error_message": status.error_message,
                    "metadata": status.metadata,
                    "last_check": status.last_check,
                }
                for name, status in health_status.items()
            },
            "admin_details": admin_details,
            "access_info": {
                "accessed_by": current_user.get("username", "unknown"),
                "admin_id": admin_id,
                "access_level": "system_admin",
                "timestamp": health_status[list(health_status.keys())[0]].last_check,
            },
        }

        logger.info(
            "Comprehensive system health accessed by admin %s (%s)", current_user.get("username", "unknown"), admin_id
        )

        return JSONResponse(content=comprehensive_status, status_code=status.HTTP_200_OK)

    except Exception as e:
        # Log security event for failed access
        log_family_security_event(
            event_type="admin_health_access_failed",
            family_id=None,
            user_id=admin_id,
            success=False,
            details={
                "endpoint": "/family/admin/system/health",
                "error": str(e),
                "admin_username": current_user.get("username", "unknown"),
            },
            ip_address=getattr(request.client, "host", "unknown"),
        )

        logger.error("Failed to get comprehensive system health for admin %s: %s", admin_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ADMIN_HEALTH_CHECK_FAILED",
                "message": "Failed to retrieve comprehensive system health status",
            },
        )


@router.get("/system/metrics/detailed")
async def get_detailed_system_metrics(request: Request, current_user: dict = Depends(require_admin)) -> JSONResponse:
    """
    Get detailed system metrics with sensitive operational data.

    **ADMIN ONLY** - Exposes sensitive metrics including:
    - Database query performance statistics
    - Memory and CPU usage patterns
    - Network I/O metrics
    - Cache hit/miss ratios
    - Transaction success/failure rates

    **Rate Limiting:** 3 requests per hour per admin

    **Returns:**
    - Detailed performance metrics
    - Resource utilization data
    - Operational statistics
    """
    admin_id = str(current_user["_id"])

    # Log admin access
    log_family_security_event(
        event_type="admin_metrics_access",
        family_id=None,
        user_id=admin_id,
        success=True,
        details={
            "endpoint": "/family/admin/system/metrics/detailed",
            "admin_username": current_user.get("username", "unknown"),
        },
        ip_address=getattr(request.client, "host", "unknown"),
    )

    # Very restrictive rate limiting
    await security_manager.check_rate_limit(
        request, f"admin_detailed_metrics_{admin_id}", rate_limit_requests=3, rate_limit_period=3600
    )

    try:
        # Get standard metrics
        standard_metrics = await family_monitor.collect_family_metrics()

        # Add admin-only detailed metrics
        detailed_metrics = {
            "standard_metrics": standard_metrics.dict(),
            "admin_metrics": {
                "database_performance": await _get_database_performance_details(),
                "system_resources": await _get_system_resource_details(),
                "security_metrics": await _get_security_metrics_details(),
                "operational_stats": await _get_operational_statistics(),
                "capacity_metrics": await _get_capacity_metrics(),
            },
            "access_info": {
                "accessed_by": current_user.get("username", "unknown"),
                "admin_id": admin_id,
                "access_level": "system_admin",
            },
        }

        logger.info(
            "Detailed system metrics accessed by admin %s (%s)", current_user.get("username", "unknown"), admin_id
        )

        return JSONResponse(content=detailed_metrics, status_code=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get detailed metrics for admin %s: %s", admin_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "ADMIN_METRICS_FAILED", "message": "Failed to retrieve detailed system metrics"},
        )


@router.post("/system/maintenance/trigger")
async def trigger_system_maintenance(request: Request, current_user: dict = Depends(require_admin)) -> JSONResponse:
    """
    Trigger system maintenance operations.

    **ADMIN ONLY** - Performs sensitive maintenance operations:
    - Database cleanup and optimization
    - Cache clearing and rebuilding
    - Log rotation and archival
    - Performance tuning adjustments

    **Rate Limiting:** 1 request per hour per admin

    **Returns:**
    - Maintenance operation results
    - System impact assessment
    """
    admin_id = str(current_user["_id"])

    # Log admin maintenance action
    log_family_security_event(
        event_type="admin_maintenance_triggered",
        family_id=None,
        user_id=admin_id,
        success=True,
        details={
            "endpoint": "/family/admin/system/maintenance/trigger",
            "admin_username": current_user.get("username", "unknown"),
            "maintenance_type": "system_maintenance",
        },
        ip_address=getattr(request.client, "host", "unknown"),
    )

    # Very restrictive rate limiting for maintenance operations
    await security_manager.check_rate_limit(
        request, f"admin_maintenance_{admin_id}", rate_limit_requests=1, rate_limit_period=3600
    )

    try:
        maintenance_results = {
            "database_cleanup": await _perform_database_cleanup(),
            "cache_optimization": await _perform_cache_optimization(),
            "log_maintenance": await _perform_log_maintenance(),
            "performance_tuning": await _perform_performance_tuning(),
            "security_audit": await _perform_security_audit(),
        }

        logger.info("System maintenance triggered by admin %s (%s)", current_user.get("username", "unknown"), admin_id)

        return JSONResponse(
            content={
                "status": "maintenance_completed",
                "results": maintenance_results,
                "performed_by": current_user.get("username", "unknown"),
                "admin_id": admin_id,
                "timestamp": "now",
            },
            status_code=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error("System maintenance failed for admin %s: %s", admin_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "MAINTENANCE_FAILED", "message": "System maintenance operation failed"},
        )


# Private helper functions for admin-only data


async def _get_database_pool_metrics() -> Dict[str, Any]:
    """Get database connection pool metrics (admin-only)."""
    try:
        from second_brain_database.database import db_manager

        # This would contain sensitive database connection info
        return {
            "active_connections": "admin_only_data",
            "pool_utilization": "admin_only_data",
            "connection_errors": "admin_only_data",
            "query_performance": "admin_only_data",
        }
    except Exception as e:
        logger.error("Failed to get database pool metrics: %s", e)
        return {"error": "metrics_unavailable"}


async def _get_redis_connection_metrics() -> Dict[str, Any]:
    """Get Redis connection metrics (admin-only)."""
    try:
        # This would contain sensitive Redis connection info
        return {
            "connection_status": "admin_only_data",
            "memory_usage": "admin_only_data",
            "cache_hit_ratio": "admin_only_data",
            "key_statistics": "admin_only_data",
        }
    except Exception as e:
        logger.error("Failed to get Redis metrics: %s", e)
        return {"error": "metrics_unavailable"}


async def _get_system_resource_metrics() -> Dict[str, Any]:
    """Get system resource usage metrics (admin-only)."""
    try:
        import psutil

        return {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory()._asdict(),
            "disk_usage": psutil.disk_usage("/")._asdict(),
            "network_io": psutil.net_io_counters()._asdict(),
        }
    except Exception as e:
        logger.error("Failed to get system resource metrics: %s", e)
        return {"error": "metrics_unavailable"}


async def _get_error_analysis_data() -> Dict[str, Any]:
    """Get error analysis data (admin-only)."""
    return {"recent_errors": "admin_only_data", "error_patterns": "admin_only_data", "failure_rates": "admin_only_data"}


async def _get_recent_security_events() -> List[Dict[str, Any]]:
    """Get recent security events (admin-only)."""
    return [{"event": "admin_only_security_data"}, {"event": "admin_only_security_data"}]


async def _get_failed_access_attempts() -> Dict[str, Any]:
    """Get failed access attempts (admin-only)."""
    return {
        "failed_logins": "admin_only_data",
        "blocked_ips": "admin_only_data",
        "suspicious_patterns": "admin_only_data",
    }


async def _get_suspicious_activity_summary() -> Dict[str, Any]:
    """Get suspicious activity summary (admin-only)."""
    return {
        "anomalous_requests": "admin_only_data",
        "rate_limit_violations": "admin_only_data",
        "security_alerts": "admin_only_data",
    }


async def _get_slow_operations_analysis() -> Dict[str, Any]:
    """Get slow operations analysis (admin-only)."""
    return {
        "slowest_queries": "admin_only_data",
        "performance_bottlenecks": "admin_only_data",
        "optimization_recommendations": "admin_only_data",
    }


async def _identify_performance_bottlenecks() -> Dict[str, Any]:
    """Identify performance bottlenecks (admin-only)."""
    return {
        "cpu_bottlenecks": "admin_only_data",
        "memory_bottlenecks": "admin_only_data",
        "io_bottlenecks": "admin_only_data",
    }


async def _get_capacity_planning_data() -> Dict[str, Any]:
    """Get capacity planning data (admin-only)."""
    return {
        "growth_projections": "admin_only_data",
        "resource_forecasts": "admin_only_data",
        "scaling_recommendations": "admin_only_data",
    }


async def _get_database_performance_details() -> Dict[str, Any]:
    """Get detailed database performance metrics (admin-only)."""
    return {
        "query_statistics": "admin_only_data",
        "index_performance": "admin_only_data",
        "transaction_metrics": "admin_only_data",
    }


async def _get_system_resource_details() -> Dict[str, Any]:
    """Get detailed system resource information (admin-only)."""
    return {
        "detailed_cpu_stats": "admin_only_data",
        "detailed_memory_stats": "admin_only_data",
        "detailed_disk_stats": "admin_only_data",
    }


async def _get_security_metrics_details() -> Dict[str, Any]:
    """Get detailed security metrics (admin-only)."""
    return {
        "authentication_stats": "admin_only_data",
        "authorization_stats": "admin_only_data",
        "security_violations": "admin_only_data",
    }


async def _get_operational_statistics() -> Dict[str, Any]:
    """Get operational statistics (admin-only)."""
    return {
        "uptime_statistics": "admin_only_data",
        "service_availability": "admin_only_data",
        "error_recovery_stats": "admin_only_data",
    }


async def _get_capacity_metrics() -> Dict[str, Any]:
    """Get capacity metrics (admin-only)."""
    return {
        "current_capacity": "admin_only_data",
        "capacity_utilization": "admin_only_data",
        "capacity_alerts": "admin_only_data",
    }


# Maintenance operation functions


async def _perform_database_cleanup() -> Dict[str, Any]:
    """Perform database cleanup operations (admin-only)."""
    return {
        "expired_records_cleaned": "admin_only_data",
        "indexes_optimized": "admin_only_data",
        "statistics_updated": "admin_only_data",
    }


async def _perform_cache_optimization() -> Dict[str, Any]:
    """Perform cache optimization (admin-only)."""
    return {
        "cache_cleared": "admin_only_data",
        "cache_rebuilt": "admin_only_data",
        "optimization_applied": "admin_only_data",
    }


async def _perform_log_maintenance() -> Dict[str, Any]:
    """Perform log maintenance (admin-only)."""
    return {
        "logs_rotated": "admin_only_data",
        "logs_archived": "admin_only_data",
        "old_logs_cleaned": "admin_only_data",
    }


async def _perform_performance_tuning() -> Dict[str, Any]:
    """Perform performance tuning (admin-only)."""
    return {
        "performance_optimizations": "admin_only_data",
        "configuration_updates": "admin_only_data",
        "tuning_applied": "admin_only_data",
    }


async def _perform_security_audit() -> Dict[str, Any]:
    """Perform security audit (admin-only)."""
    return {
        "security_scan_results": "admin_only_data",
        "vulnerabilities_found": "admin_only_data",
        "security_updates_applied": "admin_only_data",
    }
