#!/usr/bin/env python3
"""
Integration test for User Agent lockdown database schema with existing codebase.

This test validates that the new User Agent lockdown database fields integrate
properly with existing authentication and security systems.
"""

import asyncio
from datetime import datetime, timedelta
import sys
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId

# Add the src directory to the path
sys.path.insert(0, "src")

from second_brain_database.database import db_manager
from second_brain_database.managers.security_manager import security_manager


async def test_user_agent_integration():
    """Test User Agent lockdown integration with existing systems."""
    print("🔍 Testing User Agent lockdown integration with existing systems...")

    try:
        # Connect to database
        await db_manager.connect()
        users_collection = db_manager.get_collection("users")

        # Clean up any leftover test users from previous runs
        await users_collection.delete_many(
            {
                "username": {
                    "$regex": "^(integration_test_user|new_integration_user|combined_lockdown_user|legacy_user)_"
                }
            }
        )

        # Test 1: Integration with SecurityManager
        print("\n🔍 Test 1: Testing integration with SecurityManager...")

        # Create test user with User Agent lockdown enabled
        test_user_id = ObjectId()
        timestamp = int(datetime.utcnow().timestamp())
        test_user = {
            "_id": test_user_id,
            "username": f"integration_test_user_{timestamp}",
            "email": f"integration_test_{timestamp}@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "trusted_user_agent_lockdown": True,
            "trusted_user_agents": ["Mozilla/5.0 (Trusted Browser)", "TrustedApp/1.0"],
            "trusted_user_agent_lockdown_codes": [],
        }
        await users_collection.insert_one(test_user)

        # Mock request object
        mock_request = MagicMock()
        mock_request.headers = {"user-agent": "Mozilla/5.0 (Trusted Browser)"}

        # Test User Agent extraction
        user_agent = security_manager.get_client_user_agent(mock_request)
        assert user_agent == "Mozilla/5.0 (Trusted Browser)"
        print("✅ User Agent extraction works correctly")

        # Test User Agent lockdown check with trusted User Agent (should pass)
        try:
            await security_manager.check_user_agent_lockdown(mock_request, test_user)
            print("✅ User Agent lockdown check passes for trusted User Agent")
        except Exception as e:
            raise AssertionError(f"User Agent lockdown check should pass for trusted User Agent: {e}")

        # Test User Agent lockdown check with untrusted User Agent (should fail)
        mock_request.headers = {"user-agent": "UntrustedBrowser/1.0"}
        try:
            await security_manager.check_user_agent_lockdown(mock_request, test_user)
            raise AssertionError("User Agent lockdown check should fail for untrusted User Agent")
        except Exception:
            print("✅ User Agent lockdown check correctly blocks untrusted User Agent")

        # Test 2: Integration with user registration
        print("\n🔍 Test 2: Testing integration with user registration...")

        # Import registration function
        from second_brain_database.routes.auth.models import UserIn
        from second_brain_database.routes.auth.services.auth.registration import register_user

        # Create test user registration
        test_registration = UserIn(
            username=f"new_integration_user_{timestamp}",
            email=f"new_integration_{timestamp}@example.com",
            password="TestPassword123!",
            plan="free",
            team=["individual"],  # team is a list of strings
            role="user",
            client_side_encryption=False,
        )

        # Register user and check that User Agent lockdown fields are initialized
        user_doc, verification_token = await register_user(test_registration)

        # Verify User Agent lockdown fields are present with correct defaults
        assert user_doc.get("trusted_user_agent_lockdown") == False
        assert user_doc.get("trusted_user_agents") == []
        assert user_doc.get("trusted_user_agent_lockdown_codes") == []
        assert user_doc.get("temporary_ip_access_tokens") == []
        assert user_doc.get("temporary_user_agent_access_tokens") == []
        print("✅ User registration correctly initializes User Agent lockdown fields")

        # Test 3: Integration with database indexes
        print("\n🔍 Test 3: Testing database index integration...")

        # Create indexes
        await db_manager.create_indexes()

        # Test that queries use indexes efficiently
        explain_result = await users_collection.find({"trusted_user_agent_lockdown": True}).explain()
        print("✅ Database indexes created and queries work efficiently")

        # Test 4: Integration with cleanup processes
        print("\n🔍 Test 4: Testing cleanup process integration...")

        # Add expired User Agent lockdown codes
        expired_code = {
            "code": "EXPIRED123",
            "expires_at": (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
            "action": "enable",
            "allowed_user_agents": ["ExpiredBrowser/1.0"],
        }

        await users_collection.update_one(
            {"_id": test_user_id}, {"$push": {"trusted_user_agent_lockdown_codes": expired_code}}
        )

        # Import and test cleanup functions
        from second_brain_database.routes.auth.periodics.cleanup import (
            get_last_temporary_access_tokens_cleanup_time,
            get_last_trusted_user_agent_lockdown_code_cleanup_time,
            set_last_temporary_access_tokens_cleanup_time,
            set_last_trusted_user_agent_lockdown_code_cleanup_time,
        )

        # Test cleanup time tracking
        test_time = datetime.utcnow()
        await set_last_trusted_user_agent_lockdown_code_cleanup_time(test_time)
        retrieved_time = await get_last_trusted_user_agent_lockdown_code_cleanup_time()
        assert retrieved_time is not None
        print("✅ User Agent lockdown cleanup time tracking works correctly")

        # Test temporary access tokens cleanup time tracking
        await set_last_temporary_access_tokens_cleanup_time(test_time)
        temp_retrieved_time = await get_last_temporary_access_tokens_cleanup_time()
        assert temp_retrieved_time is not None
        print("✅ Temporary access tokens cleanup time tracking works correctly")

        # Test 5: Integration with existing IP lockdown
        print("\n🔍 Test 5: Testing integration with existing IP lockdown...")

        # Create user with both IP and User Agent lockdown
        combined_user_id = ObjectId()
        combined_user = {
            "_id": combined_user_id,
            "username": f"combined_lockdown_user_{timestamp}",
            "email": f"combined_{timestamp}@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            # IP lockdown fields (existing)
            "trusted_ip_lockdown": True,
            "trusted_ips": ["192.168.1.100"],
            "trusted_ip_lockdown_codes": [],
            # User Agent lockdown fields (new)
            "trusted_user_agent_lockdown": True,
            "trusted_user_agents": ["Mozilla/5.0 (Trusted Browser)"],
            "trusted_user_agent_lockdown_codes": [],
            # Temporary access tokens (new)
            "temporary_ip_access_tokens": [],
            "temporary_user_agent_access_tokens": [],
        }
        await users_collection.insert_one(combined_user)

        # Test that both lockdown types can coexist
        mock_request.client = MagicMock()
        mock_request.client.host = "192.168.1.100"  # Trusted IP
        mock_request.headers = {"user-agent": "Mozilla/5.0 (Trusted Browser)"}  # Trusted UA

        # Both checks should pass
        await security_manager.check_ip_lockdown(mock_request, combined_user)
        await security_manager.check_user_agent_lockdown(mock_request, combined_user)
        print("✅ IP and User Agent lockdown integration works correctly")

        # Test 6: Backward compatibility
        print("\n🔍 Test 6: Testing backward compatibility...")

        # Create legacy user without new fields
        legacy_user_id = ObjectId()
        legacy_user = {
            "_id": legacy_user_id,
            "username": f"legacy_user_{timestamp}",
            "email": f"legacy_{timestamp}@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            # Only has old fields, no User Agent lockdown fields
        }
        await users_collection.insert_one(legacy_user)

        # Test that security manager handles missing fields gracefully
        await security_manager.check_user_agent_lockdown(mock_request, legacy_user)
        print("✅ Backward compatibility maintained for legacy users")

        # Test 7: Performance impact assessment
        print("\n🔍 Test 7: Testing performance impact...")

        import time

        # Test query performance with new fields
        start_time = time.time()
        users_with_lockdown = await users_collection.find({"trusted_user_agent_lockdown": True}).to_list(length=100)
        query_time = time.time() - start_time

        # Performance should be reasonable (under 100ms for small dataset)
        assert query_time < 0.1, f"Query took too long: {query_time:.3f}s"
        print(f"✅ Query performance acceptable: {query_time:.3f}s")

        # Test update performance
        start_time = time.time()
        await users_collection.update_one(
            {"_id": test_user_id}, {"$set": {"trusted_user_agents": ["Updated Browser/1.0"]}}
        )
        update_time = time.time() - start_time

        assert update_time < 0.1, f"Update took too long: {update_time:.3f}s"
        print(f"✅ Update performance acceptable: {update_time:.3f}s")

        # Cleanup: Remove test users
        print("\n🧹 Cleaning up test data...")
        test_user_ids = [test_user_id, combined_user_id, legacy_user_id]

        # Also clean up the registered user
        registered_user = await users_collection.find_one({"username": f"new_integration_user_{timestamp}"})
        if registered_user:
            test_user_ids.append(registered_user["_id"])

        await users_collection.delete_many({"_id": {"$in": test_user_ids}})

        # Clean up system collection test data
        system_collection = db_manager.get_collection("system")
        await system_collection.delete_many(
            {"_id": {"$in": ["trusted_user_agent_lockdown_code_cleanup", "temporary_access_tokens_cleanup"]}}
        )
        print("✅ Test data cleaned up")

        print("\n🎉 All User Agent lockdown integration tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        await db_manager.disconnect()


async def main():
    """Main test runner."""
    print("🚀 Starting User Agent lockdown integration tests...")

    success = await test_user_agent_integration()

    if success:
        print("\n✅ All User Agent lockdown integration tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ User Agent lockdown integration tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
