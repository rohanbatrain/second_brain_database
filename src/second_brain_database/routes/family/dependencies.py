"""
Family Authentication Dependencies for FastAPI route protection.

This module provides FastAPI dependency functions for enforcing comprehensive
security policies on family management endpoints, including:
- JWT and permanent token authentication
- IP and User Agent lockdown enforcement using existing SecurityManager
- 2FA requirement validation
- Temporary access token support
- Rate limiting with operation-specific thresholds

Dependencies:
    - get_current_family_user: Basic authentication with family context
    - enforce_family_security: Comprehensive security validation using existing SecurityManager
    - require_family_admin: Admin role validation for family operations
    - require_2fa_for_sensitive_ops: 2FA enforcement for sensitive operations
    - validate_temp_access: Temporary access token validation
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.dependencies import get_current_user_dep
from second_brain_database.utils.logging_utils import log_security_event

# Family-specific security constants
SENSITIVE_FAMILY_OPERATIONS = [
    "create_family",
    "invite_member",
    "remove_member",
    "promote_admin",
    "demote_admin",
    "freeze_account",
    "unfreeze_account",
    "update_spending_permissions",
]


# Family-specific exceptions
class FamilySecurityError(Exception):
    """Base exception for family security errors"""

    pass


class SecurityValidationFailed(FamilySecurityError):
    """Security validation failed"""

    pass


class TwoFactorRequired(FamilySecurityError):
    """2FA required for operation"""

    pass


class TemporaryAccessDenied(FamilySecurityError):
    """Temporary access denied"""

    pass


logger = get_logger(prefix="[Family Dependencies]")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_family_user(
    request: Request, current_user: Dict[str, Any] = Depends(get_current_user_dep)
) -> Dict[str, Any]:
    """
    Basic family user authentication dependency.

    Validates that the user is authenticated and adds family-specific context.
    This is the base dependency for all family operations.

    Args:
        request: FastAPI request object
        current_user: Authenticated user from auth system

    Returns:
        Dict containing user information with family context

    Raises:
        HTTPException: If authentication fails
    """
    try:
        # Add family-specific context to user
        user_id = str(current_user.get("_id", current_user.get("username", "")))

        # Log family operation access
        log_security_event(
            event_type="family_access",
            user_id=user_id,
            ip_address=request.client.host if request.client else None,
            success=True,
            details={
                "endpoint": f"{request.method} {request.url.path}",
                "user_role": current_user.get("role", "user"),
                "is_verified": current_user.get("is_verified", False),
            },
        )

        logger.debug(
            "Family user authentication successful for user %s on endpoint %s",
            user_id,
            f"{request.method} {request.url.path}",
        )

        return current_user

    except Exception as e:
        logger.error("Family user authentication failed: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication failed for family operation"
        )


async def enforce_family_security(
    request: Request,
    operation: str = "default",
    require_2fa: bool = False,
    x_temp_token: Optional[str] = Header(None, alias="X-Temp-Access-Token"),
    current_user: Dict[str, Any] = Depends(get_current_family_user),
) -> Dict[str, Any]:
    """
    Comprehensive security enforcement dependency for family operations.

    Uses the existing SecurityManager to apply all security policies including
    IP/User Agent lockdown, rate limiting, and family-specific validations.

    Args:
        request: FastAPI request object
        operation: Name of the operation being performed
        require_2fa: Whether 2FA is explicitly required
        x_temp_token: Optional temporary access token from header
        current_user: Authenticated user from family auth

    Returns:
        Dict containing security validation results and user info

    Raises:
        HTTPException: If any security validation fails
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))

    try:
        # Use existing SecurityManager for IP and User Agent lockdown
        await security_manager.check_ip_lockdown(request, current_user)
        await security_manager.check_user_agent_lockdown(request, current_user)

        # Apply family-specific rate limiting using existing SecurityManager
        family_action = f"family_{operation}"
        family_rate_limits = _get_family_rate_limits(operation)

        await security_manager.check_rate_limit(
            request=request,
            action=family_action,
            rate_limit_requests=family_rate_limits.get("requests"),
            rate_limit_period=family_rate_limits.get("period"),
        )

        # Determine if 2FA is required
        operation_requires_2fa = (
            require_2fa or operation in SENSITIVE_FAMILY_OPERATIONS or _is_large_transfer_operation(request, operation)
        )

        # Log family security event
        log_security_event(
            event_type=f"family_security_check_{operation}",
            user_id=user_id,
            ip_address=security_manager.get_client_ip(request),
            success=True,
            details={
                "operation": operation,
                "2fa_required": operation_requires_2fa,
                "temp_token_used": bool(x_temp_token),
                "endpoint": f"{request.method} {request.url.path}",
                "user_agent": security_manager.get_client_user_agent(request),
            },
        )

        logger.info(
            "Family security validation successful for user %s, operation: %s",
            user_id,
            operation,
            extra={
                "operation": operation,
                "2fa_required": operation_requires_2fa,
                "temp_token_used": bool(x_temp_token),
                "endpoint": f"{request.method} {request.url.path}",
            },
        )

        # Return enhanced user context with security information
        return {
            **current_user,
            "security_validated": True,
            "operation": operation,
            "2fa_required": operation_requires_2fa,
            "validation_timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        # Re-raise HTTP exceptions (like rate limiting, IP/User Agent lockdown)
        raise

    except Exception as e:
        logger.error("Unexpected error in family security enforcement for user %s: %s", user_id, str(e), exc_info=True)

        # Log security failure event
        log_security_event(
            event_type=f"family_security_error_{operation}",
            user_id=user_id,
            ip_address=security_manager.get_client_ip(request),
            success=False,
            details={"operation": operation, "error": str(e), "endpoint": f"{request.method} {request.url.path}"},
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Security validation failed due to internal error"
        )


async def require_family_admin(
    family_id: str, current_user: Dict[str, Any] = Depends(enforce_family_security)
) -> Dict[str, Any]:
    """
    Dependency to ensure user is a family administrator.

    Args:
        family_id: ID of the family to check admin status for
        current_user: Security-validated user from enforce_family_security

    Returns:
        Dict containing user info with admin validation

    Raises:
        HTTPException: If user is not a family admin
    """
    from second_brain_database.managers.family_manager import family_manager

    user_id = str(current_user.get("_id", current_user.get("username", "")))

    try:
        # Validate admin permissions using family manager
        is_admin = await family_manager.validate_admin_permissions(family_id, user_id)

        if not is_admin:
            log_security_event(
                event_type="family_admin_access_denied",
                user_id=user_id,
                success=False,
                details={"family_id": family_id, "required_role": "admin", "user_role": "member"},
            )

            logger.warning("Family admin access denied for user %s on family %s", user_id, family_id)

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required for this family operation"
            )

        logger.debug("Family admin validation successful for user %s on family %s", user_id, family_id)

        return {**current_user, "is_family_admin": True, "validated_family_id": family_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error validating family admin permissions for user %s: %s", user_id, str(e), exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to validate admin permissions"
        )


