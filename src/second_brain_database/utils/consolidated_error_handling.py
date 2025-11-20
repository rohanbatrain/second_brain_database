"""
Consolidated Error Handling for Family Management System

This module consolidates all error handling patterns to eliminate redundancies
and provide standardized error responses across security components.

Key consolidations:
1. Unified exception hierarchy for security errors
2. Standardized error response formatting
3. Consolidated error logging patterns
4. Optimized error monitoring and alerting
5. Centralized error recovery mechanisms

Requirements addressed: 4.1-4.6 (Security Implementation Consolidation)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from fastapi import HTTPException, status
from pydantic import BaseModel

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.logging_utils import log_security_event

logger = get_logger(prefix="[Consolidated Error Handling]")


class ErrorCategory(Enum):
    """Categories of errors for consolidated handling"""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    RATE_LIMITING = "rate_limiting"
    VALIDATION = "validation"
    SECURITY_POLICY = "security_policy"
    FAMILY_OPERATION = "family_operation"
    SBD_OPERATION = "sbd_operation"
    SYSTEM = "system"


class ErrorSeverity(Enum):
    """Severity levels for error handling and alerting"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConsolidatedErrorResponse(BaseModel):
    """Standardized error response format"""

    error: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    details: Optional[Dict[str, Any]] = None
    timestamp: str
    request_id: Optional[str] = None
    retry_after: Optional[int] = None


class ConsolidatedSecurityError(Exception):
    """Base exception for consolidated security errors"""

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        retry_after: Optional[int] = None,
    ):
        self.message = message
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(message)

    def to_response(self) -> ConsolidatedErrorResponse:
        """Convert exception to standardized response format"""
        return ConsolidatedErrorResponse(
            error=self.__class__.__name__.lower().replace("error", ""),
            message=self.message,
            category=self.category,
            severity=self.severity,
            details=self.details,
            timestamp=datetime.now().isoformat(),
            retry_after=self.retry_after,
        )


class AuthenticationError(ConsolidatedSecurityError):
    """Authentication-related errors"""

    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            status_code=status.HTTP_401_UNAUTHORIZED,
            **kwargs,
        )


class AuthorizationError(ConsolidatedSecurityError):
    """Authorization-related errors"""

    def __init__(self, message: str = "Access denied", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            status_code=status.HTTP_403_FORBIDDEN,
            **kwargs,
        )


class RateLimitError(ConsolidatedSecurityError):
    """Rate limiting errors"""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60, **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMITING,
            severity=ErrorSeverity.MEDIUM,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            retry_after=retry_after,
            **kwargs,
        )


class SecurityPolicyError(ConsolidatedSecurityError):
    """Security policy violations"""

    def __init__(self, message: str = "Security policy violation", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.SECURITY_POLICY,
            severity=ErrorSeverity.HIGH,
            status_code=status.HTTP_403_FORBIDDEN,
            **kwargs,
        )


class ValidationError(ConsolidatedSecurityError):
    """Input validation errors"""

    def __init__(self, message: str = "Validation failed", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            **kwargs,
        )


class FamilyOperationError(ConsolidatedSecurityError):
    """Family operation errors"""

    def __init__(self, message: str = "Family operation failed", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.FAMILY_OPERATION,
            severity=ErrorSeverity.MEDIUM,
            status_code=status.HTTP_400_BAD_REQUEST,
            **kwargs,
        )


class SBDOperationError(ConsolidatedSecurityError):
    """SBD operation errors"""

    def __init__(self, message: str = "SBD operation failed", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.SBD_OPERATION,
            severity=ErrorSeverity.MEDIUM,
            status_code=status.HTTP_400_BAD_REQUEST,
            **kwargs,
        )


class SystemError(ConsolidatedSecurityError):
    """System-level errors"""

    def __init__(self, message: str = "System error occurred", **kwargs):
        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            **kwargs,
        )


