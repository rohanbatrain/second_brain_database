"""
Comprehensive monitoring and metrics system for OAuth2 browser authentication.

This module provides enterprise-grade monitoring capabilities for OAuth2 flows,
including metrics collection, performance monitoring, and operational dashboards.

Features:
- OAuth2 flow completion rate tracking by authentication method
- Performance metrics for template rendering and authentication
- Session lifecycle monitoring and analytics
- Security event monitoring and alerting
- Operational health checks and diagnostics
- Real-time metrics for monitoring dashboards
"""

import asyncio
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

from fastapi import Request
from pydantic import BaseModel

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[OAuth2 Monitoring]")


class AuthenticationMethod(str, Enum):
    """Authentication methods for OAuth2 flows."""
    JWT_TOKEN = "jwt_token"
    BROWSER_SESSION = "browser_session"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class FlowStage(str, Enum):
    """OAuth2 flow stages for completion tracking."""
    AUTHORIZATION_REQUEST = "authorization_request"
    AUTHENTICATION = "authentication"
    CONSENT = "consent"
    CODE_GENERATION = "code_generation"
    TOKEN_EXCHANGE = "token_exchange"
    COMPLETED = "completed"
    FAILED = "failed"


class MetricType(str, Enum):
    """Types of metrics collected."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class FlowMetrics:
    """Metrics for OAuth2 flow tracking."""
    flow_id: str
    client_id: str
    user_id: Optional[str]
    auth_method: AuthenticationMethod
    start_time: datetime
    current_stage: FlowStage
    stages_completed: List[FlowStage] = field(default_factory=list)
    stage_timings: Dict[FlowStage, float] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    template_render_times: Dict[str, float] = field(default_factory=dict)
    security_events: List[str] = field(default_factory=list)
    completed_at: Optional[datetime] = None
    total_duration: Optional[float] = None


@dataclass
class SessionMetrics:
    """Metrics for browser session lifecycle."""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    oauth2_flows: List[str] = field(default_factory=list)
    security_events: List[str] = field(default_factory=list)
    expired_at: Optional[datetime] = None
    cleanup_reason: Optional[str] = None


@dataclass
class PerformanceMetric:
    """Performance metric data point."""
    metric_name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE


class OAuth2MonitoringSystem:
    """
    Comprehensive monitoring system for OAuth2 browser authentication flows.
    
    Provides real-time metrics collection, performance monitoring, and
    operational insights for OAuth2 authentication flows with both
    API and browser clients.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[OAuth2 Monitoring System]")
        
        # Flow tracking
        self.active_flows: Dict[str, FlowMetrics] = {}
        self.completed_flows: deque = deque(maxlen=1000)  # Keep last 1000 completed flows
        
        # Session tracking
        self.active_sessions: Dict[str, SessionMetrics] = {}
        self.session_history: deque = deque(maxlen=500)  # Keep last 500 sessions
        
        # Performance metrics
        self.performance_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Completion rate tracking
        self.completion_rates: Dict[AuthenticationMethod, Dict[str, int]] = {
            AuthenticationMethod.JWT_TOKEN: {"completed": 0, "failed": 0, "total": 0},
            AuthenticationMethod.BROWSER_SESSION: {"completed": 0, "failed": 0, "total": 0},
            AuthenticationMethod.MIXED: {"completed": 0, "failed": 0, "total": 0}
        }
        
        # Template rendering metrics
        self.template_metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=50))
        
        # Security monitoring
        self.security_events: deque = deque(maxlen=200)
        
        # Health status
        self.health_status = {
            "monitoring_active": True,
            "last_health_check": datetime.now(timezone.utc),
            "active_flows_count": 0,
            "active_sessions_count": 0,
            "error_rate": 0.0,
            "avg_flow_duration": 0.0
        }
        
        # Start background monitoring tasks
        self._start_background_tasks()
    
    def start_oauth2_flow(
        self,
        flow_id: str,
        client_id: str,
        auth_method: AuthenticationMethod,
        user_id: Optional[str] = None,
        request: Optional[Request] = None
    ) -> None:
        """
        Start tracking an OAuth2 flow.
        
        Args:
            flow_id: Unique flow identifier
            client_id: OAuth2 client ID
            auth_method: Authentication method being used
            user_id: User ID if authenticated
            request: FastAPI request object
        """
        flow_metrics = FlowMetrics(
            flow_id=flow_id,
            client_id=client_id,
            user_id=user_id,
            auth_method=auth_method,
            start_time=datetime.now(timezone.utc),
            current_stage=FlowStage.AUTHORIZATION_REQUEST
        )
        
        self.active_flows[flow_id] = flow_metrics
        self.completion_rates[auth_method]["total"] += 1
        
        # Log flow start
        self.logger.info(
            "OAuth2 flow started",
            extra={
                "flow_id": flow_id,
                "client_id": client_id,
                "auth_method": auth_method.value,
                "user_id": user_id,
                "client_ip": request.client.host if request and request.client else None,
                "event_type": "flow_started"
            }
        )
        
        # Update health status
        self.health_status["active_flows_count"] = len(self.active_flows)
    
    def update_flow_stage(
        self,
        flow_id: str,
        stage: FlowStage,
        duration: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Update the current stage of an OAuth2 flow.
        
        Args:
            flow_id: Flow identifier
            stage: New flow stage
            duration: Time taken for this stage
            error: Error message if stage failed
        """
        if flow_id not in self.active_flows:
            self.logger.warning(f"Attempted to update unknown flow: {flow_id}")
            return
        
        flow = self.active_flows[flow_id]
        previous_stage = flow.current_stage
        
        # Record stage completion
        if stage != FlowStage.FAILED:
            flow.stages_completed.append(stage)
        
        # Record timing
        if duration is not None:
            flow.stage_timings[stage] = duration
        
        # Record error
        if error:
            flow.errors.append(f"{stage.value}: {error}")
        
        # Update current stage
        flow.current_stage = stage
        
        # Log stage update
        self.logger.info(
            "OAuth2 flow stage updated",
            extra={
                "flow_id": flow_id,
                "client_id": flow.client_id,
                "auth_method": flow.auth_method.value,
                "previous_stage": previous_stage.value,
                "new_stage": stage.value,
                "duration": duration,
                "error": error,
                "event_type": "flow_stage_updated"
            }
        )
        
        # Handle flow completion or failure
        if stage in [FlowStage.COMPLETED, FlowStage.FAILED]:
            self._complete_flow(flow_id, stage == FlowStage.COMPLETED)
    
    def record_template_render_time(
        self,
        flow_id: str,
        template_name: str,
        render_time: float
    ) -> None:
        """
        Record template rendering performance.
        
        Args:
            flow_id: Flow identifier
            template_name: Name of the template rendered
            render_time: Time taken to render in seconds
        """
        # Update flow metrics
        if flow_id in self.active_flows:
            self.active_flows[flow_id].template_render_times[template_name] = render_time
        
        # Update global template metrics
        self.template_metrics[template_name].append(render_time)
        
        # Log slow template rendering
        if render_time > 0.5:  # More than 500ms
            self.logger.warning(
                "Slow template rendering detected",
                extra={
                    "flow_id": flow_id,
                    "template_name": template_name,
                    "render_time": render_time,
                    "event_type": "slow_template_render"
                }
            )
        
        # Record performance metric
        self._record_performance_metric(
            f"template_render_time_{template_name}",
            render_time,
            {"template": template_name}
        )
    
    def record_security_event(
        self,
        flow_id: Optional[str],
        session_id: Optional[str],
        event_type: str,
        severity: str,
        description: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Record a security event for monitoring.
        
        Args:
            flow_id: Flow identifier if applicable
            session_id: Session identifier if applicable
            event_type: Type of security event
            severity: Event severity (low/medium/high/critical)
            description: Event description
            client_id: OAuth2 client ID
            user_id: User ID if applicable
        """
        security_event = {
            "timestamp": datetime.now(timezone.utc),
            "flow_id": flow_id,
            "session_id": session_id,
            "event_type": event_type,
            "severity": severity,
            "description": description,
            "client_id": client_id,
            "user_id": user_id
        }
        
        self.security_events.append(security_event)
        
        # Update flow metrics
        if flow_id and flow_id in self.active_flows:
            self.active_flows[flow_id].security_events.append(event_type)
        
        # Update session metrics
        if session_id and session_id in self.active_sessions:
            self.active_sessions[session_id].security_events.append(event_type)
        
        # Log security event
        log_level = "critical" if severity == "critical" else "warning"
        getattr(self.logger, log_level)(
            f"OAuth2 security event: {event_type}",
            extra={
                "flow_id": flow_id,
                "session_id": session_id,
                "event_type": event_type,
                "severity": severity,
                "description": description,
                "client_id": client_id,
                "user_id": user_id,
                "security_event": True
            }
        )
    
    def start_session_tracking(
        self,
        session_id: str,
        user_id: str
    ) -> None:
        """
        Start tracking a browser session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
        """
        session_metrics = SessionMetrics(
            session_id=session_id,
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
            last_activity=datetime.now(timezone.utc)
        )
        
        self.active_sessions[session_id] = session_metrics
        
        # Log session start
        self.logger.info(
            "Browser session started",
            extra={
                "session_id": session_id,
                "user_id": user_id,
                "event_type": "session_started"
            }
        )
        
        # Update health status
        self.health_status["active_sessions_count"] = len(self.active_sessions)
    
    def update_session_activity(
        self,
        session_id: str,
        flow_id: Optional[str] = None
    ) -> None:
        """
        Update session activity timestamp.
        
        Args:
            session_id: Session identifier
            flow_id: Flow identifier if part of OAuth2 flow
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.last_activity = datetime.now(timezone.utc)
            
            if flow_id and flow_id not in session.oauth2_flows:
                session.oauth2_flows.append(flow_id)
    
    def end_session_tracking(
        self,
        session_id: str,
        reason: str = "logout"
    ) -> None:
        """
        End session tracking.
        
        Args:
            session_id: Session identifier
            reason: Reason for session end
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]
            session.expired_at = datetime.now(timezone.utc)
            session.cleanup_reason = reason
            
            # Move to history
            self.session_history.append(session)
            del self.active_sessions[session_id]
            
            # Log session end
            self.logger.info(
                "Browser session ended",
                extra={
                    "session_id": session_id,
                    "user_id": session.user_id,
                    "reason": reason,
                    "duration": (session.expired_at - session.created_at).total_seconds(),
                    "oauth2_flows_count": len(session.oauth2_flows),
                    "event_type": "session_ended"
                }
            )
            
            # Update health status
            self.health_status["active_sessions_count"] = len(self.active_sessions)
    
    def get_completion_rates(self) -> Dict[str, Dict[str, float]]:
        """
        Get OAuth2 flow completion rates by authentication method.
        
        Returns:
            Dictionary with completion rates for each authentication method
        """
        rates = {}
        
        for auth_method, stats in self.completion_rates.items():
            total = stats["total"]
            if total > 0:
                completion_rate = (stats["completed"] / total) * 100
                failure_rate = (stats["failed"] / total) * 100
            else:
                completion_rate = 0.0
                failure_rate = 0.0
            
            rates[auth_method.value] = {
                "completion_rate": completion_rate,
                "failure_rate": failure_rate,
                "total_flows": total,
                "completed_flows": stats["completed"],
                "failed_flows": stats["failed"]
            }
        
        return rates
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics summary.
        
        Returns:
            Dictionary with performance metrics
        """
        metrics = {}
        
        # Template rendering metrics
        template_stats = {}
        for template_name, times in self.template_metrics.items():
            if times:
                template_stats[template_name] = {
                    "avg_render_time": sum(times) / len(times),
                    "max_render_time": max(times),
                    "min_render_time": min(times),
                    "render_count": len(times)
                }
        
        metrics["template_rendering"] = template_stats
        
        # Flow duration metrics
        completed_flows = list(self.completed_flows)
        if completed_flows:
            durations = [f.total_duration for f in completed_flows if f.total_duration]
            if durations:
                metrics["flow_duration"] = {
                    "avg_duration": sum(durations) / len(durations),
                    "max_duration": max(durations),
                    "min_duration": min(durations)
                }
        
        # Performance metrics by type
        perf_summary = {}
        for metric_name, values in self.performance_metrics.items():
            if values:
                perf_summary[metric_name] = {
                    "current": values[-1].value if values else 0,
                    "avg": sum(v.value for v in values) / len(values),
                    "max": max(v.value for v in values),
                    "min": min(v.value for v in values)
                }
        
        metrics["performance"] = perf_summary
        
        return metrics
    
    def get_security_summary(self) -> Dict[str, Any]:
        """
        Get security events summary.
        
        Returns:
            Dictionary with security metrics
        """
        if not self.security_events:
            return {"total_events": 0, "events_by_type": {}, "events_by_severity": {}}
        
        events_by_type = defaultdict(int)
        events_by_severity = defaultdict(int)
        
        for event in self.security_events:
            events_by_type[event["event_type"]] += 1
            events_by_severity[event["severity"]] += 1
        
        return {
            "total_events": len(self.security_events),
            "events_by_type": dict(events_by_type),
            "events_by_severity": dict(events_by_severity),
            "recent_events": list(self.security_events)[-10:]  # Last 10 events
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get system health status.
        
        Returns:
            Dictionary with health metrics
        """
        # Update error rate
        completed_flows = list(self.completed_flows)
        if completed_flows:
            failed_count = sum(1 for f in completed_flows if f.current_stage == FlowStage.FAILED)
            self.health_status["error_rate"] = (failed_count / len(completed_flows)) * 100
            
            # Update average flow duration
            durations = [f.total_duration for f in completed_flows if f.total_duration]
            if durations:
                self.health_status["avg_flow_duration"] = sum(durations) / len(durations)
        
        self.health_status["last_health_check"] = datetime.now(timezone.utc)
        
        return self.health_status.copy()
    
    def _complete_flow(self, flow_id: str, success: bool) -> None:
        """Complete flow tracking and update metrics."""
        if flow_id not in self.active_flows:
            return
        
        flow = self.active_flows[flow_id]
        flow.completed_at = datetime.now(timezone.utc)
        flow.total_duration = (flow.completed_at - flow.start_time).total_seconds()
        
        # Update completion rates
        if success:
            self.completion_rates[flow.auth_method]["completed"] += 1
            flow.current_stage = FlowStage.COMPLETED
        else:
            self.completion_rates[flow.auth_method]["failed"] += 1
            flow.current_stage = FlowStage.FAILED
        
        # Move to completed flows
        self.completed_flows.append(flow)
        del self.active_flows[flow_id]
        
        # Log completion
        self.logger.info(
            f"OAuth2 flow {'completed' if success else 'failed'}",
            extra={
                "flow_id": flow_id,
                "client_id": flow.client_id,
                "auth_method": flow.auth_method.value,
                "duration": flow.total_duration,
                "stages_completed": len(flow.stages_completed),
                "errors_count": len(flow.errors),
                "success": success,
                "event_type": "flow_completed"
            }
        )
        
        # Update health status
        self.health_status["active_flows_count"] = len(self.active_flows)
    
    def _record_performance_metric(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a performance metric."""
        metric = PerformanceMetric(
            metric_name=metric_name,
            value=value,
            timestamp=datetime.now(timezone.utc),
            labels=labels or {}
        )
        
        self.performance_metrics[metric_name].append(metric)
    
    def _start_background_tasks(self) -> None:
        """Start background monitoring tasks."""
        # Note: In a real implementation, these would be proper background tasks
        # For now, we'll implement cleanup methods that can be called periodically
        pass
    
    async def cleanup_expired_flows(self) -> None:
        """Clean up expired flows that haven't completed."""
        current_time = datetime.now(timezone.utc)
        expired_flows = []
        
        for flow_id, flow in self.active_flows.items():
            # Consider flows older than 1 hour as expired
            if (current_time - flow.start_time).total_seconds() > 3600:
                expired_flows.append(flow_id)
        
        for flow_id in expired_flows:
            self.logger.warning(
                f"Cleaning up expired OAuth2 flow: {flow_id}",
                extra={"flow_id": flow_id, "event_type": "flow_expired"}
            )
            self._complete_flow(flow_id, success=False)
    
    async def cleanup_expired_sessions(self) -> None:
        """Clean up expired session tracking."""
        current_time = datetime.now(timezone.utc)
        expired_sessions = []
        
        for session_id, session in self.active_sessions.items():
            # Consider sessions inactive for more than 24 hours as expired
            if (current_time - session.last_activity).total_seconds() > 86400:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            self.end_session_tracking(session_id, "expired")


# Global monitoring system instance
oauth2_monitoring = OAuth2MonitoringSystem()


# Convenience functions for common monitoring operations
def start_flow_monitoring(
    flow_id: str,
    client_id: str,
    auth_method: AuthenticationMethod,
    user_id: Optional[str] = None,
    request: Optional[Request] = None
) -> None:
    """Start monitoring an OAuth2 flow."""
    oauth2_monitoring.start_oauth2_flow(flow_id, client_id, auth_method, user_id, request)


def update_flow_stage(
    flow_id: str,
    stage: FlowStage,
    duration: Optional[float] = None,
    error: Optional[str] = None
) -> None:
    """Update OAuth2 flow stage."""
    oauth2_monitoring.update_flow_stage(flow_id, stage, duration, error)


def record_template_performance(
    flow_id: str,
    template_name: str,
    render_time: float
) -> None:
    """Record template rendering performance."""
    oauth2_monitoring.record_template_render_time(flow_id, template_name, render_time)


def record_security_event(
    event_type: str,
    severity: str,
    description: str,
    flow_id: Optional[str] = None,
    session_id: Optional[str] = None,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> None:
    """Record a security event."""
    oauth2_monitoring.record_security_event(
        flow_id, session_id, event_type, severity, description, client_id, user_id
    )


def start_session_monitoring(session_id: str, user_id: str) -> None:
    """Start monitoring a browser session."""
    oauth2_monitoring.start_session_tracking(session_id, user_id)


def update_session_activity(session_id: str, flow_id: Optional[str] = None) -> None:
    """Update session activity."""
    oauth2_monitoring.update_session_activity(session_id, flow_id)


def end_session_monitoring(session_id: str, reason: str = "logout") -> None:
    """End session monitoring."""
    oauth2_monitoring.end_session_tracking(session_id, reason)