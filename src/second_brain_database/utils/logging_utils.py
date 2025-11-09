"""Logging utilities for comprehensive application logging.

This module provides decorators, middleware, and utilities for adding
detailed logging throughout the application with performance monitoring,
security context, and error handling.
"""

import asyncio
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import functools
import time
import traceback
from typing import Any, Callable, Dict, Optional
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from second_brain_database.managers.logging_manager import get_logger

# Context variables for request tracing
request_id_context: ContextVar[str] = ContextVar("request_id", default="")
user_id_context: ContextVar[str] = ContextVar("user_id", default="")
ip_address_context: ContextVar[str] = ContextVar("ip_address", default="")


@dataclass
class SecurityContext:
    """Security event context for logging."""

    event_type: str
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    success: bool = True
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None


@dataclass
class DatabaseContext:
    """Database operation context for logging."""

    operation: str
    collection: str
    query: Optional[Dict[str, Any]] = None
    duration: Optional[float] = None
    result_count: Optional[int] = None
    timestamp: Optional[str] = None


class SecurityLogger:
    """Specialized logger for security events."""

    def __init__(self, prefix: str = "[SECURITY]"):
        self.logger = get_logger(name="Second_Brain_Database_Security", prefix=prefix)

    def log_event(self, context: SecurityContext):
        """Log a security event with full context (structured JSON)."""
        import os

        event_data = {
            "event": "security_event",
            "event_type": context.event_type,
            "timestamp": context.timestamp or datetime.now(timezone.utc).isoformat(),
            "success": context.success,
            "user_id": context.user_id or "anonymous",
            "ip_address": context.ip_address or "unknown",
            "details": _sanitize_security_details(context.details) if context.details else None,
            "process": os.getpid(),
            "host": os.getenv("HOSTNAME", "unknown"),
            "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
            "env": os.getenv("ENV", "dev"),
        }
        status = "SUCCESS" if context.success else "FAILURE"
        event_data["status"] = status
        self.logger.info(event_data)


class DatabaseLogger:
    """Specialized logger for database operations (structured JSON)."""

    def __init__(self, prefix: str = "[DATABASE]"):
        self.logger = get_logger(name="Second_Brain_Database_DB_Operations", prefix=prefix)

    def log_operation(self, context: DatabaseContext):
        import os

        log_data = {
            "event": "database_operation",
            "operation": context.operation,
            "collection": context.collection,
            "query": _sanitize_security_details(context.query) if context.query else None,
            "duration": context.duration,
            "result_count": context.result_count,
            "timestamp": context.timestamp or datetime.now(timezone.utc).isoformat(),
            "process": os.getpid(),
            "host": os.getenv("HOSTNAME", "unknown"),
            "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
            "env": os.getenv("ENV", "dev"),
        }
        self.logger.info(log_data)

    def log_query(self, context: DatabaseContext):
        """Log database query with appropriate level based on success/error."""
        if hasattr(context, "error") and context.error:
            self.logger.error(
                f"DB {context.operation.upper()} on {context.collection} FAILED - {context.error} - Duration: {context.duration:.3f}s"
            )
        else:
            result_info = f" - Results: {context.result_count}" if context.result_count is not None else ""
            self.logger.info(
                f"DB {context.operation.upper()} on {context.collection} - Duration: {context.duration:.3f}s{result_info}"
            )

    def log_slow_query(self, context: DatabaseContext, threshold: float = 1.0):
        """Log slow database queries."""
        self.logger.warning(
            f"SLOW QUERY: {context.operation.upper()} on {context.collection} - Duration: {context.duration:.3f}s (threshold: {threshold:.3f}s)"
        )


class PerformanceLogger:
    """Specialized logger for performance monitoring."""

    def __init__(self, prefix: str = "[PERFORMANCE]"):
        self.logger = get_logger(name="Second_Brain_Database_Performance", prefix=prefix)

    def log_operation(self, operation_name: str, duration: float):
        """Log operation performance."""
        self.logger.info(f"Operation '{operation_name}' completed in {duration:.3f}s")

    def log_slow_operation(self, operation_name: str, duration: float, threshold: float = 1.0):
        """Log slow operations."""
        self.logger.warning(f"SLOW OPERATION: '{operation_name}' took {duration:.3f}s (threshold: {threshold:.3f}s)")


