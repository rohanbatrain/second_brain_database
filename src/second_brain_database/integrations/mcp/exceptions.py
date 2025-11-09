"""
MCP Exception Hierarchy

MCP-specific exceptions that extend the existing error handling patterns.
Provides comprehensive error types for MCP operations with proper inheritance
from existing error classes and integration with error handling utilities.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ...utils.error_handling import (
    BulkheadCapacityError,
    CircuitBreakerOpenError,
    ErrorContext,
    GracefulDegradationError,
    RetryExhaustedError,
    ValidationError as BaseValidationError,
)


class MCPError(Exception):
    """
    Base exception for all MCP-related errors.

    Provides common functionality for MCP exceptions including error codes,
    user-friendly messages, and context information for debugging and auditing.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        """
        Initialize MCP error.

        Args:
            message: Technical error message for logging
            error_code: Unique error code for categorization
            context: Additional context information
            user_message: User-friendly error message
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.context = context or {}
        self.user_message = user_message or self._get_default_user_message()
        self.timestamp = datetime.now(timezone.utc)

    def _get_default_user_message(self) -> str:
        """Get default user-friendly message for this error type."""
        return "An error occurred while processing your MCP request. Please try again."

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging and API responses."""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of the error."""
        return f"{self.__class__.__name__}: {self.message}"


class MCPSecurityError(MCPError):
    """
    Base class for MCP security-related errors.

    Extends MCPError with security-specific functionality and context.
    Used as base for authentication, authorization, and validation errors.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
        security_event: bool = True,
    ):
        super().__init__(message, error_code, context, user_message)
        self.security_event = security_event

    def _get_default_user_message(self) -> str:
        """Get default user-friendly message for security errors."""
        return "Access denied. Please check your permissions and try again."


class MCPAuthenticationError(MCPSecurityError):
    """
    Authentication failure in MCP operations.

    Raised when user authentication fails or is missing for MCP tool access.
    Integrates with existing authentication patterns and audit logging.
    """

    def __init__(
        self,
        message: str = "Authentication required for MCP access",
        error_code: str = "MCP_AUTH_REQUIRED",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "Authentication is required to access this resource.",
        )


class MCPAuthorizationError(MCPSecurityError):
    """
    Authorization failure in MCP operations.

    Raised when user lacks required permissions for MCP tool access.
    Includes information about required permissions for debugging.
    """

    def __init__(
        self,
        message: str,
        required_permissions: Optional[list] = None,
        user_permissions: Optional[list] = None,
        error_code: str = "MCP_INSUFFICIENT_PERMISSIONS",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if required_permissions:
            context["required_permissions"] = required_permissions
        if user_permissions:
            context["user_permissions"] = user_permissions

        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "You don't have permission to perform this action.",
        )

        self.required_permissions = required_permissions or []
        self.user_permissions = user_permissions or []


class MCPValidationError(MCPSecurityError, BaseValidationError):
    """
    Input validation failure in MCP operations.

    Extends both MCPSecurityError and the existing ValidationError to maintain
    compatibility with existing validation patterns while adding MCP-specific context.
    """

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Optional[Any] = None,
        validation_rule: Optional[str] = None,
        error_code: str = "MCP_VALIDATION_ERROR",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if field_name:
            context["field_name"] = field_name
        if field_value is not None:
            context["field_value"] = str(field_value)  # Convert to string for safety
        if validation_rule:
            context["validation_rule"] = validation_rule

        MCPSecurityError.__init__(
            self,
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "The provided input is not valid. Please check your data and try again.",
            security_event=False,  # Validation errors are not security events
        )

        self.field_name = field_name
        self.field_value = field_value
        self.validation_rule = validation_rule


