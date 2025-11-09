"""
Family Management System Health Check Endpoints.

This module provides health check endpoints specifically for the family management system,
including component health, performance metrics, and operational status monitoring.
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse

from second_brain_database.managers.family_monitoring import FamilyMetrics, family_monitor
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns, require_admin

logger = get_logger(prefix="[Family Health]")

router = APIRouter(prefix="/family/health", tags=["Family Health"])


@router.get("/status")
async def get_family_system_health(
    request: Request, current_user: dict = Depends(require_admin)  # ✅ Admin-only access
) -> JSONResponse:
    """
    Get comprehensive health status of the family management system.

    Performs health checks on all family system components including:
    - Database connectivity for family collections
    - Redis cache connectivity
    - SBD token integration
    - Email system for invitations
    - Notification system

    **Rate Limiting:** 10 requests per hour per user

    **Requirements:**
    - User must be authenticated

    **Returns:**
    - Overall health status
    - Individual component health details
    - Response times for each component
    - Last health check timestamp
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, f"family_health_check_{user_id}", rate_limit_requests=10, rate_limit_period=3600
    )

    try:
        health_status = await family_monitor.get_health_status()

        logger.info(
            "Family system health check requested by user %s - Overall healthy: %s",
            user_id,
            health_status["overall_healthy"],
        )

        status_code = status.HTTP_200_OK if health_status["overall_healthy"] else status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(
            content={
                "status": "healthy" if health_status["overall_healthy"] else "unhealthy",
                "timestamp": health_status["last_check"],
                "components": health_status["components"],
                "cache_hit": health_status["cache_hit"],
                "summary": {
                    "total_components": len(health_status["components"]),
                    "healthy_components": sum(1 for comp in health_status["components"].values() if comp["healthy"]),
                    "unhealthy_components": sum(
                        1 for comp in health_status["components"].values() if not comp["healthy"]
                    ),
                },
            },
            status_code=status_code,
        )

    except Exception as e:
        logger.error("Failed to get family system health status: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "HEALTH_CHECK_FAILED", "message": "Failed to retrieve family system health status"},
        )


@router.get("/metrics")
async def get_family_system_metrics(
    request: Request, current_user: dict = Depends(require_admin)  # ✅ Admin-only access
) -> FamilyMetrics:
    """
    Get comprehensive metrics for the family management system.

    Collects and returns detailed metrics including:
    - Family and member counts
    - Pending invitations and token requests
    - Operation rates and error rates
    - Performance metrics
    - SBD token metrics

    **Rate Limiting:** 5 requests per hour per user

    **Requirements:**
    - User must be authenticated

    **Returns:**
    - Comprehensive family system metrics
    - Performance statistics
    - Operational health indicators
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, f"family_metrics_{user_id}", rate_limit_requests=5, rate_limit_period=3600
    )

    try:
        metrics = await family_monitor.collect_family_metrics()

        logger.info(
            "Family system metrics collected by user %s - Families: %d, Members: %d",
            user_id,
            metrics.total_families,
            metrics.total_members,
        )

        return metrics

    except Exception as e:
        logger.error("Failed to collect family system metrics: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "METRICS_COLLECTION_FAILED", "message": "Failed to collect family system metrics"},
        )


@router.get("/performance")
async def get_family_performance_summary(
    request: Request, current_user: dict = Depends(require_admin)  # ✅ Admin-only access
) -> JSONResponse:
    """
    Get performance summary for family operations.

    Returns detailed performance statistics including:
    - Average operation durations
    - Success rates by operation type
    - Slow operation counts
    - Performance trends

    **Rate Limiting:** 10 requests per hour per user

    **Requirements:**
    - User must be authenticated

    **Returns:**
    - Performance summary by operation type
    - Overall performance statistics
    - Slow operation indicators
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, f"family_performance_{user_id}", rate_limit_requests=10, rate_limit_period=3600
    )

    try:
        performance_summary = await family_monitor.get_performance_summary()

        logger.info(
            "Family performance summary requested by user %s - Total ops: %d",
            user_id,
            performance_summary["overall_stats"]["total_operations"],
        )

        return JSONResponse(content=performance_summary, status_code=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Failed to get family performance summary: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "PERFORMANCE_SUMMARY_FAILED", "message": "Failed to retrieve family performance summary"},
        )


@router.post("/check")
async def trigger_family_health_check(
    request: Request, current_user: dict = Depends(require_admin)  # ✅ Admin-only access
) -> JSONResponse:
    """
    Manually trigger a comprehensive family system health check.

    Forces a fresh health check of all family system components,
    bypassing any cached results. Useful for immediate health verification
    after system changes or during troubleshooting.

    **Rate Limiting:** 3 requests per hour per user

    **Requirements:**
    - User must be authenticated

    **Returns:**
    - Fresh health check results
    - Component-by-component status
    - Performance timing information
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, f"family_health_trigger_{user_id}", rate_limit_requests=3, rate_limit_period=3600
    )

    try:
        # Force fresh health check
        health_results = await family_monitor.check_family_system_health()

        overall_healthy = all(status.healthy for status in health_results.values())

        logger.info(
            "Manual family health check triggered by user %s - Result: %s",
            user_id,
            "healthy" if overall_healthy else "unhealthy",
        )

        response_data = {
            "status": "healthy" if overall_healthy else "unhealthy",
            "triggered_by": user_id,
            "triggered_at": health_results[list(health_results.keys())[0]].last_check,
            "components": {
                name: {
                    "healthy": status.healthy,
                    "response_time": status.response_time,
                    "error_message": status.error_message,
                    "metadata": status.metadata,
                }
                for name, status in health_results.items()
            },
            "summary": {
                "total_components": len(health_results),
                "healthy_components": sum(1 for status in health_results.values() if status.healthy),
                "unhealthy_components": sum(1 for status in health_results.values() if not status.healthy),
                "avg_response_time": sum(
                    status.response_time for status in health_results.values() if status.response_time is not None
                )
                / len([s for s in health_results.values() if s.response_time is not None]),
            },
        }

        status_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(content=response_data, status_code=status_code)

    except Exception as e:
        logger.error("Failed to trigger family health check: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "HEALTH_CHECK_TRIGGER_FAILED", "message": "Failed to trigger family system health check"},
        )


@router.get("/readiness")
async def family_system_readiness(request: Request) -> JSONResponse:
    """
    Family system readiness probe for Kubernetes deployments.

    Lightweight readiness check that verifies the family system
    is ready to handle traffic. Checks essential components only.

    **Rate Limiting:** 20 requests per minute per IP

    **No Authentication Required** - Designed for Kubernetes probes

    **Returns:**
    - Ready/not ready status
    - Essential component status
    - Quick response for probe systems
    """
    # Apply IP-based rate limiting for unauthenticated endpoint
    await security_manager.check_rate_limit(
        request, f"family_readiness_{request.client.host}", rate_limit_requests=20, rate_limit_period=60
    )

    try:
        # Quick essential checks only
        from second_brain_database.database import db_manager
        from second_brain_database.managers.redis_manager import redis_manager

        # Check database connectivity
        db_healthy = await db_manager.health_check()

        # Check Redis connectivity
        try:
            redis_conn = await redis_manager.get_redis()
            await redis_conn.ping()
            redis_healthy = True
        except Exception:
            redis_healthy = False

        # Check family collections exist
        try:
            families_collection = db_manager.get_collection("families")
            await families_collection.find_one({}, {"_id": 1})
            collections_healthy = True
        except Exception:
            collections_healthy = False

        overall_ready = db_healthy and redis_healthy and collections_healthy

        response_data = {
            "status": "ready" if overall_ready else "not_ready",
            "components": {"database": db_healthy, "redis": redis_healthy, "family_collections": collections_healthy},
        }

        status_code = status.HTTP_200_OK if overall_ready else status.HTTP_503_SERVICE_UNAVAILABLE

        return JSONResponse(content=response_data, status_code=status_code)

    except Exception as e:
        logger.error("Family readiness check failed: %s", e)
        return JSONResponse(
            content={"status": "not_ready", "error": "readiness_check_failed", "message": str(e)},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@router.get("/liveness")
async def family_system_liveness(request: Request) -> JSONResponse:
    """
    Family system liveness probe for Kubernetes deployments.

    Simple liveness check that confirms the family system components
    are alive and responding. Does not perform heavy checks.

    **Rate Limiting:** 30 requests per minute per IP

    **No Authentication Required** - Designed for Kubernetes probes

    **Returns:**
    - Alive status
    - Basic system information
    """
    # Apply IP-based rate limiting for unauthenticated endpoint
    await security_manager.check_rate_limit(
        request, f"family_liveness_{request.client.host}", rate_limit_requests=30, rate_limit_period=60
    )

    try:
        # Very basic liveness check - just verify imports work
        from second_brain_database.managers.family_manager import family_manager
        from second_brain_database.managers.family_monitoring import family_monitor

        return JSONResponse(
            content={"status": "alive", "family_system": "operational", "monitoring": "active"},
            status_code=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.error("Family liveness check failed: %s", e)
        return JSONResponse(
            content={"status": "not_alive", "error": "liveness_check_failed", "message": str(e)},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@router.get("/error-handling")
async def get_error_handling_health(
    request: Request, current_user: dict = Depends(require_admin)  # ✅ Admin-only access
) -> JSONResponse:
    """
    Get health status of the error handling and resilience system.

    Provides comprehensive information about:
    - Circuit breaker states and statistics
    - Bulkhead capacity and utilization
    - Error monitoring statistics
    - Recovery system status
    - Recent error patterns and alerts

    **Rate Limiting:** 5 requests per hour per user

    **Requirements:**
    - User must be authenticated as admin

    **Returns:**
    - Error handling system health status
    - Circuit breaker and bulkhead statistics
    - Error monitoring metrics
    - Recovery system performance
    """
    user_id = str(current_user["_id"])

    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, f"error_handling_health_{user_id}", rate_limit_requests=5, rate_limit_period=3600
    )

    try:
        from second_brain_database.utils.error_handling import get_error_handling_health
        from second_brain_database.utils.error_monitoring import error_monitor
        from second_brain_database.utils.error_recovery import recovery_manager

        # Get error handling component health
        error_handling_health = await get_error_handling_health()

        # Get recovery system statistics
        recovery_stats = recovery_manager.get_recovery_stats()
        recent_recoveries = recovery_manager.get_recent_recoveries(limit=5)

        # Get error monitoring statistics
        monitoring_stats = error_monitor.get_monitoring_stats()
        error_patterns = error_monitor.get_error_patterns(limit=10)
        active_alerts = error_monitor.get_active_alerts()

        logger.info("Error handling health check requested by admin %s", user_id)

        response_data = {
            "status": "healthy" if error_handling_health["overall_healthy"] else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_handling": error_handling_health,
            "recovery_system": {"statistics": recovery_stats, "recent_recoveries": recent_recoveries},
            "error_monitoring": {
                "statistics": monitoring_stats,
                "top_error_patterns": error_patterns,
                "active_alerts": active_alerts,
            },
            "system_resilience": {
                "circuit_breakers_healthy": all(
                    cb["state"] != "open" for cb in error_handling_health["circuit_breakers"].values()
                ),
                "bulkheads_healthy": all(
                    bulkhead["rejection_rate"] < 0.1 for bulkhead in error_handling_health["bulkheads"].values()
                ),
                "recovery_rate_healthy": recovery_stats["success_rate"] > 0.7,
                "error_rate_healthy": monitoring_stats["error_statistics"]["error_rate_24h"] < 10.0,
            },
        }

        status_code = (
            status.HTTP_200_OK if error_handling_health["overall_healthy"] else status.HTTP_503_SERVICE_UNAVAILABLE
        )

        return JSONResponse(content=response_data, status_code=status_code)

    except Exception as e:
        logger.error("Failed to get error handling health status: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ERROR_HANDLING_HEALTH_CHECK_FAILED",
                "message": "Failed to retrieve error handling system health status",
            },
        )
