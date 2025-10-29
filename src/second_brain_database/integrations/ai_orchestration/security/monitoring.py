"""
AI Security Monitoring Service

This module provides real-time security monitoring and alerting for AI operations,
integrating with existing security infrastructure and adding AI-specific monitoring.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta
import asyncio
import json
from enum import Enum

from ....managers.logging_manager import get_logger
from ....managers.redis_manager import redis_manager
from .config import ai_security_config
from .ai_security_manager import ai_security_manager

logger = get_logger(prefix="[AISecurityMonitoring]")


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityAlert:
    """Security alert data structure."""
    
    def __init__(
        self,
        alert_type: str,
        severity: AlertSeverity,
        message: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        self.alert_id = f"ai_alert_{datetime.now(timezone.utc).timestamp()}"
        self.alert_type = alert_type
        self.severity = severity
        self.message = message
        self.details = details
        self.user_id = user_id
        self.session_id = session_id
        self.timestamp = datetime.now(timezone.utc)
        self.resolved = False
        self.resolution_notes = ""


class AISecurityMonitoring:
    """
    AI security monitoring service.
    """
    
    def __init__(self):
        self.logger = logger
        self.env_prefix = getattr(ai_security_config, "ENV_PREFIX", "dev")
        self.monitoring_enabled = True
        self.active_alerts: Dict[str, SecurityAlert] = {}
        
        # Monitoring intervals
        self.monitoring_intervals = {
            "threat_detection": 30,  # seconds
            "quota_monitoring": 60,  # seconds
            "session_monitoring": 120,  # seconds
            "performance_monitoring": 300  # seconds
        }

    async def get_redis(self):
        """Get Redis connection."""
        return await redis_manager.get_redis()

    async def start_monitoring(self):
        """Start all monitoring tasks."""
        if not self.monitoring_enabled:
            return
        
        self.logger.info("Starting AI security monitoring")
        
        # Start monitoring tasks
        tasks = [
            asyncio.create_task(self._monitor_threats()),
            asyncio.create_task(self._monitor_quotas()),
            asyncio.create_task(self._monitor_sessions()),
            asyncio.create_task(self._monitor_performance())
        ]
        
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_monitoring(self):
        """Stop monitoring."""
        self.monitoring_enabled = False
        self.logger.info("Stopped AI security monitoring")

    async def _monitor_threats(self):
        """Monitor for security threats."""
        while self.monitoring_enabled:
            try:
                await self._check_rapid_requests()
                await self._check_suspicious_patterns()
                await self._check_failed_authentications()
                
                await asyncio.sleep(self.monitoring_intervals["threat_detection"])
                
            except Exception as e:
                self.logger.error("Error in threat monitoring: %s", str(e), exc_info=True)
                await asyncio.sleep(self.monitoring_intervals["threat_detection"])

    async def _monitor_quotas(self):
        """Monitor AI usage quotas."""
        while self.monitoring_enabled:
            try:
                await self._check_quota_violations()
                await self._check_rate_limit_violations()
                
                await asyncio.sleep(self.monitoring_intervals["quota_monitoring"])
                
            except Exception as e:
                self.logger.error("Error in quota monitoring: %s", str(e), exc_info=True)
                await asyncio.sleep(self.monitoring_intervals["quota_monitoring"])

    async def _monitor_sessions(self):
        """Monitor AI sessions for anomalies."""
        while self.monitoring_enabled:
            try:
                await self._check_session_anomalies()
                await self._check_expired_sessions()
                
                await asyncio.sleep(self.monitoring_intervals["session_monitoring"])
                
            except Exception as e:
                self.logger.error("Error in session monitoring: %s", str(e), exc_info=True)
                await asyncio.sleep(self.monitoring_intervals["session_monitoring"])

    async def _monitor_performance(self):
        """Monitor AI performance metrics."""
        while self.monitoring_enabled:
            try:
                await self._check_performance_anomalies()
                await self._check_resource_usage()
                
                await asyncio.sleep(self.monitoring_intervals["performance_monitoring"])
                
            except Exception as e:
                self.logger.error("Error in performance monitoring: %s", str(e), exc_info=True)
                await asyncio.sleep(self.monitoring_intervals["performance_monitoring"])

    async def _check_rapid_requests(self):
        """Check for rapid request patterns."""
        try:
            redis_conn = await self.get_redis()
            threshold_config = ai_security_config.get_monitoring_threshold("high_frequency_requests")
            
            if not threshold_config:
                return
            
            threshold = threshold_config.get("threshold", 100)
            window = threshold_config.get("window", 300)
            
            # Get all user request rate keys
            rate_keys = await redis_conn.keys(f"{self.env_prefix}:ai_request_rate:*")
            
            for key in rate_keys:
                try:
                    user_id = key.split(":")[-1]
                    
                    # Count requests in the window
                    now = datetime.now(timezone.utc).timestamp()
                    window_start = now - window
                    
                    request_count = await redis_conn.zcount(key, window_start, now)
                    
                    if request_count > threshold:
                        await self._create_alert(
                            alert_type="rapid_requests",
                            severity=AlertSeverity.HIGH,
                            message=f"User {user_id} exceeded request threshold",
                            details={
                                "user_id": user_id,
                                "request_count": request_count,
                                "threshold": threshold,
                                "window_seconds": window
                            },
                            user_id=user_id
                        )
                        
                except Exception as e:
                    self.logger.warning("Error checking rapid requests for key %s: %s", key, str(e))
                    
        except Exception as e:
            self.logger.error("Error in rapid request monitoring: %s", str(e), exc_info=True)

    async def _check_suspicious_patterns(self):
        """Check for suspicious content patterns."""
        try:
            redis_conn = await self.get_redis()
            
            # Get recent audit events
            audit_keys = await redis_conn.keys(f"{self.env_prefix}:ai_audit:*")
            
            for key in audit_keys[-100:]:  # Check last 100 events
                try:
                    audit_data = await redis_conn.get(key)
                    if not audit_data:
                        continue
                    
                    audit_event = json.loads(audit_data)
                    
                    # Check for suspicious patterns in event details
                    if self._contains_suspicious_patterns(audit_event):
                        await self._create_alert(
                            alert_type="suspicious_content",
                            severity=AlertSeverity.MEDIUM,
                            message="Suspicious content pattern detected",
                            details={
                                "event_id": audit_event.get("event_id"),
                                "user_id": audit_event.get("user_id"),
                                "action": audit_event.get("action"),
                                "timestamp": audit_event.get("timestamp")
                            },
                            user_id=audit_event.get("user_id"),
                            session_id=audit_event.get("session_id")
                        )
                        
                except Exception as e:
                    self.logger.warning("Error checking suspicious patterns for key %s: %s", key, str(e))
                    
        except Exception as e:
            self.logger.error("Error in suspicious pattern monitoring: %s", str(e), exc_info=True)

    async def _check_failed_authentications(self):
        """Check for failed authentication attempts."""
        try:
            redis_conn = await self.get_redis()
            threshold_config = ai_security_config.get_monitoring_threshold("failed_authentications")
            
            if not threshold_config:
                return
            
            threshold = threshold_config.get("threshold", 10)
            window = threshold_config.get("window", 600)
            
            # Get failed authentication events
            failed_auth_keys = await redis_conn.keys(f"{self.env_prefix}:ai_failed_auth:*")
            
            for key in failed_auth_keys:
                try:
                    ip_address = key.split(":")[-1]
                    
                    # Count failed attempts in the window
                    now = datetime.now(timezone.utc).timestamp()
                    window_start = now - window
                    
                    failed_count = await redis_conn.zcount(key, window_start, now)
                    
                    if failed_count > threshold:
                        await self._create_alert(
                            alert_type="failed_authentications",
                            severity=AlertSeverity.HIGH,
                            message=f"Multiple failed authentications from IP {ip_address}",
                            details={
                                "ip_address": ip_address,
                                "failed_count": failed_count,
                                "threshold": threshold,
                                "window_seconds": window
                            }
                        )
                        
                except Exception as e:
                    self.logger.warning("Error checking failed auth for key %s: %s", key, str(e))
                    
        except Exception as e:
            self.logger.error("Error in failed authentication monitoring: %s", str(e), exc_info=True)

    async def _check_quota_violations(self):
        """Check for quota violations."""
        try:
            redis_conn = await self.get_redis()
            
            # Check daily quotas
            daily_quota_keys = await redis_conn.keys(f"{self.env_prefix}:ai_quota:daily:*")
            
            for key in daily_quota_keys:
                try:
                    user_id = key.split(":")[-1]
                    usage = await redis_conn.get(key)
                    
                    if usage and int(usage) > ai_security_config.AI_DAILY_QUOTA * 0.9:  # 90% threshold
                        await self._create_alert(
                            alert_type="quota_violation",
                            severity=AlertSeverity.MEDIUM,
                            message=f"User {user_id} approaching daily quota limit",
                            details={
                                "user_id": user_id,
                                "current_usage": int(usage),
                                "daily_quota": ai_security_config.AI_DAILY_QUOTA,
                                "percentage": (int(usage) / ai_security_config.AI_DAILY_QUOTA) * 100
                            },
                            user_id=user_id
                        )
                        
                except Exception as e:
                    self.logger.warning("Error checking quota for key %s: %s", key, str(e))
                    
        except Exception as e:
            self.logger.error("Error in quota monitoring: %s", str(e), exc_info=True)

    async def _check_rate_limit_violations(self):
        """Check for rate limit violations."""
        try:
            redis_conn = await self.get_redis()
            
            # Get rate limit violation keys
            rate_limit_keys = await redis_conn.keys(f"{self.env_prefix}:abuse:*")
            
            for key in rate_limit_keys:
                try:
                    ip_address = key.split(":")[-1]
                    abuse_count = await redis_conn.get(key)
                    
                    if abuse_count and int(abuse_count) > 5:  # Multiple violations
                        await self._create_alert(
                            alert_type="rate_limit_violations",
                            severity=AlertSeverity.HIGH,
                            message=f"Multiple rate limit violations from IP {ip_address}",
                            details={
                                "ip_address": ip_address,
                                "violation_count": int(abuse_count)
                            }
                        )
                        
                except Exception as e:
                    self.logger.warning("Error checking rate limits for key %s: %s", key, str(e))
                    
        except Exception as e:
            self.logger.error("Error in rate limit monitoring: %s", str(e), exc_info=True)

    async def _check_session_anomalies(self):
        """Check for session anomalies."""
        try:
            redis_conn = await self.get_redis()
            
            # Get all active sessions
            session_keys = await redis_conn.keys(f"{self.env_prefix}:ai_session:*")
            
            for key in session_keys:
                try:
                    session_data = await redis_conn.get(key)
                    if not session_data:
                        continue
                    
                    session_info = json.loads(session_data)
                    session_id = session_info.get("session_id")
                    user_id = session_info.get("user_id")
                    
                    # Check for long-running sessions
                    created_at = datetime.fromisoformat(session_info.get("created_at", ""))
                    session_duration = (datetime.now(timezone.utc) - created_at).total_seconds()
                    
                    if session_duration > ai_security_config.AI_SESSION_TIMEOUT * 2:  # Double the normal timeout
                        await self._create_alert(
                            alert_type="long_running_session",
                            severity=AlertSeverity.MEDIUM,
                            message=f"Long-running AI session detected",
                            details={
                                "session_id": session_id,
                                "user_id": user_id,
                                "duration_seconds": session_duration,
                                "normal_timeout": ai_security_config.AI_SESSION_TIMEOUT
                            },
                            user_id=user_id,
                            session_id=session_id
                        )
                        
                except Exception as e:
                    self.logger.warning("Error checking session anomaly for key %s: %s", key, str(e))
                    
        except Exception as e:
            self.logger.error("Error in session anomaly monitoring: %s", str(e), exc_info=True)

    async def _check_expired_sessions(self):
        """Check for and clean up expired sessions."""
        try:
            redis_conn = await self.get_redis()
            cleaned_count = 0
            
            # Get all session keys
            session_keys = await redis_conn.keys(f"{self.env_prefix}:ai_session:*")
            
            for key in session_keys:
                try:
                    ttl = await redis_conn.ttl(key)
                    if ttl == -2:  # Key doesn't exist
                        continue
                    elif ttl <= 0 and ttl != -1:  # Key has expired
                        await redis_conn.delete(key)
                        cleaned_count += 1
                        
                except Exception as e:
                    self.logger.warning("Error checking session expiration for key %s: %s", key, str(e))
            
            if cleaned_count > 0:
                self.logger.info("Cleaned up %d expired AI sessions", cleaned_count)
                
        except Exception as e:
            self.logger.error("Error in expired session cleanup: %s", str(e), exc_info=True)

    async def _check_performance_anomalies(self):
        """Check for performance anomalies."""
        try:
            # This would integrate with performance monitoring
            # For now, just log that we're monitoring
            self.logger.debug("Checking AI performance anomalies")
            
        except Exception as e:
            self.logger.error("Error in performance monitoring: %s", str(e), exc_info=True)

    async def _check_resource_usage(self):
        """Check resource usage patterns."""
        try:
            redis_conn = await self.get_redis()
            
            # Get memory usage info
            memory_info = await redis_conn.info("memory")
            used_memory = memory_info.get("used_memory", 0)
            max_memory = memory_info.get("maxmemory", 0)
            
            if max_memory > 0:
                memory_usage_percent = (used_memory / max_memory) * 100
                
                if memory_usage_percent > 90:  # 90% memory usage
                    await self._create_alert(
                        alert_type="high_memory_usage",
                        severity=AlertSeverity.HIGH,
                        message="High Redis memory usage detected",
                        details={
                            "used_memory": used_memory,
                            "max_memory": max_memory,
                            "usage_percent": memory_usage_percent
                        }
                    )
                    
        except Exception as e:
            self.logger.error("Error in resource usage monitoring: %s", str(e), exc_info=True)

    def _contains_suspicious_patterns(self, audit_event: Dict[str, Any]) -> bool:
        """Check if audit event contains suspicious patterns."""
        try:
            suspicious_patterns = ai_security_config.AI_SUSPICIOUS_PATTERNS
            
            # Check event details for suspicious content
            details = audit_event.get("details", {})
            
            for key, value in details.items():
                if isinstance(value, str):
                    value_lower = value.lower()
                    for pattern in suspicious_patterns:
                        if pattern in value_lower:
                            return True
            
            return False
            
        except Exception as e:
            self.logger.error("Error checking suspicious patterns: %s", str(e))
            return False

    async def _create_alert(
        self,
        alert_type: str,
        severity: AlertSeverity,
        message: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Create and store security alert."""
        try:
            alert = SecurityAlert(
                alert_type=alert_type,
                severity=severity,
                message=message,
                details=details,
                user_id=user_id,
                session_id=session_id
            )
            
            # Store alert
            self.active_alerts[alert.alert_id] = alert
            
            # Store in Redis
            redis_conn = await self.get_redis()
            alert_key = f"{self.env_prefix}:ai_security_alert:{alert.alert_id}"
            alert_data = {
                "alert_id": alert.alert_id,
                "alert_type": alert.alert_type,
                "severity": alert.severity.value,
                "message": alert.message,
                "details": alert.details,
                "user_id": alert.user_id,
                "session_id": alert.session_id,
                "timestamp": alert.timestamp.isoformat(),
                "resolved": alert.resolved
            }
            
            await redis_conn.setex(alert_key, 7 * 24 * 3600, json.dumps(alert_data))  # 7 days
            
            # Log alert
            self.logger.warning(
                "AI security alert created: %s - %s (severity: %s)",
                alert.alert_type, alert.message, alert.severity.value
            )
            
            # TODO: Integrate with external alerting systems
            
        except Exception as e:
            self.logger.error("Error creating security alert: %s", str(e), exc_info=True)

    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get all active security alerts."""
        try:
            redis_conn = await self.get_redis()
            alert_keys = await redis_conn.keys(f"{self.env_prefix}:ai_security_alert:*")
            
            alerts = []
            for key in alert_keys:
                try:
                    alert_data = await redis_conn.get(key)
                    if alert_data:
                        alert_dict = json.loads(alert_data)
                        if not alert_dict.get("resolved", False):
                            alerts.append(alert_dict)
                except Exception as e:
                    self.logger.warning("Error loading alert from key %s: %s", key, str(e))
            
            return sorted(alerts, key=lambda x: x.get("timestamp", ""), reverse=True)
            
        except Exception as e:
            self.logger.error("Error getting active alerts: %s", str(e), exc_info=True)
            return []

    async def resolve_alert(self, alert_id: str, resolution_notes: str = "") -> bool:
        """Resolve a security alert."""
        try:
            redis_conn = await self.get_redis()
            alert_key = f"{self.env_prefix}:ai_security_alert:{alert_id}"
            
            alert_data = await redis_conn.get(alert_key)
            if not alert_data:
                return False
            
            alert_dict = json.loads(alert_data)
            alert_dict["resolved"] = True
            alert_dict["resolution_notes"] = resolution_notes
            alert_dict["resolved_at"] = datetime.now(timezone.utc).isoformat()
            
            await redis_conn.setex(alert_key, 7 * 24 * 3600, json.dumps(alert_dict))
            
            # Remove from active alerts
            if alert_id in self.active_alerts:
                del self.active_alerts[alert_id]
            
            self.logger.info("Resolved AI security alert: %s", alert_id)
            return True
            
        except Exception as e:
            self.logger.error("Error resolving alert %s: %s", alert_id, str(e), exc_info=True)
            return False


# Global monitoring instance
ai_security_monitoring = AISecurityMonitoring()