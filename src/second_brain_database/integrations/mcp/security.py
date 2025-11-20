"""
MCP Security Wrappers

Security decorators and utilities for MCP tools that integrate with
existing authentication and authorization patterns.
"""

import asyncio
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, Request

from ...config import settings
from ...managers.logging_manager import get_logger
from ...managers.security_manager import security_manager
from .context import (
    MCPRequestContext,
    MCPUserContext,
    clear_mcp_context,
    create_mcp_request_context,
    create_mcp_user_context_from_fastapi_user,
    extract_client_info_from_request,
    get_mcp_user_context,
    set_mcp_request_context,
    set_mcp_user_context,
)
from .exceptions import MCPAuthenticationError, MCPAuthorizationError, MCPRateLimitError

logger = get_logger(prefix="[MCP_Security]")


def secure_mcp_tool(
    permissions: Optional[List[str]] = None, rate_limit_action: Optional[str] = None, audit: bool = True
):
    """
    Security decorator for MCP tools using existing auth patterns.

    This decorator integrates with the existing authentication and authorization
    system to provide security controls for MCP tool access.

    Args:
        permissions: List of required permissions for tool access
        rate_limit_action: Rate limiting action key for SecurityManager
        audit: Whether to log tool execution for audit purposes

    Raises:
        MCPAuthenticationError: If user is not authenticated
        MCPAuthorizationError: If user lacks required permissions
        MCPRateLimitError: If rate limit is exceeded
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if authentication is required based on configuration
            auth_required = settings.MCP_SECURITY_ENABLED and settings.MCP_REQUIRE_AUTH

            # For STDIO transport or when auth is disabled, create a default context
            if not auth_required or settings.MCP_TRANSPORT == "stdio":
                # Create a default user context for development/STDIO mode
                try:
                    user_context = get_mcp_user_context()
                except MCPAuthenticationError:
                    # Create a default development user context
                    from .simple_auth import create_development_user_context

                    user_context = await create_development_user_context()
                    set_mcp_user_context(user_context)
            else:
                # Get user context from MCP security context (HTTP mode with auth)
                try:
                    user_context = get_mcp_user_context()
                except MCPAuthenticationError:
                    auth_error = MCPAuthenticationError("Authentication required for MCP tool access")
                    logger.warning("MCP tool access attempted without authentication: %s", func.__name__)
                    raise auth_error

            # Validate authentication if required
            if auth_required and (not user_context or not user_context.user_id):
                auth_error = MCPAuthenticationError("Authentication required for MCP tool access")
                logger.warning("MCP tool access attempted without authentication: %s", func.__name__)

                # Log authentication failure if we have partial context
                if user_context:
                    await log_mcp_authentication_event(user_context, success=False, error=auth_error)

                raise auth_error

            # Validate permissions if specified
            if permissions:
                if not await _validate_user_permissions(user_context.user_id, permissions):
                    authz_error = MCPAuthorizationError(f"Missing required permissions: {permissions}")
                    logger.warning(
                        "MCP tool access denied for user %s, missing permissions: %s", user_context.user_id, permissions
                    )

                    # Log authorization failure
                    await log_mcp_authorization_event(
                        user_context, permissions, success=False, error=authz_error, resource=func.__name__
                    )

                    raise authz_error

            # Apply rate limiting if specified
            if rate_limit_action and settings.MCP_RATE_LIMIT_ENABLED:
                await _apply_mcp_rate_limiting(user_context, rate_limit_action, func.__name__)

            # Log tool execution for audit if enabled
            if audit and settings.MCP_AUDIT_ENABLED:
                await _log_mcp_tool_execution(func.__name__, args, kwargs, user_context)

                # Also log authentication and authorization events
                await log_mcp_authentication_event(user_context, success=True)
                if permissions:
                    await log_mcp_authorization_event(user_context, permissions, success=True, resource=func.__name__)

            # Execute the tool function
            try:
                result = await func(*args, **kwargs)

                # Log successful execution
                if audit and settings.MCP_AUDIT_ENABLED:
                    logger.info("MCP tool executed successfully: %s by user %s", func.__name__, user_context.user_id)

                return result

            except Exception as e:
                # Log tool execution error
                logger.error(
                    "MCP tool execution failed: %s by user %s, error: %s", func.__name__, user_context.user_id, e
                )
                raise

        return wrapper

    return decorator


def authenticated_tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    permissions: Optional[List[str]] = None,
    rate_limit_action: Optional[str] = None,
    audit: bool = True,
    tags: Optional[List[str]] = None,
):
    """
    Combined FastMCP 2.x tool registration with security validation.

    This decorator combines FastMCP's @tool decorator with security validation,
    providing a convenient way to register secure MCP tools following FastMCP 2.x patterns.

    Args:
        name: Tool name for MCP registration
        description: Tool description for MCP registration
        permissions: Required permissions for tool access
        rate_limit_action: Rate limiting action key
        audit: Whether to enable audit logging
        tags: Tags for FastMCP 2.x component filtering
    """

    def decorator(func):
        # Apply security wrapper first
        secured_func = secure_mcp_tool(permissions=permissions, rate_limit_action=rate_limit_action, audit=audit)(func)

        # Determine tags for FastMCP 2.x
        tool_tags = set(tags or [])
        tool_tags.update({"secure", "production"})

        # Add function-specific tags
        func_name = func.__name__
        if "create" in func_name or "add" in func_name:
            tool_tags.add("write")
        elif "get" in func_name or "list" in func_name:
            tool_tags.add("read")
        elif "update" in func_name or "modify" in func_name:
            tool_tags.add("write")
        elif "delete" in func_name or "remove" in func_name:
            tool_tags.add("write")

        # Apply FastMCP 2.x @tool decorator (without tags - not supported in 2.x)
        try:
            from .modern_server import mcp

            mcp_tool_decorator = mcp.tool(name=name or func.__name__, description=description or func.__doc__ or "")
            secured_func = mcp_tool_decorator(secured_func)
        except ImportError:
            # Fallback if modern_server is not available
            pass

        # Add metadata for compatibility
        secured_func._mcp_tool_name = name or func.__name__
        secured_func._mcp_tool_description = description or func.__doc__ or ""
        secured_func._mcp_tool_permissions = permissions or []
        secured_func._mcp_rate_limit_action = rate_limit_action
        secured_func._mcp_audit_enabled = audit
        secured_func._mcp_tool_tags = tool_tags

        return secured_func

    return decorator


def mcp_context_manager(operation_type: str = "tool"):
    """
    Context manager decorator for MCP operations.

    This decorator ensures proper context setup and cleanup for MCP operations,
    including request tracking and error handling.

    Args:
        operation_type: Type of MCP operation ('tool', 'resource', 'prompt')
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request_context = None
            try:
                # Create request context if not exists
                try:
                    from .context import get_mcp_request_context

                    request_context = get_mcp_request_context()
                except RuntimeError:
                    # No request context, create one
                    request_context = create_mcp_request_context(operation_type=operation_type, tool_name=func.__name__)
                    set_mcp_request_context(request_context)

                # Execute function
                result = await func(*args, **kwargs)

                # Mark request as completed successfully
                if request_context:
                    request_context.mark_completed()
                    request_context.security_checks_passed = True

                return result

            except Exception as e:
                # Mark request as failed
                if request_context:
                    request_context.mark_completed(error=e)

                logger.error("MCP operation failed: %s, error: %s", func.__name__, e)
                raise

            finally:
                # Context cleanup is handled by the MCP server
                pass

        return wrapper

    return decorator


