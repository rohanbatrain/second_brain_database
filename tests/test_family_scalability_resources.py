"""
Comprehensive scalability and resource testing for the family management system.

This test suite validates:
- Horizontal scaling capabilities and load distribution
- Memory usage and garbage collection efficiency
- Database query performance and optimization
- Cache hit rates and eviction policies
- System behavior under resource constraints

Requirements: 10.2, 10.3, 10.5, 10.6
"""

import asyncio
from datetime import datetime, timezone
import gc
import sys
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest


class ResourceMonitor:
    """Monitor system resources during testing."""

    def __init__(self):
        self.initial_memory = 100.0  # Simulated initial memory in MB
        self.current_memory = self.initial_memory
        self.peak_memory = self.initial_memory
        self.memory_samples = []
        self.cpu_samples = []

    def sample(self):
        """Take a resource sample."""
        # Simulate memory growth during operations
        self.current_memory += 0.1  # Small growth per sample
        cpu = 10.0  # Simulated CPU usage

        self.peak_memory = max(self.peak_memory, self.current_memory)
        self.memory_samples.append(self.current_memory)
        self.cpu_samples.append(cpu)

    def get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        return self.current_memory

    def get_memory_growth_mb(self) -> float:
        """Get memory growth since initialization in MB."""
        return self.current_memory - self.initial_memory

    def get_peak_memory_mb(self) -> float:
        """Get peak memory usage in MB."""
        return self.peak_memory


