"""Middleware for automatic IPAM metrics tracking.

This module provides utilities to automatically track metrics for IPAM operations
without requiring manual tracking calls in every endpoint.
"""

import time
from functools import wraps
from typing import Callable

from fastapi import Request

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.ipam.monitoring.metrics_tracker import get_ipam_metrics_tracker

logger = get_logger("Second_Brain_Database.IPAM.MetricsMiddleware")


def track_ipam_metrics(operation_type: str = None):
    """Decorator to automatically track metrics for IPAM operations.
    
    This decorator wraps endpoint functions to automatically track:
    - Request counts
    - Response times
    - Errors
    - Operation success/failure
    
    Args:
        operation_type: Optional operation type for tracking (e.g., "allocate_region")
    
    Usage:
        @track_ipam_metrics(operation_type="allocate_region")
        async def create_region(...):
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            metrics_tracker = get_ipam_metrics_tracker(redis_manager)
            
            # Extract request and user_id from kwargs
            request = kwargs.get("request")
            current_user = kwargs.get("current_user", {})
            user_id = str(current_user.get("_id", current_user.get("username", "")))
            
            # Get endpoint path
            endpoint = request.url.path if request else "unknown"
            
            # Track request
            try:
                await metrics_tracker.track_request(
                    endpoint=endpoint,
                    user_id=user_id,
                    method=request.method if request else "GET"
                )
            except Exception as e:
                logger.warning(f"Failed to track request: {e}")
            
            # Execute the endpoint function
            success = False
            error_type = None
            try:
                result = await func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                # Track error
                error_type = type(e).__name__
                try:
                    await metrics_tracker.track_error(
                        error_type=error_type,
                        endpoint=endpoint,
                        user_id=user_id
                    )
                except Exception as track_error:
                    logger.warning(f"Failed to track error: {track_error}")
                
                # Re-raise the original exception
                raise
            finally:
                # Track response time
                response_time = time.time() - start_time
                try:
                    await metrics_tracker.track_response_time(
                        endpoint=endpoint,
                        response_time=response_time,
                        user_id=user_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to track response time: {e}")
                
                # Track operation if operation_type specified
                if operation_type:
                    try:
                        await metrics_tracker.track_operation(
                            operation_type=operation_type,
                            success=success,
                            user_id=user_id
                        )
                    except Exception as e:
                        logger.warning(f"Failed to track operation: {e}")
        
        return wrapper
    return decorator


async def track_error_from_exception(
    exception: Exception,
    endpoint: str,
    user_id: str = None
):
    """Helper function to track errors from exception handlers.
    
    Args:
        exception: The exception that occurred
        endpoint: The endpoint where the error occurred
        user_id: Optional user ID
    """
    try:
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        error_type = type(exception).__name__
        
        await metrics_tracker.track_error(
            error_type=error_type,
            endpoint=endpoint,
            user_id=user_id
        )
    except Exception as e:
        logger.warning(f"Failed to track error from exception: {e}")


async def track_capacity_warning_event(
    resource_type: str,
    resource_id: str,
    utilization: float,
    threshold: int
):
    """Helper function to track capacity warnings.
    
    Args:
        resource_type: Type of resource (country, region, host)
        resource_id: ID of the resource
        utilization: Current utilization percentage
        threshold: Threshold that was exceeded
    """
    try:
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        
        await metrics_tracker.track_capacity_warning(
            resource_type=resource_type,
            resource_id=resource_id,
            utilization=utilization,
            threshold=threshold
        )
    except Exception as e:
        logger.warning(f"Failed to track capacity warning: {e}")


async def track_quota_exceeded_event(
    user_id: str,
    quota_type: str,
    current: int,
    limit: int
):
    """Helper function to track quota exceeded events.
    
    Args:
        user_id: User who exceeded quota
        quota_type: Type of quota (region, host)
        current: Current usage
        limit: Quota limit
    """
    try:
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        
        await metrics_tracker.track_quota_exceeded(
            user_id=user_id,
            quota_type=quota_type,
            current=current,
            limit=limit
        )
    except Exception as e:
        logger.warning(f"Failed to track quota exceeded: {e}")


async def track_allocation_event(
    resource_type: str,
    user_id: str
):
    """Helper function to track resource allocations.
    
    Args:
        resource_type: Type of resource allocated (region, host)
        user_id: User who allocated the resource
    """
    try:
        metrics_tracker = get_ipam_metrics_tracker(redis_manager)
        
        await metrics_tracker.track_allocation(
            resource_type=resource_type,
            user_id=user_id
        )
    except Exception as e:
        logger.warning(f"Failed to track allocation: {e}")
