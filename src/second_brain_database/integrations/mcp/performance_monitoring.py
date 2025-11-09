"""
MCP Performance Monitoring and Metrics Collection

Tracks MCP tool execution times, success rates, concurrent usage, and resource
consumption. Integrates with existing monitoring infrastructure for comprehensive
observability and performance optimization.
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import json
import statistics
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set

from ...config import settings
from ...managers.logging_manager import get_logger
from .context import MCPUserContext, get_mcp_request_context, get_mcp_user_context

logger = get_logger(prefix="[MCP_Performance]")


class MetricType(Enum):
    """Types of performance metrics."""

    EXECUTION_TIME = "execution_time"
    SUCCESS_RATE = "success_rate"
    CONCURRENT_USAGE = "concurrent_usage"
    RESOURCE_CONSUMPTION = "resource_consumption"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    LATENCY = "latency"


@dataclass
class PerformanceMetric:
    """Individual performance metric data point."""

    timestamp: datetime
    metric_type: MetricType
    tool_name: str
    user_id: Optional[str]
    value: float
    unit: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metric_type": self.metric_type.value,
            "tool_name": self.tool_name,
            "user_id": self.user_id,
            "value": self.value,
            "unit": self.unit,
            "metadata": self.metadata,
        }


@dataclass
class ToolExecutionStats:
    """Statistics for a specific tool's execution."""

    tool_name: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time: float = 0.0
    min_execution_time: float = float("inf")
    max_execution_time: float = 0.0
    execution_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    error_types: Dict[str, int] = field(default_factory=dict)
    last_execution: Optional[datetime] = None
    concurrent_executions: int = 0
    peak_concurrent_executions: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_executions == 0:
            return 0.0
        return (self.successful_executions / self.total_executions) * 100

    @property
    def error_rate(self) -> float:
        """Calculate error rate percentage."""
        if self.total_executions == 0:
            return 0.0
        return (self.failed_executions / self.total_executions) * 100

    @property
    def average_execution_time(self) -> float:
        """Calculate average execution time."""
        if self.successful_executions == 0:
            return 0.0
        return self.total_execution_time / self.successful_executions

    @property
    def median_execution_time(self) -> float:
        """Calculate median execution time."""
        if not self.execution_times:
            return 0.0
        return statistics.median(self.execution_times)

    @property
    def p95_execution_time(self) -> float:
        """Calculate 95th percentile execution time."""
        if not self.execution_times:
            return 0.0
        sorted_times = sorted(self.execution_times)
        index = int(0.95 * len(sorted_times))
        return sorted_times[min(index, len(sorted_times) - 1)]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "average_execution_time": self.average_execution_time,
            "median_execution_time": self.median_execution_time,
            "p95_execution_time": self.p95_execution_time,
            "min_execution_time": self.min_execution_time if self.min_execution_time != float("inf") else 0.0,
            "max_execution_time": self.max_execution_time,
            "concurrent_executions": self.concurrent_executions,
            "peak_concurrent_executions": self.peak_concurrent_executions,
            "error_types": self.error_types,
            "last_execution": self.last_execution.isoformat() if self.last_execution else None,
        }


@dataclass
class SystemResourceMetrics:
    """System resource consumption metrics."""

    timestamp: datetime
    cpu_usage_percent: float = 0.0
    memory_usage_mb: float = 0.0
    active_connections: int = 0
    database_connections: int = 0
    redis_connections: int = 0
    concurrent_tools: int = 0
    queue_size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_usage_percent": self.cpu_usage_percent,
            "memory_usage_mb": self.memory_usage_mb,
            "active_connections": self.active_connections,
            "database_connections": self.database_connections,
            "redis_connections": self.redis_connections,
            "concurrent_tools": self.concurrent_tools,
            "queue_size": self.queue_size,
        }