class ConsolidatedErrorHandler:
    """
    Consolidated error handler that standardizes error processing
    """

    def __init__(self):
        self.logger = logger
        self._error_counters = {}
        self._alert_thresholds = {
            ErrorSeverity.LOW: 100,
            ErrorSeverity.MEDIUM: 50,
            ErrorSeverity.HIGH: 20,
            ErrorSeverity.CRITICAL: 5,
        }

    async def handle_security_error(
        self,
        error: Union[ConsolidatedSecurityError, Exception],
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> HTTPException:
        """
        Handle security errors with consolidated logging and monitoring

        Args:
            error: The error to handle
            user_id: Optional user ID for context
            ip_address: Optional IP address for context
            endpoint: Optional endpoint for context
            additional_context: Optional additional context

        Returns:
            HTTPException with standardized format
        """
        # Convert to consolidated error if needed
        if isinstance(error, ConsolidatedSecurityError):
            consolidated_error = error
        else:
            consolidated_error = SystemError(message=str(error), details={"original_error": str(error)})

        # Log the error with consolidated format
        await self._log_consolidated_error(
            consolidated_error,
            user_id=user_id,
            ip_address=ip_address,
            endpoint=endpoint,
            additional_context=additional_context,
        )

        # Update error counters and check for alerting
        await self._update_error_counters(consolidated_error)

        # Create standardized HTTP exception
        error_response = consolidated_error.to_response()

        return HTTPException(
            status_code=consolidated_error.status_code,
            detail=error_response.dict(),
            headers={"Retry-After": str(consolidated_error.retry_after)} if consolidated_error.retry_after else None,
        )

    async def _log_consolidated_error(
        self,
        error: ConsolidatedSecurityError,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        endpoint: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log error with consolidated format to reduce duplication"""

        # Create consolidated log details
        log_details = {
            "error_category": error.category.value,
            "error_severity": error.severity.value,
            "error_message": error.message,
            "status_code": error.status_code,
            **error.details,
        }

        if endpoint:
            log_details["endpoint"] = endpoint

        if additional_context:
            log_details.update(additional_context)

        # Log security event
        log_security_event(
            event_type=f"consolidated_error_{error.category.value}",
            user_id=user_id,
            ip_address=ip_address,
            success=False,
            details=log_details,
        )

        # Log to application logger based on severity
        log_message = f"Consolidated security error: {error.message}"

        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, extra=log_details, exc_info=True)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, extra=log_details)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message, extra=log_details)
        else:
            self.logger.info(log_message, extra=log_details)

    async def _update_error_counters(self, error: ConsolidatedSecurityError) -> None:
        """Update error counters and trigger alerts if thresholds are exceeded"""
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        counter_key = f"{error.category.value}:{error.severity.value}:{current_hour}"

        # Update counter
        self._error_counters[counter_key] = self._error_counters.get(counter_key, 0) + 1

        # Check alert threshold
        threshold = self._alert_thresholds.get(error.severity, 50)
        if self._error_counters[counter_key] >= threshold:
            await self._trigger_error_alert(error, self._error_counters[counter_key])

    async def _trigger_error_alert(self, error: ConsolidatedSecurityError, count: int) -> None:
        """Trigger alert for high error rates"""
        alert_details = {
            "error_category": error.category.value,
            "error_severity": error.severity.value,
            "error_count": count,
            "time_window": "1 hour",
            "alert_type": "error_threshold_exceeded",
        }

        self.logger.critical(
            "Error threshold exceeded: %s errors of severity %s in the last hour",
            count,
            error.severity.value,
            extra=alert_details,
        )

        # Log alert event
        log_security_event(event_type="error_threshold_alert", success=False, details=alert_details)

    def create_user_friendly_message(self, error: ConsolidatedSecurityError) -> str:
        """Create user-friendly error messages"""
        user_friendly_messages = {
            ErrorCategory.AUTHENTICATION: "Please check your login credentials and try again.",
            ErrorCategory.AUTHORIZATION: "You don't have permission to perform this action.",
            ErrorCategory.RATE_LIMITING: f"Too many requests. Please wait {error.retry_after or 60} seconds and try again.",
            ErrorCategory.VALIDATION: "Please check your input and try again.",
            ErrorCategory.SECURITY_POLICY: "This action violates security policies.",
            ErrorCategory.FAMILY_OPERATION: "Family operation failed. Please try again or contact support.",
            ErrorCategory.SBD_OPERATION: "SBD operation failed. Please try again or contact support.",
            ErrorCategory.SYSTEM: "A system error occurred. Please try again later.",
        }

        return user_friendly_messages.get(error.category, error.message)

    def get_error_statistics(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")

        stats = {"current_hour": current_hour, "error_counts": {}, "total_errors": 0}

        for key, count in self._error_counters.items():
            if current_hour in key:
                category, severity, _ = key.split(":")
                if category not in stats["error_counts"]:
                    stats["error_counts"][category] = {}
                stats["error_counts"][category][severity] = count
                stats["total_errors"] += count

        return stats


# Global consolidated error handler instance
consolidated_error_handler = ConsolidatedErrorHandler()


def handle_consolidated_errors(func):
    """
    Decorator to handle errors with consolidated error handling
    """

    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ConsolidatedSecurityError as e:
            # Extract context from function arguments
            user_id = None
            ip_address = None
            endpoint = None

            # Try to extract context from common parameter names
            for arg in args:
                if hasattr(arg, "client") and hasattr(arg.client, "host"):
                    ip_address = arg.client.host
                if hasattr(arg, "method") and hasattr(arg, "url"):
                    endpoint = f"{arg.method} {arg.url.path}"

            for key, value in kwargs.items():
                if key == "current_user" and isinstance(value, dict):
                    user_id = str(value.get("_id", value.get("username", "")))

            raise await consolidated_error_handler.handle_security_error(
                error=e, user_id=user_id, ip_address=ip_address, endpoint=endpoint
            )
        except Exception as e:
            # Handle unexpected errors
            raise await consolidated_error_handler.handle_security_error(
                error=SystemError(message="An unexpected error occurred", details={"original_error": str(e)})
            )

    return wrapper
