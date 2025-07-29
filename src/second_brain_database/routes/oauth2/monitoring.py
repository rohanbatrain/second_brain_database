"""
OAuth2 monitoring and alerting system.

This module provides comprehensive monitoring capabilities for OAuth2 operations,
including performance monitoring, security alerting, and health checks.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.datetime_utils import utc_now

from .logging_utils import (
    oauth2_logger,
    log_performance_event,
    log_rate_limit_event,
    OAuth2EventType
)

try:
    from .metrics import oauth2_metrics
    METRICS_AVAILABLE = True
except ImportError:
    oauth2_metrics = None
    METRICS_AVAILABLE = False

logger = get_logger(prefix="[OAuth2 Monitoring]")


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of OAuth2 alerts."""
    
    PERFORMANCE = "performance"
    SECURITY = "security"
    AVAILABILITY = "availability"
    COMPLIANCE = "compliance"
    RATE_LIMIT = "rate_limit"
    ERROR_RATE = "error_rate"


@dataclass
class AlertRule:
    """OAuth2 alert rule configuration."""
    
    name: str
    alert_type: AlertType
    severity: AlertSeverity
    condition: str
    threshold: float
    time_window: int  # seconds
    description: str
    enabled: bool = True
    cooldown: int = 300  # 5 minutes default cooldown


@dataclass
class Alert:
    """OAuth2 alert instance."""
    
    alert_id: str
    rule_name: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    context: Optional[Dict[str, Any]] = None
    acknowledged: bool = False


