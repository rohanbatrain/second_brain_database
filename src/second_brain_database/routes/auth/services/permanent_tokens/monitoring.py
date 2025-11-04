"""
Permanent token cache performance monitoring service.

This module provides comprehensive monitoring and metrics collection for
permanent token cache performance, including hit/miss ratios, response times,
and health checks.
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict, List, Optional, Tuple

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth.services.permanent_tokens.cache_manager import get_cache_statistics
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Permanent Token Cache Monitor]")
security_logger = SecurityLogger(prefix="[PERM-TOKEN-MONITOR-SECURITY]")
db_logger = DatabaseLogger(prefix="[PERM-TOKEN-MONITOR-DB]")

# Monitoring configuration
METRICS_WINDOW_SIZE = 1000  # Keep last 1000 operations
METRICS_RETENTION_HOURS = 24  # Keep metrics for 24 hours
HEALTH_CHECK_INTERVAL = 300  # Health check every 5 minutes
PERFORMANCE_ALERT_THRESHOLD = 0.8  # Alert if hit rate drops below 80%


@dataclass
class CacheOperation:
    """Represents a single cache operation for metrics tracking."""

    operation_type: str  # 'hit', 'miss', 'set', 'delete'
    timestamp: float
    response_time_ms: float
    token_hash_prefix: str  # First 8 chars for debugging
    success: bool


@dataclass
class CacheMetrics:
    """Aggregated cache performance metrics."""

    total_operations: int
    cache_hits: int
    cache_misses: int
    cache_sets: int
    cache_deletes: int
    hit_rate: float
    miss_rate: float
    avg_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    operations_per_second: float
    error_count: int
    error_rate: float
    timestamp: str


class CachePerformanceMonitor:
    """
    Monitors cache performance and collects metrics for permanent tokens.
    """

    def __init__(self):
        self.operations: deque = deque(maxlen=METRICS_WINDOW_SIZE)
        self.hourly_metrics: Dict[str, CacheMetrics] = {}
        self.last_health_check: Optional[datetime] = None
        self.health_status: Dict[str, Any] = {}

    def record_operation(
        self, operation_type: str, response_time_ms: float, token_hash: str = "", success: bool = True
    ):
        """
        Record a cache operation for metrics tracking.

        Args:
            operation_type (str): Type of operation ('hit', 'miss', 'set', 'delete')
            response_time_ms (float): Response time in milliseconds
            token_hash (str): Token hash for debugging (will be truncated)
            success (bool): Whether the operation was successful
        """
        operation = CacheOperation(
            operation_type=operation_type,
            timestamp=time.time(),
            response_time_ms=response_time_ms,
            token_hash_prefix=token_hash[:8] if token_hash else "",
            success=success,
        )

        self.operations.append(operation)

        logger.debug(
            "Recorded cache operation: %s (%.2fms) for token %s - success: %s",
            operation_type,
            response_time_ms,
            operation.token_hash_prefix or "unknown",
            success,
        )

        # Log performance issues
        if operation_type in ["hit", "miss"] and response_time_ms > 100:
            logger.warning(
                "Slow cache operation: %s took %.2fms for token %s",
                operation_type,
                response_time_ms,
                operation.token_hash_prefix,
            )

            # Log security event for slow cache operations
            log_security_event(
                event_type="cache_performance_degraded",
                success=True,
                details={
                    "operation_type": operation_type,
                    "response_time_ms": response_time_ms,
                    "token_hash_prefix": operation.token_hash_prefix,
                    "threshold_ms": 100,
                },
            )

        if not success:
            logger.error("Failed cache operation: %s for token %s", operation_type, operation.token_hash_prefix)

            # Log security event for failed cache operations
            log_security_event(
                event_type="cache_operation_failed",
                success=False,
                details={
                    "operation_type": operation_type,
                    "response_time_ms": response_time_ms,
                    "token_hash_prefix": operation.token_hash_prefix,
                },
            )

    def get_current_metrics(self, window_minutes: int = 60) -> CacheMetrics:
        """
        Get current performance metrics for the specified time window.

        Args:
            window_minutes (int): Time window in minutes for metrics calculation

        Returns:
            CacheMetrics: Aggregated performance metrics
        """
        cutoff_time = time.time() - (window_minutes * 60)
        recent_ops = [op for op in self.operations if op.timestamp >= cutoff_time]

        if not recent_ops:
            return CacheMetrics(
                total_operations=0,
                cache_hits=0,
                cache_misses=0,
                cache_sets=0,
                cache_deletes=0,
                hit_rate=0.0,
                miss_rate=0.0,
                avg_response_time_ms=0.0,
                max_response_time_ms=0.0,
                min_response_time_ms=0.0,
                operations_per_second=0.0,
                error_count=0,
                error_rate=0.0,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        # Count operations by type
        op_counts = defaultdict(int)
        response_times = []
        error_count = 0

        for op in recent_ops:
            op_counts[op.operation_type] += 1
            response_times.append(op.response_time_ms)
            if not op.success:
                error_count += 1

        total_ops = len(recent_ops)
        cache_hits = op_counts["hit"]
        cache_misses = op_counts["miss"]
        cache_requests = cache_hits + cache_misses

        # Calculate rates
        hit_rate = (cache_hits / cache_requests * 100) if cache_requests > 0 else 0.0
        miss_rate = (cache_misses / cache_requests * 100) if cache_requests > 0 else 0.0
        error_rate = (error_count / total_ops * 100) if total_ops > 0 else 0.0

        # Calculate response time stats
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0.0
        max_response_time = max(response_times) if response_times else 0.0
        min_response_time = min(response_times) if response_times else 0.0

        # Calculate operations per second
        time_span = window_minutes * 60
        ops_per_second = total_ops / time_span if time_span > 0 else 0.0

        return CacheMetrics(
            total_operations=total_ops,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            cache_sets=op_counts["set"],
            cache_deletes=op_counts["delete"],
            hit_rate=round(hit_rate, 2),
            miss_rate=round(miss_rate, 2),
            avg_response_time_ms=round(avg_response_time, 2),
            max_response_time_ms=round(max_response_time, 2),
            min_response_time_ms=round(min_response_time, 2),
            operations_per_second=round(ops_per_second, 2),
            error_count=error_count,
            error_rate=round(error_rate, 2),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def perform_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive cache health check.

        Returns:
            Dict[str, Any]: Health check results
        """
        health_check_start = time.time()
        health_status = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": "healthy",
            "checks": {},
            "alerts": [],
        }

        try:
            # Test Redis connectivity
            redis_start = time.time()
            redis_conn = await redis_manager.get_redis()
            await redis_conn.ping()
            redis_time = (time.time() - redis_start) * 1000

            health_status["checks"]["redis_connectivity"] = {
                "status": "healthy",
                "response_time_ms": round(redis_time, 2),
            }

            if redis_time > 50:  # Alert if Redis is slow
                health_status["alerts"].append(f"Redis response time is high: {redis_time:.2f}ms")

        except Exception as e:
            health_status["checks"]["redis_connectivity"] = {"status": "unhealthy", "error": str(e)}
            health_status["overall_status"] = "unhealthy"
            health_status["alerts"].append(f"Redis connectivity failed: {str(e)}")

        try:
            # Get cache statistics
            cache_stats = await get_cache_statistics()
            health_status["checks"]["cache_statistics"] = {
                "status": "healthy",
                "cache_count": cache_stats.get("cache_count", 0),
                "cache_memory_mb": cache_stats.get("cache_memory_mb", 0),
                "hit_rate": cache_stats.get("cache_hit_rate", 0),
            }

            # Check hit rate
            hit_rate = cache_stats.get("cache_hit_rate", 0)
            if hit_rate < PERFORMANCE_ALERT_THRESHOLD * 100:
                health_status["alerts"].append(f"Cache hit rate is low: {hit_rate}%")

        except Exception as e:
            health_status["checks"]["cache_statistics"] = {"status": "unhealthy", "error": str(e)}
            health_status["alerts"].append(f"Failed to get cache statistics: {str(e)}")

        # Check recent performance metrics
        try:
            recent_metrics = self.get_current_metrics(window_minutes=15)
            health_status["checks"]["recent_performance"] = {
                "status": "healthy",
                "hit_rate": recent_metrics.hit_rate,
                "avg_response_time_ms": recent_metrics.avg_response_time_ms,
                "error_rate": recent_metrics.error_rate,
                "operations_per_second": recent_metrics.operations_per_second,
            }

            # Performance alerts
            if recent_metrics.hit_rate < PERFORMANCE_ALERT_THRESHOLD * 100:
                health_status["alerts"].append(f"Recent hit rate is low: {recent_metrics.hit_rate}%")

            if recent_metrics.avg_response_time_ms > 100:
                health_status["alerts"].append(
                    f"Average response time is high: {recent_metrics.avg_response_time_ms}ms"
                )

            if recent_metrics.error_rate > 5:
                health_status["alerts"].append(f"Error rate is high: {recent_metrics.error_rate}%")

        except Exception as e:
            health_status["checks"]["recent_performance"] = {"status": "unhealthy", "error": str(e)}
            health_status["alerts"].append(f"Failed to get recent performance metrics: {str(e)}")

        # Overall health determination
        if health_status["alerts"]:
            health_status["overall_status"] = (
                "degraded" if health_status["overall_status"] == "healthy" else "unhealthy"
            )

        total_time = (time.time() - health_check_start) * 1000
        health_status["health_check_duration_ms"] = round(total_time, 2)

        self.last_health_check = datetime.now(timezone.utc)
        self.health_status = health_status

        # Log health check results
        if health_status["overall_status"] != "healthy":
            logger.warning("Cache health check failed: %s", health_status["alerts"])
        else:
            logger.debug("Cache health check passed")

        return health_status

    def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get a comprehensive performance summary.

        Returns:
            Dict[str, Any]: Performance summary with multiple time windows
        """
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "last_15_minutes": asdict(self.get_current_metrics(15)),
                "last_hour": asdict(self.get_current_metrics(60)),
                "last_4_hours": asdict(self.get_current_metrics(240)),
            },
            "health_status": self.health_status,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
        }

        return summary

    def clear_old_metrics(self):
        """
        Clear old metrics to prevent memory buildup.
        Called periodically to maintain performance.
        """
        cutoff_time = time.time() - (METRICS_RETENTION_HOURS * 3600)

        # Clear old operations (deque handles this automatically with maxlen)
        # Clear old hourly metrics
        old_hours = []
        for hour_key in self.hourly_metrics:
            try:
                hour_time = datetime.fromisoformat(hour_key).timestamp()
                if hour_time < cutoff_time:
                    old_hours.append(hour_key)
            except ValueError:
                old_hours.append(hour_key)  # Remove invalid keys

        for hour_key in old_hours:
            del self.hourly_metrics[hour_key]

        if old_hours:
            logger.debug("Cleared %d old hourly metrics", len(old_hours))


# Global performance monitor instance
cache_monitor = CachePerformanceMonitor()


async def get_cache_performance_metrics(window_minutes: int = 60) -> Dict[str, Any]:
    """
    Get cache performance metrics for the specified time window.

    Args:
        window_minutes (int): Time window in minutes

    Returns:
        Dict[str, Any]: Performance metrics
    """
    try:
        metrics = cache_monitor.get_current_metrics(window_minutes)
        return asdict(metrics)
    except Exception as e:
        logger.error("Error getting cache performance metrics: %s", e)
        return {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}


async def perform_cache_health_check() -> Dict[str, Any]:
    """
    Perform cache health check and return results.

    Returns:
        Dict[str, Any]: Health check results
    """
    try:
        return await cache_monitor.perform_health_check()
    except Exception as e:
        logger.error("Error performing cache health check: %s", e)
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "overall_status": "unhealthy", "error": str(e)}


def record_cache_hit(response_time_ms: float, token_hash: str = ""):
    """Record a cache hit operation."""
    cache_monitor.record_operation("hit", response_time_ms, token_hash, True)


def record_cache_miss(response_time_ms: float, token_hash: str = ""):
    """Record a cache miss operation."""
    cache_monitor.record_operation("miss", response_time_ms, token_hash, True)


def record_cache_set(response_time_ms: float, token_hash: str = "", success: bool = True):
    """Record a cache set operation."""
    cache_monitor.record_operation("set", response_time_ms, token_hash, success)


def record_cache_delete(response_time_ms: float, token_hash: str = "", success: bool = True):
    """Record a cache delete operation."""
    cache_monitor.record_operation("delete", response_time_ms, token_hash, success)


async def start_periodic_health_checks():
    """
    Start periodic health checks in the background.
    This should be called during application startup.
    """

    async def health_check_loop():
        while True:
            try:
                await asyncio.sleep(HEALTH_CHECK_INTERVAL)
                await cache_monitor.perform_health_check()
                cache_monitor.clear_old_metrics()
            except Exception as e:
                logger.error("Error in periodic health check: %s", e)

    # Start the health check loop as a background task
    asyncio.create_task(health_check_loop())
    logger.info("Started periodic cache health checks (interval: %ds)", HEALTH_CHECK_INTERVAL)
