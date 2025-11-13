"""
IPAM route utility functions.

Helper functions for IPAM route handlers including response formatting,
error handling, and common operations.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAM Utils]")


def format_region_response(region_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format region data for API response.
    
    Args:
        region_data: Raw region data from manager
        
    Returns:
        Formatted region response
    """
    return {
        "region_id": str(region_data.get("_id", "")),
        "user_id": region_data.get("user_id"),
        "country": region_data.get("country"),
        "continent": region_data.get("continent"),
        "x_octet": region_data.get("x_octet"),
        "y_octet": region_data.get("y_octet"),
        "cidr": region_data.get("cidr"),
        "region_name": region_data.get("region_name"),
        "description": region_data.get("description"),
        "owner": region_data.get("owner"),
        "status": region_data.get("status"),
        "tags": region_data.get("tags", {}),
        "comments": region_data.get("comments", []),
        "created_at": region_data.get("created_at"),
        "updated_at": region_data.get("updated_at"),
        "created_by": region_data.get("created_by"),
        "updated_by": region_data.get("updated_by"),
    }


def format_host_response(host_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format host data for API response.
    
    Args:
        host_data: Raw host data from manager
        
    Returns:
        Formatted host response
    """
    return {
        "host_id": str(host_data.get("_id", "")),
        "user_id": host_data.get("user_id"),
        "region_id": str(host_data.get("region_id", "")),
        "x_octet": host_data.get("x_octet"),
        "y_octet": host_data.get("y_octet"),
        "z_octet": host_data.get("z_octet"),
        "ip_address": host_data.get("ip_address"),
        "hostname": host_data.get("hostname"),
        "device_type": host_data.get("device_type"),
        "os_type": host_data.get("os_type"),
        "application": host_data.get("application"),
        "cost_center": host_data.get("cost_center"),
        "owner": host_data.get("owner"),
        "purpose": host_data.get("purpose"),
        "status": host_data.get("status"),
        "tags": host_data.get("tags", {}),
        "notes": host_data.get("notes"),
        "comments": host_data.get("comments", []),
        "created_at": host_data.get("created_at"),
        "updated_at": host_data.get("updated_at"),
        "created_by": host_data.get("created_by"),
        "updated_by": host_data.get("updated_by"),
    }


def format_country_response(country_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format country mapping data for API response.
    
    Args:
        country_data: Raw country data from manager
        
    Returns:
        Formatted country response
    """
    return {
        "continent": country_data.get("continent"),
        "country": country_data.get("country"),
        "x_start": country_data.get("x_start"),
        "x_end": country_data.get("x_end"),
        "total_blocks": country_data.get("total_blocks"),
        "is_reserved": country_data.get("is_reserved", False),
    }


def format_utilization_response(utilization_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format utilization statistics for API response.
    
    Args:
        utilization_data: Raw utilization data from manager
        
    Returns:
        Formatted utilization response
    """
    return {
        "resource_type": utilization_data.get("resource_type"),
        "resource_id": utilization_data.get("resource_id"),
        "total_capacity": utilization_data.get("total_capacity"),
        "allocated": utilization_data.get("allocated"),
        "available": utilization_data.get("available"),
        "utilization_percent": utilization_data.get("utilization_percent"),
        "breakdown": utilization_data.get("breakdown", {}),
    }


def format_pagination_response(
    items: List[Dict[str, Any]],
    page: int,
    page_size: int,
    total_count: int
) -> Dict[str, Any]:
    """
    Format paginated response.
    
    Args:
        items: List of items for current page
        page: Current page number
        page_size: Items per page
        total_count: Total number of items
        
    Returns:
        Formatted pagination response
    """
    total_pages = (total_count + page_size - 1) // page_size
    
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }
    }


def format_error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Format error response.
    
    Args:
        error_code: Error code identifier
        message: Human-readable error message
        details: Optional additional error details
        
    Returns:
        Formatted error response
    """
    response = {
        "error": error_code,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if details:
        response["details"] = details
    
    return response


def validate_pagination_params(page: int, page_size: int, max_page_size: int = 100) -> tuple:
    """
    Validate and normalize pagination parameters.
    
    Args:
        page: Page number (1-indexed)
        page_size: Items per page
        max_page_size: Maximum allowed page size
        
    Returns:
        Tuple of (validated_page, validated_page_size)
        
    Raises:
        ValueError: If parameters are invalid
    """
    if page < 1:
        raise ValueError("Page number must be >= 1")
    
    if page_size < 1:
        raise ValueError("Page size must be >= 1")
    
    if page_size > max_page_size:
        logger.warning("Page size %d exceeds maximum %d, capping to maximum", page_size, max_page_size)
        page_size = max_page_size
    
    return page, page_size


def extract_client_info(request) -> Dict[str, Any]:
    """
    Extract client information from request.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Dict containing client IP and user agent
    """
    return {
        "ip_address": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
    }