class MCPRateLimitError(MCPSecurityError):
    """
    Rate limit exceeded for MCP operations.

    Raised when user exceeds rate limits for MCP tool access.
    Includes information about limits and retry timing.
    """

    def __init__(
        self,
        message: str,
        rate_limit_key: Optional[str] = None,
        current_count: Optional[int] = None,
        limit: Optional[int] = None,
        reset_time: Optional[datetime] = None,
        error_code: str = "MCP_RATE_LIMIT_EXCEEDED",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if rate_limit_key:
            context["rate_limit_key"] = rate_limit_key
        if current_count is not None:
            context["current_count"] = current_count
        if limit is not None:
            context["limit"] = limit
        if reset_time:
            context["reset_time"] = reset_time.isoformat()

        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "You are making requests too quickly. Please wait a moment and try again.",
        )

        self.rate_limit_key = rate_limit_key
        self.current_count = current_count
        self.limit = limit
        self.reset_time = reset_time


class MCPToolError(MCPError):
    """
    MCP tool execution error.

    Raised when MCP tool execution fails due to business logic errors,
    external service failures, or other non-security related issues.
    """

    def __init__(
        self,
        message: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
        error_code: str = "MCP_TOOL_ERROR",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if tool_name:
            context["tool_name"] = tool_name
        if tool_args:
            context["tool_args"] = tool_args
        if original_error:
            context["original_error"] = str(original_error)
            context["original_error_type"] = type(original_error).__name__

        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "The requested operation could not be completed. Please try again.",
        )

        self.tool_name = tool_name
        self.tool_args = tool_args
        self.original_error = original_error


class MCPResourceError(MCPError):
    """
    MCP resource access error.

    Raised when MCP resource access fails due to missing resources,
    access restrictions, or resource generation errors.
    """

    def __init__(
        self,
        message: str,
        resource_uri: Optional[str] = None,
        resource_type: Optional[str] = None,
        error_code: str = "MCP_RESOURCE_ERROR",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if resource_uri:
            context["resource_uri"] = resource_uri
        if resource_type:
            context["resource_type"] = resource_type

        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message
            or "The requested resource could not be accessed. Please check the resource identifier.",
        )

        self.resource_uri = resource_uri
        self.resource_type = resource_type


class MCPPromptError(MCPError):
    """
    MCP prompt generation error.

    Raised when MCP prompt generation fails due to missing context,
    template errors, or prompt processing issues.
    """

    def __init__(
        self,
        message: str,
        prompt_name: Optional[str] = None,
        prompt_args: Optional[Dict[str, Any]] = None,
        error_code: str = "MCP_PROMPT_ERROR",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if prompt_name:
            context["prompt_name"] = prompt_name
        if prompt_args:
            context["prompt_args"] = prompt_args

        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "The requested prompt could not be generated. Please try again.",
        )

        self.prompt_name = prompt_name
        self.prompt_args = prompt_args


class MCPServerError(MCPError):
    """
    MCP server infrastructure error.

    Raised when MCP server encounters infrastructure issues like
    startup failures, configuration errors, or service unavailability.
    """

    def __init__(
        self,
        message: str,
        server_component: Optional[str] = None,
        error_code: str = "MCP_SERVER_ERROR",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if server_component:
            context["server_component"] = server_component

        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "The MCP server is temporarily unavailable. Please try again later.",
        )

        self.server_component = server_component


