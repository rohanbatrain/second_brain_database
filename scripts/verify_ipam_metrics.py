#!/usr/bin/env python3
"""Verify IPAM metrics monitoring system.

This script verifies that the IPAM metrics tracking system is properly
configured and operational. It checks:
- Metrics tracker initialization
- Redis connectivity
- Metrics endpoints accessibility
- Metrics data collection
- Performance requirements

Usage:
    python scripts/verify_ipam_metrics.py
"""

import asyncio
import sys
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, "src")

from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.ipam.monitoring.metrics_tracker import (
    IPAMMetricsTracker,
    get_ipam_metrics_tracker,
)


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80)


def print_success(text: str):
    """Print a success message."""
    print(f"✓ {text}")


def print_error(text: str):
    """Print an error message."""
    print(f"✗ {text}")


def print_warning(text: str):
    """Print a warning message."""
    print(f"⚠ {text}")


async def verify_redis_connection():
    """Verify Redis connection for metrics storage."""
    print_header("1. Redis Connection Verification")
    
    try:
        client = await redis_manager.get_redis()
        
        # Test ping
        await client.ping()
        print_success("Redis connection successful")
        
        # Test set/get
        test_key = "ipam:metrics:test:verification"
        await client.setex(test_key, 10, "test_value")
        value = await client.get(test_key)
        
        if value:
            print_success("Redis read/write operations working")
            await client.delete(test_key)
        else:
            print_error("Redis read operation failed")
            return False
        
        # Check memory
        info = await client.info("memory")
        used_memory = info.get("used_memory_human", "unknown")
        print_success(f"Redis memory usage: {used_memory}")
        
        return True
        
    except Exception as e:
        print_error(f"Redis connection failed: {e}")
        return False


async def verify_metrics_tracker_initialization():
    """Verify metrics tracker can be initialized."""
    print_header("2. Metrics Tracker Initialization")
    
    try:
        # Get tracker instance
        tracker = get_ipam_metrics_tracker(redis_manager)
        print_success("Metrics tracker initialized successfully")
        
        # Verify tracker has required methods
        required_methods = [
            "track_error",
            "track_request",
            "track_response_time",
            "track_capacity_warning",
            "track_quota_exceeded",
            "track_operation",
            "track_allocation",
            "get_error_rates",
            "get_metrics_summary",
        ]
        
        for method in required_methods:
            if hasattr(tracker, method):
                print_success(f"Method '{method}' available")
            else:
                print_error(f"Method '{method}' missing")
                return False
        
        return True
        
    except Exception as e:
        print_error(f"Metrics tracker initialization failed: {e}")
        return False


async def verify_metrics_tracking():
    """Verify metrics can be tracked and retrieved."""
    print_header("3. Metrics Tracking Verification")
    
    try:
        tracker = get_ipam_metrics_tracker(redis_manager)
        
        # Track test error
        await tracker.track_error(
            error_type="test_error",
            endpoint="/ipam/test",
            user_id="test_user"
        )
        print_success("Error tracking successful")
        
        # Track test request
        await tracker.track_request(
            endpoint="/ipam/test",
            user_id="test_user",
            method="GET"
        )
        print_success("Request tracking successful")
        
        # Track test response time
        await tracker.track_response_time(
            endpoint="/ipam/test",
            response_time=0.125,
            user_id="test_user"
        )
        print_success("Response time tracking successful")
        
        # Track test capacity warning
        await tracker.track_capacity_warning(
            resource_type="test_resource",
            resource_id="test_id",
            utilization=85.0,
            threshold=80
        )
        print_success("Capacity warning tracking successful")
        
        # Track test quota exceeded
        await tracker.track_quota_exceeded(
            user_id="test_user",
            quota_type="test_quota",
            current=100,
            limit=100
        )
        print_success("Quota exceeded tracking successful")
        
        # Track test operation
        await tracker.track_operation(
            operation_type="test_operation",
            success=True,
            user_id="test_user"
        )
        print_success("Operation tracking successful")
        
        # Track test allocation
        await tracker.track_allocation(
            resource_type="test_resource",
            user_id="test_user"
        )
        print_success("Allocation tracking successful")
        
        # Wait a moment for Redis to process
        await asyncio.sleep(0.1)
        
        return True
        
    except Exception as e:
        print_error(f"Metrics tracking failed: {e}")
        return False


async def verify_metrics_retrieval():
    """Verify metrics can be retrieved."""
    print_header("4. Metrics Retrieval Verification")
    
    try:
        tracker = get_ipam_metrics_tracker(redis_manager)
        
        # Get error rates
        error_rates = await tracker.get_error_rates()
        print_success(f"Error rates retrieved: {len(error_rates)} metrics")
        
        # Get requests per minute
        rpm = await tracker.get_requests_per_minute()
        print_success(f"Requests per minute: {rpm}")
        
        # Get average response time
        avg_time = await tracker.get_average_response_time()
        print_success(f"Average response time: {avg_time:.3f}s")
        
        # Get capacity warnings
        warnings = await tracker.get_capacity_warnings()
        print_success(f"Capacity warnings retrieved: {len(warnings)} types")
        
        # Get quota exceeded counts
        quotas = await tracker.get_quota_exceeded_counts()
        print_success(f"Quota exceeded counts retrieved: {len(quotas)} types")
        
        # Get operation stats
        op_stats = await tracker.get_operation_stats("test_operation")
        print_success(f"Operation stats retrieved: {op_stats.get('total_count', 0)} operations")
        
        # Get allocation rate
        alloc_rate = await tracker.get_allocation_rate("test_resource")
        print_success(f"Allocation rate: {alloc_rate} per minute")
        
        return True
        
    except Exception as e:
        print_error(f"Metrics retrieval failed: {e}")
        return False