async def _apply_mcp_rate_limiting(user_context: MCPUserContext, rate_limit_action: str, tool_name: str) -> None:
    """
    Apply rate limiting for MCP operations using existing SecurityManager.

    Args:
        user_context: MCP user context with request information
        rate_limit_action: Rate limiting action key
        tool_name: Name of the MCP tool being executed

    Raises:
        MCPRateLimitError: If rate limit is exceeded
    """
    try:
        # Create a mock request object for SecurityManager
        # This is needed because SecurityManager expects a FastAPI Request object
        mock_request = _create_mock_request_for_rate_limiting(user_context)

        # Use existing SecurityManager rate limiting with MCP-specific settings
        await security_manager.check_rate_limit(
            mock_request,
            f"mcp_{rate_limit_action}",  # Prefix with 'mcp_' to separate from regular API limits
            rate_limit_requests=settings.MCP_RATE_LIMIT_REQUESTS,
            rate_limit_period=settings.MCP_RATE_LIMIT_PERIOD,
        )

        logger.debug(
            "Rate limit check passed for user %s, action %s, tool %s",
            user_context.user_id,
            rate_limit_action,
            tool_name,
        )

    except HTTPException as e:
        # Convert FastAPI HTTPException to MCPRateLimitError
        logger.warning(
            "Rate limit exceeded for user %s on MCP action %s (tool %s): %s",
            user_context.user_id,
            rate_limit_action,
            tool_name,
            e.detail,
        )

        # Update request context with rate limit information
        try:
            from .context import get_mcp_request_context

            request_context = get_mcp_request_context()
            request_context.rate_limit_key = f"mcp_{rate_limit_action}"
            request_context.rate_limit_remaining = 0  # Exceeded
        except RuntimeError:
            pass  # No request context available

        raise MCPRateLimitError(
            f"Rate limit exceeded for MCP action '{rate_limit_action}' on tool '{tool_name}'"
        ) from e

    except Exception as e:
        logger.error(
            "Rate limiting error for user %s, action %s, tool %s: %s",
            user_context.user_id,
            rate_limit_action,
            tool_name,
            e,
        )
        # Don't block the request on rate limiting errors, but log them
        logger.warning("Proceeding with MCP request despite rate limiting error")