class MCPConfigurationError(MCPServerError):
    """
    MCP configuration error.

    Raised when MCP server configuration is invalid or missing.
    Used during server initialization and validation.
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[Any] = None,
        error_code: str = "MCP_CONFIG_ERROR",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if config_key:
            context["config_key"] = config_key
        if config_value is not None:
            context["config_value"] = str(config_value)

        super().__init__(
            message=message,
            server_component="configuration",
            error_code=error_code,
            context=context,
            user_message=user_message or "Server configuration error. Please contact support.",
        )

        self.config_key = config_key
        self.config_value = config_value


class MCPTimeoutError(MCPError):
    """
    MCP operation timeout error.

    Raised when MCP operations exceed configured timeout limits.
    Includes timeout duration and operation context.
    """

    def __init__(
        self,
        message: str,
        timeout_duration: Optional[float] = None,
        operation_type: Optional[str] = None,
        error_code: str = "MCP_TIMEOUT_ERROR",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if timeout_duration is not None:
            context["timeout_duration"] = timeout_duration
        if operation_type:
            context["operation_type"] = operation_type

        super().__init__(
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "The operation took too long to complete. Please try again.",
        )

        self.timeout_duration = timeout_duration
        self.operation_type = operation_type


# MCP-specific wrappers for existing error handling patterns
class MCPCircuitBreakerError(MCPError, CircuitBreakerOpenError):
    """
    MCP circuit breaker error.

    Wrapper for CircuitBreakerOpenError with MCP-specific context.
    Maintains compatibility with existing circuit breaker patterns.
    """

    def __init__(
        self,
        message: str,
        circuit_breaker_name: Optional[str] = None,
        error_code: str = "MCP_CIRCUIT_BREAKER_OPEN",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if circuit_breaker_name:
            context["circuit_breaker_name"] = circuit_breaker_name

        MCPError.__init__(
            self,
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "This service is temporarily unavailable. Please try again later.",
        )

        self.circuit_breaker_name = circuit_breaker_name


class MCPBulkheadError(MCPError, BulkheadCapacityError):
    """
    MCP bulkhead capacity error.

    Wrapper for BulkheadCapacityError with MCP-specific context.
    Maintains compatibility with existing bulkhead patterns.
    """

    def __init__(
        self,
        message: str,
        bulkhead_name: Optional[str] = None,
        error_code: str = "MCP_BULKHEAD_CAPACITY_EXCEEDED",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if bulkhead_name:
            context["bulkhead_name"] = bulkhead_name

        MCPError.__init__(
            self,
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message or "The system is currently at capacity. Please try again later.",
        )

        self.bulkhead_name = bulkhead_name


class MCPRetryExhaustedError(MCPError, RetryExhaustedError):
    """
    MCP retry exhausted error.

    Wrapper for RetryExhaustedError with MCP-specific context.
    Maintains compatibility with existing retry patterns.
    """

    def __init__(
        self,
        message: str,
        retry_attempts: Optional[int] = None,
        last_error: Optional[Exception] = None,
        error_code: str = "MCP_RETRY_EXHAUSTED",
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        context = context or {}
        if retry_attempts is not None:
            context["retry_attempts"] = retry_attempts
        if last_error:
            context["last_error"] = str(last_error)
            context["last_error_type"] = type(last_error).__name__

        MCPError.__init__(
            self,
            message=message,
            error_code=error_code,
            context=context,
            user_message=user_message
            or "The operation could not be completed after multiple attempts. Please try again later.",
        )

        self.retry_attempts = retry_attempts
        self.last_error = last_error


def create_mcp_error_context(
    operation: str,
    user_id: Optional[str] = None,
    tool_name: Optional[str] = None,
    request_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    **kwargs,
) -> ErrorContext:
    """
    Create error context for MCP operations.

    Convenience function to create ErrorContext instances with MCP-specific
    metadata for use with existing error handling decorators.

    Args:
        operation: MCP operation name
        user_id: User ID for the operation
        tool_name: MCP tool name being executed
        request_id: Request ID for tracking
        ip_address: Client IP address
        **kwargs: Additional metadata

    Returns:
        ErrorContext instance for MCP operations
    """
    metadata = kwargs.copy()
    if tool_name:
        metadata["mcp_tool"] = tool_name

    return ErrorContext(
        operation=operation, user_id=user_id, request_id=request_id, ip_address=ip_address, metadata=metadata
    )


def is_mcp_error(exception: Exception) -> bool:
    """
    Check if an exception is an MCP-related error.

    Args:
        exception: Exception to check

    Returns:
        True if the exception is MCP-related, False otherwise
    """
    return isinstance(exception, MCPError)


def get_mcp_error_code(exception: Exception) -> Optional[str]:
    """
    Get the MCP error code from an exception.

    Args:
        exception: Exception to extract error code from

    Returns:
        MCP error code if available, None otherwise
    """
    if isinstance(exception, MCPError):
        return exception.error_code
    return None


def get_mcp_user_message(exception: Exception) -> Optional[str]:
    """
    Get the user-friendly message from an MCP exception.

    Args:
        exception: Exception to extract user message from

    Returns:
        User-friendly message if available, None otherwise
    """
    if isinstance(exception, MCPError):
        return exception.user_message
    return None
