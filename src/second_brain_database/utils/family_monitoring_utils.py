"""
Family Management Monitoring Utilities.

This module provides decorators and utilities for monitoring family operations
with structured logging, performance tracking, and alerting integration.
"""

import asyncio
from datetime import datetime, timezone
import functools
import time
from typing import Any, Callable, Dict, Optional

from second_brain_database.managers.logging_manager import get_logger

# Import monitoring system with graceful fallback
try:
    from second_brain_database.managers.family_monitoring import (
        FamilyOperationContext,
        FamilyOperationType,
        family_monitor,
    )

    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False

logger = get_logger(prefix="[Family Monitoring Utils]")


def monitor_family_operation(
    operation_type: FamilyOperationType, extract_context: Optional[Callable] = None, log_args: bool = False
):
    """
    Decorator for monitoring family operations with comprehensive logging and metrics.

    Args:
        operation_type: Type of family operation being monitored
        extract_context: Function to extract context from function arguments
        log_args: Whether to log function arguments (be careful with sensitive data)

    Usage:
        @monitor_family_operation(FamilyOperationType.FAMILY_CREATE)
        async def create_family(self, user_id: str, name: str):
            # Implementation here
            pass

        @monitor_family_operation(
            FamilyOperationType.MEMBER_INVITE,
            extract_context=lambda args, kwargs: {
                "family_id": args[1] if len(args) > 1 else kwargs.get("family_id"),
                "user_id": args[2] if len(args) > 2 else kwargs.get("inviter_id")
            }
        )
        async def invite_member(self, family_id: str, inviter_id: str, ...):
            # Implementation here
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            operation_id = f"{operation_type.value}_{int(time.time() * 1000)}"

            # Extract context if function provided
            context_data = {}
            if extract_context:
                try:
                    context_data = extract_context(args, kwargs) or {}
                except Exception as e:
                    logger.warning("Failed to extract context for %s: %s", operation_type.value, e)

            # Log operation start
            if log_args and (args or kwargs):
                safe_args = _sanitize_args(args, kwargs)
                logger.info("[%s] Starting %s with args: %s", operation_id, operation_type.value, safe_args)
            else:
                logger.info("[%s] Starting %s", operation_id, operation_type.value)

            success = False
            error_message = None
            result = None

            try:
                result = await func(*args, **kwargs)
                success = True
                duration = time.time() - start_time

                logger.info("[%s] Completed %s successfully in %.3fs", operation_id, operation_type.value, duration)

                # Log to monitoring system
                if MONITORING_ENABLED:
                    await family_monitor.log_family_operation(
                        FamilyOperationContext(
                            operation_type=operation_type,
                            family_id=context_data.get("family_id"),
                            user_id=context_data.get("user_id"),
                            target_user_id=context_data.get("target_user_id"),
                            amount=context_data.get("amount"),
                            duration=duration,
                            success=True,
                            metadata=context_data.get("metadata", {}),
                            request_id=context_data.get("request_id"),
                            ip_address=context_data.get("ip_address"),
                        )
                    )
                    await family_monitor.log_family_performance(
                        operation_type, duration, success=True, metadata=context_data.get("metadata", {})
                    )

                return result

            except Exception as e:
                success = False
                error_message = str(e)
                duration = time.time() - start_time

                logger.error(
                    "[%s] Failed %s after %.3fs: %s", operation_id, operation_type.value, duration, error_message
                )

                # Log to monitoring system
                if MONITORING_ENABLED:
                    await family_monitor.log_family_operation(
                        FamilyOperationContext(
                            operation_type=operation_type,
                            family_id=context_data.get("family_id"),
                            user_id=context_data.get("user_id"),
                            target_user_id=context_data.get("target_user_id"),
                            amount=context_data.get("amount"),
                            duration=duration,
                            success=False,
                            error_message=error_message,
                            metadata={**context_data.get("metadata", {}), "error_type": type(e).__name__},
                            request_id=context_data.get("request_id"),
                            ip_address=context_data.get("ip_address"),
                        )
                    )
                    await family_monitor.log_family_performance(
                        operation_type,
                        duration,
                        success=False,
                        metadata={**context_data.get("metadata", {}), "error_type": type(e).__name__},
                    )

                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For synchronous functions, we can't use the async monitoring
            # but we can still do basic logging
            start_time = time.time()
            operation_id = f"{operation_type.value}_{int(time.time() * 1000)}"

            logger.info("[%s] Starting %s (sync)", operation_id, operation_type.value)

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                logger.info(
                    "[%s] Completed %s (sync) successfully in %.3fs", operation_id, operation_type.value, duration
                )
                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.error(
                    "[%s] Failed %s (sync) after %.3fs: %s", operation_id, operation_type.value, duration, str(e)
                )
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def log_family_security_event(
    event_type: str,
    family_id: Optional[str] = None,
    user_id: Optional[str] = None,
    target_user_id: Optional[str] = None,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
):
    """
    Log family-related security events with structured data.

    Args:
        event_type: Type of security event
        family_id: Family ID if applicable
        user_id: User performing the action
        target_user_id: Target user if applicable
        success: Whether the event was successful
        details: Additional event details
        ip_address: Client IP address
    """
    security_logger = get_logger(name="Family_Security", prefix="[FAMILY_SECURITY]")

    event_data = {
        "event": "family_security_event",
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "family_id": family_id,
        "user_id": user_id,
        "target_user_id": target_user_id,
        "success": success,
        "ip_address": ip_address or "unknown",
        "details": _sanitize_security_details(details) if details else {},
        "process": __import__("os").getpid(),
        "host": __import__("os").getenv("HOSTNAME", "unknown"),
        "app": __import__("os").getenv("APP_NAME", "Second_Brain_Database-app"),
        "env": __import__("os").getenv("ENV", "dev"),
    }

    if success:
        security_logger.info(event_data)
    else:
        security_logger.warning(event_data)


def log_family_audit_event(
    action: str,
    family_id: str,
    admin_user_id: str,
    target_user_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
):
    """
    Log family audit events for compliance and tracking.

    Args:
        action: Action performed (promote, demote, remove, etc.)
        family_id: Family ID
        admin_user_id: Admin user performing the action
        target_user_id: Target user if applicable
        details: Additional action details
        ip_address: Client IP address
    """
    audit_logger = get_logger(name="Family_Audit", prefix="[FAMILY_AUDIT]")

    audit_data = {
        "event": "family_audit_event",
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "family_id": family_id,
        "admin_user_id": admin_user_id,
        "target_user_id": target_user_id,
        "ip_address": ip_address or "unknown",
        "details": details or {},
        "process": __import__("os").getpid(),
        "host": __import__("os").getenv("HOSTNAME", "unknown"),
        "app": __import__("os").getenv("APP_NAME", "Second_Brain_Database-app"),
        "env": __import__("os").getenv("ENV", "dev"),
    }

    audit_logger.info(audit_data)


def log_sbd_transaction(
    transaction_type: str,
    family_id: str,
    user_id: str,
    amount: int,
    success: bool = True,
    details: Optional[Dict[str, Any]] = None,
    transaction_id: Optional[str] = None,
):
    """
    Log SBD token transactions for family accounts.

    Args:
        transaction_type: Type of transaction (deposit, spend, freeze, etc.)
        family_id: Family ID
        user_id: User performing the transaction
        amount: Transaction amount
        success: Whether transaction was successful
        details: Additional transaction details
        transaction_id: Unique transaction ID
    """
    sbd_logger = get_logger(name="Family_SBD", prefix="[FAMILY_SBD]")

    transaction_data = {
        "event": "family_sbd_transaction",
        "transaction_type": transaction_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "family_id": family_id,
        "user_id": user_id,
        "amount": amount,
        "success": success,
        "transaction_id": transaction_id,
        "details": details or {},
        "process": __import__("os").getpid(),
        "host": __import__("os").getenv("HOSTNAME", "unknown"),
        "app": __import__("os").getenv("APP_NAME", "Second_Brain_Database-app"),
        "env": __import__("os").getenv("ENV", "dev"),
    }

    if success:
        sbd_logger.info(transaction_data)
    else:
        sbd_logger.error(transaction_data)


# Helper functions


def _sanitize_args(args: tuple, kwargs: dict) -> dict:
    """
    Sanitize function arguments to avoid logging sensitive data.
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
        "signature",
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
        "auth_token",
    }

    sanitized = {}
    for key, value in details.items():
        if any(sensitive_key in key.lower() for sensitive_key in sensitive_keys):
            sanitized[key] = "<REDACTED>"
        else:
            sanitized[key] = value

    return sanitized


