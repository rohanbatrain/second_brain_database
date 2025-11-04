"""
Permanent token audit logging service.

This module provides comprehensive audit logging for all permanent token operations
including creation, validation, revocation, and security events. All logs include
IP addresses, user agents, and detailed context for security monitoring.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
import json
from typing import Any, Dict, List, Optional

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Permanent Token Audit]")
security_logger = SecurityLogger(prefix="[PERM-TOKEN-AUDIT-SECURITY]")
db_logger = DatabaseLogger(prefix="[PERM-TOKEN-AUDIT-DB]")

# Audit log collection name
AUDIT_COLLECTION = "permanent_token_audit_logs"


class AuditEventType(Enum):
    """Enumeration of audit event types for permanent tokens."""

    TOKEN_CREATED = "token_created"
    TOKEN_VALIDATED = "token_validated"
    TOKEN_REVOKED = "token_revoked"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_BLACKLISTED = "token_blacklisted"
    CACHE_HIT = "cache_hit"
    CACHE_MISS = "cache_miss"
    VALIDATION_FAILED = "validation_failed"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    BULK_REVOCATION = "bulk_revocation"
    CACHE_INVALIDATED = "cache_invalidated"


class AuditSeverity(Enum):
    """Audit event severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents a single audit event for permanent tokens."""

    event_type: str
    severity: str
    user_id: Optional[str]
    username: Optional[str]
    token_id: Optional[str]
    token_hash_prefix: Optional[str]  # First 8 chars for debugging
    ip_address: Optional[str]
    user_agent: Optional[str]
    timestamp: datetime
    details: Dict[str, Any]
    success: bool
    error_message: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None


class PermanentTokenAuditLogger:
    """
    Audit logger for permanent token operations.

    Provides comprehensive logging of all token-related activities
    with security monitoring and suspicious activity detection.
    """

    def __init__(self):
        self.suspicious_patterns = {
            "rapid_token_creation": {"threshold": 10, "window_minutes": 5},
            "failed_validations": {"threshold": 20, "window_minutes": 10},
            "multiple_ip_usage": {"threshold": 5, "window_minutes": 60},
            "bulk_operations": {"threshold": 50, "window_minutes": 30},
        }

    @log_performance("log_audit_event")
    async def log_event(
        self,
        event_type: AuditEventType,
        severity: AuditSeverity = AuditSeverity.INFO,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        token_id: Optional[str] = None,
        token_hash: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        """
        Log an audit event for permanent token operations.

        Args:
            event_type: Type of event being logged
            severity: Severity level of the event
            user_id: MongoDB ObjectId of the user
            username: Username of the user
            token_id: Unique token identifier
            token_hash: SHA-256 hash of the token (will be truncated)
            ip_address: Client IP address
            user_agent: Client user agent string
            details: Additional event details
            success: Whether the operation was successful
            error_message: Error message if operation failed
            session_id: Session identifier if available
            request_id: Request identifier for tracing
        """
        logger.debug(
            "Logging audit event: %s (severity: %s) for user: %s from IP: %s",
            event_type.value,
            severity.value,
            username or "unknown",
            ip_address or "unknown",
        )

        try:
            audit_event = AuditEvent(
                event_type=event_type.value,
                severity=severity.value,
                user_id=user_id,
                username=username,
                token_id=token_id,
                token_hash_prefix=token_hash[:8] if token_hash else None,
                ip_address=ip_address,
                user_agent=user_agent,
                timestamp=datetime.utcnow(),
                details=details or {},
                success=success,
                error_message=error_message,
                session_id=session_id,
                request_id=request_id,
            )

            # Store in database
            collection = db_manager.get_collection(AUDIT_COLLECTION)
            result = await collection.insert_one(asdict(audit_event))

            log_database_operation(
                operation="insert_audit_event",
                collection=AUDIT_COLLECTION,
                query={},
                result={
                    "inserted_id": str(result.inserted_id),
                    "event_type": event_type.value,
                    "severity": severity.value,
                    "user_id": user_id,
                    "success": success,
                },
            )

            # Log to application logger based on severity
            log_message = f"[{event_type.value}] User: {username or 'unknown'}, Token: {token_id or 'unknown'}, IP: {ip_address or 'unknown'}"

            if severity == AuditSeverity.CRITICAL:
                logger.critical(log_message)
            elif severity == AuditSeverity.ERROR:
                logger.error(log_message)
            elif severity == AuditSeverity.WARNING:
                logger.warning(log_message)
            else:
                logger.info(log_message)

            # Log security event for high-severity audit events
            if severity in [AuditSeverity.ERROR, AuditSeverity.CRITICAL]:
                log_security_event(
                    event_type=f"audit_{event_type.value}",
                    user_id=username or user_id,
                    ip_address=ip_address,
                    success=success,
                    details={
                        "audit_severity": severity.value,
                        "token_id": token_id,
                        "error_message": error_message,
                        "audit_details": details or {},
                    },
                )

            # Check for suspicious activity patterns
            await self._check_suspicious_activity(audit_event)

            logger.info("Successfully logged audit event: %s for user: %s", event_type.value, username or "unknown")

        except Exception as e:
            logger.error(
                "Failed to log audit event %s for user %s: %s",
                event_type.value,
                username or "unknown",
                e,
                exc_info=True,
            )
            log_error_with_context(
                e,
                context={
                    "event_type": event_type.value,
                    "severity": severity.value,
                    "user_id": user_id,
                    "username": username,
                    "token_id": token_id,
                    "ip_address": ip_address,
                    "success": success,
                },
                operation="log_audit_event",
            )

    async def log_token_creation(
        self,
        user_id: str,
        username: str,
        token_id: str,
        token_hash: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        description: Optional[str] = None,
    ):
        """Log permanent token creation event."""
        await self.log_event(
            event_type=AuditEventType.TOKEN_CREATED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            username=username,
            token_id=token_id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"description": description, "creation_method": "api_endpoint"},
        )

    async def log_token_validation(
        self,
        user_id: str,
        username: str,
        token_id: str,
        token_hash: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        cache_hit: bool = False,
        response_time_ms: Optional[float] = None,
    ):
        """Log permanent token validation event."""
        await self.log_event(
            event_type=AuditEventType.TOKEN_VALIDATED,
            severity=AuditSeverity.INFO,
            user_id=user_id,
            username=username,
            token_id=token_id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            details={
                "cache_hit": cache_hit,
                "response_time_ms": response_time_ms,
                "validation_method": "cache_first" if cache_hit else "database_fallback",
            },
        )

    async def log_token_revocation(
        self,
        user_id: str,
        username: str,
        token_id: str,
        token_hash: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        revocation_reason: Optional[str] = None,
    ):
        """Log permanent token revocation event."""
        await self.log_event(
            event_type=AuditEventType.TOKEN_REVOKED,
            severity=AuditSeverity.WARNING,
            user_id=user_id,
            username=username,
            token_id=token_id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"revocation_reason": revocation_reason or "user_requested", "revocation_method": "api_endpoint"},
        )

    async def log_validation_failure(
        self,
        token_hash: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        failure_reason: str = "invalid_token",
        error_message: Optional[str] = None,
    ):
        """Log permanent token validation failure."""
        await self.log_event(
            event_type=AuditEventType.VALIDATION_FAILED,
            severity=AuditSeverity.WARNING,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"failure_reason": failure_reason, "attempted_validation": True},
            success=False,
            error_message=error_message,
        )

    async def log_suspicious_activity(
        self,
        event_description: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """Log suspicious activity related to permanent tokens."""
        await self.log_event(
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
            severity=AuditSeverity.CRITICAL,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"description": event_description, "requires_investigation": True, **(details or {})},
        )

    async def log_bulk_revocation(
        self,
        user_id: str,
        username: str,
        revoked_count: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        reason: str = "security_incident",
    ):
        """Log bulk token revocation event."""
        await self.log_event(
            event_type=AuditEventType.BULK_REVOCATION,
            severity=AuditSeverity.ERROR,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"revoked_count": revoked_count, "reason": reason, "bulk_operation": True},
        )

    async def _check_suspicious_activity(self, event: AuditEvent):
        """
        Check for suspicious activity patterns and log alerts.

        Args:
            event: The audit event to analyze
        """
        try:
            # Check for rapid token creation
            if event.event_type == AuditEventType.TOKEN_CREATED.value:
                await self._check_rapid_token_creation(event)

            # Check for excessive failed validations
            elif event.event_type == AuditEventType.VALIDATION_FAILED.value:
                await self._check_excessive_failures(event)

            # Check for multiple IP usage of same token
            elif event.event_type == AuditEventType.TOKEN_VALIDATED.value:
                await self._check_multiple_ip_usage(event)

        except Exception as e:
            logger.error("Error checking suspicious activity: %s", e)

    async def _check_rapid_token_creation(self, event: AuditEvent):
        """Check for rapid token creation by the same user."""
        if not event.user_id:
            return

        pattern = self.suspicious_patterns["rapid_token_creation"]
        cutoff_time = datetime.utcnow() - timedelta(minutes=pattern["window_minutes"])

        collection = db_manager.get_collection(AUDIT_COLLECTION)
        count = await collection.count_documents(
            {
                "event_type": AuditEventType.TOKEN_CREATED.value,
                "user_id": event.user_id,
                "timestamp": {"$gte": cutoff_time},
            }
        )

        if count >= pattern["threshold"]:
            await self.log_suspicious_activity(
                f"Rapid token creation detected: {count} tokens in {pattern['window_minutes']} minutes",
                user_id=event.user_id,
                username=event.username,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                details={
                    "pattern": "rapid_token_creation",
                    "count": count,
                    "threshold": pattern["threshold"],
                    "window_minutes": pattern["window_minutes"],
                },
            )

    async def _check_excessive_failures(self, event: AuditEvent):
        """Check for excessive validation failures from the same IP."""
        if not event.ip_address:
            return

        pattern = self.suspicious_patterns["failed_validations"]
        cutoff_time = datetime.utcnow() - timedelta(minutes=pattern["window_minutes"])

        collection = db_manager.get_collection(AUDIT_COLLECTION)
        count = await collection.count_documents(
            {
                "event_type": AuditEventType.VALIDATION_FAILED.value,
                "ip_address": event.ip_address,
                "timestamp": {"$gte": cutoff_time},
            }
        )

        if count >= pattern["threshold"]:
            await self.log_suspicious_activity(
                f"Excessive validation failures detected: {count} failures in {pattern['window_minutes']} minutes",
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                details={
                    "pattern": "excessive_failures",
                    "count": count,
                    "threshold": pattern["threshold"],
                    "window_minutes": pattern["window_minutes"],
                },
            )

    async def _check_multiple_ip_usage(self, event: AuditEvent):
        """Check for the same token being used from multiple IPs."""
        if not event.token_id or not event.ip_address:
            return

        pattern = self.suspicious_patterns["multiple_ip_usage"]
        cutoff_time = datetime.utcnow() - timedelta(minutes=pattern["window_minutes"])

        collection = db_manager.get_collection(AUDIT_COLLECTION)
        pipeline = [
            {
                "$match": {
                    "event_type": AuditEventType.TOKEN_VALIDATED.value,
                    "token_id": event.token_id,
                    "timestamp": {"$gte": cutoff_time},
                }
            },
            {"$group": {"_id": "$ip_address", "count": {"$sum": 1}}},
        ]

        cursor = collection.aggregate(pipeline)
        unique_ips = await cursor.to_list(length=None)

        if len(unique_ips) >= pattern["threshold"]:
            await self.log_suspicious_activity(
                f"Token used from multiple IPs: {len(unique_ips)} different IPs in {pattern['window_minutes']} minutes",
                user_id=event.user_id,
                username=event.username,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                details={
                    "pattern": "multiple_ip_usage",
                    "unique_ip_count": len(unique_ips),
                    "threshold": pattern["threshold"],
                    "window_minutes": pattern["window_minutes"],
                    "ip_addresses": [ip["_id"] for ip in unique_ips],
                },
            )

    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        severity: Optional[AuditSeverity] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit logs with optional filtering.

        Args:
            user_id: Filter by user ID
            event_type: Filter by event type
            severity: Filter by severity level
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of logs to return

        Returns:
            List of audit log entries
        """
        try:
            collection = db_manager.get_collection(AUDIT_COLLECTION)

            # Build query
            query = {}
            if user_id:
                query["user_id"] = user_id
            if event_type:
                query["event_type"] = event_type.value
            if severity:
                query["severity"] = severity.value
            if start_time or end_time:
                time_query = {}
                if start_time:
                    time_query["$gte"] = start_time
                if end_time:
                    time_query["$lte"] = end_time
                query["timestamp"] = time_query

            # Execute query
            cursor = collection.find(query).sort("timestamp", -1).limit(limit)
            logs = await cursor.to_list(length=limit)

            # Remove MongoDB ObjectId for JSON serialization
            for log in logs:
                log.pop("_id", None)

            return logs

        except Exception as e:
            logger.error("Error retrieving audit logs: %s", e)
            return []

    async def get_security_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get security summary for the specified time period.

        Args:
            hours: Number of hours to analyze

        Returns:
            Security summary with statistics and alerts
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            collection = db_manager.get_collection(AUDIT_COLLECTION)

            # Aggregate statistics
            pipeline = [
                {"$match": {"timestamp": {"$gte": cutoff_time}}},
                {"$group": {"_id": {"event_type": "$event_type", "severity": "$severity"}, "count": {"$sum": 1}}},
            ]

            cursor = collection.aggregate(pipeline)
            stats = await cursor.to_list(length=None)

            # Process statistics
            summary = {
                "time_period_hours": hours,
                "timestamp": datetime.utcnow().isoformat(),
                "event_counts": {},
                "severity_counts": {},
                "total_events": 0,
                "security_alerts": 0,
                "failed_operations": 0,
            }

            for stat in stats:
                event_type = stat["_id"]["event_type"]
                severity = stat["_id"]["severity"]
                count = stat["count"]

                summary["event_counts"][event_type] = summary["event_counts"].get(event_type, 0) + count
                summary["severity_counts"][severity] = summary["severity_counts"].get(severity, 0) + count
                summary["total_events"] += count

                if severity in ["error", "critical"]:
                    summary["security_alerts"] += count

                if event_type in ["validation_failed", "unauthorized_access"]:
                    summary["failed_operations"] += count

            return summary

        except Exception as e:
            logger.error("Error generating security summary: %s", e)
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}


