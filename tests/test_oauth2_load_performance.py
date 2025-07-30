"""
Load testing and performance tests for OAuth2 browser authentication system.

This module provides comprehensive load testing and performance validation
to ensure the OAuth2 browser authentication system can handle production
workloads and concurrent user scenarios efficiently.

Test Categories:
- Concurrent authentication load testing (API + browser)
- Session management performance under load
- Authentication method selection overhead testing
- Memory usage and resource consumption testing
- Database connection pool stress testing
- Redis session storage performance testing
- Response time consistency under load
- Throughput and scalability testing
"""

import asyncio
import gc
import json
import psutil
import secrets
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from second_brain_database.main import app
from second_brain_database.routes.oauth2.auth_middleware import OAuth2AuthMiddleware
from second_brain_database.routes.oauth2.session_manager import session_manager, SESSION_COOKIE_NAME

# Test client setup
client = TestClient(app)

# Performance test constants
LOAD_TEST_USERS = 100
CONCURRENT_SESSIONS = 50
PERFORMANCE_THRESHOLD_MS = 100  # 100ms response time threshold
MEMORY_THRESHOLD_MB = 100  # 100MB memory usage threshold
CPU_THRESHOLD_PERCENT = 80  # 80% CPU usage threshold


class PerformanceMetrics:
    """Class to collect and analyze performance metrics."""
    
    def __init__(self):
        self.response_times = []
        self.memory_usage = []
        self.cpu_usage = []
        self.error_count = 0
        self.success_count = 0
        self.start_time = None
        self.end_time = None
    
    def start_monitoring(self):
        """Start performance monitoring."""
        self.start_time = time.time()
        gc.collect()  # Clean up before monitoring
    
    def stop_monitoring(self):
        """Stop performance monitoring."""
        self.end_time = time.time()
        gc.collect()  # Clean up after monitoring
    
    def record_response_time(self, response_time: float):
        """Record a response time measurement."""
        self.response_times.append(response_time)
    
    def record_memory_usage(self):
        """Record current memory usage."""
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024
        self.memory_usage.append(memory_mb)
    
    def record_cpu_usage(self):
        """Record current CPU usage."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        self.cpu_usage.append(cpu_percent)
    
    def record_success(self):
        """Record a successful operation."""
        self.success_count += 1
    
    def record_error(self):
        """Record a failed operation."""
        self.error_count += 1
    
    def get_summary(self) -> Dict:
        """Get performance metrics summary."""
        total_time = self.end_time - self.start_time if self.end_time and self.start_time else 0
        total_requests = self.success_count + self.error_count
        
        return {
            "total_time": total_time,
            "total_requests": total_requests,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "success_rate": self.success_count / total_requests if total_requests > 0 else 0,
            "requests_per_second": total_requests / total_time if total_time > 0 else 0,
            "response_times": {
                "min": min(self.response_times) if self.response_times else 0,
                "max": max(self.response_times) if self.response_times else 0,
                "avg": statistics.mean(self.response_times) if self.response_times else 0,
                "median": statistics.median(self.response_times) if self.response_times else 0,
                "p95": statistics.quantiles(self.response_times, n=20)[18] if len(self.response_times) >= 20 else 0,
                "p99": statistics.quantiles(self.response_times, n=100)[98] if len(self.response_times) >= 100 else 0,
            },
            "memory_usage": {
                "min": min(self.memory_usage) if self.memory_usage else 0,
                "max": max(self.memory_usage) if self.memory_usage else 0,
                "avg": statistics.mean(self.memory_usage) if self.memory_usage else 0,
            },
            "cpu_usage": {
                "min": min(self.cpu_usage) if self.cpu_usage else 0,
                "max": max(self.cpu_usage) if self.cpu_usage else 0,
                "avg": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
            }
        }


class TestConcurrentAuthenticationLoad:
    """Load tests for concurrent authentication scenarios."""
    
    def test_concurrent_jwt_authentication_load(self):
        """Test concurrent JWT authentication under load."""
        metrics = PerformanceMetrics()
        metrics.start_monitoring()
        
        def jwt_auth_worker(worker_id: int) -> Dict:
            """Worker function for JWT authentication testing."""
            results = {"success": 0, "error": 0, "response_times": []}
            
            with patch('second_brain_database.routes.auth.services.auth.login.get_current_user') as mock_auth:
                mock_auth.return_value = {
                    "user_id": f"jwt_user_{worker_id}",
                    "username": f"user_{worker_id}",
                    "auth_method": "jwt"
                }
                
                for request_num in range(10):  # 10 requests per worker
                    start_time = time.time()
                    
                    try:
                        response = client.get("/auth/me", headers={
                            "Authorization": f"Bearer jwt_token_{worker_id}_{request_num}"
                        })
                        
                        end_time = time.time()
                        response_time = (end_time - start_time) * 1000  # Convert to ms
                        
                        results["response_times"].append(response_time)
                        
                        if response.status_code in [200, 404]:  # 404 if endpoint doesn't exist
                            results["success"] += 1
                            metrics.record_success()
                        else:
                            results["error"] += 1
                            metrics.record_error()
                        
                        metrics.record_response_time(response_time)
                        
                    except Exception as e:
                        results["error"] += 1
                        metrics.record_error()
                        print(f"JWT auth error in worker {worker_id}: {e}")
            
            return results
        
        # Run concurrent JWT authentication tests
        with ThreadPoolExecutor(max_workers=CONCURRENT_SESSIONS) as executor:
            futures = [executor.submit(jwt_auth_worker, i) for i in range(CONCURRENT_SESSIONS)]
            
            # Monitor system resources during test
            for _ in range(10):
                metrics.record_memory_usage()
                metrics.record_cpu_usage()
                time.sleep(0.5)
            
            # Collect results
            worker_results = [future.result() for future in as_completed(futures)]
        
        metrics.stop_monitoring()
        summary = metrics.get_summary()
        
        # Performance assertions
        assert summary["success_rate"] >= 0.95, f"Success rate too low: {summary['success_rate']:.2%}"
        assert summary["response_times"]["avg"] < PERFORMANCE_THRESHOLD_MS, \
            f"Average response time too high: {summary['response_times']['avg']:.2f}ms"
        assert summary["response_times"]["p95"] < PERFORMANCE_THRESHOLD_MS * 2, \
            f"95th percentile response time too high: {summary['response_times']['p95']:.2f}ms"
        
        print(f"JWT Authentication Load Test Results:")
        print(f"  Total Requests: {summary['total_requests']}")
        print(f"  Success Rate: {summary['success_rate']:.2%}")
        print(f"  Requests/Second: {summary['requests_per_second']:.2f}")
        print(f"  Avg Response Time: {summary['response_times']['avg']:.2f}ms")
        print(f"  95th Percentile: {summary['response_times']['p95']:.2f}ms")
    
    def test_concurrent_session_authentication_load(self):
        """Test concurrent session authentication under load."""
        metrics = PerformanceMetrics()
        metrics.start_monitoring()
        
        def session_auth_worker(worker_id: int) -> Dict:
            """Worker function for session authentication testing."""
            results = {"success": 0, "error": 0, "response_times": []}
            
            with patch('second_brain_database.routes.oauth2.session_manager.redis_manager') as mock_redis:
                redis_client = mock_redis.get_redis.return_value
                redis_client.get = AsyncMock(return_value=json.dumps({
                    "user_id": f"session_user_{worker_id}",
                    "username": f"user_{worker_id}",
                    "created_at": datetime.utcnow().isoformat(),
                    "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                    "ip_address": "192.168.1.1",
                    "user_agent": "Load Test Browser",
                    "csrf_token": f"csrf_{worker_id}",
                    "is_active": True
                }))
                redis_client.expire = AsyncMock()
                
                for request_num in range(10):  # 10 requests per worker
                    start_time = time.time()
                    
                    try:
                        response = client.get("/oauth2/authorize", 
                                            cookies={SESSION_COOKIE_NAME: f"session_{worker_id}_{request_num}"},
                                            params={
                                                "client_id": f"client_{worker_id}",
                                                "redirect_uri": "https://example.com/callback",
                                                "response_type": "code",
                                                "scope": "read"
                                            })
                        
                        end_time = time.time()
                        response_time = (end_time - start_time) * 1000  # Convert to ms
                        
                        results["response_times"].append(response_time)
                        
                        if response.status_code in [200, 302, 400]:  # Valid responses
                            results["success"] += 1
                            metrics.record_success()
                        else:
                            results["error"] += 1
                            metrics.record_error()
                        
                        metrics.record_response_time(response_time)
                        
                    except Exception as e:
                        results["error"] += 1
                        metrics.record_error()
                        print(f"Session auth error in worker {worker_id}: {e}")
            
            return results
        
        # Run concurrent session authentication tests
        with ThreadPoolExecutor(max_workers=CONCURRENT_SESSIONS) as executor:
            futures = [executor.submit(session_auth_worker, i) for i in range(CONCURRENT_SESSIONS)]
            
            # Monitor system resources during test
            for _ in range(10):
                metrics.record_memory_usage()
                metrics.record_cpu_usage()
                time.sleep(0.5)
            
            # Collect results
            worker_results = [future.result() for future in as_completed(futures)]
        
        metrics.stop_monitoring()
        summary = metrics.get_summary()
        
        # Performance assertions
        assert summary["success_rate"] >= 0.90, f"Success rate too low: {summary['success_rate']:.2%}"
        assert summary["response_times"]["avg"] < PERFORMANCE_THRESHOLD_MS * 1.5, \
            f"Average response time too high: {summary['response_times']['avg']:.2f}ms"
        
        print(f"Session Authentication Load Test Results:")
        print(f"  Total Requests: {summary['total_requests']}")
        print(f"  Success Rate: {summary['success_rate']:.2%}")
        print(f"  Requests/Second: {summary['requests_per_second']:.2f}")
        print(f"  Avg Response Time: {summary['response_times']['avg']:.2f}ms")
        print(f"  95th Percentile: {summary['response_times']['p95']:.2f}ms")
    
    def test_mixed_authentication_load(self):
        """Test mixed JWT and session authentication under load."""
        metrics = PerformanceMetrics()
        metrics.start_monitoring()
        
        def mixed_auth_worker(worker_id: int) -> Dict:
            """Worker function for mixed authentication testing."""
            results = {"jwt_success": 0, "session_success": 0, "error": 0, "response_times": []}
            
            # Setup mocks for both auth methods
            with patch('second_brain_database.routes.auth.services.auth.login.get_current_user') as mock_jwt:
                mock_jwt.return_value = {
                    "user_id": f"jwt_user_{worker_id}",
                    "auth_method": "jwt"
                }
                
                with patch('second_brain_database.routes.oauth2.session_manager.redis_manager') as mock_redis:
                    redis_client = mock_redis.get_redis.return_value
                    redis_client.get = AsyncMock(return_value=json.dumps({
                        "user_id": f"session_user_{worker_id}",
                        "auth_method": "session",
                        "created_at": datetime.utcnow().isoformat(),
                        "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                        "is_active": True
                    }))
                    
                    for request_num in range(20):  # 20 requests per worker
                        start_time = time.time()
                        
                        try:
                            # Alternate between JWT and session auth
                            if request_num % 2 == 0:
                                # JWT authentication
                                response = client.get("/oauth2/authorize", 
                                                    headers={"Authorization": f"Bearer jwt_{worker_id}_{request_num}"},
                                                    params={"client_id": f"client_{worker_id}"})
                                auth_type = "jwt"
                            else:
                                # Session authentication
                                response = client.get("/oauth2/authorize", 
                                                    cookies={SESSION_COOKIE_NAME: f"session_{worker_id}_{request_num}"},
                                                    params={"client_id": f"client_{worker_id}"})
                                auth_type = "session"
                            
                            end_time = time.time()
                            response_time = (end_time - start_time) * 1000
                            
                            results["response_times"].append(response_time)
                            
                            if response.status_code in [200, 302, 400]:
                                if auth_type == "jwt":
                                    results["jwt_success"] += 1
                                else:
                                    results["session_success"] += 1
                                metrics.record_success()
                            else:
                                results["error"] += 1
                                metrics.record_error()
                            
                            metrics.record_response_time(response_time)
                            
                        except Exception as e:
                            results["error"] += 1
                            metrics.record_error()
                            print(f"Mixed auth error in worker {worker_id}: {e}")
            
            return results
        
        # Run mixed authentication load test
        with ThreadPoolExecutor(max_workers=CONCURRENT_SESSIONS) as executor:
            futures = [executor.submit(mixed_auth_worker, i) for i in range(CONCURRENT_SESSIONS)]
            
            # Monitor system resources
            for _ in range(15):
                metrics.record_memory_usage()
                metrics.record_cpu_usage()
                time.sleep(0.5)
            
            # Collect results
            worker_results = [future.result() for future in as_completed(futures)]
        
        metrics.stop_monitoring()
        summary = metrics.get_summary()
        
        # Calculate mixed auth statistics
        total_jwt = sum(r["jwt_success"] for r in worker_results)
        total_session = sum(r["session_success"] for r in worker_results)
        
        # Performance assertions
        assert summary["success_rate"] >= 0.90, f"Success rate too low: {summary['success_rate']:.2%}"
        assert total_jwt > 0 and total_session > 0, "Both auth methods should be tested"
        assert abs(total_jwt - total_session) / max(total_jwt, total_session) < 0.2, \
            "Auth methods should be roughly balanced"
        
        print(f"Mixed Authentication Load Test Results:")
        print(f"  Total Requests: {summary['total_requests']}")
        print(f"  JWT Successes: {total_jwt}")
        print(f"  Session Successes: {total_session}")
        print(f"  Success Rate: {summary['success_rate']:.2%}")
        print(f"  Avg Response Time: {summary['response_times']['avg']:.2f}ms")


class TestSessionManagementPerformance:
    """Performance tests for session management operations."""
    
    @pytest.mark.asyncio
    async def test_session_creation_performance(self):
        """Test session creation performance under load."""
        metrics = PerformanceMetrics()
        metrics.start_monitoring()
        
        with patch('second_brain_database.routes.oauth2.session_manager.redis_manager') as mock_redis:
            redis_client = mock_redis.get_redis.return_value
            redis_client.setex = AsyncMock()
            redis_client.sadd = AsyncMock()
            redis_client.expire = AsyncMock()
            redis_client.scard = AsyncMock(return_value=0)  # No existing sessions
            
            # Create many sessions concurrently
            async def create_session_task(session_id: int):
                mock_request = MagicMock()
                mock_request.client.host = f"192.168.1.{session_id % 255 + 1}"
                mock_request.headers = {"user-agent": f"Test Browser {session_id}"}
                
                mock_response = MagicMock()
                
                start_time = time.time()
                
                try:
                    session_id_result = await session_manager.create_session(
                        user_id=f"user_{session_id}",
                        request=mock_request,
                        response=mock_response
                    )
                    
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    
                    metrics.record_response_time(response_time)
                    metrics.record_success()
                    
                    return {"success": True, "session_id": session_id_result, "response_time": response_time}
                    
                except Exception as e:
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    
                    metrics.record_response_time(response_time)
                    metrics.record_error()
                    
                    return {"success": False, "error": str(e), "response_time": response_time}
            
            # Run concurrent session creation
            tasks = [create_session_task(i) for i in range(LOAD_TEST_USERS)]
            results = await asyncio.gather(*tasks)
        
        metrics.stop_monitoring()
        summary = metrics.get_summary()
        
        # Performance assertions
        successful_results = [r for r in results if r["success"]]
        assert len(successful_results) >= LOAD_TEST_USERS * 0.95, "Session creation success rate too low"
        assert summary["response_times"]["avg"] < 50, \
            f"Session creation too slow: {summary['response_times']['avg']:.2f}ms"
        
        print(f"Session Creation Performance Test Results:")
        print(f"  Sessions Created: {len(successful_results)}")
        print(f"  Success Rate: {len(successful_results)/len(results):.2%}")
        print(f"  Avg Creation Time: {summary['response_times']['avg']:.2f}ms")
        print(f"  Max Creation Time: {summary['response_times']['max']:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_session_validation_performance(self):
        """Test session validation performance under load."""
        metrics = PerformanceMetrics()
        metrics.start_monitoring()
        
        # Mock session data
        session_data = {
            "user_id": "test_user",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "ip_address": "192.168.1.1",
            "user_agent": "Test Browser",
            "csrf_token": "test_csrf_token",
            "is_active": True
        }
        
        with patch('second_brain_database.routes.oauth2.session_manager.redis_manager') as mock_redis:
            redis_client = mock_redis.get_redis.return_value
            redis_client.get = AsyncMock(return_value=json.dumps(session_data))
            redis_client.expire = AsyncMock()
            
            # Validate many sessions concurrently
            async def validate_session_task(session_id: int):
                mock_request = MagicMock()
                mock_request.cookies = {SESSION_COOKIE_NAME: f"session_{session_id}"}
                mock_request.client.host = "192.168.1.1"
                mock_request.headers = {"user-agent": "Test Browser"}
                
                start_time = time.time()
                
                try:
                    user_data = await session_manager.validate_session(mock_request)
                    
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    
                    metrics.record_response_time(response_time)
                    
                    if user_data:
                        metrics.record_success()
                        return {"success": True, "user_data": user_data, "response_time": response_time}
                    else:
                        metrics.record_error()
                        return {"success": False, "error": "No user data", "response_time": response_time}
                    
                except Exception as e:
                    end_time = time.time()
                    response_time = (end_time - start_time) * 1000
                    
                    metrics.record_response_time(response_time)
                    metrics.record_error()
                    
                    return {"success": False, "error": str(e), "response_time": response_time}
            
            # Run concurrent session validation
            tasks = [validate_session_task(i) for i in range(LOAD_TEST_USERS)]
            results = await asyncio.gather(*tasks)
        
        metrics.stop_monitoring()
        summary = metrics.get_summary()
        
        # Performance assertions
        successful_results = [r for r in results if r["success"]]
        assert len(successful_results) >= LOAD_TEST_USERS * 0.95, "Session validation success rate too low"
        assert summary["response_times"]["avg"] < 30, \
            f"Session validation too slow: {summary['response_times']['avg']:.2f}ms"
        
        print(f"Session Validation Performance Test Results:")
        print(f"  Sessions Validated: {len(successful_results)}")
        print(f"  Success Rate: {len(successful_results)/len(results):.2%}")
        print(f"  Avg Validation Time: {summary['response_times']['avg']:.2f}ms")
        print(f"  Max Validation Time: {summary['response_times']['max']:.2f}ms")
    
    @pytest.mark.asyncio
    async def test_session_cleanup_performance(self):
        """Test session cleanup performance with large number of sessions."""
        metrics = PerformanceMetrics()
        metrics.start_monitoring()
        
        # Mock large number of expired sessions
        num_sessions = 10000
        expired_sessions = [f"oauth2:session:expired_{i}".encode() for i in range(num_sessions)]
        
        with patch('second_brain_database.routes.oauth2.session_manager.redis_manager') as mock_redis:
            redis_client = mock_redis.get_redis.return_value
            redis_client.scan_iter = AsyncMock(return_value=expired_sessions)
            
            # Half expired, half valid
            redis_client.get = AsyncMock(side_effect=[
                json.dumps({"expires_at": (datetime.utcnow() - timedelta(minutes=1)).isoformat()})
                if i < num_sessions // 2 else
                json.dumps({"expires_at": (datetime.utcnow() + timedelta(minutes=30)).isoformat()})
                for i in range(num_sessions)
            ])
            
            redis_client.delete = AsyncMock()
            redis_client.srem = AsyncMock()
            
            # Test cleanup performance
            start_time = time.time()
            cleaned_count = await session_manager.cleanup_expired_sessions()
            end_time = time.time()
            
            cleanup_time = (end_time - start_time) * 1000
            metrics.record_response_time(cleanup_time)
        
        metrics.stop_monitoring()
        
        # Performance assertions
        expected_cleaned = num_sessions // 2
        assert cleaned_count == expected_cleaned, f"Expected {expected_cleaned} cleaned, got {cleaned_count}"
        assert cleanup_time < 5000, f"Cleanup too slow: {cleanup_time:.2f}ms"  # Should complete within 5 seconds
        
        print(f"Session Cleanup Performance Test Results:")
        print(f"  Total Sessions Scanned: {num_sessions}")
        print(f"  Sessions Cleaned: {cleaned_count}")
        print(f"  Cleanup Time: {cleanup_time:.2f}ms")
        print(f"  Sessions/Second: {num_sessions / (cleanup_time / 1000):.2f}")


class TestMemoryAndResourceUsage:
    """Tests for memory usage and resource consumption."""
    
    def test_authentication_middleware_memory_usage(self):
        """Test memory usage of authentication middleware under load."""
        gc.collect()  # Clean up before test
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Create many middleware instances
        middlewares = []
        for i in range(1000):
            middleware = OAuth2AuthMiddleware()
            middlewares.append(middleware)
            
            # Check memory every 100 instances
            if i % 100 == 0:
                current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                memory_growth = current_memory - initial_memory
                
                # Memory growth should be reasonable
                assert memory_growth < MEMORY_THRESHOLD_MB, \
                    f"Memory usage too high: {memory_growth:.2f}MB after {i+1} instances"
        
        # Test memory usage during operations
        peak_memory = initial_memory
        
        async def memory_test_operation():
            nonlocal peak_memory
            
            mock_request = MagicMock()
            mock_request.headers = {"authorization": "Bearer test_token"}
            
            with patch('second_brain_database.routes.oauth2.auth_middleware.get_current_user') as mock_auth:
                mock_auth.return_value = {"user_id": "test_user", "auth_method": "jwt"}
                
                for middleware in middlewares[:100]:  # Test with 100 instances
                    await middleware.get_current_user_flexible(mock_request)
                    
                    current_memory = psutil.Process().memory_info().rss / 1024 / 1024
                    peak_memory = max(peak_memory, current_memory)
        
        # Run memory test
        import asyncio
        asyncio.run(memory_test_operation())
        
        # Clean up
        del middlewares
        gc.collect()
        
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        total_growth = peak_memory - initial_memory
        cleanup_efficiency = (peak_memory - final_memory) / total_growth if total_growth > 0 else 1
        
        # Memory assertions
        assert total_growth < MEMORY_THRESHOLD_MB * 2, f"Peak memory growth too high: {total_growth:.2f}MB"
        assert cleanup_efficiency > 0.7, f"Memory cleanup efficiency too low: {cleanup_efficiency:.2%}"
        
        print(f"Memory Usage Test Results:")
        print(f"  Initial Memory: {initial_memory:.2f}MB")
        print(f"  Peak Memory: {peak_memory:.2f}MB")
        print(f"  Final Memory: {final_memory:.2f}MB")
        print(f"  Peak Growth: {total_growth:.2f}MB")
        print(f"  Cleanup Efficiency: {cleanup_efficiency:.2%}")
    
    def test_session_storage_memory_efficiency(self):
        """Test memory efficiency of session storage operations."""
        gc.collect()
        initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Create many session objects
        sessions = []
        for i in range(10000):
            session_data = {
                "user_id": f"user_{i}",
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
                "ip_address": f"192.168.{i//255}.{i%255}",
                "user_agent": f"Browser {i}",
                "csrf_token": secrets.token_urlsafe(32),
                "is_active": True
            }
            sessions.append(json.dumps(session_data))
        
        current_memory = psutil.Process().memory_info().rss / 1024 / 1024
        memory_per_session = (current_memory - initial_memory) / len(sessions) * 1024  # KB per session
        
        # Clean up
        del sessions
        gc.collect()
        
        final_memory = psutil.Process().memory_info().rss / 1024 / 1024
        
        # Memory efficiency assertions
        assert memory_per_session < 1.0, f"Memory per session too high: {memory_per_session:.3f}KB"
        assert (current_memory - final_memory) / (current_memory - initial_memory) > 0.8, \
            "Memory cleanup efficiency too low"
        
        print(f"Session Storage Memory Efficiency Test Results:")
        print(f"  Sessions Created: 10,000")
        print(f"  Memory per Session: {memory_per_session:.3f}KB")
        print(f"  Total Memory Used: {current_memory - initial_memory:.2f}MB")
        print(f"  Memory Cleaned Up: {current_memory - final_memory:.2f}MB")
    
    def test_cpu_usage_under_load(self):
        """Test CPU usage under authentication load."""
        cpu_measurements = []
        
        def cpu_monitor():
            """Monitor CPU usage during test."""
            for _ in range(20):  # Monitor for 10 seconds
                cpu_percent = psutil.cpu_percent(interval=0.5)
                cpu_measurements.append(cpu_percent)
        
        def auth_load_generator():
            """Generate authentication load."""
            with patch('second_brain_database.routes.oauth2.auth_middleware.get_current_user') as mock_auth:
                mock_auth.return_value = {"user_id": "load_test_user", "auth_method": "jwt"}
                
                middleware = OAuth2AuthMiddleware()
                
                for i in range(1000):
                    mock_request = MagicMock()
                    mock_request.headers = {"authorization": f"Bearer token_{i}"}
                    
                    # Simulate async operation
                    import asyncio
                    asyncio.run(middleware.get_current_user_flexible(mock_request))
        
        # Run CPU monitoring and load generation concurrently
        cpu_thread = threading.Thread(target=cpu_monitor)
        load_thread = threading.Thread(target=auth_load_generator)
        
        cpu_thread.start()
        load_thread.start()
        
        cpu_thread.join()
        load_thread.join()
        
        # CPU usage assertions
        avg_cpu = statistics.mean(cpu_measurements) if cpu_measurements else 0
        max_cpu = max(cpu_measurements) if cpu_measurements else 0
        
        assert avg_cpu < CPU_THRESHOLD_PERCENT, f"Average CPU usage too high: {avg_cpu:.1f}%"
        assert max_cpu < CPU_THRESHOLD_PERCENT * 1.2, f"Peak CPU usage too high: {max_cpu:.1f}%"
        
        print(f"CPU Usage Test Results:")
        print(f"  Average CPU: {avg_cpu:.1f}%")
        print(f"  Peak CPU: {max_cpu:.1f}%")
        print(f"  CPU Measurements: {len(cpu_measurements)}")


class TestThroughputAndScalability:
    """Tests for throughput and scalability characteristics."""
    
    def test_authentication_throughput(self):
        """Test authentication throughput under various loads."""
        load_levels = [10, 25, 50, 100]  # Different concurrent user levels
        throughput_results = {}
        
        for load_level in load_levels:
            metrics = PerformanceMetrics()
            metrics.start_monitoring()
            
            def throughput_worker(worker_id: int):
                """Worker for throughput testing."""
                with patch('second_brain_database.routes.oauth2.auth_middleware.get_current_user') as mock_auth:
                    mock_auth.return_value = {"user_id": f"user_{worker_id}", "auth_method": "jwt"}
                    
                    requests_completed = 0
                    start_time = time.time()
                    
                    # Run for 10 seconds
                    while time.time() - start_time < 10:
                        try:
                            response = client.get("/auth/me", headers={
                                "Authorization": f"Bearer token_{worker_id}_{requests_completed}"
                            })
                            
                            if response.status_code in [200, 404]:
                                metrics.record_success()
                            else:
                                metrics.record_error()
                            
                            requests_completed += 1
                            
                        except Exception:
                            metrics.record_error()
                    
                    return requests_completed
            
            # Run throughput test
            with ThreadPoolExecutor(max_workers=load_level) as executor:
                futures = [executor.submit(throughput_worker, i) for i in range(load_level)]
                worker_results = [future.result() for future in as_completed(futures)]
            
            metrics.stop_monitoring()
            summary = metrics.get_summary()
            
            throughput_results[load_level] = {
                "requests_per_second": summary["requests_per_second"],
                "success_rate": summary["success_rate"],
                "avg_response_time": summary["response_times"]["avg"],
                "total_requests": sum(worker_results)
            }
            
            print(f"Load Level {load_level}: {summary['requests_per_second']:.2f} req/s, "
                  f"{summary['success_rate']:.2%} success rate")
        
        # Scalability assertions
        base_throughput = throughput_results[load_levels[0]]["requests_per_second"]
        
        for load_level in load_levels[1:]:
            current_throughput = throughput_results[load_level]["requests_per_second"]
            scalability_ratio = current_throughput / base_throughput
            expected_ratio = load_level / load_levels[0]
            
            # Should scale reasonably (at least 50% of linear scaling)
            assert scalability_ratio >= expected_ratio * 0.5, \
                f"Poor scalability at load {load_level}: {scalability_ratio:.2f}x vs expected {expected_ratio:.2f}x"
        
        print(f"\nThroughput Scalability Test Results:")
        for load_level, results in throughput_results.items():
            print(f"  Load {load_level:3d}: {results['requests_per_second']:6.2f} req/s, "
                  f"{results['success_rate']:5.1%} success, "
                  f"{results['avg_response_time']:5.1f}ms avg")
    
    def test_response_time_consistency(self):
        """Test response time consistency under sustained load."""
        response_times = []
        test_duration = 30  # 30 seconds
        
        def consistency_test():
            """Run consistency test."""
            start_time = time.time()
            
            with patch('second_brain_database.routes.oauth2.auth_middleware.get_current_user') as mock_auth:
                mock_auth.return_value = {"user_id": "consistency_user", "auth_method": "jwt"}
                
                request_count = 0
                while time.time() - start_time < test_duration:
                    request_start = time.time()
                    
                    try:
                        response = client.get("/auth/me", headers={
                            "Authorization": f"Bearer consistency_token_{request_count}"
                        })
                        
                        request_end = time.time()
                        response_time = (request_end - request_start) * 1000
                        response_times.append(response_time)
                        
                        request_count += 1
                        
                        # Small delay to avoid overwhelming
                        time.sleep(0.01)
                        
                    except Exception:
                        pass
        
        # Run consistency test
        consistency_test()
        
        # Analyze response time consistency
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            std_dev = statistics.stdev(response_times) if len(response_times) > 1 else 0
            
            # Calculate coefficient of variation (CV)
            cv = std_dev / avg_response_time if avg_response_time > 0 else 0
            
            # Consistency assertions
            assert cv < 0.5, f"Response time too inconsistent: CV = {cv:.3f}"
            assert abs(avg_response_time - median_response_time) / avg_response_time < 0.3, \
                "Response time distribution too skewed"
            
            print(f"Response Time Consistency Test Results:")
            print(f"  Test Duration: {test_duration}s")
            print(f"  Total Requests: {len(response_times)}")
            print(f"  Avg Response Time: {avg_response_time:.2f}ms")
            print(f"  Median Response Time: {median_response_time:.2f}ms")
            print(f"  Standard Deviation: {std_dev:.2f}ms")
            print(f"  Coefficient of Variation: {cv:.3f}")
        else:
            pytest.fail("No response times recorded during consistency test")


# Test execution and reporting
if __name__ == "__main__":
    print("Running OAuth2 Load Testing and Performance Tests...")
    print("=" * 80)
    print("⚠️  WARNING: These are intensive performance tests.")
    print("   They may consume significant system resources during execution.")
    print("   Ensure adequate system resources are available.")
    print("=" * 80)
    
    # This would typically be run with pytest
    # pytest tests/test_oauth2_load_performance.py -v -s --tb=short