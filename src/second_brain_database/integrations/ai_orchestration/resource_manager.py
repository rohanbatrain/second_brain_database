"""
AI Resource Management System

This module provides comprehensive resource management for AI operations
including session cleanup, memory optimization, and performance monitoring.

Features:
- Automatic session cleanup and resource management
- Memory usage optimization and monitoring
- Performance metrics collection and analysis
- Resource scaling and load balancing support
- Circuit breaker patterns for external dependencies
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import asyncio
import gc
import weakref
from collections import defaultdict

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    # Mock psutil for basic functionality
    class MockProcess:
        def memory_info(self):
            return type('MemoryInfo', (), {'rss': 0})()
        def cpu_percent(self):
            return 0.0
    
    class MockPsutil:
        def Process(self):
            return MockProcess()
    
    psutil = MockPsutil()

from ...managers.redis_manager import redis_manager
from ...managers.logging_manager import get_logger
from ...config import settings

logger = get_logger(prefix="[ResourceManager]")


@dataclass
class ResourceMetrics:
    """Resource usage metrics."""
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0
    active_sessions: int = 0
    cached_contexts: int = 0
    model_pool_usage: int = 0
    redis_connections: int = 0
    mongodb_connections: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SessionInfo:
    """Session information for resource tracking."""
    session_id: str
    user_id: str
    created_at: datetime
    last_activity: datetime
    memory_usage_mb: float = 0.0
    message_count: int = 0
    agent_type: str = "personal"
    status: str = "active"  # active, idle, expired


@dataclass
class PerformanceThresholds:
    """Performance thresholds for resource management."""
    max_memory_mb: float = 1024.0  # 1GB default
    max_cpu_percent: float = 80.0
    max_sessions: int = 100
    session_timeout_minutes: int = 60
    idle_timeout_minutes: int = 30
    cleanup_interval_minutes: int = 5


class CircuitBreaker:
    """
    Circuit breaker pattern for external service dependencies.
    
    Prevents cascading failures by temporarily disabling calls
    to failing external services.
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
        self.logger = get_logger(prefix="[CircuitBreaker]")
    
    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
                self.logger.info("Circuit breaker half-open, attempting reset")
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except Exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = datetime.now(timezone.utc) - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            self.logger.warning(
                "Circuit breaker opened after %d failures",
                self.failure_count
            )


