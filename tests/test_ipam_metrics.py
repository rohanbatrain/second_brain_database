"""Tests for IPAM metrics tracking.

This module tests the IPAM metrics tracker functionality including:
- Error rate tracking
- Request rate tracking
- Response time tracking
- Capacity warning tracking
- Quota exceeded tracking
- Operation success/failure tracking
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from second_brain_database.routes.ipam.monitoring.metrics_tracker import IPAMMetricsTracker


@pytest.fixture
def mock_redis_manager():
    """Create a mock Redis manager for testing."""
    redis_manager = MagicMock()
    redis_client = AsyncMock()
    redis_manager.get_client.return_value = redis_client
    return redis_manager, redis_client


@pytest.mark.asyncio
async def test_track_error(mock_redis_manager):
    """Test error tracking."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Track an error
    await tracker.track_error(
        error_type="capacity_exhausted",
        endpoint="/ipam/regions",
        user_id="test_user"
    )
    
    # Verify Redis calls
    assert redis_client.incr.called
    assert redis_client.expire.called


@pytest.mark.asyncio
async def test_track_request(mock_redis_manager):
    """Test request tracking."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Track a request
    await tracker.track_request(
        endpoint="/ipam/regions",
        user_id="test_user",
        method="POST"
    )
    
    # Verify Redis calls
    assert redis_client.incr.called


@pytest.mark.asyncio
async def test_track_response_time(mock_redis_manager):
    """Test response time tracking."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Track response time
    await tracker.track_response_time(
        endpoint="/ipam/regions",
        response_time=0.125,
        user_id="test_user"
    )
    
    # Verify Redis calls
    assert redis_client.incr.called
    assert redis_client.incrbyfloat.called


@pytest.mark.asyncio
async def test_track_capacity_warning(mock_redis_manager):
    """Test capacity warning tracking."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Track capacity warning
    await tracker.track_capacity_warning(
        resource_type="country",
        resource_id="India",
        utilization=85.5,
        threshold=80
    )
    
    # Verify Redis calls
    assert redis_client.incr.called


@pytest.mark.asyncio
async def test_track_quota_exceeded(mock_redis_manager):
    """Test quota exceeded tracking."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Track quota exceeded
    await tracker.track_quota_exceeded(
        user_id="test_user",
        quota_type="region",
        current=1000,
        limit=1000
    )
    
    # Verify Redis calls
    assert redis_client.incr.called


@pytest.mark.asyncio
async def test_track_operation(mock_redis_manager):
    """Test operation tracking."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Track successful operation
    await tracker.track_operation(
        operation_type="allocate_region",
        success=True,
        user_id="test_user"
    )
    
    # Verify Redis calls
    assert redis_client.incr.called
    
    # Track failed operation
    await tracker.track_operation(
        operation_type="allocate_region",
        success=False,
        user_id="test_user"
    )
    
    # Verify Redis calls
    assert redis_client.incr.called


@pytest.mark.asyncio
async def test_track_allocation(mock_redis_manager):
    """Test allocation tracking."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Track allocation
    await tracker.track_allocation(
        resource_type="region",
        user_id="test_user"
    )
    
    # Verify Redis calls
    assert redis_client.incr.called


@pytest.mark.asyncio
async def test_get_error_rates(mock_redis_manager):
    """Test getting error rates."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Mock scan_iter to return some error keys
    async def mock_scan_iter(pattern):
        keys = [
            b"ipam:metrics:errors:capacity_exhausted",
            b"ipam:metrics:errors:quota_exceeded"
        ]
        for key in keys:
            yield key
    
    redis_client.scan_iter = mock_scan_iter
    redis_client.get = AsyncMock(side_effect=[5, 12, 17, 0])  # counts for each key
    
    # Get error rates
    error_rates = await tracker.get_error_rates()
    
    # Verify results
    assert "capacity_exhausted" in error_rates
    assert "quota_exceeded" in error_rates
    assert "total" in error_rates


@pytest.mark.asyncio
async def test_get_metrics_summary(mock_redis_manager):
    """Test getting comprehensive metrics summary."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Mock all the necessary Redis calls
    async def mock_scan_iter(pattern):
        if "errors" in pattern:
            yield b"ipam:metrics:errors:capacity_exhausted"
        elif "capacity_warnings" in pattern:
            yield b"ipam:metrics:capacity_warnings:country"
        elif "quota_exceeded" in pattern:
            yield b"ipam:metrics:quota_exceeded:region"
        return
    
    redis_client.scan_iter = mock_scan_iter
    redis_client.get = AsyncMock(return_value=10)
    
    # Get metrics summary
    summary = await tracker.get_metrics_summary()
    
    # Verify structure
    assert "timestamp" in summary
    assert "requests" in summary
    assert "errors" in summary
    assert "capacity_warnings" in summary
    assert "quota_exceeded" in summary
    assert "operations" in summary
    assert "allocation_rates" in summary


@pytest.mark.asyncio
async def test_reset_metrics(mock_redis_manager):
    """Test resetting all metrics."""
    redis_manager, redis_client = mock_redis_manager
    tracker = IPAMMetricsTracker(redis_manager)
    
    # Mock scan_iter to return some keys
    async def mock_scan_iter(pattern):
        keys = [
            b"ipam:metrics:errors:total",
            b"ipam:metrics:requests:total"
        ]
        for key in keys:
            yield key
    
    redis_client.scan_iter = mock_scan_iter
    redis_client.delete = AsyncMock()
    
    # Reset metrics
    await tracker.reset_metrics()
    
    # Verify delete was called
    assert redis_client.delete.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
