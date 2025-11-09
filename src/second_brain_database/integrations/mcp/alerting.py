"""
MCP Alerting System

Implements comprehensive alerting for MCP server failures, suspicious activity,
and performance threshold violations. Integrates with existing monitoring
infrastructure and provides configurable alert channels and thresholds.
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import time
from typing import Any, Callable, Dict, List, Optional, Set, Union

from ...config import settings
from ...managers.logging_manager import get_logger
from .context import MCPUserContext, get_mcp_user_context
from .error_recovery import mcp_recovery_manager
from .performance_monitoring import MetricType, mcp_performance_monitor

logger = get_logger(prefix="[MCP_Alerting]")


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertCategory(Enum):
    """Categories of alerts."""

    SERVER_HEALTH = "server_health"
    PERFORMANCE = "performance"
    SECURITY = "security"
    ERROR_RATE = "error_rate"
    RESOURCE_USAGE = "resource_usage"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    CIRCUIT_BREAKER = "circuit_breaker"
    BULKHEAD = "bulkhead"


@dataclass
class Alert:
    """Individual alert instance."""

    id: str
    severity: AlertSeverity
    category: AlertCategory
    title: str
    message: str
    timestamp: datetime
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            "id": self.id,
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "metadata": self.metadata,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
        }


@dataclass
class AlertRule:
    """Configuration for alert rules and thresholds."""

    name: str
    category: AlertCategory
    severity: AlertSeverity
    condition: Callable[[Dict[str, Any]], bool]
    threshold_value: Optional[float] = None
    time_window_minutes: int = 5
    min_occurrences: int = 1
    cooldown_minutes: int = 15
    enabled: bool = True
    description: str = ""

    def __post_init__(self):
        if not self.description:
            self.description = f"Alert rule for {self.name}"


class AlertChannel:
    """Base class for alert notification channels."""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    async def send_alert(self, alert: Alert) -> bool:
        """
        Send alert through this channel.

        Args:
            alert: Alert to send

        Returns:
            True if sent successfully, False otherwise
        """
        raise NotImplementedError

    async def test_connection(self) -> bool:
        """Test if the alert channel is working."""
        raise NotImplementedError


class LogAlertChannel(AlertChannel):
    """Alert channel that logs alerts to the application logger."""

    def __init__(self, name: str = "log", enabled: bool = True):
        super().__init__(name, enabled)

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to application logs."""
        if not self.enabled:
            return False

        try:
            log_level = {
                AlertSeverity.INFO: logger.info,
                AlertSeverity.WARNING: logger.warning,
                AlertSeverity.ERROR: logger.error,
                AlertSeverity.CRITICAL: logger.critical,
            }.get(alert.severity, logger.info)

            log_level(
                "MCP ALERT [%s] %s: %s",
                alert.severity.value.upper(),
                alert.title,
                alert.message,
                extra={
                    "mcp_alert": True,
                    "alert_id": alert.id,
                    "alert_category": alert.category.value,
                    "alert_metadata": alert.metadata,
                },
            )

            return True

        except Exception as e:
            logger.error("Failed to send alert to log channel: %s", e)
            return False

    async def test_connection(self) -> bool:
        """Test log channel (always available)."""
        return True


class EmailAlertChannel(AlertChannel):
    """Alert channel that sends alerts via email."""

    def __init__(self, name: str = "email", recipients: List[str] = None, enabled: bool = True):
        super().__init__(name, enabled)
        self.recipients = recipients or []

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        if not self.enabled or not self.recipients:
            return False

        try:
            # Import email utilities (would need to be implemented)
            # from ...utils.email_utils import send_alert_email

            subject = f"MCP Alert [{alert.severity.value.upper()}]: {alert.title}"
            body = self._format_email_body(alert)

            # This would need to be implemented based on existing email infrastructure
            # success = await send_alert_email(self.recipients, subject, body)

            logger.info("Email alert would be sent to %s recipients", len(self.recipients))
            return True  # Placeholder

        except Exception as e:
            logger.error("Failed to send email alert: %s", e)
            return False

    def _format_email_body(self, alert: Alert) -> str:
        """Format alert as email body."""
        return f"""
MCP Alert Notification

Severity: {alert.severity.value.upper()}
Category: {alert.category.value}
Time: {alert.timestamp.isoformat()}
Source: {alert.source}

Title: {alert.title}

Message:
{alert.message}

Metadata:
{json.dumps(alert.metadata, indent=2)}

Alert ID: {alert.id}
        """.strip()

    async def test_connection(self) -> bool:
        """Test email channel connectivity."""
        # This would test actual email configuration
        return len(self.recipients) > 0