def log_auth_success(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """Log successful authentication events."""
    context = SecurityContext(
        event_type=event_type, user_id=user_id, ip_address=ip_address, success=True, details=details
    )
    security_logger = SecurityLogger()
    security_logger.log_event(context)


def log_auth_failure(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
):
    """Log failed authentication events."""
    context = SecurityContext(
        event_type=event_type, user_id=user_id, ip_address=ip_address, success=False, details=details
    )
    security_logger = SecurityLogger()
    security_logger.log_event(context)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive request/response logging middleware for FastAPI.

    Logs all incoming requests and outgoing responses with timing,
    status codes, and relevant context information.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.logger = get_logger(name="Second_Brain_Database_Requests", prefix="[REQUEST]")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with comprehensive logging (structured JSON)."""
        from datetime import datetime, timezone
        import os
        import traceback

        # Generate unique request ID for tracing
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Extract request information
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "unknown")
        method = request.method
        path = str(request.url.path)
        query_params = str(request.url.query) if request.url.query else None

        # Log incoming request (structured JSON)
        log_data = {
            "event": "request_received",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "method": method,
            "path": path,
            "query_params": query_params,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "process": os.getpid(),
            "thread": None,  # Optionally add threading.get_ident() if needed
            "host": os.getenv("HOSTNAME", "unknown"),
            "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
            "env": os.getenv("ENV", "dev"),
        }
        self.logger.info(log_data)

        # Process request and capture response
        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log successful response (structured JSON)
            response_log = {
                "event": "response_sent",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration": duration,
                "response_size": len(getattr(response, "body", b"")),
                "client_ip": client_ip,
                "user_agent": user_agent,
                "process": os.getpid(),
                "thread": None,
                "host": os.getenv("HOSTNAME", "unknown"),
                "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
                "env": os.getenv("ENV", "dev"),
            }
            self.logger.info(response_log)

            # Log slow requests
            if duration > 1.0:
                slow_log = response_log.copy()
                slow_log["event"] = "slow_request"
                self.logger.warning(slow_log)

            return response

        except Exception as e:
            duration = time.time() - start_time
            error_log = {
                "event": "request_error",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "method": method,
                "path": path,
                "duration": duration,
                "exception": str(e),
                "stack_trace": traceback.format_exc(),
                "client_ip": client_ip,
                "user_agent": user_agent,
                "process": os.getpid(),
                "thread": None,
                "host": os.getenv("HOSTNAME", "unknown"),
                "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
                "env": os.getenv("ENV", "dev"),
            }
            self.logger.error(error_log)
            raise

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request headers."""
        # Check for forwarded headers first (for reverse proxy setups)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to direct client IP
        return getattr(request.client, "host", "unknown")


def log_performance(operation_name: str, log_args: bool = False):
    """
    Decorator for logging function/method performance with timing.

    Args:
        operation_name: Name of the operation for logging
        log_args: Whether to log function arguments (be careful with sensitive data)
    """

    def decorator(func: Callable) -> Callable:
        logger = get_logger(name="Second_Brain_Database_Performance", prefix="[PERFORMANCE]")

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = str(uuid.uuid4())[:8]

            # Log operation start
            if log_args and (args or kwargs):
                # Sanitize arguments to avoid logging sensitive data
                safe_args = _sanitize_args(args, kwargs)
                logger.info("[%s] Starting %s with args: %s", operation_id, operation_name, safe_args)
            else:
                logger.info("[%s] Starting %s", operation_id, operation_name)

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info("[%s] Completed %s in %.3fs", operation_id, operation_name, duration)

                # Log slow operations
                if duration > 2.0:
                    logger.warning("[%s] SLOW OPERATION: %s took %.3fs", operation_id, operation_name, duration)

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error("[%s] Failed %s after %.3fs: %s", operation_id, operation_name, duration, str(e))
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = str(uuid.uuid4())[:8]

            # Log operation start
            if log_args and (args or kwargs):
                safe_args = _sanitize_args(args, kwargs)
                logger.info("[%s] Starting %s with args: %s", operation_id, operation_name, safe_args)
            else:
                logger.info("[%s] Starting %s", operation_id, operation_name)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info("[%s] Completed %s in %.3fs", operation_id, operation_name, duration)

                if duration > 2.0:
                    logger.warning("[%s] SLOW OPERATION: %s took %.3fs", operation_id, operation_name, duration)

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error("[%s] Failed %s after %.3fs: %s", operation_id, operation_name, duration, str(e))
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_database_operation(collection_name: str, operation_type: str):
    """
    Decorator for logging database operations with performance metrics.

    Args:
        collection_name: Name of the MongoDB collection
        operation_type: Type of operation (find, insert, update, delete, etc.)
    """

    def decorator(func: Callable) -> Callable:
        logger = get_logger(name="Second_Brain_Database_DB_Operations", prefix="[DATABASE]")

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = str(uuid.uuid4())[:8]

            logger.info("[%s] DB %s on %s", operation_id, operation_type, collection_name)

            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Try to get result count if available
                result_count = None
                if hasattr(result, "inserted_id"):
                    result_count = 1
                elif hasattr(result, "modified_count"):
                    result_count = result.modified_count
                elif hasattr(result, "deleted_count"):
                    result_count = result.deleted_count
                elif isinstance(result, list):
                    result_count = len(result)

                if result_count is not None:
                    logger.info(
                        "[%s] DB %s on %s completed in %.3fs - %s records affected",
                        operation_id,
                        operation_type,
                        collection_name,
                        duration,
                        result_count,
                    )
                else:
                    logger.info(
                        "[%s] DB %s on %s completed in %.3fs", operation_id, operation_type, collection_name, duration
                    )

                # Log slow database operations
                if duration > 1.0:
                    logger.warning(
                        "[%s] SLOW DB OPERATION: %s on %s took %.3fs",
                        operation_id,
                        operation_type,
                        collection_name,
                        duration,
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "[%s] DB %s on %s failed after %.3fs: %s",
                    operation_id,
                    operation_type,
                    collection_name,
                    duration,
                    str(e),
                )
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = str(uuid.uuid4())[:8]

            logger.info("[%s] DB %s on %s", operation_id, operation_type, collection_name)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                logger.info(
                    "[%s] DB %s on %s completed in %.3fs", operation_id, operation_type, collection_name, duration
                )

                if duration > 1.0:
                    logger.warning(
                        "[%s] SLOW DB OPERATION: %s on %s took %.3fs",
                        operation_id,
                        operation_type,
                        collection_name,
                        duration,
                    )

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "[%s] DB %s on %s failed after %.3fs: %s",
                    operation_id,
                    operation_type,
                    collection_name,
                    duration,
                    str(e),
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log security-related events with proper context.

    Args:
        event_type: Type of security event (login, logout, token_creation, etc.)
        user_id: User identifier if available
        ip_address: Client IP address if available
        success: Whether the security event was successful
        details: Additional event details
    """
    logger = get_logger(name="Second_Brain_Database_Security", prefix="[SECURITY]")

    event_data = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success": success,
        "user_id": user_id or "anonymous",
        "ip_address": ip_address or "unknown",
    }

    if details:
        # Sanitize details to avoid logging sensitive information
        event_data["details"] = _sanitize_security_details(details)

    status = "SUCCESS" if success else "FAILURE"
    logger.info("SECURITY EVENT [%s]: %s - %s", status, event_type, event_data)


def log_application_lifecycle(event: str, details: Optional[Dict[str, Any]] = None):
    """
    Log application lifecycle events (startup, shutdown, etc.).

    Args:
        event: Lifecycle event name
        details: Additional event details
    """
    logger = get_logger(name="Second_Brain_Database_Lifecycle", prefix="[LIFECYCLE]")

    event_data = {"event": event, "timestamp": datetime.now(timezone.utc).isoformat()}

    if details:
        event_data.update(details)

    logger.info("APPLICATION LIFECYCLE: %s - %s", event, event_data)


def log_error_with_context(error: Exception, context: Optional[Dict[str, Any]] = None, operation: Optional[str] = None):
    """
    Log errors with full context and stack trace.

    Args:
        error: The exception that occurred
        context: Additional context information
        operation: Name of the operation that failed
    """
    logger = get_logger(name="Second_Brain_Database_Errors", prefix="[ERROR]")

    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stack_trace": traceback.format_exc(),
    }

    if operation:
        error_data["operation"] = operation

    if context:
        error_data["context"] = _sanitize_args({}, context)

    logger.error("ERROR OCCURRED: %s", error_data)


@asynccontextmanager
async def log_operation_context(operation_name: str, **context):
    """
    Context manager for logging operation start/end with context preservation.

    Args:
        operation_name: Name of the operation
        **context: Additional context to log
    """
    logger = get_logger(name="Second_Brain_Database_Operations", prefix="[OPERATION]")
    operation_id = str(uuid.uuid4())[:8]
    start_time = time.time()

    logger.info("[%s] Starting %s - Context: %s", operation_id, operation_name, context)

    try:
        yield operation_id
        duration = time.time() - start_time
        logger.info("[%s] Completed %s in %.3fs", operation_id, operation_name, duration)
    except Exception as e:
        duration = time.time() - start_time
        logger.error("[%s] Failed %s after %.3fs: %s", operation_id, operation_name, duration, str(e))
        raise


def _sanitize_args(args: tuple, kwargs: dict) -> dict:
    """
    Sanitize function arguments to avoid logging sensitive data.

    Args:
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Sanitized arguments dictionary
    """
    sensitive_keys = {
        "password",
        "token",
        "secret",
        "key",
        "auth",
        "credential",
        "private",
        "confidential",
        "sensitive",
        "hash",
    }

    sanitized = {}

    # Handle positional args
    if args:
        sanitized["args"] = [
            (
                "<REDACTED>"
                if any(key in str(arg).lower() for key in sensitive_keys)
                else str(arg)[:100] + ("..." if len(str(arg)) > 100 else "")
            )
            for arg in args
        ]

    # Handle keyword args
    if kwargs:
        sanitized["kwargs"] = {}
        for key, value in kwargs.items():
            if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
                sanitized["kwargs"][key] = "<REDACTED>"
            else:
                str_value = str(value)
                sanitized["kwargs"][key] = str_value[:100] + ("..." if len(str_value) > 100 else "")

    return sanitized


def _sanitize_security_details(details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize security event details to avoid logging sensitive information.

    Args:
        details: Original details dictionary

    Returns:
        Sanitized details dictionary
    """
    sensitive_keys = {
        "password",
        "token",
        "secret",
        "key",
        "hash",
        "signature",
        "private_key",
        "public_key",
        "credential",
    }

    sanitized = {}
    for key, value in details.items():
        if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            sanitized[key] = "<REDACTED>"
        else:
            sanitized[key] = value

    return sanitized
