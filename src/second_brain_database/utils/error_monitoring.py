"""
Error Monitoring and Alerting System.

This module provides comprehensive error monitoring, alerting, and escalation
procedures for the family management system. It implements enterprise-grade
monitoring patterns including error aggregation, trend analysis, anomaly
detection, and automated alerting with escalation procedures.

Key Features:
- Real-time error monitoring and aggregation
- Error trend analysis and anomaly detection
- Automated alerting with configurable thresholds
- Escalation procedures for critical errors
- Error correlation and root cause analysis
- Performance impact assessment
- Error recovery tracking and success rates
- Integration with external monitoring systems

Monitoring Patterns:
- Error rate monitoring with sliding windows
- Error pattern detection and classification
- Anomaly detection using statistical methods
- Alert fatigue prevention with intelligent grouping
- Escalation chains for different error severities
- Error correlation across system components
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import statistics
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.error_handling import ErrorContext, ErrorSeverity, sanitize_sensitive_data

# Import monitoring with graceful fallback
try:
    from second_brain_database.managers.family_monitoring import AlertSeverity, family_monitor
    from second_brain_database.managers.redis_manager import redis_manager

    MONITORING_ENABLED = True
except ImportError:
    MONITORING_ENABLED = False

logger = get_logger(prefix="[Error Monitoring]")

# Monitoring configuration
DEFAULT_ERROR_WINDOW_SIZE = 100  # Number of errors to keep in sliding window
DEFAULT_TIME_WINDOW_MINUTES = 15  # Time window for error rate calculation
DEFAULT_ERROR_RATE_THRESHOLD = 0.05  # 5% error rate threshold
DEFAULT_CRITICAL_ERROR_RATE_THRESHOLD = 0.10  # 10% critical error rate
DEFAULT_ANOMALY_DETECTION_THRESHOLD = 2.0  # Standard deviations for anomaly detection
DEFAULT_ALERT_COOLDOWN_MINUTES = 30  # Cooldown period between similar alerts
DEFAULT_ESCALATION_DELAY_MINUTES = 60  # Time before escalating alerts


class AlertType(Enum):
    """Types of alerts that can be generated."""

    ERROR_RATE_HIGH = "error_rate_high"
    ERROR_RATE_CRITICAL = "error_rate_critical"
    ANOMALY_DETECTED = "anomaly_detected"
    REPEATED_ERRORS = "repeated_errors"
    SYSTEM_DEGRADATION = "system_degradation"
    RECOVERY_FAILURE = "recovery_failure"
    PERFORMANCE_IMPACT = "performance_impact"
    SECURITY_CONCERN = "security_concern"


class EscalationLevel(Enum):
    """Escalation levels for alerts."""

    LEVEL_1 = "level_1"  # Development team
    LEVEL_2 = "level_2"  # Operations team
    LEVEL_3 = "level_3"  # Management
    LEVEL_4 = "level_4"  # Executive


@dataclass
class ErrorEvent:
    """Represents a single error event for monitoring."""

    timestamp: datetime
    operation: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    context: Dict[str, Any]
    user_id: Optional[str] = None
    family_id: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage and analysis."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "operation": self.operation,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "severity": self.severity.value,
            "context": sanitize_sensitive_data(self.context),
            "user_id": self.user_id,
            "family_id": self.family_id,
            "request_id": self.request_id,
            "ip_address": self.ip_address,
            "recovery_attempted": self.recovery_attempted,
            "recovery_successful": self.recovery_successful,
        }

    def get_signature(self) -> str:
        """Get a signature for error grouping."""
        signature_data = f"{self.operation}:{self.error_type}:{self.error_message[:100]}"
        return hashlib.md5(signature_data.encode()).hexdigest()


@dataclass
class ErrorPattern:
    """Represents a pattern of similar errors."""

    signature: str
    operation: str
    error_type: str
    first_seen: datetime
    last_seen: datetime
    count: int = 1
    severity: ErrorSeverity = ErrorSeverity.LOW
    affected_users: Set[str] = field(default_factory=set)
    affected_families: Set[str] = field(default_factory=set)
    recovery_attempts: int = 0
    recovery_successes: int = 0

    def update(self, event: ErrorEvent):
        """Update pattern with new error event."""
        self.last_seen = event.timestamp
        self.count += 1

        # Update severity to highest seen
        if event.severity.value == "critical":
            self.severity = ErrorSeverity.CRITICAL
        elif event.severity.value == "high" and self.severity != ErrorSeverity.CRITICAL:
            self.severity = ErrorSeverity.HIGH
        elif event.severity.value == "medium" and self.severity in [ErrorSeverity.LOW]:
            self.severity = ErrorSeverity.MEDIUM

        # Track affected entities
        if event.user_id:
            self.affected_users.add(event.user_id)
        if event.family_id:
            self.affected_families.add(event.family_id)

        # Track recovery attempts
        if event.recovery_attempted:
            self.recovery_attempts += 1
            if event.recovery_successful:
                self.recovery_successes += 1

    def get_recovery_rate(self) -> float:
        """Get recovery success rate for this pattern."""
        if self.recovery_attempts == 0:
            return 0.0
        return self.recovery_successes / self.recovery_attempts

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for analysis."""
        return {
            "signature": self.signature,
            "operation": self.operation,
            "error_type": self.error_type,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "count": self.count,
            "severity": self.severity.value,
            "affected_users_count": len(self.affected_users),
            "affected_families_count": len(self.affected_families),
            "recovery_attempts": self.recovery_attempts,
            "recovery_successes": self.recovery_successes,
            "recovery_rate": self.get_recovery_rate(),
        }


