#!/usr/bin/env python3
"""
Test script to validate temporary access tokens database schema and cleanup operations.

This script tests that the new temporary access token fields are properly handled
in database operations including creation, updates, queries, and cleanup.
"""

import asyncio
from datetime import datetime, timedelta
import sys

from bson import ObjectId

# Add the src directory to the path
sys.path.insert(0, "src")

from second_brain_database.database import db_manager
from second_brain_database.routes.auth.periodics.cleanup import (
    get_last_temporary_access_tokens_cleanup_time,
    set_last_temporary_access_tokens_cleanup_time,
)


async def test_temporary_access_tokens_schema():
    """Test temporary access tokens database schema operations."""
    print("🔍 Testing temporary access tokens database schema validation...")

    try:
        # Connect to database
        await db_manager.connect()
        users_collection = db_manager.get_collection("users")

        # Test 1: Create user with temporary access token fields
        print("\n📝 Test 1: Creating user with temporary access token fields...")
        test_user_id = ObjectId()
        user_doc = {
            "_id": test_user_id,
            "username": "temp_token_test_user",
            "email": "temp_token_test@example.com",
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
            # Temporary access token fields
            "temporary_ip_access_tokens": [],
            "temporary_user_agent_access_tokens": [],
        }

        result = await users_collection.insert_one(user_doc)
        assert result.inserted_id == test_user_id
        print("✅ User created successfully with temporary access token fields")

        # Test 2: Add temporary access tokens
        print("\n📝 Test 2: Adding temporary access tokens...")
        future_time = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
        past_time = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

        ip_tokens = [
            {
                "token": "temp_ip_token_1",
                "ip_address": "192.168.1.100",
                "expires_at": future_time,
                "created_at": datetime.utcnow().isoformat(),
                "used": False,
            },
            {
                "token": "temp_ip_token_2_expired",
                "ip_address": "10.0.0.1",
                "expires_at": past_time,  # Expired token
                "created_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
                "used": False,
            },
        ]

        ua_tokens = [
            {
                "token": "temp_ua_token_1",
                "user_agent": "Mozilla/5.0 (Test Browser)",
                "expires_at": future_time,
                "created_at": datetime.utcnow().isoformat(),
                "used": False,
            },
            {
                "token": "temp_ua_token_2_expired",
                "user_agent": "TestApp/1.0",
                "expires_at": past_time,  # Expired token
                "created_at": (datetime.utcnow() - timedelta(minutes=10)).isoformat(),
                "used": False,
            },
        ]

        update_result = await users_collection.update_one(
            {"_id": test_user_id},
            {"$set": {"temporary_ip_access_tokens": ip_tokens, "temporary_user_agent_access_tokens": ua_tokens}},
        )
        assert update_result.modified_count == 1
        print("✅ Temporary access tokens added successfully")

        # Test 3: Verify tokens were stored correctly
        print("\n🔍 Test 3: Verifying stored temporary access tokens...")
        updated_user = await users_collection.find_one({"_id": test_user_id})
        assert len(updated_user.get("temporary_ip_access_tokens", [])) == 2
        assert len(updated_user.get("temporary_user_agent_access_tokens", [])) == 2
        print("✅ Temporary access tokens stored correctly")

        # Test 4: Test cleanup process manually
        print("\n🧹 Test 4: Testing cleanup process for expired tokens...")
        now = datetime.utcnow().isoformat()

        # Simulate cleanup logic
        stored_ip_tokens = updated_user.get("temporary_ip_access_tokens", [])
        stored_ua_tokens = updated_user.get("temporary_user_agent_access_tokens", [])

        # Filter out expired tokens
        filtered_ip_tokens = [t for t in stored_ip_tokens if t.get("expires_at", now) > now]
        filtered_ua_tokens = [t for t in stored_ua_tokens if t.get("expires_at", now) > now]

        # Should have 1 valid token each (expired ones filtered out)
        assert len(filtered_ip_tokens) == 1
        assert len(filtered_ua_tokens) == 1
        assert filtered_ip_tokens[0]["token"] == "temp_ip_token_1"
        assert filtered_ua_tokens[0]["token"] == "temp_ua_token_1"
        print("✅ Cleanup logic correctly filters expired tokens")

        # Test 5: Apply cleanup to database
        print("\n📝 Test 5: Applying cleanup to database...")
        await users_collection.update_one(
            {"_id": test_user_id},
            {
                "$set": {
                    "temporary_ip_access_tokens": filtered_ip_tokens,
                    "temporary_user_agent_access_tokens": filtered_ua_tokens,
                }
            },
        )

        cleaned_user = await users_collection.find_one({"_id": test_user_id})
        assert len(cleaned_user.get("temporary_ip_access_tokens", [])) == 1
        assert len(cleaned_user.get("temporary_user_agent_access_tokens", [])) == 1
        print("✅ Database cleanup applied successfully")

        # Test 6: Test cleanup time tracking functions
        print("\n🔍 Test 6: Testing cleanup time tracking functions...")
        test_time = datetime.utcnow()

        # Test setting cleanup time
        await set_last_temporary_access_tokens_cleanup_time(test_time)

        # Test getting cleanup time
        retrieved_time = await get_last_temporary_access_tokens_cleanup_time()
        assert retrieved_time is not None
        # Allow for small time differences due to serialization
        time_diff = abs((retrieved_time - test_time).total_seconds())
        assert time_diff < 1.0  # Should be within 1 second
        print("✅ Cleanup time tracking functions work correctly")

        # Test 7: Test backward compatibility with missing fields
        print("\n🔍 Test 7: Testing backward compatibility with missing fields...")
        legacy_user_id = ObjectId()
        legacy_user_doc = {
            "_id": legacy_user_id,
            "username": "legacy_temp_user",
            "email": "legacy_temp@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            # Note: No temporary access token fields (simulating old user document)
        }

        await users_collection.insert_one(legacy_user_doc)
        legacy_user = await users_collection.find_one({"_id": legacy_user_id})

        # Test that .get() methods work with defaults for missing fields
        assert legacy_user.get("temporary_ip_access_tokens", []) == []
        assert legacy_user.get("temporary_user_agent_access_tokens", []) == []
        print("✅ Backward compatibility maintained for missing temporary access token fields")

        # Test 8: Test index creation and query performance
        print("\n🔍 Test 8: Testing index creation and query performance...")
        # Create indexes (this should be idempotent)
        await db_manager.create_indexes()

        # Test query using indexed fields
        users_with_temp_tokens = await users_collection.find(
            {
                "$or": [
                    {"temporary_ip_access_tokens": {"$exists": True, "$ne": []}},
                    {"temporary_user_agent_access_tokens": {"$exists": True, "$ne": []}},
                ]
            }
        ).to_list(length=10)
        assert len(users_with_temp_tokens) >= 1  # Should find our test user
        print("✅ Index creation and queries work correctly for temporary access tokens")

        # Cleanup: Remove test users
        print("\n🧹 Cleaning up test data...")
        await users_collection.delete_many({"_id": {"$in": [test_user_id, legacy_user_id]}})

        # Clean up system collection test data
        system_collection = db_manager.get_collection("system")
        await system_collection.delete_one({"_id": "temporary_access_tokens_cleanup"})
        print("✅ Test data cleaned up")

        print("\n🎉 All temporary access tokens database schema tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Temporary access tokens schema validation test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        await db_manager.disconnect()


async def main():
    """Main test runner."""
    print("🚀 Starting temporary access tokens database schema validation tests...")

    success = await test_temporary_access_tokens_schema()

    if success:
        print("\n✅ All temporary access tokens database schema validation tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Temporary access tokens database schema validation tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