async def verify_metrics_summary():
    """Verify comprehensive metrics summary."""
    print_header("5. Metrics Summary Verification")
    
    try:
        tracker = get_ipam_metrics_tracker(redis_manager)
        
        # Get comprehensive summary
        summary = await tracker.get_metrics_summary()
        
        # Verify structure
        required_keys = [
            "timestamp",
            "requests",
            "errors",
            "capacity_warnings",
            "quota_exceeded",
            "operations",
            "allocation_rates",
        ]
        
        for key in required_keys:
            if key in summary:
                print_success(f"Summary contains '{key}'")
            else:
                print_error(f"Summary missing '{key}'")
                return False
        
        # Display summary
        print(f"\nMetrics Summary:")
        print(f"  Timestamp: {summary.get('timestamp', 'N/A')}")
        print(f"  Requests per minute: {summary.get('requests', {}).get('requests_per_minute', 0)}")
        print(f"  Average response time: {summary.get('requests', {}).get('average_response_time', 0):.3f}s")
        print(f"  Total errors: {summary.get('errors', {}).get('total', 0)}")
        print(f"  Capacity warnings: {summary.get('capacity_warnings', {}).get('total', 0)}")
        print(f"  Quota exceeded: {summary.get('quota_exceeded', {}).get('total', 0)}")
        
        return True
        
    except Exception as e:
        print_error(f"Metrics summary failed: {e}")
        return False


async def verify_performance_requirements():
    """Verify metrics tracking meets performance requirements."""
    print_header("6. Performance Requirements Verification")
    
    try:
        tracker = get_ipam_metrics_tracker(redis_manager)
        
        # Test tracking performance (should be fast, non-blocking)
        iterations = 100
        
        # Test error tracking performance
        start = time.time()
        for i in range(iterations):
            await tracker.track_error(
                error_type="perf_test",
                endpoint="/ipam/test",
                user_id="perf_user"
            )
        error_time = (time.time() - start) / iterations
        
        if error_time < 0.01:  # Should be < 10ms per call
            print_success(f"Error tracking performance: {error_time*1000:.2f}ms per call")
        else:
            print_warning(f"Error tracking slow: {error_time*1000:.2f}ms per call (target: <10ms)")
        
        # Test retrieval performance
        start = time.time()
        for i in range(10):
            await tracker.get_metrics_summary()
        retrieval_time = (time.time() - start) / 10
        
        if retrieval_time < 0.1:  # Should be < 100ms per call
            print_success(f"Metrics retrieval performance: {retrieval_time*1000:.2f}ms per call")
        else:
            print_warning(f"Metrics retrieval slow: {retrieval_time*1000:.2f}ms per call (target: <100ms)")
        
        return True
        
    except Exception as e:
        print_error(f"Performance verification failed: {e}")
        return False


async def cleanup_test_data():
    """Clean up test metrics data."""
    print_header("7. Cleanup Test Data")
    
    try:
        client = await redis_manager.get_redis()
        
        # Delete test keys
        test_patterns = [
            "ipam:metrics:*test*",
            "ipam:metrics:*perf*",
        ]
        
        deleted_count = 0
        for pattern in test_patterns:
            async for key in client.scan_iter(pattern):
                await client.delete(key)
                deleted_count += 1
        
        print_success(f"Cleaned up {deleted_count} test metrics keys")
        
        return True
        
    except Exception as e:
        print_error(f"Cleanup failed: {e}")
        return False


async def main():
    """Run all verification checks."""
    print_header("IPAM Metrics Monitoring System Verification")
    print(f"Started at: {datetime.now().isoformat()}")
    
    results = []
    
    # Run verification checks
    results.append(("Redis Connection", await verify_redis_connection()))
    results.append(("Metrics Tracker Init", await verify_metrics_tracker_initialization()))
    results.append(("Metrics Tracking", await verify_metrics_tracking()))
    results.append(("Metrics Retrieval", await verify_metrics_retrieval()))
    results.append(("Metrics Summary", await verify_metrics_summary()))
    results.append(("Performance", await verify_performance_requirements()))
    results.append(("Cleanup", await cleanup_test_data()))
    
    # Print summary
    print_header("Verification Summary")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {check_name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print_success("\n✅ All metrics monitoring checks passed!")
        print("\nThe IPAM metrics monitoring system is properly configured and operational.")
        return 0
    else:
        print_error(f"\n❌ {total - passed} checks failed!")
        print("\nPlease review the errors above and fix the issues.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