class MCPPerformanceCollector:
    """
    Collects and aggregates performance metrics for MCP operations.

    Tracks execution times, success rates, resource usage, and provides
    statistical analysis for performance optimization and monitoring.
    """

    def __init__(self, max_metrics_history: int = 10000):
        self.max_metrics_history = max_metrics_history
        self._tool_stats: Dict[str, ToolExecutionStats] = {}
        self._metrics_history: deque = deque(maxlen=max_metrics_history)
        self._resource_metrics: deque = deque(maxlen=1000)
        self._active_executions: Set[str] = set()
        self._lock = threading.RLock()

        # Performance thresholds
        self.slow_execution_threshold = 5.0  # seconds
        self.high_error_rate_threshold = 10.0  # percent
        self.high_concurrency_threshold = 50  # concurrent executions

        logger.info("MCP Performance Collector initialized")

    def start_execution(self, tool_name: str, execution_id: str) -> None:
        """
        Mark the start of a tool execution.

        Args:
            tool_name: Name of the tool being executed
            execution_id: Unique execution identifier
        """
        with self._lock:
            # Initialize tool stats if not exists
            if tool_name not in self._tool_stats:
                self._tool_stats[tool_name] = ToolExecutionStats(tool_name=tool_name)

            # Track active execution
            self._active_executions.add(execution_id)

            # Update concurrent execution counts
            stats = self._tool_stats[tool_name]
            stats.concurrent_executions += 1
            stats.peak_concurrent_executions = max(stats.peak_concurrent_executions, stats.concurrent_executions)

            logger.debug("Started execution for tool %s (ID: %s)", tool_name, execution_id)

    def end_execution(
        self,
        tool_name: str,
        execution_id: str,
        execution_time: float,
        success: bool,
        error_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark the end of a tool execution and record metrics.

        Args:
            tool_name: Name of the tool that was executed
            execution_id: Unique execution identifier
            execution_time: Execution time in seconds
            success: Whether the execution was successful
            error_type: Type of error if execution failed
            metadata: Additional metadata about the execution
        """
        with self._lock:
            # Remove from active executions
            self._active_executions.discard(execution_id)

            # Get or create tool stats
            if tool_name not in self._tool_stats:
                self._tool_stats[tool_name] = ToolExecutionStats(tool_name=tool_name)

            stats = self._tool_stats[tool_name]

            # Update execution counts
            stats.total_executions += 1
            stats.concurrent_executions = max(0, stats.concurrent_executions - 1)
            stats.last_execution = datetime.now(timezone.utc)

            if success:
                stats.successful_executions += 1
                stats.total_execution_time += execution_time
                stats.execution_times.append(execution_time)

                # Update min/max execution times
                stats.min_execution_time = min(stats.min_execution_time, execution_time)
                stats.max_execution_time = max(stats.max_execution_time, execution_time)

                # Record execution time metric
                self._record_metric(MetricType.EXECUTION_TIME, tool_name, execution_time, "seconds", metadata or {})

                # Check for slow execution
                if execution_time > self.slow_execution_threshold:
                    logger.warning(
                        "Slow execution detected for tool %s: %.2fs (threshold: %.2fs)",
                        tool_name,
                        execution_time,
                        self.slow_execution_threshold,
                    )
            else:
                stats.failed_executions += 1
                if error_type:
                    stats.error_types[error_type] = stats.error_types.get(error_type, 0) + 1

                logger.warning(
                    "Failed execution for tool %s (ID: %s): %s", tool_name, execution_id, error_type or "Unknown error"
                )

            # Record success rate metric
            self._record_metric(
                MetricType.SUCCESS_RATE,
                tool_name,
                stats.success_rate,
                "percent",
                {"total_executions": stats.total_executions},
            )

            # Check for high error rate
            if stats.error_rate > self.high_error_rate_threshold and stats.total_executions >= 10:
                logger.error(
                    "High error rate detected for tool %s: %.1f%% (threshold: %.1f%%)",
                    tool_name,
                    stats.error_rate,
                    self.high_error_rate_threshold,
                )

            logger.debug(
                "Completed execution for tool %s (ID: %s) - Success: %s, Time: %.3fs",
                tool_name,
                execution_id,
                success,
                execution_time,
            )

    def _record_metric(
        self, metric_type: MetricType, tool_name: str, value: float, unit: str, metadata: Dict[str, Any]
    ) -> None:
        """Record a performance metric."""
        # Get user context if available
        user_id = None
        try:
            user_context = get_mcp_user_context()
            user_id = user_context.user_id
        except Exception:  # TODO: Use specific exception type
            pass  # No user context available

        metric = PerformanceMetric(
            timestamp=datetime.now(timezone.utc),
            metric_type=metric_type,
            tool_name=tool_name,
            user_id=user_id,
            value=value,
            unit=unit,
            metadata=metadata,
        )

        self._metrics_history.append(metric)

    def record_resource_metrics(self, resource_metrics: SystemResourceMetrics) -> None:
        """
        Record system resource metrics.

        Args:
            resource_metrics: System resource consumption data
        """
        with self._lock:
            self._resource_metrics.append(resource_metrics)

            # Check for high concurrency
            if resource_metrics.concurrent_tools > self.high_concurrency_threshold:
                logger.warning(
                    "High concurrency detected: %d concurrent tools (threshold: %d)",
                    resource_metrics.concurrent_tools,
                    self.high_concurrency_threshold,
                )

    def get_tool_stats(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance statistics for tools.

        Args:
            tool_name: Specific tool name, or None for all tools

        Returns:
            Dictionary containing tool performance statistics
        """
        with self._lock:
            if tool_name:
                stats = self._tool_stats.get(tool_name)
                return stats.to_dict() if stats else {}
            else:
                return {name: stats.to_dict() for name, stats in self._tool_stats.items()}

    def get_system_metrics(self, minutes: int = 60) -> Dict[str, Any]:
        """
        Get system resource metrics for the specified time period.

        Args:
            minutes: Number of minutes of history to include

        Returns:
            Dictionary containing system metrics
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes)

        with self._lock:
            recent_metrics = [m for m in self._resource_metrics if m.timestamp >= cutoff_time]

            if not recent_metrics:
                return {"period_minutes": minutes, "data_points": 0, "metrics": {}}

            # Calculate aggregated metrics
            cpu_values = [m.cpu_usage_percent for m in recent_metrics]
            memory_values = [m.memory_usage_mb for m in recent_metrics]
            concurrent_tools = [m.concurrent_tools for m in recent_metrics]

            return {
                "period_minutes": minutes,
                "data_points": len(recent_metrics),
                "metrics": {
                    "cpu_usage": {
                        "average": statistics.mean(cpu_values),
                        "min": min(cpu_values),
                        "max": max(cpu_values),
                        "current": cpu_values[-1] if cpu_values else 0,
                    },
                    "memory_usage": {
                        "average": statistics.mean(memory_values),
                        "min": min(memory_values),
                        "max": max(memory_values),
                        "current": memory_values[-1] if memory_values else 0,
                    },
                    "concurrent_tools": {
                        "average": statistics.mean(concurrent_tools),
                        "min": min(concurrent_tools),
                        "max": max(concurrent_tools),
                        "current": concurrent_tools[-1] if concurrent_tools else 0,
                    },
                },
                "latest_timestamp": recent_metrics[-1].timestamp.isoformat(),
            }

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive performance summary.

        Returns:
            Dictionary containing overall performance summary
        """
        with self._lock:
            total_executions = sum(stats.total_executions for stats in self._tool_stats.values())
            total_successful = sum(stats.successful_executions for stats in self._tool_stats.values())
            total_failed = sum(stats.failed_executions for stats in self._tool_stats.values())

            # Calculate overall metrics
            overall_success_rate = (total_successful / total_executions * 100) if total_executions > 0 else 0
            overall_error_rate = (total_failed / total_executions * 100) if total_executions > 0 else 0

            # Find slowest and fastest tools
            tool_performance = []
            for stats in self._tool_stats.values():
                if stats.successful_executions > 0:
                    tool_performance.append(
                        {
                            "tool_name": stats.tool_name,
                            "average_time": stats.average_execution_time,
                            "executions": stats.total_executions,
                            "success_rate": stats.success_rate,
                        }
                    )

            tool_performance.sort(key=lambda x: x["average_time"], reverse=True)

            return {
                "summary": {
                    "total_executions": total_executions,
                    "successful_executions": total_successful,
                    "failed_executions": total_failed,
                    "overall_success_rate": overall_success_rate,
                    "overall_error_rate": overall_error_rate,
                    "active_executions": len(self._active_executions),
                    "total_tools": len(self._tool_stats),
                },
                "slowest_tools": tool_performance[:5],
                "fastest_tools": tool_performance[-5:] if len(tool_performance) > 5 else [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    def export_metrics(self, format_type: str = "json") -> str:
        """
        Export performance metrics in specified format.

        Args:
            format_type: Export format ("json", "csv")

        Returns:
            Formatted metrics data
        """
        with self._lock:
            if format_type.lower() == "json":
                export_data = {
                    "tool_stats": self.get_tool_stats(),
                    "system_metrics": self.get_system_metrics(),
                    "performance_summary": self.get_performance_summary(),
                    "export_timestamp": datetime.now(timezone.utc).isoformat(),
                }
                return json.dumps(export_data, indent=2)
            else:
                raise ValueError(f"Unsupported export format: {format_type}")


class MCPPerformanceMonitor:
    """
    Main performance monitoring coordinator for MCP operations.

    Integrates with existing monitoring infrastructure and provides
    real-time performance tracking and alerting capabilities.
    """

    def __init__(self):
        self.collector = MCPPerformanceCollector()
        self._monitoring_enabled = True
        self._resource_monitoring_task: Optional[asyncio.Task] = None
        self._monitoring_interval = 30  # seconds

        logger.info("MCP Performance Monitor initialized")

    async def start_monitoring(self) -> None:
        """Start background performance monitoring tasks."""
        if self._resource_monitoring_task and not self._resource_monitoring_task.done():
            logger.warning("Performance monitoring already running")
            return

        self._monitoring_enabled = True
        self._resource_monitoring_task = asyncio.create_task(self._resource_monitoring_loop())

        logger.info("Started MCP performance monitoring")

    async def stop_monitoring(self) -> None:
        """Stop background performance monitoring tasks."""
        self._monitoring_enabled = False

        if self._resource_monitoring_task and not self._resource_monitoring_task.done():
            self._resource_monitoring_task.cancel()
            try:
                await self._resource_monitoring_task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped MCP performance monitoring")

    async def _resource_monitoring_loop(self) -> None:
        """Background loop for collecting system resource metrics."""
        while self._monitoring_enabled:
            try:
                # Collect system resource metrics
                resource_metrics = await self._collect_system_resources()
                self.collector.record_resource_metrics(resource_metrics)

                # Log performance summary periodically
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    summary = self.collector.get_performance_summary()
                    logger.info(
                        "MCP Performance Summary - Executions: %d, Success Rate: %.1f%%, Active: %d",
                        summary["summary"]["total_executions"],
                        summary["summary"]["overall_success_rate"],
                        summary["summary"]["active_executions"],
                    )

                await asyncio.sleep(self._monitoring_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in resource monitoring loop: %s", e)
                await asyncio.sleep(self._monitoring_interval)

    async def _collect_system_resources(self) -> SystemResourceMetrics:
        """Collect current system resource metrics."""
        try:
            import psutil

            # Get CPU and memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_mb = memory.used / (1024 * 1024)

            # Get network connections (approximate)
            connections = len(psutil.net_connections())

        except ImportError:
            # Fallback if psutil is not available
            cpu_percent = 0.0
            memory_mb = 0.0
            connections = 0

        # Get MCP-specific metrics
        concurrent_tools = len(self.collector._active_executions)

        # Get database connection count (if available)
        db_connections = 0
        redis_connections = 0
        try:
            from ...managers.redis_manager import redis_manager

            # This would need to be implemented in redis_manager
            # redis_connections = await redis_manager.get_connection_count()
        except Exception:  # TODO: Use specific exception type
            pass

        return SystemResourceMetrics(
            timestamp=datetime.now(timezone.utc),
            cpu_usage_percent=cpu_percent,
            memory_usage_mb=memory_mb,
            active_connections=connections,
            database_connections=db_connections,
            redis_connections=redis_connections,
            concurrent_tools=concurrent_tools,
            queue_size=0,  # Would need to be implemented based on actual queue
        )

    def track_execution(self, tool_name: str, execution_id: Optional[str] = None) -> "ExecutionTracker":
        """
        Create an execution tracker for a tool.

        Args:
            tool_name: Name of the tool being executed
            execution_id: Optional execution identifier

        Returns:
            ExecutionTracker context manager
        """
        if not execution_id:
            execution_id = f"{tool_name}_{int(time.time() * 1000000)}"

        return ExecutionTracker(self.collector, tool_name, execution_id)

    async def get_health_status(self) -> Dict[str, Any]:
        """Get performance monitoring health status."""
        summary = self.collector.get_performance_summary()
        system_metrics = self.collector.get_system_metrics(minutes=5)

        # Determine health status
        healthy = True
        issues = []

        # Check error rates
        if summary["summary"]["overall_error_rate"] > 10:
            healthy = False
            issues.append(f"High error rate: {summary['summary']['overall_error_rate']:.1f}%")

        # Check system resources
        if system_metrics.get("metrics", {}).get("cpu_usage", {}).get("current", 0) > 80:
            healthy = False
            issues.append("High CPU usage")

        if system_metrics.get("metrics", {}).get("memory_usage", {}).get("current", 0) > 1000:  # 1GB
            issues.append("High memory usage")

        return {
            "healthy": healthy,
            "issues": issues,
            "monitoring_enabled": self._monitoring_enabled,
            "performance_summary": summary,
            "system_metrics": system_metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class ExecutionTracker:
    """
    Context manager for tracking individual tool executions.

    Automatically records start/end times and handles success/failure tracking.
    """

    def __init__(self, collector: MCPPerformanceCollector, tool_name: str, execution_id: str):
        self.collector = collector
        self.tool_name = tool_name
        self.execution_id = execution_id
        self.start_time: Optional[float] = None
        self.metadata: Dict[str, Any] = {}

    def __enter__(self) -> "ExecutionTracker":
        self.start_time = time.time()
        self.collector.start_execution(self.tool_name, self.execution_id)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.start_time is None:
            return

        execution_time = time.time() - self.start_time
        success = exc_type is None
        error_type = exc_type.__name__ if exc_type else None

        self.collector.end_execution(
            self.tool_name, self.execution_id, execution_time, success, error_type, self.metadata
        )

    async def __aenter__(self) -> "ExecutionTracker":
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.__exit__(exc_type, exc_val, exc_tb)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata to the execution tracking."""
        self.metadata[key] = value


# Global performance monitor instance
mcp_performance_monitor = MCPPerformanceMonitor()


# Decorator for automatic performance tracking
def track_performance(tool_name: Optional[str] = None):
    """
    Decorator to automatically track performance of MCP tool functions.

    Args:
        tool_name: Optional tool name override
    """

    def decorator(func: Callable) -> Callable:
        actual_tool_name = tool_name or func.__name__

        async def async_wrapper(*args, **kwargs):
            with mcp_performance_monitor.track_execution(actual_tool_name) as tracker:
                # Add user context to metadata if available
                try:
                    user_context = get_mcp_user_context()
                    tracker.add_metadata("user_id", user_context.user_id)
                    tracker.add_metadata("user_role", user_context.role)
                except Exception:  # TODO: Use specific exception type
                    pass

                # Add request context if available
                try:
                    request_context = get_mcp_request_context()
                    tracker.add_metadata("request_id", request_context.request_id)
                    tracker.add_metadata("operation_type", request_context.operation_type)
                except Exception:  # TODO: Use specific exception type
                    pass

                return await func(*args, **kwargs)

        def sync_wrapper(*args, **kwargs):
            with mcp_performance_monitor.track_execution(actual_tool_name) as tracker:
                # Add context metadata
                try:
                    user_context = get_mcp_user_context()
                    tracker.add_metadata("user_id", user_context.user_id)
                    tracker.add_metadata("user_role", user_context.role)
                except Exception:  # TODO: Use specific exception type
                    pass

                return func(*args, **kwargs)

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
