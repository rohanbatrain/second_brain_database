"""
Family Security Monitoring and Metrics Collection.

This module provides comprehensive monitoring, metrics collection, and alerting
for family management security operations. It integrates with the existing
logging infrastructure and provides real-time security monitoring capabilities.

Features:
    - Real-time security event monitoring
    - Metrics collection for Prometheus integration
    - Automated alerting for security violations
    - Performance monitoring for family operations
    - Audit trail management and retention
    - Security dashboard data aggregation

Monitoring Categories:
    - Authentication and authorization events
    - Rate limiting violations and patterns
    - 2FA enforcement and bypass attempts
    - Temporary token usage and abuse
    - IP/User Agent lockdown violations
    - Admin privilege escalations and changes
"""

import asyncio
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import json
from typing import Any, Dict, List, Optional, Tuple

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import log_security_event

logger = get_logger(prefix="[FamilySecurityMonitoring]")

# Monitoring configuration
SECURITY_METRICS_RETENTION_HOURS = 24
ALERT_THRESHOLD_VIOLATIONS_PER_HOUR = 10
ALERT_THRESHOLD_FAILED_2FA_PER_HOUR = 5
ALERT_THRESHOLD_TEMP_TOKEN_ABUSE_PER_HOUR = 20
PERFORMANCE_METRICS_WINDOW_MINUTES = 15
AUDIT_LOG_RETENTION_DAYS = 90

# Security event types for monitoring
MONITORED_SECURITY_EVENTS = {
    "authentication_failure",
    "authorization_failure",
    "rate_limit_exceeded",
    "ip_lockdown_violation",
    "user_agent_lockdown_violation",
    "2fa_required_but_not_enabled",
    "2fa_verification_failed",
    "temp_token_abuse",
    "admin_privilege_escalation",
    "suspicious_family_activity",
}

# Performance metrics to track
PERFORMANCE_METRICS = {
    "family_operation_duration",
    "security_validation_duration",
    "database_query_duration",
    "redis_operation_duration",
    "email_notification_duration",
}


