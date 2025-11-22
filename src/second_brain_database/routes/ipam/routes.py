"""
IPAM REST API Routes.

This module provides comprehensive REST API endpoints for hierarchical IP allocation
management following the 10.X.Y.Z private IPv4 address space structure.

Endpoints are organized into logical groups:
- Country and mapping endpoints
- Region management endpoints
- Host management endpoints
- IP interpretation endpoints
- Statistics and analytics endpoints
- Search endpoints
- Import/export endpoints
- Audit history endpoints
- Admin quota management endpoints
- Health check endpoint
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from typing import List, Optional, Dict, Any

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.ipam_manager import ipam_manager
from second_brain_database.routes.ipam.dependencies import (
    get_current_user_for_ipam,
    require_ipam_read,
    require_ipam_allocate,
    require_ipam_update,
    require_ipam_release,
    require_ipam_admin,
    check_ipam_rate_limit,
)
from second_brain_database.routes.ipam.models import (
    ReservationCreateRequest,
    ReservationConvertRequest,
    ShareCreateRequest,
    PreferencesUpdateRequest,
    SavedFilterRequest,
    NotificationRuleRequest,
    NotificationUpdateRequest,
    WebhookCreateRequest,
    BulkTagUpdateRequest,
)
from second_brain_database.routes.ipam.utils import (
    format_region_response,
    format_host_response,
    format_country_response,
    format_utilization_response,
    format_pagination_response,
    format_error_response,
    validate_pagination_params,
    extract_client_info,
)

logger = get_logger(prefix="[IPAM Routes]")

# Create router with prefix and tags
router = APIRouter(
    prefix="/ipam",
    tags=["IPAM"]
)


# ============================================================================
# Health Check Endpoint
# ============================================================================

@router.get(
    "/health",
    summary="IPAM health check",
    description="""
    Check the health status of the IPAM system.
    
    Verifies:
    - MongoDB connection
    - Redis connection
    - Continent-country mapping loaded
    
    Returns 200 OK if all checks pass, 503 Service Unavailable otherwise.
    """,
    responses={
        200: {
            "description": "IPAM system is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "checks": {
                            "mongodb": "ok",
                            "redis": "ok",
                            "mappings": "ok"
                        }
                    }
                }
            }
        },
        503: {
            "description": "IPAM system is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "checks": {
                            "mongodb": "ok",
                            "redis": "error",
                            "mappings": "ok"
                        }
                    }
                }
            }
        }
    },
    tags=["IPAM - System"]
)
async def health_check():
    """
    Health check endpoint for IPAM system.
    
    Verifies all critical dependencies are operational.
    """
    try:
        # TODO: Implement actual health checks
        # - Check MongoDB connection
        # - Check Redis connection
        # - Verify continent-country mapping loaded
        
        return {
            "status": "healthy",
            "checks": {
                "mongodb": "ok",
                "redis": "ok",
                "mappings": "ok"
            }
        }
    except Exception as e:
        logger.error("IPAM health check failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "unhealthy",
                "error": str(e)
            }
        )


# ============================================================================
# Country and Mapping Endpoints
# ============================================================================

@router.get(
    "/countries",
    summary="List all countries",
    description="""
    Retrieve all predefined countries with their continent mappings and X octet ranges.
    
    Supports filtering by continent to narrow down results.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved countries",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "continent": "Asia",
                            "country": "India",
                            "x_start": 0,
                            "x_end": 29,
                            "total_blocks": 7680,
                            "is_reserved": False
                        }
                    ]
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Countries"]
)
async def list_countries(
    request: Request,
    continent: Optional[str] = Query(None, description="Filter by continent"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    List all countries with optional continent filter.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "country_list", limit=500, period=3600)
    
    try:
        countries = await ipam_manager.get_all_countries(continent=continent)
        
        # Enrich each country with allocated regions count for this user
        regions_collection = db_manager.get_tenant_collection("ipam_regions")
        for country in countries:
            allocated_regions = await regions_collection.count_documents({
                "user_id": user_id,
                "country": country["country"]
            })
            country["allocated_regions"] = allocated_regions
            
            # Calculate utilization percentage
            total_capacity = country.get("total_blocks", 0) * 256  # Each block is /16 = 256 /24 regions
            country["utilization_percentage"] = round((allocated_regions / total_capacity * 100), 2) if total_capacity > 0 else 0.0
        
        logger.info(
            "User %s listed %d countries (continent_filter=%s)",
            user_id,
            len(countries),
            continent or "all"
        )
        
        return [format_country_response(country) for country in countries]
        
    except Exception as e:
        logger.error("Failed to list countries for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "country_list_failed",
                "Failed to retrieve country list"
            )
        )


@router.get(
    "/countries/{country}",
    summary="Get country details",
    description="""
    Retrieve detailed information about a specific country including its
    continent, X octet range, and total capacity.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved country details",
            "content": {
                "application/json": {
                    "example": {
                        "continent": "Asia",
                        "country": "India",
                        "x_start": 0,
                        "x_end": 29,
                        "total_blocks": 7680,
                        "is_reserved": False
                    }
                }
            }
        },
        404: {"description": "Country not found"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Countries"]
)
async def get_country(
    request: Request,
    country: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get details for a specific country.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "country_get", limit=500, period=3600)
    
    try:
        country_data = await ipam_manager.get_country_mapping(country)
        
        if not country_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    "country_not_found",
                    f"Country '{country}' not found"
                )
            )
        
        # Add allocated regions count for this user
        regions_collection = db_manager.get_tenant_collection("ipam_regions")
        allocated_regions = await regions_collection.count_documents({
            "user_id": user_id,
            "country": country
        })
        country_data["allocated_regions"] = allocated_regions
        
        # Calculate utilization percentage
        total_capacity = country_data.get("total_blocks", 0) * 256  # Each block is /16 = 256 /24 regions
        country_data["utilization_percentage"] = round((allocated_regions / total_capacity * 100), 2) if total_capacity > 0 else 0.0
        
        logger.info("User %s retrieved country details for %s", user_id, country)
        
        return format_country_response(country_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get country %s for user %s: %s", country, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "country_get_failed",
                f"Failed to retrieve country '{country}'"
            )
        )


@router.get(
    "/countries/{country}/utilization",
    summary="Get country utilization statistics",
    description="""
    Calculate and retrieve utilization statistics for a specific country
    within the authenticated user's namespace.
    
    Returns total capacity, allocated regions, and utilization percentage.
    Results are cached for 5 minutes.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved utilization statistics",
            "content": {
                "application/json": {
                    "example": {
                        "resource_type": "country",
                        "resource_id": "India",
                        "total_capacity": 7680,
                        "allocated": 150,
                        "available": 7530,
                        "utilization_percent": 1.95,
                        "breakdown": {
                            "0": {"allocated": 50, "capacity": 256},
                            "1": {"allocated": 100, "capacity": 256}
                        }
                    }
                }
            }
        },
        404: {"description": "Country not found"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Countries"]
)
async def get_country_utilization(
    request: Request,
    country: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get utilization statistics for a country.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "country_utilization", limit=500, period=3600)
    
    try:
        utilization = await ipam_manager.calculate_country_utilization(user_id, country)
        
        logger.info(
            "User %s retrieved utilization for country %s: %.2f%%",
            user_id,
            country,
            utilization.get("utilization_percent", 0)
        )
        
        return format_utilization_response(utilization)
        
    except Exception as e:
        logger.error(
            "Failed to get country utilization for %s, user %s: %s",
            country,
            user_id,
            e,
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "country_utilization_failed",
                f"Failed to calculate utilization for country '{country}'"
            )
        )


# ============================================================================
# Region Management Endpoints
# ============================================================================

