"""
IPAM Audit Logging Utilities.

This module provides comprehensive audit trail logging for IPAM operations,
following the established audit patterns from family_audit_manager.

Features:
    - Complete resource snapshots for point-in-time recovery
    - Field-level change tracking for updates
    - User identity and timestamp tracking
    - Action type and result logging
    - Integration with centralized logging_manager
    - Immutable audit trail storage

Audit Event Types:
    - create: New allocation created
    - update: Allocation metadata updated
    - release: Host address released
    - retire: Allocation permanently deleted
    - reserve: Address space reserved
    - reservation_expired: Reservation automatically expired
    - capacity_warning: Capacity threshold reached
    - quota_exceeded: User quota limit reached
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.errors import PyMongoError

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMAudit]")

# Audit event types
AUDIT_EVENT_TYPES = {
    "create": "Resource Created",
    "update": "Resource Updated",
    "release": "Host Address Released",
    "retire": "Allocation Retired",
    "reserve": "Address Space Reserved",
    "reservation_expired": "Reservation Expired",
    "capacity_warning": "Capacity Threshold Reached",
    "quota_exceeded": "Quota Limit Reached",
}

# Resource types
RESOURCE_TYPES = {
    "region": "Regional Block (/24)",
    "host": "Host Address",
    "reservation": "Address Reservation",
}


class IPAMAuditError(Exception):
    """Base IPAM audit exception."""

    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code or "IPAM_AUDIT_ERROR"
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)


async def log_ipam_audit_event(
    user_id: str,
    action_type: str,
    resource_type: str,
    resource_id: str,
    details: Dict[str, Any],
    ip_address: Optional[str] = None,
    session: Optional[ClientSession] = None,
) -> Dict[str, Any]:
    """
    Log comprehensive audit trail for IPAM operations.

    This function creates an immutable audit record with complete resource snapshots
    and field-level change tracking, following the pattern from family_audit_manager.

    Args:
        user_id: ID of user performing the action
        action_type: Type of action (create, update, release, retire, etc.)
        resource_type: Type of resource (region, host, reservation)
        resource_id: Unique identifier of the resource
        details: Complete resource snapshot and additional context
        ip_address: IP address or CIDR for the resource (optional)
        session: Database session for transaction safety (optional)

    Returns:
        Dict containing audit trail information with audit_id

    Raises:
        IPAMAuditError: If audit logging fails

    Example:
        >>> await log_ipam_audit_event(
        ...     user_id="user123",
        ...     action_type="create",
        ...     resource_type="region",
        ...     resource_id="550e8400-e29b-41d4-a716-446655440000",
        ...     details={
        ...         "snapshot": {"cidr": "10.5.23.0/24", "region_name": "Mumbai DC1"},
        ...         "country": "India",
        ...         "x_octet": 5,
        ...         "y_octet": 23
        ...     },
        ...     ip_address="10.5.23.0/24"
        ... )
    """
    operation_context = {
        "user_id": user_id,
        "action_type": action_type,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "operation": "log_ipam_audit_event",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    start_time = db_manager.log_query_start("ipam_audit_history", "insert_audit", operation_context)

    try:
        # Prepare audit document
        audit_doc = {
            "user_id": user_id,
            "action_type": action_type,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "ip_address": ip_address,
            "cidr": details.get("cidr"),
            "snapshot": details.get("snapshot", {}),
            "changes": details.get("changes", []),
            "reason": details.get("reason"),
            "metadata": {
                "country": details.get("country"),
                "region_name": details.get("region_name"),
                "hostname": details.get("hostname"),
                "x_octet": details.get("x_octet"),
                "y_octet": details.get("y_octet"),
                "z_octet": details.get("z_octet"),
                "status": details.get("status"),
                "owner": details.get("owner"),
            },
            "timestamp": datetime.now(timezone.utc),
            "result": details.get("result", "success"),
            "error_message": details.get("error_message"),
        }

        # Insert audit record
        audit_collection = db_manager.get_collection("ipam_audit_history")
        result = await audit_collection.insert_one(audit_doc, session=session)

        audit_id = str(result.inserted_id)

        # Log structured audit event
        logger.info(
            "ipam_audit_event_logged",
            extra={
                "audit_id": audit_id,
                "user_id": user_id,
                "action_type": action_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "ip_address": ip_address,
                "result": audit_doc["result"],
            },
        )

        db_manager.log_query_end(start_time, "ipam_audit_history", "insert_audit", operation_context)

        return {
            "audit_id": audit_id,
            "timestamp": audit_doc["timestamp"],
            "action_type": action_type,
            "resource_type": resource_type,
            "result": audit_doc["result"],
        }

    except PyMongoError as e:
        db_manager.log_query_end(start_time, "ipam_audit_history", "insert_audit", operation_context, error=str(e))
        logger.error(
            "ipam_audit_logging_failed",
            extra={
                "user_id": user_id,
                "action_type": action_type,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "error": str(e),
            },
            exc_info=True,
        )
        raise IPAMAuditError(
            f"Failed to log audit event: {str(e)}",
            error_code="AUDIT_LOGGING_FAILED",
            context=operation_context,
        ) from e


async def log_region_creation(
    user_id: str,
    region_id: str,
    region_snapshot: Dict[str, Any],
    session: Optional[ClientSession] = None,
) -> Dict[str, Any]:
    """
    Log audit trail for region creation.

    Args:
        user_id: ID of user creating the region
        region_id: Unique identifier of the created region
        region_snapshot: Complete region document snapshot
        session: Database session for transaction safety

    Returns:
        Dict containing audit trail information
    """
    return await log_ipam_audit_event(
        user_id=user_id,
        action_type="create",
        resource_type="region",
        resource_id=region_id,
        details={
            "snapshot": region_snapshot,
            "cidr": region_snapshot.get("cidr"),
            "country": region_snapshot.get("country"),
            "region_name": region_snapshot.get("region_name"),
            "x_octet": region_snapshot.get("x_octet"),
            "y_octet": region_snapshot.get("y_octet"),
            "status": region_snapshot.get("status"),
            "owner": region_snapshot.get("owner"),
        },
        ip_address=region_snapshot.get("cidr"),
        session=session,
    )


async def log_host_creation(
    user_id: str,
    host_id: str,
    host_snapshot: Dict[str, Any],
    session: Optional[ClientSession] = None,
) -> Dict[str, Any]:
    """
    Log audit trail for host creation.

    Args:
        user_id: ID of user creating the host
        host_id: Unique identifier of the created host
        host_snapshot: Complete host document snapshot
        session: Database session for transaction safety

    Returns:
        Dict containing audit trail information
    """
    return await log_ipam_audit_event(
        user_id=user_id,
        action_type="create",
        resource_type="host",
        resource_id=host_id,
        details={
            "snapshot": host_snapshot,
            "hostname": host_snapshot.get("hostname"),
            "x_octet": host_snapshot.get("x_octet"),
            "y_octet": host_snapshot.get("y_octet"),
            "z_octet": host_snapshot.get("z_octet"),
            "status": host_snapshot.get("status"),
            "owner": host_snapshot.get("owner"),
        },
        ip_address=host_snapshot.get("ip_address"),
        session=session,
    )


async def log_resource_update(
    user_id: str,
    resource_type: str,
    resource_id: str,
    old_snapshot: Dict[str, Any],
    new_snapshot: Dict[str, Any],
    session: Optional[ClientSession] = None,
) -> Dict[str, Any]:
    """
    Log audit trail for resource updates with field-level change tracking.

    Args:
        user_id: ID of user updating the resource
        resource_type: Type of resource (region or host)
        resource_id: Unique identifier of the resource
        old_snapshot: Resource state before update
        new_snapshot: Resource state after update
        session: Database session for transaction safety

    Returns:
        Dict containing audit trail information
    """
    # Calculate field-level changes
    changes = []
    for field in new_snapshot:
        if field in ["_id", "created_at", "created_by", "user_id"]:
            continue  # Skip immutable fields
        old_value = old_snapshot.get(field)
        new_value = new_snapshot.get(field)
        if old_value != new_value:
            changes.append({"field": field, "old_value": old_value, "new_value": new_value})

    return await log_ipam_audit_event(
        user_id=user_id,
        action_type="update",
        resource_type=resource_type,
        resource_id=resource_id,
        details={
            "snapshot": new_snapshot,
            "changes": changes,
            "cidr": new_snapshot.get("cidr"),
            "country": new_snapshot.get("country"),
            "region_name": new_snapshot.get("region_name"),
            "hostname": new_snapshot.get("hostname"),
            "x_octet": new_snapshot.get("x_octet"),
            "y_octet": new_snapshot.get("y_octet"),
            "z_octet": new_snapshot.get("z_octet"),
            "status": new_snapshot.get("status"),
            "owner": new_snapshot.get("owner"),
        },
        ip_address=new_snapshot.get("ip_address") or new_snapshot.get("cidr"),
        session=session,
    )


async def log_resource_retirement(
    user_id: str,
    resource_type: str,
    resource_id: str,
    resource_snapshot: Dict[str, Any],
    reason: str,
    session: Optional[ClientSession] = None,
) -> Dict[str, Any]:
    """
    Log audit trail for resource retirement (hard delete).

    Args:
        user_id: ID of user retiring the resource
        resource_type: Type of resource (region or host)
        resource_id: Unique identifier of the resource
        resource_snapshot: Complete resource state before deletion
        reason: Reason for retirement
        session: Database session for transaction safety

    Returns:
        Dict containing audit trail information
    """
    return await log_ipam_audit_event(
        user_id=user_id,
        action_type="retire",
        resource_type=resource_type,
        resource_id=resource_id,
        details={
            "snapshot": resource_snapshot,
            "reason": reason,
            "cidr": resource_snapshot.get("cidr"),
            "country": resource_snapshot.get("country"),
            "region_name": resource_snapshot.get("region_name"),
            "hostname": resource_snapshot.get("hostname"),
            "x_octet": resource_snapshot.get("x_octet"),
            "y_octet": resource_snapshot.get("y_octet"),
            "z_octet": resource_snapshot.get("z_octet"),
            "status": resource_snapshot.get("status"),
            "owner": resource_snapshot.get("owner"),
        },
        ip_address=resource_snapshot.get("ip_address") or resource_snapshot.get("cidr"),
        session=session,
    )


async def log_capacity_warning(
    user_id: str,
    resource_type: str,
    identifier: str,
    utilization: float,
    threshold: float,
    capacity: int,
    allocated: int,
) -> Dict[str, Any]:
    """
    Log capacity threshold warning event.

    Args:
        user_id: ID of user whose allocation triggered the warning
        resource_type: Type of resource (country or region)
        identifier: Country name or region ID
        utilization: Current utilization percentage
        threshold: Threshold percentage that was exceeded
        capacity: Total capacity
        allocated: Currently allocated count

    Returns:
        Dict containing audit trail information
    """
    return await log_ipam_audit_event(
        user_id=user_id,
        action_type="capacity_warning",
        resource_type=resource_type,
        resource_id=identifier,
        details={
            "snapshot": {
                "utilization": utilization,
                "threshold": threshold,
                "capacity": capacity,
                "allocated": allocated,
            },
            "country": identifier if resource_type == "country" else None,
        },
    )


async def log_quota_exceeded(
    user_id: str,
    quota_type: str,
    limit: int,
    current: int,
    attempted_action: str,
) -> Dict[str, Any]:
    """
    Log quota exceeded event.

    Args:
        user_id: ID of user who exceeded quota
        quota_type: Type of quota (region or host)
        limit: Quota limit
        current: Current allocation count
        attempted_action: Action that was attempted

    Returns:
        Dict containing audit trail information
    """
    return await log_ipam_audit_event(
        user_id=user_id,
        action_type="quota_exceeded",
        resource_type=quota_type,
        resource_id=user_id,
        details={
            "snapshot": {"limit": limit, "current": current, "attempted_action": attempted_action},
            "result": "failure",
        },
    )