class FamilySecurityMonitor:
    """
    Comprehensive security monitoring system for family operations.

    Provides real-time monitoring, metrics collection, alerting, and
    audit trail management for all family security events.
    """

    def __init__(self):
        self.logger = logger
        self.redis_manager = redis_manager

        # In-memory metrics storage for real-time monitoring
        self.security_events = deque(maxlen=1000)
        self.performance_metrics = defaultdict(lambda: deque(maxlen=100))
        self.alert_counters = defaultdict(int)

        # Monitoring state
        self.monitoring_active = True
        self.last_cleanup = datetime.now(timezone.utc)

        self.logger.info("Family security monitoring initialized")

    async def record_security_event(
        self,
        event_type: str,
        user_id: str,
        details: Dict[str, Any],
        severity: str = "info",
        ip_address: str = None,
        success: bool = True,
    ) -> None:
        """
        Record a security event for monitoring and analysis.

        Args:
            event_type: Type of security event
            user_id: ID of the user involved
            details: Additional event details
            severity: Event severity (info, warning, error, critical)
            ip_address: IP address of the request
            success: Whether the operation was successful
        """
        try:
            timestamp = datetime.now(timezone.utc)

            # Create comprehensive security event record
            security_event = {
                "event_id": f"fam_sec_{timestamp.timestamp()}_{user_id}",
                "event_type": event_type,
                "user_id": user_id,
                "timestamp": timestamp,
                "severity": severity,
                "ip_address": ip_address,
                "success": success,
                "details": details,
                "source": "family_security_monitor",
            }

            # Store in memory for real-time monitoring
            self.security_events.append(security_event)

            # Store in Redis for short-term analysis
            await self._store_event_in_redis(security_event)

            # Store in database for long-term retention
            await self._store_event_in_database(security_event)

            # Check for alert conditions
            await self._check_alert_conditions(security_event)

            # Log using standard security event logging
            log_security_event(
                event_type=f"family_{event_type}",
                user_id=user_id,
                ip_address=ip_address,
                success=success,
                details=details,
            )

            self.logger.debug(
                "Security event recorded: %s for user %s (severity: %s)",
                event_type,
                user_id,
                severity,
                extra={
                    "event_id": security_event["event_id"],
                    "event_type": event_type,
                    "user_id": user_id,
                    "severity": severity,
                    "success": success,
                },
            )

        except Exception as e:
            self.logger.error(
                "Failed to record security event: %s",
                str(e),
                exc_info=True,
                extra={"event_type": event_type, "user_id": user_id, "details": details},
            )

    async def record_performance_metric(
        self,
        metric_name: str,
        value: float,
        operation: str = None,
        user_id: str = None,
        additional_tags: Dict[str, str] = None,
    ) -> None:
        """
        Record a performance metric for monitoring.

        Args:
            metric_name: Name of the metric
            value: Metric value (usually duration in seconds)
            operation: Operation being measured
            user_id: User ID associated with the metric
            additional_tags: Additional metric tags
        """
        try:
            timestamp = datetime.now(timezone.utc)

            metric_record = {
                "metric_name": metric_name,
                "value": value,
                "timestamp": timestamp,
                "operation": operation,
                "user_id": user_id,
                "tags": additional_tags or {},
            }

            # Store in memory for real-time monitoring
            self.performance_metrics[metric_name].append(metric_record)

            # Store in Redis for short-term analysis
            await self._store_metric_in_redis(metric_record)

            self.logger.debug("Performance metric recorded: %s = %f for operation %s", metric_name, value, operation)

        except Exception as e:
            self.logger.error(
                "Failed to record performance metric: %s",
                str(e),
                exc_info=True,
                extra={"metric_name": metric_name, "value": value, "operation": operation},
            )

    async def get_security_dashboard_data(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Get aggregated security data for dashboard display.

        Args:
            time_window_hours: Time window for data aggregation

        Returns:
            Dict containing dashboard data
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

            # Get recent security events
            recent_events = [event for event in self.security_events if event["timestamp"] > cutoff_time]

            # Aggregate security metrics
            event_counts = defaultdict(int)
            severity_counts = defaultdict(int)
            user_activity = defaultdict(int)
            ip_activity = defaultdict(int)

            for event in recent_events:
                event_counts[event["event_type"]] += 1
                severity_counts[event["severity"]] += 1
                user_activity[event["user_id"]] += 1
                if event.get("ip_address"):
                    ip_activity[event["ip_address"]] += 1

            # Get performance metrics summary
            performance_summary = {}
            for metric_name, metrics in self.performance_metrics.items():
                recent_metrics = [m for m in metrics if m["timestamp"] > cutoff_time]
                if recent_metrics:
                    values = [m["value"] for m in recent_metrics]
                    performance_summary[metric_name] = {
                        "count": len(values),
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                    }

            # Get alert status
            active_alerts = await self._get_active_alerts()

            dashboard_data = {
                "time_window_hours": time_window_hours,
                "generated_at": datetime.now(timezone.utc),
                "total_events": len(recent_events),
                "event_counts": dict(event_counts),
                "severity_counts": dict(severity_counts),
                "top_users": dict(sorted(user_activity.items(), key=lambda x: x[1], reverse=True)[:10]),
                "top_ips": dict(sorted(ip_activity.items(), key=lambda x: x[1], reverse=True)[:10]),
                "performance_summary": performance_summary,
                "active_alerts": active_alerts,
                "monitoring_status": {
                    "active": self.monitoring_active,
                    "last_cleanup": self.last_cleanup,
                    "events_in_memory": len(self.security_events),
                    "metrics_tracked": len(self.performance_metrics),
                },
            }

            self.logger.debug(
                "Security dashboard data generated: %d events, %d alerts", len(recent_events), len(active_alerts)
            )

            return dashboard_data

        except Exception as e:
            self.logger.error("Failed to generate security dashboard data: %s", str(e), exc_info=True)
            return {"error": "Failed to generate dashboard data", "generated_at": datetime.now(timezone.utc)}

    async def get_user_security_summary(self, user_id: str, time_window_hours: int = 24) -> Dict[str, Any]:
        """
        Get security summary for a specific user.

        Args:
            user_id: ID of the user
            time_window_hours: Time window for data aggregation

        Returns:
            Dict containing user security summary
        """
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_window_hours)

            # Get user's security events
            user_events = [
                event
                for event in self.security_events
                if event["user_id"] == user_id and event["timestamp"] > cutoff_time
            ]

            # Aggregate user metrics
            event_types = defaultdict(int)
            severity_counts = defaultdict(int)
            success_rate = {"success": 0, "failure": 0}
            ip_addresses = set()

            for event in user_events:
                event_types[event["event_type"]] += 1
                severity_counts[event["severity"]] += 1
                if event["success"]:
                    success_rate["success"] += 1
                else:
                    success_rate["failure"] += 1
                if event.get("ip_address"):
                    ip_addresses.add(event["ip_address"])

            # Calculate success rate percentage
            total_events = success_rate["success"] + success_rate["failure"]
            success_percentage = (success_rate["success"] / total_events * 100) if total_events > 0 else 100

            # Get recent alerts for user
            user_alerts = await self._get_user_alerts(user_id)

            user_summary = {
                "user_id": user_id,
                "time_window_hours": time_window_hours,
                "generated_at": datetime.now(timezone.utc),
                "total_events": len(user_events),
                "event_types": dict(event_types),
                "severity_counts": dict(severity_counts),
                "success_rate": {
                    "percentage": round(success_percentage, 2),
                    "successful": success_rate["success"],
                    "failed": success_rate["failure"],
                },
                "unique_ip_addresses": len(ip_addresses),
                "ip_addresses": list(ip_addresses),
                "recent_alerts": user_alerts,
                "risk_score": self._calculate_user_risk_score(user_events),
            }

            self.logger.debug(
                "User security summary generated for %s: %d events, risk score: %d",
                user_id,
                len(user_events),
                user_summary["risk_score"],
            )

            return user_summary

        except Exception as e:
            self.logger.error("Failed to generate user security summary for %s: %s", user_id, str(e), exc_info=True)
            return {
                "error": "Failed to generate user security summary",
                "user_id": user_id,
                "generated_at": datetime.now(timezone.utc),
            }

    async def cleanup_old_data(self) -> None:
        """Clean up old monitoring data to prevent memory leaks."""
        try:
            current_time = datetime.now(timezone.utc)
            cutoff_time = current_time - timedelta(hours=SECURITY_METRICS_RETENTION_HOURS)

            # Clean up Redis data
            await self._cleanup_redis_data(cutoff_time)

            # Clean up database audit logs
            await self._cleanup_database_audit_logs()

            # Reset alert counters periodically
            if (current_time - self.last_cleanup).total_seconds() > 3600:  # Every hour
                self.alert_counters.clear()
                self.last_cleanup = current_time

            self.logger.debug("Security monitoring data cleanup completed")

        except Exception as e:
            self.logger.error("Failed to cleanup old monitoring data: %s", str(e), exc_info=True)

    async def _store_event_in_redis(self, security_event: Dict[str, Any]) -> None:
        """Store security event in Redis for short-term analysis."""
        try:
            redis_conn = await self.redis_manager.get_redis()

            # Store event with expiration
            event_key = f"family_security_event:{security_event['event_id']}"
            await redis_conn.setex(
                event_key, SECURITY_METRICS_RETENTION_HOURS * 3600, json.dumps(security_event, default=str)
            )

            # Add to time-series for analysis
            timestamp_key = f"family_security_events:{security_event['timestamp'].strftime('%Y%m%d%H')}"
            await redis_conn.lpush(timestamp_key, security_event["event_id"])
            await redis_conn.expire(timestamp_key, SECURITY_METRICS_RETENTION_HOURS * 3600)

        except Exception as e:
            self.logger.error("Failed to store event in Redis: %s", str(e))

    async def _store_event_in_database(self, security_event: Dict[str, Any]) -> None:
        """Store security event in database for long-term retention."""
        try:
            security_events_collection = db_manager.get_collection("family_security_events")
            await security_events_collection.insert_one(security_event)

        except Exception as e:
            self.logger.error("Failed to store event in database: %s", str(e))

    async def _store_metric_in_redis(self, metric_record: Dict[str, Any]) -> None:
        """Store performance metric in Redis."""
        try:
            redis_conn = await self.redis_manager.get_redis()

            # Store metric with expiration
            metric_key = (
                f"family_performance_metric:{metric_record['metric_name']}:{metric_record['timestamp'].timestamp()}"
            )
            await redis_conn.setex(
                metric_key, SECURITY_METRICS_RETENTION_HOURS * 3600, json.dumps(metric_record, default=str)
            )

        except Exception as e:
            self.logger.error("Failed to store metric in Redis: %s", str(e))

    async def _check_alert_conditions(self, security_event: Dict[str, Any]) -> None:
        """Check if security event triggers any alert conditions."""
        try:
            event_type = security_event["event_type"]
            user_id = security_event["user_id"]
            severity = security_event["severity"]

            # Count events per hour for alerting
            hour_key = datetime.now(timezone.utc).strftime("%Y%m%d%H")
            self.alert_counters[f"{event_type}:{hour_key}"] += 1

            # Check various alert conditions
            if severity in ["error", "critical"]:
                await self._trigger_alert("high_severity_event", security_event)

            if event_type in ["rate_limit_exceeded", "ip_lockdown_violation"]:
                if self.alert_counters[f"{event_type}:{hour_key}"] >= ALERT_THRESHOLD_VIOLATIONS_PER_HOUR:
                    await self._trigger_alert("repeated_security_violations", security_event)

            if event_type == "2fa_verification_failed":
                if self.alert_counters[f"{event_type}:{hour_key}"] >= ALERT_THRESHOLD_FAILED_2FA_PER_HOUR:
                    await self._trigger_alert("repeated_2fa_failures", security_event)

            if event_type == "temp_token_abuse":
                if self.alert_counters[f"{event_type}:{hour_key}"] >= ALERT_THRESHOLD_TEMP_TOKEN_ABUSE_PER_HOUR:
                    await self._trigger_alert("temp_token_abuse_pattern", security_event)

        except Exception as e:
            self.logger.error("Failed to check alert conditions: %s", str(e))

    async def _trigger_alert(self, alert_type: str, security_event: Dict[str, Any]) -> None:
        """Trigger a security alert."""
        try:
            alert = {
                "alert_id": f"fam_alert_{datetime.now(timezone.utc).timestamp()}",
                "alert_type": alert_type,
                "triggered_by": security_event["event_id"],
                "user_id": security_event["user_id"],
                "timestamp": datetime.now(timezone.utc),
                "severity": "high",
                "details": {"triggering_event": security_event, "alert_reason": alert_type},
            }

            # Store alert
            alerts_collection = db_manager.get_collection("family_security_alerts")
            await alerts_collection.insert_one(alert)

            # Log alert
            self.logger.warning(
                "Security alert triggered: %s for user %s", alert_type, security_event["user_id"], extra=alert
            )

            # TODO: Implement alert notification system (email, Slack, etc.)

        except Exception as e:
            self.logger.error("Failed to trigger alert: %s", str(e))

    async def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get currently active security alerts."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

            alerts_collection = db_manager.get_collection("family_security_alerts")
            active_alerts = await alerts_collection.find({"timestamp": {"$gte": cutoff_time}}).to_list(length=100)

            return active_alerts

        except Exception as e:
            self.logger.error("Failed to get active alerts: %s", str(e))
            return []

    async def _get_user_alerts(self, user_id: str) -> List[Dict[str, Any]]:
        """Get recent alerts for a specific user."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)

            alerts_collection = db_manager.get_collection("family_security_alerts")
            user_alerts = await alerts_collection.find(
                {"user_id": user_id, "timestamp": {"$gte": cutoff_time}}
            ).to_list(length=50)

            return user_alerts

        except Exception as e:
            self.logger.error("Failed to get user alerts: %s", str(e))
            return []

    def _calculate_user_risk_score(self, user_events: List[Dict[str, Any]]) -> int:
        """Calculate a risk score for a user based on their security events."""
        try:
            risk_score = 0

            for event in user_events:
                # Add points based on event type and severity
                if event["event_type"] in ["ip_lockdown_violation", "user_agent_lockdown_violation"]:
                    risk_score += 10
                elif event["event_type"] == "2fa_verification_failed":
                    risk_score += 15
                elif event["event_type"] == "rate_limit_exceeded":
                    risk_score += 5
                elif event["event_type"] == "temp_token_abuse":
                    risk_score += 20

                # Add points based on severity
                if event["severity"] == "critical":
                    risk_score += 25
                elif event["severity"] == "error":
                    risk_score += 15
                elif event["severity"] == "warning":
                    risk_score += 5

                # Subtract points for successful operations
                if event["success"]:
                    risk_score = max(0, risk_score - 1)

            # Cap risk score at 100
            return min(100, risk_score)

        except Exception as e:
            self.logger.error("Failed to calculate user risk score: %s", str(e))
            return 0

    async def _cleanup_redis_data(self, cutoff_time: datetime) -> None:
        """Clean up old Redis monitoring data."""
        try:
            redis_conn = await self.redis_manager.get_redis()

            # Clean up old event keys
            pattern = "family_security_event:*"
            async for key in redis_conn.scan_iter(match=pattern):
                # Check if key is old and delete it
                ttl = await redis_conn.ttl(key)
                if ttl <= 0:  # Key has expired or will expire soon
                    await redis_conn.delete(key)

        except Exception as e:
            self.logger.error("Failed to cleanup Redis data: %s", str(e))

    async def _cleanup_database_audit_logs(self) -> None:
        """Clean up old database audit logs."""
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(days=AUDIT_LOG_RETENTION_DAYS)

            # Clean up old security events
            security_events_collection = db_manager.get_collection("family_security_events")
            result = await security_events_collection.delete_many({"timestamp": {"$lt": cutoff_time}})

            if result.deleted_count > 0:
                self.logger.info("Cleaned up %d old security events from database", result.deleted_count)

            # Clean up old alerts
            alerts_collection = db_manager.get_collection("family_security_alerts")
            result = await alerts_collection.delete_many({"timestamp": {"$lt": cutoff_time}})

            if result.deleted_count > 0:
                self.logger.info("Cleaned up %d old security alerts from database", result.deleted_count)

        except Exception as e:
            self.logger.error("Failed to cleanup database audit logs: %s", str(e))


# Global instance
family_security_monitor = FamilySecurityMonitor()


# Decorator for monitoring family operations
def monitor_family_operation(operation_name: str, require_2fa: bool = False):
    """
    Decorator to automatically monitor family operations.

    Args:
        operation_name: Name of the operation being monitored
        require_2fa: Whether the operation requires 2FA
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = datetime.now(timezone.utc)
            user_id = None
            success = False
            error = None

            try:
                # Extract user_id from arguments if available
                for arg in args:
                    if isinstance(arg, dict) and "user_id" in arg:
                        user_id = arg["user_id"]
                        break

                # Execute the function
                result = await func(*args, **kwargs)
                success = True

                return result

            except Exception as e:
                error = str(e)
                raise

            finally:
                # Record performance metric
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                await family_security_monitor.record_performance_metric(
                    metric_name="family_operation_duration",
                    value=duration,
                    operation=operation_name,
                    user_id=user_id,
                    additional_tags={"success": str(success), "require_2fa": str(require_2fa)},
                )

                # Record security event
                await family_security_monitor.record_security_event(
                    event_type=f"family_operation_{operation_name}",
                    user_id=user_id or "unknown",
                    details={
                        "operation": operation_name,
                        "duration_seconds": duration,
                        "require_2fa": require_2fa,
                        "error": error,
                    },
                    severity="info" if success else "error",
                    success=success,
                )

        return wrapper

    return decorator