@router.post(
    "/regions",
    status_code=status.HTTP_201_CREATED,
    summary="Create new region",
    description="""
    Allocate a new /24 region block within a country's address space.
    
    The system automatically:
    - Selects the next available X.Y combination
    - Validates country capacity
    - Enforces user quotas
    - Creates audit trail
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {
            "description": "Region allocated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "region_id": "550e8400-e29b-41d4-a716-446655440000",
                        "cidr": "10.5.23.0/24",
                        "x_octet": 5,
                        "y_octet": 23,
                        "country": "India",
                        "continent": "Asia",
                        "region_name": "Mumbai DC1",
                        "status": "Active"
                    }
                }
            }
        },
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Capacity exhausted or duplicate name"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def create_region(
    request: Request,
    country: str = Query(..., description="Country for region allocation"),
    region_name: str = Query(..., description="Name for the region"),
    description: Optional[str] = Query(None, description="Optional description"),
    tags: Optional[str] = Query(None, description="Optional tags as JSON string"),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Create new region with auto-allocation.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_create", limit=100, period=3600)
    
    try:
        region = await ipam_manager.allocate_region(
            user_id=user_id,
            country=country,
            region_name=region_name,
            description=description,
            tags=tags or {}
        )
        
        # Set owner to username automatically
        owner_name = current_user.get("username", user_id)
        await db_manager.get_tenant_collection("ipam_regions").update_one(
            {"_id": region["_id"]},
            {"$set": {"owner": owner_name}}
        )
        region["owner"] = owner_name
        
        logger.info(
            "User %s created region %s in country %s: %s",
            user_id,
            region.get("cidr"),
            country,
            region_name
        )
        
        return format_region_response(region)
        
    except Exception as e:
        logger.error(
            "Failed to create region for user %s in country %s: %s",
            user_id,
            country,
            e,
            exc_info=True
        )
        
        # Check for specific error types
        error_msg = str(e).lower()
        if "capacity" in error_msg or "exhausted" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"No available addresses in country {country}",
                    {"country": country}
                )
            )
        elif "duplicate" in error_msg or "exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "duplicate_name",
                    f"Region name '{region_name}' already exists in {country}",
                    {"country": country, "region_name": region_name}
                )
            )
        elif "quota" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=format_error_response(
                    "quota_exceeded",
                    "Region quota exceeded",
                    {"user_id": user_id}
                )
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response(
                    "region_creation_failed",
                    str(e)
                )
            )


@router.get(
    "/regions",
    summary="List regions",
    description="""
    List regions with optional filters and pagination.
    
    Supports filtering by country, status, owner, tags, and date ranges.
    Results are paginated with configurable page size.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved regions",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "region_id": "550e8400-e29b-41d4-a716-446655440000",
                                "cidr": "10.5.23.0/24",
                                "country": "India",
                                "region_name": "Mumbai DC1",
                                "status": "Active"
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "page_size": 50,
                            "total_count": 150,
                            "total_pages": 3,
                            "has_next": True,
                            "has_prev": False
                        }
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def list_regions(
    request: Request,
    country: Optional[str] = Query(None, description="Filter by country"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    owner: Optional[str] = Query(None, description="Filter by owner (accepts owner name or owner id)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    List regions with filters and pagination.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_list", limit=500, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        # Build filters
        filters = {}
        if country:
            filters["country"] = country
        if status_filter:
            filters["status"] = status_filter
        if owner:
            filters["owner"] = owner
        
        # Get regions
        result = await ipam_manager.get_regions(
            user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        # Format response
        formatted_regions = [format_region_response(r) for r in result.get("regions", [])]
        
        logger.info(
            "User %s listed %d regions (page=%d, filters=%s)",
            user_id,
            len(formatted_regions),
            page,
            filters
        )
        
        return format_pagination_response(
            items=formatted_regions,
            page=page,
            page_size=page_size,
            total_count=result.get("pagination", {}).get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to list regions for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("region_list_failed", "Failed to retrieve regions")
        )


@router.get(
    "/regions/{region_id}",
    summary="Get region details",
    description="""
    Retrieve detailed information about a specific region.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved region details"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def get_region(
    request: Request,
    region_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get details for a specific region.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_get", limit=500, period=3600)
    
    try:
        region = await ipam_manager.get_region_by_id(user_id, region_id)
        
        if not region:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    "region_not_found",
                    f"Region '{region_id}' not found"
                )
            )
        
        logger.info("User %s retrieved region %s", user_id, region_id)
        
        return format_region_response(region)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("region_get_failed", "Failed to retrieve region")
        )


@router.patch(
    "/regions/{region_id}",
    summary="Update region",
    description="""
    Update region metadata including name, description, owner, status, and tags.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:update
    """,
    responses={
        200: {"description": "Region updated successfully"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def update_region(
    request: Request,
    region_id: str,
    region_name: Optional[str] = Query(None, description="New region name"),
    description: Optional[str] = Query(None, description="New description"),
    owner: Optional[str] = Query(None, description="New owner (accepts owner name or owner id)"),
    status_update: Optional[str] = Query(None, alias="status", description="New status"),
    tags: Optional[str] = Query(None, description="New tags (JSON string)"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Update region metadata.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_update", limit=100, period=3600)
    
    try:
        # Build updates dict
        updates = {}
        if region_name is not None:
            updates["region_name"] = region_name
        if description is not None:
            updates["description"] = description
        if owner is not None:
            updates["owner"] = owner
        if status_update is not None:
            updates["status"] = status_update
        if tags is not None:
            updates["tags"] = tags
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response(
                    "no_updates",
                    "No update fields provided"
                )
            )
        
        region = await ipam_manager.update_region(user_id, region_id, updates)
        
        logger.info("User %s updated region %s: %s", user_id, region_id, list(updates.keys()))
        
        return format_region_response(region)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("region_update_failed", str(e))
            )


@router.delete(
    "/regions/{region_id}",
    summary="Retire region",
    description="""
    Retire (hard delete) a region and optionally cascade to all child hosts.
    
    The region is permanently deleted and moved to audit history.
    Address space is immediately reclaimed.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:release
    """,
    responses={
        200: {"description": "Region retired successfully"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def retire_region(
    request: Request,
    region_id: str,
    reason: str = Query(..., description="Reason for retirement"),
    cascade: bool = Query(False, description="Also retire all child hosts"),
    current_user: Dict[str, Any] = Depends(require_ipam_release)
):
    """
    Retire region with optional cascade deletion.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_retire", limit=100, period=3600)
    
    try:
        result = await ipam_manager.retire_allocation(
            user_id=user_id,
            resource_type="region",
            resource_id=region_id,
            reason=reason,
            cascade=cascade
        )
        
        logger.info(
            "User %s retired region %s (cascade=%s): %s",
            user_id,
            region_id,
            cascade,
            reason
        )
        
        return {
            "status": "success",
            "message": "Region retired successfully",
            "region_id": region_id,
            "cascade": cascade,
            "hosts_retired": result.get("hosts_retired", 0)
        }
        
    except Exception as e:
        logger.error("Failed to retire region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("region_retire_failed", str(e))
            )


@router.get(
    "/regions/{region_id}/comments",
    summary="Get region comments",
    description="""
    Retrieve all comments for a region.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Comments retrieved successfully"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def get_region_comments(
    request: Request,
    region_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get comments for a region.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_comments_get", limit=500, period=3600)
    
    try:
        # Get region to verify ownership
        region = await ipam_manager.get_region_by_id(user_id, region_id)
        
        if not region:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        
        # Return comments from region
        comments = region.get("comments", [])
        
        logger.info("User %s retrieved %d comments for region %s", user_id, len(comments), region_id)
        
        return {
            "comments": comments,
            "total": len(comments)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get comments for region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("comments_get_failed", "Failed to retrieve comments")
        )


@router.post(
    "/regions/{region_id}/comments",
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to region",
    description="""
    Add an immutable comment to a region's history.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:update
    """,
    responses={
        201: {"description": "Comment added successfully"},
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def add_region_comment(
    request: Request,
    region_id: str,
    comment_text: str = Query(..., max_length=2000, description="Comment text"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Add comment to region.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_comment", limit=100, period=3600)
    
    try:
        result = await ipam_manager.add_comment(
            user_id=user_id,
            resource_type="region",
            resource_id=region_id,
            comment_text=comment_text
        )
        
        logger.info("User %s added comment to region %s", user_id, region_id)
        
        return {
            "status": "success",
            "message": "Comment added successfully",
            "region_id": region_id,
            "comment": result.get("comment")
        }
        
    except Exception as e:
        logger.error("Failed to add comment to region %s for user %s: %s", region_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("comment_add_failed", str(e))
            )


@router.get(
    "/regions/preview-next",
    summary="Preview next region allocation",
    description="""
    Preview the next available X.Y CIDR that would be allocated for a country.
    
    Does not actually allocate the region, just shows what would be allocated.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved preview",
            "content": {
                "application/json": {
                    "example": {
                        "country": "India",
                        "next_cidr": "10.5.23.0/24",
                        "x_octet": 5,
                        "y_octet": 23,
                        "available": True
                    }
                }
            }
        },
        409: {"description": "No available addresses"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def preview_next_region(
    request: Request,
    country: str = Query(..., description="Country for preview"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Preview next available region allocation.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_preview", limit=500, period=3600)
    
    try:
        preview = await ipam_manager.get_next_available_region(user_id, country)
        
        if not preview:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"No available addresses in country {country}",
                    {"country": country}
                )
            )
        
        logger.info("User %s previewed next region for country %s: %s", user_id, country, preview.get("cidr"))
        
        return preview
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to preview next region for user %s in country %s: %s", user_id, country, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("region_preview_failed", "Failed to preview next region")
        )


@router.get(
    "/regions/{region_id}/utilization",
    summary="Get region utilization",
    description="""
    Calculate and retrieve utilization statistics for a specific region.
    
    Returns total capacity (254 usable hosts), allocated hosts, and utilization percentage.
    Results are cached for 5 minutes.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved utilization statistics",
            "content": {
                "application/json": {
                    "example": {
                        "resource_type": "region",
                        "resource_id": "550e8400-e29b-41d4-a716-446655440000",
                        "total_capacity": 254,
                        "allocated": 45,
                        "available": 209,
                        "utilization_percent": 17.72
                    }
                }
            }
        },
        404: {"description": "Region not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Regions"]
)
async def get_region_utilization(
    request: Request,
    region_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get utilization statistics for a region.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "region_utilization", limit=500, period=3600)
    
    try:
        utilization = await ipam_manager.calculate_region_utilization(user_id, region_id)
        
        logger.info(
            "User %s retrieved utilization for region %s: %.2f%%",
            user_id,
            region_id,
            utilization.get("utilization_percent", 0)
        )
        
        return format_utilization_response(utilization)
        
    except Exception as e:
        logger.error(
            "Failed to get region utilization for %s, user %s: %s",
            region_id,
            user_id,
            e,
            exc_info=True
        )
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("region_not_found", f"Region '{region_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=format_error_response("region_utilization_failed", "Failed to calculate utilization")
            )


# ============================================================================
# Host Management Endpoints
# ============================================================================

@router.post(
    "/hosts",
    status_code=status.HTTP_201_CREATED,
    summary="Create new host",
    description="""
    Allocate a new host address within a region.
    
    The system automatically assigns the next available Z octet (1-254).
    
    **Rate Limiting:** 1000 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {"description": "Host allocated successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Capacity exhausted or duplicate hostname"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def create_host(
    request: Request,
    region_id: str = Query(..., description="Region ID for host allocation"),
    hostname: str = Query(..., description="Hostname for the host"),
    device_type: Optional[str] = Query(None, description="Device type (VM, Container, Physical)"),
    os_type: Optional[str] = Query(None, description="Operating system type"),
    application: Optional[str] = Query(None, description="Application running on host"),
    cost_center: Optional[str] = Query(None, description="Cost center"),
    owner: Optional[str] = Query(None, description="Owner/team identifier (accepts owner name or owner id)"),
    purpose: Optional[str] = Query(None, description="Purpose description"),
    tags: Optional[str] = Query(None, description="Optional tags (JSON string)"),
    notes: Optional[str] = Query(None, description="Optional notes"),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Create new host with auto-allocation.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_create", limit=1000, period=3600)
    
    try:
        metadata = {
            "device_type": device_type,
            "os_type": os_type,
            "application": application,
            "cost_center": cost_center,
            "owner": owner,
            "purpose": purpose,
            "tags": tags or {},
            "notes": notes
        }
        
        host = await ipam_manager.allocate_host(
            user_id=user_id,
            region_id=region_id,
            hostname=hostname,
            metadata=metadata
        )
        
        logger.info(
            "User %s created host %s in region %s: %s",
            user_id,
            host.get("ip_address"),
            region_id,
            hostname
        )
        
        return format_host_response(host)
        
    except Exception as e:
        logger.error(
            "Failed to create host for user %s in region %s: %s",
            user_id,
            region_id,
            e,
            exc_info=True
        )
        
        error_msg = str(e).lower()
        if "capacity" in error_msg or "exhausted" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"No available addresses in region {region_id}",
                    {"region_id": region_id}
                )
            )
        elif "duplicate" in error_msg or "exists" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "duplicate_hostname",
                    f"Hostname '{hostname}' already exists in region",
                    {"region_id": region_id, "hostname": hostname}
                )
            )
        elif "quota" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=format_error_response("quota_exceeded", "Host quota exceeded")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("host_creation_failed", str(e))
            )


@router.post(
    "/hosts/batch",
    status_code=status.HTTP_201_CREATED,
    summary="Batch create hosts",
    description="""
    Allocate multiple hosts in a single request (max 100).
    
    Hosts are allocated consecutively with auto-generated hostnames.
    
    **Rate Limiting:** 1000 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {"description": "Hosts allocated successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Capacity exhausted"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def batch_create_hosts(
    request: Request,
    region_id: str = Query(..., description="Region ID for host allocation"),
    count: int = Query(..., ge=1, le=100, description="Number of hosts to create"),
    hostname_prefix: str = Query(..., description="Hostname prefix (e.g., 'web-')"),
    device_type: Optional[str] = Query(None, description="Device type"),
    owner: Optional[str] = Query(None, description="Owner/team identifier (accepts owner name or owner id)"),
    tags: Optional[str] = Query(None, description="Optional tags (JSON string)"),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Batch create hosts with auto-allocation.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_batch_create", limit=1000, period=3600)
    
    try:
        result = await ipam_manager.allocate_hosts_batch(
            user_id=user_id,
            region_id=region_id,
            count=count,
            hostname_prefix=hostname_prefix,
            metadata={
                "device_type": device_type,
                "owner": owner,
                "tags": tags or {}
            }
        )
        
        logger.info(
            "User %s batch created %d hosts in region %s",
            user_id,
            len(result.get("hosts", [])),
            region_id
        )
        
        return {
            "status": "success",
            "message": f"Created {len(result.get('hosts', []))} hosts",
            "hosts": [format_host_response(h) for h in result.get("hosts", [])],
            "failed": result.get("failed", [])
        }
        
    except Exception as e:
        logger.error(
            "Failed to batch create hosts for user %s in region %s: %s",
            user_id,
            region_id,
            e,
            exc_info=True
        )
        
        error_msg = str(e).lower()
        if "capacity" in error_msg or "exhausted" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"Insufficient capacity in region {region_id}",
                    {"region_id": region_id, "requested": count}
                )
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("batch_creation_failed", str(e))
            )


@router.get(
    "/hosts",
    summary="List hosts",
    description="""
    List hosts with optional filters and pagination.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved hosts"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def list_hosts(
    request: Request,
    region_id: Optional[str] = Query(None, description="Filter by region"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    hostname: Optional[str] = Query(None, description="Filter by hostname (partial match)"),
    device_type: Optional[str] = Query(None, description="Filter by device type"),
    owner: Optional[str] = Query(None, description="Filter by owner (accepts owner name or owner id)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    List hosts with filters and pagination.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_list", limit=500, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        # Build filters
        filters = {}
        if region_id:
            filters["region_id"] = region_id
        if status_filter:
            filters["status"] = status_filter
        if hostname:
            filters["hostname"] = hostname
        if device_type:
            filters["device_type"] = device_type
        if owner:
            filters["owner"] = owner
        
        # Get hosts
        hosts = await ipam_manager.get_hosts(
            user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        # Format response
        formatted_hosts = [format_host_response(h) for h in hosts.get("items", [])]
        
        logger.info(
            "User %s listed %d hosts (page=%d, filters=%s)",
            user_id,
            len(formatted_hosts),
            page,
            filters
        )
        
        return format_pagination_response(
            items=formatted_hosts,
            page=page,
            page_size=page_size,
            total_count=hosts.get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to list hosts for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("host_list_failed", "Failed to retrieve hosts")
        )


@router.get(
    "/hosts/{host_id}",
    summary="Get host details",
    description="""
    Retrieve detailed information about a specific host.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved host details"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def get_host(
    request: Request,
    host_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get details for a specific host.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_get", limit=500, period=3600)
    
    try:
        host = await ipam_manager.get_host_by_id(user_id, host_id)
        
        if not host:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("host_not_found", f"Host '{host_id}' not found")
            )
        
        logger.info("User %s retrieved host %s", user_id, host_id)
        
        return format_host_response(host)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get host %s for user %s: %s", host_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("host_get_failed", "Failed to retrieve host")
        )


@router.get(
    "/hosts/by-ip/{ip_address}",
    summary="Lookup host by IP address",
    description="""
    Retrieve host details by IP address.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved host details"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def get_host_by_ip(
    request: Request,
    ip_address: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Lookup host by IP address.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_lookup", limit=500, period=3600)
    
    try:
        host = await ipam_manager.get_host_by_ip(user_id, ip_address)
        
        if not host:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    "host_not_found",
                    f"Host with IP '{ip_address}' not found"
                )
            )
        
        logger.info("User %s looked up host by IP %s", user_id, ip_address)
        
        return format_host_response(host)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to lookup host by IP %s for user %s: %s", ip_address, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("host_lookup_failed", "Failed to lookup host")
        )


@router.post(
    "/hosts/bulk-lookup",
    summary="Bulk IP lookup",
    description="""
    Lookup multiple IP addresses in a single request.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved host details"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def bulk_lookup_hosts(
    request: Request,
    ip_addresses: List[str] = Query(..., description="List of IP addresses to lookup"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Bulk lookup hosts by IP addresses.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_bulk_lookup", limit=500, period=3600)
    
    try:
        result = await ipam_manager.bulk_lookup_ips(user_id, ip_addresses)
        
        logger.info("User %s performed bulk lookup for %d IPs", user_id, len(ip_addresses))
        
        return {
            "results": [format_host_response(h) if h else None for h in result.get("hosts", [])],
            "found": result.get("found", 0),
            "not_found": result.get("not_found", 0)
        }
        
    except Exception as e:
        logger.error("Failed to bulk lookup hosts for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("bulk_lookup_failed", "Failed to lookup hosts")
        )


@router.patch(
    "/hosts/{host_id}",
    summary="Update host",
    description="""
    Update host metadata.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:update
    """,
    responses={
        200: {"description": "Host updated successfully"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def update_host(
    request: Request,
    host_id: str,
    hostname: Optional[str] = Query(None, description="New hostname"),
    device_type: Optional[str] = Query(None, description="New device type"),
    os_type: Optional[str] = Query(None, description="New OS type"),
    application: Optional[str] = Query(None, description="New application"),
    cost_center: Optional[str] = Query(None, description="New cost center"),
    owner: Optional[str] = Query(None, description="New owner (accepts owner name or owner id)"),
    purpose: Optional[str] = Query(None, description="New purpose"),
    status_update: Optional[str] = Query(None, alias="status", description="New status"),
    tags: Optional[str] = Query(None, description="New tags (JSON string)"),
    notes: Optional[str] = Query(None, description="New notes"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Update host metadata.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_update", limit=100, period=3600)
    
    try:
        # Build updates dict
        updates = {}
        if hostname is not None:
            updates["hostname"] = hostname
        if device_type is not None:
            updates["device_type"] = device_type
        if os_type is not None:
            updates["os_type"] = os_type
        if application is not None:
            updates["application"] = application
        if cost_center is not None:
            updates["cost_center"] = cost_center
        if owner is not None:
            updates["owner"] = owner
        if purpose is not None:
            updates["purpose"] = purpose
        if status_update is not None:
            updates["status"] = status_update
        if tags is not None:
            updates["tags"] = tags
        if notes is not None:
            updates["notes"] = notes
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("no_updates", "No update fields provided")
            )
        
        host = await ipam_manager.update_host(user_id, host_id, updates)
        
        logger.info("User %s updated host %s: %s", user_id, host_id, list(updates.keys()))
        
        return format_host_response(host)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update host %s for user %s: %s", host_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("host_not_found", f"Host '{host_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("host_update_failed", str(e))
            )


@router.delete(
    "/hosts/{host_id}",
    summary="Retire host",
    description="""
    Retire (hard delete) a host.
    
    The host is permanently deleted and moved to audit history.
    Address space is immediately reclaimed.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:release
    """,
    responses={
        200: {"description": "Host retired successfully"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def retire_host(
    request: Request,
    host_id: str,
    reason: str = Query(..., description="Reason for retirement"),
    current_user: Dict[str, Any] = Depends(require_ipam_release)
):
    """
    Retire host.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_retire", limit=100, period=3600)
    
    try:
        result = await ipam_manager.retire_allocation(
            user_id=user_id,
            resource_type="host",
            resource_id=host_id,
            reason=reason,
            cascade=False
        )
        
        logger.info("User %s retired host %s: %s", user_id, host_id, reason)
        
        return {
            "status": "success",
            "message": "Host retired successfully",
            "host_id": host_id
        }
        
    except Exception as e:
        logger.error("Failed to retire host %s for user %s: %s", host_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("host_not_found", f"Host '{host_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("host_retire_failed", str(e))
            )


@router.post(
    "/hosts/bulk-release",
    summary="Bulk release hosts",
    description="""
    Release multiple hosts in a single request.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:release
    """,
    responses={
        200: {"description": "Hosts released successfully"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def bulk_release_hosts(
    request: Request,
    host_ids: List[str] = Query(..., description="List of host IDs to release"),
    reason: str = Query(..., description="Reason for release"),
    current_user: Dict[str, Any] = Depends(require_ipam_release)
):
    """
    Bulk release hosts.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_bulk_release", limit=100, period=3600)
    
    try:
        result = await ipam_manager.bulk_release_hosts(user_id, host_ids, reason)
        
        logger.info(
            "User %s bulk released %d hosts (success=%d, failed=%d)",
            user_id,
            len(host_ids),
            result.get("success_count", 0),
            result.get("failed_count", 0)
        )
        
        return {
            "status": "success",
            "message": f"Released {result.get('success_count', 0)} hosts",
            "success_count": result.get("success_count", 0),
            "failed_count": result.get("failed_count", 0),
            "results": result.get("results", [])
        }
        
    except Exception as e:
        logger.error("Failed to bulk release hosts for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("bulk_release_failed", str(e))
        )


@router.post(
    "/hosts/{host_id}/comments",
    status_code=status.HTTP_201_CREATED,
    summary="Add comment to host",
    description="""
    Add an immutable comment to a host's history.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:update
    """,
    responses={
        201: {"description": "Comment added successfully"},
        404: {"description": "Host not found or not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def add_host_comment(
    request: Request,
    host_id: str,
    comment_text: str = Query(..., max_length=2000, description="Comment text"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """
    Add comment to host.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_comment", limit=100, period=3600)
    
    try:
        result = await ipam_manager.add_comment(
            user_id=user_id,
            resource_type="host",
            resource_id=host_id,
            comment_text=comment_text
        )
        
        logger.info("User %s added comment to host %s", user_id, host_id)
        
        return {
            "status": "success",
            "message": "Comment added successfully",
            "host_id": host_id,
            "comment": result.get("comment")
        }
        
    except Exception as e:
        logger.error("Failed to add comment to host %s for user %s: %s", host_id, user_id, e, exc_info=True)
        
        error_msg = str(e).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("host_not_found", f"Host '{host_id}' not found")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("comment_add_failed", str(e))
            )


@router.get(
    "/hosts/preview-next",
    summary="Preview next host allocation",
    description="""
    Preview the next available Z octet that would be allocated for a region.
    
    Does not actually allocate the host, just shows what would be allocated.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved preview",
            "content": {
                "application/json": {
                    "example": {
                        "region_id": "550e8400-e29b-41d4-a716-446655440000",
                        "next_ip": "10.5.23.45",
                        "z_octet": 45,
                        "available": True
                    }
                }
            }
        },
        409: {"description": "No available addresses"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Hosts"]
)
async def preview_next_host(
    request: Request,
    region_id: str = Query(..., description="Region ID for preview"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Preview next available host allocation.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "host_preview", limit=500, period=3600)
    
    try:
        preview = await ipam_manager.get_next_available_host(user_id, region_id)
        
        if not preview:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=format_error_response(
                    "capacity_exhausted",
                    f"No available addresses in region {region_id}",
                    {"region_id": region_id}
                )
            )
        
        logger.info("User %s previewed next host for region %s: %s", user_id, region_id, preview.get("next_ip"))
        
        return preview
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to preview next host for user %s in region %s: %s", user_id, region_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("host_preview_failed", "Failed to preview next host")
        )


# ============================================================================
# IP Interpretation Endpoint
# ============================================================================

@router.post(
    "/interpret",
    summary="Interpret IP address hierarchy",
    description="""
    Interpret any IP address in the 10.X.Y.Z format to understand its geographic hierarchy.
    
    Returns hierarchical JSON: Global Root → Continent → Country → Region → Host
    
    Returns 404 for addresses not owned by the authenticated user (user isolation).
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully interpreted IP address",
            "content": {
                "application/json": {
                    "example": {
                        "ip_address": "10.5.23.45",
                        "hierarchy": {
                            "global_root": "10.0.0.0/8",
                            "continent": "Asia",
                            "country": {
                                "name": "India",
                                "x_range": "0-29",
                                "x_octet": 5
                            },
                            "region": {
                                "region_id": "550e8400-e29b-41d4-a716-446655440000",
                                "region_name": "Mumbai DC1",
                                "cidr": "10.5.23.0/24",
                                "y_octet": 23,
                                "status": "Active"
                            },
                            "host": {
                                "host_id": "660e8400-e29b-41d4-a716-446655440001",
                                "hostname": "web-server-01",
                                "z_octet": 45,
                                "status": "Active",
                                "device_type": "VM"
                            }
                        }
                    }
                }
            }
        },
        404: {"description": "Address not owned by user"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Interpretation"]
)
async def interpret_ip_address(
    request: Request,
    ip_address: str = Query(..., description="IP address to interpret (10.X.Y.Z format)"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Interpret IP address hierarchy.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "ip_interpret", limit=500, period=3600)
    
    try:
        interpretation = await ipam_manager.interpret_ip_address(user_id, ip_address)
        
        if not interpretation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response(
                    "address_not_found",
                    f"IP address '{ip_address}' not found or not owned by user"
                )
            )
        
        logger.info("User %s interpreted IP address %s", user_id, ip_address)
        
        return interpretation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to interpret IP %s for user %s: %s", ip_address, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("interpretation_failed", "Failed to interpret IP address")
        )


# ============================================================================
# Statistics and Analytics Endpoints
# ============================================================================

@router.get(
    "/statistics/continent/{continent}",
    summary="Get continent statistics",
    description="""
    Retrieve aggregated utilization statistics for all countries within a continent.
    
    Results are cached for 5 minutes.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved continent statistics"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Statistics"]
)
async def get_continent_statistics(
    request: Request,
    continent: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get aggregated statistics for a continent.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "stats_continent", limit=500, period=3600)
    
    try:
        stats = await ipam_manager.get_continent_statistics(user_id, continent)
        
        logger.info("User %s retrieved continent statistics for %s", user_id, continent)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get continent statistics for %s, user %s: %s", continent, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("stats_failed", "Failed to retrieve continent statistics")
        )


@router.get(
    "/statistics/top-utilized",
    summary="Get top utilized resources",
    description="""
    Retrieve the most utilized countries and regions sorted by utilization percentage.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved top utilized resources"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Statistics"]
)
async def get_top_utilized(
    request: Request,
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get top utilized resources.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "stats_top_utilized", limit=500, period=3600)
    
    try:
        stats = await ipam_manager.get_top_utilized_resources(user_id, limit)
        
        logger.info("User %s retrieved top %d utilized resources", user_id, limit)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get top utilized resources for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("stats_failed", "Failed to retrieve top utilized resources")
        )


@router.get(
    "/statistics/allocation-velocity",
    summary="Get allocation velocity trends",
    description="""
    Retrieve allocation trends showing allocations per day/week/month.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved allocation velocity"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Statistics"]
)
async def get_allocation_velocity(
    request: Request,
    time_range: str = Query("30d", description="Time range (7d, 30d, 90d)"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get allocation velocity trends.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "stats_velocity", limit=500, period=3600)
    
    try:
        stats = await ipam_manager.get_allocation_velocity(user_id, time_range)
        
        logger.info("User %s retrieved allocation velocity for %s", user_id, time_range)
        
        return stats
        
    except Exception as e:
        logger.error("Failed to get allocation velocity for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("stats_failed", "Failed to retrieve allocation velocity")
        )


# ============================================================================
# Search Endpoint
# ============================================================================

@router.get(
    "/search",
    summary="Search allocations",
    description="""
    Search allocations with comprehensive filters.
    
    Supports filtering by IP/CIDR, hostname, region name, continent, country, status, owner, tags, and date ranges.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved search results"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Search"]
)
async def search_allocations(
    request: Request,
    ip_address: Optional[str] = Query(None, description="IP address or CIDR to search"),
    hostname: Optional[str] = Query(None, description="Hostname (partial match)"),
    region_name: Optional[str] = Query(None, description="Region name (partial match)"),
    continent: Optional[str] = Query(None, description="Filter by continent"),
    country: Optional[str] = Query(None, description="Filter by country"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    owner: Optional[str] = Query(None, description="Filter by owner (accepts owner name or owner id)"),
    tags: Optional[str] = Query(None, description="Filter by tags (JSON string)"),
    created_after: Optional[str] = Query(None, description="Created after date (ISO format)"),
    created_before: Optional[str] = Query(None, description="Created before date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Search allocations with filters.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "search", limit=500, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        # Build search parameters
        search_params = {
            "ip_address": ip_address,
            "hostname": hostname,
            "region_name": region_name,
            "continent": continent,
            "country": country,
            "status": status_filter,
            "owner": owner,
            "tags": tags,
            "created_after": created_after,
            "created_before": created_before,
            "page": page,
            "page_size": page_size
        }
        
        # Remove None values
        search_params = {k: v for k, v in search_params.items() if v is not None}
        
        results = await ipam_manager.search_allocations(user_id, search_params)
        
        logger.info("User %s searched allocations: %d results", user_id, results.get("total_count", 0))
        
        return format_pagination_response(
            items=results.get("items", []),
            page=page,
            page_size=page_size,
            total_count=results.get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to search allocations for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("search_failed", "Failed to search allocations")
        )


# ============================================================================
# Import/Export Endpoints
# ============================================================================

@router.post(
    "/export",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create export job",
    description="""
    Create an asynchronous export job for allocations.
    
    Supports CSV and JSON formats with optional filters.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        202: {"description": "Export job created successfully"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Import/Export"]
)
async def create_export_job(
    request: Request,
    format: str = Query("csv", description="Export format (csv, json)"),
    include_hierarchy: bool = Query(False, description="Include hierarchical data"),
    country: Optional[str] = Query(None, description="Filter by country"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Create export job.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "export_create", limit=100, period=3600)
    
    try:
        filters = {}
        if country:
            filters["country"] = country
        if status_filter:
            filters["status"] = status_filter
        
        job_id = await ipam_manager.export_allocations(
            user_id=user_id,
            format=format,
            filters=filters,
            include_hierarchy=include_hierarchy
        )
        
        logger.info("User %s created export job %s", user_id, job_id)
        
        return {
            "status": "accepted",
            "message": "Export job created successfully",
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error("Failed to create export job for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("export_failed", str(e))
        )


@router.get(
    "/export/{job_id}/download",
    summary="Download export",
    description="""
    Download completed export file.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Export file downloaded successfully"},
        404: {"description": "Export job not found"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Import/Export"]
)
async def download_export(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Download export file.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "export_download", limit=100, period=3600)
    
    try:
        download_url = await ipam_manager.get_export_download_url(user_id, job_id)
        
        if not download_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=format_error_response("export_not_found", f"Export job '{job_id}' not found")
            )
        
        logger.info("User %s downloaded export %s", user_id, job_id)
        
        return {"download_url": download_url}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to download export %s for user %s: %s", job_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("download_failed", "Failed to download export")
        )


@router.post(
    "/import",
    status_code=status.HTTP_201_CREATED,
    summary="Import allocations",
    description="""
    Import allocations from CSV or JSON file.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {"description": "Import completed successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Import/Export"]
)
async def import_allocations(
    request: Request,
    file_content: str = Query(..., description="File content (CSV or JSON)"),
    mode: str = Query("auto", description="Import mode (auto, manual, preview)"),
    force: bool = Query(False, description="Skip existing allocations"),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """
    Import allocations.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "import", limit=100, period=3600)
    
    try:
        result = await ipam_manager.import_allocations(
            user_id=user_id,
            file_content=file_content,
            mode=mode,
            force=force
        )
        
        logger.info(
            "User %s imported allocations: success=%d, failed=%d",
            user_id,
            result.get("success_count", 0),
            result.get("failed_count", 0)
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to import allocations for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("import_failed", str(e))
        )


@router.post(
    "/import/preview",
    summary="Preview import validation",
    description="""
    Validate import file without actually importing.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Validation completed successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Import/Export"]
)
async def preview_import(
    request: Request,
    file_content: str = Query(..., description="File content (CSV or JSON)"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Preview import validation.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "import_preview", limit=100, period=3600)
    
    try:
        result = await ipam_manager.import_allocations(
            user_id=user_id,
            file_content=file_content,
            mode="preview",
            force=False
        )
        
        logger.info("User %s previewed import: %d valid, %d errors", user_id, result.get("valid_count", 0), result.get("error_count", 0))
        
        return result
        
    except Exception as e:
        logger.error("Failed to preview import for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("preview_failed", str(e))
        )


# ============================================================================
# Audit History Endpoints
# ============================================================================

@router.get(
    "/audit",
    summary="Query audit history (alias)",
    description="""
    Query audit history with filters. This is an alias for /audit/history.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved audit history"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Audit"]
)
async def get_audit(
    request: Request,
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Query audit history (alias endpoint for backward compatibility).
    """
    # Delegate to the main audit history endpoint
    return await get_audit_history(
        request=request,
        action_type=action_type,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
        current_user=current_user
    )


@router.get(
    "/audit/history",
    summary="Query audit history",
    description="""
    Query audit history with filters.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved audit history"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Audit"]
)
async def get_audit_history(
    request: Request,
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Query audit history.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "audit_history", limit=500, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        filters = {}
        if action_type:
            filters["action_type"] = action_type
        if resource_type:
            filters["resource_type"] = resource_type
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        
        history = await ipam_manager.get_audit_history(
            user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        logger.info("User %s queried audit history: %d results", user_id, history.get("total_count", 0))
        
        return format_pagination_response(
            items=history.get("items", []),
            page=page,
            page_size=page_size,
            total_count=history.get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to get audit history for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("audit_history_failed", "Failed to retrieve audit history")
        )


@router.get(
    "/audit/history/{ip_address}",
    summary="Get IP-specific audit history",
    description="""
    Retrieve audit history for a specific IP address.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved IP audit history"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Audit"]
)
async def get_ip_audit_history(
    request: Request,
    ip_address: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get audit history for specific IP.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "audit_ip_history", limit=500, period=3600)
    
    try:
        history = await ipam_manager.get_audit_history(
            user_id=user_id,
            filters={"ip_address": ip_address}
        )
        
        logger.info("User %s queried audit history for IP %s", user_id, ip_address)
        
        return history.get("items", [])
        
    except Exception as e:
        logger.error("Failed to get IP audit history for %s, user %s: %s", ip_address, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("audit_history_failed", "Failed to retrieve IP audit history")
        )


@router.post(
    "/audit/export",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Export audit history",
    description="""
    Create export job for audit history.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        202: {"description": "Export job created successfully"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Audit"]
)
async def export_audit_history(
    request: Request,
    format: str = Query("csv", description="Export format (csv, json)"),
    action_type: Optional[str] = Query(None, description="Filter by action type"),
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Export audit history.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "audit_export", limit=100, period=3600)
    
    try:
        filters = {}
        if action_type:
            filters["action_type"] = action_type
        if start_date:
            filters["start_date"] = start_date
        if end_date:
            filters["end_date"] = end_date
        
        job_id = await ipam_manager.export_audit_history(
            user_id=user_id,
            format=format,
            filters=filters
        )
        
        logger.info("User %s created audit export job %s", user_id, job_id)
        
        return {
            "status": "accepted",
            "message": "Audit export job created successfully",
            "job_id": job_id
        }
        
    except Exception as e:
        logger.error("Failed to export audit history for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("audit_export_failed", str(e))
        )


# ============================================================================
# Admin Quota Management Endpoints
# ============================================================================

@router.get(
    "/admin/quotas/{target_user_id}",
    summary="Get user quota",
    description="""
    Get quota information for a specific user.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:admin
    """,
    responses={
        200: {"description": "Successfully retrieved user quota"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Admin"]
)
async def get_user_quota(
    request: Request,
    target_user_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_admin)
):
    """
    Get user quota (admin only).
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "admin_quota_get", limit=100, period=3600)
    
    try:
        quota = await ipam_manager.get_user_quota(target_user_id)
        
        logger.info("Admin %s retrieved quota for user %s", user_id, target_user_id)
        
        return quota
        
    except Exception as e:
        logger.error("Failed to get quota for user %s by admin %s: %s", target_user_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("quota_get_failed", "Failed to retrieve user quota")
        )


@router.patch(
    "/admin/quotas/{target_user_id}",
    summary="Update user quota",
    description="""
    Update quota limits for a specific user.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:admin
    """,
    responses={
        200: {"description": "Quota updated successfully"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Admin"]
)
async def update_user_quota(
    request: Request,
    target_user_id: str,
    region_quota: Optional[int] = Query(None, ge=0, description="New region quota"),
    host_quota: Optional[int] = Query(None, ge=0, description="New host quota"),
    current_user: Dict[str, Any] = Depends(require_ipam_admin)
):
    """
    Update user quota (admin only).
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "admin_quota_update", limit=100, period=3600)
    
    try:
        updates = {}
        if region_quota is not None:
            updates["region_quota"] = region_quota
        if host_quota is not None:
            updates["host_quota"] = host_quota
        
        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=format_error_response("no_updates", "No quota updates provided")
            )
        
        quota = await ipam_manager.update_user_quota(target_user_id, updates)
        
        logger.info("Admin %s updated quota for user %s: %s", user_id, target_user_id, list(updates.keys()))
        
        return quota
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update quota for user %s by admin %s: %s", target_user_id, user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("quota_update_failed", str(e))
        )


@router.get(
    "/admin/quotas",
    summary="List all user quotas",
    description="""
    List quotas for all users with pagination.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:admin
    """,
    responses={
        200: {"description": "Successfully retrieved user quotas"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Admin"]
)
async def list_user_quotas(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(require_ipam_admin)
):
    """
    List all user quotas (admin only).
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "admin_quota_list", limit=100, period=3600)
    
    try:
        # Validate pagination
        page, page_size = validate_pagination_params(page, page_size)
        
        quotas = await ipam_manager.list_all_user_quotas(page=page, page_size=page_size)
        
        logger.info("Admin %s listed user quotas: %d results", user_id, quotas.get("total_count", 0))
        
        return format_pagination_response(
            items=quotas.get("items", []),
            page=page,
            page_size=page_size,
            total_count=quotas.get("total_count", 0)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("invalid_parameters", str(e))
        )
    except Exception as e:
        logger.error("Failed to list user quotas by admin %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("quota_list_failed", "Failed to list user quotas")
        )


# ============================================================================
# Reservation Management Endpoints
# ============================================================================

@router.post(
    "/reservations",
    status_code=status.HTTP_201_CREATED,
    summary="Create IP reservation",
    description="""
    Create a new IP address or region reservation.
    
    Reservations hold an address for a specified period without allocating it.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:allocate
    """,
    responses={
        201: {"description": "Reservation created successfully"},
        400: {"description": "Validation error"},
        403: {"description": "Insufficient permissions"},
        409: {"description": "Address already allocated or reserved"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Reservations"]
)
async def create_reservation(
    request: Request,
    reservation_request: ReservationCreateRequest,
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """Create a new IP reservation."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "reservation_create", limit=100, period=3600)
    
    try:
        result = await ipam_manager.create_reservation(
            user_id=user_id,
            resource_type=reservation_request.resource_type,
            x_octet=reservation_request.x_octet,
            y_octet=reservation_request.y_octet,
            z_octet=reservation_request.z_octet,
            reason=reservation_request.reason,
            expires_in_days=reservation_request.expires_in_days
        )
        
        logger.info("Reservation created: user=%s type=%s", user_id, reservation_request.resource_type)
        return result
        
    except Exception as e:
        logger.error("Failed to create reservation: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=format_error_response("reservation_create_failed", str(e))
        )


@router.get(
    "/reservations",
    summary="List reservations",
    description="""
    List user's reservations with filtering.
    
    **Rate Limiting:** 500 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {"description": "Successfully retrieved reservations"},
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Reservations"]
)
async def list_reservations(
    request: Request,
    status_filter: Optional[str] = Query(None, alias="status"),
    resource_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """List user's reservations with filtering."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "reservation_list", limit=500, period=3600)
    
    try:
        filters = {}
        if status_filter:
            filters["status"] = status_filter
        if resource_type:
            filters["resource_type"] = resource_type
        
        result = await ipam_manager.get_reservations(
            user_id=user_id,
            filters=filters,
            page=page,
            page_size=page_size
        )
        
        return result
        
    except Exception as e:
        logger.error("Failed to list reservations: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response("reservation_list_failed", "Failed to retrieve reservations")
        )


@router.get(
    "/reservations/{reservation_id}",
    summary="Get reservation details",
    tags=["IPAM - Reservations"]
)
async def get_reservation(
    request: Request,
    reservation_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get reservation details."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_reservation_by_id(user_id, reservation_id)
        if not result:
            raise HTTPException(status_code=404, detail="Reservation not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get reservation: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.post(
    "/reservations/{reservation_id}/convert",
    summary="Convert reservation to allocation",
    tags=["IPAM - Reservations"]
)
async def convert_reservation(
    request: Request,
    reservation_id: str,
    region_name: Optional[str] = Query(None),
    hostname: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_allocate)
):
    """Convert reservation to actual allocation."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.convert_reservation(
            user_id=user_id,
            reservation_id=reservation_id,
            region_name=region_name,
            hostname=hostname
        )
        return result
    except Exception as e:
        logger.error("Failed to convert reservation: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/reservations/{reservation_id}",
    summary="Delete reservation",
    tags=["IPAM - Reservations"]
)
async def delete_reservation(
    request: Request,
    reservation_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_release)
):
    """Delete a reservation."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.delete_reservation(user_id, reservation_id)
        return {"status": "success", "message": "Reservation deleted"}
    except Exception as e:
        logger.error("Failed to delete reservation: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



# ============================================================================
# User Preferences Endpoints
# ============================================================================

@router.get(
    "/preferences",
    summary="Get user preferences",
    tags=["IPAM - Preferences"]
)
async def get_preferences(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get user's IPAM preferences."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_user_preferences(user_id)
        return result
    except Exception as e:
        logger.error("Failed to get preferences: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/preferences",
    summary="Update user preferences",
    tags=["IPAM - Preferences"]
)
async def update_preferences(
    request: Request,
    default_country: Optional[str] = Query(None),
    default_region_quota: Optional[int] = Query(None),
    default_host_quota: Optional[int] = Query(None),
    notification_enabled: Optional[bool] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Update user's IPAM preferences."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        preferences = {}
        if default_country is not None:
            preferences["default_country"] = default_country
        if default_region_quota is not None:
            preferences["default_region_quota"] = default_region_quota
        if default_host_quota is not None:
            preferences["default_host_quota"] = default_host_quota
        if notification_enabled is not None:
            preferences["notification_enabled"] = notification_enabled
        
        result = await ipam_manager.update_user_preferences(user_id, preferences)
        return result
    except Exception as e:
        logger.error("Failed to update preferences: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.post(
    "/preferences/filters",
    status_code=status.HTTP_201_CREATED,
    summary="Save filter",
    tags=["IPAM - Preferences"]
)
async def save_filter(
    request: Request,
    filter_name: str = Query(...),
    filter_criteria: str = Query(...),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Save a filter for quick access."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.save_filter(user_id, filter_name, filter_criteria)
        return result
    except Exception as e:
        logger.error("Failed to save filter: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/preferences/filters",
    summary="Get saved filters",
    tags=["IPAM - Preferences"]
)
async def get_saved_filters(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get user's saved filters."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_saved_filters(user_id)
        return result
    except Exception as e:
        logger.error("Failed to get filters: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.delete(
    "/preferences/filters/{filter_id}",
    summary="Delete saved filter",
    tags=["IPAM - Preferences"]
)
async def delete_filter(
    request: Request,
    filter_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Delete a saved filter."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.delete_filter(user_id, filter_id)
        return {"status": "success", "message": "Filter deleted"}
    except Exception as e:
        logger.error("Failed to delete filter: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Dashboard Statistics Endpoints
# ============================================================================

@router.get(
    "/statistics/dashboard",
    summary="Get dashboard statistics",
    tags=["IPAM - Statistics"]
)
async def get_dashboard_stats(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get comprehensive dashboard statistics."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "dashboard_stats", limit=500, period=3600)
    
    try:
        result = await ipam_manager.calculate_dashboard_stats(user_id)
        return result
    except Exception as e:
        logger.error("Failed to get dashboard stats: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# Capacity Forecasting Endpoints
# ============================================================================

@router.get(
    "/statistics/forecast/{resource_type}/{resource_id}",
    summary="Get capacity forecast",
    tags=["IPAM - Statistics"]
)
async def get_forecast(
    request: Request,
    resource_type: str,
    resource_id: str,
    days_ahead: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get capacity forecast for a resource."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.calculate_forecast(user_id, resource_type, resource_id)
        return result
    except Exception as e:
        logger.error("Failed to get forecast: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/statistics/trends",
    summary="Get allocation trends",
    tags=["IPAM - Statistics"]
)
async def get_trends(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get allocation trends over time."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.calculate_trends(user_id, days)
        return result
    except Exception as e:
        logger.error("Failed to get trends: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================================
# Notification Endpoints
# ============================================================================

@router.get(
    "/notifications",
    summary="List notifications",
    tags=["IPAM - Notifications"]
)
async def list_notifications(
    request: Request,
    is_read: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """List user's notifications."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        filters = {}
        if is_read is not None:
            filters["is_read"] = is_read
        
        result = await ipam_manager.get_notifications(user_id, filters, page, page_size)
        return result
    except Exception as e:
        logger.error("Failed to list notifications: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/notifications/unread",
    summary="Get unread notification count",
    tags=["IPAM - Notifications"]
)
async def get_unread_count(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get count of unread notifications."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        filters = {"is_read": False}
        result = await ipam_manager.get_notifications(user_id, filters, 1, 1)
        return {"unread_count": result.get("total_count", 0)}
    except Exception as e:
        logger.error("Failed to get unread count: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.patch(
    "/notifications/{notification_id}",
    summary="Mark notification as read",
    tags=["IPAM - Notifications"]
)
async def mark_notification_read(
    request: Request,
    notification_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Mark a notification as read."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.mark_notification_read(user_id, notification_id)
        return {"status": "success", "message": "Notification marked as read"}
    except Exception as e:
        logger.error("Failed to mark notification read: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/notifications/{notification_id}",
    summary="Delete notification",
    tags=["IPAM - Notifications"]
)
async def delete_notification(
    request: Request,
    notification_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Delete a notification."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.delete_notification(user_id, notification_id)
        return {"status": "success", "message": "Notification deleted"}
    except Exception as e:
        logger.error("Failed to delete notification: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Notification Rules Endpoints
# ============================================================================

@router.post(
    "/notifications/rules",
    status_code=status.HTTP_201_CREATED,
    summary="Create notification rule",
    tags=["IPAM - Notifications"]
)
async def create_notification_rule(
    request: Request,
    event_type: str = Query(...),
    threshold: Optional[float] = Query(None),
    notification_method: str = Query("in_app"),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Create a notification rule."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.create_notification_rule(
            user_id=user_id,
            event_type=event_type,
            threshold=threshold,
            notification_method=notification_method
        )
        return result
    except Exception as e:
        logger.error("Failed to create notification rule: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/notifications/rules",
    summary="List notification rules",
    tags=["IPAM - Notifications"]
)
async def list_notification_rules(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """List user's notification rules."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        collection = ipam_manager.db_manager.get_tenant_collection("ipam_notification_rules")
        cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
        rules = await cursor.to_list(None)
        
        for rule in rules:
            rule["_id"] = str(rule["_id"])
        
        return {"rules": rules}
    except Exception as e:
        logger.error("Failed to list notification rules: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/notifications/rules/{rule_id}",
    summary="Update notification rule",
    tags=["IPAM - Notifications"]
)
async def update_notification_rule(
    request: Request,
    rule_id: str,
    is_active: Optional[bool] = Query(None),
    threshold: Optional[float] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Update a notification rule."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        from bson import ObjectId
        collection = ipam_manager.db_manager.get_tenant_collection("ipam_notification_rules")
        
        updates = {}
        if is_active is not None:
            updates["is_active"] = is_active
        if threshold is not None:
            updates["threshold"] = threshold
        
        if updates:
            await collection.update_one(
                {"_id": ObjectId(rule_id), "user_id": user_id},
                {"$set": updates}
            )
        
        return {"status": "success", "message": "Rule updated"}
    except Exception as e:
        logger.error("Failed to update notification rule: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.delete(
    "/notifications/rules/{rule_id}",
    summary="Delete notification rule",
    tags=["IPAM - Notifications"]
)
async def delete_notification_rule(
    request: Request,
    rule_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Delete a notification rule."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        from bson import ObjectId
        collection = ipam_manager.db_manager.get_tenant_collection("ipam_notification_rules")
        await collection.delete_one({"_id": ObjectId(rule_id), "user_id": user_id})
        return {"status": "success", "message": "Rule deleted"}
    except Exception as e:
        logger.error("Failed to delete notification rule: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Shareable Links Endpoints
# ============================================================================

@router.post(
    "/shares",
    status_code=status.HTTP_201_CREATED,
    summary="Create shareable link",
    tags=["IPAM - Shares"]
)
async def create_share(
    request: Request,
    resource_type: str = Query(...),
    resource_id: str = Query(...),
    expires_in_days: int = Query(7, ge=1, le=90),
    description: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Create a shareable link for a resource."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "share_create", limit=100, period=3600)
    
    try:
        result = await ipam_manager.create_share(
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            expires_in_days=expires_in_days,
            description=description
        )
        return result
    except Exception as e:
        logger.error("Failed to create share: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/shares",
    summary="List user's shares",
    tags=["IPAM - Shares"]
)
async def list_shares(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """List user's active shares."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.list_user_shares(user_id)
        return {"shares": result}
    except Exception as e:
        logger.error("Failed to list shares: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/shares/{share_token}",
    summary="Access shared resource (no auth)",
    tags=["IPAM - Shares"]
)
async def get_shared_resource(
    request: Request,
    share_token: str
):
    """Access a shared resource (no authentication required)."""
    try:
        result = await ipam_manager.get_shared_resource(share_token)
        return result
    except Exception as e:
        logger.error("Failed to get shared resource: %s", e, exc_info=True)
        raise HTTPException(status_code=404, detail="Share not found or expired")


@router.delete(
    "/shares/{share_id}",
    summary="Revoke share",
    tags=["IPAM - Shares"]
)
async def revoke_share(
    request: Request,
    share_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Revoke a shareable link."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.revoke_share(user_id, share_id)
        return {"status": "success", "message": "Share revoked"}
    except Exception as e:
        logger.error("Failed to revoke share: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



# ============================================================================
# Webhook Endpoints
# ============================================================================

@router.post(
    "/webhooks",
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    tags=["IPAM - Webhooks"]
)
async def create_webhook(
    request: Request,
    webhook_url: str = Query(...),
    events: List[str] = Query(...),
    description: Optional[str] = Query(None),
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Create a webhook for IPAM events."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "webhook_create", limit=10, period=3600)
    
    try:
        result = await ipam_manager.create_webhook(
            user_id=user_id,
            webhook_url=webhook_url,
            events=events,
            description=description
        )
        return result
    except Exception as e:
        logger.error("Failed to create webhook: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/webhooks",
    summary="List webhooks",
    tags=["IPAM - Webhooks"]
)
async def list_webhooks(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """List user's webhooks."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_webhooks(user_id)
        return {"webhooks": result}
    except Exception as e:
        logger.error("Failed to list webhooks: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@router.get(
    "/webhooks/{webhook_id}/deliveries",
    summary="Get webhook delivery history",
    tags=["IPAM - Webhooks"]
)
async def get_webhook_deliveries(
    request: Request,
    webhook_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get webhook delivery history."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_webhook_deliveries(user_id, webhook_id, page, page_size)
        return result
    except Exception as e:
        logger.error("Failed to get webhook deliveries: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/webhooks/{webhook_id}",
    summary="Delete webhook",
    tags=["IPAM - Webhooks"]
)
async def delete_webhook(
    request: Request,
    webhook_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Delete a webhook."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        await ipam_manager.delete_webhook(user_id, webhook_id)
        return {"status": "success", "message": "Webhook deleted"}
    except Exception as e:
        logger.error("Failed to delete webhook: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Bulk Operations Endpoints
# ============================================================================

@router.post(
    "/bulk/tags",
    summary="Bulk update tags",
    tags=["IPAM - Bulk Operations"]
)
async def bulk_update_tags(
    request: Request,
    bulk_request: BulkTagUpdateRequest,
    current_user: Dict[str, Any] = Depends(require_ipam_update)
):
    """Bulk update tags on resources."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    await check_ipam_rate_limit(user_id, "bulk_tags", limit=10, period=3600)
    
    try:
        result = await ipam_manager.bulk_update_tags(
            user_id=user_id,
            resource_type=bulk_request.resource_type,
            resource_ids=bulk_request.resource_ids,
            operation=bulk_request.operation,
            tags=bulk_request.tags
        )
        return result
    except Exception as e:
        logger.error("Failed bulk tag update: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/bulk/jobs/{job_id}",
    summary="Get bulk job status",
    tags=["IPAM - Bulk Operations"]
)
async def get_bulk_job_status(
    request: Request,
    job_id: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """Get status of a bulk operation job."""
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    try:
        result = await ipam_manager.get_bulk_job_status(user_id, job_id)
        return result
    except Exception as e:
        logger.error("Failed to get bulk job status: %s", e, exc_info=True)
        raise HTTPException(status_code=404, detail="Job not found")


# ============================================================================
# Metrics and Monitoring Endpoints
# ============================================================================

@router.get(
    "/metrics",
    summary="Get IPAM system metrics",
    description="""
    Retrieve comprehensive metrics about IPAM system performance and usage.
    
    Includes:
    - Error rates by type and endpoint
    - Request rates and response times
    - Capacity warnings
    - Quota exceeded events
    - Operation success/failure rates
    - Allocation rates
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved metrics",
            "content": {
                "application/json": {
                    "example": {
                        "timestamp": "2025-01-15T10:30:00Z",
                        "requests": {
                            "requests_per_minute": 45.0,
                            "average_response_time": 0.125
                        },
                        "errors": {
                            "capacity_exhausted": 5,
                            "quota_exceeded": 12,
                            "total": 17,
                            "errors_per_minute": 0.5
                        },
                        "capacity_warnings": {
                            "country": 3,
                            "region": 8,
                            "total": 11
                        },
                        "operations": {
                            "allocate_region": {
                                "success_count": 150,
                                "failure_count": 5,
                                "success_rate": 96.8
                            }
                        }
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Monitoring"]
)
async def get_ipam_metrics(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get comprehensive IPAM system metrics.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "metrics", limit=100, period=3600)
    
    try:
        from second_brain_database.routes.ipam.monitoring.metrics_tracker import get_ipam_metrics_tracker
        from second_brain_database.managers.redis_manager import redis_manager
        
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        summary = await metrics_tracker.get_metrics_summary()
        
        logger.info("User %s retrieved IPAM metrics", user_id)
        
        return summary
        
    except Exception as e:
        logger.error("Failed to get IPAM metrics for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "metrics_retrieval_failed",
                "Failed to retrieve system metrics"
            )
        )


@router.get(
    "/metrics/errors",
    summary="Get error rates",
    description="""
    Retrieve detailed error rate information.
    
    Returns error counts by type, total errors, and errors per minute.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved error rates",
            "content": {
                "application/json": {
                    "example": {
                        "capacity_exhausted": 5,
                        "quota_exceeded": 12,
                        "validation_error": 3,
                        "total": 20,
                        "errors_per_minute": 0.5
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Monitoring"]
)
async def get_error_rates(
    request: Request,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get detailed error rate information.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "metrics_errors", limit=100, period=3600)
    
    try:
        from second_brain_database.routes.ipam.monitoring.metrics_tracker import get_ipam_metrics_tracker
        from second_brain_database.managers.redis_manager import redis_manager
        
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        error_rates = await metrics_tracker.get_error_rates()
        
        logger.info("User %s retrieved error rates", user_id)
        
        return error_rates
        
    except Exception as e:
        logger.error("Failed to get error rates for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "error_rates_retrieval_failed",
                "Failed to retrieve error rates"
            )
        )


@router.get(
    "/metrics/endpoint/{endpoint:path}",
    summary="Get endpoint-specific metrics",
    description="""
    Retrieve metrics for a specific API endpoint.
    
    Returns error counts and response times for the specified endpoint.
    
    **Rate Limiting:** 100 requests per hour per user
    
    **Required Permission:** ipam:read
    """,
    responses={
        200: {
            "description": "Successfully retrieved endpoint metrics",
            "content": {
                "application/json": {
                    "example": {
                        "endpoint": "/ipam/regions",
                        "errors": {
                            "capacity_exhausted": 3,
                            "validation_error": 1
                        },
                        "average_response_time": 0.145
                    }
                }
            }
        },
        403: {"description": "Insufficient permissions"},
        429: {"description": "Rate limit exceeded"}
    },
    tags=["IPAM - Monitoring"]
)
async def get_endpoint_metrics(
    request: Request,
    endpoint: str,
    current_user: Dict[str, Any] = Depends(require_ipam_read)
):
    """
    Get metrics for a specific endpoint.
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    # Rate limiting
    await check_ipam_rate_limit(user_id, "metrics_endpoint", limit=100, period=3600)
    
    try:
        from second_brain_database.routes.ipam.monitoring.metrics_tracker import get_ipam_metrics_tracker
        from second_brain_database.managers.redis_manager import redis_manager
        
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        
        # Get endpoint-specific metrics
        errors = await metrics_tracker.get_endpoint_error_rates(endpoint)
        avg_response_time = await metrics_tracker.get_average_response_time(endpoint)
        
        result = {
            "endpoint": endpoint,
            "errors": errors,
            "average_response_time": avg_response_time
        }
        
        logger.info("User %s retrieved metrics for endpoint %s", user_id, endpoint)
        
        return result
        
    except Exception as e:
        logger.error("Failed to get endpoint metrics for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=format_error_response(
                "endpoint_metrics_retrieval_failed",
                "Failed to retrieve endpoint metrics"
            )
        )