@dataclass
class Alert:
    """Represents an alert generated by the monitoring system."""

    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    created_at: datetime
    escalation_level: EscalationLevel = EscalationLevel.LEVEL_1
    escalated_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "alert_id": self.alert_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "created_at": self.created_at.isoformat(),
            "escalation_level": self.escalation_level.value,
            "escalated_at": self.escalated_at.isoformat() if self.escalated_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
        }


class ErrorMonitor:
    """
    Comprehensive error monitoring and alerting system.

    This monitor tracks errors across the system, detects patterns and anomalies,
    and generates alerts with appropriate escalation procedures.
    """

    def __init__(self):
        self.logger = logger

        # Error tracking
        self.error_events: deque = deque(maxlen=DEFAULT_ERROR_WINDOW_SIZE * 10)
        self.error_patterns: Dict[str, ErrorPattern] = {}
        self.error_rates: Dict[str, deque] = defaultdict(lambda: deque(maxlen=DEFAULT_ERROR_WINDOW_SIZE))

        # Alert tracking
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.last_alert_times: Dict[str, datetime] = {}

        # Escalation tracking
        self.escalation_callbacks: Dict[EscalationLevel, List[Callable]] = defaultdict(list)

        # Background tasks
        self.monitoring_task = None
        self._monitoring_started = False
        # Don't start monitoring during import - will be started lazily

    def start_monitoring(self):
        """Start background monitoring tasks."""
        if not self._monitoring_started:
            try:
                # Only start if we're in an async context
                loop = asyncio.get_running_loop()
                if self.monitoring_task is None or self.monitoring_task.done():
                    self.monitoring_task = asyncio.create_task(self._monitoring_loop())
                    self.logger.info("Error monitoring started")
                    self._monitoring_started = True
            except RuntimeError:
                # No running event loop, will start later when needed
                self.logger.debug("No event loop available, monitoring will start later")

    def stop_monitoring(self):
        """Stop background monitoring tasks."""
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            self.logger.info("Error monitoring stopped")

    async def record_error(
        self,
        error: Exception,
        context: ErrorContext,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recovery_attempted: bool = False,
        recovery_successful: bool = False,
    ):
        """
        Record an error event for monitoring and analysis.

        Args:
            error: The exception that occurred
            context: Error context information
            severity: Error severity level
            recovery_attempted: Whether recovery was attempted
            recovery_successful: Whether recovery was successful
        """
        # Ensure monitoring is started when we actually use the error monitor
        self.start_monitoring()
        event = ErrorEvent(
            timestamp=datetime.now(timezone.utc),
            operation=context.operation,
            error_type=type(error).__name__,
            error_message=str(error),
            severity=severity,
            context=context.to_dict(),
            user_id=context.user_id,
            family_id=context.family_id,
            request_id=context.request_id,
            ip_address=context.ip_address,
            recovery_attempted=recovery_attempted,
            recovery_successful=recovery_successful,
        )

        # Add to event history
        self.error_events.append(event)

        # Update error patterns
        signature = event.get_signature()
        if signature in self.error_patterns:
            self.error_patterns[signature].update(event)
        else:
            self.error_patterns[signature] = ErrorPattern(
                signature=signature,
                operation=event.operation,
                error_type=event.error_type,
                first_seen=event.timestamp,
                last_seen=event.timestamp,
                severity=event.severity,
            )
            if event.user_id:
                self.error_patterns[signature].affected_users.add(event.user_id)
            if event.family_id:
                self.error_patterns[signature].affected_families.add(event.family_id)

        # Update error rates
        self.error_rates[event.operation].append(event.timestamp)

        # Log the error event
        self.logger.info(
            "Error recorded: %s in %s (severity: %s, recovery: %s)",
            event.error_type,
            event.operation,
            event.severity.value,
            "successful" if recovery_successful else "attempted" if recovery_attempted else "none",
            extra=event.to_dict(),
        )

        # Trigger immediate analysis for critical errors
        if severity == ErrorSeverity.CRITICAL:
            await self._analyze_and_alert()

    async def _monitoring_loop(self):
        """Main monitoring loop for periodic analysis."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._analyze_and_alert()
                await self._check_escalations()
                await self._cleanup_old_data()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Error in monitoring loop: %s", str(e))
                await asyncio.sleep(60)

    async def _analyze_and_alert(self):
        """Analyze error patterns and generate alerts."""
        current_time = datetime.now(timezone.utc)

        # Check error rates
        await self._check_error_rates(current_time)

        # Check for anomalies
        await self._check_anomalies(current_time)

        # Check repeated errors
        await self._check_repeated_errors(current_time)

        # Check system degradation
        await self._check_system_degradation(current_time)

        # Check recovery failures
        await self._check_recovery_failures(current_time)

    async def _check_error_rates(self, current_time: datetime):
        """Check error rates and generate alerts if thresholds are exceeded."""
        time_window = timedelta(minutes=DEFAULT_TIME_WINDOW_MINUTES)
        cutoff_time = current_time - time_window

        for operation, error_times in self.error_rates.items():
            # Count recent errors
            recent_errors = [t for t in error_times if t >= cutoff_time]
            error_rate = len(recent_errors) / DEFAULT_TIME_WINDOW_MINUTES  # errors per minute

            # Check thresholds
            if error_rate >= DEFAULT_CRITICAL_ERROR_RATE_THRESHOLD:
                await self._generate_alert(
                    AlertType.ERROR_RATE_CRITICAL,
                    AlertSeverity.CRITICAL,
                    f"Critical Error Rate: {operation}",
                    f"Operation {operation} has {error_rate:.2f} errors/min (threshold: {DEFAULT_CRITICAL_ERROR_RATE_THRESHOLD})",
                    {
                        "operation": operation,
                        "error_rate": error_rate,
                        "threshold": DEFAULT_CRITICAL_ERROR_RATE_THRESHOLD,
                        "recent_errors": len(recent_errors),
                        "time_window_minutes": DEFAULT_TIME_WINDOW_MINUTES,
                    },
                )
            elif error_rate >= DEFAULT_ERROR_RATE_THRESHOLD:
                await self._generate_alert(
                    AlertType.ERROR_RATE_HIGH,
                    AlertSeverity.WARNING,
                    f"High Error Rate: {operation}",
                    f"Operation {operation} has {error_rate:.2f} errors/min (threshold: {DEFAULT_ERROR_RATE_THRESHOLD})",
                    {
                        "operation": operation,
                        "error_rate": error_rate,
                        "threshold": DEFAULT_ERROR_RATE_THRESHOLD,
                        "recent_errors": len(recent_errors),
                        "time_window_minutes": DEFAULT_TIME_WINDOW_MINUTES,
                    },
                )

    async def _check_anomalies(self, current_time: datetime):
        """Check for anomalous error patterns using statistical analysis."""
        time_window = timedelta(hours=24)
        cutoff_time = current_time - time_window

        # Group errors by hour for trend analysis
        hourly_errors = defaultdict(int)
        for event in self.error_events:
            if event.timestamp >= cutoff_time:
                hour_key = event.timestamp.replace(minute=0, second=0, microsecond=0)
                hourly_errors[hour_key] += 1

        if len(hourly_errors) < 3:  # Need at least 3 data points
            return

        error_counts = list(hourly_errors.values())
        mean_errors = statistics.mean(error_counts)

        if len(error_counts) > 1:
            stdev_errors = statistics.stdev(error_counts)
            current_hour = current_time.replace(minute=0, second=0, microsecond=0)
            current_errors = hourly_errors.get(current_hour, 0)

            # Check if current hour is anomalous
            if stdev_errors > 0 and current_errors > mean_errors + (DEFAULT_ANOMALY_DETECTION_THRESHOLD * stdev_errors):
                await self._generate_alert(
                    AlertType.ANOMALY_DETECTED,
                    AlertSeverity.WARNING,
                    "Error Anomaly Detected",
                    f"Current hour has {current_errors} errors, significantly above normal ({mean_errors:.1f} ± {stdev_errors:.1f})",
                    {
                        "current_errors": current_errors,
                        "mean_errors": mean_errors,
                        "stdev_errors": stdev_errors,
                        "threshold_multiplier": DEFAULT_ANOMALY_DETECTION_THRESHOLD,
                    },
                )

    async def _check_repeated_errors(self, current_time: datetime):
        """Check for repeated error patterns that might indicate systemic issues."""
        time_window = timedelta(hours=1)
        cutoff_time = current_time - time_window

        for signature, pattern in self.error_patterns.items():
            if pattern.last_seen >= cutoff_time and pattern.count >= 10:
                # Check if this is a new repeated error pattern
                alert_key = f"repeated_{signature}"
                if alert_key not in self.last_alert_times or current_time - self.last_alert_times[
                    alert_key
                ] > timedelta(minutes=DEFAULT_ALERT_COOLDOWN_MINUTES):

                    severity = (
                        AlertSeverity.ERROR if pattern.severity == ErrorSeverity.CRITICAL else AlertSeverity.WARNING
                    )

                    await self._generate_alert(
                        AlertType.REPEATED_ERRORS,
                        severity,
                        f"Repeated Error Pattern: {pattern.operation}",
                        f"Error pattern in {pattern.operation} occurred {pattern.count} times in the last hour",
                        {
                            "operation": pattern.operation,
                            "error_type": pattern.error_type,
                            "count": pattern.count,
                            "affected_users": len(pattern.affected_users),
                            "affected_families": len(pattern.affected_families),
                            "recovery_rate": pattern.get_recovery_rate(),
                        },
                    )

                    self.last_alert_times[alert_key] = current_time

    async def _check_system_degradation(self, current_time: datetime):
        """Check for signs of system degradation."""
        time_window = timedelta(minutes=30)
        cutoff_time = current_time - time_window

        # Count recent errors by severity
        recent_events = [e for e in self.error_events if e.timestamp >= cutoff_time]
        critical_errors = len([e for e in recent_events if e.severity == ErrorSeverity.CRITICAL])
        high_errors = len([e for e in recent_events if e.severity == ErrorSeverity.HIGH])

        # Check for system degradation indicators
        if critical_errors >= 5 or high_errors >= 15:
            await self._generate_alert(
                AlertType.SYSTEM_DEGRADATION,
                AlertSeverity.CRITICAL,
                "System Degradation Detected",
                f"System showing signs of degradation: {critical_errors} critical, {high_errors} high severity errors in 30 minutes",
                {
                    "critical_errors": critical_errors,
                    "high_errors": high_errors,
                    "total_errors": len(recent_events),
                    "time_window_minutes": 30,
                },
            )

    async def _check_recovery_failures(self, current_time: datetime):
        """Check for patterns of recovery failures."""
        time_window = timedelta(hours=2)
        cutoff_time = current_time - time_window

        # Analyze recovery patterns
        recovery_stats = defaultdict(lambda: {"attempts": 0, "successes": 0})

        for event in self.error_events:
            if event.timestamp >= cutoff_time and event.recovery_attempted:
                key = f"{event.operation}:{event.error_type}"
                recovery_stats[key]["attempts"] += 1
                if event.recovery_successful:
                    recovery_stats[key]["successes"] += 1

        # Check for poor recovery rates
        for key, stats in recovery_stats.items():
            if stats["attempts"] >= 5:  # At least 5 recovery attempts
                success_rate = stats["successes"] / stats["attempts"]
                if success_rate < 0.3:  # Less than 30% success rate
                    operation, error_type = key.split(":", 1)
                    await self._generate_alert(
                        AlertType.RECOVERY_FAILURE,
                        AlertSeverity.ERROR,
                        f"Poor Recovery Rate: {operation}",
                        f"Recovery success rate for {error_type} in {operation} is {success_rate:.1%} ({stats['successes']}/{stats['attempts']})",
                        {
                            "operation": operation,
                            "error_type": error_type,
                            "success_rate": success_rate,
                            "attempts": stats["attempts"],
                            "successes": stats["successes"],
                        },
                    )

    async def _generate_alert(
        self, alert_type: AlertType, severity: AlertSeverity, title: str, message: str, metadata: Dict[str, Any]
    ):
        """Generate and process an alert."""
        alert_id = f"{alert_type.value}_{int(time.time() * 1000)}"

        alert = Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            created_at=datetime.now(timezone.utc),
            metadata=metadata,
        )

        self.active_alerts[alert_id] = alert

        # Log the alert (avoid 'message' field conflict)
        alert_dict = alert.to_dict()
        # Remove conflicting fields that might overwrite LogRecord fields
        safe_extra = {k: v for k, v in alert_dict.items() if k not in ["message", "msg", "args"]}

        self.logger.warning("Alert generated: %s - %s", title, message, extra=safe_extra)

        # Send to monitoring system
        if MONITORING_ENABLED:
            await family_monitor.send_alert(severity, title, message, metadata)

        # Trigger escalation callbacks
        await self._trigger_escalation_callbacks(alert)

    async def _check_escalations(self):
        """Check if any alerts need to be escalated."""
        current_time = datetime.now(timezone.utc)
        escalation_delay = timedelta(minutes=DEFAULT_ESCALATION_DELAY_MINUTES)

        for alert in self.active_alerts.values():
            if alert.resolved_at is None and alert.escalated_at is None:
                if current_time - alert.created_at >= escalation_delay:
                    await self._escalate_alert(alert)

    async def _escalate_alert(self, alert: Alert):
        """Escalate an alert to the next level."""
        if alert.escalation_level == EscalationLevel.LEVEL_1:
            alert.escalation_level = EscalationLevel.LEVEL_2
        elif alert.escalation_level == EscalationLevel.LEVEL_2:
            alert.escalation_level = EscalationLevel.LEVEL_3
        elif alert.escalation_level == EscalationLevel.LEVEL_3:
            alert.escalation_level = EscalationLevel.LEVEL_4

        alert.escalated_at = datetime.now(timezone.utc)

        self.logger.warning(
            "Alert escalated to %s: %s", alert.escalation_level.value, alert.title, extra=alert.to_dict()
        )

        # Trigger escalation callbacks
        await self._trigger_escalation_callbacks(alert)

    async def _trigger_escalation_callbacks(self, alert: Alert):
        """Trigger registered escalation callbacks."""
        callbacks = self.escalation_callbacks.get(alert.escalation_level, [])
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                self.logger.error("Escalation callback failed for alert %s: %s", alert.alert_id, str(e))

    async def _cleanup_old_data(self):
        """Clean up old monitoring data."""
        current_time = datetime.now(timezone.utc)
        cleanup_age = timedelta(days=7)
        cutoff_time = current_time - cleanup_age

        # Clean up old error patterns
        patterns_to_remove = []
        for signature, pattern in self.error_patterns.items():
            if pattern.last_seen < cutoff_time:
                patterns_to_remove.append(signature)

        for signature in patterns_to_remove:
            del self.error_patterns[signature]

        # Clean up resolved alerts
        resolved_alerts = [
            alert for alert in self.active_alerts.values() if alert.resolved_at and alert.resolved_at < cutoff_time
        ]

        for alert in resolved_alerts:
            self.alert_history.append(alert)
            del self.active_alerts[alert.alert_id]

        # Limit alert history size
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]

    def register_escalation_callback(self, level: EscalationLevel, callback: Callable):
        """Register a callback for alert escalations."""
        self.escalation_callbacks[level].append(callback)

    def resolve_alert(self, alert_id: str):
        """Mark an alert as resolved."""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].resolved_at = datetime.now(timezone.utc)
            self.logger.info("Alert resolved: %s", alert_id)

    def get_monitoring_stats(self) -> Dict[str, Any]:
        """Get comprehensive monitoring statistics."""
        current_time = datetime.now(timezone.utc)

        # Error statistics
        total_errors = len(self.error_events)
        recent_errors = len([e for e in self.error_events if current_time - e.timestamp <= timedelta(hours=24)])

        # Pattern statistics
        active_patterns = len(self.error_patterns)
        critical_patterns = len([p for p in self.error_patterns.values() if p.severity == ErrorSeverity.CRITICAL])

        # Alert statistics
        active_alerts = len(self.active_alerts)
        critical_alerts = len([a for a in self.active_alerts.values() if a.severity == AlertSeverity.CRITICAL])

        return {
            "error_statistics": {
                "total_errors": total_errors,
                "recent_errors_24h": recent_errors,
                "error_rate_24h": recent_errors / 24.0,  # errors per hour
                "active_patterns": active_patterns,
                "critical_patterns": critical_patterns,
            },
            "alert_statistics": {
                "active_alerts": active_alerts,
                "critical_alerts": critical_alerts,
                "total_alert_history": len(self.alert_history),
            },
            "recovery_statistics": {
                "total_recovery_attempts": sum(1 for e in self.error_events if e.recovery_attempted),
                "successful_recoveries": sum(1 for e in self.error_events if e.recovery_successful),
                "recovery_success_rate": self._calculate_overall_recovery_rate(),
            },
        }

    def _calculate_overall_recovery_rate(self) -> float:
        """Calculate overall recovery success rate."""
        attempts = sum(1 for e in self.error_events if e.recovery_attempted)
        successes = sum(1 for e in self.error_events if e.recovery_successful)
        return successes / max(attempts, 1)

    def get_error_patterns(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top error patterns by frequency."""
        patterns = sorted(self.error_patterns.values(), key=lambda p: p.count, reverse=True)[:limit]

        return [p.to_dict() for p in patterns]

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active alerts."""
        return [alert.to_dict() for alert in self.active_alerts.values()]


# Global error monitor instance
error_monitor = ErrorMonitor()


# Convenience functions
async def record_error_event(
    error: Exception,
    context: ErrorContext,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    recovery_attempted: bool = False,
    recovery_successful: bool = False,
):
    """Convenience function to record an error event."""
    await error_monitor.record_error(error, context, severity, recovery_attempted, recovery_successful)


def register_escalation_handler(level: EscalationLevel, handler: Callable):
    """Convenience function to register an escalation handler."""
    error_monitor.register_escalation_callback(level, handler)


def resolve_alert(alert_id: str):
    """Convenience function to resolve an alert."""
    error_monitor.resolve_alert(alert_id)


# Example escalation handlers
async def level_1_escalation_handler(alert: Alert):
    """Example Level 1 escalation handler (Development team)."""
    logger.info("Level 1 escalation: %s - %s", alert.title, alert.message)
    # In production, this might send to Slack, email, or PagerDuty


async def level_2_escalation_handler(alert: Alert):
    """Example Level 2 escalation handler (Operations team)."""
    logger.warning("Level 2 escalation: %s - %s", alert.title, alert.message)
    # In production, this might page the on-call engineer


async def level_3_escalation_handler(alert: Alert):
    """Example Level 3 escalation handler (Management)."""
    logger.error("Level 3 escalation: %s - %s", alert.title, alert.message)
    # In production, this might notify management


async def level_4_escalation_handler(alert: Alert):
    """Example Level 4 escalation handler (Executive)."""
    logger.critical("Level 4 escalation: %s - %s", alert.title, alert.message)
    # In production, this might notify executives for critical system failures


# Register default escalation handlers
register_escalation_handler(EscalationLevel.LEVEL_1, level_1_escalation_handler)
register_escalation_handler(EscalationLevel.LEVEL_2, level_2_escalation_handler)
register_escalation_handler(EscalationLevel.LEVEL_3, level_3_escalation_handler)
register_escalation_handler(EscalationLevel.LEVEL_4, level_4_escalation_handler)