class WebhookAlertChannel(AlertChannel):
    """Alert channel that sends alerts to webhook endpoints."""

    def __init__(
        self, name: str = "webhook", webhook_url: str = "", headers: Dict[str, str] = None, enabled: bool = True
    ):
        super().__init__(name, enabled)
        self.webhook_url = webhook_url
        self.headers = headers or {"Content-Type": "application/json"}

    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to webhook endpoint."""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            import aiohttp

            payload = {
                "alert": alert.to_dict(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "mcp_server",
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status < 400:
                        logger.debug("Webhook alert sent successfully to %s", self.webhook_url)
                        return True
                    else:
                        logger.error("Webhook alert failed with status %d", response.status)
                        return False

        except Exception as e:
            logger.error("Failed to send webhook alert: %s", e)
            return False

    async def test_connection(self) -> bool:
        """Test webhook endpoint connectivity."""
        if not self.webhook_url:
            return False

        try:
            import aiohttp

            test_payload = {"test": True, "timestamp": datetime.now(timezone.utc).isoformat()}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=test_payload, headers=self.headers, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status < 400

        except Exception:
            return False


class MCPAlertManager:
    """
    Centralized alert management for MCP operations.

    Manages alert rules, channels, and provides intelligent alerting
    with deduplication, rate limiting, and escalation capabilities.
    """

    def __init__(self):
        self._alert_rules: Dict[str, AlertRule] = {}
        self._alert_channels: Dict[str, AlertChannel] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: deque = deque(maxlen=10000)
        self._alert_counts: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._last_alert_times: Dict[str, datetime] = {}
        self._monitoring_enabled = True
        self._monitoring_task: Optional[asyncio.Task] = None

        # Initialize default alert channels
        self._initialize_default_channels()

        # Initialize default alert rules
        self._initialize_default_rules()

        logger.info("MCP Alert Manager initialized")

    def _initialize_default_channels(self) -> None:
        """Initialize default alert channels."""
        # Log channel (always available)
        self.add_channel(LogAlertChannel())

        # Email channel (if configured)
        email_recipients = getattr(settings, "MCP_ALERT_EMAIL_RECIPIENTS", [])
        if email_recipients:
            self.add_channel(EmailAlertChannel(recipients=email_recipients))

        # Webhook channel (if configured)
        webhook_url = getattr(settings, "MCP_ALERT_WEBHOOK_URL", "")
        if webhook_url:
            self.add_channel(WebhookAlertChannel(webhook_url=webhook_url))

    def _initialize_default_rules(self) -> None:
        """Initialize default alert rules."""
        # Server health alerts
        self.add_rule(
            AlertRule(
                name="mcp_server_down",
                category=AlertCategory.SERVER_HEALTH,
                severity=AlertSeverity.CRITICAL,
                condition=lambda data: not data.get("server_running", True),
                description="MCP server is not running",
            )
        )

        # Performance alerts
        self.add_rule(
            AlertRule(
                name="high_error_rate",
                category=AlertCategory.ERROR_RATE,
                severity=AlertSeverity.ERROR,
                condition=lambda data: data.get("error_rate", 0) > 10.0,
                threshold_value=10.0,
                time_window_minutes=5,
                description="Error rate exceeds 10%",
            )
        )

        self.add_rule(
            AlertRule(
                name="slow_response_time",
                category=AlertCategory.PERFORMANCE,
                severity=AlertSeverity.WARNING,
                condition=lambda data: data.get("avg_response_time", 0) > 5.0,
                threshold_value=5.0,
                time_window_minutes=10,
                description="Average response time exceeds 5 seconds",
            )
        )

        # Resource usage alerts
        self.add_rule(
            AlertRule(
                name="high_cpu_usage",
                category=AlertCategory.RESOURCE_USAGE,
                severity=AlertSeverity.WARNING,
                condition=lambda data: data.get("cpu_usage", 0) > 80.0,
                threshold_value=80.0,
                time_window_minutes=5,
                description="CPU usage exceeds 80%",
            )
        )

        self.add_rule(
            AlertRule(
                name="high_memory_usage",
                category=AlertCategory.RESOURCE_USAGE,
                severity=AlertSeverity.WARNING,
                condition=lambda data: data.get("memory_usage_mb", 0) > 1000,
                threshold_value=1000,
                time_window_minutes=5,
                description="Memory usage exceeds 1GB",
            )
        )

        # Circuit breaker alerts
        self.add_rule(
            AlertRule(
                name="circuit_breaker_open",
                category=AlertCategory.CIRCUIT_BREAKER,
                severity=AlertSeverity.ERROR,
                condition=lambda data: data.get("circuit_breaker_open", False),
                cooldown_minutes=30,
                description="Circuit breaker is open",
            )
        )

        # Suspicious activity alerts
        self.add_rule(
            AlertRule(
                name="rapid_failed_requests",
                category=AlertCategory.SUSPICIOUS_ACTIVITY,
                severity=AlertSeverity.WARNING,
                condition=lambda data: data.get("failed_requests_per_minute", 0) > 20,
                threshold_value=20,
                time_window_minutes=1,
                description="Rapid failed requests detected",
            )
        )

        self.add_rule(
            AlertRule(
                name="unusual_tool_usage",
                category=AlertCategory.SUSPICIOUS_ACTIVITY,
                severity=AlertSeverity.INFO,
                condition=lambda data: data.get("unusual_pattern", False),
                time_window_minutes=15,
                description="Unusual tool usage pattern detected",
            )
        )

    def add_channel(self, channel: AlertChannel) -> None:
        """Add an alert channel."""
        self._alert_channels[channel.name] = channel
        logger.info("Added alert channel: %s (enabled: %s)", channel.name, channel.enabled)

    def remove_channel(self, channel_name: str) -> bool:
        """Remove an alert channel."""
        if channel_name in self._alert_channels:
            del self._alert_channels[channel_name]
            logger.info("Removed alert channel: %s", channel_name)
            return True
        return False

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self._alert_rules[rule.name] = rule
        logger.info("Added alert rule: %s (severity: %s)", rule.name, rule.severity.value)

    def remove_rule(self, rule_name: str) -> bool:
        """Remove an alert rule."""
        if rule_name in self._alert_rules:
            del self._alert_rules[rule_name]
            logger.info("Removed alert rule: %s", rule_name)
            return True
        return False

    async def trigger_alert(
        self,
        severity: AlertSeverity,
        category: AlertCategory,
        title: str,
        message: str,
        source: str = "mcp_server",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Alert]:
        """
        Trigger an alert manually.

        Args:
            severity: Alert severity level
            category: Alert category
            title: Alert title
            message: Alert message
            source: Source of the alert
            metadata: Additional metadata

        Returns:
            Created alert if successful, None if suppressed
        """
        # Generate alert ID
        alert_id = self._generate_alert_id(title, message, source)

        # Check for duplicate/cooldown
        if self._should_suppress_alert(alert_id, severity):
            logger.debug("Alert suppressed due to cooldown: %s", alert_id)
            return None

        # Create alert
        alert = Alert(
            id=alert_id,
            severity=severity,
            category=category,
            title=title,
            message=message,
            timestamp=datetime.now(timezone.utc),
            source=source,
            metadata=metadata or {},
        )

        # Store alert
        self._active_alerts[alert_id] = alert
        self._alert_history.append(alert)
        self._last_alert_times[alert_id] = alert.timestamp

        # Send through all enabled channels
        await self._send_alert_to_channels(alert)

        logger.info("Alert triggered: [%s] %s - %s", severity.value.upper(), title, message)

        return alert

    async def _send_alert_to_channels(self, alert: Alert) -> None:
        """Send alert through all enabled channels."""
        send_tasks = []

        for channel in self._alert_channels.values():
            if channel.enabled:
                send_tasks.append(self._send_to_channel(channel, alert))

        if send_tasks:
            results = await asyncio.gather(*send_tasks, return_exceptions=True)

            success_count = sum(1 for result in results if result is True)
            logger.debug("Alert sent to %d/%d channels successfully", success_count, len(send_tasks))

    async def _send_to_channel(self, channel: AlertChannel, alert: Alert) -> bool:
        """Send alert to a specific channel with error handling."""
        try:
            return await channel.send_alert(alert)
        except Exception as e:
            logger.error("Failed to send alert through channel %s: %s", channel.name, e)
            return False

    def _generate_alert_id(self, title: str, message: str, source: str) -> str:
        """Generate unique alert ID based on content."""
        content = f"{title}:{message}:{source}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _should_suppress_alert(self, alert_id: str, severity: AlertSeverity) -> bool:
        """Check if alert should be suppressed due to cooldown or rate limiting."""
        now = datetime.now(timezone.utc)

        # Check cooldown period
        last_alert_time = self._last_alert_times.get(alert_id)
        if last_alert_time:
            cooldown_minutes = 15  # Default cooldown
            if now - last_alert_time < timedelta(minutes=cooldown_minutes):
                return True

        # Check rate limiting (max 5 alerts per minute for same ID)
        alert_times = self._alert_counts[alert_id]
        cutoff_time = now - timedelta(minutes=1)

        # Remove old entries
        while alert_times and alert_times[0] < cutoff_time:
            alert_times.popleft()

        # Check if rate limit exceeded
        if len(alert_times) >= 5:
            return True

        # Record this alert time
        alert_times.append(now)

        return False

    async def resolve_alert(self, alert_id: str, resolved_by: Optional[str] = None) -> bool:
        """
        Resolve an active alert.

        Args:
            alert_id: ID of the alert to resolve
            resolved_by: Who resolved the alert

        Returns:
            True if alert was resolved, False if not found
        """
        if alert_id in self._active_alerts:
            alert = self._active_alerts[alert_id]
            alert.resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            alert.resolved_by = resolved_by

            # Remove from active alerts
            del self._active_alerts[alert_id]

            logger.info("Alert resolved: %s by %s", alert_id, resolved_by or "system")
            return True

        return False

    async def start_monitoring(self) -> None:
        """Start background alert monitoring."""
        if self._monitoring_task and not self._monitoring_task.done():
            logger.warning("Alert monitoring already running")
            return

        self._monitoring_enabled = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())

        logger.info("Started MCP alert monitoring")

    async def stop_monitoring(self) -> None:
        """Stop background alert monitoring."""
        self._monitoring_enabled = False

        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped MCP alert monitoring")

    async def _monitoring_loop(self) -> None:
        """Background monitoring loop for checking alert conditions."""
        while self._monitoring_enabled:
            try:
                # Collect current metrics
                metrics = await self._collect_monitoring_metrics()

                # Check all alert rules
                for rule in self._alert_rules.values():
                    if rule.enabled and rule.condition(metrics):
                        await self._handle_rule_trigger(rule, metrics)

                # Auto-resolve alerts that are no longer triggered
                await self._auto_resolve_alerts(metrics)

                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in alert monitoring loop: %s", e)
                await asyncio.sleep(30)

    async def _collect_monitoring_metrics(self) -> Dict[str, Any]:
        """Collect current metrics for alert rule evaluation."""
        metrics = {}

        try:
            # Get performance metrics
            perf_health = await mcp_performance_monitor.get_health_status()
            if perf_health:
                summary = perf_health.get("performance_summary", {}).get("summary", {})
                system_metrics = perf_health.get("system_metrics", {}).get("metrics", {})

                metrics.update(
                    {
                        "error_rate": summary.get("overall_error_rate", 0),
                        "avg_response_time": 0,  # Would need to be calculated
                        "cpu_usage": system_metrics.get("cpu_usage", {}).get("current", 0),
                        "memory_usage_mb": system_metrics.get("memory_usage", {}).get("current", 0),
                        "concurrent_tools": system_metrics.get("concurrent_tools", {}).get("current", 0),
                    }
                )

            # Get recovery manager health
            recovery_health = await mcp_recovery_manager.get_recovery_health_status()
            if recovery_health:
                cb_health = recovery_health.get("circuit_breakers", {})
                metrics["circuit_breaker_open"] = not cb_health.get("healthy", True)

            # Check server status
            metrics["server_running"] = True  # Would check actual server status

            # Add timestamp
            metrics["timestamp"] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            logger.error("Failed to collect monitoring metrics: %s", e)
            metrics = {"error": str(e)}

        return metrics

    async def _handle_rule_trigger(self, rule: AlertRule, metrics: Dict[str, Any]) -> None:
        """Handle when an alert rule is triggered."""
        # Create alert message with context
        message = rule.description
        if rule.threshold_value is not None:
            current_value = metrics.get(rule.name.replace("high_", "").replace("_", "_"), 0)
            message += f" (current: {current_value}, threshold: {rule.threshold_value})"

        await self.trigger_alert(
            severity=rule.severity,
            category=rule.category,
            title=rule.name.replace("_", " ").title(),
            message=message,
            source="alert_rule",
            metadata={"rule_name": rule.name, "threshold": rule.threshold_value, "metrics": metrics},
        )

    async def _auto_resolve_alerts(self, metrics: Dict[str, Any]) -> None:
        """Auto-resolve alerts that are no longer triggered."""
        to_resolve = []

        for alert_id, alert in self._active_alerts.items():
            # Check if the condition that triggered this alert is still true
            rule_name = alert.metadata.get("rule_name")
            if rule_name and rule_name in self._alert_rules:
                rule = self._alert_rules[rule_name]
                if not rule.condition(metrics):
                    to_resolve.append(alert_id)

        # Resolve alerts
        for alert_id in to_resolve:
            await self.resolve_alert(alert_id, "auto_resolved")

    async def get_alert_status(self) -> Dict[str, Any]:
        """Get current alert system status."""
        # Test channel connectivity
        channel_status = {}
        for name, channel in self._alert_channels.items():
            try:
                channel_status[name] = {"enabled": channel.enabled, "connected": await channel.test_connection()}
            except Exception as e:
                channel_status[name] = {"enabled": channel.enabled, "connected": False, "error": str(e)}

        return {
            "monitoring_enabled": self._monitoring_enabled,
            "active_alerts": len(self._active_alerts),
            "total_rules": len(self._alert_rules),
            "enabled_rules": sum(1 for rule in self._alert_rules.values() if rule.enabled),
            "channels": channel_status,
            "recent_alerts": len(
                [
                    alert
                    for alert in self._alert_history
                    if alert.timestamp > datetime.now(timezone.utc) - timedelta(hours=24)
                ]
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get list of active alerts."""
        return [alert.to_dict() for alert in self._active_alerts.values()]

    def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get alert history for specified time period."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        return [alert.to_dict() for alert in self._alert_history if alert.timestamp >= cutoff_time]


