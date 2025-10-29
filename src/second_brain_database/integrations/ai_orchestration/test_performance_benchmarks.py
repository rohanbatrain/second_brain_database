"""
Performance Benchmark Tests

This module provides comprehensive tests for the AI performance benchmarking system
to ensure sub-300ms response times are met and properly measured.
"""

import pytest
import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from .performance_benchmarks import (
    PerformanceBenchmarkSuite,
    BenchmarkResult,
    BenchmarkSuite,
    PerformanceMetrics,
    run_performance_benchmarks,
    get_current_performance_metrics
)
from ...config import settings


class TestBenchmarkResult:
    """Test BenchmarkResult dataclass."""
    
    def test_benchmark_result_creation(self):
        """Test creating a benchmark result."""
        result = BenchmarkResult(
            test_name="test_operation",
            operation_type="model_response",
            response_time_ms=150.5,
            success=True
        )
        
        assert result.test_name == "test_operation"
        assert result.operation_type == "model_response"
        assert result.response_time_ms == 150.5
        assert result.success is True
        assert result.error_message is None
        assert isinstance(result.timestamp, datetime)


class TestBenchmarkSuite:
    """Test BenchmarkSuite dataclass."""
    
    def test_benchmark_suite_creation(self):
        """Test creating a benchmark suite."""
        suite = BenchmarkSuite(
            suite_name="Test Suite",
            target_latency_ms=300.0
        )
        
        assert suite.suite_name == "Test Suite"
        assert suite.target_latency_ms == 300.0
        assert len(suite.results) == 0
        assert isinstance(suite.started_at, datetime)
        assert suite.completed_at is None
    
    def test_suite_metrics_calculation(self):
        """Test suite metrics calculation."""
        suite = BenchmarkSuite(
            suite_name="Test Suite",
            target_latency_ms=300.0
        )
        
        # Add test results
        suite.results = [
            BenchmarkResult("test1", "op1", 100.0, True),
            BenchmarkResult("test2", "op1", 200.0, True),
            BenchmarkResult("test3", "op1", 150.0, True),
            BenchmarkResult("test4", "op1", 0.0, False),  # Failed test
        ]
        
        suite.completed_at = datetime.now(timezone.utc)
        
        # Test metrics
        assert suite.success_rate == 75.0  # 3 out of 4 successful
        assert suite.average_response_time == 150.0  # (100 + 200 + 150) / 3
        assert suite.meets_target is True  # 150 < 300
        assert suite.duration_ms > 0
    
    def test_p95_calculation(self):
        """Test 95th percentile calculation."""
        suite = BenchmarkSuite(
            suite_name="Test Suite",
            target_latency_ms=300.0
        )
        
        # Add many results for percentile calculation
        response_times = [i * 10 for i in range(1, 21)]  # 10, 20, 30, ..., 200
        suite.results = [
            BenchmarkResult(f"test{i}", "op1", time_ms, True)
            for i, time_ms in enumerate(response_times)
        ]
        
        p95 = suite.p95_response_time
        assert p95 > 0
        assert p95 <= max(response_times)


class TestPerformanceMetrics:
    """Test PerformanceMetrics class."""
    
    def test_metrics_recording(self):
        """Test recording operation metrics."""
        metrics = PerformanceMetrics()
        
        # Record some operations
        metrics.record_operation("model_response", 150.0, True)
        metrics.record_operation("model_response", 200.0, True)
        metrics.record_operation("model_response", 0.0, False)
        
        assert metrics.operation_counts["model_response"] == 3
        assert metrics.error_counts["model_response"] == 1
        assert len(metrics.response_times["model_response"]) == 2  # Only successful ones
    
    def test_average_response_time(self):
        """Test average response time calculation."""
        metrics = PerformanceMetrics()
        
        metrics.record_operation("test_op", 100.0, True)
        metrics.record_operation("test_op", 200.0, True)
        metrics.record_operation("test_op", 300.0, True)
        
        avg_time = metrics.get_average_response_time("test_op")
        assert avg_time == 200.0
    
    def test_error_rate_calculation(self):
        """Test error rate calculation."""
        metrics = PerformanceMetrics()
        
        # Record 8 successful and 2 failed operations
        for _ in range(8):
            metrics.record_operation("test_op", 150.0, True)
        for _ in range(2):
            metrics.record_operation("test_op", 0.0, False)
        
        error_rate = metrics.get_error_rate("test_op")
        assert error_rate == 20.0  # 2 out of 10 = 20%


