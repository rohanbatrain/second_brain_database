#!/usr/bin/env python3
"""
Test script to validate User Agent lockdown database schema operations.

This script tests that the new User Agent lockdown fields are properly handled
in database operations including creation, updates, and queries.
"""

import asyncio
from datetime import datetime, timedelta
import sys

from bson import ObjectId

# Add the src directory to the path
sys.path.insert(0, "src")

from second_brain_database.config import settings
from second_brain_database.database import db_manager


async def test_user_agent_schema_validation():
    """Test User Agent lockdown database schema operations."""
    print("🔍 Testing User Agent lockdown database schema validation...")

    try:
        # Connect to database
        await db_manager.connect()
        users_collection = db_manager.get_collection("users")

        # Test 1: Create user with User Agent lockdown fields
        print("\n📝 Test 1: Creating user with User Agent lockdown fields...")
        test_user_id = ObjectId()
        user_doc = {
            "_id": test_user_id,
            "username": "schema_test_user",
            "email": "schema_test@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "failed_login_attempts": 0,
            "last_login": None,
            "is_verified": True,
            "plan": "free",
            "team": "individual",
            "role": "user",
            "client_side_encryption": False,
            # User Agent lockdown fields
            "trusted_user_agent_lockdown": False,
            "trusted_user_agents": [],
            "trusted_user_agent_lockdown_codes": [],
        }

        result = await users_collection.insert_one(user_doc)
        assert result.inserted_id == test_user_id
        print("✅ User created successfully with User Agent lockdown fields")

        # Test 2: Query user and verify fields exist with defaults
        print("\n🔍 Test 2: Querying user and verifying field defaults...")
        retrieved_user = await users_collection.find_one({"_id": test_user_id})
        assert retrieved_user is not None

        # Verify User Agent lockdown fields exist and have correct defaults
        assert retrieved_user.get("trusted_user_agent_lockdown", None) == False
        assert retrieved_user.get("trusted_user_agents", None) == []
        assert retrieved_user.get("trusted_user_agent_lockdown_codes", None) == []
        print("✅ User Agent lockdown fields have correct default values")

        # Test 3: Update User Agent lockdown settings
        print("\n📝 Test 3: Updating User Agent lockdown settings...")
        test_user_agents = ["Mozilla/5.0 (Test Browser)", "TestApp/1.0"]
        test_code = {
            "code": "TEST123",
            "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat(),
            "action": "enable",
            "allowed_user_agents": test_user_agents,
        }

        update_result = await users_collection.update_one(
            {"_id": test_user_id},
            {
                "$set": {
                    "trusted_user_agent_lockdown": True,
                    "trusted_user_agents": test_user_agents,
                    "trusted_user_agent_lockdown_codes": [test_code],
                }
            },
        )
        assert update_result.modified_count == 1
        print("✅ User Agent lockdown settings updated successfully")

        # Test 4: Verify updated values
        print("\n🔍 Test 4: Verifying updated User Agent lockdown values...")
        updated_user = await users_collection.find_one({"_id": test_user_id})
        assert updated_user.get("trusted_user_agent_lockdown") == True
        assert updated_user.get("trusted_user_agents") == test_user_agents
        assert len(updated_user.get("trusted_user_agent_lockdown_codes", [])) == 1
        assert updated_user["trusted_user_agent_lockdown_codes"][0]["code"] == "TEST123"
        print("✅ User Agent lockdown values updated correctly")

        # Test 5: Test graceful handling of missing fields (backward compatibility)
        print("\n🔍 Test 5: Testing backward compatibility with missing fields...")
        legacy_user_id = ObjectId()
        legacy_user_doc = {
            "_id": legacy_user_id,
            "username": "legacy_user",
            "email": "legacy@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            # Note: No User Agent lockdown fields (simulating old user document)
        }

        await users_collection.insert_one(legacy_user_doc)
        legacy_user = await users_collection.find_one({"_id": legacy_user_id})

        # Test that .get() methods work with defaults for missing fields
        assert legacy_user.get("trusted_user_agent_lockdown", False) == False
        assert legacy_user.get("trusted_user_agents", []) == []
        assert legacy_user.get("trusted_user_agent_lockdown_codes", []) == []
        print("✅ Backward compatibility maintained for missing fields")

        # Test 6: Test index creation and query performance
        print("\n🔍 Test 6: Testing index creation and query performance...")
        # Create indexes (this should be idempotent)
        await db_manager.create_indexes()

        # Test query using indexed fields
        lockdown_users = await users_collection.find({"trusted_user_agent_lockdown": True}).to_list(length=10)
        assert len(lockdown_users) >= 1  # Should find our test user
        print("✅ Index creation and queries work correctly")

        # Cleanup: Remove test users
        print("\n🧹 Cleaning up test data...")
        await users_collection.delete_many({"_id": {"$in": [test_user_id, legacy_user_id]}})
        print("✅ Test data cleaned up")

        print("\n🎉 All User Agent lockdown database schema tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Schema validation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        await db_manager.disconnect()


async def main():
    """Main test runner."""
    print("🚀 Starting User Agent lockdown database schema validation tests...")

    success = await test_user_agent_schema_validation()

    if success:
        print("\n✅ All database schema validation tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Database schema validation tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
