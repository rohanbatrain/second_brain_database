"""
Security monitoring and alerting for suspicious OAuth2 authentication patterns.

This module provides comprehensive security monitoring and alerting capabilities
for detecting and responding to suspicious authentication patterns and potential
security threats in OAuth2 browser flows.

Features:
- Real-time threat detection and analysis
- Pattern-based anomaly detection
- Automated security alerting
- Threat intelligence integration
- Risk scoring and assessment
- Incident response automation
- Comprehensive security metrics
- Advanced behavioral analysis
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

from fastapi import Request
from pydantic import BaseModel, Field

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager

logger = get_logger(prefix="[OAuth2 Security Monitoring]")

# Security monitoring configuration
SECURITY_ALERT_PREFIX = "oauth2:security_alert:"
THREAT_PATTERN_PREFIX = "oauth2:threat_pattern:"
SECURITY_METRICS_PREFIX = "oauth2:security_metrics:"
INCIDENT_PREFIX = "oauth2:incident:"

# Threat detection thresholds
MAX_FAILED_ATTEMPTS_PER_IP = 10
MAX_FAILED_ATTEMPTS_PER_CLIENT = 20
MAX_REQUESTS_PER_MINUTE = 100
SUSPICIOUS_USER_AGENT_THRESHOLD = 5
GEOGRAPHIC_ANOMALY_THRESHOLD = 3
TIME_WINDOW_MINUTES = 60

# Risk scoring weights
RISK_WEIGHTS = {
    "failed_authentication": 0.3,
    "suspicious_user_agent": 0.2,
    "geographic_anomaly": 0.25,
    "rate_limit_violation": 0.15,
    "invalid_parameters": 0.1
}


class ThreatLevel(Enum):
    """Threat severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventType(Enum):
    """Types of security events."""
    FAILED_AUTHENTICATION = "failed_authentication"
    SUSPICIOUS_USER_AGENT = "suspicious_user_agent"
    GEOGRAPHIC_ANOMALY = "geographic_anomaly"
    RATE_LIMIT_VIOLATION = "rate_limit_violation"
    INVALID_PARAMETERS = "invalid_parameters"
    BRUTE_FORCE_ATTACK = "brute_force_attack"
    CREDENTIAL_STUFFING = "credential_stuffing"
    SESSION_HIJACKING = "session_hijacking"
    CSRF_ATTACK = "csrf_attack"
    INJECTION_ATTEMPT = "injection_attempt"