class TestPerformanceBenchmarkSuite:
    """Test PerformanceBenchmarkSuite class."""
    
    @pytest.fixture
    def benchmark_suite(self):
        """Create a benchmark suite for testing."""
        suite = PerformanceBenchmarkSuite()
        suite.test_iterations = 2  # Reduce for faster tests
        suite.concurrent_tests = 2
        suite.warmup_iterations = 1
        return suite
    
    @pytest.mark.asyncio
    async def test_component_initialization(self, benchmark_suite):
        """Test component initialization."""
        with patch('src.second_brain_database.integrations.ai_orchestration.performance_benchmarks.ModelEngine') as mock_model:
            with patch('src.second_brain_database.integrations.ai_orchestration.performance_benchmarks.MemoryLayer') as mock_memory:
                mock_model.return_value = MagicMock()
                mock_memory.return_value = MagicMock()
                
                await benchmark_suite.initialize_components()
                
                assert benchmark_suite.model_engine is not None
                assert benchmark_suite.memory_layer is not None
    
    @pytest.mark.asyncio
    async def test_warmup_tests(self, benchmark_suite):
        """Test warmup test execution."""
        # Mock components
        mock_model_engine = AsyncMock()
        mock_model_engine.generate_response = AsyncMock()
        mock_model_engine.generate_response.return_value = iter(["test response"])
        
        mock_memory_layer = AsyncMock()
        mock_memory_layer.load_user_context = AsyncMock(return_value=None)
        
        benchmark_suite.model_engine = mock_model_engine
        benchmark_suite.memory_layer = mock_memory_layer
        
        await benchmark_suite._run_warmup_tests()
        
        # Verify warmup calls were made
        assert mock_model_engine.generate_response.call_count == benchmark_suite.warmup_iterations
        assert mock_memory_layer.load_user_context.called
    
    @pytest.mark.asyncio
    async def test_model_response_benchmark(self, benchmark_suite):
        """Test model response benchmarking."""
        # Mock model engine
        mock_model_engine = AsyncMock()
        
        async def mock_generate_response(*args, **kwargs):
            await asyncio.sleep(0.01)  # Simulate processing time
            yield "test response"
        
        mock_model_engine.generate_response = mock_generate_response
        benchmark_suite.model_engine = mock_model_engine
        
        results = await benchmark_suite._benchmark_model_response()
        
        assert len(results) > 0
        assert all(isinstance(r, BenchmarkResult) for r in results)
        assert all(r.operation_type == "model_response" for r in results)
        assert all(r.response_time_ms > 0 for r in results if r.success)
    
    @pytest.mark.asyncio
    async def test_cached_response_benchmark(self, benchmark_suite):
        """Test cached response benchmarking."""
        # Mock model engine with cache simulation
        mock_model_engine = AsyncMock()
        
        call_count = 0
        async def mock_generate_response(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call - populate cache
                await asyncio.sleep(0.05)
            else:
                # Subsequent calls - fast cache retrieval
                await asyncio.sleep(0.001)
            yield "cached response"
        
        mock_model_engine.generate_response = mock_generate_response
        benchmark_suite.model_engine = mock_model_engine
        
        results = await benchmark_suite._benchmark_cached_response()
        
        assert len(results) > 0
        assert all(isinstance(r, BenchmarkResult) for r in results)
        assert all(r.operation_type == "cached_response" for r in results)
        
        # Cached responses should be faster than initial response
        successful_results = [r for r in results if r.success]
        if len(successful_results) > 1:
            # Most cached responses should be faster
            fast_responses = [r for r in successful_results if r.response_time_ms < 10]
            assert len(fast_responses) > 0
    
    @pytest.mark.asyncio
    async def test_context_loading_benchmark(self, benchmark_suite):
        """Test context loading benchmarking."""
        # Mock memory layer
        mock_memory_layer = AsyncMock()
        mock_memory_layer.load_user_context = AsyncMock()
        
        async def mock_load_context(user_id):
            await asyncio.sleep(0.01)  # Simulate loading time
            return None  # Can return None for non-existent users
        
        mock_memory_layer.load_user_context = mock_load_context
        benchmark_suite.memory_layer = mock_memory_layer
        
        results = await benchmark_suite._benchmark_context_loading()
        
        assert len(results) > 0
        assert all(isinstance(r, BenchmarkResult) for r in results)
        assert all(r.operation_type == "context_loading" for r in results)
        assert all(r.response_time_ms > 0 for r in results)
    
    @pytest.mark.asyncio
    async def test_conversation_storage_benchmark(self, benchmark_suite):
        """Test conversation storage benchmarking."""
        # Mock memory layer
        mock_memory_layer = AsyncMock()
        
        async def mock_store_message(*args, **kwargs):
            await asyncio.sleep(0.01)  # Simulate storage time
            return True
        
        mock_memory_layer.store_conversation_message = mock_store_message
        benchmark_suite.memory_layer = mock_memory_layer
        
        results = await benchmark_suite._benchmark_conversation_storage()
        
        assert len(results) > 0
        assert all(isinstance(r, BenchmarkResult) for r in results)
        assert all(r.operation_type == "conversation_storage" for r in results)
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_concurrent_operations_benchmark(self, benchmark_suite):
        """Test concurrent operations benchmarking."""
        # Mock model engine
        mock_model_engine = AsyncMock()
        
        async def mock_generate_response(*args, **kwargs):
            await asyncio.sleep(0.02)  # Simulate processing time
            yield f"response for {args[0]}"
        
        mock_model_engine.generate_response = mock_generate_response
        benchmark_suite.model_engine = mock_model_engine
        
        results = await benchmark_suite._benchmark_concurrent_operations()
        
        assert len(results) > 0
        assert all(isinstance(r, BenchmarkResult) for r in results)
        assert all(r.operation_type == "concurrent_operation" for r in results)
        
        # Check that concurrent operations were actually run
        successful_results = [r for r in results if r.success]
        assert len(successful_results) > 0
    
    @pytest.mark.asyncio
    async def test_health_check_benchmark(self, benchmark_suite):
        """Test health check benchmarking."""
        # Mock model engine
        mock_model_engine = AsyncMock()
        
        async def mock_health_check():
            await asyncio.sleep(0.005)  # Simulate health check time
            return {"status": "healthy"}
        
        mock_model_engine.health_check = mock_health_check
        benchmark_suite.model_engine = mock_model_engine
        
        results = await benchmark_suite._benchmark_health_checks()
        
        assert len(results) > 0
        assert all(isinstance(r, BenchmarkResult) for r in results)
        assert all(r.operation_type == "health_check" for r in results)
        assert all(r.success for r in results)
    
    @pytest.mark.asyncio
    async def test_full_benchmark_suite(self, benchmark_suite):
        """Test running the full benchmark suite."""
        # Mock all components
        mock_model_engine = AsyncMock()
        mock_model_engine.generate_response = AsyncMock()
        mock_model_engine.generate_response.return_value = iter(["test response"])
        mock_model_engine.health_check = AsyncMock(return_value={"status": "healthy"})
        
        mock_memory_layer = AsyncMock()
        mock_memory_layer.load_user_context = AsyncMock(return_value=None)
        mock_memory_layer.store_conversation_message = AsyncMock(return_value=True)
        mock_memory_layer.search_knowledge = AsyncMock(return_value=[])
        
        benchmark_suite.model_engine = mock_model_engine
        benchmark_suite.memory_layer = mock_memory_layer
        
        # Mock Redis for result storage
        with patch('src.second_brain_database.integrations.ai_orchestration.performance_benchmarks.redis_manager') as mock_redis_manager:
            mock_redis = AsyncMock()
            mock_redis_manager.get_redis.return_value = mock_redis
            
            suite_result = await benchmark_suite.run_full_benchmark_suite()
            
            assert isinstance(suite_result, BenchmarkSuite)
            assert suite_result.suite_name == "AI Performance Benchmark Suite"
            assert suite_result.target_latency_ms == settings.AI_RESPONSE_TARGET_LATENCY
            assert len(suite_result.results) > 0
            assert suite_result.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_performance_metrics_collection(self, benchmark_suite):
        """Test performance metrics collection."""
        # Add some test data to metrics
        benchmark_suite.metrics.record_operation("test_op", 150.0, True)
        benchmark_suite.metrics.record_operation("test_op", 200.0, True)
        benchmark_suite.metrics.record_operation("test_op", 0.0, False)
        
        metrics = await benchmark_suite.get_performance_metrics()
        
        assert "operation_counts" in metrics
        assert "error_counts" in metrics
        assert "average_response_times" in metrics
        assert "error_rates" in metrics
        assert "last_updated" in metrics
        
        assert metrics["operation_counts"]["test_op"] == 3
        assert metrics["error_counts"]["test_op"] == 1
        assert metrics["average_response_times"]["test_op"] == 175.0  # (150 + 200) / 2
        assert abs(metrics["error_rates"]["test_op"] - 33.33) < 0.1  # 1/3 ≈ 33.33%


class TestBenchmarkIntegration:
    """Test benchmark integration functions."""
    
    @pytest.mark.asyncio
    async def test_run_performance_benchmarks(self):
        """Test the main benchmark runner function."""
        with patch('src.second_brain_database.integrations.ai_orchestration.performance_benchmarks.PerformanceBenchmarkSuite') as mock_suite_class:
            mock_suite = AsyncMock()
            mock_suite.run_full_benchmark_suite = AsyncMock()
            mock_suite.run_full_benchmark_suite.return_value = BenchmarkSuite(
                suite_name="Test Suite",
                target_latency_ms=300.0
            )
            mock_suite_class.return_value = mock_suite
            
            result = await run_performance_benchmarks()
            
            assert isinstance(result, BenchmarkSuite)
            assert mock_suite.run_full_benchmark_suite.called
    
    @pytest.mark.asyncio
    async def test_get_current_performance_metrics(self):
        """Test getting current performance metrics."""
        with patch('src.second_brain_database.integrations.ai_orchestration.performance_benchmarks.PerformanceBenchmarkSuite') as mock_suite_class:
            mock_suite = AsyncMock()
            mock_suite.get_performance_metrics = AsyncMock()
            mock_suite.get_performance_metrics.return_value = {
                "operation_counts": {"test_op": 5},
                "error_counts": {"test_op": 1},
                "average_response_times": {"test_op": 150.0},
                "error_rates": {"test_op": 20.0}
            }
            mock_suite_class.return_value = mock_suite
            
            metrics = await get_current_performance_metrics()
            
            assert "operation_counts" in metrics
            assert "error_counts" in metrics
            assert "average_response_times" in metrics
            assert "error_rates" in metrics


class TestPerformanceTargets:
    """Test performance target validation."""
    
    def test_target_latency_configuration(self):
        """Test that target latency is properly configured."""
        # Verify the target latency is set to 300ms as required
        assert settings.AI_RESPONSE_TARGET_LATENCY == 300
    
    def test_benchmark_meets_target_validation(self):
        """Test benchmark target validation logic."""
        suite = BenchmarkSuite(
            suite_name="Target Test",
            target_latency_ms=300.0
        )
        
        # Test case: meets target
        suite.results = [
            BenchmarkResult("test1", "op1", 250.0, True),
            BenchmarkResult("test2", "op1", 280.0, True),
            BenchmarkResult("test3", "op1", 290.0, True),
        ]
        assert suite.meets_target is True
        
        # Test case: exceeds target
        suite.results = [
            BenchmarkResult("test1", "op1", 350.0, True),
            BenchmarkResult("test2", "op1", 320.0, True),
            BenchmarkResult("test3", "op1", 310.0, True),
        ]
        assert suite.meets_target is False
    
    def test_performance_regression_detection(self):
        """Test performance regression detection."""
        # This would be used in continuous monitoring
        baseline_avg = 200.0
        current_avg = 350.0
        
        # Simple regression detection logic
        regression_threshold = 1.5  # 50% increase
        has_regression = current_avg > baseline_avg * regression_threshold
        
        assert has_regression is True
        
        # Test no regression case
        current_avg = 220.0
        has_regression = current_avg > baseline_avg * regression_threshold
        
        assert has_regression is False


if __name__ == "__main__":
    # Run a quick benchmark test
    async def quick_test():
        suite = PerformanceBenchmarkSuite()
        suite.test_iterations = 1
        suite.concurrent_tests = 1
        suite.warmup_iterations = 0
        
        print("Running quick performance benchmark test...")
        
        # Mock components for testing
        from unittest.mock import AsyncMock, MagicMock
        
        mock_model_engine = AsyncMock()
        async def mock_generate(*args, **kwargs):
            await asyncio.sleep(0.01)
            yield "test response"
        mock_model_engine.generate_response = mock_generate
        mock_model_engine.health_check = AsyncMock(return_value={"status": "healthy"})
        
        mock_memory_layer = AsyncMock()
        mock_memory_layer.load_user_context = AsyncMock(return_value=None)
        mock_memory_layer.store_conversation_message = AsyncMock(return_value=True)
        mock_memory_layer.search_knowledge = AsyncMock(return_value=[])
        
        suite.model_engine = mock_model_engine
        suite.memory_layer = mock_memory_layer
        
        # Run a subset of benchmarks
        results = []
        results.extend(await suite._benchmark_model_response())
        results.extend(await suite._benchmark_health_checks())
        
        print(f"Completed {len(results)} benchmark tests")
        successful = [r for r in results if r.success]
        if successful:
            avg_time = sum(r.response_time_ms for r in successful) / len(successful)
            print(f"Average response time: {avg_time:.2f}ms")
            print(f"Target: {suite.target_latency_ms}ms")
            print(f"Meets target: {'✅ YES' if avg_time <= suite.target_latency_ms else '❌ NO'}")
        
        print("Quick test completed!")
    
    asyncio.run(quick_test())