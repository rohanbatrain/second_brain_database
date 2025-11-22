"""
FastAPI dependencies for security lockdown enforcement.

This module provides dependency functions for enforcing IP and User Agent lockdown
across all protected endpoints in the application.
"""

from typing import Any, Dict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.managers.workspace_manager import workspace_manager
from second_brain_database.routes.auth.services.auth.password import send_blocked_ip_notification
from second_brain_database.utils.logging_utils import log_security_event

logger = get_logger(prefix="[Security Dependencies]")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user_dep(token: str = Depends(oauth2_scheme)):
    """
    Dependency function to retrieve the current authenticated user, augmented with
    their workspace memberships, roles, and tenant context.
    
    This function also sets the tenant context for automatic tenant filtering in database operations.
    """
    from second_brain_database.routes.auth.services.auth.login import get_current_user
    from second_brain_database.middleware.tenant_context import set_tenant_context, get_current_tenant_id
    from jose import jwt
    from second_brain_database.config import settings

    # 1. Get the core user object
    user = await get_current_user(token)

    if user:
        # 2. Extract tenant information from JWT token
        try:
            secret_key = getattr(settings, "SECRET_KEY", None)
            if hasattr(secret_key, "get_secret_value"):
                secret_key = secret_key.get_secret_value()
            
            payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
            primary_tenant_id = payload.get("primary_tenant_id", settings.DEFAULT_TENANT_ID)
            tenant_memberships = payload.get("tenant_memberships", [])
            
            # Add tenant information to user object
            user["primary_tenant_id"] = primary_tenant_id
            user["tenant_memberships"] = tenant_memberships
            user["current_tenant_id"] = get_current_tenant_id() or primary_tenant_id
            
            # Set tenant context if not already set (e.g., by middleware)
            if not get_current_tenant_id():
                set_tenant_context(primary_tenant_id)
                logger.debug(f"Set tenant context to primary tenant: {primary_tenant_id}")
            
        except Exception as e:
            logger.warning(f"Failed to extract tenant info from JWT for user {user.get('_id')}: {e}")
            # Fallback to default tenant
            user["primary_tenant_id"] = settings.DEFAULT_TENANT_ID
            user["tenant_memberships"] = []
            user["current_tenant_id"] = settings.DEFAULT_TENANT_ID
            set_tenant_context(settings.DEFAULT_TENANT_ID)
        
        # 3. Augment the user object with their workspace data (tenant-scoped)
        try:
            user_id = str(user["_id"])
            user_workspaces = await workspace_manager.get_workspaces_for_user(user_id)
            user["workspaces"] = user_workspaces
            logger.debug(f"User {user_id} is a member of {len(user_workspaces)} workspaces.")
        except Exception as e:
            logger.error(f"Failed to retrieve workspaces for user {user.get('_id')}: {e}")
            # Decide if this should be a hard fail or not. For now, we'll allow login
            # but the user won't have workspace context.
            user["workspaces"] = []

    return user


async def enforce_ip_lockdown(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user_dep)
) -> Dict[str, Any]:
    """
    FastAPI dependency for IP lockdown enforcement.

    Checks if the user has IP lockdown enabled and validates the request IP
    against their trusted IP list. Sends email notifications for blocked attempts.

    Args:
        request (Request): The FastAPI request object
        current_user (Dict[str, Any]): The authenticated user document

    Returns:
        Dict[str, Any]: The user document if IP lockdown passes

    Raises:
        HTTPException: If IP lockdown blocks the request
    """
    try:
        # Check IP lockdown using the security manager
        await security_manager.check_ip_lockdown(request, current_user)

        # Log successful IP lockdown check
        request_ip = security_manager.get_client_ip(request)
        logger.debug("IP lockdown check passed for user %s from IP %s", current_user.get("username"), request_ip)

        return current_user

    except HTTPException as e:
        # IP lockdown blocked the request - log and send notification
        request_ip = security_manager.get_client_ip(request)
        user_id = current_user.get("username", current_user.get("_id", "unknown"))
        trusted_ips = current_user.get("trusted_ips", [])
        endpoint = f"{request.method} {request.url.path}"

        # Log comprehensive security event
        log_security_event(
            event_type="ip_lockdown_violation",
            user_id=user_id,
            ip_address=request_ip,
            success=False,
            details={
                "attempted_ip": request_ip,
                "trusted_ips": trusted_ips,
                "endpoint": endpoint,
                "method": request.method,
                "path": request.url.path,
                "user_agent": request.headers.get("user-agent", ""),
                "timestamp": request.headers.get("date", ""),
                "lockdown_enabled": current_user.get("trusted_ip_lockdown", False),
                "trusted_ip_count": len(trusted_ips),
            },
        )

        logger.warning(
            "IP lockdown violation: blocked request from IP %s for user %s on endpoint %s (trusted IPs: %s)",
            request_ip,
            user_id,
            endpoint,
            trusted_ips,
        )

        # Send email notification about blocked access attempt
        try:
            user_email = current_user.get("email")
            if user_email:
                await send_blocked_ip_notification(
                    email=user_email, attempted_ip=request_ip, trusted_ips=trusted_ips, endpoint=endpoint
                )
                logger.info("Sent blocked IP notification email to %s", user_email)
            else:
                logger.warning("Cannot send blocked IP notification: no email for user %s", user_id)
        except Exception as email_error:
            logger.error("Failed to send blocked IP notification email: %s", email_error, exc_info=True)

        # Re-raise the original HTTPException
        raise


