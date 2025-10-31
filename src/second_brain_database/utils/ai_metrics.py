"""
AI Performance Metrics and Monitoring Utilities
Requirement 8.1, 8.2, 8.3: Performance optimization and monitoring
"""

import time
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Individual performance metric data point"""
    name: str
    value: float
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SessionMetrics:
    """Metrics for an AI session"""
    session_id: str
    start_time: datetime
    message_count: int = 0
    total_tokens: int = 0
    avg_response_time: float = 0.0
    websocket_reconnects: int = 0
    voice_messages: int = 0
    tool_executions: int = 0
    errors: int = 0
    last_activity: Optional[datetime] = None

class AIPerformanceMonitor:
    """
    Monitors AI system performance metrics
    Requirement 8.1: Sub-500ms response time for message transmission
    Requirement 8.2: Display tokens with less than 100ms latency
    Requirement 8.3: Complete STT processing within 3 seconds
    """
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.metrics: deque = deque(maxlen=max_history)
        self.session_metrics: Dict[str, SessionMetrics] = {}
        self.response_times: deque = deque(maxlen=100)
        self.token_latencies: deque = deque(maxlen=500)
        self.voice_processing_times: deque = deque(maxlen=50)
        self.websocket_stats = {
            'connections': 0,
            'disconnections': 0,
            'reconnections': 0,
            'messages_sent': 0,
            'messages_received': 0,
            'errors': 0
        }
        
    def record_metric(self, name: str, value: float, metadata: Optional[Dict[str, Any]] = None):
        """Record a performance metric"""
        metric = PerformanceMetric(
            name=name,
            value=value,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata or {}
        )
        self.metrics.append(metric)
        
    def start_session(self, session_id: str) -> SessionMetrics:
        """Start tracking metrics for a new session"""
        session_metrics = SessionMetrics(
            session_id=session_id,
            start_time=datetime.now(timezone.utc)
        )
        self.session_metrics[session_id] = session_metrics
        logger.info(f"Started metrics tracking for session {session_id}")
        return session_metrics
        
    def end_session(self, session_id: str):
        """End tracking for a session"""
        if session_id in self.session_metrics:
            session = self.session_metrics[session_id]
            duration = (datetime.now(timezone.utc) - session.start_time).total_seconds()
            
            self.record_metric("session_duration", duration, {
                "session_id": session_id,
                "message_count": session.message_count,
                "total_tokens": session.total_tokens,
                "avg_response_time": session.avg_response_time
            })
            
            del self.session_metrics[session_id]
            logger.info(f"Ended metrics tracking for session {session_id}, duration: {duration:.2f}s")
    
    def record_message_response_time(self, session_id: str, response_time: float):
        """
        Record message response time
        Requirement 8.1: Sub-500ms response time for message transmission
        """
        self.response_times.append(response_time)
        self.record_metric("message_response_time", response_time, {"session_id": session_id})
        
        # Update session metrics
        if session_id in self.session_metrics:
            session = self.session_metrics[session_id]
            session.message_count += 1
            session.last_activity = datetime.now(timezone.utc)
            
            # Calculate running average
            if session.avg_response_time == 0:
                session.avg_response_time = response_time
            else:
                session.avg_response_time = (
                    (session.avg_response_time * (session.message_count - 1) + response_time) 
                    / session.message_count
                )
        
        # Log warning if response time exceeds target
        if response_time > 0.5:  # 500ms threshold
            logger.warning(f"Message response time exceeded target: {response_time:.3f}s (session: {session_id})")
    
    def record_token_latency(self, session_id: str, latency: float):
        """
        Record token streaming latency
        Requirement 8.2: Display tokens with less than 100ms latency
        """
        self.token_latencies.append(latency)
        self.record_metric("token_latency", latency, {"session_id": session_id})
        
        # Update session token count
        if session_id in self.session_metrics:
            self.session_metrics[session_id].total_tokens += 1
        
        # Log warning if latency exceeds target
        if latency > 0.1:  # 100ms threshold
            logger.warning(f"Token latency exceeded target: {latency:.3f}s (session: {session_id})")
    
    def record_voice_processing_time(self, session_id: str, processing_time: float, 
                                   processing_type: str = "stt"):
        """
        Record voice processing time
        Requirement 8.3: Complete STT processing within 3 seconds
        """
        self.voice_processing_times.append(processing_time)
        self.record_metric("voice_processing_time", processing_time, {
            "session_id": session_id,
            "type": processing_type
        })
        
        # Update session voice message count
        if session_id in self.session_metrics:
            self.session_metrics[session_id].voice_messages += 1
        
        # Log warning if processing time exceeds target
        if processing_type == "stt" and processing_time > 3.0:  # 3 second threshold for STT
            logger.warning(f"STT processing time exceeded target: {processing_time:.3f}s (session: {session_id})")
        elif processing_type == "tts" and processing_time > 1.0:  # 1 second threshold for TTS playback
            logger.warning(f"TTS playback time exceeded target: {processing_time:.3f}s (session: {session_id})")
    
    def record_websocket_event(self, event_type: str, session_id: Optional[str] = None):
        """Record WebSocket events for connection monitoring"""
        if event_type in self.websocket_stats:
            self.websocket_stats[event_type] += 1
        
        self.record_metric(f"websocket_{event_type}", 1, {"session_id": session_id})
        
        # Track reconnections per session
        if event_type == "reconnections" and session_id and session_id in self.session_metrics:
            self.session_metrics[session_id].websocket_reconnects += 1
    
    def record_tool_execution(self, session_id: str, tool_name: str, execution_time: float, 
                            success: bool = True):
        """Record tool execution metrics"""
        self.record_metric("tool_execution_time", execution_time, {
            "session_id": session_id,
            "tool_name": tool_name,
            "success": success
        })
        
        # Update session tool execution count
        if session_id in self.session_metrics:
            self.session_metrics[session_id].tool_executions += 1
            if not success:
                self.session_metrics[session_id].errors += 1
    
    def record_error(self, session_id: str, error_type: str, error_message: str):
        """Record error occurrences"""
        self.record_metric("error", 1, {
            "session_id": session_id,
            "error_type": error_type,
            "error_message": error_message
        })
        
        # Update session error count
        if session_id in self.session_metrics:
            self.session_metrics[session_id].errors += 1
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        now = datetime.now(timezone.utc)
        
        # Calculate averages
        avg_response_time = sum(self.response_times) / len(self.response_times) if self.response_times else 0
        avg_token_latency = sum(self.token_latencies) / len(self.token_latencies) if self.token_latencies else 0
        avg_voice_processing = sum(self.voice_processing_times) / len(self.voice_processing_times) if self.voice_processing_times else 0
        
        # Performance targets compliance
        response_time_compliance = sum(1 for rt in self.response_times if rt <= 0.5) / len(self.response_times) * 100 if self.response_times else 100
        token_latency_compliance = sum(1 for tl in self.token_latencies if tl <= 0.1) / len(self.token_latencies) * 100 if self.token_latencies else 100
        voice_processing_compliance = sum(1 for vp in self.voice_processing_times if vp <= 3.0) / len(self.voice_processing_times) * 100 if self.voice_processing_times else 100
        
        # Active sessions
        active_sessions = len([s for s in self.session_metrics.values() 
                             if s.last_activity and (now - s.last_activity).total_seconds() < 300])
        
        return {
            "timestamp": now.isoformat(),
            "performance_metrics": {
                "avg_response_time_ms": avg_response_time * 1000,
                "avg_token_latency_ms": avg_token_latency * 1000,
                "avg_voice_processing_ms": avg_voice_processing * 1000,
                "response_time_compliance_pct": response_time_compliance,
                "token_latency_compliance_pct": token_latency_compliance,
                "voice_processing_compliance_pct": voice_processing_compliance
            },
            "session_metrics": {
                "active_sessions": active_sessions,
                "total_sessions": len(self.session_metrics),
                "total_messages": sum(s.message_count for s in self.session_metrics.values()),
                "total_tokens": sum(s.total_tokens for s in self.session_metrics.values()),
                "total_voice_messages": sum(s.voice_messages for s in self.session_metrics.values()),
                "total_tool_executions": sum(s.tool_executions for s in self.session_metrics.values()),
                "total_errors": sum(s.errors for s in self.session_metrics.values())
            },
            "websocket_stats": self.websocket_stats.copy(),
            "health_status": self._calculate_health_status(
                response_time_compliance, 
                token_latency_compliance, 
                voice_processing_compliance
            )
        }
    
    def _calculate_health_status(self, response_compliance: float, 
                               token_compliance: float, voice_compliance: float) -> str:
        """Calculate overall system health status"""
        avg_compliance = (response_compliance + token_compliance + voice_compliance) / 3
        
        if avg_compliance >= 95:
            return "excellent"
        elif avg_compliance >= 85:
            return "good"
        elif avg_compliance >= 70:
            return "fair"
        else:
            return "poor"
    
    def get_session_metrics(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get metrics for a specific session"""
        if session_id not in self.session_metrics:
            return None
            
        session = self.session_metrics[session_id]
        duration = (datetime.now(timezone.utc) - session.start_time).total_seconds()
        
        return {
            "session_id": session_id,
            "duration_seconds": duration,
            "message_count": session.message_count,
            "total_tokens": session.total_tokens,
            "avg_response_time_ms": session.avg_response_time * 1000,
            "websocket_reconnects": session.websocket_reconnects,
            "voice_messages": session.voice_messages,
            "tool_executions": session.tool_executions,
            "errors": session.errors,
            "last_activity": session.last_activity.isoformat() if session.last_activity else None
        }
    
    def cleanup_old_metrics(self, max_age_hours: int = 24):
        """Clean up old metrics to prevent memory bloat"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        
        # Clean up general metrics
        initial_count = len(self.metrics)
        self.metrics = deque(
            (m for m in self.metrics if m.timestamp > cutoff_time),
            maxlen=self.max_history
        )
        
        # Clean up inactive sessions
        inactive_sessions = [
            sid for sid, session in self.session_metrics.items()
            if not session.last_activity or session.last_activity < cutoff_time
        ]
        
        for session_id in inactive_sessions:
            self.end_session(session_id)
        
        logger.info(f"Cleaned up {initial_count - len(self.metrics)} old metrics and {len(inactive_sessions)} inactive sessions")

# Global performance monitor instance
ai_performance_monitor = AIPerformanceMonitor()

class PerformanceTimer:
    """Context manager for timing operations"""
    
    def __init__(self, monitor: AIPerformanceMonitor, metric_name: str, 
                 session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self.monitor = monitor
        self.metric_name = metric_name
        self.session_id = session_id
        self.metadata = metadata or {}
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            
            # Record appropriate metric based on type
            if "response_time" in self.metric_name and self.session_id:
                self.monitor.record_message_response_time(self.session_id, duration)
            elif "token_latency" in self.metric_name and self.session_id:
                self.monitor.record_token_latency(self.session_id, duration)
            elif "voice_processing" in self.metric_name and self.session_id:
                processing_type = self.metadata.get("type", "stt")
                self.monitor.record_voice_processing_time(self.session_id, duration, processing_type)
            elif "tool_execution" in self.metric_name and self.session_id:
                tool_name = self.metadata.get("tool_name", "unknown")
                success = exc_type is None
                self.monitor.record_tool_execution(self.session_id, tool_name, duration, success)
            else:
                self.monitor.record_metric(self.metric_name, duration, self.metadata)

def performance_timer(metric_name: str, session_id: Optional[str] = None, 
                     metadata: Optional[Dict[str, Any]] = None):
    """Decorator for timing function execution"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            with PerformanceTimer(ai_performance_monitor, metric_name, session_id, metadata):
                return await func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            with PerformanceTimer(ai_performance_monitor, metric_name, session_id, metadata):
                return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator