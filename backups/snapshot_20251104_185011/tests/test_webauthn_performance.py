#!/usr/bin/env python3
"""
WebAuthn performance tests following existing patterns.

Tests performance characteristics of WebAuthn operations including
challenge generation, credential storage/retrieval, and authentication flows.
"""

import asyncio
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from second_brain_database.database import db_manager
from second_brain_database.routes.auth.services.webauthn.challenge import (
    generate_secure_challenge,
    store_challenge,
    validate_challenge,
    clear_challenge,
)
from second_brain_database.routes.auth.services.webauthn.credentials import (
    store_credential,
    get_user_credentials,
    get_credential_by_id,
    update_credential_usage,
    deactivate_credential,
)


class WebAuthnPerformanceTest:
    """WebAuthn performance test suite."""

    def __init__(self):
        self.test_user_ids = []
        self.test_credentials = []
        self.performance_results = {}

    async def setup(self):
        """Set up performance test environment."""
        print("🔧 Setting up WebAuthn performance test environment...")
        
        # Connect to database
        await db_manager.connect()
        
        # Create test user IDs
        for i in range(10):
            self.test_user_ids.append(f"507f1f77bcf86cd79943{i:04d}")
        
        print("✅ WebAuthn performance test environment ready")

    async def cleanup(self):
        """Clean up performance test data."""
        print("🧹 Cleaning up WebAuthn performance test data...")
        
        try:
            # Clean up test credentials
            for credential_id in self.test_credentials:
                try:
                    await db_manager.get_collection("webauthn_credentials").delete_many(
                        {"credential_id": credential_id}
                    )
                except:
                    pass
            
            # Clean up test challenges
            await db_manager.get_collection("webauthn_challenges").delete_many(
                {"user_id": {"$in": self.test_user_ids}}
            )
            
        except Exception as e:
            print(f"⚠️ Cleanup warning: {e}")
        
        # Disconnect from database
        await db_manager.disconnect()
        
        print("✅ WebAuthn performance test cleanup complete")

    def test_challenge_generation_performance(self):
        """Test challenge generation performance."""
        print("\n⚡ Testing challenge generation performance...")
        
        iterations = 1000
        start_time = time.time()
        
        challenges = []
        for i in range(iterations):
            challenge = generate_secure_challenge()
            challenges.append(challenge)
        
        generation_time = time.time() - start_time
        challenges_per_second = iterations / generation_time
        
        # Verify all challenges are unique
        unique_challenges = len(set(challenges))
        uniqueness_rate = (unique_challenges / iterations) * 100
        
        print(f"✅ Challenge generation performance:")
        print(f"   Generated {iterations} challenges in {generation_time:.3f}s")
        print(f"   Rate: {challenges_per_second:.1f} challenges/second")
        print(f"   Uniqueness: {uniqueness_rate:.1f}%")
        
        self.performance_results["challenge_generation"] = {
            "iterations": iterations,
            "total_time": generation_time,
            "challenges_per_second": challenges_per_second,
            "uniqueness_rate": uniqueness_rate,
        }
        
        # Performance thresholds
        if challenges_per_second < 1000:
            print("⚠️ Warning: Challenge generation rate below 1000/second")
            return False
        
        if uniqueness_rate < 100:
            print("⚠️ Warning: Challenge uniqueness below 100%")
            return False
        
        return True

    async def test_challenge_storage_performance(self):
        """Test challenge storage and validation performance."""
        print("\n💾 Testing challenge storage performance...")
        
        iterations = 100
        challenges = []
        
        # Generate challenges
        for i in range(iterations):
            challenge = generate_secure_challenge()
            challenges.append(challenge)
        
        # Test storage performance
        start_time = time.time()
        
        for i, challenge in enumerate(challenges):
            user_id = self.test_user_ids[i % len(self.test_user_ids)]
            await store_challenge(challenge, user_id, "registration")
        
        storage_time = time.time() - start_time
        storage_rate = iterations / storage_time
        
        print(f"✅ Challenge storage performance:")
        print(f"   Stored {iterations} challenges in {storage_time:.3f}s")
        print(f"   Rate: {storage_rate:.1f} challenges/second")
        
        # Test validation performance
        start_time = time.time()
        
        validation_results = []
        for i, challenge in enumerate(challenges):
            user_id = self.test_user_ids[i % len(self.test_user_ids)]
            result = await validate_challenge(challenge, user_id, "registration")
            validation_results.append(result is not None)
        
        validation_time = time.time() - start_time
        validation_rate = iterations / validation_time
        success_rate = (sum(validation_results) / iterations) * 100
        
        print(f"✅ Challenge validation performance:")
        print(f"   Validated {iterations} challenges in {validation_time:.3f}s")
        print(f"   Rate: {validation_rate:.1f} validations/second")
        print(f"   Success rate: {success_rate:.1f}%")
        
        self.performance_results["challenge_storage"] = {
            "iterations": iterations,
            "storage_time": storage_time,
            "storage_rate": storage_rate,
            "validation_time": validation_time,
            "validation_rate": validation_rate,
            "success_rate": success_rate,
        }
        
        # Performance thresholds
        if storage_rate < 50:
            print("⚠️ Warning: Challenge storage rate below 50/second")
            return False
        
        if validation_rate < 100:
            print("⚠️ Warning: Challenge validation rate below 100/second")
            return False
        
        if success_rate < 95:
            print("⚠️ Warning: Challenge validation success rate below 95%")
            return False
        
        return True

    async def test_credential_storage_performance(self):
        """Test credential storage performance."""
        print("\n🔑 Testing credential storage performance...")
        
        iterations = 50
        credentials_data = []
        
        # Prepare test data
        for i in range(iterations):
            credential_data = {
                "user_id": self.test_user_ids[i % len(self.test_user_ids)],
                "credential_id": f"perf_test_credential_{i}",
                "public_key": f"test_public_key_data_{i}",
                "device_name": f"Test Device {i}",
                "authenticator_type": "platform" if i % 2 == 0 else "cross-platform",
            }
            credentials_data.append(credential_data)
        
        # Test storage performance
        start_time = time.time()
        
        for cred_data in credentials_data:
            result = await store_credential(**cred_data)
            if result:
                self.test_credentials.append(cred_data["credential_id"])
        
        storage_time = time.time() - start_time
        storage_rate = iterations / storage_time
        
        print(f"✅ Credential storage performance:")
        print(f"   Stored {iterations} credentials in {storage_time:.3f}s")
        print(f"   Rate: {storage_rate:.1f} credentials/second")
        
        self.performance_results["credential_storage"] = {
            "iterations": iterations,
            "storage_time": storage_time,
            "storage_rate": storage_rate,
        }
        
        # Performance threshold
        if storage_rate < 10:
            print("⚠️ Warning: Credential storage rate below 10/second")
            return False
        
        return True

    async def test_credential_retrieval_performance(self):
        """Test credential retrieval performance."""
        print("\n📋 Testing credential retrieval performance...")
        
        # Ensure we have credentials to retrieve
        if not self.test_credentials:
            await self.test_credential_storage_performance()
        
        # Test user credentials retrieval
        iterations = 100
        start_time = time.time()
        
        retrieval_results = []
        for i in range(iterations):
            user_id = self.test_user_ids[i % len(self.test_user_ids)]
            credentials = await get_user_credentials(user_id)
            retrieval_results.append(len(credentials))
        
        retrieval_time = time.time() - start_time
        retrieval_rate = iterations / retrieval_time
        avg_credentials_per_user = statistics.mean(retrieval_results) if retrieval_results else 0
        
        print(f"✅ User credentials retrieval performance:")
        print(f"   Retrieved for {iterations} users in {retrieval_time:.3f}s")
        print(f"   Rate: {retrieval_rate:.1f} retrievals/second")
        print(f"   Average credentials per user: {avg_credentials_per_user:.1f}")
        
        # Test single credential retrieval
        if self.test_credentials:
            single_retrieval_times = []
            
            for i in range(min(20, len(self.test_credentials))):
                credential_id = self.test_credentials[i]
                start_time = time.time()
                credential = await get_credential_by_id(credential_id)
                single_retrieval_times.append((time.time() - start_time) * 1000)  # Convert to ms
            
            avg_single_retrieval_time = statistics.mean(single_retrieval_times)
            
            print(f"✅ Single credential retrieval performance:")
            print(f"   Average time: {avg_single_retrieval_time:.2f}ms")
        
        self.performance_results["credential_retrieval"] = {
            "user_retrieval_iterations": iterations,
            "user_retrieval_time": retrieval_time,
            "user_retrieval_rate": retrieval_rate,
            "avg_credentials_per_user": avg_credentials_per_user,
            "avg_single_retrieval_time_ms": avg_single_retrieval_time if self.test_credentials else 0,
        }
        
        # Performance thresholds
        if retrieval_rate < 50:
            print("⚠️ Warning: User credentials retrieval rate below 50/second")
            return False
        
        if self.test_credentials and avg_single_retrieval_time > 100:
            print("⚠️ Warning: Single credential retrieval time above 100ms")
            return False
        
        return True

    async def test_credential_update_performance(self):
        """Test credential update performance."""
        print("\n🔄 Testing credential update performance...")
        
        if not self.test_credentials:
            await self.test_credential_storage_performance()
        
        # Test credential usage updates
        update_iterations = min(50, len(self.test_credentials))
        start_time = time.time()
        
        update_results = []
        for i in range(update_iterations):
            credential_id = self.test_credentials[i]
            new_sign_count = i + 1
            success = await update_credential_usage(credential_id, new_sign_count)
            update_results.append(success)
        
        update_time = time.time() - start_time
        update_rate = update_iterations / update_time
        success_rate = (sum(update_results) / update_iterations) * 100
        
        print(f"✅ Credential update performance:")
        print(f"   Updated {update_iterations} credentials in {update_time:.3f}s")
        print(f"   Rate: {update_rate:.1f} updates/second")
        print(f"   Success rate: {success_rate:.1f}%")
        
        self.performance_results["credential_update"] = {
            "iterations": update_iterations,
            "update_time": update_time,
            "update_rate": update_rate,
            "success_rate": success_rate,
        }
        
        # Performance thresholds
        if update_rate < 20:
            print("⚠️ Warning: Credential update rate below 20/second")
            return False
        
        if success_rate < 95:
            print("⚠️ Warning: Credential update success rate below 95%")
            return False
        
        return True

    async def test_concurrent_operations_performance(self):
        """Test concurrent WebAuthn operations performance."""
        print("\n⚡ Testing concurrent operations performance...")
        
        # Test concurrent challenge generation
        concurrent_challenges = 50
        
        async def generate_challenge_task():
            return generate_secure_challenge()
        
        start_time = time.time()
        tasks = [generate_challenge_task() for _ in range(concurrent_challenges)]
        challenges = await asyncio.gather(*tasks)
        concurrent_generation_time = time.time() - start_time
        
        concurrent_generation_rate = concurrent_challenges / concurrent_generation_time
        unique_challenges = len(set(challenges))
        
        print(f"✅ Concurrent challenge generation:")
        print(f"   Generated {concurrent_challenges} challenges concurrently in {concurrent_generation_time:.3f}s")
        print(f"   Rate: {concurrent_generation_rate:.1f} challenges/second")
        print(f"   Uniqueness: {unique_challenges}/{concurrent_challenges}")
        
        # Test concurrent credential retrieval
        if self.test_user_ids:
            concurrent_retrievals = 20
            
            async def retrieve_credentials_task(user_id):
                return await get_user_credentials(user_id)
            
            start_time = time.time()
            tasks = [retrieve_credentials_task(self.test_user_ids[i % len(self.test_user_ids)]) 
                    for i in range(concurrent_retrievals)]
            retrieval_results = await asyncio.gather(*tasks)
            concurrent_retrieval_time = time.time() - start_time
            
            concurrent_retrieval_rate = concurrent_retrievals / concurrent_retrieval_time
            
            print(f"✅ Concurrent credential retrieval:")
            print(f"   Retrieved for {concurrent_retrievals} users concurrently in {concurrent_retrieval_time:.3f}s")
            print(f"   Rate: {concurrent_retrieval_rate:.1f} retrievals/second")
        
        self.performance_results["concurrent_operations"] = {
            "concurrent_generation_rate": concurrent_generation_rate,
            "concurrent_retrieval_rate": concurrent_retrieval_rate if self.test_user_ids else 0,
            "challenge_uniqueness": unique_challenges / concurrent_challenges,
        }
        
        # Performance thresholds
        if concurrent_generation_rate < 100:
            print("⚠️ Warning: Concurrent challenge generation rate below 100/second")
            return False
        
        if self.test_user_ids and concurrent_retrieval_rate < 50:
            print("⚠️ Warning: Concurrent credential retrieval rate below 50/second")
            return False
        
        return True

    async def generate_performance_report(self):
        """Generate comprehensive performance report."""
        print("\n📊 WebAuthn Performance Report")
        print("=" * 60)
        
        # Challenge Generation Performance
        if "challenge_generation" in self.performance_results:
            gen = self.performance_results["challenge_generation"]
            print(f"Challenge Generation:")
            print(f"  • Rate: {gen['challenges_per_second']:.1f} challenges/second")
            print(f"  • Uniqueness: {gen['uniqueness_rate']:.1f}%")
        
        # Challenge Storage Performance
        if "challenge_storage" in self.performance_results:
            storage = self.performance_results["challenge_storage"]
            print(f"\nChallenge Storage:")
            print(f"  • Storage rate: {storage['storage_rate']:.1f} challenges/second")
            print(f"  • Validation rate: {storage['validation_rate']:.1f} validations/second")
            print(f"  • Success rate: {storage['success_rate']:.1f}%")
        
        # Credential Storage Performance
        if "credential_storage" in self.performance_results:
            cred_storage = self.performance_results["credential_storage"]
            print(f"\nCredential Storage:")
            print(f"  • Storage rate: {cred_storage['storage_rate']:.1f} credentials/second")
        
        # Credential Retrieval Performance
        if "credential_retrieval" in self.performance_results:
            retrieval = self.performance_results["credential_retrieval"]
            print(f"\nCredential Retrieval:")
            print(f"  • User retrieval rate: {retrieval['user_retrieval_rate']:.1f} users/second")
            print(f"  • Single credential time: {retrieval['avg_single_retrieval_time_ms']:.2f}ms")
        
        # Credential Update Performance
        if "credential_update" in self.performance_results:
            update = self.performance_results["credential_update"]
            print(f"\nCredential Updates:")
            print(f"  • Update rate: {update['update_rate']:.1f} updates/second")
            print(f"  • Success rate: {update['success_rate']:.1f}%")
        
        # Concurrent Operations Performance
        if "concurrent_operations" in self.performance_results:
            concurrent = self.performance_results["concurrent_operations"]
            print(f"\nConcurrent Operations:")
            print(f"  • Concurrent generation rate: {concurrent['concurrent_generation_rate']:.1f}/second")
            print(f"  • Concurrent retrieval rate: {concurrent['concurrent_retrieval_rate']:.1f}/second")
            print(f"  • Challenge uniqueness: {concurrent['challenge_uniqueness']:.3f}")
        
        print("\n" + "=" * 60)

    async def run_all_tests(self):
        """Run all WebAuthn performance tests."""
        print("🚀 Starting WebAuthn Performance Tests")
        print("=" * 60)
        
        try:
            await self.setup()
            
            # Run performance tests
            tests = [
                ("Challenge Generation Performance", self.test_challenge_generation_performance),
                ("Challenge Storage Performance", self.test_challenge_storage_performance),
                ("Credential Storage Performance", self.test_credential_storage_performance),
                ("Credential Retrieval Performance", self.test_credential_retrieval_performance),
                ("Credential Update Performance", self.test_credential_update_performance),
                ("Concurrent Operations Performance", self.test_concurrent_operations_performance),
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
            
            # Generate performance report
            await self.generate_performance_report()
            
            # Print summary
            print("🏁 WebAuthn Performance Test Summary")
            print(f"✅ Passed: {passed}")
            print(f"❌ Failed: {failed}")
            print(f"📊 Success Rate: {(passed / (passed + failed)) * 100:.1f}%")
            
            if failed == 0:
                print("\n🎉 All WebAuthn performance tests passed!")
                print("✅ WebAuthn system meets performance requirements")
                return True
            else:
                print(f"\n⚠️ {failed} WebAuthn performance test(s) failed")
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
    test_runner = WebAuthnPerformanceTest()
    return await test_runner.run_all_tests()


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)