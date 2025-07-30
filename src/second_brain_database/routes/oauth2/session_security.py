"""
Advanced session hijacking protection with fingerprinting and anomaly detection.

This module provides enterprise-grade session security features including:
- Session fingerprinting for hijacking detection
- Anomaly detection for suspicious session activity
- Session fixation protection
- Secure session regeneration
- Comprehensive security monitoring and alerting

Features:
- Multi-factor session fingerprinting
- Behavioral anomaly detection
- Geographic location tracking
- Device fingerprinting
- Session lifecycle security
- Real-time threat detection
"""

import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager

logger = get_logger(prefix="[Session Security]")

# Session security configuration
SESSION_FINGERPRINT_PREFIX = "oauth2:session_fp:"
SESSION_ANOMALY_PREFIX = "oauth2:session_anomaly:"
SESSION_SECURITY_PREFIX = "oauth2:session_security:"
DEVICE_FINGERPRINT_PREFIX = "oauth2:device_fp:"

# Security thresholds
MAX_LOCATION_CHANGES_PER_HOUR = 3
MAX_USER_AGENT_CHANGES_PER_DAY = 2
MAX_IP_CHANGES_PER_HOUR = 5
SUSPICIOUS_ACTIVITY_THRESHOLD = 0.7
SESSION_ANOMALY_WINDOW_HOURS = 24

# Fingerprinting weights
FINGERPRINT_WEIGHTS = {
    "ip_address": 0.3,
    "user_agent": 0.25,
    "accept_language": 0.15,
    "accept_encoding": 0.1,
    "timezone": 0.1,
    "screen_resolution": 0.05,
    "color_depth": 0.05
}


class SessionFingerprint(BaseModel):
    """
    Comprehensive session fingerprint for security validation.
    """
    
    # Network fingerprinting
    ip_address: str = Field(..., description="Client IP address")
    ip_hash: str = Field(..., description="Hashed IP for privacy")
    
    # Browser fingerprinting
    user_agent: str = Field(..., description="User agent string")
    user_agent_hash: str = Field(..., description="Hashed user agent")
    accept_language: str = Field(default="", description="Accept-Language header")
    accept_encoding: str = Field(default="", description="Accept-Encoding header")
    
    # Client environment
    timezone: Optional[str] = Field(None, description="Client timezone")
    screen_resolution: Optional[str] = Field(None, description="Screen resolution")
    color_depth: Optional[int] = Field(None, description="Color depth")
    
    # Security metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    fingerprint_hash: str = Field(..., description="Combined fingerprint hash")
    confidence_score: float = Field(default=1.0, description="Fingerprint confidence")
    
    # Geographic data (if available)
    country: Optional[str] = Field(None, description="Country code")
    region: Optional[str] = Field(None, description="Region/state")
    city: Optional[str] = Field(None, description="City")
    
    def generate_hash(self) -> str:
        """Generate comprehensive fingerprint hash."""
        fingerprint_data = {
            "ip_hash": self.ip_hash,
            "user_agent_hash": self.user_agent_hash,
            "accept_language": self.accept_language,
            "accept_encoding": self.accept_encoding,
            "timezone": self.timezone,
            "screen_resolution": self.screen_resolution,
            "color_depth": self.color_depth
        }
        
        # Create deterministic hash
        fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()


