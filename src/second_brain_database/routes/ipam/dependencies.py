"""
IPAM Authentication and Authorization Dependencies.

This module provides FastAPI dependency functions for enforcing security policies
on IPAM endpoints, including:
- JWT authentication
- RBAC permission checks
- Rate limiting for IPAM operations
"""

from typing import Dict, Any

from fastapi import Depends, HTTPException, Request, status

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.dependencies import get_current_user_dep

logger = get_logger(prefix="[IPAM Dependencies]")

# IPAM-specific permissions
IPAM_PERMISSIONS = {
    "read": "ipam:read",
    "allocate": "ipam:allocate",
    "update": "ipam:update",
    "release": "ipam:release",
    "admin": "ipam:admin",
}


async def get_current_user_for_ipam(
    current_user: Dict[str, Any] = Depends(get_current_user_dep)
) -> Dict[str, Any]:
    """
    Get current authenticated user for IPAM operations.
    
    Reuses existing authentication dependency and adds IPAM-specific context.
    
    Args:
        current_user: Authenticated user from auth system
        
    Returns:
        Dict containing user information with IPAM context
        
    Raises:
        HTTPException: If authentication fails
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))
    
    logger.debug("IPAM user authentication successful for user %s", user_id)
    
    return current_user


async def require_ipam_permission(
    permission: str,
    user: Dict[str, Any] = Depends(get_current_user_for_ipam)
) -> Dict[str, Any]:
    """
    Validate user has required IPAM permission.
    
    Follows same pattern as family routes permission enforcement.
    
    Args:
        permission: Required permission (e.g., "ipam:read", "ipam:allocate")
        user: Authenticated user
        
    Returns:
        Dict containing user info if permission check passes
        
    Raises:
        HTTPException: If user lacks required permission
    """
    user_id = str(user.get("_id", user.get("username", "")))
    user_permissions = user.get("permissions", [])
    
    if permission not in user_permissions:
        logger.warning(
            "IPAM permission denied for user %s: required %s, has %s",
            user_id,
            permission,
            user_permissions
        )
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "insufficient_permissions",
                "required_permission": permission,
                "message": f"This operation requires {permission} permission"
            }
        )
    
    logger.debug("IPAM permission check passed for user %s: %s", user_id, permission)
    
    return user


async def check_ipam_rate_limit(
    user_id: str,
    operation: str,
    limit: int = 100,
    period: int = 3600
) -> None:
    """
    Check rate limit for IPAM operations using Redis.
    
    Follows existing rate limiting pattern from family routes.
    
    Args:
        user_id: User ID for rate limiting
        operation: Operation name (e.g., "region_create", "host_create")
        limit: Maximum requests allowed
        period: Time period in seconds
        
    Raises:
        HTTPException: If rate limit exceeded
    """
    redis = await redis_manager.get_redis()
    key = f"ipam:ratelimit:{user_id}:{operation}"
    
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, period)
        
        if current > limit:
            retry_after = await redis.ttl(key)
            
            logger.warning(
                "IPAM rate limit exceeded for user %s: operation %s, count %d/%d",
                user_id,
                operation,
                current,
                limit
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "limit": limit,
                    "period": period,
                    "retry_after": retry_after if retry_after > 0 else period,
                    "message": f"Rate limit exceeded. Try again in {retry_after if retry_after > 0 else period} seconds."
                }
            )
        
        logger.debug(
            "IPAM rate limit check passed for user %s: operation %s, count %d/%d",
            user_id,
            operation,
            current,
            limit
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error checking IPAM rate limit for user %s: %s", user_id, e, exc_info=True)
        # Don't block on rate limit errors, just log
        pass


# Pre-configured dependencies for common IPAM operations
async def require_ipam_read(user: Dict[str, Any] = Depends(get_current_user_for_ipam)) -> Dict[str, Any]:
    """Dependency requiring ipam:read permission."""
    return await require_ipam_permission(IPAM_PERMISSIONS["read"], user)


async def require_ipam_allocate(user: Dict[str, Any] = Depends(get_current_user_for_ipam)) -> Dict[str, Any]:
    """Dependency requiring ipam:allocate permission."""
    return await require_ipam_permission(IPAM_PERMISSIONS["allocate"], user)


async def require_ipam_update(user: Dict[str, Any] = Depends(get_current_user_for_ipam)) -> Dict[str, Any]:
    """Dependency requiring ipam:update permission."""
    return await require_ipam_permission(IPAM_PERMISSIONS["update"], user)


async def require_ipam_release(user: Dict[str, Any] = Depends(get_current_user_for_ipam)) -> Dict[str, Any]:
    """Dependency requiring ipam:release permission."""
    return await require_ipam_permission(IPAM_PERMISSIONS["release"], user)


async def require_ipam_admin(user: Dict[str, Any] = Depends(get_current_user_for_ipam)) -> Dict[str, Any]:
    """Dependency requiring ipam:admin permission."""
    return await require_ipam_permission(IPAM_PERMISSIONS["admin"], user)
