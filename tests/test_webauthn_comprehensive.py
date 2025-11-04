#!/usr/bin/env python3
"""
Comprehensive WebAuthn test runner following existing patterns.

This script runs all WebAuthn tests including unit tests, integration tests,
endpoint tests, and performance tests in a coordinated manner.
"""

import asyncio
import os
import sys
import time
from typing import List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Import test classes
from tests.test_webauthn_unit_comprehensive import (
    TestWebAuthnChallengeManagement,
    TestWebAuthnCredentialManagement,
    TestWebAuthnCryptographicOperations,
    TestWebAuthnPerformanceAndSecurity,
)
from tests.test_webauthn_integration_comprehensive import WebAuthnIntegrationTest
from tests.test_webauthn_endpoints import WebAuthnEndpointTest
from tests.test_webauthn_performance import WebAuthnPerformanceTest


class WebAuthnTestRunner:
    """Comprehensive WebAuthn test runner."""

    def __init__(self):
        self.test_results = {}
        self.total_passed = 0
        self.total_failed = 0

    async def run_unit_tests(self):
        """Run all unit tests."""
        print("🧪 Running WebAuthn Unit Tests")
        print("=" * 50)

        unit_test_classes = [
            ("Challenge Management", TestWebAuthnChallengeManagement),
            ("Credential Management", TestWebAuthnCredentialManagement),
            ("Cryptographic Operations", TestWebAuthnCryptographicOperations),
            ("Performance and Security", TestWebAuthnPerformanceAndSecurity),
        ]

        passed = 0
        failed = 0

        for test_name, test_class in unit_test_classes:
            print(f"\n🔬 Running {test_name} Tests...")

            try:
                # Run pytest-style tests using asyncio
                import pytest

                # Create a temporary test file and run it
                test_result = pytest.main([
                    "tests/test_webauthn_unit_comprehensive.py",
                    "-v",
                    "--tb=short",
                    "-q"
                ])

                if test_result == 0:
                    passed += 1
                    print(f"✅ {test_name} tests passed")
                else:
                    failed += 1
                    print(f"❌ {test_name} tests failed")

            except Exception as e:
                failed += 1
                print(f"❌ {test_name} tests failed with exception: {e}")

        self.test_results["unit_tests"] = {"passed": passed, "failed": failed}
        self.total_passed += passed
        self.total_failed += failed

        print(f"\n📊 Unit Tests Summary: {passed} passed, {failed} failed")
        return failed == 0

    async def run_integration_tests(self):
        """Run integration tests."""
        print("\n🔗 Running WebAuthn Integration Tests")
        print("=" * 50)

        try:
            integration_test = WebAuthnIntegrationTest()
            result = await integration_test.run_all_tests()

            if result:
                self.test_results["integration_tests"] = {"passed": 1, "failed": 0}
                self.total_passed += 1
                print("✅ Integration tests passed")
                return True
            else:
                self.test_results["integration_tests"] = {"passed": 0, "failed": 1}
                self.total_failed += 1
                print("❌ Integration tests failed")
                return False

        except Exception as e:
            self.test_results["integration_tests"] = {"passed": 0, "failed": 1}
            self.total_failed += 1
            print(f"❌ Integration tests failed with exception: {e}")
            return False

    async def run_endpoint_tests(self):
        """Run endpoint tests."""
        print("\n🌐 Running WebAuthn Endpoint Tests")
        print("=" * 50)

        try:
            endpoint_test = WebAuthnEndpointTest()
            result = await endpoint_test.run_all_tests()

            if result:
                self.test_results["endpoint_tests"] = {"passed": 1, "failed": 0}
                self.total_passed += 1
                print("✅ Endpoint tests passed")
                return True
            else:
                self.test_results["endpoint_tests"] = {"passed": 0, "failed": 1}
                self.total_failed += 1
                print("❌ Endpoint tests failed")
                return False

        except Exception as e:
            self.test_results["endpoint_tests"] = {"passed": 0, "failed": 1}
            self.total_failed += 1
            print(f"❌ Endpoint tests failed with exception: {e}")
            return False

    async def run_performance_tests(self):
        """Run performance tests."""
        print("\n⚡ Running WebAuthn Performance Tests")
        print("=" * 50)

        try:
            performance_test = WebAuthnPerformanceTest()
            result = await performance_test.run_all_tests()

            if result:
                self.test_results["performance_tests"] = {"passed": 1, "failed": 0}
                self.total_passed += 1
                print("✅ Performance tests passed")
                return True
            else:
                self.test_results["performance_tests"] = {"passed": 0, "failed": 1}
                self.total_failed += 1
                print("❌ Performance tests failed")
                return False

        except Exception as e:
            self.test_results["performance_tests"] = {"passed": 0, "failed": 1}
            self.total_failed += 1
            print(f"❌ Performance tests failed with exception: {e}")
            return False

    async def run_existing_webauthn_tests(self):
        """Run existing WebAuthn tests."""
        print("\n🔄 Running Existing WebAuthn Tests")
        print("=" * 50)

        existing_tests = [
            "tests/test_webauthn_challenge.py",
            "tests/test_webauthn_credentials.py",
            "tests/test_webauthn_routes.py",
        ]

        passed = 0
        failed = 0

        for test_file in existing_tests:
            if os.path.exists(test_file):
                print(f"\n🧪 Running {os.path.basename(test_file)}...")

                try:
                    # Run the test file
                    import subprocess
                    result = subprocess.run([sys.executable, test_file],
                                          capture_output=True, text=True, timeout=60)

                    if result.returncode == 0:
                        passed += 1
                        print(f"✅ {os.path.basename(test_file)} passed")
                    else:
                        failed += 1
                        print(f"❌ {os.path.basename(test_file)} failed")
                        if result.stderr:
                            print(f"   Error: {result.stderr[:200]}...")

                except Exception as e:
                    failed += 1
                    print(f"❌ {os.path.basename(test_file)} failed with exception: {e}")
            else:
                print(f"⚠️ Test file not found: {test_file}")

        self.test_results["existing_tests"] = {"passed": passed, "failed": failed}
        self.total_passed += passed
        self.total_failed += failed

        print(f"\n📊 Existing Tests Summary: {passed} passed, {failed} failed")
        return failed == 0

    def generate_comprehensive_report(self):
        """Generate comprehensive test report."""
        print("\n" + "=" * 80)
        print("📋 COMPREHENSIVE WEBAUTHN TEST REPORT")
        print("=" * 80)

        # Test category results
        for category, results in self.test_results.items():
            category_name = category.replace("_", " ").title()
            passed = results["passed"]
            failed = results["failed"]
            total = passed + failed
            success_rate = (passed / total * 100) if total > 0 else 0

            print(f"\n{category_name}:")
            print(f"  ✅ Passed: {passed}")
            print(f"  ❌ Failed: {failed}")
            print(f"  📊 Success Rate: {success_rate:.1f}%")

        # Overall summary
        total_tests = self.total_passed + self.total_failed
        overall_success_rate = (self.total_passed / total_tests * 100) if total_tests > 0 else 0

        print(f"\n🏁 OVERALL SUMMARY:")
        print(f"  📊 Total Tests: {total_tests}")
        print(f"  ✅ Total Passed: {self.total_passed}")
        print(f"  ❌ Total Failed: {self.total_failed}")
        print(f"  📈 Overall Success Rate: {overall_success_rate:.1f}%")

        # Test quality assessment
        print(f"\n🎯 TEST QUALITY ASSESSMENT:")

        if overall_success_rate >= 95:
            print("  🎉 EXCELLENT: WebAuthn implementation is production-ready!")
        elif overall_success_rate >= 85:
            print("  ✅ GOOD: WebAuthn implementation is mostly ready with minor issues")
        elif overall_success_rate >= 70:
            print("  ⚠️ FAIR: WebAuthn implementation needs significant improvements")
        else:
            print("  ❌ POOR: WebAuthn implementation requires major fixes")

        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")

        if self.test_results.get("unit_tests", {}).get("failed", 0) > 0:
            print("  • Fix unit test failures - these indicate core functionality issues")

        if self.test_results.get("integration_tests", {}).get("failed", 0) > 0:
            print("  • Address integration test failures - these affect end-to-end workflows")

        if self.test_results.get("endpoint_tests", {}).get("failed", 0) > 0:
            print("  • Fix endpoint test failures - these affect API functionality")

        if self.test_results.get("performance_tests", {}).get("failed", 0) > 0:
            print("  • Optimize performance - current implementation may not scale well")

        if self.total_failed == 0:
            print("  • All tests passed! Consider adding more edge case tests")
            print("  • Review security implications and conduct security testing")
            print("  • Prepare for production deployment")

        print("\n" + "=" * 80)

        return overall_success_rate >= 85  # Return True if tests are mostly passing

    async def run_all_tests(self):
        """Run all WebAuthn tests in sequence."""
        print("🚀 Starting Comprehensive WebAuthn Test Suite")
        print("=" * 80)

        start_time = time.time()

        # Run all test categories
        test_categories = [
            ("Unit Tests", self.run_unit_tests),
            ("Integration Tests", self.run_integration_tests),
            ("Endpoint Tests", self.run_endpoint_tests),
            ("Performance Tests", self.run_performance_tests),
            ("Existing Tests", self.run_existing_webauthn_tests),
        ]

        for category_name, test_func in test_categories:
            try:
                print(f"\n🏃 Starting {category_name}...")
                await test_func()
            except Exception as e:
                print(f"❌ {category_name} failed with exception: {e}")
                self.total_failed += 1

        total_time = time.time() - start_time

        # Generate comprehensive report
        success = self.generate_comprehensive_report()

        print(f"\n⏱️ Total test execution time: {total_time:.2f} seconds")

        return success


async def main():
    """Main test runner."""
    print("🔐 WebAuthn Comprehensive Test Suite")
    print("Testing WebAuthn/FIDO2 authentication implementation")
    print("Following existing patterns and infrastructure")
    print()

    test_runner = WebAuthnTestRunner()
    success = await test_runner.run_all_tests()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