class SessionAnomalyEvent(BaseModel):
    """
    Represents a detected session anomaly.
    """
    
    event_type: str = Field(..., description="Type of anomaly detected")
    severity: str = Field(..., description="Severity level (low/medium/high/critical)")
    description: str = Field(..., description="Human-readable description")
    
    # Context data
    session_id: str = Field(..., description="Session identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Anomaly details
    current_value: Any = Field(None, description="Current detected value")
    expected_value: Any = Field(None, description="Expected value")
    confidence: float = Field(..., description="Detection confidence (0-1)")
    
    # Risk assessment
    risk_score: float = Field(..., description="Risk score (0-1)")
    recommended_action: str = Field(..., description="Recommended security action")


class EnterpriseSessionSecurity:
    """
    Enterprise-grade session security system with advanced threat detection.
    
    Provides comprehensive session protection including fingerprinting,
    anomaly detection, and automated threat response.
    """
    
    def __init__(self):
        """Initialize the session security system."""
        self.logger = logger
        
        # Anomaly detection models (simplified for this implementation)
        self._anomaly_detectors = {
            "location_change": self._detect_location_anomaly,
            "user_agent_change": self._detect_user_agent_anomaly,
            "ip_change": self._detect_ip_anomaly,
            "timing_anomaly": self._detect_timing_anomaly,
            "behavioral_anomaly": self._detect_behavioral_anomaly
        }
        
        # Statistics for monitoring
        self.stats = {
            "fingerprints_created": 0,
            "anomalies_detected": 0,
            "sessions_invalidated": 0,
            "security_alerts_sent": 0,
            "false_positives": 0
        }
    
    async def create_session_fingerprint(
        self,
        request: Request,
        session_id: str,
        user_id: Optional[str] = None
    ) -> SessionFingerprint:
        """
        Create comprehensive session fingerprint for security validation.
        
        Args:
            request: FastAPI request object
            session_id: Session identifier
            user_id: Optional user identifier
            
        Returns:
            SessionFingerprint: Created fingerprint object
        """
        try:
            # Extract client information
            ip_address = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            accept_language = request.headers.get("accept-language", "")
            accept_encoding = request.headers.get("accept-encoding", "")
            
            # Create privacy-preserving hashes
            ip_hash = self._hash_sensitive_data(ip_address)
            user_agent_hash = self._hash_sensitive_data(user_agent)
            
            # Extract additional client data (if available)
            timezone = request.headers.get("x-timezone")
            screen_resolution = request.headers.get("x-screen-resolution")
            color_depth_str = request.headers.get("x-color-depth")
            color_depth = int(color_depth_str) if color_depth_str and color_depth_str.isdigit() else None
            
            # Create fingerprint
            fingerprint = SessionFingerprint(
                ip_address=ip_address,
                ip_hash=ip_hash,
                user_agent=user_agent,
                user_agent_hash=user_agent_hash,
                accept_language=accept_language,
                accept_encoding=accept_encoding,
                timezone=timezone,
                screen_resolution=screen_resolution,
                color_depth=color_depth
            )
            
            # Generate combined hash
            fingerprint.fingerprint_hash = fingerprint.generate_hash()
            
            # Add geographic data (if available)
            await self._enrich_geographic_data(fingerprint)
            
            # Store fingerprint
            await self._store_session_fingerprint(session_id, fingerprint)
            
            # Update statistics
            self.stats["fingerprints_created"] += 1
            
            # Log fingerprint creation
            self.logger.info(
                "Session fingerprint created for session %s",
                session_id,
                extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "fingerprint_hash": fingerprint.fingerprint_hash[:16],
                    "ip_hash": ip_hash[:16],
                    "confidence_score": fingerprint.confidence_score,
                    "event_type": "session_fingerprint_created"
                }
            )
            
            return fingerprint
            
        except Exception as e:
            self.logger.error(
                "Failed to create session fingerprint: %s",
                e,
                exc_info=True,
                extra={
                    "session_id": session_id,
                    "user_id": user_id
                }
            )
            raise
    
    async def validate_session_security(
        self,
        request: Request,
        session_id: str,
        user_id: Optional[str] = None
    ) -> Tuple[bool, List[SessionAnomalyEvent]]:
        """
        Validate session security and detect anomalies.
        
        Args:
            request: FastAPI request object
            session_id: Session identifier
            user_id: Optional user identifier
            
        Returns:
            Tuple[bool, List[SessionAnomalyEvent]]: (is_valid, detected_anomalies)
        """
        start_time = time.time()
        anomalies = []
        
        try:
            # Get stored fingerprint
            stored_fingerprint = await self._get_session_fingerprint(session_id)
            if not stored_fingerprint:
                # No stored fingerprint - create new one
                await self.create_session_fingerprint(request, session_id, user_id)
                return True, []
            
            # Create current fingerprint
            current_fingerprint = await self.create_session_fingerprint(
                request, f"{session_id}_current", user_id
            )
            
            # Run anomaly detection
            for detector_name, detector_func in self._anomaly_detectors.items():
                try:
                    anomaly = await detector_func(
                        stored_fingerprint, current_fingerprint, session_id
                    )
                    if anomaly:
                        anomalies.append(anomaly)
                except Exception as e:
                    self.logger.error(
                        "Error in anomaly detector %s: %s",
                        detector_name,
                        e,
                        extra={"session_id": session_id}
                    )
            
            # Calculate overall risk score
            overall_risk = self._calculate_overall_risk(anomalies)
            
            # Determine if session is valid
            is_valid = overall_risk < SUSPICIOUS_ACTIVITY_THRESHOLD
            
            # Log validation result
            self.logger.info(
                "Session security validation completed for %s",
                session_id,
                extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "is_valid": is_valid,
                    "anomaly_count": len(anomalies),
                    "overall_risk": overall_risk,
                    "duration_ms": (time.time() - start_time) * 1000,
                    "event_type": "session_security_validated"
                }
            )
            
            # Handle detected anomalies
            if anomalies:
                await self._handle_session_anomalies(session_id, anomalies, user_id)
            
            return is_valid, anomalies
            
        except Exception as e:
            self.logger.error(
                "Error validating session security: %s",
                e,
                exc_info=True,
                extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "duration_ms": (time.time() - start_time) * 1000
                }
            )
            
            # Fail secure - assume session is compromised
            return False, []
    
    async def regenerate_session_security(
        self,
        request: Request,
        old_session_id: str,
        new_session_id: str,
        user_id: Optional[str] = None
    ) -> None:
        """
        Regenerate session security data for session fixation protection.
        
        Args:
            request: FastAPI request object
            old_session_id: Old session identifier
            new_session_id: New session identifier
            user_id: Optional user identifier
        """
        try:
            # Create new fingerprint
            new_fingerprint = await self.create_session_fingerprint(
                request, new_session_id, user_id
            )
            
            # Invalidate old session security data
            await self._invalidate_session_security(old_session_id)
            
            # Log session regeneration
            self.logger.info(
                "Session security regenerated: %s -> %s",
                old_session_id,
                new_session_id,
                extra={
                    "old_session_id": old_session_id,
                    "new_session_id": new_session_id,
                    "user_id": user_id,
                    "new_fingerprint_hash": new_fingerprint.fingerprint_hash[:16],
                    "event_type": "session_security_regenerated"
                }
            )
            
        except Exception as e:
            self.logger.error(
                "Failed to regenerate session security: %s",
                e,
                exc_info=True,
                extra={
                    "old_session_id": old_session_id,
                    "new_session_id": new_session_id,
                    "user_id": user_id
                }
            )
            raise
    
    # Private methods for anomaly detection
    
    async def _detect_location_anomaly(
        self,
        stored_fp: SessionFingerprint,
        current_fp: SessionFingerprint,
        session_id: str
    ) -> Optional[SessionAnomalyEvent]:
        """Detect geographic location anomalies."""
        if not stored_fp.country or not current_fp.country:
            return None
        
        if stored_fp.country != current_fp.country:
            # Check recent location changes
            recent_changes = await self._get_recent_location_changes(session_id)
            
            if recent_changes >= MAX_LOCATION_CHANGES_PER_HOUR:
                return SessionAnomalyEvent(
                    event_type="excessive_location_changes",
                    severity="high",
                    description=f"Excessive location changes detected: {recent_changes} in past hour",
                    session_id=session_id,
                    current_value=current_fp.country,
                    expected_value=stored_fp.country,
                    confidence=0.9,
                    risk_score=0.8,
                    recommended_action="invalidate_session"
                )
        
        return None
    
    async def _detect_user_agent_anomaly(
        self,
        stored_fp: SessionFingerprint,
        current_fp: SessionFingerprint,
        session_id: str
    ) -> Optional[SessionAnomalyEvent]:
        """Detect user agent anomalies."""
        if stored_fp.user_agent_hash != current_fp.user_agent_hash:
            # Check if this is a minor version update vs major change
            similarity = self._calculate_user_agent_similarity(
                stored_fp.user_agent, current_fp.user_agent
            )
            
            if similarity < 0.7:  # Major change
                return SessionAnomalyEvent(
                    event_type="user_agent_change",
                    severity="medium",
                    description="Significant user agent change detected",
                    session_id=session_id,
                    current_value=current_fp.user_agent[:50],
                    expected_value=stored_fp.user_agent[:50],
                    confidence=0.8,
                    risk_score=0.6,
                    recommended_action="require_reauthentication"
                )
        
        return None
    
    async def _detect_ip_anomaly(
        self,
        stored_fp: SessionFingerprint,
        current_fp: SessionFingerprint,
        session_id: str
    ) -> Optional[SessionAnomalyEvent]:
        """Detect IP address anomalies."""
        if stored_fp.ip_hash != current_fp.ip_hash:
            # Check recent IP changes
            recent_changes = await self._get_recent_ip_changes(session_id)
            
            if recent_changes >= MAX_IP_CHANGES_PER_HOUR:
                return SessionAnomalyEvent(
                    event_type="excessive_ip_changes",
                    severity="high",
                    description=f"Excessive IP changes detected: {recent_changes} in past hour",
                    session_id=session_id,
                    current_value=current_fp.ip_hash[:16],
                    expected_value=stored_fp.ip_hash[:16],
                    confidence=0.9,
                    risk_score=0.9,
                    recommended_action="invalidate_session"
                )
        
        return None
    
    async def _detect_timing_anomaly(
        self,
        stored_fp: SessionFingerprint,
        current_fp: SessionFingerprint,
        session_id: str
    ) -> Optional[SessionAnomalyEvent]:
        """Detect timing-based anomalies."""
        # Check for impossible travel times between locations
        if (stored_fp.country and current_fp.country and 
            stored_fp.country != current_fp.country):
            
            time_diff = (current_fp.created_at - stored_fp.created_at).total_seconds()
            
            # If location changed in less than 1 hour, it might be suspicious
            if time_diff < 3600:  # 1 hour
                return SessionAnomalyEvent(
                    event_type="impossible_travel",
                    severity="critical",
                    description="Impossible travel time between geographic locations",
                    session_id=session_id,
                    current_value=f"{current_fp.country} at {current_fp.created_at}",
                    expected_value=f"{stored_fp.country} at {stored_fp.created_at}",
                    confidence=0.95,
                    risk_score=0.95,
                    recommended_action="invalidate_session"
                )
        
        return None
    
    async def _detect_behavioral_anomaly(
        self,
        stored_fp: SessionFingerprint,
        current_fp: SessionFingerprint,
        session_id: str
    ) -> Optional[SessionAnomalyEvent]:
        """Detect behavioral anomalies."""
        # Calculate fingerprint similarity score
        similarity = self._calculate_fingerprint_similarity(stored_fp, current_fp)
        
        if similarity < 0.5:  # Low similarity indicates potential hijacking
            return SessionAnomalyEvent(
                event_type="low_fingerprint_similarity",
                severity="high",
                description=f"Low fingerprint similarity detected: {similarity:.2f}",
                session_id=session_id,
                current_value=similarity,
                expected_value="> 0.7",
                confidence=0.8,
                risk_score=1.0 - similarity,
                recommended_action="require_reauthentication"
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
    
    def _hash_sensitive_data(self, data: str) -> str:
        """Create privacy-preserving hash of sensitive data."""
        # Add salt for additional security
        salt = getattr(settings, "SESSION_SECURITY_SALT", "default_salt")
        salted_data = f"{data}:{salt}"
        return hashlib.sha256(salted_data.encode()).hexdigest()
    
    async def _enrich_geographic_data(self, fingerprint: SessionFingerprint) -> None:
        """Enrich fingerprint with geographic data (placeholder)."""
        # In a real implementation, this would use a GeoIP service
        # For now, we'll leave geographic fields as None
        pass
    
    async def _store_session_fingerprint(
        self,
        session_id: str,
        fingerprint: SessionFingerprint
    ) -> None:
        """Store session fingerprint in Redis."""
        key = f"{SESSION_FINGERPRINT_PREFIX}{session_id}"
        data = fingerprint.model_dump_json()
        
        # Store with 24-hour expiration
        await redis_manager.setex(key, 86400, data)
    
    async def _get_session_fingerprint(
        self,
        session_id: str
    ) -> Optional[SessionFingerprint]:
        """Retrieve session fingerprint from Redis."""
        key = f"{SESSION_FINGERPRINT_PREFIX}{session_id}"
        data = await redis_manager.get(key)
        
        if not data:
            return None
        
        try:
            return SessionFingerprint.model_validate_json(data)
        except Exception as e:
            self.logger.error("Failed to parse session fingerprint: %s", e)
            return None
    
    def _calculate_fingerprint_similarity(
        self,
        fp1: SessionFingerprint,
        fp2: SessionFingerprint
    ) -> float:
        """Calculate similarity score between two fingerprints."""
        total_weight = 0.0
        matching_weight = 0.0
        
        # Compare each component with its weight
        for component, weight in FINGERPRINT_WEIGHTS.items():
            total_weight += weight
            
            val1 = getattr(fp1, component, None)
            val2 = getattr(fp2, component, None)
            
            if val1 and val2:
                if val1 == val2:
                    matching_weight += weight
                elif component == "user_agent":
                    # Special handling for user agent similarity
                    similarity = self._calculate_user_agent_similarity(val1, val2)
                    matching_weight += weight * similarity
        
        return matching_weight / total_weight if total_weight > 0 else 0.0
    
    def _calculate_user_agent_similarity(self, ua1: str, ua2: str) -> float:
        """Calculate similarity between user agent strings."""
        # Simple similarity based on common tokens
        tokens1 = set(ua1.lower().split())
        tokens2 = set(ua2.lower().split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_overall_risk(self, anomalies: List[SessionAnomalyEvent]) -> float:
        """Calculate overall risk score from detected anomalies."""
        if not anomalies:
            return 0.0
        
        # Weight anomalies by severity and confidence
        severity_weights = {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.8,
            "critical": 1.0
        }
        
        total_risk = 0.0
        for anomaly in anomalies:
            severity_weight = severity_weights.get(anomaly.severity, 0.5)
            weighted_risk = anomaly.risk_score * severity_weight * anomaly.confidence
            total_risk += weighted_risk
        
        # Normalize to 0-1 range
        return min(total_risk, 1.0)
    
    async def _handle_session_anomalies(
        self,
        session_id: str,
        anomalies: List[SessionAnomalyEvent],
        user_id: Optional[str] = None
    ) -> None:
        """Handle detected session anomalies."""
        self.stats["anomalies_detected"] += len(anomalies)
        
        for anomaly in anomalies:
            # Log anomaly
            self.logger.warning(
                "Session anomaly detected: %s",
                anomaly.event_type,
                extra={
                    "session_id": session_id,
                    "user_id": user_id,
                    "anomaly_type": anomaly.event_type,
                    "severity": anomaly.severity,
                    "risk_score": anomaly.risk_score,
                    "confidence": anomaly.confidence,
                    "recommended_action": anomaly.recommended_action,
                    "event_type": "session_anomaly_detected"
                }
            )
            
            # Store anomaly for analysis
            await self._store_session_anomaly(anomaly)
            
            # Take action based on severity
            if anomaly.severity in ["high", "critical"]:
                await self._send_security_alert(anomaly, user_id)
    
    async def _store_session_anomaly(self, anomaly: SessionAnomalyEvent) -> None:
        """Store session anomaly for analysis."""
        key = f"{SESSION_ANOMALY_PREFIX}{anomaly.session_id}:{int(time.time())}"
        data = anomaly.model_dump_json()
        
        # Store with 7-day expiration
        await redis_manager.setex(key, 604800, data)
    
    async def _send_security_alert(
        self,
        anomaly: SessionAnomalyEvent,
        user_id: Optional[str] = None
    ) -> None:
        """Send security alert for high-severity anomalies."""
        self.stats["security_alerts_sent"] += 1
        
        # In a real implementation, this would send alerts via email, SMS, etc.
        self.logger.critical(
            "SECURITY ALERT: High-severity session anomaly detected",
            extra={
                "anomaly_type": anomaly.event_type,
                "session_id": anomaly.session_id,
                "user_id": user_id,
                "severity": anomaly.severity,
                "risk_score": anomaly.risk_score,
                "recommended_action": anomaly.recommended_action,
                "event_type": "security_alert_sent"
            }
        )
    
    async def _get_recent_location_changes(self, session_id: str) -> int:
        """Get count of recent location changes for session."""
        # Placeholder implementation
        return 0
    
    async def _get_recent_ip_changes(self, session_id: str) -> int:
        """Get count of recent IP changes for session."""
        # Placeholder implementation
        return 0
    
    async def _invalidate_session_security(self, session_id: str) -> None:
        """Invalidate session security data."""
        keys_to_delete = [
            f"{SESSION_FINGERPRINT_PREFIX}{session_id}",
            f"{SESSION_SECURITY_PREFIX}{session_id}"
        ]
        
        for key in keys_to_delete:
            await redis_manager.delete(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get session security statistics."""
        return {
            **self.stats,
            "anomaly_detection_rate": (
                self.stats["anomalies_detected"] / 
                max(1, self.stats["fingerprints_created"])
            ),
            "session_invalidation_rate": (
                self.stats["sessions_invalidated"] / 
                max(1, self.stats["anomalies_detected"])
            )
        }


# Global session security instance
session_security = EnterpriseSessionSecurity()