# Context managers for operation tracking


class FamilyOperationTracker:
    """
    Context manager for tracking family operations with automatic logging.

    Usage:
        async with FamilyOperationTracker(
            FamilyOperationType.FAMILY_CREATE,
            family_id="fam_123",
            user_id="user_456"
        ) as tracker:
            # Perform operation
            result = await some_operation()
            tracker.set_success(True)
            tracker.add_metadata({"result_count": len(result)})
    """

    def __init__(
        self,
        operation_type: FamilyOperationType,
        family_id: Optional[str] = None,
        user_id: Optional[str] = None,
        target_user_id: Optional[str] = None,
        amount: Optional[int] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ):
        self.operation_type = operation_type
        self.family_id = family_id
        self.user_id = user_id
        self.target_user_id = target_user_id
        self.amount = amount
        self.request_id = request_id
        self.ip_address = ip_address
        self.start_time = None
        self.success = False
        self.error_message = None
        self.metadata = {}

    async def __aenter__(self):
        self.start_time = time.time()
        logger.info(
            "Starting family operation: %s (family: %s, user: %s)",
            self.operation_type.value,
            self.family_id,
            self.user_id,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time if self.start_time else 0

        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)

        # Log to monitoring system
        if MONITORING_ENABLED:
            await family_monitor.log_family_operation(
                FamilyOperationContext(
                    operation_type=self.operation_type,
                    family_id=self.family_id,
                    user_id=self.user_id,
                    target_user_id=self.target_user_id,
                    amount=self.amount,
                    duration=duration,
                    success=self.success,
                    error_message=self.error_message,
                    metadata=self.metadata,
                    request_id=self.request_id,
                    ip_address=self.ip_address,
                )
            )
            await family_monitor.log_family_performance(
                self.operation_type, duration, success=self.success, metadata=self.metadata
            )

        if self.success:
            logger.info("Completed family operation: %s in %.3fs", self.operation_type.value, duration)
        else:
            logger.error(
                "Failed family operation: %s after %.3fs - %s", self.operation_type.value, duration, self.error_message
            )

    def set_success(self, success: bool):
        """Mark the operation as successful or failed."""
        self.success = success

    def add_metadata(self, metadata: Dict[str, Any]):
        """Add metadata to the operation context."""
        self.metadata.update(metadata)

    def set_error(self, error_message: str):
        """Set error message for failed operations."""
        self.success = False
        self.error_message = error_message