class ResourceManager:
    """
    Comprehensive resource management system for AI operations.
    
    Manages sessions, memory usage, performance monitoring,
    and automatic cleanup of resources.
    """
    
    def __init__(self):
        """Initialize the resource manager."""
        self.logger = get_logger(prefix="[ResourceManager]")
        
        # Configuration
        self.thresholds = PerformanceThresholds(
            max_memory_mb=getattr(settings, 'AI_MAX_MEMORY_MB', 1024.0),
            max_cpu_percent=getattr(settings, 'AI_MAX_CPU_PERCENT', 80.0),
            max_sessions=settings.AI_MAX_CONCURRENT_SESSIONS,
            session_timeout_minutes=settings.AI_SESSION_TIMEOUT // 60,
            idle_timeout_minutes=getattr(settings, 'AI_IDLE_TIMEOUT', 1800) // 60,
            cleanup_interval_minutes=settings.AI_SESSION_CLEANUP_INTERVAL // 60
        )
        
        # Resource tracking
        self.active_sessions: Dict[str, SessionInfo] = {}
        self.session_refs: Dict[str, weakref.ref] = {}
        self.metrics_history: List[ResourceMetrics] = []
        self.max_metrics_history = 100
        
        # Circuit breakers for external services
        self.circuit_breakers = {
            "ollama": CircuitBreaker(failure_threshold=3, recovery_timeout=30),
            "redis": CircuitBreaker(failure_threshold=5, recovery_timeout=60),
            "mongodb": CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        }
        
        # Background tasks
        self.cleanup_task = None
        self.monitoring_task = None
        self.running = False
        
        # Performance optimization flags
        self.memory_pressure = False
        self.cpu_pressure = False
        self.session_pressure = False
    
    async def start(self):
        """Start the resource manager background tasks."""
        if self.running:
            return
        
        self.running = True
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_task())
        
        # Start monitoring task
        self.monitoring_task = asyncio.create_task(self._monitoring_task())
        
        self.logger.info("Resource manager started")
    
    async def stop(self):
        """Stop the resource manager background tasks."""
        self.running = False
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Resource manager stopped")
    
    async def _cleanup_task(self):
        """Background task for resource cleanup."""
        while self.running:
            try:
                await asyncio.sleep(self.thresholds.cleanup_interval_minutes * 60)
                await self._perform_cleanup()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Cleanup task error: %s", e)
    
    async def _monitoring_task(self):
        """Background task for performance monitoring."""
        while self.running:
            try:
                await asyncio.sleep(30)  # Monitor every 30 seconds
                await self._collect_metrics()
                await self._check_thresholds()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Monitoring task error: %s", e)
    
    async def _perform_cleanup(self):
        """Perform comprehensive resource cleanup."""
        try:
            cleanup_stats = {
                "expired_sessions": 0,
                "idle_sessions": 0,
                "memory_freed_mb": 0.0,
                "cache_entries_cleared": 0
            }
            
            # Clean up expired sessions
            expired_sessions = await self._cleanup_expired_sessions()
            cleanup_stats["expired_sessions"] = len(expired_sessions)
            
            # Clean up idle sessions
            idle_sessions = await self._cleanup_idle_sessions()
            cleanup_stats["idle_sessions"] = len(idle_sessions)
            
            # Force garbage collection if under memory pressure
            if self.memory_pressure:
                before_gc = psutil.Process().memory_info().rss / 1024 / 1024
                gc.collect()
                after_gc = psutil.Process().memory_info().rss / 1024 / 1024
                cleanup_stats["memory_freed_mb"] = before_gc - after_gc
                
                self.logger.info("Forced garbage collection freed %.2f MB", 
                               cleanup_stats["memory_freed_mb"])
            
            # Clean up old cache entries if under pressure
            if self.memory_pressure or self.session_pressure:
                cache_cleared = await self._cleanup_cache_entries()
                cleanup_stats["cache_entries_cleared"] = cache_cleared
            
            # Clean up old metrics
            self._cleanup_old_metrics()
            
            # Log cleanup results
            if any(cleanup_stats.values()):
                self.logger.info("Cleanup completed: %s", cleanup_stats)
            
        except Exception as e:
            self.logger.error("Cleanup failed: %s", e)
    
    async def _cleanup_expired_sessions(self) -> List[str]:
        """Clean up expired sessions."""
        expired_sessions = []
        current_time = datetime.now(timezone.utc)
        timeout_delta = timedelta(minutes=self.thresholds.session_timeout_minutes)
        
        for session_id, session_info in list(self.active_sessions.items()):
            if current_time - session_info.last_activity > timeout_delta:
                await self._cleanup_session(session_id, "expired")
                expired_sessions.append(session_id)
        
        return expired_sessions
    
    async def _cleanup_idle_sessions(self) -> List[str]:
        """Clean up idle sessions."""
        idle_sessions = []
        current_time = datetime.now(timezone.utc)
        idle_delta = timedelta(minutes=self.thresholds.idle_timeout_minutes)
        
        # Only clean up idle sessions if we're under pressure
        if not (self.memory_pressure or self.session_pressure):
            return idle_sessions
        
        for session_id, session_info in list(self.active_sessions.items()):
            time_since_activity = current_time - session_info.last_activity
            if (time_since_activity > idle_delta and 
                session_info.status == "idle" and
                session_info.message_count == 0):
                
                await self._cleanup_session(session_id, "idle_cleanup")
                idle_sessions.append(session_id)
        
        return idle_sessions
    
    async def _cleanup_cache_entries(self) -> int:
        """Clean up old cache entries."""
        try:
            redis = await redis_manager.get_redis()
            
            # Get all AI-related cache keys
            cache_patterns = [
                "ai:context:*",
                "ai:model:cache:*",
                "ai:conversation:*"
            ]
            
            total_cleared = 0
            for pattern in cache_patterns:
                keys = await redis.keys(pattern)
                
                # Remove oldest 25% of entries for each pattern
                if len(keys) > 10:  # Only if we have significant cache
                    keys_to_remove = keys[:len(keys) // 4]
                    if keys_to_remove:
                        await redis.delete(*keys_to_remove)
                        total_cleared += len(keys_to_remove)
            
            return total_cleared
            
        except Exception as e:
            self.logger.error("Failed to cleanup cache entries: %s", e)
            return 0
    
    def _cleanup_old_metrics(self):
        """Clean up old metrics history."""
        if len(self.metrics_history) > self.max_metrics_history:
            self.metrics_history = self.metrics_history[-self.max_metrics_history:]
    
    async def _collect_metrics(self):
        """Collect current resource metrics."""
        try:
            # Get system metrics
            process = psutil.Process()
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()
            
            # Get Redis connection count
            redis_connections = 0
            try:
                redis = await redis_manager.get_redis()
                info = await redis.info("clients")
                redis_connections = info.get("connected_clients", 0)
            except:
                pass
            
            # Create metrics object
            metrics = ResourceMetrics(
                memory_usage_mb=memory_info.rss / 1024 / 1024,
                cpu_usage_percent=cpu_percent,
                active_sessions=len(self.active_sessions),
                redis_connections=redis_connections,
                timestamp=datetime.now(timezone.utc)
            )
            
            # Add to history
            self.metrics_history.append(metrics)
            
            # Persist metrics to Redis for monitoring
            await self._persist_metrics(metrics)
            
        except Exception as e:
            self.logger.error("Failed to collect metrics: %s", e)
    
    async def _persist_metrics(self, metrics: ResourceMetrics):
        """Persist metrics to Redis."""
        try:
            redis = await redis_manager.get_redis()
            
            metrics_data = {
                "memory_usage_mb": metrics.memory_usage_mb,
                "cpu_usage_percent": metrics.cpu_usage_percent,
                "active_sessions": metrics.active_sessions,
                "redis_connections": metrics.redis_connections,
                "timestamp": metrics.timestamp.isoformat()
            }
            
            await redis.setex(
                "ai:resource:metrics",
                300,  # 5 minute TTL
                str(metrics_data)
            )
            
        except Exception as e:
            self.logger.error("Failed to persist metrics: %s", e)
    
    async def _check_thresholds(self):
        """Check resource thresholds and update pressure flags."""
        if not self.metrics_history:
            return
        
        current_metrics = self.metrics_history[-1]
        
        # Check memory pressure
        memory_pressure = current_metrics.memory_usage_mb > self.thresholds.max_memory_mb
        if memory_pressure != self.memory_pressure:
            self.memory_pressure = memory_pressure
            if memory_pressure:
                self.logger.warning(
                    "Memory pressure detected: %.2f MB > %.2f MB",
                    current_metrics.memory_usage_mb,
                    self.thresholds.max_memory_mb
                )
        
        # Check CPU pressure
        cpu_pressure = current_metrics.cpu_usage_percent > self.thresholds.max_cpu_percent
        if cpu_pressure != self.cpu_pressure:
            self.cpu_pressure = cpu_pressure
            if cpu_pressure:
                self.logger.warning(
                    "CPU pressure detected: %.2f%% > %.2f%%",
                    current_metrics.cpu_usage_percent,
                    self.thresholds.max_cpu_percent
                )
        
        # Check session pressure
        session_pressure = current_metrics.active_sessions > self.thresholds.max_sessions
        if session_pressure != self.session_pressure:
            self.session_pressure = session_pressure
            if session_pressure:
                self.logger.warning(
                    "Session pressure detected: %d > %d",
                    current_metrics.active_sessions,
                    self.thresholds.max_sessions
                )
    
    async def register_session(
        self,
        session_id: str,
        user_id: str,
        agent_type: str = "personal"
    ) -> bool:
        """
        Register a new session for resource tracking.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            agent_type: Type of agent handling the session
            
        Returns:
            True if registered successfully, False if rejected due to limits
        """
        try:
            # Check if we're at session limit
            if len(self.active_sessions) >= self.thresholds.max_sessions:
                self.logger.warning(
                    "Session registration rejected: at limit (%d)",
                    self.thresholds.max_sessions
                )
                return False
            
            # Create session info
            session_info = SessionInfo(
                session_id=session_id,
                user_id=user_id,
                created_at=datetime.now(timezone.utc),
                last_activity=datetime.now(timezone.utc),
                agent_type=agent_type,
                status="active"
            )
            
            self.active_sessions[session_id] = session_info
            
            self.logger.debug("Registered session %s for user %s", session_id, user_id)
            return True
            
        except Exception as e:
            self.logger.error("Failed to register session %s: %s", session_id, e)
            return False
    
    async def update_session_activity(
        self,
        session_id: str,
        message_count_delta: int = 1,
        memory_usage_mb: float = None
    ):
        """
        Update session activity and resource usage.
        
        Args:
            session_id: Session identifier
            message_count_delta: Change in message count
            memory_usage_mb: Current memory usage estimate
        """
        try:
            session_info = self.active_sessions.get(session_id)
            if session_info:
                session_info.last_activity = datetime.now(timezone.utc)
                session_info.message_count += message_count_delta
                session_info.status = "active"
                
                if memory_usage_mb is not None:
                    session_info.memory_usage_mb = memory_usage_mb
                
        except Exception as e:
            self.logger.error("Failed to update session activity %s: %s", session_id, e)
    
    async def mark_session_idle(self, session_id: str):
        """Mark a session as idle."""
        try:
            session_info = self.active_sessions.get(session_id)
            if session_info:
                session_info.status = "idle"
                
        except Exception as e:
            self.logger.error("Failed to mark session idle %s: %s", session_id, e)
    
    async def _cleanup_session(self, session_id: str, reason: str = "manual"):
        """Clean up a specific session."""
        try:
            session_info = self.active_sessions.get(session_id)
            if session_info:
                # Remove from active sessions
                del self.active_sessions[session_id]
                
                # Clean up session cache
                await self._cleanup_session_cache(session_id)
                
                self.logger.debug(
                    "Cleaned up session %s (reason: %s, duration: %s)",
                    session_id,
                    reason,
                    datetime.now(timezone.utc) - session_info.created_at
                )
                
        except Exception as e:
            self.logger.error("Failed to cleanup session %s: %s", session_id, e)
    
    async def _cleanup_session_cache(self, session_id: str):
        """Clean up cache entries for a session."""
        try:
            redis = await redis_manager.get_redis()
            
            # Clean up conversation cache
            conversation_key = f"ai:conversation:{session_id}"
            await redis.delete(conversation_key)
            
            # Clean up any session-specific context cache
            context_pattern = f"ai:context:*:{session_id}"
            context_keys = await redis.keys(context_pattern)
            if context_keys:
                await redis.delete(*context_keys)
                
        except Exception as e:
            self.logger.error("Failed to cleanup session cache %s: %s", session_id, e)
    
    async def cleanup_session(self, session_id: str) -> bool:
        """
        Manually clean up a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if cleaned up successfully, False otherwise
        """
        try:
            await self._cleanup_session(session_id, "manual")
            return True
            
        except Exception as e:
            self.logger.error("Failed to cleanup session %s: %s", session_id, e)
            return False
    
    def get_circuit_breaker(self, service: str) -> Optional[CircuitBreaker]:
        """
        Get circuit breaker for a service.
        
        Args:
            service: Service name (ollama, redis, mongodb)
            
        Returns:
            CircuitBreaker instance or None
        """
        return self.circuit_breakers.get(service)
    
    async def execute_with_circuit_breaker(
        self,
        service: str,
        func,
        *args,
        **kwargs
    ):
        """
        Execute function with circuit breaker protection.
        
        Args:
            service: Service name
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Exception: If circuit breaker is open or function fails
        """
        circuit_breaker = self.get_circuit_breaker(service)
        if circuit_breaker:
            return await circuit_breaker.call(func, *args, **kwargs)
        else:
            return await func(*args, **kwargs)
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get current resource status."""
        current_metrics = self.metrics_history[-1] if self.metrics_history else None
        
        return {
            "status": "healthy" if not any([
                self.memory_pressure, self.cpu_pressure, self.session_pressure
            ]) else "under_pressure",
            "pressures": {
                "memory": self.memory_pressure,
                "cpu": self.cpu_pressure,
                "sessions": self.session_pressure
            },
            "current_metrics": {
                "memory_usage_mb": current_metrics.memory_usage_mb if current_metrics else 0,
                "cpu_usage_percent": current_metrics.cpu_usage_percent if current_metrics else 0,
                "active_sessions": len(self.active_sessions),
                "redis_connections": current_metrics.redis_connections if current_metrics else 0
            },
            "thresholds": {
                "max_memory_mb": self.thresholds.max_memory_mb,
                "max_cpu_percent": self.thresholds.max_cpu_percent,
                "max_sessions": self.thresholds.max_sessions
            },
            "circuit_breakers": {
                name: {
                    "state": cb.state,
                    "failure_count": cb.failure_count,
                    "last_failure": cb.last_failure_time.isoformat() if cb.last_failure_time else None
                }
                for name, cb in self.circuit_breakers.items()
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session."""
        session_info = self.active_sessions.get(session_id)
        if session_info:
            return {
                "session_id": session_info.session_id,
                "user_id": session_info.user_id,
                "agent_type": session_info.agent_type,
                "status": session_info.status,
                "created_at": session_info.created_at.isoformat(),
                "last_activity": session_info.last_activity.isoformat(),
                "message_count": session_info.message_count,
                "memory_usage_mb": session_info.memory_usage_mb,
                "duration_minutes": (
                    datetime.now(timezone.utc) - session_info.created_at
                ).total_seconds() / 60
            }
        return None
    
    def list_active_sessions(self) -> List[Dict[str, Any]]:
        """List all active sessions."""
        return [
            self.get_session_info(session_id)
            for session_id in self.active_sessions.keys()
        ]
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics history."""
        if not self.metrics_history:
            return {"error": "No metrics available"}
        
        # Calculate averages over last 10 minutes
        recent_metrics = [
            m for m in self.metrics_history
            if (datetime.now(timezone.utc) - m.timestamp).total_seconds() <= 600
        ]
        
        if recent_metrics:
            avg_memory = sum(m.memory_usage_mb for m in recent_metrics) / len(recent_metrics)
            avg_cpu = sum(m.cpu_usage_percent for m in recent_metrics) / len(recent_metrics)
            max_sessions = max(m.active_sessions for m in recent_metrics)
        else:
            avg_memory = avg_cpu = max_sessions = 0
        
        return {
            "current": self.get_resource_status(),
            "recent_averages": {
                "memory_usage_mb": avg_memory,
                "cpu_usage_percent": avg_cpu,
                "max_sessions": max_sessions,
                "sample_count": len(recent_metrics)
            },
            "history_length": len(self.metrics_history),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on resource manager."""
        health_status = {
            "status": "healthy",
            "running": self.running,
            "active_sessions": len(self.active_sessions),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Check if under pressure
        if any([self.memory_pressure, self.cpu_pressure, self.session_pressure]):
            health_status["status"] = "under_pressure"
            health_status["pressures"] = {
                "memory": self.memory_pressure,
                "cpu": self.cpu_pressure,
                "sessions": self.session_pressure
            }
        
        # Check circuit breakers
        open_breakers = [
            name for name, cb in self.circuit_breakers.items()
            if cb.state == "open"
        ]
        
        if open_breakers:
            health_status["status"] = "degraded"
            health_status["open_circuit_breakers"] = open_breakers
        
        return health_status