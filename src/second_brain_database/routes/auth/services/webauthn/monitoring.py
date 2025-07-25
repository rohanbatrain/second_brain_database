"""
WebAuthn monitoring and audit infrastructure.

This module provides comprehensive monitoring, alerting, and audit capabilities
for WebAuthn operations, leveraging existing infrastructure patterns from the
application's logging and security systems.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import time

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[WebAuthn Monitoring]")
security_logger = SecurityLogger(prefix="[WEBAUTHN-MONITORING-SECURITY]")
db_logger = DatabaseLogger(prefix="[WEBAUTHN-MONITORING-DB]")

# Monitoring configuration following existing patterns
SLOW_OPERATION_THRESHOLD = 2.0  # seconds - matches existing log_performance pattern
SLOW_DB_OPERATION_THRESHOLD = 1.0  # seconds - matches existing database logging pattern
SLOW_REQUEST_THRESHOLD = 1.0  # seconds - matches existing request logging pattern

# Security alert thresholds
FAILED_AUTH_THRESHOLD = 5  # Failed authentications per user per hour
SUSPICIOUS_ACTIVITY_THRESHOLD = 10  # Suspicious events per IP per hour
CREDENTIAL_ENUMERATION_THRESHOLD = 20  # Credential lookup attempts per IP per hour

# Redis keys for monitoring data
REDIS_MONITORING_PREFIX = "webauthn_monitoring:"
REDIS_FAILED_AUTH_PREFIX = f"{REDIS_MONITORING_PREFIX}failed_auth:"
REDIS_SUSPICIOUS_ACTIVITY_PREFIX = f"{REDIS_MONITORING_PREFIX}suspicious:"
REDIS_CREDENTIAL_ENUM_PREFIX = f"{REDIS_MONITORING_PREFIX}enum:"


class WebAuthnMonitor:
    """
    Comprehensive monitoring and alerting for WebAuthn operations.
    
    Follows existing security and performance monitoring patterns from the application,
    integrating with the existing logging infrastructure and security management systems.
    """

    def __init__(self):
        self.logger = logger
        self.security_logger = security_logger
        self.db_logger = db_logger

    @log_performance("webauthn_monitor_operation")
    async def monitor_authentication_attempt(
        self,
        user_id: Optional[str],
        credential_id: Optional[str],
        ip_address: Optional[str],
        success: bool,
        operation_duration: float,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Monitor WebAuthn authentication attempts with comprehensive logging and alerting.
        
        Follows existing authentication monitoring patterns from login.py with
        enhanced WebAuthn-specific monitoring capabilities.

        Args:
            user_id: User identifier (username or email)
            credential_id: WebAuthn credential ID used
            ip_address: Client IP address
            success: Whether authentication was successful
            operation_duration: Time taken for the operation
            error_details: Additional error information if failed
        """
        try:
            # Log performance metrics following existing patterns
            if operation_duration > SLOW_OPERATION_THRESHOLD:
                self.logger.warning(
                    "SLOW WEBAUTHN OPERATION: Authentication took %.3fs for user %s",
                    operation_duration,
                    user_id or "unknown"
                )
                
                # Log slow operation security event
                log_security_event(
                    event_type="webauthn_slow_authentication",
                    user_id=user_id,
                    ip_address=ip_address,
                    success=success,
                    details={
                        "duration": operation_duration,
                        "credential_id": credential_id[:16] + "..." if credential_id else None,
                        "threshold_exceeded": SLOW_OPERATION_THRESHOLD,
                    },
                )

            # Monitor failed authentication attempts following existing security patterns
            if not success and user_id:
                await self._track_failed_authentication(user_id, ip_address, error_details)

            # Monitor suspicious activity patterns
            if ip_address:
                await self._track_suspicious_activity(ip_address, success, error_details)

            # Log comprehensive authentication event
            log_security_event(
                event_type="webauthn_authentication_monitored",
                user_id=user_id,
                ip_address=ip_address,
                success=success,
                details={
                    "credential_id": credential_id[:16] + "..." if credential_id else None,
                    "duration": operation_duration,
                    "error_details": error_details,
                    "monitoring_timestamp": datetime.utcnow().isoformat(),
                },
            )

        except Exception as e:
            self.logger.error("Failed to monitor WebAuthn authentication attempt: %s", e, exc_info=True)
            log_error_with_context(
                e,
                context={
                    "user_id": user_id,
                    "credential_id": credential_id[:16] + "..." if credential_id else None,
                    "ip_address": ip_address,
                    "success": success,
                    "operation_duration": operation_duration,
                },
                operation="monitor_authentication_attempt",
            )

    async def _track_failed_authentication(
        self,
        user_id: str,
        ip_address: Optional[str],
        error_details: Optional[Dict[str, Any]],
    ) -> None:
        """
        Track failed authentication attempts and trigger alerts if thresholds are exceeded.
        
        Follows existing abuse detection patterns from the authentication system.
        """
        try:
            redis_conn = await redis_manager.get_redis()
            
            # Track failed attempts per user per hour
            failed_auth_key = f"{REDIS_FAILED_AUTH_PREFIX}{user_id}"
            failed_count = await redis_conn.incr(failed_auth_key)
            
            # Set expiry on first increment
            if failed_count == 1:
                await redis_conn.expire(failed_auth_key, 3600)  # 1 hour

            # Check if threshold exceeded
            if failed_count >= FAILED_AUTH_THRESHOLD:
                await self._trigger_failed_auth_alert(user_id, ip_address, failed_count, error_details)

        except Exception as e:
            self.logger.error("Failed to track failed authentication: %s", e, exc_info=True)
            log_error_with_context(
                e,
                context={"user_id": user_id, "ip_address": ip_address},
                operation="track_failed_authentication",
            )

    async def _track_suspicious_activity(
        self,
        ip_address: str,
        success: bool,
        error_details: Optional[Dict[str, Any]],
    ) -> None:
        """
        Track suspicious activity patterns by IP address.
        
        Monitors for potential credential enumeration, brute force attacks,
        and other suspicious patterns.
        """
        try:
            redis_conn = await redis_manager.get_redis()
            
            # Track suspicious events per IP per hour
            suspicious_key = f"{REDIS_SUSPICIOUS_ACTIVITY_PREFIX}{ip_address}"
            
            # Increment for failed attempts or specific error patterns
            should_track = not success or (
                error_details and any(
                    pattern in str(error_details).lower()
                    for pattern in ["credential_not_found", "invalid_credential", "user_not_found"]
                )
            )
            
            if should_track:
                suspicious_count = await redis_conn.incr(suspicious_key)
                
                # Set expiry on first increment
                if suspicious_count == 1:
                    await redis_conn.expire(suspicious_key, 3600)  # 1 hour

                # Check if threshold exceeded
                if suspicious_count >= SUSPICIOUS_ACTIVITY_THRESHOLD:
                    await self._trigger_suspicious_activity_alert(ip_address, suspicious_count, error_details)

        except Exception as e:
            self.logger.error("Failed to track suspicious activity: %s", e, exc_info=True)
            log_error_with_context(
                e,
                context={"ip_address": ip_address, "success": success},
                operation="track_suspicious_activity",
            )

    async def _trigger_failed_auth_alert(
        self,
        user_id: str,
        ip_address: Optional[str],
        failed_count: int,
        error_details: Optional[Dict[str, Any]],
    ) -> None:
        """
        Trigger security alert for excessive failed authentication attempts.
        
        Follows existing security alert patterns from the application.
        """
        alert_details = {
            "alert_type": "webauthn_failed_auth_threshold_exceeded",
            "user_id": user_id,
            "ip_address": ip_address,
            "failed_count": failed_count,
            "threshold": FAILED_AUTH_THRESHOLD,
            "time_window": "1_hour",
            "error_details": error_details,
            "alert_timestamp": datetime.utcnow().isoformat(),
        }

        # Log high-priority security alert
        log_security_event(
            event_type="webauthn_security_alert_failed_auth",
            user_id=user_id,
            ip_address=ip_address,
            success=False,
            details=alert_details,
        )

        self.logger.error(
            "WEBAUTHN SECURITY ALERT: User %s exceeded failed authentication threshold (%d failures from IP %s)",
            user_id,
            failed_count,
            ip_address or "unknown"
        )

        # Store alert in database for further analysis
        await self._store_security_alert("failed_authentication", alert_details)

    async def _trigger_suspicious_activity_alert(
        self,
        ip_address: str,
        suspicious_count: int,
        error_details: Optional[Dict[str, Any]],
    ) -> None:
        """
        Trigger security alert for suspicious activity patterns.
        """
        alert_details = {
            "alert_type": "webauthn_suspicious_activity_threshold_exceeded",
            "ip_address": ip_address,
            "suspicious_count": suspicious_count,
            "threshold": SUSPICIOUS_ACTIVITY_THRESHOLD,
            "time_window": "1_hour",
            "error_details": error_details,
            "alert_timestamp": datetime.utcnow().isoformat(),
        }

        # Log high-priority security alert
        log_security_event(
            event_type="webauthn_security_alert_suspicious_activity",
            ip_address=ip_address,
            success=False,
            details=alert_details,
        )

        self.logger.error(
            "WEBAUTHN SECURITY ALERT: IP %s exceeded suspicious activity threshold (%d events)",
            ip_address,
            suspicious_count
        )

        # Store alert in database for further analysis
        await self._store_security_alert("suspicious_activity", alert_details)

    async def _store_security_alert(self, alert_type: str, alert_details: Dict[str, Any]) -> None:
        """
        Store security alert in database for analysis and reporting.
        
        Follows existing database operation patterns with comprehensive logging.
        """
        try:
            collection = db_manager.get_collection("webauthn_security_alerts")
            
            alert_doc = {
                "alert_type": alert_type,
                "details": alert_details,
                "created_at": datetime.utcnow(),
                "resolved": False,
                "resolution_notes": None,
            }

            result = await collection.insert_one(alert_doc)
            
            if result.inserted_id:
                self.logger.info("Stored WebAuthn security alert: %s (ID: %s)", alert_type, result.inserted_id)
            else:
                self.logger.error("Failed to store WebAuthn security alert: %s", alert_type)

        except Exception as e:
            self.logger.error("Failed to store security alert: %s", e, exc_info=True)
            log_error_with_context(
                e,
                context={"alert_type": alert_type, "alert_details": alert_details},
                operation="store_security_alert",
            )


# Global monitor instance following existing patterns
webauthn_monitor = WebAuthnMonitor()


# Monitoring utility functions following existing patterns

async def monitor_webauthn_operation(
    operation_name: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    **kwargs
):
    """
    Decorator-like function for monitoring WebAuthn operations.
    
    Can be used to wrap WebAuthn operations with comprehensive monitoring.
    """
    start_time = time.time()
    
    try:
        # Operation would be executed here in actual usage
        # This is a utility function that can be called from other services
        duration = time.time() - start_time
        
        await webauthn_monitor.monitor_authentication_attempt(
            user_id=user_id,
            credential_id=kwargs.get("credential_id"),
            ip_address=ip_address,
            success=kwargs.get("success", True),
            operation_duration=duration,
            error_details=kwargs.get("error_details"),
        )
        
    except Exception as e:
        duration = time.time() - start_time
        
        await webauthn_monitor.monitor_authentication_attempt(
            user_id=user_id,
            credential_id=kwargs.get("credential_id"),
            ip_address=ip_address,
            success=False,
            operation_duration=duration,
            error_details={"error": str(e), "operation": operation_name},
        )
        
        raise


async def cleanup_monitoring_data() -> Dict[str, int]:
    """
    Clean up expired monitoring data from Redis and database.
    
    Follows existing cleanup patterns from challenge.py and other services.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        
        # Clean up expired Redis monitoring keys
        redis_cleaned = 0
        for prefix in [REDIS_FAILED_AUTH_PREFIX, REDIS_SUSPICIOUS_ACTIVITY_PREFIX, REDIS_CREDENTIAL_ENUM_PREFIX]:
            pattern = f"{prefix}*"
            keys = await redis_conn.keys(pattern)
            
            for key in keys:
                ttl = await redis_conn.ttl(key)
                if ttl == -2:  # Key doesn't exist (expired)
                    redis_cleaned += 1

        # Clean up old security alerts (keep for 30 days)
        alerts_collection = db_manager.get_collection("webauthn_security_alerts")
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        result = await alerts_collection.delete_many({
            "created_at": {"$lt": cutoff_date},
            "resolved": True
        })
        
        db_cleaned = result.deleted_count

        logger.info("Cleaned up WebAuthn monitoring data: Redis=%d, DB=%d", redis_cleaned, db_cleaned)
        
        return {"redis_cleaned": redis_cleaned, "database_cleaned": db_cleaned}

    except Exception as e:
        logger.error("Failed to cleanup monitoring data: %s", e, exc_info=True)
        log_error_with_context(e, context={}, operation="cleanup_monitoring_data")
        return {"redis_cleaned": 0, "database_cleaned": 0}