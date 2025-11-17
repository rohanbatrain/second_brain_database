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
    # Validate utilization_percentage
    utilization_percentage = region_data.get("utilization_percentage", 0.0)
    if utilization_percentage is None or not isinstance(utilization_percentage, (int, float)):
        utilization_percentage = 0.0
    else:
        import math
        if math.isnan(utilization_percentage) or math.isinf(utilization_percentage):
            utilization_percentage = 0.0
        elif not (0 <= utilization_percentage <= 100):
            utilization_percentage = max(0.0, min(100.0, utilization_percentage))
    
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
    # `owner` historically held a human-friendly name in newer code but
    # older clients sometimes expect an id. Provide both fields explicitly
    # so frontend can always use `owner_name` while `owner_id` remains
    # available for compatibility.
    "owner": region_data.get("owner"),
    "owner_name": region_data.get("owner"),
    "owner_id": region_data.get("owner_id"),
        "status": region_data.get("status"),
        "utilization_percentage": round(utilization_percentage, 2),
        "allocated_hosts": region_data.get("allocated_hosts", 0),
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
    # Provide owner_name and owner_id explicitly. Keep `owner` as the
    # human-friendly owner name for backwards compatibility with UI code
    # that expects a single `owner` field.
    "owner": host_data.get("owner"),
    "owner_name": host_data.get("owner"),
    "owner_id": host_data.get("owner_id"),
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
    # Calculate capacity (each X block has 256 Y values = 256 possible regions)
    total_blocks = country_data.get("total_blocks", 0)
    total_capacity = total_blocks * 256  # X blocks * Y values (regions per block)
    
    # Get utilization data with validation
    allocated_regions = country_data.get("allocated_regions", 0)
    remaining_capacity = country_data.get("remaining_capacity", total_capacity)
    utilization_percent = country_data.get("utilization_percent", 0.0)
    utilization_percentage = country_data.get("utilization_percentage", 0.0)
    
    # Ensure utilization_percentage is a valid number (not None, NaN, or Infinity)
    if utilization_percentage is None or not isinstance(utilization_percentage, (int, float)):
        utilization_percentage = 0.0
    else:
        # Check for NaN or Infinity
        import math
        if math.isnan(utilization_percentage) or math.isinf(utilization_percentage):
            utilization_percentage = 0.0
        elif not (0 <= utilization_percentage <= 100):
            # Clamp to valid range
            utilization_percentage = max(0.0, min(100.0, utilization_percentage))
    
    # Also validate utilization_percent for backward compatibility
    if utilization_percent is None or not isinstance(utilization_percent, (int, float)):
        utilization_percent = 0.0
    else:
        import math
        if math.isnan(utilization_percent) or math.isinf(utilization_percent):
            utilization_percent = 0.0
        elif not (0 <= utilization_percent <= 100):
            utilization_percent = max(0.0, min(100.0, utilization_percent))
    
    return {
        "continent": country_data.get("continent"),
        "country": country_data.get("country"),
        "x_start": country_data.get("x_start"),
        "x_end": country_data.get("x_end"),
        "total_blocks": total_blocks,
        "is_reserved": country_data.get("is_reserved", False),
        # Additional fields for frontend (matching expected field names)
        "total_capacity": total_capacity,
        "allocated_regions": allocated_regions,
        "utilization_percentage": round(utilization_percentage, 2),
        "utilization_percent": round(utilization_percent, 2),
        "remaining_capacity": remaining_capacity,
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
        "results": items,
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
