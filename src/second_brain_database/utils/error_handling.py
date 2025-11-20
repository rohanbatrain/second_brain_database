"""
Enterprise Error Handling and Resilience Utilities.

This module provides comprehensive error handling, recovery mechanisms, and resilience patterns
for the family management system and the broader application. It implements enterprise-grade
patterns including circuit breakers, bulkhead isolation, automatic retry logic, and graceful
degradation strategies.

Key Features:
- Circuit breaker pattern for external service protection
- Bulkhead pattern for resource isolation
- Automatic retry with exponential backoff
- Graceful degradation for system failures
- Comprehensive error monitoring and alerting
- User-friendly error message translation
- Input validation and sanitization
- Error recovery mechanisms

Enterprise Patterns:
- Circuit Breaker: Prevents cascading failures by monitoring service health
- Bulkhead: Isolates resources to prevent total system failure
- Retry: Automatic retry with configurable backoff strategies
- Timeout: Configurable timeouts for all operations
- Fallback: Graceful degradation when services are unavailable
- Monitoring: Comprehensive error tracking and alerting
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import functools
import hashlib
import json
import re
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Type, Union

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

# Import monitoring with graceful fallback
try:
    from second_brain_database.managers.family_monitoring import AlertSeverity, family_monitor

    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False

logger = get_logger(prefix="[Error Handling]")

# Error handling configuration
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0
DEFAULT_CIRCUIT_BREAKER_THRESHOLD = 5
DEFAULT_CIRCUIT_BREAKER_TIMEOUT = 60
DEFAULT_OPERATION_TIMEOUT = 30
DEFAULT_BULKHEAD_CAPACITY = 10

# Sensitive data patterns for sanitization
SENSITIVE_PATTERNS = [
    r'password["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'token["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'secret["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'key["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'auth["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'credential["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'private["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'hash["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'signature["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
]


class ErrorSeverity(Enum):
    """Error severity levels for monitoring and alerting."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class RetryStrategy(Enum):
    """Retry strategies for failed operations."""

    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIBONACCI_BACKOFF = "fibonacci_backoff"