async def enforce_user_agent_lockdown(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user_dep)
) -> Dict[str, Any]:
    """
    FastAPI dependency for User Agent lockdown enforcement.

    Checks if the user has User Agent lockdown enabled and validates the request
    User Agent against their trusted User Agent list.

    Args:
        request (Request): The FastAPI request object
        current_user (Dict[str, Any]): The authenticated user document

    Returns:
        Dict[str, Any]: The user document if User Agent lockdown passes

    Raises:
        HTTPException: If User Agent lockdown blocks the request
    """
    try:
        # Check User Agent lockdown using the security manager
        await security_manager.check_user_agent_lockdown(request, current_user)

        # Log successful User Agent lockdown check
        request_user_agent = security_manager.get_client_user_agent(request)
        logger.debug(
            "User Agent lockdown check passed for user %s with User Agent %s",
            current_user.get("username"),
            request_user_agent,
        )

        return current_user

    except HTTPException as e:
        # User Agent lockdown blocked the request - log and send notification
        request_ip = security_manager.get_client_ip(request)
        request_user_agent = security_manager.get_client_user_agent(request)
        user_id = current_user.get("username", current_user.get("_id", "unknown"))
        trusted_user_agents = current_user.get("trusted_user_agents", [])
        endpoint = f"{request.method} {request.url.path}"

        # Log comprehensive security event
        log_security_event(
            event_type="user_agent_lockdown_violation",
            user_id=user_id,
            ip_address=request_ip,
            success=False,
            details={
                "attempted_user_agent": request_user_agent,
                "trusted_user_agents": trusted_user_agents,
                "endpoint": endpoint,
                "method": request.method,
                "path": request.url.path,
                "timestamp": request.headers.get("date", ""),
                "lockdown_enabled": current_user.get("trusted_user_agent_lockdown", False),
                "trusted_user_agent_count": len(trusted_user_agents),
            },
        )

        logger.warning(
            "User Agent lockdown violation: blocked request with User Agent %s for user %s on endpoint %s (trusted User Agents: %s)",
            request_user_agent,
            user_id,
            endpoint,
            trusted_user_agents,
        )

        # Send email notification about blocked access attempt
        try:
            from second_brain_database.routes.auth.services.auth.password import send_blocked_user_agent_notification

            user_email = current_user.get("email")
            if user_email:
                await send_blocked_user_agent_notification(
                    email=user_email,
                    attempted_user_agent=request_user_agent,
                    trusted_user_agents=trusted_user_agents,
                    endpoint=endpoint,
                )
                logger.info("Sent blocked User Agent notification email to %s", user_email)
            else:
                logger.warning("Cannot send blocked User Agent notification: no email for user %s", user_id)
        except Exception as email_error:
            logger.error("Failed to send blocked User Agent notification email: %s", email_error, exc_info=True)

        # Re-raise the original HTTPException
        raise


async def enforce_all_lockdowns(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user_dep)
) -> Dict[str, Any]:
    """
    Combined dependency for both IP and User Agent lockdown enforcement.

    Applies both IP and User Agent lockdown checks in sequence. If either
    lockdown is enabled and blocks the request, appropriate logging and
    notifications are handled by the individual dependency functions.

    This function ensures consistent application of all lockdown policies
    across protected endpoints through FastAPI dependency injection.

    Args:
        request (Request): The FastAPI request object
        current_user (Dict[str, Any]): The authenticated user document

    Returns:
        Dict[str, Any]: The user document if all lockdown checks pass

    Raises:
        HTTPException: If any lockdown check blocks the request
    """
    user_id = current_user.get("username", current_user.get("_id", "unknown"))
    endpoint = f"{request.method} {request.url.path}"

    logger.debug("Starting combined lockdown checks for user %s on endpoint %s", user_id, endpoint)

    try:
        # First check IP lockdown - this will handle its own logging and notifications
        user = await enforce_ip_lockdown(request, current_user)

        # Then check User Agent lockdown - this will handle its own logging and notifications
        user = await enforce_user_agent_lockdown(request, user)

        logger.debug("All lockdown checks passed for user %s on endpoint %s", user_id, endpoint)
        return user

    except HTTPException as e:
        # Individual lockdown functions handle their own logging and notifications
        # We just need to log that the combined check failed and re-raise
        logger.info("Combined lockdown check failed for user %s on endpoint %s: %s", user_id, endpoint, e.detail)
        raise