class OAuth2MonitoringSystem:
    """
    Comprehensive OAuth2 monitoring and alerting system.
    
    Provides real-time monitoring of OAuth2 operations with configurable
    alerting rules and performance tracking.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[OAuth2 Monitoring System]")
        
        # Redis keys for monitoring data
        self.METRICS_KEY = "oauth2:monitoring:metrics"
        self.ALERTS_KEY = "oauth2:monitoring:alerts"
        self.HEALTH_KEY = "oauth2:monitoring:health"
        self.PERFORMANCE_KEY = "oauth2:monitoring:performance"
        
        # Alert rules
        self.alert_rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        
        # Performance thresholds
        self.performance_thresholds = {
            "authorization_request_time": 2.0,  # seconds
            "token_request_time": 1.0,          # seconds
            "token_generation_time": 0.5,       # seconds
            "database_operation_time": 0.3      # seconds
        }
        
        # Initialize default alert rules
        self._initialize_default_alert_rules()
        
        # Start monitoring tasks
        self._monitoring_tasks: List[asyncio.Task] = []
    
    def _initialize_default_alert_rules(self) -> None:
        """Initialize default OAuth2 alert rules."""
        
        default_rules = [
            AlertRule(
                name="high_error_rate",
                alert_type=AlertType.ERROR_RATE,
                severity=AlertSeverity.HIGH,
                condition="error_rate > threshold",
                threshold=0.05,  # 5% error rate
                time_window=300,  # 5 minutes
                description="OAuth2 error rate exceeds 5% over 5 minutes"
            ),
            AlertRule(
                name="slow_authorization_requests",
                alert_type=AlertType.PERFORMANCE,
                severity=AlertSeverity.MEDIUM,
                condition="avg_authorization_time > threshold",
                threshold=3.0,  # 3 seconds
                time_window=300,
                description="Average authorization request time exceeds 3 seconds"
            ),
            AlertRule(
                name="slow_token_requests",
                alert_type=AlertType.PERFORMANCE,
                severity=AlertSeverity.MEDIUM,
                condition="avg_token_time > threshold",
                threshold=2.0,  # 2 seconds
                time_window=300,
                description="Average token request time exceeds 2 seconds"
            ),
            AlertRule(
                name="high_rate_limit_hits",
                alert_type=AlertType.RATE_LIMIT,
                severity=AlertSeverity.MEDIUM,
                condition="rate_limit_hits > threshold",
                threshold=100,  # 100 hits per window
                time_window=300,
                description="High number of rate limit hits detected"
            ),
            AlertRule(
                name="security_violations",
                alert_type=AlertType.SECURITY,
                severity=AlertSeverity.HIGH,
                condition="security_violations > threshold",
                threshold=10,  # 10 violations per window
                time_window=300,
                description="Multiple security violations detected"
            ),
            AlertRule(
                name="critical_security_event",
                alert_type=AlertType.SECURITY,
                severity=AlertSeverity.CRITICAL,
                condition="critical_security_events > threshold",
                threshold=1,  # Any critical event
                time_window=60,
                description="Critical security event detected"
            ),
            AlertRule(
                name="oauth2_service_unavailable",
                alert_type=AlertType.AVAILABILITY,
                severity=AlertSeverity.CRITICAL,
                condition="service_availability < threshold",
                threshold=0.95,  # 95% availability
                time_window=300,
                description="OAuth2 service availability below 95%"
            )
        ]
        
        for rule in default_rules:
            self.alert_rules[rule.name] = rule
    
    async def start_monitoring(self) -> None:
        """Start OAuth2 monitoring tasks."""
        try:
            # Start monitoring tasks
            self._monitoring_tasks = [
                asyncio.create_task(self._monitor_performance()),
                asyncio.create_task(self._monitor_error_rates()),
                asyncio.create_task(self._monitor_security_events()),
                asyncio.create_task(self._monitor_rate_limits()),
                asyncio.create_task(self._check_alert_rules()),
                asyncio.create_task(self._update_health_status())
            ]
            
            self.logger.info("OAuth2 monitoring system started")
            
        except Exception as e:
            self.logger.error(f"Failed to start OAuth2 monitoring: {e}", exc_info=True)
            raise
    
    async def stop_monitoring(self) -> None:
        """Stop OAuth2 monitoring tasks."""
        try:
            for task in self._monitoring_tasks:
                task.cancel()
            
            await asyncio.gather(*self._monitoring_tasks, return_exceptions=True)
            self._monitoring_tasks.clear()
            
            self.logger.info("OAuth2 monitoring system stopped")
            
        except Exception as e:
            self.logger.error(f"Failed to stop OAuth2 monitoring: {e}", exc_info=True)
    
    async def record_performance_metric(
        self,
        metric_name: str,
        value: float,
        client_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Record OAuth2 performance metric.
        
        Args:
            metric_name: Name of the performance metric
            value: Metric value
            client_id: OAuth2 client identifier
            labels: Additional metric labels
        """
        try:
            timestamp = utc_now().timestamp()
            
            metric_data = {
                "metric_name": metric_name,
                "value": value,
                "client_id": client_id,
                "labels": labels or {},
                "timestamp": timestamp
            }
            
            # Store in Redis time series
            metric_key = f"{self.PERFORMANCE_KEY}:{metric_name}"
            await redis_manager.zadd(metric_key, {json.dumps(metric_data): timestamp})
            
            # Keep only last hour of data
            cutoff_time = timestamp - 3600
            await redis_manager.zremrangebyscore(metric_key, 0, cutoff_time)
            
            # Check performance thresholds
            if metric_name in self.performance_thresholds:
                threshold = self.performance_thresholds[metric_name]
                if value > threshold:
                    await self._trigger_performance_alert(metric_name, value, threshold, client_id)
            
            # Log performance event if slow
            if value > 1.0:  # Log operations taking more than 1 second
                log_performance_event(
                    operation=metric_name,
                    duration=value,
                    client_id=client_id,
                    success=True
                )
            
        except Exception as e:
            self.logger.error(f"Failed to record performance metric: {e}", exc_info=True)
    
    async def record_error_event(
        self,
        error_type: str,
        error_code: str,
        client_id: Optional[str] = None,
        severity: str = "medium"
    ) -> None:
        """
        Record OAuth2 error event for monitoring.
        
        Args:
            error_type: Type of error
            error_code: OAuth2 error code
            client_id: OAuth2 client identifier
            severity: Error severity level
        """
        try:
            timestamp = utc_now().timestamp()
            
            error_data = {
                "error_type": error_type,
                "error_code": error_code,
                "client_id": client_id,
                "severity": severity,
                "timestamp": timestamp
            }
            
            # Store in Redis
            error_key = f"{self.METRICS_KEY}:errors"
            await redis_manager.zadd(error_key, {json.dumps(error_data): timestamp})
            
            # Keep only last hour of data
            cutoff_time = timestamp - 3600
            await redis_manager.zremrangebyscore(error_key, 0, cutoff_time)
            
        except Exception as e:
            self.logger.error(f"Failed to record error event: {e}", exc_info=True)
    
    async def record_security_event(
        self,
        event_type: str,
        severity: str,
        client_id: Optional[str] = None,
        description: str = ""
    ) -> None:
        """
        Record OAuth2 security event for monitoring.
        
        Args:
            event_type: Type of security event
            severity: Event severity level
            client_id: OAuth2 client identifier
            description: Event description
        """
        try:
            timestamp = utc_now().timestamp()
            
            security_data = {
                "event_type": event_type,
                "severity": severity,
                "client_id": client_id,
                "description": description,
                "timestamp": timestamp
            }
            
            # Store in Redis
            security_key = f"{self.METRICS_KEY}:security"
            await redis_manager.zadd(security_key, {json.dumps(security_data): timestamp})
            
            # Keep only last 24 hours of security events
            cutoff_time = timestamp - 86400
            await redis_manager.zremrangebyscore(security_key, 0, cutoff_time)
            
            # Trigger immediate alert for critical security events
            if severity == "critical":
                await self._trigger_security_alert(event_type, severity, client_id, description)
            
        except Exception as e:
            self.logger.error(f"Failed to record security event: {e}", exc_info=True)
    
    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get OAuth2 system health status.
        
        Returns:
            Health status information
        """
        try:
            health_data = await redis_manager.get(self.HEALTH_KEY)
            if health_data:
                return json.loads(health_data)
            
            # Generate health status if not cached
            return await self._calculate_health_status()
            
        except Exception as e:
            self.logger.error(f"Failed to get health status: {e}", exc_info=True)
            return {
                "status": "unknown",
                "error": str(e),
                "timestamp": utc_now().isoformat()
            }
    
    async def get_performance_metrics(
        self,
        metric_name: Optional[str] = None,
        time_window: int = 3600
    ) -> Dict[str, Any]:
        """
        Get OAuth2 performance metrics.
        
        Args:
            metric_name: Specific metric name to retrieve
            time_window: Time window in seconds
            
        Returns:
            Performance metrics data
        """
        try:
            current_time = utc_now().timestamp()
            start_time = current_time - time_window
            
            metrics = {}
            
            if metric_name:
                metric_keys = [f"{self.PERFORMANCE_KEY}:{metric_name}"]
            else:
                # Get all performance metrics
                pattern = f"{self.PERFORMANCE_KEY}:*"
                metric_keys = await redis_manager.keys(pattern)
            
            for key in metric_keys:
                metric_data = await redis_manager.zrangebyscore(
                    key, start_time, current_time, withscores=True
                )
                
                if metric_data:
                    metric_name_key = key.split(":")[-1]
                    values = []
                    
                    for data, timestamp in metric_data:
                        try:
                            parsed_data = json.loads(data)
                            values.append({
                                "value": parsed_data["value"],
                                "timestamp": timestamp,
                                "client_id": parsed_data.get("client_id"),
                                "labels": parsed_data.get("labels", {})
                            })
                        except json.JSONDecodeError:
                            continue
                    
                    if values:
                        metrics[metric_name_key] = {
                            "values": values,
                            "count": len(values),
                            "avg": sum(v["value"] for v in values) / len(values),
                            "min": min(v["value"] for v in values),
                            "max": max(v["value"] for v in values)
                        }
            
            return {
                "metrics": metrics,
                "time_window": time_window,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}", exc_info=True)
            return {}
    
    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """
        Get active OAuth2 alerts.
        
        Returns:
            List of active alerts
        """
        try:
            alerts_data = await redis_manager.get(f"{self.ALERTS_KEY}:active")
            if alerts_data:
                alerts = json.loads(alerts_data)
                return [alert for alert in alerts if not alert.get("resolved_at")]
            
            return []
            
        except Exception as e:
            self.logger.error(f"Failed to get active alerts: {e}", exc_info=True)
            return []
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> bool:
        """
        Acknowledge an OAuth2 alert.
        
        Args:
            alert_id: Alert identifier
            acknowledged_by: User who acknowledged the alert
            
        Returns:
            True if alert was acknowledged successfully
        """
        try:
            alerts_data = await redis_manager.get(f"{self.ALERTS_KEY}:active")
            if not alerts_data:
                return False
            
            alerts = json.loads(alerts_data)
            
            for alert in alerts:
                if alert["alert_id"] == alert_id:
                    alert["acknowledged"] = True
                    alert["acknowledged_by"] = acknowledged_by
                    alert["acknowledged_at"] = datetime.utcnow().isoformat()
                    break
            else:
                return False
            
            # Update alerts in Redis
            await redis_manager.set(f"{self.ALERTS_KEY}:active", json.dumps(alerts, default=str))
            
            self.logger.info(f"OAuth2 alert acknowledged: {alert_id} by {acknowledged_by}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to acknowledge alert: {e}", exc_info=True)
            return False
    
    async def _monitor_performance(self) -> None:
        """Monitor OAuth2 performance metrics."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # Get recent performance data
                current_time = datetime.utcnow().timestamp()
                start_time = current_time - 300  # Last 5 minutes
                
                for metric_name, threshold in self.performance_thresholds.items():
                    metric_key = f"{self.PERFORMANCE_KEY}:{metric_name}"
                    recent_data = await redis_manager.zrangebyscore(metric_key, start_time, current_time)
                    
                    if recent_data:
                        values = []
                        for data in recent_data:
                            try:
                                parsed_data = json.loads(data)
                                values.append(parsed_data["value"])
                            except json.JSONDecodeError:
                                continue
                        
                        if values:
                            avg_value = sum(values) / len(values)
                            if avg_value > threshold:
                                await self._trigger_performance_alert(metric_name, avg_value, threshold)
                
            except Exception as e:
                self.logger.error(f"Error in performance monitoring: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _monitor_error_rates(self) -> None:
        """Monitor OAuth2 error rates."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.utcnow().timestamp()
                start_time = current_time - 300  # Last 5 minutes
                
                # Get error events
                error_key = f"{self.METRICS_KEY}:errors"
                error_data = await redis_manager.zrangebyscore(error_key, start_time, current_time)
                
                # Get total requests (would need to be tracked separately)
                # For now, we'll use a simplified approach
                error_count = len(error_data)
                
                if error_count > 50:  # More than 50 errors in 5 minutes
                    await self._trigger_error_rate_alert(error_count, 300)
                
            except Exception as e:
                self.logger.error(f"Error in error rate monitoring: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _monitor_security_events(self) -> None:
        """Monitor OAuth2 security events."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                current_time = datetime.utcnow().timestamp()
                start_time = current_time - 300  # Last 5 minutes
                
                security_key = f"{self.METRICS_KEY}:security"
                security_data = await redis_manager.zrangebyscore(security_key, start_time, current_time)
                
                critical_events = 0
                high_events = 0
                
                for data in security_data:
                    try:
                        parsed_data = json.loads(data)
                        severity = parsed_data.get("severity", "low")
                        if severity == "critical":
                            critical_events += 1
                        elif severity == "high":
                            high_events += 1
                    except json.JSONDecodeError:
                        continue
                
                if critical_events > 0:
                    await self._trigger_security_alert("multiple_critical_events", "critical", None, 
                                                     f"{critical_events} critical security events in 5 minutes")
                elif high_events > 5:
                    await self._trigger_security_alert("multiple_high_events", "high", None,
                                                     f"{high_events} high severity security events in 5 minutes")
                
            except Exception as e:
                self.logger.error(f"Error in security event monitoring: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _monitor_rate_limits(self) -> None:
        """Monitor OAuth2 rate limit hits."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                # This would integrate with the actual rate limiting system
                # For now, we'll implement a placeholder
                
                await asyncio.sleep(60)
                
            except Exception as e:
                self.logger.error(f"Error in rate limit monitoring: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _check_alert_rules(self) -> None:
        """Check alert rules and trigger alerts."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                
                for rule_name, rule in self.alert_rules.items():
                    if not rule.enabled:
                        continue
                    
                    # Check if rule is in cooldown
                    cooldown_key = f"{self.ALERTS_KEY}:cooldown:{rule_name}"
                    if await redis_manager.exists(cooldown_key):
                        continue
                    
                    # Evaluate rule condition (simplified implementation)
                    should_trigger = await self._evaluate_alert_rule(rule)
                    
                    if should_trigger:
                        await self._trigger_alert(rule)
                
            except Exception as e:
                self.logger.error(f"Error in alert rule checking: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _update_health_status(self) -> None:
        """Update OAuth2 system health status."""
        while True:
            try:
                await asyncio.sleep(30)  # Update every 30 seconds
                
                health_status = await self._calculate_health_status()
                await redis_manager.setex(self.HEALTH_KEY, 60, json.dumps(health_status, default=str))
                
            except Exception as e:
                self.logger.error(f"Error updating health status: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _calculate_health_status(self) -> Dict[str, Any]:
        """Calculate OAuth2 system health status."""
        try:
            current_time = datetime.utcnow().timestamp()
            start_time = current_time - 300  # Last 5 minutes
            
            # Check error rates
            error_key = f"{self.METRICS_KEY}:errors"
            error_count = await redis_manager.zcount(error_key, start_time, current_time)
            
            # Check security events
            security_key = f"{self.METRICS_KEY}:security"
            security_count = await redis_manager.zcount(security_key, start_time, current_time)
            
            # Check active alerts
            active_alerts = await self.get_active_alerts()
            critical_alerts = [a for a in active_alerts if a.get("severity") == "critical"]
            
            # Determine overall health status
            if critical_alerts:
                status = "critical"
            elif error_count > 100 or security_count > 20:
                status = "degraded"
            elif error_count > 50 or security_count > 10:
                status = "warning"
            else:
                status = "healthy"
            
            return {
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": {
                    "error_count_5min": error_count,
                    "security_events_5min": security_count,
                    "active_alerts": len(active_alerts),
                    "critical_alerts": len(critical_alerts)
                },
                "components": {
                    "authorization_endpoint": "healthy",  # Would check actual endpoint health
                    "token_endpoint": "healthy",
                    "metrics_collection": "healthy" if METRICS_AVAILABLE else "degraded",
                    "audit_logging": "healthy"
                }
            }
            
        except Exception as e:
            return {
                "status": "unknown",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _evaluate_alert_rule(self, rule: AlertRule) -> bool:
        """Evaluate if an alert rule should trigger."""
        # Simplified rule evaluation - in a real implementation,
        # this would parse and evaluate the rule condition
        return False
    
    async def _trigger_alert(self, rule: AlertRule) -> None:
        """Trigger an alert based on a rule."""
        try:
            alert_id = f"alert_{rule.name}_{datetime.utcnow().timestamp()}"
            
            alert = Alert(
                alert_id=alert_id,
                rule_name=rule.name,
                alert_type=rule.alert_type,
                severity=rule.severity,
                message=rule.description,
                triggered_at=datetime.utcnow()
            )
            
            # Store alert
            alerts_data = await redis_manager.get(f"{self.ALERTS_KEY}:active") or "[]"
            alerts = json.loads(alerts_data)
            alerts.append(alert.__dict__)
            
            await redis_manager.set(f"{self.ALERTS_KEY}:active", json.dumps(alerts, default=str))
            
            # Set cooldown
            await redis_manager.setex(f"{self.ALERTS_KEY}:cooldown:{rule.name}", rule.cooldown, "1")
            
            # Log alert
            self.logger.warning(f"OAuth2 alert triggered: {rule.name} - {rule.description}")
            
        except Exception as e:
            self.logger.error(f"Failed to trigger alert: {e}", exc_info=True)
    
    async def _trigger_performance_alert(
        self,
        metric_name: str,
        value: float,
        threshold: float,
        client_id: Optional[str] = None
    ) -> None:
        """Trigger performance-related alert."""
        message = f"Performance threshold exceeded: {metric_name} = {value:.2f}s (threshold: {threshold:.2f}s)"
        if client_id:
            message += f" for client {client_id}"
        
        self.logger.warning(f"OAuth2 performance alert: {message}")
    
    async def _trigger_security_alert(
        self,
        event_type: str,
        severity: str,
        client_id: Optional[str],
        description: str
    ) -> None:
        """Trigger security-related alert."""
        message = f"Security event: {event_type} - {description}"
        if client_id:
            message += f" (client: {client_id})"
        
        if severity == "critical":
            self.logger.critical(f"OAuth2 CRITICAL security alert: {message}")
        else:
            self.logger.error(f"OAuth2 security alert: {message}")
    
    async def _trigger_error_rate_alert(self, error_count: int, time_window: int) -> None:
        """Trigger error rate alert."""
        message = f"High error rate: {error_count} errors in {time_window} seconds"
        self.logger.error(f"OAuth2 error rate alert: {message}")


# Global OAuth2 monitoring system instance
oauth2_monitoring = OAuth2MonitoringSystem()


# Convenience functions for monitoring operations
async def record_performance_metric(
    metric_name: str,
    value: float,
    client_id: Optional[str] = None,
    labels: Optional[Dict[str, str]] = None
) -> None:
    """Record OAuth2 performance metric."""
    await oauth2_monitoring.record_performance_metric(metric_name, value, client_id, labels)


async def record_error_event(
    error_type: str,
    error_code: str,
    client_id: Optional[str] = None,
    severity: str = "medium"
) -> None:
    """Record OAuth2 error event."""
    await oauth2_monitoring.record_error_event(error_type, error_code, client_id, severity)


async def record_security_event(
    event_type: str,
    severity: str,
    client_id: Optional[str] = None,
    description: str = ""
) -> None:
    """Record OAuth2 security event."""
    await oauth2_monitoring.record_security_event(event_type, severity, client_id, description)


async def get_health_status() -> Dict[str, Any]:
    """Get OAuth2 system health status."""
    return await oauth2_monitoring.get_health_status()


async def start_monitoring() -> None:
    """Start OAuth2 monitoring system."""
    await oauth2_monitoring.start_monitoring()


async def stop_monitoring() -> None:
    """Stop OAuth2 monitoring system."""
    await oauth2_monitoring.stop_monitoring()