@dataclass
class ErrorContext:
    """Context information for error handling and recovery."""

    operation: str
    user_id: Optional[str] = None
    family_id: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return {
            "operation": self.operation,
            "user_id": self.user_id,
            "family_id": self.family_id,
            "request_id": self.request_id,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""

    max_attempts: int = DEFAULT_RETRY_ATTEMPTS
    initial_delay: float = DEFAULT_RETRY_DELAY
    backoff_factor: float = DEFAULT_RETRY_BACKOFF
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    retryable_exceptions: List[Type[Exception]] = field(default_factory=list)
    non_retryable_exceptions: List[Type[Exception]] = field(default_factory=list)


class CircuitBreaker:
    """
    Circuit breaker implementation for protecting against cascading failures.

    The circuit breaker monitors the failure rate of operations and opens
    when the failure threshold is exceeded, preventing further calls until
    the service recovers.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
        recovery_timeout: int = DEFAULT_CIRCUIT_BREAKER_TIMEOUT,
        expected_exception: Type[Exception] = Exception,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
        self.success_count = 0

        logger.info(
            "Circuit breaker initialized: %s (threshold: %d, timeout: %ds)", name, failure_threshold, recovery_timeout
        )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: When circuit is open
            Original exception: When function fails
        """
        if self.state == CircuitBreakerState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker %s moved to HALF_OPEN state", self.name)
            else:
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")

        try:
            result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            self._on_success()
            return result

        except self.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt to reset."""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self):
        """Handle successful operation."""
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            logger.info("Circuit breaker %s moved to CLOSED state", self.name)
        self.success_count += 1

    def _on_failure(self):
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker %s moved to OPEN state (failures: %d)", self.name, self.failure_count)

            # Send alert for circuit breaker opening
            if MONITORING_ENABLED:
                asyncio.create_task(
                    family_monitor.send_alert(
                        AlertSeverity.ERROR,
                        f"Circuit Breaker Opened: {self.name}",
                        f"Circuit breaker {self.name} opened after {self.failure_count} failures",
                        {
                            "circuit_breaker": self.name,
                            "failure_count": self.failure_count,
                            "threshold": self.failure_threshold,
                        },
                    )
                )

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self.last_failure_time,
        }


class BulkheadSemaphore:
    """
    Bulkhead pattern implementation using semaphores for resource isolation.

    Limits the number of concurrent operations to prevent resource exhaustion
    and isolate failures to specific resource pools.
    """

    def __init__(self, name: str, capacity: int = DEFAULT_BULKHEAD_CAPACITY):
        self.name = name
        self.capacity = capacity
        self.semaphore = asyncio.Semaphore(capacity)
        self.active_count = 0
        self.total_requests = 0
        self.rejected_requests = 0

        logger.info("Bulkhead semaphore initialized: %s (capacity: %d)", name, capacity)

    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire semaphore with optional timeout.

        Args:
            timeout: Maximum time to wait for acquisition

        Returns:
            True if acquired, False if timeout
        """
        self.total_requests += 1

        try:
            if timeout:
                await asyncio.wait_for(self.semaphore.acquire(), timeout=timeout)
            else:
                await self.semaphore.acquire()

            self.active_count += 1
            return True

        except asyncio.TimeoutError:
            self.rejected_requests += 1
            logger.warning(
                "Bulkhead %s rejected request due to timeout (active: %d/%d)",
                self.name,
                self.active_count,
                self.capacity,
            )
            return False

    def release(self):
        """Release semaphore."""
        if self.active_count > 0:
            self.semaphore.release()
            self.active_count -= 1

    def get_stats(self) -> Dict[str, Any]:
        """Get bulkhead statistics."""
        return {
            "name": self.name,
            "capacity": self.capacity,
            "active_count": self.active_count,
            "total_requests": self.total_requests,
            "rejected_requests": self.rejected_requests,
            "rejection_rate": self.rejected_requests / max(self.total_requests, 1),
        }


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open."""

    pass


class BulkheadCapacityError(Exception):
    """Exception raised when bulkhead capacity is exceeded."""

    pass


class RetryExhaustedError(Exception):
    """Exception raised when retry attempts are exhausted."""

    pass


class ValidationError(Exception):
    """Exception raised for input validation failures."""

    pass


class GracefulDegradationError(Exception):
    """Exception raised when graceful degradation is triggered."""

    pass


# Global circuit breakers and bulkheads
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_bulkheads: Dict[str, BulkheadSemaphore] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = DEFAULT_CIRCUIT_BREAKER_THRESHOLD,
    recovery_timeout: int = DEFAULT_CIRCUIT_BREAKER_TIMEOUT,
    expected_exception: Type[Exception] = Exception,
) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, failure_threshold, recovery_timeout, expected_exception)
    return _circuit_breakers[name]


def get_bulkhead(name: str, capacity: int = DEFAULT_BULKHEAD_CAPACITY) -> BulkheadSemaphore:
    """Get or create a bulkhead semaphore."""
    if name not in _bulkheads:
        _bulkheads[name] = BulkheadSemaphore(name, capacity)
    return _bulkheads[name]


async def retry_with_backoff(func: Callable, config: RetryConfig, context: ErrorContext, *args, **kwargs) -> Any:
    """
    Execute function with retry logic and configurable backoff strategies.

    Args:
        func: Function to execute
        config: Retry configuration
        context: Error context for logging
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Function result

    Raises:
        RetryExhaustedError: When all retry attempts are exhausted
        Original exception: When non-retryable exception occurs
    """
    last_exception = None
    delay = config.initial_delay

    for attempt in range(config.max_attempts):
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            if attempt > 0:
                logger.info("Operation succeeded after %d attempts: %s", attempt + 1, context.operation)

            return result

        except Exception as e:
            last_exception = e

            # Check if exception is non-retryable
            if config.non_retryable_exceptions and any(
                isinstance(e, exc_type) for exc_type in config.non_retryable_exceptions
            ):
                logger.info("Non-retryable exception for %s: %s", context.operation, str(e))
                raise

            # Check if exception is retryable (if specified)
            if config.retryable_exceptions and not any(
                isinstance(e, exc_type) for exc_type in config.retryable_exceptions
            ):
                logger.info("Non-retryable exception (not in retryable list) for %s: %s", context.operation, str(e))
                raise

            # Log retry attempt
            if attempt < config.max_attempts - 1:
                logger.warning(
                    "Attempt %d/%d failed for %s, retrying in %.2fs: %s",
                    attempt + 1,
                    config.max_attempts,
                    context.operation,
                    delay,
                    str(e),
                )

                await asyncio.sleep(delay)
                delay = _calculate_next_delay(delay, config)
            else:
                logger.error("All %d attempts failed for %s: %s", config.max_attempts, context.operation, str(e))

    # All attempts exhausted
    raise RetryExhaustedError(
        f"Operation {context.operation} failed after {config.max_attempts} attempts. "
        f"Last error: {str(last_exception)}"
    ) from last_exception


def _calculate_next_delay(current_delay: float, config: RetryConfig) -> float:
    """Calculate next delay based on retry strategy."""
    if config.strategy == RetryStrategy.FIXED_DELAY:
        return config.initial_delay
    elif config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
        return min(current_delay * config.backoff_factor, config.max_delay)
    elif config.strategy == RetryStrategy.LINEAR_BACKOFF:
        return min(current_delay + config.initial_delay, config.max_delay)
    elif config.strategy == RetryStrategy.FIBONACCI_BACKOFF:
        # Simplified Fibonacci-like progression
        return min(current_delay * 1.618, config.max_delay)  # Golden ratio
    else:
        return current_delay


def sanitize_sensitive_data(data: Any) -> Any:
    """
    Sanitize sensitive data from logs and error messages.

    Args:
        data: Data to sanitize (string, dict, list, etc.)

    Returns:
        Sanitized data with sensitive information redacted
    """
    if isinstance(data, str):
        sanitized = data
        for pattern in SENSITIVE_PATTERNS:
            sanitized = re.sub(pattern, r"\1<REDACTED>", sanitized, flags=re.IGNORECASE)
        return sanitized

    elif isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if any(
                sensitive in key.lower()
                for sensitive in [
                    "password",
                    "token",
                    "secret",
                    "key",
                    "auth",
                    "credential",
                    "private",
                    "hash",
                    "signature",
                ]
            ):
                sanitized[key] = "<REDACTED>"
            else:
                sanitized[key] = sanitize_sensitive_data(value)
        return sanitized

    elif isinstance(data, list):
        return [sanitize_sensitive_data(item) for item in data]

    elif isinstance(data, tuple):
        return tuple(sanitize_sensitive_data(item) for item in data)

    else:
        return data


def validate_input(data: Any, schema: Dict[str, Any], context: ErrorContext) -> Dict[str, Any]:
    """
    Validate and sanitize input data with comprehensive security controls.

    Args:
        data: Input data to validate
        schema: Validation schema
        context: Error context for logging

    Returns:
        Validated and sanitized data

    Raises:
        ValidationError: When validation fails
    """
    try:
        validated = {}

        for field, rules in schema.items():
            value = data.get(field) if isinstance(data, dict) else getattr(data, field, None)

            # Check required fields
            if rules.get("required", False) and value is None:
                raise ValidationError(f"Required field '{field}' is missing")

            if value is not None:
                # Type validation
                expected_type = rules.get("type")
                if expected_type and not isinstance(value, expected_type):
                    raise ValidationError(
                        f"Field '{field}' must be of type {expected_type.__name__}, " f"got {type(value).__name__}"
                    )

                # Length validation for strings
                if isinstance(value, str):
                    min_length = rules.get("min_length")
                    max_length = rules.get("max_length")

                    if min_length and len(value) < min_length:
                        raise ValidationError(f"Field '{field}' must be at least {min_length} characters")

                    if max_length and len(value) > max_length:
                        raise ValidationError(f"Field '{field}' must be at most {max_length} characters")

                    # Pattern validation
                    pattern = rules.get("pattern")
                    if pattern and not re.match(pattern, value):
                        raise ValidationError(f"Field '{field}' does not match required pattern")

                    # Sanitize string input
                    value = _sanitize_string_input(value)

                # Numeric validation
                if isinstance(value, (int, float)):
                    min_value = rules.get("min_value")
                    max_value = rules.get("max_value")

                    if min_value is not None and value < min_value:
                        raise ValidationError(f"Field '{field}' must be at least {min_value}")

                    if max_value is not None and value > max_value:
                        raise ValidationError(f"Field '{field}' must be at most {max_value}")

                # Custom validation function
                validator = rules.get("validator")
                if validator and not validator(value):
                    raise ValidationError(f"Field '{field}' failed custom validation")

                validated[field] = value

        logger.debug("Input validation successful for %s", context.operation)
        return validated

    except ValidationError:
        raise
    except Exception as e:
        logger.error("Input validation error for %s: %s", context.operation, str(e), extra=context.to_dict())
        raise ValidationError(f"Validation failed: {str(e)}") from e


def _sanitize_string_input(value: str) -> str:
    """Sanitize string input to prevent injection attacks."""
    # Remove null bytes
    value = value.replace("\x00", "")

    # Limit length to prevent DoS
    if len(value) > 10000:
        value = value[:10000]

    # Remove or escape potentially dangerous characters
    # This is a basic implementation - in production, use a proper sanitization library
    dangerous_chars = ["<", ">", '"', "'", "&", "\r", "\n"]
    for char in dangerous_chars:
        value = value.replace(char, "")

    return value.strip()


def create_user_friendly_error(
    exception: Exception, context: ErrorContext, include_technical_details: bool = False
) -> Dict[str, Any]:
    """
    Create user-friendly error messages from technical exceptions.

    Args:
        exception: Original exception
        context: Error context
        include_technical_details: Whether to include technical details

    Returns:
        User-friendly error response
    """
    error_type = type(exception).__name__

    # Map technical errors to user-friendly messages
    user_messages = {
        "ValidationError": "The information you provided is not valid. Please check your input and try again.",
        "FamilyLimitExceeded": "You have reached your family limit. Please upgrade your account to create more families.",
        "InsufficientPermissions": "You do not have permission to perform this action.",
        "FamilyNotFound": "The requested family could not be found.",
        "InvitationNotFound": "The invitation could not be found or has expired.",
        "AccountFrozen": "This family account is currently frozen and cannot be used.",
        "SpendingLimitExceeded": "This transaction exceeds your spending limit.",
        "RateLimitExceeded": "You are making requests too quickly. Please wait a moment and try again.",
        "CircuitBreakerOpenError": "This service is temporarily unavailable. Please try again later.",
        "BulkheadCapacityError": "The system is currently at capacity. Please try again later.",
        "RetryExhaustedError": "The operation could not be completed after multiple attempts. Please try again later.",
        "TimeoutError": "The operation took too long to complete. Please try again.",
        "ConnectionError": "Unable to connect to the service. Please check your connection and try again.",
        "DatabaseError": "A database error occurred. Please try again later.",
        "EmailError": "Unable to send email. Please verify your email address and try again.",
    }

    user_message = user_messages.get(error_type, "An unexpected error occurred. Please try again later.")

    error_response = {
        "error": {
            "code": error_type.upper(),
            "message": user_message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": context.request_id,
            "support_reference": _generate_support_reference(exception, context),
        }
    }

    # Add technical details for debugging (admin users or development)
    if include_technical_details:
        error_response["error"]["technical_details"] = {
            "exception_type": error_type,
            "exception_message": str(exception),
            "operation": context.operation,
            "context": sanitize_sensitive_data(context.to_dict()),
        }

    # Add specific error context based on exception type
    if hasattr(exception, "context"):
        error_response["error"]["context"] = sanitize_sensitive_data(exception.context)

    return error_response


def _generate_support_reference(exception: Exception, context: ErrorContext) -> str:
    """Generate a unique support reference for error tracking."""
    error_data = f"{type(exception).__name__}:{context.operation}:{context.timestamp.isoformat()}"
    return hashlib.md5(error_data.encode()).hexdigest()[:12].upper()


# Decorator for comprehensive error handling
def handle_errors(
    operation_name: str,
    circuit_breaker: Optional[str] = None,
    bulkhead: Optional[str] = None,
    retry_config: Optional[RetryConfig] = None,
    timeout: Optional[float] = None,
    fallback_func: Optional[Callable] = None,
    user_friendly_errors: bool = True,
):
    """
    Comprehensive error handling decorator with circuit breaker, bulkhead, retry, and fallback.

    Args:
        operation_name: Name of the operation for logging
        circuit_breaker: Circuit breaker name (creates if not exists)
        bulkhead: Bulkhead name (creates if not exists)
        retry_config: Retry configuration
        timeout: Operation timeout in seconds
        fallback_func: Fallback function to call on failure
        user_friendly_errors: Whether to return user-friendly error messages
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Extract context from function arguments
            context = ErrorContext(
                operation=operation_name,
                user_id=kwargs.get("user_id") or (args[1] if len(args) > 1 else None),
                family_id=kwargs.get("family_id") or (args[2] if len(args) > 2 else None),
                request_id=kwargs.get("request_id"),
                ip_address=kwargs.get("ip_address"),
            )

            start_time = time.time()

            try:
                # Bulkhead protection
                bulkhead_sem = None
                if bulkhead:
                    bulkhead_sem = get_bulkhead(bulkhead)
                    acquired = await bulkhead_sem.acquire(timeout=5.0)
                    if not acquired:
                        raise BulkheadCapacityError(f"Bulkhead {bulkhead} at capacity")

                try:
                    # Circuit breaker protection
                    if circuit_breaker:
                        cb = get_circuit_breaker(circuit_breaker)

                        # Retry logic
                        if retry_config:

                            async def circuit_breaker_func():
                                return await cb.call(func, *args, **kwargs)

                            result = await retry_with_backoff(circuit_breaker_func, retry_config, context)
                        else:
                            result = await cb.call(func, *args, **kwargs)
                    else:
                        # Retry without circuit breaker
                        if retry_config:
                            result = await retry_with_backoff(func, retry_config, context, *args, **kwargs)
                        else:
                            # Timeout protection
                            if timeout:
                                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
                            else:
                                result = await func(*args, **kwargs)

                    duration = time.time() - start_time
                    logger.info(
                        "Operation %s completed successfully in %.3fs",
                        operation_name,
                        duration,
                        extra=context.to_dict(),
                    )

                    return result

                finally:
                    # Release bulkhead
                    if bulkhead_sem:
                        bulkhead_sem.release()

            except Exception as e:
                duration = time.time() - start_time

                # Log error with context
                logger.error(
                    "Operation %s failed after %.3fs: %s",
                    operation_name,
                    duration,
                    str(e),
                    extra={
                        **context.to_dict(),
                        "exception_type": type(e).__name__,
                        "traceback": traceback.format_exc(),
                    },
                )

                # Send alert for critical errors
                if MONITORING_ENABLED and isinstance(
                    e, (CircuitBreakerOpenError, BulkheadCapacityError, RetryExhaustedError)
                ):
                    await family_monitor.send_alert(
                        AlertSeverity.ERROR,
                        f"Operation Failure: {operation_name}",
                        f"Operation {operation_name} failed: {str(e)}",
                        {
                            "operation": operation_name,
                            "error_type": type(e).__name__,
                            "duration": duration,
                            "context": sanitize_sensitive_data(context.to_dict()),
                        },
                    )

                # Try fallback function
                if fallback_func:
                    try:
                        logger.info("Attempting fallback for %s", operation_name)
                        fallback_result = await fallback_func(*args, **kwargs)
                        logger.info("Fallback successful for %s", operation_name)
                        return fallback_result
                    except Exception as fallback_error:
                        logger.error("Fallback failed for %s: %s", operation_name, str(fallback_error))

                # Return user-friendly error or re-raise
                if user_friendly_errors:
                    error_response = create_user_friendly_error(e, context)
                    # In a real application, you might want to raise a custom HTTP exception
                    # For now, we'll add the error response to the exception
                    e.user_friendly_response = error_response

                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Simplified synchronous version
            context = ErrorContext(operation=operation_name)
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info("Operation %s (sync) completed successfully in %.3fs", operation_name, duration)
                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error("Operation %s (sync) failed after %.3fs: %s", operation_name, duration, str(e))

                if user_friendly_errors:
                    error_response = create_user_friendly_error(e, context)
                    e.user_friendly_response = error_response

                raise

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Health check functions for error handling components
async def get_error_handling_health() -> Dict[str, Any]:
    """Get health status of error handling components."""
    health_status = {"circuit_breakers": {}, "bulkheads": {}, "overall_healthy": True}

    # Check circuit breakers
    for name, cb in _circuit_breakers.items():
        stats = cb.get_stats()
        health_status["circuit_breakers"][name] = stats
        if stats["state"] == CircuitBreakerState.OPEN.value:
            health_status["overall_healthy"] = False

    # Check bulkheads
    for name, bulkhead in _bulkheads.items():
        stats = bulkhead.get_stats()
        health_status["bulkheads"][name] = stats
        if stats["rejection_rate"] > 0.1:  # 10% rejection rate threshold
            health_status["overall_healthy"] = False

    return health_status


# Graceful degradation helpers
async def with_graceful_degradation(
    primary_func: Callable, fallback_func: Callable, context: ErrorContext, *args, **kwargs
) -> Any:
    """
    Execute function with graceful degradation fallback.

    Args:
        primary_func: Primary function to execute
        fallback_func: Fallback function if primary fails
        context: Error context
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Result from primary or fallback function
    """
    try:
        return await primary_func(*args, **kwargs)
    except Exception as e:
        logger.warning("Primary function failed for %s, attempting graceful degradation: %s", context.operation, str(e))

        try:
            result = await fallback_func(*args, **kwargs)
            logger.info("Graceful degradation successful for %s", context.operation)
            return result
        except Exception as fallback_error:
            logger.error("Graceful degradation failed for %s: %s", context.operation, str(fallback_error))
            raise GracefulDegradationError(f"Both primary and fallback functions failed for {context.operation}") from e