def _create_mock_request_for_rate_limiting(user_context: MCPUserContext):
    """
    Create a mock request object for SecurityManager rate limiting.

    The SecurityManager expects a FastAPI Request object to extract IP and headers.
    This function creates a minimal mock that provides the necessary information.

    Args:
        user_context: MCP user context with client information

    Returns:
        Mock request object compatible with SecurityManager
    """

    class MockRequest:
        def __init__(self, ip_address: str, user_agent: str):
            self.client = MockClient(ip_address)
            self.headers = {"user-agent": user_agent or "", "x-forwarded-for": ip_address}
            self.method = "MCP"
            self.url = MockURL()

    class MockClient:
        def __init__(self, host: str):
            self.host = host or "127.0.0.1"

    class MockURL:
        def __init__(self):
            self.path = "/mcp/tool"

    return MockRequest(
        ip_address=user_context.ip_address or "127.0.0.1", user_agent=user_context.user_agent or "MCP-Client"
    )


async def check_mcp_rate_limit_status(user_context: MCPUserContext, rate_limit_action: str) -> Dict[str, Any]:
    """
    Check current rate limit status for a user and action.

    Args:
        user_context: MCP user context
        rate_limit_action: Rate limiting action key

    Returns:
        Dictionary with rate limit status information
    """
    try:
        # Import Redis manager to check current limits
        from ...managers.redis_manager import redis_manager

        redis_conn = await redis_manager.get_redis()
        ip = user_context.ip_address or "127.0.0.1"

        # Check current rate limit count
        rate_key = f"{settings.ENV_PREFIX}:ratelimit:mcp_{rate_limit_action}:{ip}"
        current_count = await redis_conn.get(rate_key)
        current_count = int(current_count) if current_count else 0

        # Calculate remaining requests
        remaining = max(0, settings.MCP_RATE_LIMIT_REQUESTS - current_count)

        # Get TTL for the rate limit window
        ttl = await redis_conn.ttl(rate_key)
        ttl = max(0, ttl) if ttl > 0 else settings.MCP_RATE_LIMIT_PERIOD

        return {
            "action": rate_limit_action,
            "limit": settings.MCP_RATE_LIMIT_REQUESTS,
            "remaining": remaining,
            "reset_in_seconds": ttl,
            "current_count": current_count,
            "window_seconds": settings.MCP_RATE_LIMIT_PERIOD,
        }

    except Exception as e:
        logger.error("Failed to check rate limit status: %s", e)
        return {
            "action": rate_limit_action,
            "limit": settings.MCP_RATE_LIMIT_REQUESTS,
            "remaining": settings.MCP_RATE_LIMIT_REQUESTS,  # Assume full limit available
            "reset_in_seconds": settings.MCP_RATE_LIMIT_PERIOD,
            "current_count": 0,
            "window_seconds": settings.MCP_RATE_LIMIT_PERIOD,
            "error": str(e),
        }


