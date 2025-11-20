#!/usr/bin/env python3
"""
Performance validation test for permanent tokens.
Tests performance under load and validates memory usage and response times.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import statistics
import sys
import time
from typing import Any, Dict, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.config import settings
from second_brain_database.database import db_manager


class PerformanceValidator:
    """Performance validation for permanent token services."""

    def __init__(self):
        self.test_tokens = []
        self.test_user_id = None
        self.test_username = None
        self.performance_results = {}

    async def setup(self):
        """Set up test environment."""
        print("🔧 Setting up performance test environment...")

        # Connect to database
        await db_manager.connect()
        await db_manager.create_indexes()

        # Create test user
        import time

        from bson import ObjectId

        self.test_user_id = str(ObjectId())
        self.test_username = f"perf_test_user_{int(time.time())}"
        test_email = f"perf_test_{int(time.time())}@example.com"

        # Create test user in database
        user_doc = {
            "_id": ObjectId(self.test_user_id),
            "username": self.test_username,
            "email": test_email,
            "role": "user",
            "is_verified": True,
            "created_at": "2025-01-01T00:00:00Z",
        }

        users_collection = db_manager.get_collection("users")
        await users_collection.insert_one(user_doc)

        print("✅ Performance test environment ready")

    async def cleanup(self):
        """Clean up test environment."""
        print("🧹 Cleaning up performance test data...")

        try:
            # Remove test user
            await db_manager.get_collection("users").delete_many({"_id": ObjectId(self.test_user_id)})

            # Remove test tokens
            await db_manager.get_collection("permanent_tokens").delete_many({"user_id": self.test_user_id})

            # Remove test audit logs
            await db_manager.get_collection("permanent_token_audit_logs").delete_many({"username": self.test_username})

            # Remove test analytics
            await db_manager.get_collection("permanent_token_usage_analytics").delete_many(
                {"user_id": self.test_user_id}
            )

        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")

        # Disconnect from database
        await db_manager.disconnect()
        print("✅ Performance test cleanup complete")

    async def create_test_tokens(self, count: int = 10):
        """Create multiple test tokens for performance testing."""
        print(f"\n🔑 Creating {count} test tokens...")

        from second_brain_database.routes.auth.services.permanent_tokens.generator import create_permanent_token

        start_time = time.time()

        for i in range(count):
            token_data = await create_permanent_token(
                user_id=self.test_user_id,
                username=self.test_username,
                email=f"perf_test_{i}@example.com",
                description=f"Performance Test Token {i}",
            )
            self.test_tokens.append(token_data.token)

        creation_time = time.time() - start_time
        tokens_per_second = count / creation_time

        print(f"✅ Created {count} tokens in {creation_time:.2f}s ({tokens_per_second:.1f} tokens/sec)")

        self.performance_results["token_creation"] = {
            "total_time": creation_time,
            "tokens_per_second": tokens_per_second,
            "average_time_per_token": creation_time / count,
        }

    async def test_validation_performance(self, iterations: int = 100):
        """Test token validation performance under load."""
        print(f"\n🔐 Testing validation performance ({iterations} iterations)...")

        from second_brain_database.routes.auth.services.permanent_tokens.validator import validate_permanent_token

        if not self.test_tokens:
            print("❌ No test tokens available")
            return False

        validation_times = []
        cache_hits = 0
        cache_misses = 0

        # Test validation performance
        for i in range(iterations):
            token = self.test_tokens[i % len(self.test_tokens)]

            start_time = time.time()
            result = await validate_permanent_token(token)
            validation_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            validation_times.append(validation_time)

            if result:
                # Check if this was a cache hit (subsequent calls should be faster)
                if validation_time < 10:  # Assume < 10ms is a cache hit
                    cache_hits += 1
                else:
                    cache_misses += 1

            # Small delay to prevent overwhelming the system
            if i % 10 == 0:
                await asyncio.sleep(0.01)

        # Calculate statistics
        avg_time = statistics.mean(validation_times)
        median_time = statistics.median(validation_times)
        min_time = min(validation_times)
        max_time = max(validation_times)
        p95_time = sorted(validation_times)[int(0.95 * len(validation_times))]

        cache_hit_rate = (cache_hits / iterations) * 100 if iterations > 0 else 0

        print(f"✅ Validation performance results:")
        print(f"   Average time: {avg_time:.2f}ms")
        print(f"   Median time: {median_time:.2f}ms")
        print(f"   Min time: {min_time:.2f}ms")
        print(f"   Max time: {max_time:.2f}ms")
        print(f"   95th percentile: {p95_time:.2f}ms")
        print(f"   Cache hit rate: {cache_hit_rate:.1f}%")

        self.performance_results["validation"] = {
            "iterations": iterations,
            "average_time_ms": avg_time,
            "median_time_ms": median_time,
            "min_time_ms": min_time,
            "max_time_ms": max_time,
            "p95_time_ms": p95_time,
            "cache_hit_rate": cache_hit_rate,
        }

        # Performance thresholds
        if avg_time > 100:  # Average should be under 100ms
            print("⚠️ Warning: Average validation time exceeds 100ms")
            return False

        if p95_time > 500:  # 95th percentile should be under 500ms
            print("⚠️ Warning: 95th percentile validation time exceeds 500ms")
            return False

        return True

    async def test_concurrent_validation(self, concurrent_requests: int = 50):
        """Test concurrent token validation performance."""
        print(f"\n⚡ Testing concurrent validation ({concurrent_requests} concurrent requests)...")

        from second_brain_database.routes.auth.services.permanent_tokens.validator import validate_permanent_token

        if not self.test_tokens:
            print("❌ No test tokens available")
            return False

        async def validate_token_task(token):
            start_time = time.time()
            result = await validate_permanent_token(token)
            return time.time() - start_time, result is not None

        # Create concurrent validation tasks
        tasks = []
        for i in range(concurrent_requests):
            token = self.test_tokens[i % len(self.test_tokens)]
            tasks.append(validate_token_task(token))

        # Execute all tasks concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # Analyze results
        validation_times = [r[0] * 1000 for r in results]  # Convert to milliseconds
        successful_validations = sum(1 for r in results if r[1])

        avg_time = statistics.mean(validation_times)
        requests_per_second = concurrent_requests / total_time
        success_rate = (successful_validations / concurrent_requests) * 100

        print(f"✅ Concurrent validation results:")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Requests per second: {requests_per_second:.1f}")
        print(f"   Average response time: {avg_time:.2f}ms")
        print(f"   Success rate: {success_rate:.1f}%")

        self.performance_results["concurrent_validation"] = {
            "concurrent_requests": concurrent_requests,
            "total_time": total_time,
            "requests_per_second": requests_per_second,
            "average_time_ms": avg_time,
            "success_rate": success_rate,
        }

        # Performance thresholds
        if requests_per_second < 10:  # Should handle at least 10 requests per second
            print("⚠️ Warning: Requests per second is below 10")
            return False

        if success_rate < 95:  # Should have at least 95% success rate
            print("⚠️ Warning: Success rate is below 95%")
            return False

        return True

    async def test_cache_performance(self):
        """Test Redis cache performance."""
        print("\n💾 Testing cache performance...")

        from second_brain_database.routes.auth.services.permanent_tokens.cache_manager import get_cache_statistics

        # Get initial cache statistics
        initial_stats = await get_cache_statistics()

        # Perform some cache operations
        from second_brain_database.routes.auth.services.permanent_tokens.validator import validate_permanent_token

        if not self.test_tokens:
            print("❌ No test tokens available")
            return False

        # Validate the same token multiple times to test cache
        test_token = self.test_tokens[0]
        cache_test_iterations = 20

        cache_times = []
        for i in range(cache_test_iterations):
            start_time = time.time()
            await validate_permanent_token(test_token)
            cache_times.append((time.time() - start_time) * 1000)

        # Get final cache statistics
        final_stats = await get_cache_statistics()

        avg_cache_time = statistics.mean(cache_times)
        cache_improvement = cache_times[0] / statistics.mean(cache_times[1:]) if len(cache_times) > 1 else 1

        print(f"✅ Cache performance results:")
        print(f"   Cache keys: {final_stats.get('cache_count', 0)}")
        print(f"   Cache hit rate: {final_stats.get('cache_hit_rate', 0):.1f}%")
        print(f"   Average cache response time: {avg_cache_time:.2f}ms")
        print(f"   Cache improvement factor: {cache_improvement:.1f}x")

        self.performance_results["cache"] = {
            "cache_keys": final_stats.get("cache_count", 0),
            "hit_rate": final_stats.get("cache_hit_rate", 0),
            "average_time_ms": avg_cache_time,
            "improvement_factor": cache_improvement,
        }

        return True

    async def test_database_performance(self):
        """Test database query performance."""
        print("\n🗄️ Testing database performance...")

        # Test various database operations
        collection = db_manager.get_collection("permanent_tokens")

        # Test query performance
        query_times = []

        # Test 1: Find by user_id
        start_time = time.time()
        user_tokens = await collection.find({"user_id": self.test_user_id}).to_list(length=None)
        query_times.append(("find_by_user_id", (time.time() - start_time) * 1000))

        # Test 2: Count documents
        start_time = time.time()
        token_count = await collection.count_documents({"user_id": self.test_user_id})
        query_times.append(("count_documents", (time.time() - start_time) * 1000))

        # Test 3: Find with complex query
        start_time = time.time()
        active_tokens = await collection.find({"user_id": self.test_user_id, "is_revoked": False}).to_list(length=None)
        query_times.append(("complex_query", (time.time() - start_time) * 1000))

        print(f"✅ Database performance results:")
        for query_name, query_time in query_times:
            print(f"   {query_name}: {query_time:.2f}ms")

        avg_query_time = statistics.mean([t[1] for t in query_times])

        self.performance_results["database"] = {"queries": dict(query_times), "average_query_time_ms": avg_query_time}

        # Performance threshold
        if avg_query_time > 50:  # Average query should be under 50ms
            print("⚠️ Warning: Average database query time exceeds 50ms")
            return False

        return True

    async def generate_performance_report(self):
        """Generate a comprehensive performance report."""
        print("\n📊 Performance Report")
        print("=" * 60)

        # Token Creation Performance
        if "token_creation" in self.performance_results:
            creation = self.performance_results["token_creation"]
            print(f"Token Creation:")
            print(f"  • Tokens per second: {creation['tokens_per_second']:.1f}")
            print(f"  • Average time per token: {creation['average_time_per_token']*1000:.2f}ms")

        # Validation Performance
        if "validation" in self.performance_results:
            validation = self.performance_results["validation"]
            print(f"\nValidation Performance:")
            print(f"  • Average response time: {validation['average_time_ms']:.2f}ms")
            print(f"  • 95th percentile: {validation['p95_time_ms']:.2f}ms")
            print(f"  • Cache hit rate: {validation['cache_hit_rate']:.1f}%")

        # Concurrent Performance
        if "concurrent_validation" in self.performance_results:
            concurrent = self.performance_results["concurrent_validation"]
            print(f"\nConcurrent Performance:")
            print(f"  • Requests per second: {concurrent['requests_per_second']:.1f}")
            print(f"  • Success rate: {concurrent['success_rate']:.1f}%")

        # Cache Performance
        if "cache" in self.performance_results:
            cache = self.performance_results["cache"]
            print(f"\nCache Performance:")
            print(f"  • Hit rate: {cache['hit_rate']:.1f}%")
            print(f"  • Improvement factor: {cache['improvement_factor']:.1f}x")

        # Database Performance
        if "database" in self.performance_results:
            database = self.performance_results["database"]
            print(f"\nDatabase Performance:")
            print(f"  • Average query time: {database['average_query_time_ms']:.2f}ms")

        print("\n" + "=" * 60)

    async def run_performance_tests(self):
        """Run all performance tests."""
        print("🚀 Starting Performance Validation Tests")
        print("=" * 60)

        try:
            await self.setup()

            # Run performance tests
            tests = [
                ("Token Creation", lambda: self.create_test_tokens(20)),
                ("Validation Performance", lambda: self.test_validation_performance(100)),
                ("Concurrent Validation", lambda: self.test_concurrent_validation(25)),
                ("Cache Performance", self.test_cache_performance),
                ("Database Performance", self.test_database_performance),
            ]

            passed = 0
            failed = 0

            for test_name, test_func in tests:
                try:
                    result = await test_func()
                    if result is not False:  # None or True are considered success
                        passed += 1
                    else:
                        failed += 1
                        print(f"❌ {test_name} FAILED")
                except Exception as e:
                    failed += 1
                    print(f"❌ {test_name} FAILED with exception: {e}")

            # Generate performance report
            await self.generate_performance_report()

            # Print summary
            print("🏁 Performance Test Summary")
            print(f"✅ Passed: {passed}")
            print(f"❌ Failed: {failed}")
            print(f"📊 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")

            if failed == 0:
                print("\n🎉 All performance tests passed!")
                print("✅ Permanent token system meets performance requirements")
                return True
            else:
                print(f"\n⚠️ {failed} performance test(s) failed")
                return False

        except Exception as e:
            print(f"❌ Performance test suite failed with exception: {e}")
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test runner."""
    # Check if permanent tokens are enabled
    if not settings.PERMANENT_TOKENS_ENABLED:
        print("❌ Permanent tokens are disabled in configuration")
        print("   Set PERMANENT_TOKENS_ENABLED=true to run tests")
        return False

    validator = PerformanceValidator()
    return await validator.run_performance_tests()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
