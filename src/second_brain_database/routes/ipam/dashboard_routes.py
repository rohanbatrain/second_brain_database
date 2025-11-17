"""
IPAM Dashboard API Routes.

Simplified dashboard endpoints that match frontend expectations.
These are convenience wrappers around the main statistics endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from typing import Dict, Any, Optional

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.ipam_manager import ipam_manager
from second_brain_database.routes.ipam.dependencies import (
    require_ipam_read,
    check_ipam_rate_limit,
)

logger = get_logger(prefix="[IPAM Dashboard]")

# Create router with prefix
router = APIRouter(
    prefix="/ipam/dashboard",
    tags=["IPAM - Dashboard"]
)


@router.get(
    "/stats",
    summary="Get dashboard statistics",
    description="""
    Get comprehensive dashboard statistics including:
    - Total countries, regions, and hosts
    - Overall utilization percentage
    - Recent activity summary
    
    **Rate Limiting:** 500 requests per hour per user
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved dashboard statistics",
            "content": {
                "application/json": {
                    "example": {
                        "total_countries": 5,
                        "total_regions": 150,
                        "total_hosts": 3500,
                        "overall_utilization": 45.2,
                        "active_regions": 145,
                        "reserved_regions": 5
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_dashboard_stats(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get dashboard statistics."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "dashboard_stats", limit=500, period=3600)
    
    try:
        result = await ipam_manager.calculate_dashboard_stats(user_id)
        logger.info("User %s retrieved dashboard stats", user_id)
        return result
    except Exception as e:
        logger.error("Failed to get dashboard stats for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "dashboard_stats_failed", "message": "Failed to retrieve dashboard statistics"}
        )


@router.get(
    "/top-countries",
    summary="Get top countries by utilization",
    description="""
    Get the top N countries ranked by utilization percentage.
    
    **Rate Limiting:** 500 requests per hour per user
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved top countries",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "country": "India",
                            "continent": "Asia",
                            "total_regions": 50,
                            "allocated_hosts": 1200,
                            "utilization_percentage": 78.5
                        }
                    ]
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_top_countries(
    request: Request,
    limit: int = Query(10, ge=1, le=50, description="Number of countries to return"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get top countries by utilization."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "dashboard_top_countries", limit=500, period=3600)
    
    try:
        result = await ipam_manager.get_top_countries_by_utilization(user_id, limit=limit)
        logger.info("User %s retrieved top %d countries", user_id, limit)
        return result
    except Exception as e:
        logger.error("Failed to get top countries for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "top_countries_failed", "message": "Failed to retrieve top countries"}
        )


@router.get(
    "/recent-activity",
    summary="Get recent activity",
    description="""
    Get recent allocation and modification activity.
    
    **Rate Limiting:** 500 requests per hour per user
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved recent activity",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "timestamp": "2025-11-16T10:30:00Z",
                            "action": "region_created",
                            "resource_type": "region",
                            "resource_id": "550e8400-e29b-41d4-a716-446655440000",
                            "resource_name": "Mumbai DC1",
                            "user_id": "user123"
                        }
                    ]
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    }
)
async def get_recent_activity(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="Number of activities to return"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get recent activity."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "dashboard_recent_activity", limit=500, period=3600)
    
    try:
        result = await ipam_manager.get_recent_activity(user_id, limit=limit)
        logger.info("User %s retrieved recent activity (limit=%d)", user_id, limit)
        return result
    except Exception as e:
        logger.error("Failed to get recent activity for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "recent_activity_failed", "message": "Failed to retrieve recent activity"}
        )
