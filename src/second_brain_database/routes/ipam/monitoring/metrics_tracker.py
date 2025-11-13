"""Metrics tracking for IPAM operations.

This module provides comprehensive metrics tracking for IPAM operations including:
- Error rates by type and endpoint
- Request rates per endpoint
- Response times
- Capacity utilization trends
- Quota usage patterns
- Operation success/failure rates

Requirements: Deployment monitoring (tasks.md - Deployment Checklist)
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import RedisManager

logger = get_logger("Second_Brain_Database.IPAM.Metrics")


class IPAMMetricsTracker:
    """Tracker for IPAM system metrics.
    
    This class provides methods to track and retrieve various metrics about
    IPAM system performance, errors, and usage. Metrics are stored in Redis for
    real-time access and can be exported for historical analysis.
    
    Metrics tracked:
    - Error rates by type and endpoint
    - Request rates per endpoint
    - Average response times
    - Capacity utilization warnings
    - Quota exceeded events
    - Operation success/failure rates
    - Allocation/release rates
    
    Attributes:
        redis_manager: Redis manager for real-time metrics storage
        metrics_ttl: TTL for Redis metrics (default: 1 hour)
    """
    
    def __init__(
        self,
        redis_manager: RedisManager,
        metrics_ttl: int = 3600
    ):
        """Initialize IPAMMetricsTracker.
        
        Args:
            redis_manager: Redis manager for metrics storage
            metrics_ttl: TTL for Redis metrics in seconds (default: 1 hour)
        """
        self.redis_manager = redis_manager
        self.metrics_ttl = metrics_ttl
        redis_client = None  # Will be initialized async on first use
    
    async def _get_redis(self):
        """Get Redis client, initializing if needed."""
        # Ensure attribute exists (for backwards compatibility)
        if not hasattr(self, '_redis_client'):
            self._redis_client = None
        
        if self._redis_client is None:
            self._redis_client = await self.redis_manager.get_redis()
        return self._redis_client
    
    # Error Rate Tracking
    
    async def track_error(
        self,
        error_type: str,
        endpoint: str,
        user_id: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        """Track an error occurrence.
        
        Args:
            error_type: Type/category of error (e.g., "capacity_exhausted", "quota_exceeded")
            endpoint: API endpoint where error occurred
            user_id: Optional user ID associated with error
            details: Optional additional error details
        """
        try:
            redis_client = await self._get_redis()
            current_time = int(time.time())
            
            # Track global error count by type
            error_key = f"ipam:metrics:errors:{error_type}"
            await redis_client.incr(error_key)
            await redis_client.expire(error_key, self.metrics_ttl)
            
            # Track errors per endpoint
            endpoint_error_key = f"ipam:metrics:errors:endpoint:{endpoint}:{error_type}"
            await redis_client.incr(endpoint_error_key)
            await redis_client.expire(endpoint_error_key, self.metrics_ttl)
            
            # Track total error count
            await redis_client.incr("ipam:metrics:errors:total")
            
            # Track errors per minute (for rate calculation)
            minute_key = f"ipam:metrics:errors:minute:{current_time // 60}"
            await redis_client.incr(minute_key)
            await redis_client.expire(minute_key, 120)  # Keep for 2 minutes
            
            # Track per-user error count if user_id provided
            if user_id:
                user_error_key = f"ipam:metrics:errors:user:{user_id}"
                await redis_client.incr(user_error_key)
                await redis_client.expire(user_error_key, self.metrics_ttl)
            
            logger.debug(
                f"Tracked error: type={error_type}, endpoint={endpoint}, user={user_id}"
            )
            
        except Exception as e:
            logger.error(f"Error tracking error metric: {e}", exc_info=True)
    
    async def get_error_rates(self) -> Dict[str, any]:
        """Get error counts and rates by type.
        
        Returns:
            Dict with error counts by type, total errors, and errors per minute
        """
        try:
            redis_client = await self._get_redis()
            # Get all error keys
            error_keys = []
            async for key in redis_client.scan_iter("ipam:metrics:errors:*"):
                key_str = key.decode() if isinstance(key, bytes) else key
                if (key_str != "ipam:metrics:errors:total" and 
                    ":endpoint:" not in key_str and 
                    ":user:" not in key_str and
                    ":minute:" not in key_str):
                    error_keys.append(key)
            
            # Get counts for each error type
            error_rates = {}
            for key in error_keys:
                count = await redis_client.get(key)
                if count:
                    # Extract error type from key
                    key_str = key.decode() if isinstance(key, bytes) else key
                    error_type = key_str.replace("ipam:metrics:errors:", "")
                    error_rates[error_type] = int(count)
            
            # Get total error count
            total = await redis_client.get("ipam:metrics:errors:total")
            error_rates["total"] = int(total) if total else 0
            
            # Calculate errors per minute
            current_time = int(time.time())
            current_minute = current_time // 60
            minute_key = f"ipam:metrics:errors:minute:{current_minute}"
            minute_count = await redis_client.get(minute_key)
            error_rates["errors_per_minute"] = int(minute_count) if minute_count else 0
            
            return error_rates
            
        except Exception as e:
            logger.error(f"Error getting error rates: {e}", exc_info=True)
            return {"total": 0, "errors_per_minute": 0}
    
    async def get_endpoint_error_rates(self, endpoint: str) -> Dict[str, int]:
        """Get error counts for a specific endpoint.
        
        Args:
            endpoint: API endpoint to get errors for
            
        Returns:
            Dict mapping error types to counts for this endpoint
        """
        try:
            redis_client = await self._get_redis()
            pattern = f"ipam:metrics:errors:endpoint:{endpoint}:*"
            error_keys = []
            async for key in redis_client.scan_iter(pattern):
                error_keys.append(key)
            
            endpoint_errors = {}
            for key in error_keys:
                count = await redis_client.get(key)
                if count:
                    # Extract error type from key
                    key_str = key.decode() if isinstance(key, bytes) else key
                    error_type = key_str.split(":")[-1]
                    endpoint_errors[error_type] = int(count)
            
            return endpoint_errors
            
        except Exception as e:
            logger.error(f"Error getting endpoint error rates: {e}", exc_info=True)
            return {}
    
    # Request Rate Tracking
    
    async def track_request(
        self,
        endpoint: str,
        user_id: str,
        method: str = "GET"
    ):
        """Track an API request.
        
        Args:
            endpoint: API endpoint being called
            user_id: User making the request
            method: HTTP method (GET, POST, etc.)
        """
        try:
            redis_client = await self._get_redis()
            current_time = int(time.time())
            
            # Track global request count
            await redis_client.incr("ipam:metrics:requests:total")
            
            # Track requests per minute (for rate calculation)
            minute_key = f"ipam:metrics:requests:minute:{current_time // 60}"
            await redis_client.incr(minute_key)
            await redis_client.expire(minute_key, 120)  # Keep for 2 minutes
            
            # Track per-endpoint request count
            endpoint_key = f"ipam:metrics:requests:endpoint:{endpoint}"
            await redis_client.incr(endpoint_key)
            await redis_client.expire(endpoint_key, self.metrics_ttl)
            
            # Track per-user request count
            user_key = f"ipam:metrics:requests:user:{user_id}"
            await redis_client.incr(user_key)
            await redis_client.expire(user_key, self.metrics_ttl)
            
            logger.debug(f"Tracked request: endpoint={endpoint}, user={user_id}, method={method}")
            
        except Exception as e:
            logger.error(f"Error tracking request: {e}", exc_info=True)
    
    async def get_requests_per_minute(self) -> float:
        """Get current requests per minute rate.
        
        Returns:
            float: Requests per minute (averaged over last minute)
        """
        try:
            redis_client = await self._get_redis()
            current_time = int(time.time())
            current_minute = current_time // 60
            
            # Get request count for current minute
            minute_key = f"ipam:metrics:requests:minute:{current_minute}"
            count = await redis_client.get(minute_key)
            
            if count is None:
                return 0.0
            
            return float(count)
            
        except Exception as e:
            logger.error(f"Error calculating requests per minute: {e}", exc_info=True)
            return 0.0
    
    # Response Time Tracking
    
    async def track_response_time(
        self,
        endpoint: str,
        response_time: float,
        user_id: Optional[str] = None
    ):
        """Track response time for an API request.
        
        Args:
            endpoint: API endpoint
            response_time: Response time in seconds
            user_id: Optional user ID
        """
        try:
            redis_client = await self._get_redis()
            # Track global average response time
            await self._update_average(
                "ipam:metrics:response_time:global",
                response_time
            )
            
            # Track per-endpoint average response time
            endpoint_key = f"ipam:metrics:response_time:endpoint:{endpoint}"
            await self._update_average(endpoint_key, response_time)
            
            logger.debug(
                f"Tracked response time {response_time:.3f}s for endpoint {endpoint}"
            )
            
        except Exception as e:
            logger.error(f"Error tracking response time: {e}", exc_info=True)
    
    async def get_average_response_time(
        self,
        endpoint: Optional[str] = None
    ) -> float:
        """Get average response time.
        
        Args:
            endpoint: Optional endpoint to get endpoint-specific average
            
        Returns:
            float: Average response time in seconds
        """
        try:
            redis_client = await self._get_redis()
            if endpoint:
                key = f"ipam:metrics:response_time:endpoint:{endpoint}"
            else:
                key = "ipam:metrics:response_time:global"
            
            avg = await self._get_average(key)
            return avg
            
        except Exception as e:
            logger.error(f"Error getting average response time: {e}", exc_info=True)
            return 0.0
    
    # Capacity Monitoring
    
    async def track_capacity_warning(
        self,
        resource_type: str,
        resource_id: str,
        utilization: float,
        threshold: int
    ):
        """Track a capacity warning event.
        
        Args:
            resource_type: Type of resource (country, region, host)
            resource_id: ID of the resource
            utilization: Current utilization percentage
            threshold: Threshold that was exceeded
        """
        try:
            redis_client = await self._get_redis()
            # Track capacity warnings by type
            warning_key = f"ipam:metrics:capacity_warnings:{resource_type}"
            await redis_client.incr(warning_key)
            await redis_client.expire(warning_key, self.metrics_ttl)
            
            # Track total capacity warnings
            await redis_client.incr("ipam:metrics:capacity_warnings:total")
            
            logger.debug(
                f"Tracked capacity warning: type={resource_type}, id={resource_id}, "
                f"utilization={utilization:.1f}%, threshold={threshold}%"
            )
            
        except Exception as e:
            logger.error(f"Error tracking capacity warning: {e}", exc_info=True)
    
    async def get_capacity_warnings(self) -> Dict[str, int]:
        """Get capacity warning counts by resource type.
        
        Returns:
            Dict mapping resource types to warning counts
        """
        try:
            redis_client = await self._get_redis()
            pattern = "ipam:metrics:capacity_warnings:*"
            warning_keys = []
            async for key in redis_client.scan_iter(pattern):
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str != "ipam:metrics:capacity_warnings:total":
                    warning_keys.append(key)
            
            warnings = {}
            for key in warning_keys:
                count = await redis_client.get(key)
                if count:
                    key_str = key.decode() if isinstance(key, bytes) else key
                    resource_type = key_str.replace("ipam:metrics:capacity_warnings:", "")
                    warnings[resource_type] = int(count)
            
            # Get total
            total = await redis_client.get("ipam:metrics:capacity_warnings:total")
            warnings["total"] = int(total) if total else 0
            
            return warnings
            
        except Exception as e:
            logger.error(f"Error getting capacity warnings: {e}", exc_info=True)
            return {"total": 0}
    
    # Quota Tracking
    
    async def track_quota_exceeded(
        self,
        user_id: str,
        quota_type: str,
        current: int,
        limit: int
    ):
        """Track a quota exceeded event.
        
        Args:
            user_id: User who exceeded quota
            quota_type: Type of quota (region, host)
            current: Current usage
            limit: Quota limit
        """
        try:
            redis_client = await self._get_redis()
            # Track quota exceeded events by type
            quota_key = f"ipam:metrics:quota_exceeded:{quota_type}"
            await redis_client.incr(quota_key)
            await redis_client.expire(quota_key, self.metrics_ttl)
            
            # Track total quota exceeded events
            await redis_client.incr("ipam:metrics:quota_exceeded:total")
            
            # Track per-user quota exceeded events
            user_key = f"ipam:metrics:quota_exceeded:user:{user_id}"
            await redis_client.incr(user_key)
            await redis_client.expire(user_key, self.metrics_ttl)
            
            logger.debug(
                f"Tracked quota exceeded: user={user_id}, type={quota_type}, "
                f"current={current}, limit={limit}"
            )
            
        except Exception as e:
            logger.error(f"Error tracking quota exceeded: {e}", exc_info=True)
    
    async def get_quota_exceeded_counts(self) -> Dict[str, int]:
        """Get quota exceeded counts by type.
        
        Returns:
            Dict mapping quota types to exceeded counts
        """
        try:
            redis_client = await self._get_redis()
            pattern = "ipam:metrics:quota_exceeded:*"
            quota_keys = []
            async for key in redis_client.scan_iter(pattern):
                key_str = key.decode() if isinstance(key, bytes) else key
                if (key_str != "ipam:metrics:quota_exceeded:total" and 
                    ":user:" not in key_str):
                    quota_keys.append(key)
            
            quotas = {}
            for key in quota_keys:
                count = await redis_client.get(key)
                if count:
                    key_str = key.decode() if isinstance(key, bytes) else key
                    quota_type = key_str.replace("ipam:metrics:quota_exceeded:", "")
                    quotas[quota_type] = int(count)
            
            # Get total
            total = await redis_client.get("ipam:metrics:quota_exceeded:total")
            quotas["total"] = int(total) if total else 0
            
            return quotas
            
        except Exception as e:
            logger.error(f"Error getting quota exceeded counts: {e}", exc_info=True)
            return {"total": 0}
    
    # Operation Success/Failure Tracking
    
    async def track_operation(
        self,
        operation_type: str,
        success: bool,
        user_id: Optional[str] = None
    ):
        """Track an IPAM operation success or failure.
        
        Args:
            operation_type: Type of operation (allocate_region, allocate_host, etc.)
            success: Whether operation was successful
            user_id: Optional user ID
        """
        try:
            redis_client = await self._get_redis()
            if success:
                success_key = f"ipam:metrics:operations:{operation_type}:success"
                await redis_client.incr(success_key)
                await redis_client.expire(success_key, self.metrics_ttl)
            else:
                failure_key = f"ipam:metrics:operations:{operation_type}:failure"
                await redis_client.incr(failure_key)
                await redis_client.expire(failure_key, self.metrics_ttl)
            
            logger.debug(
                f"Tracked operation: type={operation_type}, success={success}, user={user_id}"
            )
            
        except Exception as e:
            logger.error(f"Error tracking operation: {e}", exc_info=True)
    
    async def get_operation_stats(self, operation_type: str) -> Dict[str, any]:
        """Get statistics for a specific operation type.
        
        Args:
            operation_type: Type of operation
            
        Returns:
            Dict with success_count, failure_count, success_rate
        """
        try:
            redis_client = await self._get_redis()
            success_key = f"ipam:metrics:operations:{operation_type}:success"
            failure_key = f"ipam:metrics:operations:{operation_type}:failure"
            
            success_count = await redis_client.get(success_key)
            failure_count = await redis_client.get(failure_key)
            
            success_count = int(success_count) if success_count else 0
            failure_count = int(failure_count) if failure_count else 0
            
            total = success_count + failure_count
            success_rate = (success_count / total * 100.0) if total > 0 else 0.0
            
            return {
                "success_count": success_count,
                "failure_count": failure_count,
                "total_count": total,
                "success_rate": success_rate
            }
            
        except Exception as e:
            logger.error(f"Error getting operation stats: {e}", exc_info=True)
            return {
                "success_count": 0,
                "failure_count": 0,
                "total_count": 0,
                "success_rate": 0.0
            }
    
    # Allocation Rate Tracking
    
    async def track_allocation(
        self,
        resource_type: str,
        user_id: str
    ):
        """Track a resource allocation.
        
        Args:
            resource_type: Type of resource allocated (region, host)
            user_id: User who allocated the resource
        """
        try:
            redis_client = await self._get_redis()
            current_time = int(time.time())
            
            # Track allocations per minute
            minute_key = f"ipam:metrics:allocations:{resource_type}:minute:{current_time // 60}"
            await redis_client.incr(minute_key)
            await redis_client.expire(minute_key, 120)
            
            # Track total allocations
            total_key = f"ipam:metrics:allocations:{resource_type}:total"
            await redis_client.incr(total_key)
            
            logger.debug(f"Tracked allocation: type={resource_type}, user={user_id}")
            
        except Exception as e:
            logger.error(f"Error tracking allocation: {e}", exc_info=True)
    
    async def get_allocation_rate(self, resource_type: str) -> float:
        """Get current allocation rate for a resource type.
        
        Args:
            resource_type: Type of resource (region, host)
            
        Returns:
            float: Allocations per minute
        """
        try:
            redis_client = await self._get_redis()
            current_time = int(time.time())
            current_minute = current_time // 60
            
            minute_key = f"ipam:metrics:allocations:{resource_type}:minute:{current_minute}"
            count = await redis_client.get(minute_key)
            
            return float(count) if count else 0.0
            
        except Exception as e:
            logger.error(f"Error getting allocation rate: {e}", exc_info=True)
            return 0.0
    
    # Helper Methods
    
    async def _update_average(self, key: str, value: float):
        """Update a running average in Redis.
        
        Uses a simple moving average approach with count and sum.
        
        Args:
            key: Redis key for the average
            value: New value to include in average
        """
        try:
            redis_client = await self._get_redis()
            count_key = f"{key}:count"
            sum_key = f"{key}:sum"
            
            # Increment count
            await redis_client.incr(count_key)
            await redis_client.expire(count_key, self.metrics_ttl)
            
            # Add to sum
            await redis_client.incrbyfloat(sum_key, value)
            await redis_client.expire(sum_key, self.metrics_ttl)
            
        except Exception as e:
            logger.error(f"Error updating average for {key}: {e}", exc_info=True)
    
    async def _get_average(self, key: str) -> float:
        """Get a running average from Redis.
        
        Args:
            key: Redis key for the average
            
        Returns:
            float: Average value
        """
        try:
            redis_client = await self._get_redis()
            count_key = f"{key}:count"
            sum_key = f"{key}:sum"
            
            count = await redis_client.get(count_key)
            total = await redis_client.get(sum_key)
            
            if not count or not total:
                return 0.0
            
            count = int(count)
            total = float(total)
            
            if count == 0:
                return 0.0
            
            return total / count
            
        except Exception as e:
            logger.error(f"Error getting average for {key}: {e}", exc_info=True)
            return 0.0
    
    # Summary Methods
    
    async def get_metrics_summary(self) -> Dict[str, any]:
        """Get a comprehensive summary of all IPAM metrics.
        
        Returns:
            Dict with all tracked metrics
        """
        try:
            redis_client = await self._get_redis()
            summary = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "requests": {
                    "requests_per_minute": await self.get_requests_per_minute(),
                    "average_response_time": await self.get_average_response_time()
                },
                "errors": await self.get_error_rates(),
                "capacity_warnings": await self.get_capacity_warnings(),
                "quota_exceeded": await self.get_quota_exceeded_counts(),
                "operations": {
                    "allocate_region": await self.get_operation_stats("allocate_region"),
                    "allocate_host": await self.get_operation_stats("allocate_host"),
                    "retire_region": await self.get_operation_stats("retire_region"),
                    "release_host": await self.get_operation_stats("release_host")
                },
                "allocation_rates": {
                    "regions_per_minute": await self.get_allocation_rate("region"),
                    "hosts_per_minute": await self.get_allocation_rate("host")
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting metrics summary: {e}", exc_info=True)
            return {}
    
    async def reset_metrics(self):
        """Reset all metrics (useful for testing or periodic resets).
        
        WARNING: This will delete all current metrics data.
        """
        try:
            redis_client = await self._get_redis()
            # Get all IPAM metrics keys
            pattern = "ipam:metrics:*"
            keys_to_delete = []
            async for key in redis_client.scan_iter(pattern):
                keys_to_delete.append(key)
            
            # Delete all metrics keys
            if keys_to_delete:
                await redis_client.delete(*keys_to_delete)
                logger.info(f"Reset {len(keys_to_delete)} metrics keys")
            else:
                logger.info("No metrics keys to reset")
            
        except Exception as e:
            logger.error(f"Error resetting metrics: {e}", exc_info=True)


# Global metrics tracker instance (initialized on first use)
_metrics_tracker: Optional[IPAMMetricsTracker] = None


def get_ipam_metrics_tracker(
    redis_manager: RedisManager
) -> IPAMMetricsTracker:
    """Get or create global IPAM metrics tracker instance.
    
    Args:
        redis_manager: Redis manager for metrics storage
        
    Returns:
        IPAMMetricsTracker: Global metrics tracker instance
    """
    global _metrics_tracker
    
    if _metrics_tracker is None:
        _metrics_tracker = IPAMMetricsTracker(
            redis_manager=redis_manager
        )
    
    return _metrics_tracker