# Global alert manager instance
mcp_alert_manager = MCPAlertManager()


# Convenience functions for triggering alerts
async def alert_server_failure(message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Trigger server failure alert."""
    await mcp_alert_manager.trigger_alert(
        AlertSeverity.CRITICAL, AlertCategory.SERVER_HEALTH, "MCP Server Failure", message, metadata=metadata
    )


async def alert_performance_issue(message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Trigger performance issue alert."""
    await mcp_alert_manager.trigger_alert(
        AlertSeverity.WARNING, AlertCategory.PERFORMANCE, "MCP Performance Issue", message, metadata=metadata
    )


async def alert_security_incident(message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Trigger security incident alert."""
    await mcp_alert_manager.trigger_alert(
        AlertSeverity.ERROR, AlertCategory.SECURITY, "MCP Security Incident", message, metadata=metadata
    )


async def alert_suspicious_activity(message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Trigger suspicious activity alert."""
    await mcp_alert_manager.trigger_alert(
        AlertSeverity.WARNING, AlertCategory.SUSPICIOUS_ACTIVITY, "MCP Suspicious Activity", message, metadata=metadata
    )


# Decorator for automatic alerting on function failures
def alert_on_failure(
    severity: AlertSeverity = AlertSeverity.ERROR,
    category: AlertCategory = AlertCategory.ERROR_RATE,
    custom_message: Optional[str] = None,
):
    """
    Decorator to automatically trigger alerts when functions fail.

    Args:
        severity: Alert severity level
        category: Alert category
        custom_message: Custom alert message template
    """

    def decorator(func: Callable) -> Callable:
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                message = custom_message or f"Function {func.__name__} failed: {str(e)}"

                # Get user context for metadata
                metadata = {"function": func.__name__, "error": str(e)}
                try:
                    user_context = get_mcp_user_context()
                    metadata["user_id"] = user_context.user_id
                    metadata["user_role"] = user_context.role
                except Exception:  # TODO: Use specific exception type
                    pass

                await mcp_alert_manager.trigger_alert(
                    severity=severity,
                    category=category,
                    title=f"Function Failure: {func.__name__}",
                    message=message,
                    source="function_decorator",
                    metadata=metadata,
                )

                raise

        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                message = custom_message or f"Function {func.__name__} failed: {str(e)}"

                # Create alert task
                asyncio.create_task(
                    mcp_alert_manager.trigger_alert(
                        severity=severity,
                        category=category,
                        title=f"Function Failure: {func.__name__}",
                        message=message,
                        source="function_decorator",
                        metadata={"function": func.__name__, "error": str(e)},
                    )
                )

                raise

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
