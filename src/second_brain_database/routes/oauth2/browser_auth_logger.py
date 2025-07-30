"""
Specialized logging system for OAuth2 browser authentication events.

This module provides comprehensive structured logging specifically designed
for browser-based OAuth2 authentication flows, capturing detailed context
about user interactions, authentication methods, and flow progression.

Features:
- Structured logging for browser authentication events
- User journey tracking and flow analysis
- Authentication method detection and logging
- Session lifecycle event logging
- Security event logging for suspicious browser activity
- Performance monitoring for browser-specific operations
- Integration with monitoring and metrics systems
"""

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass, field
from urllib.parse import urlparse

from fastapi import Request, Response
from pydantic import BaseModel

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.logging_utils import SecurityContext, log_auth_success, log_auth_failure

logger = get_logger(prefix="[OAuth2 Browser Auth]")


class BrowserAuthEvent(str, Enum):
    """Browser authentication event types."""
    
    # Authentication flow events
    AUTH_FLOW_STARTED = "auth_flow_started"
    AUTH_METHOD_DETECTED = "auth_method_detected"
    AUTH_REDIRECT_INITIATED = "auth_redirect_initiated"
    AUTH_REDIRECT_COMPLETED = "auth_redirect_completed"
    AUTH_STATE_PRESERVED = "auth_state_preserved"
    AUTH_STATE_RESTORED = "auth_state_restored"
    
    # Session events
    SESSION_CREATED = "session_created"
    SESSION_VALIDATED = "session_validated"
    SESSION_EXPIRED = "session_expired"
    SESSION_REGENERATED = "session_regenerated"
    SESSION_CLEANUP = "session_cleanup"
    
    # User interaction events
    USER_CONSENT_SHOWN = "user_consent_shown"
    USER_CONSENT_GRANTED = "user_consent_granted"
    USER_CONSENT_DENIED = "user_consent_denied"
    USER_LOGIN_REQUIRED = "user_login_required"
    USER_LOGIN_COMPLETED = "user_login_completed"
    
    # Security events
    SUSPICIOUS_BROWSER_ACTIVITY = "suspicious_browser_activity"
    CSRF_TOKEN_VALIDATION = "csrf_token_validation"
    SESSION_FIXATION_ATTEMPT = "session_fixation_attempt"
    RATE_LIMIT_TRIGGERED = "rate_limit_triggered"
    SECURITY_HEADER_VIOLATION = "security_header_violation"
    
    # Performance events
    TEMPLATE_RENDER_SLOW = "template_render_slow"
    AUTH_FLOW_SLOW = "auth_flow_slow"
    DATABASE_OPERATION_SLOW = "database_operation_slow"
    
    # Error events
    AUTH_FLOW_ERROR = "auth_flow_error"
    SESSION_ERROR = "session_error"
    TEMPLATE_ERROR = "template_error"
    VALIDATION_ERROR = "validation_error"


class AuthenticationMethod(str, Enum):
    """Authentication methods for browser flows."""
    JWT_TOKEN = "jwt_token"
    BROWSER_SESSION = "browser_session"
    MIXED_AUTH = "mixed_auth"
    NO_AUTH = "no_auth"
    UNKNOWN = "unknown"


@dataclass
class BrowserContext:
    """Browser-specific context information."""
    user_agent: str
    accept_language: Optional[str] = None
    accept_encoding: Optional[str] = None
    referer: Optional[str] = None
    origin: Optional[str] = None
    is_mobile: bool = False
    is_bot: bool = False
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    os_name: Optional[str] = None


@dataclass
class OAuth2FlowContext:
    """OAuth2 flow-specific context."""
    flow_id: str
    client_id: str
    redirect_uri: str
    scopes: List[str]
    state: str
    code_challenge_method: str
    response_type: str
    auth_method: AuthenticationMethod
    flow_stage: str
    start_time: datetime
    current_time: datetime
    duration_so_far: float = 0.0


@dataclass
class SessionContext:
    """Session-specific context."""
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    session_created_at: Optional[datetime] = None
    session_last_activity: Optional[datetime] = None
    session_expires_at: Optional[datetime] = None
    csrf_token_valid: bool = False
    session_regenerated: bool = False


