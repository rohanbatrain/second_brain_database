"""
Tenant context management using context variables.

This module provides thread-safe tenant context management for request-scoped
tenant isolation using Python's contextvars.
"""

from contextvars import ContextVar
from typing import Optional

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Tenant Context]")

# Context variable for tenant isolation
_tenant_context: ContextVar[Optional[str]] = ContextVar("tenant_context", default=None)


def get_current_tenant_id() -> Optional[str]:
    """
    Get the current tenant ID from context.

    Returns:
        Optional[str]: The current tenant ID, or None if not set
    """
    return _tenant_context.get()


def set_tenant_context(tenant_id: str) -> None:
    """
    Set the tenant context for the current request.

    Args:
        tenant_id: The tenant ID to set in context
    """
    _tenant_context.set(tenant_id)
    logger.debug("Set tenant context: %s", tenant_id)


def clear_tenant_context() -> None:
    """Clear the tenant context."""
    _tenant_context.set(None)
    logger.debug("Cleared tenant context")


def require_tenant_context() -> str:
    """
    Get the current tenant ID, raising an error if not set.

    Returns:
        str: The current tenant ID

    Raises:
        RuntimeError: If no tenant context is set
    """
    tenant_id = get_current_tenant_id()
    if tenant_id is None:
        raise RuntimeError("No tenant context available - tenant context must be set")
    return tenant_id
