"""
AI Performance Benchmarking System

This module provides comprehensive performance benchmarking for AI operations
to ensure sub-300ms response times and optimal system performance.

Features:
- Response time benchmarking for all AI operations
- Latency measurement and analysis
- Performance regression detection
- Automated performance testing
- Real-time performance monitoring
- Performance optimization recommendations
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
import asyncio
import time
import statistics
import json
from collections import defaultdict, deque

from ...managers.redis_manager import redis_manager
from ...managers.logging_manager import get_logger
from ...config import settings
from .model_engine import ModelEngine
from .orchestrator import AgentOrchestrator
from .memory_layer import MemoryLayer
from ...integrations.mcp.context import MCPUserContext

logger = get_logger(prefix="[PerformanceBenchmarks]")


@dataclass
class BenchmarkResult:
    """Individual benchmark test result."""
    test_name: str
    operation_type: str
    response_time_ms: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results."""
    suite_name: str
    target_latency_ms: float
    results: List[BenchmarkResult] = field(default_factory=list)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    
    @property
    def duration_ms(self) -> float:
        """Calculate total benchmark duration."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if not self.results:
            return 0.0
        successful = sum(1 for r in self.results if r.success)
        return (successful / len(self.results)) * 100
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        if not self.results:
            return 0.0
        successful_results = [r for r in self.results if r.success]
        if not successful_results:
            return 0.0
        return statistics.mean(r.response_time_ms for r in successful_results)
    
    @property
    def p95_response_time(self) -> float:
        """Calculate 95th percentile response time."""
        if not self.results:
            return 0.0
        successful_results = [r for r in self.results if r.success]
        if not successful_results:
            return 0.0
        times = [r.response_time_ms for r in successful_results]
        return statistics.quantiles(times, n=20)[18]  # 95th percentile
    
    @property
    def meets_target(self) -> bool:
        """Check if benchmark meets target latency."""
        return self.average_response_time <= self.target_latency_ms


@dataclass
class PerformanceMetrics:
    """Real-time performance metrics."""
    operation_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    response_times: Dict[str, deque] = field(default_factory=lambda: defaultdict(lambda: deque(maxlen=100)))
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def record_operation(self, operation_type: str, response_time_ms: float, success: bool):
        """Record an operation result."""
        self.operation_counts[operation_type] += 1
        if success:
            self.response_times[operation_type].append(response_time_ms)
        else:
            self.error_counts[operation_type] += 1
        self.last_updated = datetime.now(timezone.utc)
    
    def get_average_response_time(self, operation_type: str) -> float:
        """Get average response time for operation type."""
        times = self.response_times.get(operation_type, deque())
        if not times:
            return 0.0
        return statistics.mean(times)
    
    def get_error_rate(self, operation_type: str) -> float:
        """Get error rate percentage for operation type."""
        total = self.operation_counts.get(operation_type, 0)
        errors = self.error_counts.get(operation_type, 0)
        if total == 0:
            return 0.0
        return (errors / total) * 100


class PerformanceBenchmarkSuite:
    """
    Comprehensive performance benchmarking suite for AI operations.
    
    Tests all critical AI operations to ensure they meet sub-300ms response time targets.
    """
    
    def __init__(self):
        """Initialize the performance benchmark suite."""
        self.logger = get_logger(prefix="[PerformanceBenchmarks]")
        self.target_latency_ms = settings.AI_RESPONSE_TARGET_LATENCY
        self.metrics = PerformanceMetrics()
        
        # Initialize components for testing
        self.model_engine = None
        self.orchestrator = None
        self.memory_layer = None
        
        # Test configuration
        self.test_iterations = 10
        self.concurrent_tests = 5
        self.warmup_iterations = 3
    
    async def initialize_components(self):
        """Initialize AI components for testing."""
        try:
            self.model_engine = ModelEngine()
            self.memory_layer = MemoryLayer()
            # Note: We'll create a minimal orchestrator for testing
            # to avoid circular dependencies
            
            self.logger.info("Performance benchmark components initialized")
            
        except Exception as e:
            self.logger.error("Failed to initialize benchmark components: %s", e)
            raise
    
    async def run_full_benchmark_suite(self) -> BenchmarkSuite:
        """
        Run the complete performance benchmark suite.
        
        Returns:
            BenchmarkSuite with all test results
        """
        suite = BenchmarkSuite(
            suite_name="AI Performance Benchmark Suite",
            target_latency_ms=self.target_latency_ms
        )
        
        try:
            await self.initialize_components()
            
            # Run warmup iterations
            await self._run_warmup_tests()
            
            # Run core benchmark tests
            benchmark_tests = [
                self._benchmark_model_response,
                self._benchmark_cached_response,
                self._benchmark_context_loading,
                self._benchmark_conversation_storage,
                self._benchmark_agent_routing,
                self._benchmark_concurrent_operations,
                self._benchmark_memory_operations,
                self._benchmark_health_checks
            ]
            
            for test_func in benchmark_tests:
                try:
                    results = await test_func()
                    suite.results.extend(results)
                    
                except Exception as e:
                    self.logger.error("Benchmark test failed: %s - %s", test_func.__name__, e)
                    # Add failed test result
                    suite.results.append(BenchmarkResult(
                        test_name=test_func.__name__,
                        operation_type="benchmark_test",
                        response_time_ms=0.0,
                        success=False,
                        error_message=str(e)
                    ))
            
            suite.completed_at = datetime.now(timezone.utc)
            
            # Log benchmark summary
            self._log_benchmark_summary(suite)
            
            # Store benchmark results
            await self._store_benchmark_results(suite)
            
            return suite
            
        except Exception as e:
            self.logger.error("Benchmark suite execution failed: %s", e)
            suite.completed_at = datetime.now(timezone.utc)
            return suite
    
    async def _run_warmup_tests(self):
        """Run warmup tests to prepare components."""
        self.logger.info("Running warmup tests...")
        
        try:
            # Warm up model engine
            if self.model_engine:
                for _ in range(self.warmup_iterations):
                    async for _ in self.model_engine.generate_response(
                        "Hello, this is a warmup test.",
                        use_cache=False,
                        stream=False
                    ):
                        pass
            
            # Warm up memory layer
            if self.memory_layer:
                test_user_id = "benchmark_user"
                await self.memory_layer.load_user_context(test_user_id)
            
            self.logger.info("Warmup tests completed")
            
        except Exception as e:
            self.logger.warning("Warmup tests failed: %s", e)
    
    async def _benchmark_model_response(self) -> List[BenchmarkResult]:
        """Benchmark model response generation."""
        results = []
        test_prompts = [
            "Hello, how are you?",
            "What is the weather like today?",
            "Can you help me with a task?",
            "Tell me about artificial intelligence.",
            "What are your capabilities?"
        ]
        
        for i, prompt in enumerate(test_prompts):
            for iteration in range(self.test_iterations):
                start_time = time.time()
                success = False
                error_message = None
                
                try:
                    response_received = False
                    async for response in self.model_engine.generate_response(
                        prompt,
                        use_cache=False,
                        stream=False
                    ):
                        if response:
                            response_received = True
                            break
                    
                    success = response_received
                    
                except Exception as e:
                    error_message = str(e)
                
                response_time_ms = (time.time() - start_time) * 1000
                
                result = BenchmarkResult(
                    test_name=f"model_response_prompt_{i+1}_iter_{iteration+1}",
                    operation_type="model_response",
                    response_time_ms=response_time_ms,
                    success=success,
                    error_message=error_message,
                    metadata={"prompt_length": len(prompt)}
                )
                
                results.append(result)
                self.metrics.record_operation("model_response", response_time_ms, success)
                
                # Small delay between iterations
                await asyncio.sleep(0.1)
        
        return results
    
    async def _benchmark_cached_response(self) -> List[BenchmarkResult]:
        """Benchmark cached response retrieval."""
        results = []
        test_prompt = "This is a test prompt for caching."
        
        # First, populate the cache
        async for _ in self.model_engine.generate_response(
            test_prompt,
            use_cache=True,
            stream=False
        ):
            pass
        
        # Now benchmark cache retrieval
        for iteration in range(self.test_iterations):
            start_time = time.time()
            success = False
            error_message = None
            
            try:
                response_received = False
                async for response in self.model_engine.generate_response(
                    test_prompt,
                    use_cache=True,
                    stream=False
                ):
                    if response:
                        response_received = True
                        break
                
                success = response_received
                
            except Exception as e:
                error_message = str(e)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            result = BenchmarkResult(
                test_name=f"cached_response_iter_{iteration+1}",
                operation_type="cached_response",
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message
            )
            
            results.append(result)
            self.metrics.record_operation("cached_response", response_time_ms, success)
            
            await asyncio.sleep(0.05)
        
        return results
    
    async def _benchmark_context_loading(self) -> List[BenchmarkResult]:
        """Benchmark context loading operations."""
        results = []
        test_user_id = "benchmark_user_context"
        
        for iteration in range(self.test_iterations):
            start_time = time.time()
            success = False
            error_message = None
            
            try:
                context = await self.memory_layer.load_user_context(test_user_id)
                success = True  # Loading can return None for non-existent users
                
            except Exception as e:
                error_message = str(e)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            result = BenchmarkResult(
                test_name=f"context_loading_iter_{iteration+1}",
                operation_type="context_loading",
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message
            )
            
            results.append(result)
            self.metrics.record_operation("context_loading", response_time_ms, success)
            
            await asyncio.sleep(0.05)
        
        return results
    
    async def _benchmark_conversation_storage(self) -> List[BenchmarkResult]:
        """Benchmark conversation message storage."""
        results = []
        test_session_id = "benchmark_session"
        test_user_id = "benchmark_user"
        
        for iteration in range(self.test_iterations):
            start_time = time.time()
            success = False
            error_message = None
            
            try:
                success = await self.memory_layer.store_conversation_message(
                    session_id=test_session_id,
                    user_id=test_user_id,
                    role="user",
                    content=f"Test message {iteration}",
                    agent_type="personal"
                )
                
            except Exception as e:
                error_message = str(e)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            result = BenchmarkResult(
                test_name=f"conversation_storage_iter_{iteration+1}",
                operation_type="conversation_storage",
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message
            )
            
            results.append(result)
            self.metrics.record_operation("conversation_storage", response_time_ms, success)
            
            await asyncio.sleep(0.05)
        
        return results
    
    async def _benchmark_agent_routing(self) -> List[BenchmarkResult]:
        """Benchmark agent routing decisions."""
        results = []
        test_inputs = [
            "Help me with my family",
            "I need to buy something",
            "Can you help with work?",
            "What's my security status?",
            "Hello there"
        ]
        
        # Create a minimal session context for testing
        from .orchestrator import SessionContext
        user_context = MCPUserContext(
            user_id="benchmark_user",
            username="benchmark",
            permissions=[]
        )
        
        session_context = SessionContext(
            session_id="benchmark_session",
            user_id="benchmark_user",
            user_context=user_context
        )
        
        # Create a minimal orchestrator for routing tests
        from .orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        
        for i, test_input in enumerate(test_inputs):
            for iteration in range(self.test_iterations):
                start_time = time.time()
                success = False
                error_message = None
                
                try:
                    agent_type = await orchestrator.route_request(test_input, session_context)
                    success = agent_type is not None
                    
                except Exception as e:
                    error_message = str(e)
                
                response_time_ms = (time.time() - start_time) * 1000
                
                result = BenchmarkResult(
                    test_name=f"agent_routing_input_{i+1}_iter_{iteration+1}",
                    operation_type="agent_routing",
                    response_time_ms=response_time_ms,
                    success=success,
                    error_message=error_message,
                    metadata={"input_length": len(test_input)}
                )
                
                results.append(result)
                self.metrics.record_operation("agent_routing", response_time_ms, success)
                
                await asyncio.sleep(0.01)
        
        return results
    
    async def _benchmark_concurrent_operations(self) -> List[BenchmarkResult]:
        """Benchmark concurrent operation performance."""
        results = []
        
        async def concurrent_model_request(request_id: int) -> BenchmarkResult:
            start_time = time.time()
            success = False
            error_message = None
            
            try:
                response_received = False
                async for response in self.model_engine.generate_response(
                    f"Concurrent test request {request_id}",
                    use_cache=False,
                    stream=False
                ):
                    if response:
                        response_received = True
                        break
                
                success = response_received
                
            except Exception as e:
                error_message = str(e)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            return BenchmarkResult(
                test_name=f"concurrent_operation_request_{request_id}",
                operation_type="concurrent_operation",
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message
            )
        
        # Run concurrent requests
        for batch in range(3):  # 3 batches of concurrent requests
            tasks = []
            for i in range(self.concurrent_tests):
                request_id = batch * self.concurrent_tests + i + 1
                tasks.append(concurrent_model_request(request_id))
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in batch_results:
                if isinstance(result, BenchmarkResult):
                    results.append(result)
                    self.metrics.record_operation(
                        "concurrent_operation", 
                        result.response_time_ms, 
                        result.success
                    )
                else:
                    # Handle exceptions
                    results.append(BenchmarkResult(
                        test_name=f"concurrent_operation_exception",
                        operation_type="concurrent_operation",
                        response_time_ms=0.0,
                        success=False,
                        error_message=str(result)
                    ))
            
            # Delay between batches
            await asyncio.sleep(0.5)
        
        return results
    
    async def _benchmark_memory_operations(self) -> List[BenchmarkResult]:
        """Benchmark memory layer operations."""
        results = []
        test_user_id = "benchmark_memory_user"
        
        # Test knowledge search
        for iteration in range(self.test_iterations):
            start_time = time.time()
            success = False
            error_message = None
            
            try:
                knowledge_results = await self.memory_layer.search_knowledge(
                    user_id=test_user_id,
                    query="test query",
                    limit=10
                )
                success = True  # Search can return empty results
                
            except Exception as e:
                error_message = str(e)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            result = BenchmarkResult(
                test_name=f"memory_search_iter_{iteration+1}",
                operation_type="memory_search",
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message
            )
            
            results.append(result)
            self.metrics.record_operation("memory_search", response_time_ms, success)
            
            await asyncio.sleep(0.05)
        
        return results
    
    async def _benchmark_health_checks(self) -> List[BenchmarkResult]:
        """Benchmark health check operations."""
        results = []
        
        for iteration in range(self.test_iterations):
            start_time = time.time()
            success = False
            error_message = None
            
            try:
                # Test model engine health
                health_result = await self.model_engine.health_check()
                success = health_result.get("status") in ["healthy", "degraded"]
                
            except Exception as e:
                error_message = str(e)
            
            response_time_ms = (time.time() - start_time) * 1000
            
            result = BenchmarkResult(
                test_name=f"health_check_iter_{iteration+1}",
                operation_type="health_check",
                response_time_ms=response_time_ms,
                success=success,
                error_message=error_message
            )
            
            results.append(result)
            self.metrics.record_operation("health_check", response_time_ms, success)
            
            await asyncio.sleep(0.05)
        
        return results
    
    def _log_benchmark_summary(self, suite: BenchmarkSuite):
        """Log benchmark suite summary."""
        self.logger.info("=" * 60)
        self.logger.info("PERFORMANCE BENCHMARK RESULTS")
        self.logger.info("=" * 60)
        self.logger.info("Suite: %s", suite.suite_name)
        self.logger.info("Target Latency: %dms", suite.target_latency_ms)
        self.logger.info("Duration: %.2fms", suite.duration_ms)
        self.logger.info("Total Tests: %d", len(suite.results))
        self.logger.info("Success Rate: %.1f%%", suite.success_rate)
        self.logger.info("Average Response Time: %.2fms", suite.average_response_time)
        self.logger.info("95th Percentile: %.2fms", suite.p95_response_time)
        self.logger.info("Meets Target: %s", "✅ YES" if suite.meets_target else "❌ NO")
        
        # Log per-operation breakdown
        operation_stats = defaultdict(list)
        for result in suite.results:
            if result.success:
                operation_stats[result.operation_type].append(result.response_time_ms)
        
        self.logger.info("-" * 60)
        self.logger.info("PER-OPERATION BREAKDOWN:")
        for operation, times in operation_stats.items():
            if times:
                avg_time = statistics.mean(times)
                p95_time = statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times)
                meets_target = avg_time <= suite.target_latency_ms
                
                self.logger.info(
                    "%s: avg=%.2fms, p95=%.2fms, count=%d %s",
                    operation,
                    avg_time,
                    p95_time,
                    len(times),
                    "✅" if meets_target else "❌"
                )
        
        self.logger.info("=" * 60)
    
    async def _store_benchmark_results(self, suite: BenchmarkSuite):
        """Store benchmark results in Redis for historical tracking."""
        try:
            redis = await redis_manager.get_redis()
            
            # Store detailed results
            results_key = f"ai:benchmarks:{suite.started_at.strftime('%Y%m%d_%H%M%S')}"
            results_data = {
                "suite_name": suite.suite_name,
                "target_latency_ms": suite.target_latency_ms,
                "started_at": suite.started_at.isoformat(),
                "completed_at": suite.completed_at.isoformat() if suite.completed_at else None,
                "duration_ms": suite.duration_ms,
                "success_rate": suite.success_rate,
                "average_response_time": suite.average_response_time,
                "p95_response_time": suite.p95_response_time,
                "meets_target": suite.meets_target,
                "total_tests": len(suite.results),
                "results": [
                    {
                        "test_name": r.test_name,
                        "operation_type": r.operation_type,
                        "response_time_ms": r.response_time_ms,
                        "success": r.success,
                        "error_message": r.error_message,
                        "metadata": r.metadata,
                        "timestamp": r.timestamp.isoformat()
                    }
                    for r in suite.results
                ]
            }
            
            await redis.setex(
                results_key,
                86400 * 7,  # Keep for 7 days
                json.dumps(results_data, default=str)
            )
            
            # Store summary for quick access
            summary_key = "ai:benchmarks:latest"
            summary_data = {
                "timestamp": suite.completed_at.isoformat() if suite.completed_at else None,
                "success_rate": suite.success_rate,
                "average_response_time": suite.average_response_time,
                "p95_response_time": suite.p95_response_time,
                "meets_target": suite.meets_target,
                "total_tests": len(suite.results)
            }
            
            await redis.setex(summary_key, 86400, json.dumps(summary_data))
            
            self.logger.info("Benchmark results stored successfully")
            
        except Exception as e:
            self.logger.error("Failed to store benchmark results: %s", e)
    
    async def get_latest_benchmark_results(self) -> Optional[Dict[str, Any]]:
        """Get the latest benchmark results."""
        try:
            redis = await redis_manager.get_redis()
            summary_data = await redis.get("ai:benchmarks:latest")
            
            if summary_data:
                return json.loads(summary_data)
            
        except Exception as e:
            self.logger.error("Failed to get latest benchmark results: %s", e)
        
        return None
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics."""
        metrics_data = {
            "operation_counts": dict(self.metrics.operation_counts),
            "error_counts": dict(self.metrics.error_counts),
            "average_response_times": {},
            "error_rates": {},
            "last_updated": self.metrics.last_updated.isoformat()
        }
        
        for operation_type in self.metrics.operation_counts.keys():
            metrics_data["average_response_times"][operation_type] = (
                self.metrics.get_average_response_time(operation_type)
            )
            metrics_data["error_rates"][operation_type] = (
                self.metrics.get_error_rate(operation_type)
            )
        
        return metrics_data
    
    async def run_continuous_monitoring(self, interval_minutes: int = 30):
        """Run continuous performance monitoring."""
        self.logger.info("Starting continuous performance monitoring (interval: %d minutes)", interval_minutes)
        
        while True:
            try:
                # Run a subset of benchmarks for continuous monitoring
                suite = BenchmarkSuite(
                    suite_name="Continuous Performance Monitor",
                    target_latency_ms=self.target_latency_ms
                )
                
                # Run lightweight tests
                results = []
                results.extend(await self._benchmark_model_response())
                results.extend(await self._benchmark_cached_response())
                results.extend(await self._benchmark_context_loading())
                
                suite.results = results
                suite.completed_at = datetime.now(timezone.utc)
                
                # Check if performance is degrading
                if not suite.meets_target:
                    self.logger.warning(
                        "Performance degradation detected! Average response time: %.2fms (target: %dms)",
                        suite.average_response_time,
                        suite.target_latency_ms
                    )
                
                # Store monitoring results
                await self._store_benchmark_results(suite)
                
                # Wait for next interval
                await asyncio.sleep(interval_minutes * 60)
                
            except Exception as e:
                self.logger.error("Continuous monitoring error: %s", e)
                await asyncio.sleep(60)  # Wait 1 minute before retrying


# Global benchmark suite instance
_benchmark_suite = None


async def get_benchmark_suite() -> PerformanceBenchmarkSuite:
    """Get the global benchmark suite instance."""
    global _benchmark_suite
    if _benchmark_suite is None:
        _benchmark_suite = PerformanceBenchmarkSuite()
    return _benchmark_suite


async def run_performance_benchmarks() -> BenchmarkSuite:
    """Run the complete performance benchmark suite."""
    suite = await get_benchmark_suite()
    return await suite.run_full_benchmark_suite()


async def get_current_performance_metrics() -> Dict[str, Any]:
    """Get current performance metrics."""
    suite = await get_benchmark_suite()
    return await suite.get_performance_metrics()


async def start_continuous_monitoring(interval_minutes: int = 30):
    """Start continuous performance monitoring."""
    suite = await get_benchmark_suite()
    await suite.run_continuous_monitoring(interval_minutes)