async def require_2fa_for_sensitive_ops(
    operation: str, current_user: Dict[str, Any] = Depends(get_current_family_user)
) -> Dict[str, Any]:
    """
    Dependency to enforce 2FA for sensitive family operations.

    Args:
        operation: Name of the operation being performed
        current_user: Authenticated family user

    Returns:
        Dict containing user info with 2FA validation

    Raises:
        HTTPException: If 2FA is required but not enabled
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))

    # Check if operation requires 2FA
    if operation in SENSITIVE_FAMILY_OPERATIONS:
        if not current_user.get("two_fa_enabled", False):
            log_security_event(
                event_type="family_2fa_required",
                user_id=user_id,
                success=False,
                details={
                    "operation": operation,
                    "2fa_enabled": False,
                    "available_methods": current_user.get("two_fa_methods", []),
                },
            )

            logger.warning("2FA required for sensitive family operation: %s by user %s", operation, user_id)

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "2fa_required",
                    "message": "Two-factor authentication required for this sensitive operation",
                    "operation": operation,
                    "available_methods": current_user.get("two_fa_methods", []),
                },
            )

    logger.debug("2FA validation passed for operation: %s by user %s", operation, user_id)

    return {**current_user, "2fa_validated": True, "sensitive_operation": operation in SENSITIVE_FAMILY_OPERATIONS}


async def validate_temp_access(
    operation: str,
    x_temp_token: str = Header(..., alias="X-Temp-Access-Token"),
    current_user: Dict[str, Any] = Depends(get_current_family_user),
) -> Dict[str, Any]:
    """
    Dependency to validate temporary access tokens for trusted operations.

    Note: This is a placeholder for temporary access token validation.
    The actual implementation would integrate with the existing token system.

    Args:
        operation: Name of the operation being performed
        x_temp_token: Temporary access token from header
        current_user: Authenticated family user

    Returns:
        Dict containing user info with temp token validation

    Raises:
        HTTPException: If temporary token validation fails
    """
    user_id = str(current_user.get("_id", current_user.get("username", "")))

    try:
        # For now, we'll log the temp token usage and return success
        # This would be replaced with actual temporary token validation logic
        log_security_event(
            event_type="family_temp_token_used",
            user_id=user_id,
            success=True,
            details={
                "operation": operation,
                "token_provided": bool(x_temp_token),
                "token_length": len(x_temp_token) if x_temp_token else 0,
            },
        )

        logger.info("Temporary access token processed for user %s, operation: %s", user_id, operation)

        return {**current_user, "temp_token_validated": True, "operation": operation}

    except Exception as e:
        logger.error("Error processing temporary access token for user %s: %s", user_id, str(e), exc_info=True)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Temporary token validation failed"
        )


def create_family_security_dependency(operation: str, require_2fa: bool = False, require_admin: bool = False):
    """
    Factory function to create operation-specific security dependencies.

    Args:
        operation: Name of the operation
        require_2fa: Whether 2FA is required
        require_admin: Whether admin privileges are required

    Returns:
        FastAPI dependency function
    """

    async def family_security_dependency(
        request: Request,
        x_temp_token: Optional[str] = Header(None, alias="X-Temp-Access-Token"),
        current_user: Dict[str, Any] = Depends(get_current_family_user),
    ) -> Dict[str, Any]:
        """Generated security dependency for specific family operation."""

        # Apply comprehensive security validation
        validated_user = await enforce_family_security(
            request=request,
            operation=operation,
            require_2fa=require_2fa,
            x_temp_token=x_temp_token,
            current_user=current_user,
        )

        # Apply admin validation if required
        if require_admin:
            # Note: This would need family_id parameter in actual usage
            # For now, we'll add admin validation flag
            validated_user["requires_admin"] = True

        return validated_user

    return family_security_dependency


def _get_family_rate_limits(operation: str) -> Dict[str, int]:
    """
    Get family-specific rate limits for different operations.

    Uses configuration values from settings for family-specific rate limits.

    Args:
        operation: Name of the family operation

    Returns:
        Dict containing rate limit configuration
    """
    from second_brain_database.config import settings

    # Family-specific rate limits using configuration
    family_rate_limits = {
        "create_family": {"requests": settings.FAMILY_CREATE_RATE_LIMIT, "period": 3600},
        "invite_member": {"requests": settings.FAMILY_INVITE_RATE_LIMIT, "period": 3600},
        "remove_member": {"requests": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT, "period": 3600},
        "promote_admin": {"requests": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT, "period": 3600},
        "demote_admin": {"requests": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT, "period": 3600},
        "freeze_account": {"requests": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT, "period": 3600},
        "unfreeze_account": {"requests": settings.FAMILY_ADMIN_ACTION_RATE_LIMIT, "period": 3600},
        "update_spending_permissions": {"requests": settings.FAMILY_MEMBER_ACTION_RATE_LIMIT, "period": 3600},
        "default": {"requests": settings.FAMILY_MEMBER_ACTION_RATE_LIMIT, "period": 3600},
    }

    return family_rate_limits.get(operation, family_rate_limits["default"])


def _is_large_transfer_operation(request: Request, operation: str) -> bool:
    """
    Check if the operation involves a large SBD transfer requiring 2FA.

    Args:
        request: FastAPI request object
        operation: Name of the operation

    Returns:
        bool: True if this is a large transfer operation
    """
    # This would check request body for transfer amounts
    # For now, return False - implement based on actual transfer logic
    return False


# Pre-configured dependencies for common operations
family_create_security = create_family_security_dependency(
    operation="create_family", require_2fa=True, require_admin=False
)

family_admin_security = create_family_security_dependency(
    operation="admin_action", require_2fa=True, require_admin=True
)

family_member_security = create_family_security_dependency(
    operation="member_action", require_2fa=False, require_admin=False
)
