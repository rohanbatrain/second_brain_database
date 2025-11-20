"""
Consolidated Security Implementation for Family Management System

This module consolidates all security-related functionality to eliminate redundancies
and provide a unified approach to authentication, authorization, and rate limiting.

Key consolidations:
1. Unified rate limiting configuration and implementation
2. Consolidated security dependencies for family operations
3. Standardized error handling across security components
4. Optimized security event logging to reduce duplication
5. Centralized 2FA enforcement logic

Requirements addressed: 4.1-4.6 (Security Implementation Consolidation)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.dependencies import get_current_user_dep
from second_brain_database.utils.logging_utils import log_security_event

logger = get_logger(prefix="[Consolidated Security]")


class SecurityLevel(Enum):
    """Security levels for different operations"""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    FAMILY_MEMBER = "family_member"
    FAMILY_ADMIN = "family_admin"
    SENSITIVE = "sensitive"
    CRITICAL = "critical"


class OperationType(Enum):
    """Types of operations for rate limiting and security"""

    # Family operations
    FAMILY_CREATE = "family_create"
    FAMILY_INVITE = "family_invite"
    FAMILY_ADMIN_ACTION = "family_admin_action"
    FAMILY_MEMBER_ACTION = "family_member_action"

    # SBD operations
    SBD_READ = "sbd_read"
    SBD_TRANSACTION = "sbd_transaction"

    # Health and monitoring
    HEALTH_CHECK = "health_check"
    METRICS_READ = "metrics_read"
    ADMIN_HEALTH = "admin_health"

    # General operations
    DEFAULT = "default"


class RateLimitConfig(BaseModel):
    """Configuration for rate limiting"""

    requests: int
    period: int  # seconds
    operation_type: OperationType
    security_level: SecurityLevel


class SecurityValidationResult(BaseModel):
    """Result of security validation"""

    user_id: str
    is_authenticated: bool
    is_family_admin: bool = False
    requires_2fa: bool = False
    security_level: SecurityLevel
    operation_type: OperationType
    validation_timestamp: str
    temp_token_used: bool = False


class ConsolidatedSecurityManager:
    """
    Consolidated security manager that unifies all security operations
    """

    def __init__(self):
        self.logger = logger
        self._rate_limit_configs = self._initialize_rate_limit_configs()
        self._sensitive_operations = self._initialize_sensitive_operations()

    def _initialize_rate_limit_configs(self) -> Dict[OperationType, RateLimitConfig]:
        """Initialize consolidated rate limiting configurations"""
        return {
            # Family operations
            OperationType.FAMILY_CREATE: RateLimitConfig(
                requests=settings.FAMILY_CREATE_RATE_LIMIT,
                period=3600,
                operation_type=OperationType.FAMILY_CREATE,
                security_level=SecurityLevel.SENSITIVE,
            ),
            OperationType.FAMILY_INVITE: RateLimitConfig(
                requests=settings.FAMILY_INVITE_RATE_LIMIT,
                period=3600,
                operation_type=OperationType.FAMILY_INVITE,
                security_level=SecurityLevel.FAMILY_ADMIN,
            ),
            OperationType.FAMILY_ADMIN_ACTION: RateLimitConfig(
                requests=settings.FAMILY_ADMIN_ACTION_RATE_LIMIT,
                period=3600,
                operation_type=OperationType.FAMILY_ADMIN_ACTION,
                security_level=SecurityLevel.CRITICAL,
            ),
            OperationType.FAMILY_MEMBER_ACTION: RateLimitConfig(
                requests=settings.FAMILY_MEMBER_ACTION_RATE_LIMIT,
                period=3600,
                operation_type=OperationType.FAMILY_MEMBER_ACTION,
                security_level=SecurityLevel.FAMILY_MEMBER,
            ),
            # SBD operations
            OperationType.SBD_READ: RateLimitConfig(
                requests=10,
                period=60,
                operation_type=OperationType.SBD_READ,
                security_level=SecurityLevel.AUTHENTICATED,
            ),
            OperationType.SBD_TRANSACTION: RateLimitConfig(
                requests=10,
                period=60,
                operation_type=OperationType.SBD_TRANSACTION,
                security_level=SecurityLevel.SENSITIVE,
            ),
            # Health and monitoring
            OperationType.HEALTH_CHECK: RateLimitConfig(
                requests=10,
                period=3600,
                operation_type=OperationType.HEALTH_CHECK,
                security_level=SecurityLevel.AUTHENTICATED,
            ),
            OperationType.METRICS_READ: RateLimitConfig(
                requests=5,
                period=3600,
                operation_type=OperationType.METRICS_READ,
                security_level=SecurityLevel.AUTHENTICATED,
            ),
            OperationType.ADMIN_HEALTH: RateLimitConfig(
                requests=5,
                period=3600,
                operation_type=OperationType.ADMIN_HEALTH,
                security_level=SecurityLevel.FAMILY_ADMIN,
            ),
            # Default
            OperationType.DEFAULT: RateLimitConfig(
                requests=settings.FAMILY_MEMBER_ACTION_RATE_LIMIT,
                period=3600,
                operation_type=OperationType.DEFAULT,
                security_level=SecurityLevel.AUTHENTICATED,
            ),
        }

    def _initialize_sensitive_operations(self) -> Dict[OperationType, bool]:
        """Initialize operations that require 2FA"""
        return {
            OperationType.FAMILY_CREATE: True,
            OperationType.FAMILY_INVITE: True,
            OperationType.FAMILY_ADMIN_ACTION: True,
            OperationType.SBD_TRANSACTION: True,
            OperationType.FAMILY_MEMBER_ACTION: False,
            OperationType.SBD_READ: False,
            OperationType.HEALTH_CHECK: False,
            OperationType.METRICS_READ: False,
            OperationType.ADMIN_HEALTH: False,
            OperationType.DEFAULT: False,
        }

    async def validate_comprehensive_security(
        self,
        request: Request,
        operation_type: OperationType,
        current_user: Dict[str, Any],
        family_id: Optional[str] = None,
        require_admin: bool = False,
        x_temp_token: Optional[str] = None,
    ) -> SecurityValidationResult:
        """
        Comprehensive security validation that consolidates all security checks

        Args:
            request: FastAPI request object
            operation_type: Type of operation being performed
            current_user: Authenticated user
            family_id: Optional family ID for admin validation
            require_admin: Whether admin privileges are required
            x_temp_token: Optional temporary access token

        Returns:
            SecurityValidationResult with validation details

        Raises:
            HTTPException: If any security validation fails
        """
        user_id = str(current_user.get("_id", current_user.get("username", "")))

        try:
            # Get rate limit configuration for this operation
            rate_config = self._rate_limit_configs.get(operation_type, self._rate_limit_configs[OperationType.DEFAULT])

            # Apply existing security manager validations
            await security_manager.check_ip_lockdown(request, current_user)
            await security_manager.check_user_agent_lockdown(request, current_user)

            # Apply consolidated rate limiting
            await self._apply_consolidated_rate_limiting(request, operation_type, user_id, rate_config)

            # Validate admin permissions if required
            is_family_admin = False
            if require_admin and family_id:
                is_family_admin = await self._validate_family_admin(family_id, user_id)

            # Determine 2FA requirements
            requires_2fa = self._requires_2fa(operation_type, request, current_user)

            # Create validation result
            result = SecurityValidationResult(
                user_id=user_id,
                is_authenticated=True,
                is_family_admin=is_family_admin,
                requires_2fa=requires_2fa,
                security_level=rate_config.security_level,
                operation_type=operation_type,
                validation_timestamp=datetime.now().isoformat(),
                temp_token_used=bool(x_temp_token),
            )

            # Log consolidated security event
            await self._log_consolidated_security_event(request, result, success=True)

            return result

        except HTTPException:
            # Log security failure
            await self._log_consolidated_security_event(
                request,
                SecurityValidationResult(
                    user_id=user_id,
                    is_authenticated=True,
                    security_level=SecurityLevel.AUTHENTICATED,
                    operation_type=operation_type,
                    validation_timestamp=datetime.now().isoformat(),
                ),
                success=False,
            )
            raise
        except Exception as e:
            self.logger.error(
                "Unexpected error in consolidated security validation for user %s: %s", user_id, str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Security validation failed due to internal error",
            )

    async def _apply_consolidated_rate_limiting(
        self, request: Request, operation_type: OperationType, user_id: str, rate_config: RateLimitConfig
    ) -> None:
        """Apply consolidated rate limiting with operation-specific configuration"""
        action_key = f"{operation_type.value}_{user_id}"

        await security_manager.check_rate_limit(
            request=request,
            action=action_key,
            rate_limit_requests=rate_config.requests,
            rate_limit_period=rate_config.period,
        )

    async def _validate_family_admin(self, family_id: str, user_id: str) -> bool:
        """Validate family admin permissions"""
        from second_brain_database.managers.family_manager import family_manager

        try:
            is_admin = await family_manager.validate_admin_permissions(family_id, user_id)

            if not is_admin:
                self.logger.warning("Family admin access denied for user %s on family %s", user_id, family_id)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required for this family operation"
                )

            return True

        except HTTPException:
            raise
        except Exception as e:
            self.logger.error(
                "Error validating family admin permissions for user %s: %s", user_id, str(e), exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to validate admin permissions"
            )

    def _requires_2fa(self, operation_type: OperationType, request: Request, current_user: Dict[str, Any]) -> bool:
        """Determine if operation requires 2FA"""
        # Check if operation is inherently sensitive
        if self._sensitive_operations.get(operation_type, False):
            return True

        # Check for large transfer operations (placeholder for future implementation)
        if operation_type == OperationType.SBD_TRANSACTION:
            # This would check request body for large amounts
            return False

        return False

    async def _log_consolidated_security_event(
        self, request: Request, result: SecurityValidationResult, success: bool, error: Optional[str] = None
    ) -> None:
        """Log consolidated security events to reduce duplication"""
        event_type = f"consolidated_security_{result.operation_type.value}"

        details = {
            "operation_type": result.operation_type.value,
            "security_level": result.security_level.value,
            "requires_2fa": result.requires_2fa,
            "is_family_admin": result.is_family_admin,
            "temp_token_used": result.temp_token_used,
            "endpoint": f"{request.method} {request.url.path}",
            "user_agent": security_manager.get_client_user_agent(request),
        }

        if error:
            details["error"] = error

        log_security_event(
            event_type=event_type,
            user_id=result.user_id,
            ip_address=security_manager.get_client_ip(request),
            success=success,
            details=details,
        )

    def get_rate_limit_config(self, operation_type: OperationType) -> RateLimitConfig:
        """Get rate limit configuration for an operation type"""
        return self._rate_limit_configs.get(operation_type, self._rate_limit_configs[OperationType.DEFAULT])


# Global consolidated security manager instance
consolidated_security = ConsolidatedSecurityManager()


def create_consolidated_security_dependency(
    operation_type: OperationType, require_admin: bool = False, family_id_param: Optional[str] = None
):
    """
    Factory function to create consolidated security dependencies

    Args:
        operation_type: Type of operation for security validation
        require_admin: Whether admin privileges are required
        family_id_param: Parameter name for family ID (if applicable)

    Returns:
        FastAPI dependency function
    """

    async def consolidated_security_dependency(
        request: Request,
        x_temp_token: Optional[str] = Header(None, alias="X-Temp-Access-Token"),
        current_user: Dict[str, Any] = Depends(get_current_user_dep),
    ) -> SecurityValidationResult:
        """Generated consolidated security dependency"""

        # Extract family_id from path parameters if needed
        family_id = None
        if family_id_param and hasattr(request, "path_params"):
            family_id = request.path_params.get(family_id_param)

        return await consolidated_security.validate_comprehensive_security(
            request=request,
            operation_type=operation_type,
            current_user=current_user,
            family_id=family_id,
            require_admin=require_admin,
            x_temp_token=x_temp_token,
        )

    return consolidated_security_dependency


# Pre-configured consolidated dependencies for common operations
family_create_security_consolidated = create_consolidated_security_dependency(
    operation_type=OperationType.FAMILY_CREATE, require_admin=False
)

family_admin_security_consolidated = create_consolidated_security_dependency(
    operation_type=OperationType.FAMILY_ADMIN_ACTION, require_admin=True, family_id_param="family_id"
)

family_member_security_consolidated = create_consolidated_security_dependency(
    operation_type=OperationType.FAMILY_MEMBER_ACTION, require_admin=False
)

sbd_read_security_consolidated = create_consolidated_security_dependency(
    operation_type=OperationType.SBD_READ, require_admin=False
)

sbd_transaction_security_consolidated = create_consolidated_security_dependency(
    operation_type=OperationType.SBD_TRANSACTION, require_admin=False
)

health_check_security_consolidated = create_consolidated_security_dependency(
    operation_type=OperationType.HEALTH_CHECK, require_admin=False
)

admin_health_security_consolidated = create_consolidated_security_dependency(
    operation_type=OperationType.ADMIN_HEALTH, require_admin=True
)
