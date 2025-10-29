"""
AI Orchestration Monitoring and Health Checks

This module provides comprehensive monitoring and health check functionality
for the AI orchestration system, integrating with existing Prometheus metrics
and system monitoring infrastructure.
"""

import time
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings

logger = get_logger(prefix="[AI_Monitoring]")

# Import metrics integration
try:
    from .metrics import record_ai_health_check
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.warning("AI metrics integration not available")


@dataclass
class ComponentHealth:
    """Health status for a system component."""
    name: str
    status: str  # "healthy", "degraded", "unhealthy", "unknown"
    message: str
    response_time_ms: Optional[float] = None
    last_check: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class AIMetrics:
    """AI system performance metrics."""
    active_sessions: int = 0
    total_messages: int = 0
    average_response_time_ms: float = 0.0
    model_requests_per_minute: float = 0.0
    error_rate: float = 0.0
    memory_usage_mb: float = 0.0
    cache_hit_rate: float = 0.0
    uptime_seconds: float = 0.0


class AIHealthMonitor:
    """
    Comprehensive health monitoring for AI orchestration system.
    
    Provides health checks for all AI components and integrates with
    existing system monitoring infrastructure.
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.last_health_check = None
        self.health_history: List[Dict[str, Any]] = []
        self.max_history_size = 100
        
        # Component health cache
        self._component_health_cache: Dict[str, ComponentHealth] = {}
        self._cache_ttl = 30  # seconds
        self._last_cache_update = 0
        
        # Metrics tracking
        self.metrics = AIMetrics()
        self._metrics_history: List[AIMetrics] = []
        
        logger.info("AI Health Monitor initialized")
    
    async def comprehensive_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check of all AI orchestration components.
        
        Returns:
            Comprehensive health status including all components
        """
        check_start_time = time.time()
        
        try:
            # Get orchestrator instance
            from second_brain_database.integrations.ai_orchestration.orchestrator import get_global_orchestrator
            orchestrator = get_global_orchestrator()
            
            health_status = {
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "check_duration_ms": 0,
                "components": {},
                "metrics": {},
                "system_info": {
                    "uptime_seconds": time.time() - self.start_time,
                    "ai_enabled": settings.ai_should_be_enabled,
                    "enabled_agents": getattr(settings, 'ai_enabled_agents', [])
                }
            }
            
            # Check orchestrator health
            if orchestrator:
                orchestrator_health = await self._check_orchestrator_health(orchestrator)
                health_status["components"]["orchestrator"] = asdict(orchestrator_health)
                
                # Check individual components
                component_checks = await asyncio.gather(
                    self._check_model_engine_health(orchestrator),
                    self._check_memory_layer_health(orchestrator),
                    self._check_resource_manager_health(orchestrator),
                    self._check_event_bus_health(),
                    self._check_agents_health(orchestrator),
                    return_exceptions=True
                )
                
                # Process component check results
                component_names = ["model_engine", "memory_layer", "resource_manager", "event_bus", "agents"]
                for i, check_result in enumerate(component_checks):
                    if isinstance(check_result, Exception):
                        health_status["components"][component_names[i]] = {
                            "status": "unhealthy",
                            "message": f"Health check failed: {str(check_result)}",
                            "error": str(check_result)
                        }
                    else:
                        health_status["components"][component_names[i]] = asdict(check_result)
                
                # Collect metrics
                health_status["metrics"] = await self._collect_ai_metrics(orchestrator)
                
            else:
                health_status["status"] = "unhealthy"
                health_status["components"]["orchestrator"] = {
                    "status": "unhealthy",
                    "message": "AI orchestrator not available"
                }
            
            # Determine overall health status
            overall_status = self._determine_overall_status(health_status["components"])
            health_status["status"] = overall_status
            
            # Record check duration
            check_duration = (time.time() - check_start_time) * 1000
            health_status["check_duration_ms"] = round(check_duration, 2)
            
            # Update health history
            self._update_health_history(health_status)
            
            # Record metrics if available
            if METRICS_AVAILABLE:
                try:
                    component_healths = {}
                    for comp_name, comp_data in health_status.get("components", {}).items():
                        if isinstance(comp_data, dict):
                            component_healths[comp_name] = comp_data.get("status", "unknown")
                    
                    record_ai_health_check(check_duration / 1000, component_healths)
                except Exception as e:
                    logger.warning(f"Failed to record health check metrics: {e}")
            
            logger.info(f"AI health check completed in {check_duration:.2f}ms - Status: {overall_status}")
            
            return health_status
            
        except Exception as e:
            logger.error(f"AI health check failed: {e}")
            check_duration = (time.time() - check_start_time) * 1000
            
            return {
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "check_duration_ms": round(check_duration, 2),
                "error": str(e),
                "components": {},
                "metrics": {}
            }
    
    async def _check_orchestrator_health(self, orchestrator) -> ComponentHealth:
        """Check AI orchestrator health."""
        start_time = time.time()
        
        try:
            # Check if orchestrator is properly initialized
            if not hasattr(orchestrator, 'agents'):
                return ComponentHealth(
                    name="orchestrator",
                    status="unhealthy",
                    message="Orchestrator not properly initialized - missing agents",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat()
                )
            
            if not orchestrator.agents:
                return ComponentHealth(
                    name="orchestrator",
                    status="degraded",
                    message="Orchestrator initialized but no agents available",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat()
                )
            
            # Check active sessions
            active_sessions = len(getattr(orchestrator, 'active_sessions', {}))
            
            # Check if background tasks are running
            background_tasks_healthy = True
            if hasattr(orchestrator, 'background_tasks'):
                for task_name, task in orchestrator.background_tasks.items():
                    if task.done() or task.cancelled():
                        background_tasks_healthy = False
                        break
            
            status = "healthy"
            message = f"Orchestrator operational with {active_sessions} active sessions"
            
            if not background_tasks_healthy:
                status = "degraded"
                message += " (some background tasks not running)"
            
            return ComponentHealth(
                name="orchestrator",
                status=status,
                message=message,
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
                details={
                    "active_sessions": active_sessions,
                    "agents_count": len(orchestrator.agents),
                    "background_tasks_healthy": background_tasks_healthy
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="orchestrator",
                status="unhealthy",
                message=f"Orchestrator health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat()
            )
    
    async def _check_model_engine_health(self, orchestrator) -> ComponentHealth:
        """Check model engine health."""
        start_time = time.time()
        
        try:
            if not hasattr(orchestrator, 'model_engine') or not orchestrator.model_engine:
                return ComponentHealth(
                    name="model_engine",
                    status="unhealthy",
                    message="Model engine not available",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat()
                )
            
            # Check model engine health
            model_health = await orchestrator.model_engine.health_check()
            
            return ComponentHealth(
                name="model_engine",
                status=model_health.get("status", "unknown"),
                message=model_health.get("message", "Model engine status unknown"),
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
                details=model_health.get("details", {})
            )
            
        except Exception as e:
            return ComponentHealth(
                name="model_engine",
                status="unhealthy",
                message=f"Model engine health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat()
            )
    
    async def _check_memory_layer_health(self, orchestrator) -> ComponentHealth:
        """Check memory layer health."""
        start_time = time.time()
        
        try:
            if not hasattr(orchestrator, 'memory_layer') or not orchestrator.memory_layer:
                return ComponentHealth(
                    name="memory_layer",
                    status="unhealthy",
                    message="Memory layer not available",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat()
                )
            
            # Check memory layer health
            memory_health = await orchestrator.memory_layer.health_check()
            
            return ComponentHealth(
                name="memory_layer",
                status=memory_health.get("status", "unknown"),
                message=memory_health.get("message", "Memory layer status unknown"),
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
                details=memory_health.get("details", {})
            )
            
        except Exception as e:
            return ComponentHealth(
                name="memory_layer",
                status="unhealthy",
                message=f"Memory layer health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat()
            )
    
    async def _check_resource_manager_health(self, orchestrator) -> ComponentHealth:
        """Check resource manager health."""
        start_time = time.time()
        
        try:
            if not hasattr(orchestrator, 'resource_manager') or not orchestrator.resource_manager:
                return ComponentHealth(
                    name="resource_manager",
                    status="unhealthy",
                    message="Resource manager not available",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat()
                )
            
            # Check resource manager health
            resource_health = await orchestrator.resource_manager.health_check()
            
            return ComponentHealth(
                name="resource_manager",
                status=resource_health.get("status", "unknown"),
                message=resource_health.get("message", "Resource manager status unknown"),
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
                details=resource_health.get("details", {})
            )
            
        except Exception as e:
            return ComponentHealth(
                name="resource_manager",
                status="unhealthy",
                message=f"Resource manager health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat()
            )
    
    async def _check_event_bus_health(self) -> ComponentHealth:
        """Check event bus health."""
        start_time = time.time()
        
        try:
            from second_brain_database.integrations.ai_orchestration.event_bus import get_ai_event_bus
            event_bus = get_ai_event_bus()
            
            if not event_bus:
                return ComponentHealth(
                    name="event_bus",
                    status="unhealthy",
                    message="Event bus not available",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat()
                )
            
            # Get event bus stats
            stats = event_bus.get_session_stats()
            
            return ComponentHealth(
                name="event_bus",
                status="healthy",
                message=f"Event bus operational with {stats.get('active_sessions', 0)} active sessions",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
                details=stats
            )
            
        except Exception as e:
            return ComponentHealth(
                name="event_bus",
                status="unhealthy",
                message=f"Event bus health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat()
            )
    
    async def _check_agents_health(self, orchestrator) -> ComponentHealth:
        """Check individual agents health."""
        start_time = time.time()
        
        try:
            if not hasattr(orchestrator, 'agents') or not orchestrator.agents:
                return ComponentHealth(
                    name="agents",
                    status="unhealthy",
                    message="No agents available",
                    response_time_ms=(time.time() - start_time) * 1000,
                    last_check=datetime.now(timezone.utc).isoformat()
                )
            
            agent_statuses = {}
            healthy_agents = 0
            
            for agent_type, agent in orchestrator.agents.items():
                try:
                    # Basic agent health check
                    if hasattr(agent, 'health_check'):
                        agent_health = await agent.health_check()
                        agent_statuses[agent_type] = agent_health
                        if agent_health.get("status") == "healthy":
                            healthy_agents += 1
                    else:
                        agent_statuses[agent_type] = {"status": "healthy", "message": "Agent operational"}
                        healthy_agents += 1
                except Exception as e:
                    agent_statuses[agent_type] = {"status": "unhealthy", "error": str(e)}
            
            total_agents = len(orchestrator.agents)
            status = "healthy" if healthy_agents == total_agents else "degraded" if healthy_agents > 0 else "unhealthy"
            
            return ComponentHealth(
                name="agents",
                status=status,
                message=f"{healthy_agents}/{total_agents} agents healthy",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
                details=agent_statuses
            )
            
        except Exception as e:
            return ComponentHealth(
                name="agents",
                status="unhealthy",
                message=f"Agents health check failed: {str(e)}",
                response_time_ms=(time.time() - start_time) * 1000,
                last_check=datetime.now(timezone.utc).isoformat()
            )
    
    async def _collect_ai_metrics(self, orchestrator) -> Dict[str, Any]:
        """Collect AI system performance metrics."""
        try:
            metrics = {
                "uptime_seconds": time.time() - self.start_time,
                "active_sessions": len(getattr(orchestrator, 'active_sessions', {})),
                "agents_count": len(getattr(orchestrator, 'agents', {})),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Add model engine metrics if available
            if hasattr(orchestrator, 'model_engine') and orchestrator.model_engine:
                try:
                    if hasattr(orchestrator.model_engine, 'get_metrics'):
                        model_metrics = await orchestrator.model_engine.get_metrics()
                        metrics["model_engine"] = model_metrics
                    else:
                        metrics["model_engine"] = {"status": "available", "metrics_not_implemented": True}
                except Exception as e:
                    logger.warning(f"Failed to collect model engine metrics: {e}")
            
            # Add memory layer metrics if available
            if hasattr(orchestrator, 'memory_layer') and orchestrator.memory_layer:
                try:
                    if hasattr(orchestrator.memory_layer, 'get_metrics'):
                        memory_metrics = await orchestrator.memory_layer.get_metrics()
                        metrics["memory_layer"] = memory_metrics
                    else:
                        metrics["memory_layer"] = {"status": "available", "metrics_not_implemented": True}
                except Exception as e:
                    logger.warning(f"Failed to collect memory layer metrics: {e}")
            
            # Add resource manager metrics if available
            if hasattr(orchestrator, 'resource_manager') and orchestrator.resource_manager:
                try:
                    if hasattr(orchestrator.resource_manager, 'get_metrics'):
                        resource_metrics = await orchestrator.resource_manager.get_metrics()
                        metrics["resource_manager"] = resource_metrics
                    else:
                        metrics["resource_manager"] = {"status": "available", "metrics_not_implemented": True}
                except Exception as e:
                    logger.warning(f"Failed to collect resource manager metrics: {e}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect AI metrics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def _determine_overall_status(self, components: Dict[str, Any]) -> str:
        """Determine overall system health status from component statuses."""
        if not components:
            return "unknown"
        
        statuses = []
        for component_data in components.values():
            if isinstance(component_data, dict):
                statuses.append(component_data.get("status", "unknown"))
        
        if not statuses:
            return "unknown"
        
        # If any component is unhealthy, system is unhealthy
        if "unhealthy" in statuses:
            return "unhealthy"
        
        # If any component is degraded, system is degraded
        if "degraded" in statuses:
            return "degraded"
        
        # If all components are healthy, system is healthy
        if all(status == "healthy" for status in statuses):
            return "healthy"
        
        # Default to unknown if we can't determine
        return "unknown"
    
    def _update_health_history(self, health_status: Dict[str, Any]):
        """Update health check history."""
        self.health_history.append({
            "timestamp": health_status["timestamp"],
            "status": health_status["status"],
            "check_duration_ms": health_status["check_duration_ms"],
            "components_count": len(health_status.get("components", {}))
        })
        
        # Keep only recent history
        if len(self.health_history) > self.max_history_size:
            self.health_history = self.health_history[-self.max_history_size:]
    
    def get_health_history(self) -> List[Dict[str, Any]]:
        """Get health check history."""
        return self.health_history.copy()
    
    async def get_ai_performance_metrics(self) -> Dict[str, Any]:
        """Get AI system performance metrics for monitoring integration."""
        try:
            from second_brain_database.integrations.ai_orchestration.orchestrator import get_global_orchestrator
            orchestrator = get_global_orchestrator()
            
            if not orchestrator:
                return {
                    "error": "AI orchestrator not available",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
            # Collect comprehensive metrics
            metrics = await self._collect_ai_metrics(orchestrator)
            
            # Add system-level metrics
            metrics.update({
                "system": {
                    "uptime_seconds": time.time() - self.start_time,
                    "health_checks_performed": len(self.health_history),
                    "last_health_check": self.health_history[-1]["timestamp"] if self.health_history else None
                }
            })
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get AI performance metrics: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }


# Global health monitor instance
_ai_health_monitor: Optional[AIHealthMonitor] = None


def get_ai_health_monitor() -> AIHealthMonitor:
    """Get the global AI health monitor instance."""
    global _ai_health_monitor
    if _ai_health_monitor is None:
        _ai_health_monitor = AIHealthMonitor()
    return _ai_health_monitor


async def perform_ai_health_check() -> Dict[str, Any]:
    """Perform comprehensive AI health check."""
    monitor = get_ai_health_monitor()
    return await monitor.comprehensive_health_check()


async def get_ai_metrics() -> Dict[str, Any]:
    """Get AI performance metrics."""
    monitor = get_ai_health_monitor()
    return await monitor.get_ai_performance_metrics()