def get_mcp_rate_limit_key(action: str, ip_address: str) -> str:
    """
    Generate rate limit key for MCP operations.

    Args:
        action: Rate limiting action
        ip_address: Client IP address

    Returns:
        Redis key for rate limiting
    """
    return f"{settings.ENV_PREFIX}:ratelimit:mcp_{action}:{ip_address}"


async def reset_mcp_rate_limit(user_context: MCPUserContext, rate_limit_action: str) -> bool:
    """
    Reset rate limit for a specific user and action (admin function).

    Args:
        user_context: MCP user context
        rate_limit_action: Rate limiting action to reset

    Returns:
        True if reset was successful, False otherwise
    """
    try:
        # Only allow admins to reset rate limits
        if not user_context.has_permission("admin") and user_context.role != "admin":
            logger.warning("Non-admin user %s attempted to reset rate limit", user_context.user_id)
            return False

        from ...managers.redis_manager import redis_manager

        redis_conn = await redis_manager.get_redis()
        ip = user_context.ip_address or "127.0.0.1"

        # Delete rate limit keys
        rate_key = get_mcp_rate_limit_key(rate_limit_action, ip)
        abuse_key = f"{settings.ENV_PREFIX}:abuse:{ip}"

        deleted_count = await redis_conn.delete(rate_key, abuse_key)

        logger.info(
            "Admin %s reset rate limit for action %s, IP %s (deleted %d keys)",
            user_context.user_id,
            rate_limit_action,
            ip,
            deleted_count,
        )

        return True

    except Exception as e:
        logger.error("Failed to reset rate limit: %s", e)
        return False


class MCPRateLimitInfo:
    """
    Rate limit information for MCP operations.

    This class provides a structured way to track and report
    rate limiting information for MCP tools and operations.
    """

    def __init__(self, action: str, limit: int, remaining: int, reset_time: int, current_count: int = 0):
        self.action = action
        self.limit = limit
        self.remaining = remaining
        self.reset_time = reset_time
        self.current_count = current_count

    @property
    def is_exceeded(self) -> bool:
        """Check if rate limit is exceeded."""
        return self.remaining <= 0

    @property
    def usage_percentage(self) -> float:
        """Get usage percentage (0.0 to 1.0)."""
        if self.limit <= 0:
            return 0.0
        return min(1.0, self.current_count / self.limit)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "action": self.action,
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_time": self.reset_time,
            "current_count": self.current_count,
            "is_exceeded": self.is_exceeded,
            "usage_percentage": self.usage_percentage,
        }

    def __str__(self) -> str:
        return f"MCPRateLimit(action={self.action}, {self.current_count}/{self.limit}, remaining={self.remaining})"


def _sanitize_arguments_for_logging(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize arguments for audit logging by removing or masking sensitive data.

    Args:
        arguments: Dictionary of arguments to sanitize

    Returns:
        Sanitized arguments dictionary safe for logging
    """
    sanitized = {}

    for key, value in arguments.items():
        # Check if field is sensitive
        if _is_sensitive_field(key):
            sanitized[key] = "<REDACTED>"
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            sanitized[key] = _sanitize_arguments_for_logging(value)
        elif isinstance(value, list):
            # Sanitize lists
            sanitized[key] = [
                (
                    _sanitize_arguments_for_logging(item)
                    if isinstance(item, dict)
                    else (
                        "<REDACTED>"
                        if isinstance(item, str) and _is_sensitive_field(str(item))
                        else str(item)[:100] + "..." if isinstance(item, str) and len(str(item)) > 100 else item
                    )
                )
                for item in value
            ]
        elif isinstance(value, str):
            # Truncate long strings
            if len(value) > 200:
                sanitized[key] = value[:200] + "..."
            else:
                sanitized[key] = value
        else:
            # Convert other types to string and truncate if needed
            str_value = str(value)
            if len(str_value) > 200:
                sanitized[key] = str_value[:200] + "..."
            else:
                sanitized[key] = str_value

    return sanitized


async def log_mcp_security_event(
    event_type: str,
    user_context: MCPUserContext,
    success: bool = True,
    error: Optional[Exception] = None,
    additional_details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log MCP security events using existing logging patterns.

    Args:
        event_type: Type of security event
        user_context: MCP user context
        success: Whether the event was successful
        error: Exception if event failed
        additional_details: Additional event details
    """
    try:
        from ...utils.logging_utils import log_security_event

        # Prepare event details
        details = {
            "mcp_event": True,
            "user_id": user_context.user_id,
            "username": user_context.username,
            "role": user_context.role,
            "permissions": user_context.permissions,
            "token_type": user_context.token_type,
            "authenticated_at": user_context.authenticated_at.isoformat(),
            "trusted_ip_lockdown": user_context.trusted_ip_lockdown,
            "trusted_user_agent_lockdown": user_context.trusted_user_agent_lockdown,
        }

        # Add error information if present
        if error:
            details.update(
                {
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "error_details": getattr(error, "details", None),
                }
            )

        # Add additional details if provided
        if additional_details:
            details.update(additional_details)

        # Log the security event
        log_security_event(
            event_type=event_type,
            user_id=user_context.user_id,
            ip_address=user_context.ip_address,
            success=success,
            details=details,
        )

        # Also log with structured logging
        log_level = logger.info if success else logger.warning
        log_level(
            "MCP security event: %s for user %s - %s",
            event_type,
            user_context.username or user_context.user_id,
            "SUCCESS" if success else "FAILED",
            extra={
                "mcp_security_event": True,
                "event_type": event_type,
                "user_id": user_context.user_id,
                "success": success,
                "details": details,
            },
        )

    except Exception as e:
        logger.error("Failed to log MCP security event %s: %s", event_type, e, exc_info=True)


async def log_mcp_authentication_event(
    user_context: MCPUserContext,
    success: bool = True,
    error: Optional[Exception] = None,
    authentication_method: str = "jwt",
) -> None:
    """
    Log MCP authentication events.

    Args:
        user_context: MCP user context
        success: Whether authentication was successful
        error: Exception if authentication failed
        authentication_method: Method used for authentication
    """
    await log_mcp_security_event(
        event_type="mcp_authentication",
        user_context=user_context,
        success=success,
        error=error,
        additional_details={
            "authentication_method": authentication_method,
            "token_type": user_context.token_type,
            "token_id": user_context.token_id,
        },
    )


async def log_mcp_authorization_event(
    user_context: MCPUserContext,
    required_permissions: List[str],
    success: bool = True,
    error: Optional[Exception] = None,
    resource: Optional[str] = None,
) -> None:
    """
    Log MCP authorization events.

    Args:
        user_context: MCP user context
        required_permissions: Permissions that were required
        success: Whether authorization was successful
        error: Exception if authorization failed
        resource: Resource being accessed
    """
    await log_mcp_security_event(
        event_type="mcp_authorization",
        user_context=user_context,
        success=success,
        error=error,
        additional_details={
            "required_permissions": required_permissions,
            "user_permissions": user_context.permissions,
            "resource": resource,
            "has_required_permissions": user_context.has_all_permissions(required_permissions),
        },
    )


async def log_mcp_rate_limit_event(
    user_context: MCPUserContext,
    rate_limit_action: str,
    exceeded: bool = False,
    current_count: Optional[int] = None,
    limit: Optional[int] = None,
) -> None:
    """
    Log MCP rate limiting events.

    Args:
        user_context: MCP user context
        rate_limit_action: Rate limiting action
        exceeded: Whether rate limit was exceeded
        current_count: Current request count
        limit: Rate limit threshold
    """
    await log_mcp_security_event(
        event_type="mcp_rate_limit",
        user_context=user_context,
        success=not exceeded,
        additional_details={
            "rate_limit_action": rate_limit_action,
            "exceeded": exceeded,
            "current_count": current_count,
            "limit": limit,
            "rate_limit_key": f"mcp_{rate_limit_action}",
        },
    )


async def create_mcp_audit_trail(
    operation: str,
    user_context: MCPUserContext,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    changes: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Create comprehensive audit trail for MCP operations.

    Args:
        operation: Operation being performed
        user_context: MCP user context
        resource_type: Type of resource being operated on
        resource_id: ID of the resource
        changes: Changes being made (for update operations)
        metadata: Additional metadata
    """
    try:
        audit_record = {
            "audit_type": "mcp_operation",
            "operation": operation,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "user_id": user_context.user_id,
            "username": user_context.username,
            "role": user_context.role,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "timestamp": user_context.authenticated_at.isoformat(),
            "changes": _sanitize_arguments_for_logging(changes) if changes else None,
            "metadata": _sanitize_arguments_for_logging(metadata) if metadata else None,
        }

        # Get request context for additional information
        try:
            from .context import get_mcp_request_context

            request_context = get_mcp_request_context()
            audit_record.update(
                {
                    "request_id": request_context.request_id,
                    "duration_ms": request_context.duration_ms,
                    "tool_name": request_context.tool_name,
                }
            )
        except RuntimeError:
            pass  # No request context available

        # Log the audit record
        logger.info(
            "MCP audit trail: %s on %s by %s",
            operation,
            f"{resource_type}:{resource_id}" if resource_type and resource_id else "system",
            user_context.username or user_context.user_id,
            extra={"mcp_audit_trail": True, "audit_record": audit_record},
        )

        # Also use existing security event logging for compliance
        from ...utils.logging_utils import log_security_event

        log_security_event(
            event_type="mcp_audit_trail",
            user_id=user_context.user_id,
            ip_address=user_context.ip_address,
            success=True,
            details=audit_record,
        )

    except Exception as e:
        logger.error("Failed to create MCP audit trail for %s: %s", operation, e, exc_info=True)


class MCPAuditLogger:
    """
    Centralized audit logger for MCP operations.

    This class provides a structured way to log MCP operations
    for compliance, security monitoring, and debugging purposes.
    """

    def __init__(self):
        self.logger = get_logger(prefix="[MCP_Audit]")

    async def log_tool_execution(
        self,
        tool_name: str,
        user_context: MCPUserContext,
        parameters: Dict[str, Any],
        result: Optional[Any] = None,
        error: Optional[Exception] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Log MCP tool execution with full context."""
        await _log_mcp_tool_execution(tool_name, (), parameters, user_context)

        # Additional structured logging for tool execution
        execution_data = {
            "tool_name": tool_name,
            "success": error is None,
            "duration_ms": duration_ms,
            "parameter_count": len(parameters),
            "has_result": result is not None,
            "error_type": type(error).__name__ if error else None,
        }

        self.logger.info(
            "Tool execution: %s - %s (%.2fms)",
            tool_name,
            "SUCCESS" if error is None else "FAILED",
            duration_ms or 0,
            extra={"mcp_tool_execution": True, "execution_data": execution_data},
        )

    async def log_resource_access(
        self,
        resource_uri: str,
        user_context: MCPUserContext,
        access_type: str = "read",
        success: bool = True,
        error: Optional[Exception] = None,
    ) -> None:
        """Log MCP resource access."""
        await log_mcp_security_event(
            event_type="mcp_resource_access",
            user_context=user_context,
            success=success,
            error=error,
            additional_details={"resource_uri": resource_uri, "access_type": access_type},
        )

    async def log_prompt_generation(
        self,
        prompt_name: str,
        user_context: MCPUserContext,
        parameters: Dict[str, Any],
        success: bool = True,
        error: Optional[Exception] = None,
    ) -> None:
        """Log MCP prompt generation."""
        await log_mcp_security_event(
            event_type="mcp_prompt_generation",
            user_context=user_context,
            success=success,
            error=error,
            additional_details={"prompt_name": prompt_name, "parameters": _sanitize_arguments_for_logging(parameters)},
        )


# Global audit logger instance
mcp_audit_logger = MCPAuditLogger()


async def _create_default_user_context() -> MCPUserContext:
    """
    Create a default user context for development/STDIO mode.

    This is used when authentication is disabled or for STDIO transport
    where process-level security is sufficient.

    Returns:
        MCPUserContext with default development permissions
    """
    from datetime import datetime, timezone

    from .context import MCPUserContext

    logger.info("Creating default MCP user context for development mode")

    return MCPUserContext(
        user_id="dev-user",
        username="development-user",
        email="dev@localhost",
        role="admin",  # Full permissions for development
        permissions=["admin", "user", "family:admin", "shop:admin", "workspace:admin"],
        workspaces=[],
        family_memberships=[],
        ip_address="127.0.0.1",
        user_agent="MCP-Development-Client",
        trusted_ip_lockdown=False,
        trusted_user_agent_lockdown=False,
        trusted_ips=["127.0.0.1"],
        trusted_user_agents=["MCP-Development-Client"],
        token_type="development",
        token_id="dev-token",
        authenticated_at=datetime.now(timezone.utc),
    )


async def _validate_user_permissions(user_id: str, required_permissions: List[str]) -> bool:
    """
    Validate user permissions using existing authorization patterns.

    Args:
        user_id: User ID to check permissions for
        required_permissions: List of required permissions

    Returns:
        True if user has all required permissions, False otherwise
    """
    try:
        # Get user context to check permissions
        user_context = get_mcp_user_context()

        # Use the context's permission validation methods
        has_permissions = user_context.has_all_permissions(required_permissions)

        logger.debug(
            "Permission validation for user %s: required=%s, has_all=%s", user_id, required_permissions, has_permissions
        )

        return has_permissions

    except Exception as e:
        logger.error("Error validating permissions for user %s: %s", user_id, e)
        return False


async def _log_mcp_tool_execution(tool_name: str, args: tuple, kwargs: dict, user_context: MCPUserContext) -> None:
    """
    Log MCP tool execution for audit purposes using existing logging patterns.

    Args:
        tool_name: Name of the executed tool
        args: Tool arguments
        kwargs: Tool keyword arguments
        user_context: User context information
    """
    try:
        # Import existing logging utilities
        from ...utils.logging_utils import log_security_event

        # Sanitize arguments for logging (remove sensitive data)
        safe_kwargs = _sanitize_arguments_for_logging(kwargs)
        safe_args = _sanitize_arguments_for_logging({f"arg_{i}": arg for i, arg in enumerate(args)})

        # Get request context for additional information
        request_context = None
        try:
            from .context import get_mcp_request_context

            request_context = get_mcp_request_context()
        except RuntimeError:
            pass  # No request context available

        # Create comprehensive audit data
        audit_data = {
            "event_type": "mcp_tool_execution",
            "tool_name": tool_name,
            "user_id": user_context.user_id,
            "username": user_context.username,
            "email": user_context.email,
            "role": user_context.role,
            "ip_address": user_context.ip_address,
            "user_agent": user_context.user_agent,
            "timestamp": user_context.authenticated_at.isoformat(),
            "arguments": safe_kwargs,
            "positional_args": safe_args,
            "permissions": user_context.permissions,
            "token_type": user_context.token_type,
            "token_id": user_context.token_id,
            "family_memberships": [
                {"id": fm.get("family_id"), "role": fm.get("role")} for fm in user_context.family_memberships
            ],
            "workspaces": [
                {"id": ws.get("_id"), "name": ws.get("name"), "role": ws.get("role")} for ws in user_context.workspaces
            ],
        }

        # Add request context information if available
        if request_context:
            audit_data.update(
                {
                    "request_id": request_context.request_id,
                    "operation_type": request_context.operation_type,
                    "started_at": request_context.started_at.isoformat(),
                    "duration_ms": request_context.duration_ms,
                    "rate_limit_key": request_context.rate_limit_key,
                    "rate_limit_remaining": request_context.rate_limit_remaining,
                    "security_checks_passed": request_context.security_checks_passed,
                    "permission_checks": request_context.permission_checks,
                }
            )

        # Log using existing security event logging
        log_security_event(
            event_type="mcp_tool_execution",
            user_id=user_context.user_id,
            ip_address=user_context.ip_address,
            success=True,
            details=audit_data,
        )

        # Also log using structured logging for MCP-specific monitoring
        logger.info(
            "MCP tool executed: %s by user %s (%s) from %s",
            tool_name,
            user_context.username or user_context.user_id,
            user_context.role,
            user_context.ip_address,
            extra={
                "mcp_audit": True,
                "tool_name": tool_name,
                "user_id": user_context.user_id,
                "ip_address": user_context.ip_address,
                "audit_data": audit_data,
            },
        )

    except Exception as e:
        logger.error("Failed to log MCP tool execution for %s: %s", tool_name, e, exc_info=True)


def _is_sensitive_field(field_name: str) -> bool:
    """
    Check if a field contains sensitive information that should not be logged.

    Args:
        field_name: Name of the field to check

    Returns:
        True if field is sensitive, False otherwise
    """
    sensitive_fields = {
        "password",
        "token",
        "secret",
        "key",
        "auth",
        "credential",
        "private",
        "confidential",
        "sensitive",
    }

    field_lower = field_name.lower()
    return any(sensitive in field_lower for sensitive in sensitive_fields)


async def create_mcp_context_from_fastapi(
    request: Request, fastapi_user: Dict[str, Any], tool_name: Optional[str] = None, operation_type: str = "tool"
) -> tuple[MCPUserContext, MCPRequestContext]:
    """
    Create MCP context from FastAPI request and user.

    This function integrates with the existing FastAPI authentication system
    to create proper MCP context for security validation and audit logging.

    Args:
        request: FastAPI Request object
        fastapi_user: User object from get_current_user_dep
        tool_name: Name of the MCP tool being executed
        operation_type: Type of MCP operation

    Returns:
        Tuple of (MCPUserContext, MCPRequestContext)

    Raises:
        MCPAuthenticationError: If context creation fails
    """
    try:
        # Extract client information from request
        client_info = await extract_client_info_from_request(request)

        # Create user context from FastAPI user
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=fastapi_user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            token_type="jwt",  # Default to JWT, can be enhanced later
            token_id=None,  # Can be extracted from token if needed
        )

        # Create request context
        request_context = create_mcp_request_context(
            operation_type=operation_type, tool_name=tool_name, parameters={}  # Will be populated by tool decorators
        )

        # Set contexts in context variables
        set_mcp_user_context(user_context)
        set_mcp_request_context(request_context)

        logger.debug("Created MCP context for user %s, tool %s", user_context.user_id, tool_name)

        return user_context, request_context

    except Exception as e:
        logger.error("Failed to create MCP context: %s", e)
        raise MCPAuthenticationError(f"Failed to create MCP context: {e}") from e


async def authenticate_mcp_request(request: Request) -> MCPUserContext:
    """
    Authenticate MCP request using existing FastAPI authentication.

    This function integrates with the existing get_current_user_dep dependency
    to authenticate MCP requests and create proper security context.

    Args:
        request: FastAPI Request object

    Returns:
        MCPUserContext for the authenticated user

    Raises:
        MCPAuthenticationError: If authentication fails
    """
    try:
        # Import here to avoid circular imports
        from ...routes.auth.dependencies import get_current_user_dep, oauth2_scheme

        # Extract token from request
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise MCPAuthenticationError("Missing or invalid Authorization header")

        token = authorization.split(" ")[1]

        # Use existing authentication dependency
        fastapi_user = await get_current_user_dep(token)

        if not fastapi_user:
            raise MCPAuthenticationError("Invalid authentication token")

        # Create MCP user context
        client_info = await extract_client_info_from_request(request)
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=fastapi_user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            token_type="jwt",
            token_id=None,
        )

        # Set user context
        set_mcp_user_context(user_context)

        logger.debug("Authenticated MCP request for user %s", user_context.user_id)
        return user_context

    except HTTPException as e:
        logger.warning("MCP authentication failed: %s", e.detail)
        raise MCPAuthenticationError(f"Authentication failed: {e.detail}") from e
    except Exception as e:
        logger.error("MCP authentication error: %s", e)
        raise MCPAuthenticationError(f"Authentication error: {e}") from e


def require_mcp_authentication(func: Callable) -> Callable:
    """
    Decorator to require authentication for MCP operations.

    This decorator can be used independently or as part of the secure_mcp_tool
    decorator to ensure MCP operations are properly authenticated.

    Args:
        func: Function to decorate

    Returns:
        Decorated function that requires authentication
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Check if we already have user context (from secure_mcp_tool)
        try:
            user_context = get_mcp_user_context()
            logger.debug("Using existing MCP user context for %s", func.__name__)
        except MCPAuthenticationError:
            # No existing context, need to authenticate
            # This would typically be handled by the MCP server integration
            logger.warning("No MCP user context available for %s", func.__name__)
            raise MCPAuthenticationError("Authentication required for MCP tool access")

        return await func(*args, **kwargs)

    return wrapper