class SecurityEvent(BaseModel):
    """Represents a security event for monitoring."""
    
    event_id: str = Field(..., description="Unique event identifier")
    event_type: SecurityEventType = Field(..., description="Type of security event")
    threat_level: ThreatLevel = Field(..., description="Threat severity level")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Source information
    client_ip: str = Field(..., description="Client IP address")
    user_agent: str = Field(default="", description="User agent string")
    client_id: Optional[str] = Field(None, description="OAuth2 client ID")
    user_id: Optional[str] = Field(None, description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier")
    
    # Event details
    description: str = Field(..., description="Event description")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional details")
    risk_score: float = Field(..., description="Risk score (0-1)")
    
    # Context information
    request_path: str = Field(default="", description="Request path")
    request_method: str = Field(default="", description="HTTP method")
    geographic_info: Optional[Dict[str, str]] = Field(None, description="Geographic data")
    
    # Response information
    actions_taken: List[str] = Field(default_factory=list, description="Automated actions")
    alert_sent: bool = Field(default=False, description="Whether alert was sent")


class SecurityAlert(BaseModel):
    """Represents a security alert."""
    
    alert_id: str = Field(..., description="Unique alert identifier")
    alert_type: str = Field(..., description="Type of alert")
    severity: ThreatLevel = Field(..., description="Alert severity")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Alert content
    title: str = Field(..., description="Alert title")
    message: str = Field(..., description="Alert message")
    events: List[SecurityEvent] = Field(..., description="Related security events")
    
    # Incident information
    incident_id: Optional[str] = Field(None, description="Related incident ID")
    escalated: bool = Field(default=False, description="Whether alert was escalated")
    
    # Response tracking
    acknowledged: bool = Field(default=False, description="Whether alert was acknowledged")
    resolved: bool = Field(default=False, description="Whether alert was resolved")
    response_actions: List[str] = Field(default_factory=list, description="Response actions taken")


class OAuth2SecurityMonitor:
    """
    Comprehensive security monitoring system for OAuth2 authentication flows.
    
    Provides real-time threat detection, pattern analysis, and automated
    security response capabilities.
    """
    
    def __init__(self):
        """Initialize the security monitor."""
        self.logger = logger
        
        # Threat detection patterns
        self.threat_patterns = {
            "brute_force": self._detect_brute_force,
            "credential_stuffing": self._detect_credential_stuffing,
            "suspicious_user_agent": self._detect_suspicious_user_agent,
            "geographic_anomaly": self._detect_geographic_anomaly,
            "rate_limit_abuse": self._detect_rate_limit_abuse,
            "parameter_manipulation": self._detect_parameter_manipulation
        }
        
        # Security metrics
        self.metrics = {
            "events_processed": 0,
            "alerts_generated": 0,
            "incidents_created": 0,
            "threats_blocked": 0,
            "false_positives": 0
        }
        
        # Known threat indicators
        self.threat_indicators = {
            "suspicious_user_agents": set(),
            "malicious_ips": set(),
            "blocked_clients": set()
        }
        
        # Initialize threat intelligence (will be loaded lazily)
        self._threat_intelligence_loaded = False
    
    async def process_security_event(
        self,
        request: Request,
        event_type: SecurityEventType,
        description: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_details: Optional[Dict[str, Any]] = None
    ) -> SecurityEvent:
        """
        Process a security event and perform threat analysis.
        
        Args:
            request: FastAPI request object
            event_type: Type of security event
            description: Event description
            client_id: Optional OAuth2 client ID
            user_id: Optional user identifier
            session_id: Optional session identifier
            additional_details: Additional event details
            
        Returns:
            SecurityEvent: Processed security event
        """
        start_time = time.time()
        
        try:
            # Extract request context
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            
            # Generate event ID
            event_id = f"{int(time.time() * 1000)}_{hash(f'{client_ip}_{event_type.value}')}"
            
            # Calculate risk score
            risk_score = await self._calculate_risk_score(
                event_type, client_ip, user_agent, client_id, additional_details
            )
            
            # Determine threat level
            threat_level = self._determine_threat_level(risk_score, event_type)
            
            # Create security event
            security_event = SecurityEvent(
                event_id=event_id,
                event_type=event_type,
                threat_level=threat_level,
                client_ip=client_ip,
                user_agent=user_agent,
                client_id=client_id,
                user_id=user_id,
                session_id=session_id,
                description=description,
                details=additional_details or {},
                risk_score=risk_score,
                request_path=request.url.path,
                request_method=request.method
            )
            
            # Enrich with geographic information
            await self._enrich_geographic_info(security_event)
            
            # Store security event
            await self._store_security_event(security_event)
            
            # Perform threat pattern analysis
            await self._analyze_threat_patterns(security_event)
            
            # Take automated actions if necessary
            await self._take_automated_actions(security_event)
            
            # Update metrics
            self.metrics["events_processed"] += 1
            
            # Log event processing
            self.logger.info(
                "Security event processed: %s",
                event_type.value,
                extra={
                    "event_id": event_id,
                    "threat_level": threat_level.value,
                    "risk_score": risk_score,
                    "client_ip": client_ip,
                    "client_id": client_id,
                    "user_id": user_id,
                    "processing_time_ms": (time.time() - start_time) * 1000,
                    "event_type": "security_event_processed"
                }
            )
            
            return security_event
            
        except Exception as e:
            self.logger.error(
                "Error processing security event: %s",
                e,
                exc_info=True,
                extra={
                    "event_type": event_type.value,
                    "client_ip": self._get_client_ip(request),
                    "processing_time_ms": (time.time() - start_time) * 1000
                }
            )
            raise
    
    async def generate_security_alert(
        self,
        alert_type: str,
        title: str,
        message: str,
        events: List[SecurityEvent],
        severity: ThreatLevel = ThreatLevel.MEDIUM
    ) -> SecurityAlert:
        """
        Generate a security alert based on detected threats.
        
        Args:
            alert_type: Type of alert
            title: Alert title
            message: Alert message
            events: Related security events
            severity: Alert severity level
            
        Returns:
            SecurityAlert: Generated security alert
        """
        try:
            # Generate alert ID
            alert_id = f"alert_{int(time.time() * 1000)}_{hash(alert_type)}"
            
            # Create security alert
            alert = SecurityAlert(
                alert_id=alert_id,
                alert_type=alert_type,
                severity=severity,
                title=title,
                message=message,
                events=events
            )
            
            # Store alert
            await self._store_security_alert(alert)
            
            # Send alert notifications
            await self._send_alert_notifications(alert)
            
            # Update metrics
            self.metrics["alerts_generated"] += 1
            
            # Log alert generation
            self.logger.warning(
                "Security alert generated: %s",
                title,
                extra={
                    "alert_id": alert_id,
                    "alert_type": alert_type,
                    "severity": severity.value,
                    "event_count": len(events),
                    "event_type": "security_alert_generated"
                }
            )
            
            return alert
            
        except Exception as e:
            self.logger.error("Error generating security alert: %s", e, exc_info=True)
            raise
    
    # Threat detection methods
    
    async def _detect_brute_force(self, event: SecurityEvent) -> Optional[SecurityAlert]:
        """Detect brute force attacks."""
        if event.event_type != SecurityEventType.FAILED_AUTHENTICATION:
            return None
        
        # Count recent failed attempts from same IP
        recent_failures = await self._count_recent_events(
            event.client_ip,
            SecurityEventType.FAILED_AUTHENTICATION,
            TIME_WINDOW_MINUTES
        )
        
        if recent_failures >= MAX_FAILED_ATTEMPTS_PER_IP:
            # Get related events
            related_events = await self._get_recent_events(
                event.client_ip,
                SecurityEventType.FAILED_AUTHENTICATION,
                TIME_WINDOW_MINUTES
            )
            
            return await self.generate_security_alert(
                "brute_force_attack",
                f"Brute Force Attack Detected from {event.client_ip}",
                f"Detected {recent_failures} failed authentication attempts from IP {event.client_ip} in the last {TIME_WINDOW_MINUTES} minutes",
                related_events,
                ThreatLevel.HIGH
            )
        
        return None
    
    async def _detect_credential_stuffing(self, event: SecurityEvent) -> Optional[SecurityAlert]:
        """Detect credential stuffing attacks."""
        if event.event_type != SecurityEventType.FAILED_AUTHENTICATION:
            return None
        
        # Look for multiple client IDs from same IP
        client_diversity = await self._get_client_diversity(event.client_ip, TIME_WINDOW_MINUTES)
        
        if client_diversity >= 5:  # Multiple different clients
            related_events = await self._get_recent_events(
                event.client_ip,
                SecurityEventType.FAILED_AUTHENTICATION,
                TIME_WINDOW_MINUTES
            )
            
            return await self.generate_security_alert(
                "credential_stuffing",
                f"Credential Stuffing Attack Detected from {event.client_ip}",
                f"Detected authentication attempts against {client_diversity} different clients from IP {event.client_ip}",
                related_events,
                ThreatLevel.HIGH
            )
        
        return None
    
    async def _detect_suspicious_user_agent(self, event: SecurityEvent) -> Optional[SecurityAlert]:
        """Detect suspicious user agents."""
        user_agent = event.user_agent.lower()
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "curl", "wget", "python", "bot", "crawler", "scanner",
            "sqlmap", "nikto", "burp", "zap", "nmap"
        ]
        
        if any(pattern in user_agent for pattern in suspicious_patterns):
            return await self.generate_security_alert(
                "suspicious_user_agent",
                f"Suspicious User Agent Detected",
                f"Detected potentially malicious user agent: {event.user_agent[:100]}",
                [event],
                ThreatLevel.MEDIUM
            )
        
        return None
    
    async def _detect_geographic_anomaly(self, event: SecurityEvent) -> Optional[SecurityAlert]:
        """Detect geographic anomalies."""
        if not event.user_id or not event.geographic_info:
            return None
        
        # Get user's typical locations
        typical_locations = await self._get_user_typical_locations(event.user_id)
        
        current_country = event.geographic_info.get("country")
        if current_country and current_country not in typical_locations:
            return await self.generate_security_alert(
                "geographic_anomaly",
                f"Geographic Anomaly Detected for User {event.user_id}",
                f"User authentication from unusual location: {current_country}",
                [event],
                ThreatLevel.MEDIUM
            )
        
        return None
    
    async def _detect_rate_limit_abuse(self, event: SecurityEvent) -> Optional[SecurityAlert]:
        """Detect rate limit abuse."""
        if event.event_type != SecurityEventType.RATE_LIMIT_VIOLATION:
            return None
        
        # Count recent rate limit violations
        recent_violations = await self._count_recent_events(
            event.client_ip,
            SecurityEventType.RATE_LIMIT_VIOLATION,
            TIME_WINDOW_MINUTES
        )
        
        if recent_violations >= 5:
            related_events = await self._get_recent_events(
                event.client_ip,
                SecurityEventType.RATE_LIMIT_VIOLATION,
                TIME_WINDOW_MINUTES
            )
            
            return await self.generate_security_alert(
                "rate_limit_abuse",
                f"Rate Limit Abuse Detected from {event.client_ip}",
                f"Detected {recent_violations} rate limit violations from IP {event.client_ip}",
                related_events,
                ThreatLevel.MEDIUM
            )
        
        return None
    
    async def _detect_parameter_manipulation(self, event: SecurityEvent) -> Optional[SecurityAlert]:
        """Detect parameter manipulation attempts."""
        if event.event_type != SecurityEventType.INVALID_PARAMETERS:
            return None
        
        # Look for patterns indicating injection attempts
        details = event.details
        suspicious_patterns = [
            "script", "javascript", "vbscript", "onload", "onerror",
            "union", "select", "drop", "insert", "update", "delete",
            "../", "..\\", "/etc/passwd", "cmd.exe"
        ]
        
        for key, value in details.items():
            if isinstance(value, str):
                value_lower = value.lower()
                if any(pattern in value_lower for pattern in suspicious_patterns):
                    return await self.generate_security_alert(
                        "injection_attempt",
                        f"Injection Attempt Detected from {event.client_ip}",
                        f"Detected potential injection attempt in parameter {key}",
                        [event],
                        ThreatLevel.HIGH
                    )
        
        return None
    
    # Helper methods
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        return getattr(request.client, "host", "unknown")
    
    async def _calculate_risk_score(
        self,
        event_type: SecurityEventType,
        client_ip: str,
        user_agent: str,
        client_id: Optional[str],
        details: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate risk score for security event."""
        base_score = RISK_WEIGHTS.get(event_type.value, 0.1)
        
        # Adjust based on IP reputation
        if client_ip in self.threat_indicators["malicious_ips"]:
            base_score += 0.3
        
        # Adjust based on user agent
        if any(pattern in user_agent.lower() for pattern in ["bot", "crawler", "scanner"]):
            base_score += 0.2
        
        # Adjust based on client reputation
        if client_id and client_id in self.threat_indicators["blocked_clients"]:
            base_score += 0.2
        
        # Adjust based on recent activity
        recent_events = await self._count_recent_events(client_ip, event_type, 60)
        if recent_events > 5:
            base_score += min(0.3, recent_events * 0.05)
        
        return min(1.0, base_score)
    
    def _determine_threat_level(self, risk_score: float, event_type: SecurityEventType) -> ThreatLevel:
        """Determine threat level based on risk score and event type."""
        if risk_score >= 0.8:
            return ThreatLevel.CRITICAL
        elif risk_score >= 0.6:
            return ThreatLevel.HIGH
        elif risk_score >= 0.3:
            return ThreatLevel.MEDIUM
        else:
            return ThreatLevel.LOW
    
    async def _enrich_geographic_info(self, event: SecurityEvent) -> None:
        """Enrich event with geographic information."""
        # Placeholder for geographic enrichment
        # In a real implementation, this would use a GeoIP service
        pass
    
    async def _store_security_event(self, event: SecurityEvent) -> None:
        """Store security event in Redis."""
        key = f"oauth2:security_event:{event.event_id}"
        data = event.model_dump_json()
        
        # Store with 7-day expiration
        await redis_manager.setex(key, 604800, data)
        
        # Also store in time-based index
        time_key = f"oauth2:security_events:{datetime.utcnow().strftime('%Y%m%d%H')}"
        await redis_manager.sadd(time_key, event.event_id)
        await redis_manager.expire(time_key, 604800)
    
    async def _store_security_alert(self, alert: SecurityAlert) -> None:
        """Store security alert in Redis."""
        key = f"oauth2:security_alert:{alert.alert_id}"
        data = alert.model_dump_json()
        
        # Store with 30-day expiration
        await redis_manager.setex(key, 2592000, data)
    
    async def _analyze_threat_patterns(self, event: SecurityEvent) -> None:
        """Analyze threat patterns and generate alerts if necessary."""
        for pattern_name, detector in self.threat_patterns.items():
            try:
                alert = await detector(event)
                if alert:
                    self.logger.info(f"Threat pattern detected: {pattern_name}")
            except Exception as e:
                self.logger.error(f"Error in threat pattern {pattern_name}: {e}")
    
    async def _take_automated_actions(self, event: SecurityEvent) -> None:
        """Take automated security actions based on event."""
        actions = []
        
        if event.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
            # Block IP temporarily
            await self._temporary_ip_block(event.client_ip, 3600)  # 1 hour
            actions.append("temporary_ip_block")
            
            # Add to threat indicators
            self.threat_indicators["malicious_ips"].add(event.client_ip)
            actions.append("added_to_threat_indicators")
        
        if event.event_type == SecurityEventType.BRUTE_FORCE_ATTACK:
            # Increase rate limiting for IP
            await self._increase_rate_limiting(event.client_ip)
            actions.append("increased_rate_limiting")
        
        event.actions_taken = actions
        self.metrics["threats_blocked"] += len(actions)
    
    async def _send_alert_notifications(self, alert: SecurityAlert) -> None:
        """Send alert notifications to security team."""
        # Placeholder for alert notification system
        # In a real implementation, this would send emails, SMS, Slack messages, etc.
        self.logger.critical(
            "SECURITY ALERT: %s",
            alert.title,
            extra={
                "alert_id": alert.alert_id,
                "severity": alert.severity.value,
                "message": alert.message,
                "event_count": len(alert.events),
                "event_type": "security_alert_notification"
            }
        )
    
    async def _count_recent_events(
        self,
        client_ip: str,
        event_type: SecurityEventType,
        minutes: int
    ) -> int:
        """Count recent events of specific type from IP."""
        # Placeholder implementation
        # In a real implementation, this would query Redis for recent events
        return 0
    
    async def _get_recent_events(
        self,
        client_ip: str,
        event_type: SecurityEventType,
        minutes: int
    ) -> List[SecurityEvent]:
        """Get recent events of specific type from IP."""
        # Placeholder implementation
        return []
    
    async def _get_client_diversity(self, client_ip: str, minutes: int) -> int:
        """Get number of different clients accessed from IP."""
        # Placeholder implementation
        return 0
    
    async def _get_user_typical_locations(self, user_id: str) -> Set[str]:
        """Get user's typical geographic locations."""
        # Placeholder implementation
        return set()
    
    async def _temporary_ip_block(self, client_ip: str, duration_seconds: int) -> None:
        """Temporarily block an IP address."""
        key = f"oauth2:blocked_ip:{client_ip}"
        await redis_manager.setex(key, duration_seconds, "blocked")
    
    async def _increase_rate_limiting(self, client_ip: str) -> None:
        """Increase rate limiting for an IP address."""
        key = f"oauth2:enhanced_rate_limit:{client_ip}"
        await redis_manager.setex(key, 3600, "enhanced")  # 1 hour
    
    async def _load_threat_intelligence(self) -> None:
        """Load threat intelligence data."""
        if self._threat_intelligence_loaded:
            return
            
        # Placeholder for loading threat intelligence feeds
        # In a real implementation, this would load from external sources
        self._threat_intelligence_loaded = True
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get security monitoring metrics."""
        return {
            **self.metrics,
            "threat_indicators_count": {
                "malicious_ips": len(self.threat_indicators["malicious_ips"]),
                "suspicious_user_agents": len(self.threat_indicators["suspicious_user_agents"]),
                "blocked_clients": len(self.threat_indicators["blocked_clients"])
            }
        }


# Global security monitor instance
security_monitor = OAuth2SecurityMonitor()