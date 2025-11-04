#!/usr/bin/env python3
"""
Comprehensive performance tests for WebAuthn functionality following existing patterns.

This test suite provides performance testing for WebAuthn operations including
challenge generation, credential storage, authentication flows, and monitoring
to ensure the implementation meets performance requirements.
"""

import asyncio
import base64
import json
import os
import sys
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from fastapi.testclient import TestClient

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.main import app
from second_brain_database.routes.auth.services.webauthn.challenge import (
    generate_secure_challenge,
    store_challenge,
    validate_challenge,
)
from second_brain_database.routes.auth.services.webauthn.credentials import (
    store_credential,
    get_user_credentials,
    get_credential_by_id,
    deactivate_credential,
)


class WebAuthnPerformanceTestSuite:
    """Comprehensive WebAuthn performance test suite following existing patterns."""

    def __init__(self):
        self.client = TestClient(app)
        self.test_user = {
            "username": "webauthn_perf_test_user",
            "email": "webauthn_perf@example.com",
            "password": "TestPassword123!"
        }
        self.session_token = None
        self.performance_results = {}

    async def setup(self):
        """Set up performance test environment."""
        print("🔧 Setting up WebAuthn performance test environment...")

        # Connect to database
        await db_manager.connect()

        # Register and login test user
        self.client.post("/auth/register", json=self.test_user)
        login_data = {"username": self.test_user["username"], "password": self.test_user["password"]}
        response = self.client.post("/auth/login", data=login_data)

        if response.status_code == 200:
            token_data = response.json()
            self.session_token = token_data["access_token"]

        print("✅ WebAuthn performance test environment ready")

    async def cleanup(self):
        """Clean up performance test environment."""
        print("🧹 Cleaning up WebAuthn performance test data...")

        try:
            if hasattr(db_manager, "db") and db_manager.db:
                # Remove test user and related data
                await db_manager.db.users.delete_many({"username": self.test_user["username"]})
                await db_manager.db.webauthn_credentials.delete_many({"user_id": {"$regex": "webauthn_perf"}})
                await db_manager.db.webauthn_challenges.delete_many({"user_id": {"$regex": "webauthn_perf"}})

        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")

        await db_manager.disconnect()
        print("✅ WebAuthn performance test cleanup complete")

    def test_challenge_generation_performance(self):
        """Test challenge generation performance and scalability."""
        print("\n⚡ Testing challenge generation performance...")

        # Test single challenge generation
        start_time = time.time()
        challenge = generate_secure_challenge()
        single_generation_time = time.time() - start_time

        assert challenge, "Challenge should be generated"
        print(f"   Single challenge generation: {single_generation_time*1000:.2f}ms")

        # Test batch challenge generation
        batch_sizes = [10, 50, 100, 500, 1000]
        generation_times = []

        for batch_size in batch_sizes:
            start_time = time.time()
            challenges = []

            for _ in range(batch_size):
                challenge = generate_secure_challenge()
                challenges.append(challenge)

            batch_time = time.time() - start_time
            avg_time_per_challenge = (batch_time / batch_size) * 1000  # ms
            generation_times.append(avg_time_per_challenge)

            # Verify all challenges are unique
            assert len(set(challenges)) == batch_size, f"All {batch_size} challenges should be unique"

            print(f"   Batch {batch_size}: {batch_time:.3f}s total, {avg_time_per_challenge:.2f}ms avg per challenge")

        # Performance requirements
        assert single_generation_time < 0.01, f"Single challenge generation too slow: {single_generation_time}s"
        assert all(t < 5.0 for t in generation_times), "Average challenge generation should be < 5ms"

        self.performance_results["challenge_generation"] = {
            "single_time_ms": single_generation_time * 1000,
            "batch_times_ms": generation_times,
            "passed": True
        }

        print("✅ Challenge generation performance test passed")
        return True

    async def test_challenge_storage_performance(self):
        """Test challenge storage and validation performance."""
        print("\n💾 Testing challenge storage performance...")

        user_id = "507f1f77bcf86cd799439999"

        # Test single challenge storage
        challenge = generate_secure_challenge()
        start_time = time.time()
        success = await store_challenge(challenge, user_id, "registration")
        single_storage_time = time.time() - start_time

        assert success, "Challenge storage should succeed"
        print(f"   Single challenge storage: {single_storage_time*1000:.2f}ms")

        # Test challenge validation performance
        start_time = time.time()
        result = await validate_challenge(challenge, user_id, "registration")
        validation_time = time.time() - start_time

        assert result is not None, "Challenge validation should succeed"
        print(f"   Single challenge validation: {validation_time*1000:.2f}ms")

        # Test batch challenge operations
        batch_size = 100
        challenges = [generate_secure_challenge() for _ in range(batch_size)]

        # Batch storage
        start_time = time.time()
        for i, challenge in enumerate(challenges):
            await store_challenge(challenge, f"{user_id}_{i}", "registration")
        batch_storage_time = time.time() - start_time

        avg_storage_time = (batch_storage_time / batch_size) * 1000
        print(f"   Batch storage ({batch_size}): {batch_storage_time:.3f}s total, {avg_storage_time:.2f}ms avg")

        # Batch validation
        start_time = time.time()
        for i, challenge in enumerate(challenges):
            result = await validate_challenge(challenge, f"{user_id}_{i}", "registration")
            assert result is not None, f"Challenge {i} validation should succeed"
        batch_validation_time = time.time() - start_time

        avg_validation_time = (batch_validation_time / batch_size) * 1000
        print(f"   Batch validation ({batch_size}): {batch_validation_time:.3f}s total, {avg_validation_time:.2f}ms avg")

        # Performance requirements
        assert single_storage_time < 0.1, f"Single challenge storage too slow: {single_storage_time}s"
        assert validation_time < 0.1, f"Single challenge validation too slow: {validation_time}s"
        assert avg_storage_time < 50, f"Average challenge storage too slow: {avg_storage_time}ms"
        assert avg_validation_time < 50, f"Average challenge validation too slow: {avg_validation_time}ms"

        self.performance_results["challenge_storage"] = {
            "single_storage_ms": single_storage_time * 1000,
            "single_validation_ms": validation_time * 1000,
            "avg_storage_ms": avg_storage_time,
            "avg_validation_ms": avg_validation_time,
            "passed": True
        }

        print("✅ Challenge storage performance test passed")
        return True

    async def test_credential_storage_performance(self):
        """Test credential storage and retrieval performance."""
        print("\n🔐 Testing credential storage performance...")

        base_user_id = "507f1f77bcf86cd799440000"

        # Test single credential storage
        start_time = time.time()
        result = await store_credential(
            user_id=base_user_id,
            credential_id="perf_test_credential_single",
            public_key="test_public_key_single",
            device_name="Performance Test Device Single"
        )
        single_storage_time = time.time() - start_time

        assert result is not None, "Credential storage should succeed"
        print(f"   Single credential storage: {single_storage_time*1000:.2f}ms")

        # Test single credential retrieval
        start_time = time.time()
        retrieved_cred = await get_credential_by_id("perf_test_credential_single")
        single_retrieval_time = time.time() - start_time

        assert retrieved_cred is not None, "Credential retrieval should succeed"
        print(f"   Single credential retrieval: {single_retrieval_time*1000:.2f}ms")

        # Test batch credential storage
        batch_size = 50
        stored_credentials = []

        start_time = time.time()
        for i in range(batch_size):
            user_id = f"{base_user_id}_{i}"
            credential_id = f"perf_test_credential_{i}"

            result = await store_credential(
                user_id=user_id,
                credential_id=credential_id,
                public_key=f"test_public_key_{i}",
                device_name=f"Performance Test Device {i}"
            )
            stored_credentials.append((user_id, credential_id))
            assert result is not None, f"Credential {i} storage should succeed"

        batch_storage_time = time.time() - start_time
        avg_storage_time = (batch_storage_time / batch_size) * 1000

        print(f"   Batch storage ({batch_size}): {batch_storage_time:.3f}s total, {avg_storage_time:.2f}ms avg")

        # Test batch credential retrieval by user
        user_retrieval_times = []
        for i in range(min(10, batch_size)):  # Test first 10 users
            user_id = f"{base_user_id}_{i}"

            start_time = time.time()
            user_credentials = await get_user_credentials(user_id)
            retrieval_time = time.time() - start_time

            user_retrieval_times.append(retrieval_time * 1000)
            assert len(user_credentials) == 1, f"User {i} should have 1 credential"

        avg_user_retrieval_time = statistics.mean(user_retrieval_times)
        print(f"   User credential retrieval: {avg_user_retrieval_time:.2f}ms avg")

        # Test batch credential retrieval by ID
        id_retrieval_times = []
        for i in range(min(10, batch_size)):  # Test first 10 credentials
            credential_id = f"perf_test_credential_{i}"

            start_time = time.time()
            credential = await get_credential_by_id(credential_id)
            retrieval_time = time.time() - start_time

            id_retrieval_times.append(retrieval_time * 1000)
            assert credential is not None, f"Credential {i} should be retrievable"

        avg_id_retrieval_time = statistics.mean(id_retrieval_times)
        print(f"   ID credential retrieval: {avg_id_retrieval_time:.2f}ms avg")

        # Performance requirements
        assert single_storage_time < 0.2, f"Single credential storage too slow: {single_storage_time}s"
        assert single_retrieval_time < 0.1, f"Single credential retrieval too slow: {single_retrieval_time}s"
        assert avg_storage_time < 100, f"Average credential storage too slow: {avg_storage_time}ms"
        assert avg_user_retrieval_time < 50, f"Average user retrieval too slow: {avg_user_retrieval_time}ms"
        assert avg_id_retrieval_time < 50, f"Average ID retrieval too slow: {avg_id_retrieval_time}ms"

        # Clean up
        for user_id, credential_id in stored_credentials:
            await deactivate_credential(credential_id, user_id)
        await deactivate_credential("perf_test_credential_single", base_user_id)

        self.performance_results["credential_storage"] = {
            "single_storage_ms": single_storage_time * 1000,
            "single_retrieval_ms": single_retrieval_time * 1000,
            "avg_storage_ms": avg_storage_time,
            "avg_user_retrieval_ms": avg_user_retrieval_time,
            "avg_id_retrieval_ms": avg_id_retrieval_time,
            "passed": True
        }

        print("✅ Credential storage performance test passed")
        return True

    def test_endpoint_performance(self):
        """Test WebAuthn endpoint performance."""
        print("\n🌐 Testing WebAuthn endpoint performance...")

        if not self.session_token:
            print("❌ No session token available")
            return False

        headers = {"Authorization": f"Bearer {self.session_token}"}

        # Test registration begin endpoint performance
        registration_request = {
            "device_name": "Performance Test Device",
            "authenticator_type": "platform"
        }

        registration_times = []
        for i in range(10):
            start_time = time.time()
            response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
            request_time = time.time() - start_time

            registration_times.append(request_time * 1000)
            assert response.status_code == 200, f"Registration begin {i} should succeed"

        avg_registration_time = statistics.mean(registration_times)
        max_registration_time = max(registration_times)
        print(f"   Registration begin: {avg_registration_time:.2f}ms avg, {max_registration_time:.2f}ms max")

        # Test authentication begin endpoint performance
        auth_request = {"username": self.test_user["username"]}

        # First register a credential for authentication tests
        response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
        if response.status_code == 200:
            registration_data = response.json()
            challenge = registration_data["challenge"]

            # Complete registration
            mock_credential = {
                "id": "perf_test_credential_auth",
                "rawId": "perf_test_credential_auth",
                "type": "public-key",
                "response": {
                    "attestationObject": self._create_mock_attestation_object(),
                    "clientDataJSON": self._create_mock_client_data_json(challenge, "webauthn.create")
                }
            }

            complete_request = {
                "credential": mock_credential,
                "device_name": "Performance Test Device"
            }

            self.client.post("/auth/webauthn/register/complete", json=complete_request, headers=headers)

        # Now test authentication begin performance
        auth_times = []
        for i in range(10):
            start_time = time.time()
            response = self.client.post("/auth/webauthn/authenticate/begin", json=auth_request)
            request_time = time.time() - start_time

            auth_times.append(request_time * 1000)
            assert response.status_code == 200, f"Authentication begin {i} should succeed"

        avg_auth_time = statistics.mean(auth_times)
        max_auth_time = max(auth_times)
        print(f"   Authentication begin: {avg_auth_time:.2f}ms avg, {max_auth_time:.2f}ms max")

        # Test credentials list endpoint performance
        list_times = []
        for i in range(10):
            start_time = time.time()
            response = self.client.get("/auth/webauthn/credentials", headers=headers)
            request_time = time.time() - start_time

            list_times.append(request_time * 1000)
            assert response.status_code == 200, f"Credentials list {i} should succeed"

        avg_list_time = statistics.mean(list_times)
        max_list_time = max(list_times)
        print(f"   Credentials list: {avg_list_time:.2f}ms avg, {max_list_time:.2f}ms max")

        # Performance requirements
        assert avg_registration_time < 500, f"Average registration time too slow: {avg_registration_time}ms"
        assert max_registration_time < 1000, f"Max registration time too slow: {max_registration_time}ms"
        assert avg_auth_time < 300, f"Average authentication time too slow: {avg_auth_time}ms"
        assert max_auth_time < 800, f"Max authentication time too slow: {max_auth_time}ms"
        assert avg_list_time < 200, f"Average list time too slow: {avg_list_time}ms"
        assert max_list_time < 500, f"Max list time too slow: {max_list_time}ms"

        self.performance_results["endpoint_performance"] = {
            "avg_registration_ms": avg_registration_time,
            "max_registration_ms": max_registration_time,
            "avg_auth_ms": avg_auth_time,
            "max_auth_ms": max_auth_time,
            "avg_list_ms": avg_list_time,
            "max_list_ms": max_list_time,
            "passed": True
        }

        print("✅ Endpoint performance test passed")
        return True

    def test_concurrent_operations_performance(self):
        """Test performance under concurrent operations."""
        print("\n🔄 Testing concurrent operations performance...")

        if not self.session_token:
            print("❌ No session token available")
            return False

        headers = {"Authorization": f"Bearer {self.session_token}"}

        # Test concurrent registration begin requests
        registration_request = {
            "device_name": "Concurrent Test Device",
            "authenticator_type": "platform"
        }

        concurrent_count = 5

        def make_registration_request():
            start_time = time.time()
            response = self.client.post("/auth/webauthn/register/begin", json=registration_request, headers=headers)
            request_time = time.time() - start_time
            return response.status_code, request_time * 1000

        # Simulate concurrent requests using threading
        import threading
        results = []
        threads = []

        start_time = time.time()

        for i in range(concurrent_count):
            thread = threading.Thread(target=lambda: results.append(make_registration_request()))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        total_concurrent_time = time.time() - start_time

        # Analyze results
        successful_requests = sum(1 for status_code, _ in results if status_code == 200)
        request_times = [req_time for _, req_time in results]
        avg_concurrent_time = statistics.mean(request_times)
        max_concurrent_time = max(request_times)

        print(f"   Concurrent requests: {successful_requests}/{concurrent_count} successful")
        print(f"   Total time: {total_concurrent_time*1000:.2f}ms")
        print(f"   Average request time: {avg_concurrent_time:.2f}ms")
        print(f"   Max request time: {max_concurrent_time:.2f}ms")

        # Performance requirements
        assert successful_requests >= concurrent_count * 0.8, "At least 80% of concurrent requests should succeed"
        assert avg_concurrent_time < 1000, f"Average concurrent request time too slow: {avg_concurrent_time}ms"
        assert max_concurrent_time < 2000, f"Max concurrent request time too slow: {max_concurrent_time}ms"

        self.performance_results["concurrent_operations"] = {
            "successful_requests": successful_requests,
            "total_requests": concurrent_count,
            "total_time_ms": total_concurrent_time * 1000,
            "avg_request_time_ms": avg_concurrent_time,
            "max_request_time_ms": max_concurrent_time,
            "passed": True
        }

        print("✅ Concurrent operations performance test passed")
        return True

    def test_memory_usage_performance(self):
        """Test memory usage during WebAuthn operations."""
        print("\n🧠 Testing memory usage performance...")

        import psutil
        import gc

        # Get initial memory usage
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        print(f"   Initial memory usage: {initial_memory:.2f} MB")

        # Perform memory-intensive operations
        challenges = []
        for i in range(1000):
            challenge = generate_secure_challenge()
            challenges.append(challenge)

        after_challenges_memory = process.memory_info().rss / 1024 / 1024
        print(f"   After 1000 challenges: {after_challenges_memory:.2f} MB")

        # Clear challenges and force garbage collection
        challenges.clear()
        gc.collect()

        after_gc_memory = process.memory_info().rss / 1024 / 1024
        print(f"   After garbage collection: {after_gc_memory:.2f} MB")

        # Memory usage requirements
        memory_increase = after_challenges_memory - initial_memory
        memory_after_gc = after_gc_memory - initial_memory

        assert memory_increase < 50, f"Memory increase too high: {memory_increase:.2f} MB"
        assert memory_after_gc < 10, f"Memory not properly released: {memory_after_gc:.2f} MB"

        self.performance_results["memory_usage"] = {
            "initial_mb": initial_memory,
            "peak_mb": after_challenges_memory,
            "after_gc_mb": after_gc_memory,
            "increase_mb": memory_increase,
            "retained_mb": memory_after_gc,
            "passed": True
        }

        print("✅ Memory usage performance test passed")
        return True

    def _create_mock_attestation_object(self):
        """Create a mock attestation object for testing."""
        mock_data = {
            "fmt": "none",
            "attStmt": {},
            "authData": "mock_authenticator_data_with_credential_info"
        }
        return base64.b64encode(json.dumps(mock_data).encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    def _create_mock_client_data_json(self, challenge, type_):
        """Create mock client data JSON for testing."""
        client_data = {
            "type": type_,
            "challenge": challenge,
            "origin": "http://testserver",
            "crossOrigin": False
        }
        return base64.b64encode(json.dumps(client_data).encode()).decode().rstrip("=").replace("+", "-").replace("/", "_")

    def _print_performance_summary(self):
        """Print comprehensive performance test summary."""
        print("\n" + "=" * 70)
        print("📊 WebAuthn Performance Test Summary")
        print("=" * 70)

        for test_name, results in self.performance_results.items():
            status = "✅ PASSED" if results["passed"] else "❌ FAILED"
            print(f"\n{test_name.replace('_', ' ').title()}: {status}")

            # Print key metrics for each test
            if test_name == "challenge_generation":
                print(f"  Single generation: {results['single_time_ms']:.2f}ms")
                print(f"  Batch average: {min(results['batch_times_ms']):.2f}ms - {max(results['batch_times_ms']):.2f}ms")

            elif test_name == "challenge_storage":
                print(f"  Storage: {results['single_storage_ms']:.2f}ms single, {results['avg_storage_ms']:.2f}ms avg")
                print(f"  Validation: {results['single_validation_ms']:.2f}ms single, {results['avg_validation_ms']:.2f}ms avg")

            elif test_name == "credential_storage":
                print(f"  Storage: {results['single_storage_ms']:.2f}ms single, {results['avg_storage_ms']:.2f}ms avg")
                print(f"  Retrieval: {results['single_retrieval_ms']:.2f}ms single, {results['avg_user_retrieval_ms']:.2f}ms avg")

            elif test_name == "endpoint_performance":
                print(f"  Registration: {results['avg_registration_ms']:.2f}ms avg, {results['max_registration_ms']:.2f}ms max")
                print(f"  Authentication: {results['avg_auth_ms']:.2f}ms avg, {results['max_auth_ms']:.2f}ms max")
                print(f"  List: {results['avg_list_ms']:.2f}ms avg, {results['max_list_ms']:.2f}ms max")

            elif test_name == "concurrent_operations":
                print(f"  Success rate: {results['successful_requests']}/{results['total_requests']}")
                print(f"  Average time: {results['avg_request_time_ms']:.2f}ms")

            elif test_name == "memory_usage":
                print(f"  Peak usage: {results['peak_mb']:.2f} MB")
                print(f"  Memory increase: {results['increase_mb']:.2f} MB")
                print(f"  Retained after GC: {results['retained_mb']:.2f} MB")

    async def run_all_tests(self):
        """Run all WebAuthn performance tests."""
        print("🚀 Starting WebAuthn Performance Tests")
        print("=" * 70)

        try:
            await self.setup()

            # Run tests in sequence
            tests = [
                ("Challenge Generation Performance", self.test_challenge_generation_performance),
                ("Challenge Storage Performance", self.test_challenge_storage_performance),
                ("Credential Storage Performance", self.test_credential_storage_performance),
                ("Endpoint Performance", self.test_endpoint_performance),
                ("Concurrent Operations Performance", self.test_concurrent_operations_performance),
                ("Memory Usage Performance", self.test_memory_usage_performance),
            ]

            passed = 0
            failed = 0

            for test_name, test_func in tests:
                try:
                    if asyncio.iscoroutinefunction(test_func):
                        result = await test_func()
                    else:
                        result = test_func()

                    if result is not False:
                        passed += 1
                    else:
                        failed += 1
                        print(f"❌ {test_name} FAILED")
                except Exception as e:
                    failed += 1
                    print(f"❌ {test_name} FAILED with exception: {e}")
                    import traceback
                    traceback.print_exc()

            # Print detailed performance summary
            self._print_performance_summary()

            print(f"\n🏁 Performance Test Results: {passed} passed, {failed} failed")

            if failed == 0:
                print("\n🎉 All WebAuthn performance tests passed!")
                print("✅ WebAuthn implementation meets performance requirements")
                return True
            else:
                print(f"\n⚠️ {failed} performance test(s) failed")
                return False

        except Exception as e:
            print(f"❌ WebAuthn performance test suite failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test runner."""
    test_runner = WebAuthnPerformanceTestSuite()
    return await test_runner.run_all_tests()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