@dataclass
class PerformanceContext:
    """Performance-related context."""
    request_start_time: float
    processing_time: Optional[float] = None
    template_render_time: Optional[float] = None
    database_query_time: Optional[float] = None
    total_response_time: Optional[float] = None
    memory_usage: Optional[float] = None


class BrowserAuthenticationLogger:
    """
    Specialized logger for OAuth2 browser authentication events.
    
    Provides comprehensive logging with rich context for browser-based
    OAuth2 authentication flows, enabling detailed analysis and monitoring.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[OAuth2 Browser Auth Logger]")
        
        # Import monitoring system if available
        try:
            from .monitoring import oauth2_monitoring
            self.monitoring = oauth2_monitoring
            self.monitoring_available = True
        except ImportError:
            self.monitoring = None
            self.monitoring_available = False
    
    def log_authentication_event(
        self,
        event_type: BrowserAuthEvent,
        request: Request,
        oauth2_context: Optional[OAuth2FlowContext] = None,
        session_context: Optional[SessionContext] = None,
        performance_context: Optional[PerformanceContext] = None,
        security_context: Optional[Dict[str, Any]] = None,
        error_context: Optional[Dict[str, Any]] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a browser authentication event with comprehensive context.
        
        Args:
            event_type: Type of authentication event
            request: FastAPI request object
            oauth2_context: OAuth2 flow context
            session_context: Session context
            performance_context: Performance metrics
            security_context: Security-related context
            error_context: Error information if applicable
            additional_context: Additional context data
        """
        # Extract browser context
        browser_context = self._extract_browser_context(request)
        
        # Build comprehensive log entry
        log_entry = {
            "event_type": event_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": getattr(request.state, "request_id", None),
            
            # Request context
            "request": {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_ip": request.client.host if request.client else None,
                "headers": self._sanitize_headers(dict(request.headers))
            },
            
            # Browser context
            "browser": browser_context.__dict__,
            
            # OAuth2 context
            "oauth2": oauth2_context.__dict__ if oauth2_context else None,
            
            # Session context
            "session": session_context.__dict__ if session_context else None,
            
            # Performance context
            "performance": performance_context.__dict__ if performance_context else None,
            
            # Security context
            "security": security_context,
            
            # Error context
            "error": error_context,
            
            # Additional context
            "additional": additional_context
        }
        
        # Determine log level based on event type
        log_level = self._get_log_level(event_type)
        
        # Create structured log message
        message = self._create_log_message(event_type, oauth2_context, session_context, error_context)
        
        # Log with appropriate level
        getattr(self.logger, log_level)(
            message,
            extra={
                "browser_auth_event": True,
                "event_type": event_type.value,
                "oauth2_flow_id": oauth2_context.flow_id if oauth2_context else None,
                "client_id": oauth2_context.client_id if oauth2_context else None,
                "user_id": session_context.user_id if session_context else None,
                "session_id": session_context.session_id if session_context else None,
                "auth_method": oauth2_context.auth_method.value if oauth2_context else None,
                "browser_auth_context": log_entry,
                "security_relevant": self._is_security_relevant(event_type),
                "performance_relevant": self._is_performance_relevant(event_type)
            }
        )
        
        # Update monitoring system if available
        if self.monitoring_available and self.monitoring:
            self._update_monitoring(event_type, oauth2_context, session_context, performance_context)
    
    def log_authentication_flow_start(
        self,
        request: Request,
        flow_id: str,
        client_id: str,
        auth_method: AuthenticationMethod,
        redirect_uri: str,
        scopes: List[str],
        state: str,
        user_id: Optional[str] = None
    ) -> None:
        """
        Log the start of an OAuth2 browser authentication flow.
        
        Args:
            request: FastAPI request object
            flow_id: Unique flow identifier
            client_id: OAuth2 client ID
            auth_method: Detected authentication method
            redirect_uri: Client redirect URI
            scopes: Requested scopes
            state: OAuth2 state parameter
            user_id: User ID if already authenticated
        """
        oauth2_context = OAuth2FlowContext(
            flow_id=flow_id,
            client_id=client_id,
            redirect_uri=redirect_uri,
            scopes=scopes,
            state=state,
            code_challenge_method="S256",  # Default
            response_type="code",
            auth_method=auth_method,
            flow_stage="started",
            start_time=datetime.now(timezone.utc),
            current_time=datetime.now(timezone.utc)
        )
        
        session_context = SessionContext(user_id=user_id) if user_id else None
        
        self.log_authentication_event(
            BrowserAuthEvent.AUTH_FLOW_STARTED,
            request,
            oauth2_context=oauth2_context,
            session_context=session_context,
            additional_context={
                "flow_initiated": True,
                "client_type": "browser",
                "pkce_enabled": True
            }
        )
        
        # Log to security system
        log_auth_success(
            "oauth2_flow_started",
            user_id=user_id,
            ip_address=request.client.host if request.client else None,
            details={
                "flow_id": flow_id,
                "client_id": client_id,
                "auth_method": auth_method.value,
                "scopes": scopes
            }
        )
    
    def log_authentication_redirect(
        self,
        request: Request,
        flow_id: str,
        redirect_type: str,
        redirect_url: str,
        state_preserved: bool = False,
        user_id: Optional[str] = None
    ) -> None:
        """
        Log authentication redirect events.
        
        Args:
            request: FastAPI request object
            flow_id: Flow identifier
            redirect_type: Type of redirect (login/consent/callback)
            redirect_url: Target redirect URL
            state_preserved: Whether OAuth2 state was preserved
            user_id: User ID if applicable
        """
        oauth2_context = OAuth2FlowContext(
            flow_id=flow_id,
            client_id="unknown",  # Will be filled from flow context
            redirect_uri=redirect_url,
            scopes=[],
            state="",
            code_challenge_method="S256",
            response_type="code",
            auth_method=AuthenticationMethod.BROWSER_SESSION,
            flow_stage="redirect",
            start_time=datetime.now(timezone.utc),
            current_time=datetime.now(timezone.utc)
        )
        
        event_type = (
            BrowserAuthEvent.AUTH_REDIRECT_INITIATED
            if redirect_type == "initiated"
            else BrowserAuthEvent.AUTH_REDIRECT_COMPLETED
        )
        
        self.log_authentication_event(
            event_type,
            request,
            oauth2_context=oauth2_context,
            session_context=SessionContext(user_id=user_id) if user_id else None,
            additional_context={
                "redirect_type": redirect_type,
                "redirect_url": redirect_url,
                "state_preserved": state_preserved,
                "redirect_domain": urlparse(redirect_url).netloc
            }
        )
    
    def log_session_event(
        self,
        event_type: BrowserAuthEvent,
        request: Request,
        session_id: str,
        user_id: str,
        session_data: Optional[Dict[str, Any]] = None,
        security_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log browser session lifecycle events.
        
        Args:
            event_type: Type of session event
            request: FastAPI request object
            session_id: Session identifier
            user_id: User identifier
            session_data: Session data context
            security_context: Security-related context
        """
        session_context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            session_created_at=datetime.now(timezone.utc),
            session_last_activity=datetime.now(timezone.utc)
        )
        
        if session_data:
            session_context.session_expires_at = session_data.get("expires_at")
            session_context.csrf_token_valid = session_data.get("csrf_valid", False)
            session_context.session_regenerated = session_data.get("regenerated", False)
        
        self.log_authentication_event(
            event_type,
            request,
            session_context=session_context,
            security_context=security_context,
            additional_context={
                "session_data": session_data,
                "session_type": "browser_oauth2"
            }
        )
    
    def log_security_event(
        self,
        event_type: BrowserAuthEvent,
        request: Request,
        severity: str,
        description: str,
        flow_id: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        threat_indicators: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log security events for suspicious browser activity.
        
        Args:
            event_type: Type of security event
            request: FastAPI request object
            severity: Event severity (low/medium/high/critical)
            description: Event description
            flow_id: OAuth2 flow ID if applicable
            session_id: Session ID if applicable
            user_id: User ID if applicable
            threat_indicators: Threat detection indicators
        """
        security_context = {
            "severity": severity,
            "description": description,
            "threat_indicators": threat_indicators,
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
            "suspicious_patterns": self._detect_suspicious_patterns(request),
            "risk_score": self._calculate_risk_score(request, threat_indicators)
        }
        
        oauth2_context = None
        if flow_id:
            oauth2_context = OAuth2FlowContext(
                flow_id=flow_id,
                client_id="unknown",
                redirect_uri="",
                scopes=[],
                state="",
                code_challenge_method="S256",
                response_type="code",
                auth_method=AuthenticationMethod.BROWSER_SESSION,
                flow_stage="security_event",
                start_time=datetime.now(timezone.utc),
                current_time=datetime.now(timezone.utc)
            )
        
        session_context = SessionContext(
            session_id=session_id,
            user_id=user_id
        ) if session_id or user_id else None
        
        self.log_authentication_event(
            event_type,
            request,
            oauth2_context=oauth2_context,
            session_context=session_context,
            security_context=security_context,
            additional_context={
                "security_event": True,
                "requires_investigation": severity in ["high", "critical"],
                "automated_response": threat_indicators.get("automated_response") if threat_indicators else None
            }
        )
        
        # Log to security system
        if severity in ["high", "critical"]:
            log_auth_failure(
                f"oauth2_security_{event_type.value}",
                user_id=user_id,
                ip_address=request.client.host if request.client else None,
                details={
                    "severity": severity,
                    "description": description,
                    "flow_id": flow_id,
                    "session_id": session_id,
                    "threat_indicators": threat_indicators
                }
            )
    
    def log_performance_event(
        self,
        event_type: BrowserAuthEvent,
        request: Request,
        operation: str,
        duration: float,
        flow_id: Optional[str] = None,
        template_name: Optional[str] = None,
        additional_metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log performance events for browser authentication operations.
        
        Args:
            event_type: Type of performance event
            request: FastAPI request object
            operation: Operation name
            duration: Operation duration in seconds
            flow_id: OAuth2 flow ID if applicable
            template_name: Template name if applicable
            additional_metrics: Additional performance metrics
        """
        performance_context = PerformanceContext(
            request_start_time=time.time() - duration,
            processing_time=duration,
            template_render_time=duration if template_name else None,
            total_response_time=duration
        )
        
        if additional_metrics:
            performance_context.database_query_time = additional_metrics.get("db_time")
            performance_context.memory_usage = additional_metrics.get("memory_usage")
        
        oauth2_context = None
        if flow_id:
            oauth2_context = OAuth2FlowContext(
                flow_id=flow_id,
                client_id="unknown",
                redirect_uri="",
                scopes=[],
                state="",
                code_challenge_method="S256",
                response_type="code",
                auth_method=AuthenticationMethod.BROWSER_SESSION,
                flow_stage="performance_monitoring",
                start_time=datetime.now(timezone.utc),
                current_time=datetime.now(timezone.utc)
            )
        
        self.log_authentication_event(
            event_type,
            request,
            oauth2_context=oauth2_context,
            performance_context=performance_context,
            additional_context={
                "operation": operation,
                "template_name": template_name,
                "performance_threshold_exceeded": duration > 2.0,
                "slow_operation": duration > 5.0,
                "additional_metrics": additional_metrics
            }
        )
        
        # Update monitoring system
        if self.monitoring_available and self.monitoring and template_name:
            self.monitoring.record_template_render_time(flow_id or "unknown", template_name, duration)
    
    def _extract_browser_context(self, request: Request) -> BrowserContext:
        """Extract browser-specific context from request."""
        user_agent = request.headers.get("user-agent", "")
        
        # Basic browser detection
        is_mobile = any(mobile in user_agent.lower() for mobile in ["mobile", "android", "iphone", "ipad"])
        is_bot = any(bot in user_agent.lower() for bot in ["bot", "crawler", "spider", "scraper"])
        
        # Extract browser info (simplified)
        browser_name = None
        browser_version = None
        os_name = None
        
        if "chrome" in user_agent.lower():
            browser_name = "Chrome"
        elif "firefox" in user_agent.lower():
            browser_name = "Firefox"
        elif "safari" in user_agent.lower():
            browser_name = "Safari"
        elif "edge" in user_agent.lower():
            browser_name = "Edge"
        
        if "windows" in user_agent.lower():
            os_name = "Windows"
        elif "mac" in user_agent.lower():
            os_name = "macOS"
        elif "linux" in user_agent.lower():
            os_name = "Linux"
        
        return BrowserContext(
            user_agent=user_agent,
            accept_language=request.headers.get("accept-language"),
            accept_encoding=request.headers.get("accept-encoding"),
            referer=request.headers.get("referer"),
            origin=request.headers.get("origin"),
            is_mobile=is_mobile,
            is_bot=is_bot,
            browser_name=browser_name,
            browser_version=browser_version,
            os_name=os_name
        )
    
    def _sanitize_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Sanitize headers for logging."""
        sensitive_headers = {"authorization", "cookie", "x-api-key", "x-auth-token"}
        
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                sanitized[key] = "<REDACTED>"
            else:
                sanitized[key] = value
        
        return sanitized
    
    def _get_log_level(self, event_type: BrowserAuthEvent) -> str:
        """Determine appropriate log level for event type."""
        if event_type in [
            BrowserAuthEvent.SUSPICIOUS_BROWSER_ACTIVITY,
            BrowserAuthEvent.SESSION_FIXATION_ATTEMPT,
            BrowserAuthEvent.SECURITY_HEADER_VIOLATION
        ]:
            return "warning"
        elif event_type in [
            BrowserAuthEvent.AUTH_FLOW_ERROR,
            BrowserAuthEvent.SESSION_ERROR,
            BrowserAuthEvent.TEMPLATE_ERROR,
            BrowserAuthEvent.VALIDATION_ERROR
        ]:
            return "error"
        elif event_type in [
            BrowserAuthEvent.TEMPLATE_RENDER_SLOW,
            BrowserAuthEvent.AUTH_FLOW_SLOW,
            BrowserAuthEvent.DATABASE_OPERATION_SLOW
        ]:
            return "warning"
        else:
            return "info"
    
    def _create_log_message(
        self,
        event_type: BrowserAuthEvent,
        oauth2_context: Optional[OAuth2FlowContext],
        session_context: Optional[SessionContext],
        error_context: Optional[Dict[str, Any]]
    ) -> str:
        """Create human-readable log message."""
        base_message = f"OAuth2 Browser Auth: {event_type.value}"
        
        if oauth2_context:
            base_message += f" [Flow: {oauth2_context.flow_id}, Client: {oauth2_context.client_id}]"
        
        if session_context and session_context.user_id:
            base_message += f" [User: {session_context.user_id}]"
        
        if error_context:
            base_message += f" [Error: {error_context.get('message', 'Unknown error')}]"
        
        return base_message
    
    def _is_security_relevant(self, event_type: BrowserAuthEvent) -> bool:
        """Check if event type is security-relevant."""
        security_events = {
            BrowserAuthEvent.SUSPICIOUS_BROWSER_ACTIVITY,
            BrowserAuthEvent.CSRF_TOKEN_VALIDATION,
            BrowserAuthEvent.SESSION_FIXATION_ATTEMPT,
            BrowserAuthEvent.RATE_LIMIT_TRIGGERED,
            BrowserAuthEvent.SECURITY_HEADER_VIOLATION
        }
        return event_type in security_events
    
    def _is_performance_relevant(self, event_type: BrowserAuthEvent) -> bool:
        """Check if event type is performance-relevant."""
        performance_events = {
            BrowserAuthEvent.TEMPLATE_RENDER_SLOW,
            BrowserAuthEvent.AUTH_FLOW_SLOW,
            BrowserAuthEvent.DATABASE_OPERATION_SLOW
        }
        return event_type in performance_events
    
    def _detect_suspicious_patterns(self, request: Request) -> List[str]:
        """Detect suspicious patterns in request."""
        patterns = []
        
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Check for bot patterns
        if any(bot in user_agent for bot in ["bot", "crawler", "spider", "scraper"]):
            patterns.append("bot_user_agent")
        
        # Check for missing common headers
        if not request.headers.get("accept"):
            patterns.append("missing_accept_header")
        
        if not request.headers.get("accept-language"):
            patterns.append("missing_accept_language")
        
        # Check for suspicious referer
        referer = request.headers.get("referer")
        if referer and urlparse(referer).netloc != request.url.netloc:
            patterns.append("external_referer")
        
        return patterns
    
    def _calculate_risk_score(
        self,
        request: Request,
        threat_indicators: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate risk score for the request."""
        score = 0.0
        
        # Base score from suspicious patterns
        patterns = self._detect_suspicious_patterns(request)
        score += len(patterns) * 0.2
        
        # Score from threat indicators
        if threat_indicators:
            score += threat_indicators.get("malicious_ip_score", 0.0)
            score += threat_indicators.get("rate_limit_violations", 0) * 0.1
            score += threat_indicators.get("failed_auth_attempts", 0) * 0.05
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _update_monitoring(
        self,
        event_type: BrowserAuthEvent,
        oauth2_context: Optional[OAuth2FlowContext],
        session_context: Optional[SessionContext],
        performance_context: Optional[PerformanceContext]
    ) -> None:
        """Update monitoring system with event data."""
        if not self.monitoring:
            return
        
        # Update flow monitoring
        if oauth2_context and oauth2_context.flow_id:
            if event_type == BrowserAuthEvent.AUTH_FLOW_STARTED:
                from .monitoring import AuthenticationMethod as MonitoringAuthMethod, start_flow_monitoring
                auth_method = MonitoringAuthMethod.BROWSER_SESSION
                start_flow_monitoring(
                    oauth2_context.flow_id,
                    oauth2_context.client_id,
                    auth_method,
                    session_context.user_id if session_context else None
                )
        
        # Update session monitoring
        if session_context and session_context.session_id and session_context.user_id:
            if event_type == BrowserAuthEvent.SESSION_CREATED:
                from .monitoring import start_session_monitoring
                start_session_monitoring(session_context.session_id, session_context.user_id)
        
        # Record security events
        if self._is_security_relevant(event_type):
            from .monitoring import record_security_event
            record_security_event(
                event_type.value,
                "medium",  # Default severity
                f"Browser security event: {event_type.value}",
                oauth2_context.flow_id if oauth2_context else None,
                session_context.session_id if session_context else None,
                oauth2_context.client_id if oauth2_context else None,
                session_context.user_id if session_context else None
            )


# Global browser authentication logger instance
browser_auth_logger = BrowserAuthenticationLogger()


# Convenience functions for common logging scenarios
def log_auth_flow_start(
    request: Request,
    flow_id: str,
    client_id: str,
    auth_method: AuthenticationMethod,
    redirect_uri: str,
    scopes: List[str],
    state: str,
    user_id: Optional[str] = None
) -> None:
    """Log OAuth2 authentication flow start."""
    browser_auth_logger.log_authentication_flow_start(
        request, flow_id, client_id, auth_method, redirect_uri, scopes, state, user_id
    )


def log_auth_redirect(
    request: Request,
    flow_id: str,
    redirect_type: str,
    redirect_url: str,
    state_preserved: bool = False,
    user_id: Optional[str] = None
) -> None:
    """Log authentication redirect."""
    browser_auth_logger.log_authentication_redirect(
        request, flow_id, redirect_type, redirect_url, state_preserved, user_id
    )


def log_session_lifecycle(
    event_type: BrowserAuthEvent,
    request: Request,
    session_id: str,
    user_id: str,
    session_data: Optional[Dict[str, Any]] = None
) -> None:
    """Log session lifecycle event."""
    browser_auth_logger.log_session_event(
        event_type, request, session_id, user_id, session_data
    )


def log_browser_security_event(
    event_type: BrowserAuthEvent,
    request: Request,
    severity: str,
    description: str,
    flow_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    threat_indicators: Optional[Dict[str, Any]] = None
) -> None:
    """Log browser security event."""
    browser_auth_logger.log_security_event(
        event_type, request, severity, description, flow_id, session_id, user_id, threat_indicators
    )


def log_template_performance(
    request: Request,
    template_name: str,
    render_time: float,
    flow_id: Optional[str] = None,
    additional_metrics: Optional[Dict[str, Any]] = None
) -> None:
    """Log template rendering performance."""
    event_type = (
        BrowserAuthEvent.TEMPLATE_RENDER_SLOW
        if render_time > 0.5
        else BrowserAuthEvent.TEMPLATE_RENDER_SLOW  # Use same event type for consistency
    )
    
    browser_auth_logger.log_performance_event(
        event_type, request, "template_render", render_time, flow_id, template_name, additional_metrics
    )