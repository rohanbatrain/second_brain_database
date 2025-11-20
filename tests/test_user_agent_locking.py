#!/usr/bin/env python3
"""
Comprehensive test script for User Agent based locking functionality.

This script tests the complete User Agent lockdown system including:
- Enabling/disabling User Agent lockdown
- Adding/removing trusted User Agents
- Testing access with trusted vs untrusted User Agents
- Temporary bypass functionality (allow-once)
- Integration with authentication system
"""

import asyncio
from datetime import datetime, timedelta
import json
import sys
import time
from unittest.mock import MagicMock

from bson import ObjectId

# Add the src directory to the path
sys.path.insert(0, "src")

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager

logger = get_logger(prefix="[USER_AGENT_TEST]")


class UserAgentLockdownTester:
    """Test class for User Agent lockdown functionality."""

    def __init__(self):
        self.test_users = []
        self.users_collection = None

    async def setup(self):
        """Setup test environment."""
        logger.info("Setting up User Agent lockdown test environment...")
        await db_manager.connect()
        self.users_collection = db_manager.get_collection("users")

        # Clean up any existing test users
        await self.users_collection.delete_many({"username": {"$regex": "^ua_test_user_"}})
        logger.info("Test environment setup complete")

    async def cleanup(self):
        """Clean up test data."""
        logger.info("Cleaning up test data...")
        if self.test_users:
            await self.users_collection.delete_many({"_id": {"$in": self.test_users}})
        await db_manager.disconnect()
        logger.info("Cleanup complete")

    def create_mock_request(self, user_agent: str, ip: str = "192.168.1.100") -> MagicMock:
        """Create a mock FastAPI request object."""
        mock_request = MagicMock()
        mock_request.headers = {"user-agent": user_agent}
        mock_request.client = MagicMock()
        mock_request.client.host = ip
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/test"
        return mock_request

    async def create_test_user(
        self, username_suffix: str, user_agent_lockdown: bool = False, trusted_user_agents: list = None
    ) -> dict:
        """Create a test user with specified User Agent lockdown settings."""
        user_id = ObjectId()
        timestamp = int(datetime.utcnow().timestamp())

        user = {
            "_id": user_id,
            "username": f"ua_test_user_{username_suffix}_{timestamp}",
            "email": f"ua_test_{username_suffix}_{timestamp}@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "trusted_user_agent_lockdown": user_agent_lockdown,
            "trusted_user_agents": trusted_user_agents or [],
            "trusted_user_agent_lockdown_codes": [],
            "temporary_user_agent_access_tokens": [],
        }

        await self.users_collection.insert_one(user)
        self.test_users.append(user_id)
        logger.info(f"Created test user: {user['username']} (lockdown: {user_agent_lockdown})")
        return user

    async def test_basic_user_agent_lockdown(self):
        """Test basic User Agent lockdown functionality."""
        logger.info("=== Testing Basic User Agent Lockdown ===")

        # Test 1: User without lockdown should allow any User Agent
        user_no_lockdown = await self.create_test_user("no_lockdown", False)
        request = self.create_mock_request("AnyBrowser/1.0")

        try:
            await security_manager.check_user_agent_lockdown(request, user_no_lockdown)
            logger.info("✅ User without lockdown allows any User Agent")
        except Exception as e:
            logger.error(f"❌ User without lockdown should allow any User Agent: {e}")
            return False

        # Test 2: User with lockdown but no trusted User Agents should block all
        user_lockdown_empty = await self.create_test_user("lockdown_empty", True, [])

        try:
            await security_manager.check_user_agent_lockdown(request, user_lockdown_empty)
            logger.error("❌ User with lockdown but no trusted User Agents should block all requests")
            return False
        except Exception:
            logger.info("✅ User with lockdown but no trusted User Agents correctly blocks requests")

        # Test 3: User with lockdown and trusted User Agents
        trusted_user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "TrustedApp/1.0",
            "TestBrowser/2.0",
        ]
        user_with_trusted = await self.create_test_user("with_trusted", True, trusted_user_agents)

        # Test with trusted User Agent (should pass)
        trusted_request = self.create_mock_request("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        try:
            await security_manager.check_user_agent_lockdown(trusted_request, user_with_trusted)
            logger.info("✅ Trusted User Agent allowed through lockdown")
        except Exception as e:
            logger.error(f"❌ Trusted User Agent should be allowed: {e}")
            return False

        # Test with untrusted User Agent (should block)
        untrusted_request = self.create_mock_request("UntrustedBrowser/1.0")
        try:
            await security_manager.check_user_agent_lockdown(untrusted_request, user_with_trusted)
            logger.error("❌ Untrusted User Agent should be blocked")
            return False
        except Exception:
            logger.info("✅ Untrusted User Agent correctly blocked")

        return True

    async def test_user_agent_extraction(self):
        """Test User Agent extraction from different request formats."""
        logger.info("=== Testing User Agent Extraction ===")

        test_cases = [
            ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Standard browser User Agent"),
            ("TrustedApp/1.0", "Simple app User Agent"),
            ("", "Empty User Agent"),
            (None, "Missing User Agent header"),
        ]

        for user_agent, description in test_cases:
            mock_request = MagicMock()
            if user_agent is None:
                mock_request.headers = {}
            else:
                mock_request.headers = {"user-agent": user_agent}

            extracted = security_manager.get_client_user_agent(mock_request)
            logger.info(f"✅ {description}: '{extracted}'")

        return True

    async def test_temporary_bypass_functionality(self):
        """Test temporary User Agent bypass (allow-once) functionality."""
        logger.info("=== Testing Temporary User Agent Bypass ===")

        # Create user with lockdown enabled
        user_with_lockdown = await self.create_test_user("bypass_test", True, ["TrustedBrowser/1.0"])

        # Add temporary bypass for specific User Agent
        bypass_user_agent = "TemporaryBrowser/1.0"
        temporary_bypass = {
            "user_agent": bypass_user_agent,
            "expires_at": (datetime.utcnow() + timedelta(minutes=5)).isoformat(),
            "created_at": datetime.utcnow().isoformat(),
            "reason": "temporary_access",
        }

        # Update user with temporary bypass
        await self.users_collection.update_one(
            {"_id": user_with_lockdown["_id"]}, {"$push": {"temporary_user_agent_bypasses": temporary_bypass}}
        )

        # Refresh user data
        updated_user = await self.users_collection.find_one({"_id": user_with_lockdown["_id"]})

        # Test that temporary bypass works
        bypass_request = self.create_mock_request(bypass_user_agent)
        try:
            await security_manager.check_user_agent_lockdown(bypass_request, updated_user)
            logger.info("✅ Temporary User Agent bypass works correctly")
        except Exception as e:
            logger.error(f"❌ Temporary bypass should allow access: {e}")
            return False

        # Test that expired bypass doesn't work
        expired_bypass = {
            "user_agent": "ExpiredBrowser/1.0",
            "expires_at": (datetime.utcnow() - timedelta(minutes=1)).isoformat(),
            "created_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
            "reason": "expired_access",
        }

        await self.users_collection.update_one(
            {"_id": user_with_lockdown["_id"]}, {"$push": {"temporary_user_agent_bypasses": expired_bypass}}
        )

        updated_user = await self.users_collection.find_one({"_id": user_with_lockdown["_id"]})
        expired_request = self.create_mock_request("ExpiredBrowser/1.0")

        try:
            await security_manager.check_user_agent_lockdown(expired_request, updated_user)
            logger.error("❌ Expired bypass should not allow access")
            return False
        except Exception:
            logger.info("✅ Expired bypass correctly denied")

        return True

    async def test_edge_cases(self):
        """Test edge cases and error conditions."""
        logger.info("=== Testing Edge Cases ===")

        # Test 1: Missing User Agent header with lockdown enabled
        user_with_lockdown = await self.create_test_user("edge_case", True, ["TrustedBrowser/1.0"])

        mock_request = MagicMock()
        mock_request.headers = {}  # No User Agent header
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"
        mock_request.method = "GET"
        mock_request.url = MagicMock()
        mock_request.url.path = "/api/test"

        try:
            await security_manager.check_user_agent_lockdown(mock_request, user_with_lockdown)
            logger.error("❌ Missing User Agent should be blocked when lockdown is enabled")
            return False
        except Exception:
            logger.info("✅ Missing User Agent correctly blocked when lockdown enabled")

        # Test 2: Very long User Agent string
        long_user_agent = "A" * 1000  # Very long User Agent
        user_with_long_ua = await self.create_test_user("long_ua", True, [long_user_agent])

        long_request = self.create_mock_request(long_user_agent)
        try:
            await security_manager.check_user_agent_lockdown(long_request, user_with_long_ua)
            logger.info("✅ Long User Agent handled correctly")
        except Exception as e:
            logger.error(f"❌ Long User Agent should be handled: {e}")
            return False

        # Test 3: Special characters in User Agent
        special_user_agent = "Special/1.0 (Test; +http://example.com) [Bot]"
        user_with_special = await self.create_test_user("special_ua", True, [special_user_agent])

        special_request = self.create_mock_request(special_user_agent)
        try:
            await security_manager.check_user_agent_lockdown(special_request, user_with_special)
            logger.info("✅ Special characters in User Agent handled correctly")
        except Exception as e:
            logger.error(f"❌ Special characters should be handled: {e}")
            return False

        return True

    async def test_performance(self):
        """Test performance of User Agent lockdown checks."""
        logger.info("=== Testing Performance ===")

        # Create user with many trusted User Agents
        many_user_agents = [f"Browser{i}/1.0" for i in range(100)]
        user_many_ua = await self.create_test_user("performance", True, many_user_agents)

        # Test performance with User Agent at beginning of list
        start_time = time.time()
        first_request = self.create_mock_request("Browser0/1.0")
        await security_manager.check_user_agent_lockdown(first_request, user_many_ua)
        first_time = time.time() - start_time

        # Test performance with User Agent at end of list
        start_time = time.time()
        last_request = self.create_mock_request("Browser99/1.0")
        await security_manager.check_user_agent_lockdown(last_request, user_many_ua)
        last_time = time.time() - start_time

        logger.info(f"✅ Performance test - First UA: {first_time:.4f}s, Last UA: {last_time:.4f}s")

        # Both should be reasonably fast (under 10ms)
        if first_time > 0.01 or last_time > 0.01:
            logger.warning(f"⚠️  Performance may be suboptimal for large User Agent lists")

        return True

    async def demonstrate_real_world_scenario(self):
        """Demonstrate a real-world User Agent lockdown scenario."""
        logger.info("=== Real-World Scenario Demonstration ===")

        # Scenario: A user wants to restrict access to only their trusted devices
        logger.info("Scenario: User restricts access to trusted devices only")

        # Create user with common trusted User Agents
        trusted_devices = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",  # Chrome on Windows
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",  # Chrome on Mac
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",  # Safari on iPhone
            "MyCompanyApp/2.1.0 (Internal Tool)",  # Company internal app
        ]

        secure_user = await self.create_test_user("secure_scenario", True, trusted_devices)

        # Test legitimate access from trusted devices
        legitimate_requests = [
            (
                "Chrome on Windows",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            ),
            ("Company App", "MyCompanyApp/2.1.0 (Internal Tool)"),
            (
                "iPhone Safari",
                "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
            ),
        ]

        for device_name, user_agent in legitimate_requests:
            request = self.create_mock_request(user_agent)
            try:
                await security_manager.check_user_agent_lockdown(request, secure_user)
                logger.info(f"✅ {device_name}: Access granted")
            except Exception as e:
                logger.error(f"❌ {device_name}: Should be allowed - {e}")

        # Test malicious/unauthorized access attempts
        malicious_requests = [
            ("Unknown Bot", "BadBot/1.0"),
            ("Suspicious Browser", "Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1)"),  # Old IE
            ("Curl", "curl/7.68.0"),
            ("Python Script", "Python-urllib/3.8"),
        ]

        for attack_name, user_agent in malicious_requests:
            request = self.create_mock_request(user_agent)
            try:
                await security_manager.check_user_agent_lockdown(request, secure_user)
                logger.error(f"❌ {attack_name}: Should be blocked")
            except Exception:
                logger.info(f"✅ {attack_name}: Correctly blocked")

        logger.info("Real-world scenario demonstration complete")
        return True

    async def run_all_tests(self):
        """Run all User Agent lockdown tests."""
        logger.info("🚀 Starting comprehensive User Agent lockdown tests...")

        try:
            await self.setup()

            tests = [
                ("Basic User Agent Lockdown", self.test_basic_user_agent_lockdown),
                ("User Agent Extraction", self.test_user_agent_extraction),
                ("Temporary Bypass Functionality", self.test_temporary_bypass_functionality),
                ("Edge Cases", self.test_edge_cases),
                ("Performance", self.test_performance),
                ("Real-World Scenario", self.demonstrate_real_world_scenario),
            ]

            passed = 0
            failed = 0

            for test_name, test_func in tests:
                logger.info(f"\n--- Running {test_name} ---")
                try:
                    result = await test_func()
                    if result:
                        logger.info(f"✅ {test_name}: PASSED")
                        passed += 1
                    else:
                        logger.error(f"❌ {test_name}: FAILED")
                        failed += 1
                except Exception as e:
                    logger.error(f"❌ {test_name}: ERROR - {e}")
                    failed += 1

            logger.info(f"\n🎯 Test Results: {passed} passed, {failed} failed")

            if failed == 0:
                logger.info("🎉 All User Agent lockdown tests passed!")
                return True
            else:
                logger.error("💥 Some tests failed!")
                return False

        except Exception as e:
            logger.error(f"Test suite failed with error: {e}")
            return False
        finally:
            await self.cleanup()


async def main():
    """Main test runner."""
    tester = UserAgentLockdownTester()
    success = await tester.run_all_tests()

    if success:
        print("\n✅ User Agent lockdown testing completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ User Agent lockdown testing failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