# Global audit logger instance
audit_logger = PermanentTokenAuditLogger()


# Convenience functions for common audit operations
async def log_token_created(
    user_id: str,
    username: str,
    token_id: str,
    token_hash: str,
    ip_address: str = None,
    user_agent: str = None,
    description: str = None,
):
    """Log token creation event."""
    await audit_logger.log_token_creation(user_id, username, token_id, token_hash, ip_address, user_agent, description)


async def log_token_validated(
    user_id: str,
    username: str,
    token_id: str,
    token_hash: str,
    ip_address: str = None,
    user_agent: str = None,
    cache_hit: bool = False,
    response_time_ms: float = None,
):
    """Log token validation event."""
    await audit_logger.log_token_validation(
        user_id, username, token_id, token_hash, ip_address, user_agent, cache_hit, response_time_ms
    )


async def log_token_revoked(
    user_id: str,
    username: str,
    token_id: str,
    token_hash: str,
    ip_address: str = None,
    user_agent: str = None,
    reason: str = None,
):
    """Log token revocation event."""
    await audit_logger.log_token_revocation(user_id, username, token_id, token_hash, ip_address, user_agent, reason)


async def log_validation_failed(
    token_hash: str,
    ip_address: str = None,
    user_agent: str = None,
    failure_reason: str = "invalid_token",
    error_message: str = None,
):
    """Log validation failure event."""
    await audit_logger.log_validation_failure(token_hash, ip_address, user_agent, failure_reason, error_message)


async def log_suspicious_activity(
    description: str,
    user_id: str = None,
    username: str = None,
    ip_address: str = None,
    user_agent: str = None,
    details: Dict[str, Any] = None,
):
    """Log suspicious activity event."""
    await audit_logger.log_suspicious_activity(description, user_id, username, ip_address, user_agent, details)