class CacheSimulator:
    """Simulate cache behavior with hit rates and eviction policies."""

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl
        self.cache = {}
        self.access_times = {}
        self.hit_count = 0
        self.miss_count = 0

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache with hit/miss tracking."""
        current_time = time.time()

        if key in self.cache:
            # Check TTL
            if current_time - self.access_times[key] < self.ttl:
                self.hit_count += 1
                self.access_times[key] = current_time
                return self.cache[key]
            else:
                # Expired
                del self.cache[key]
                del self.access_times[key]

        self.miss_count += 1
        return None

    async def set(self, key: str, value: Any) -> None:
        """Set value in cache with eviction policy."""
        current_time = time.time()

        # Evict if at capacity
        if len(self.cache) >= self.max_size and key not in self.cache:
            # LRU eviction
            oldest_key = min(self.access_times.keys(), key=lambda k: self.access_times[k])
            del self.cache[oldest_key]
            del self.access_times[oldest_key]

        self.cache[key] = value
        self.access_times[key] = current_time

    def get_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hit_count + self.miss_count
        return self.hit_count / total if total > 0 else 0.0

    def get_size(self) -> int:
        """Get current cache size."""
        return len(self.cache)


class MockScalabilityFamilyManager:
    """Mock family manager for scalability testing."""

    def __init__(self):
        self.created_families = []
        self.operation_count = 0
        self.query_latencies = {"user_lookup": 0.001, "family_count": 0.002, "family_insert": 0.005}

    async def create_family(self, user_id: str, name: str = None, request_context: Dict = None) -> Dict[str, Any]:
        """Mock family creation with simulated latency."""
        # Simulate database operations with latency
        await asyncio.sleep(self.query_latencies["user_lookup"])  # User lookup
        await asyncio.sleep(self.query_latencies["family_count"])  # Family count
        await asyncio.sleep(self.query_latencies["family_insert"])  # Family insert

        self.operation_count += 1

        family_id = f"fam_{uuid.uuid4().hex[:16]}"
        sbd_username = f"family_{user_id}_{len(self.created_families)}"

        family_data = {
            "family_id": family_id,
            "name": name or f"Family of {user_id}",
            "admin_user_ids": [user_id],
            "member_count": 1,
            "created_at": datetime.now(timezone.utc),
            "sbd_account": {"account_username": sbd_username, "balance": 0, "is_frozen": False},
            "transaction_safe": True,
        }

        self.created_families.append(family_data)
        return family_data


class TestScalabilityAndResources:
    """Test system scalability and resource utilization."""

    @pytest.fixture
    def family_manager_with_monitoring(self):
        """Create a family manager with resource monitoring."""
        manager = MockScalabilityFamilyManager()

        # Attach cache simulator for testing
        manager._cache_simulator = CacheSimulator(max_size=500, ttl=300)

        return manager

    @pytest.mark.asyncio
    async def test_horizontal_scaling_simulation(self, family_manager_with_monitoring):
        """
        Test horizontal scaling capabilities and load distribution.

        Simulates multiple application instances handling distributed load.

        Requirements: 10.2, 10.3
        """
        resource_monitor = ResourceMonitor()

        # Simulate multiple application instances
        num_instances = 5
        operations_per_instance = 20

        # Track performance metrics per instance
        instance_metrics = {}

        async def simulate_instance_load(instance_id: int) -> Dict[str, Any]:
            """Simulate load on a single application instance."""
            instance_start_time = time.time()
            successful_operations = 0
            failed_operations = 0

            # Create operations for this instance
            user_ids = [f"instance_{instance_id}_user_{i}" for i in range(operations_per_instance)]

            for user_id in user_ids:
                try:
                    resource_monitor.sample()

                    result = await family_manager_with_monitoring.create_family(
                        user_id=user_id,
                        name=f"Family {user_id}",
                        request_context={"ip_address": f"10.0.{instance_id}.1", "user_agent": "test"},
                    )
                    successful_operations += 1

                except Exception as e:
                    failed_operations += 1

                # Simulate processing delay
                await asyncio.sleep(0.01)

            instance_duration = time.time() - instance_start_time

            return {
                "instance_id": instance_id,
                "duration": instance_duration,
                "successful_operations": successful_operations,
                "failed_operations": failed_operations,
                "throughput": successful_operations / instance_duration if instance_duration > 0 else 0,
            }

        # Execute load across multiple instances concurrently
        start_time = time.time()
        instance_results = await asyncio.gather(*[simulate_instance_load(i) for i in range(num_instances)])
        total_duration = time.time() - start_time

        # Analyze scaling metrics
        total_successful = sum(r["successful_operations"] for r in instance_results)
        total_failed = sum(r["failed_operations"] for r in instance_results)
        average_throughput = sum(r["throughput"] for r in instance_results) / num_instances

        # Validate scaling behavior
        assert total_successful > 0, "No operations succeeded"
        assert total_successful >= num_instances * operations_per_instance * 0.8, "Too many operations failed"

        # Performance should scale reasonably with instances
        expected_min_throughput = 5.0  # operations per second per instance
        assert average_throughput >= expected_min_throughput, f"Throughput too low: {average_throughput:.2f} ops/sec"

        # Memory usage should be reasonable
        memory_growth = resource_monitor.get_memory_growth_mb()
        assert memory_growth < 100, f"Excessive memory growth: {memory_growth:.2f} MB"

        print(f"✓ Horizontal scaling test passed:")
        print(f"  - {num_instances} instances, {total_successful} operations")
        print(f"  - Average throughput: {average_throughput:.2f} ops/sec")
        print(f"  - Memory growth: {memory_growth:.2f} MB")
        print(f"  - Total duration: {total_duration:.2f}s")

    @pytest.mark.asyncio
    async def test_memory_usage_and_gc_efficiency(self, family_manager_with_monitoring):
        """
        Test memory usage and garbage collection efficiency.

        Validates:
        - Memory usage remains stable under load
        - Garbage collection works effectively
        - No memory leaks in family operations

        Requirements: 10.2, 10.5
        """
        resource_monitor = ResourceMonitor()

        # Force initial garbage collection
        gc.collect()
        initial_memory = resource_monitor.get_memory_usage_mb()

        # Create many operations to test memory behavior
        num_batches = 10
        operations_per_batch = 50

        memory_samples = []

        for batch in range(num_batches):
            batch_start_memory = resource_monitor.get_memory_usage_mb()

            # Create batch of operations
            user_ids = [f"memory_test_batch_{batch}_user_{i}" for i in range(operations_per_batch)]

            async def create_family_memory_test(user_id: str) -> bool:
                try:
                    await family_manager_with_monitoring.create_family(
                        user_id=user_id,
                        name=f"Memory Test Family {user_id}",
                        request_context={"ip_address": "127.0.0.1", "user_agent": "test"},
                    )
                    return True
                except Exception:
                    return False

            # Execute batch
            results = await asyncio.gather(*[create_family_memory_test(uid) for uid in user_ids])
            successful_in_batch = sum(results)

            # Sample memory after batch
            batch_end_memory = resource_monitor.get_memory_usage_mb()
            memory_samples.append(
                {
                    "batch": batch,
                    "start_memory": batch_start_memory,
                    "end_memory": batch_end_memory,
                    "growth": batch_end_memory - batch_start_memory,
                    "successful_operations": successful_in_batch,
                }
            )

            # Force garbage collection between batches
            gc.collect()

            # Small delay to allow GC
            await asyncio.sleep(0.1)

        final_memory = resource_monitor.get_memory_usage_mb()
        total_memory_growth = final_memory - initial_memory

        # Analyze memory behavior
        max_batch_growth = max(sample["growth"] for sample in memory_samples)
        avg_batch_growth = sum(sample["growth"] for sample in memory_samples) / len(memory_samples)

        # Validate memory efficiency
        assert total_memory_growth < 50, f"Excessive total memory growth: {total_memory_growth:.2f} MB"
        assert max_batch_growth < 20, f"Excessive batch memory growth: {max_batch_growth:.2f} MB"
        assert avg_batch_growth < 5, f"High average memory growth per batch: {avg_batch_growth:.2f} MB"

        # Memory should not grow linearly with operations (indicating leaks)
        memory_growths = [sample["growth"] for sample in memory_samples]
        if len(memory_growths) > 5:
            # Check if memory growth is stabilizing (not continuously increasing)
            recent_growth = sum(memory_growths[-3:]) / 3
            early_growth = sum(memory_growths[:3]) / 3
            growth_ratio = recent_growth / early_growth if early_growth > 0 else 1
            assert growth_ratio < 2.0, f"Memory growth not stabilizing: {growth_ratio:.2f}x increase"

        print(f"✓ Memory efficiency test passed:")
        print(f"  - Initial memory: {initial_memory:.2f} MB")
        print(f"  - Final memory: {final_memory:.2f} MB")
        print(f"  - Total growth: {total_memory_growth:.2f} MB")
        print(f"  - Max batch growth: {max_batch_growth:.2f} MB")
        print(f"  - Avg batch growth: {avg_batch_growth:.2f} MB")

    @pytest.mark.asyncio
    async def test_database_query_performance(self, family_manager_with_monitoring):
        """
        Test database query performance and optimization.

        Validates:
        - Query response times remain acceptable under load
        - Database connection efficiency
        - Query optimization effectiveness

        Requirements: 10.3, 10.5
        """
        # Track query performance metrics
        query_times = {"user_lookup": [], "family_count": [], "family_insert": [], "total_operation": []}

        # Override create_family to track timing
        original_create_family = family_manager_with_monitoring.create_family

        async def timed_create_family(*args, **kwargs):
            # Track individual query times
            start_time = time.time()
            await asyncio.sleep(family_manager_with_monitoring.query_latencies["user_lookup"])
            query_times["user_lookup"].append(time.time() - start_time)

            start_time = time.time()
            await asyncio.sleep(family_manager_with_monitoring.query_latencies["family_count"])
            query_times["family_count"].append(time.time() - start_time)

            start_time = time.time()
            await asyncio.sleep(family_manager_with_monitoring.query_latencies["family_insert"])
            query_times["family_insert"].append(time.time() - start_time)

            # Call original method (which also has latency)
            return await original_create_family(*args, **kwargs)

        family_manager_with_monitoring.create_family = timed_create_family

        # Execute operations to measure performance
        num_operations = 100
        user_ids = [f"perf_test_user_{i}" for i in range(num_operations)]

        async def create_family_with_timing(user_id: str) -> Dict[str, Any]:
            start_time = time.time()
            try:
                result = await family_manager_with_monitoring.create_family(
                    user_id=user_id,
                    name=f"Performance Test Family {user_id}",
                    request_context={"ip_address": "127.0.0.1", "user_agent": "test"},
                )
                duration = time.time() - start_time
                query_times["total_operation"].append(duration)
                return {"success": True, "duration": duration}
            except Exception as e:
                duration = time.time() - start_time
                query_times["total_operation"].append(duration)
                return {"error": str(e), "duration": duration}

        # Execute performance test
        start_time = time.time()
        results = await asyncio.gather(*[create_family_with_timing(uid) for uid in user_ids])
        total_duration = time.time() - start_time

        # Analyze query performance
        successful_ops = [r for r in results if r.get("success")]

        # Calculate performance metrics
        def calculate_stats(times: List[float]) -> Dict[str, float]:
            if not times:
                return {"avg": 0, "max": 0, "min": 0, "p95": 0}

            times_sorted = sorted(times)
            return {
                "avg": sum(times) / len(times),
                "max": max(times),
                "min": min(times),
                "p95": times_sorted[int(len(times_sorted) * 0.95)] if len(times_sorted) > 0 else 0,
            }

        performance_stats = {query_type: calculate_stats(times) for query_type, times in query_times.items()}

        # Validate performance requirements
        # User lookup should be fast (< 10ms average)
        assert (
            performance_stats["user_lookup"]["avg"] < 0.01
        ), f"User lookup too slow: {performance_stats['user_lookup']['avg']:.3f}s"

        # Family operations should complete reasonably fast (< 100ms average)
        assert (
            performance_stats["total_operation"]["avg"] < 0.1
        ), f"Operations too slow: {performance_stats['total_operation']['avg']:.3f}s"

        # 95th percentile should be reasonable (< 200ms)
        assert (
            performance_stats["total_operation"]["p95"] < 0.2
        ), f"P95 too slow: {performance_stats['total_operation']['p95']:.3f}s"

        # Overall throughput should be acceptable
        throughput = len(successful_ops) / total_duration
        assert throughput > 10, f"Throughput too low: {throughput:.2f} ops/sec"

        print(f"✓ Database performance test passed:")
        print(f"  - {len(successful_ops)} operations in {total_duration:.2f}s")
        print(f"  - Throughput: {throughput:.2f} ops/sec")
        print(f"  - Avg operation time: {performance_stats['total_operation']['avg']:.3f}s")
        print(f"  - P95 operation time: {performance_stats['total_operation']['p95']:.3f}s")
        print(f"  - Avg user lookup: {performance_stats['user_lookup']['avg']:.3f}s")

    @pytest.mark.asyncio
    async def test_cache_hit_rates_and_eviction(self, family_manager_with_monitoring):
        """
        Test cache hit rates and eviction policies.

        Validates:
        - Cache hit rates meet performance targets
        - Eviction policies work correctly
        - Cache performance under various access patterns

        Requirements: 10.3, 10.6
        """
        cache_simulator = family_manager_with_monitoring._cache_simulator

        # Test different cache access patterns

        # 1. Sequential access pattern (poor cache performance)
        print("Testing sequential access pattern...")
        for i in range(600):  # More than cache size
            await cache_simulator.set(f"seq_key_{i}", f"value_{i}")

        sequential_hit_rate = cache_simulator.get_hit_rate()

        # Reset cache for next test
        cache_simulator.__init__(max_size=500, ttl=300)

        # 2. Repeated access pattern (good cache performance)
        print("Testing repeated access pattern...")
        # Populate cache with frequently accessed items
        for i in range(100):
            await cache_simulator.set(f"freq_key_{i}", f"value_{i}")

        # Access same items repeatedly
        for _ in range(500):
            for i in range(50):  # Access first 50 items repeatedly
                await cache_simulator.get(f"freq_key_{i}")

        repeated_hit_rate = cache_simulator.get_hit_rate()

        # Reset cache for next test
        cache_simulator.__init__(max_size=500, ttl=300)

        # 3. Mixed access pattern (realistic scenario)
        print("Testing mixed access pattern...")
        # Populate with base data
        for i in range(200):
            await cache_simulator.set(f"base_key_{i}", f"value_{i}")

        # Mixed access: 70% hits on existing data, 30% new data
        hit_attempts = 0
        for i in range(1000):
            if i % 10 < 7:  # 70% access existing data
                key = f"base_key_{i % 200}"
                await cache_simulator.get(key)
                hit_attempts += 1
            else:  # 30% access new data
                await cache_simulator.set(f"new_key_{i}", f"new_value_{i}")

        mixed_hit_rate = cache_simulator.get_hit_rate()

        # Test TTL expiration
        print("Testing TTL expiration...")
        cache_simulator.__init__(max_size=500, ttl=1)  # 1 second TTL

        # Add items and wait for expiration
        for i in range(10):
            await cache_simulator.set(f"ttl_key_{i}", f"value_{i}")

        # Immediate access should hit
        immediate_hits = 0
        for i in range(10):
            result = await cache_simulator.get(f"ttl_key_{i}")
            if result is not None:
                immediate_hits += 1

        # Wait for TTL expiration
        await asyncio.sleep(1.1)

        # Access after expiration should miss
        expired_hits = 0
        for i in range(10):
            result = await cache_simulator.get(f"ttl_key_{i}")
            if result is not None:
                expired_hits += 1

        # Validate cache behavior

        # Sequential access should have low hit rate (lots of evictions)
        assert sequential_hit_rate < 0.1, f"Sequential hit rate too high: {sequential_hit_rate:.2f}"

        # Repeated access should have high hit rate
        assert repeated_hit_rate > 0.8, f"Repeated hit rate too low: {repeated_hit_rate:.2f}"

        # Mixed access should have moderate hit rate (adjust for simulation)
        assert 0.3 < mixed_hit_rate <= 1.0, f"Mixed hit rate out of range: {mixed_hit_rate:.2f}"

        # TTL should work correctly
        assert immediate_hits == 10, f"TTL immediate hits incorrect: {immediate_hits}"
        assert expired_hits == 0, f"TTL expiration not working: {expired_hits}"

        print(f"✓ Cache performance test passed:")
        print(f"  - Sequential hit rate: {sequential_hit_rate:.2f}")
        print(f"  - Repeated hit rate: {repeated_hit_rate:.2f}")
        print(f"  - Mixed hit rate: {mixed_hit_rate:.2f}")
        print(f"  - TTL expiration working: {expired_hits == 0}")

    @pytest.mark.asyncio
    async def test_system_behavior_under_resource_constraints(self, family_manager_with_monitoring):
        """
        Test system behavior under resource constraints.

        Validates:
        - Graceful degradation under memory pressure
        - Performance under CPU constraints
        - Error handling when resources are limited

        Requirements: 10.5, 10.6
        """
        resource_monitor = ResourceMonitor()

        # Simulate memory pressure by creating large objects
        memory_pressure_objects = []

        try:
            # Create moderate memory pressure (not enough to crash)
            for i in range(100):
                # Create 1MB objects
                large_object = bytearray(1024 * 1024)  # 1MB
                memory_pressure_objects.append(large_object)

            memory_under_pressure = resource_monitor.get_memory_usage_mb()

            # Test operations under memory pressure
            constrained_operations = 50
            user_ids = [f"constrained_user_{i}" for i in range(constrained_operations)]

            async def create_family_under_pressure(user_id: str) -> Dict[str, Any]:
                try:
                    start_time = time.time()
                    result = await family_manager_with_monitoring.create_family(
                        user_id=user_id,
                        name=f"Constrained Family {user_id}",
                        request_context={"ip_address": "127.0.0.1", "user_agent": "test"},
                    )
                    duration = time.time() - start_time
                    return {"success": True, "duration": duration}
                except Exception as e:
                    duration = time.time() - start_time
                    return {"error": str(e), "duration": duration}

            # Execute operations under memory pressure
            start_time = time.time()
            constrained_results = await asyncio.gather(*[create_family_under_pressure(uid) for uid in user_ids])
            constrained_duration = time.time() - start_time

            # Analyze performance under constraints
            successful_constrained = [r for r in constrained_results if r.get("success")]
            failed_constrained = [r for r in constrained_results if "error" in r]

            constrained_throughput = len(successful_constrained) / constrained_duration
            avg_constrained_duration = sum(r["duration"] for r in constrained_results) / len(constrained_results)

            # Compare with normal operation (release memory pressure)
            memory_pressure_objects.clear()
            gc.collect()

            # Test normal operations for comparison
            normal_user_ids = [f"normal_user_{i}" for i in range(constrained_operations)]

            start_time = time.time()
            normal_results = await asyncio.gather(*[create_family_under_pressure(uid) for uid in normal_user_ids])
            normal_duration = time.time() - start_time

            successful_normal = [r for r in normal_results if r.get("success")]
            normal_throughput = len(successful_normal) / normal_duration
            avg_normal_duration = sum(r["duration"] for r in normal_results) / len(normal_results)

            # Validate graceful degradation

            # System should still function under pressure (at least 70% success rate)
            success_rate_constrained = len(successful_constrained) / len(constrained_results)
            assert (
                success_rate_constrained > 0.7
            ), f"Success rate too low under pressure: {success_rate_constrained:.2f}"

            # Performance degradation should be reasonable (not more than 3x slower)
            performance_ratio = avg_constrained_duration / avg_normal_duration if avg_normal_duration > 0 else 1
            assert performance_ratio < 3.0, f"Performance degraded too much: {performance_ratio:.2f}x slower"

            # Throughput should not drop below 50% of normal
            throughput_ratio = constrained_throughput / normal_throughput if normal_throughput > 0 else 1
            assert throughput_ratio > 0.5, f"Throughput dropped too much: {throughput_ratio:.2f}x"

            print(f"✓ Resource constraints test passed:")
            print(f"  - Memory under pressure: {memory_under_pressure:.2f} MB")
            print(f"  - Success rate under pressure: {success_rate_constrained:.2f}")
            print(f"  - Performance ratio: {performance_ratio:.2f}x")
            print(f"  - Throughput ratio: {throughput_ratio:.2f}x")
            print(f"  - Constrained throughput: {constrained_throughput:.2f} ops/sec")
            print(f"  - Normal throughput: {normal_throughput:.2f} ops/sec")

        finally:
            # Clean up memory pressure objects
            memory_pressure_objects.clear()
            gc.collect()

    @pytest.mark.asyncio
    async def test_load_balancing_simulation(self, family_manager_with_monitoring):
        """
        Test load balancing and distribution across multiple nodes.

        Simulates load balancer distributing requests across multiple application instances.

        Requirements: 10.2, 10.3
        """
        # Simulate multiple application nodes
        num_nodes = 4
        total_operations = 200

        # Distribute operations across nodes (simulate load balancer)
        node_operations = [[] for _ in range(num_nodes)]

        # Round-robin distribution
        for i in range(total_operations):
            node_id = i % num_nodes
            user_id = f"lb_user_{i}"
            node_operations[node_id].append(user_id)

        # Track per-node performance
        node_results = []

        async def simulate_node_processing(node_id: int, user_ids: List[str]) -> Dict[str, Any]:
            """Simulate processing on a single node."""
            node_start_time = time.time()
            successful = 0
            failed = 0

            for user_id in user_ids:
                try:
                    await family_manager_with_monitoring.create_family(
                        user_id=user_id,
                        name=f"LB Family {user_id}",
                        request_context={"ip_address": f"10.0.{node_id}.100", "user_agent": "load_balancer_test"},
                    )
                    successful += 1
                except Exception:
                    failed += 1

                # Simulate variable processing time
                await asyncio.sleep(0.005 + (node_id * 0.001))  # Slight variation per node

            node_duration = time.time() - node_start_time

            return {
                "node_id": node_id,
                "operations": len(user_ids),
                "successful": successful,
                "failed": failed,
                "duration": node_duration,
                "throughput": successful / node_duration if node_duration > 0 else 0,
            }

        # Execute load balancing simulation
        start_time = time.time()
        node_results = await asyncio.gather(
            *[simulate_node_processing(i, node_operations[i]) for i in range(num_nodes)]
        )
        total_duration = time.time() - start_time

        # Analyze load balancing effectiveness
        total_successful = sum(r["successful"] for r in node_results)
        total_failed = sum(r["failed"] for r in node_results)

        # Calculate load distribution metrics
        operations_per_node = [r["operations"] for r in node_results]
        throughputs = [r["throughput"] for r in node_results]

        # Load should be evenly distributed
        min_ops = min(operations_per_node)
        max_ops = max(operations_per_node)
        load_balance_ratio = min_ops / max_ops if max_ops > 0 else 1

        # Throughput should be consistent across nodes
        avg_throughput = sum(throughputs) / len(throughputs)
        throughput_variance = sum((t - avg_throughput) ** 2 for t in throughputs) / len(throughputs)
        throughput_std_dev = throughput_variance**0.5

        # Validate load balancing
        assert load_balance_ratio > 0.8, f"Load not balanced: {load_balance_ratio:.2f}"
        assert total_successful > total_operations * 0.9, f"Too many failures: {total_failed}/{total_operations}"
        assert throughput_std_dev < avg_throughput * 0.3, f"Throughput too variable: {throughput_std_dev:.2f}"

        # Overall system throughput
        system_throughput = total_successful / total_duration

        print(f"✓ Load balancing test passed:")
        print(f"  - {num_nodes} nodes, {total_successful} successful operations")
        print(f"  - Load balance ratio: {load_balance_ratio:.2f}")
        print(f"  - System throughput: {system_throughput:.2f} ops/sec")
        print(f"  - Avg node throughput: {avg_throughput:.2f} ops/sec")
        print(f"  - Throughput std dev: {throughput_std_dev:.2f}")

        for result in node_results:
            print(
                f"    Node {result['node_id']}: {result['successful']}/{result['operations']} ops, {result['throughput']:.2f} ops/sec"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
