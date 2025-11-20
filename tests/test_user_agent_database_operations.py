#!/usr/bin/env python3
"""
Test script to validate User Agent lockdown database operations.

This script comprehensively tests all database operations related to User Agent lockdown
including queries, updates, indexes, and performance characteristics.
"""

import asyncio
from datetime import datetime, timedelta
import sys
import time

from bson import ObjectId

# Add the src directory to the path
sys.path.insert(0, "src")

from second_brain_database.config import settings
from second_brain_database.database import db_manager


async def test_user_agent_database_operations():
    """Test all User Agent lockdown database operations."""
    print("🔍 Testing User Agent lockdown database operations...")

    try:
        # Connect to database
        await db_manager.connect()
        users_collection = db_manager.get_collection("users")

        # Test 1: Create multiple test users with different lockdown configurations
        print("\n📝 Test 1: Creating test users with different User Agent lockdown configurations...")
        test_users = []

        # User 1: No lockdown (default)
        user1_id = ObjectId()
        user1_doc = {
            "_id": user1_id,
            "username": "user_no_lockdown",
            "email": "no_lockdown@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "trusted_user_agent_lockdown": False,
            "trusted_user_agents": [],
            "trusted_user_agent_lockdown_codes": [],
        }
        test_users.append(user1_id)

        # User 2: Lockdown enabled with trusted User Agents
        user2_id = ObjectId()
        user2_doc = {
            "_id": user2_id,
            "username": "user_with_lockdown",
            "email": "with_lockdown@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "trusted_user_agent_lockdown": True,
            "trusted_user_agents": ["Mozilla/5.0 (Trusted Browser)", "TrustedApp/1.0"],
            "trusted_user_agent_lockdown_codes": [],
        }
        test_users.append(user2_id)

        # User 3: Lockdown with pending codes
        user3_id = ObjectId()
        pending_code = {
            "code": "PENDING123",
            "expires_at": (datetime.utcnow() + timedelta(minutes=15)).isoformat(),
            "action": "enable",
            "allowed_user_agents": ["Mozilla/5.0 (New Browser)"],
        }
        user3_doc = {
            "_id": user3_id,
            "username": "user_with_codes",
            "email": "with_codes@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            "trusted_user_agent_lockdown": False,
            "trusted_user_agents": [],
            "trusted_user_agent_lockdown_codes": [pending_code],
        }
        test_users.append(user3_id)

        # Insert all test users
        await users_collection.insert_many([user1_doc, user2_doc, user3_doc])
        print("✅ Test users created successfully")

        # Test 2: Query operations with User Agent lockdown fields
        print("\n🔍 Test 2: Testing query operations...")

        # Query users with lockdown enabled
        start_time = time.time()
        lockdown_enabled_users = await users_collection.find({"trusted_user_agent_lockdown": True}).to_list(length=100)
        query_time = time.time() - start_time
        assert len(lockdown_enabled_users) >= 1
        print(f"✅ Query for lockdown enabled users completed in {query_time:.3f}s")

        # Query users with specific User Agent
        start_time = time.time()
        specific_ua_users = await users_collection.find(
            {"trusted_user_agents": "Mozilla/5.0 (Trusted Browser)"}
        ).to_list(length=100)
        query_time = time.time() - start_time
        assert len(specific_ua_users) >= 1
        print(f"✅ Query for specific User Agent completed in {query_time:.3f}s")

        # Query users with pending codes
        start_time = time.time()
        pending_code_users = await users_collection.find(
            {"trusted_user_agent_lockdown_codes": {"$exists": True, "$ne": []}}
        ).to_list(length=100)
        query_time = time.time() - start_time
        assert len(pending_code_users) >= 1
        print(f"✅ Query for users with pending codes completed in {query_time:.3f}s")

        # Test 3: Update operations
        print("\n📝 Test 3: Testing update operations...")

        # Enable lockdown for user1
        start_time = time.time()
        update_result = await users_collection.update_one(
            {"_id": user1_id},
            {"$set": {"trusted_user_agent_lockdown": True, "trusted_user_agents": ["Mozilla/5.0 (Updated Browser)"]}},
        )
        update_time = time.time() - start_time
        assert update_result.modified_count == 1
        print(f"✅ Update lockdown settings completed in {update_time:.3f}s")

        # Add User Agent to existing list
        start_time = time.time()
        push_result = await users_collection.update_one(
            {"_id": user2_id}, {"$push": {"trusted_user_agents": "NewTrustedApp/2.0"}}
        )
        update_time = time.time() - start_time
        assert push_result.modified_count == 1
        print(f"✅ Add User Agent to list completed in {update_time:.3f}s")

        # Remove expired codes (simulate cleanup)
        start_time = time.time()
        expired_time = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
        cleanup_result = await users_collection.update_many(
            {"trusted_user_agent_lockdown_codes.expires_at": {"$lt": expired_time}},
            {"$pull": {"trusted_user_agent_lockdown_codes": {"expires_at": {"$lt": expired_time}}}},
        )
        update_time = time.time() - start_time
        print(
            f"✅ Cleanup expired codes completed in {update_time:.3f}s (affected {cleanup_result.modified_count} users)"
        )

        # Test 4: Complex aggregation queries
        print("\n🔍 Test 4: Testing complex aggregation queries...")

        # Count users by lockdown status
        start_time = time.time()
        lockdown_stats = await users_collection.aggregate(
            [{"$group": {"_id": "$trusted_user_agent_lockdown", "count": {"$sum": 1}}}]
        ).to_list(length=10)
        query_time = time.time() - start_time
        assert len(lockdown_stats) >= 1
        print(f"✅ Aggregation query for lockdown stats completed in {query_time:.3f}s")

        # Find users with most trusted User Agents
        start_time = time.time()
        ua_count_stats = await users_collection.aggregate(
            [
                {
                    "$project": {
                        "username": 1,
                        "trusted_user_agent_count": {"$size": {"$ifNull": ["$trusted_user_agents", []]}},
                    }
                },
                {"$sort": {"trusted_user_agent_count": -1}},
                {"$limit": 5},
            ]
        ).to_list(length=5)
        query_time = time.time() - start_time
        assert len(ua_count_stats) >= 1
        print(f"✅ Aggregation query for User Agent counts completed in {query_time:.3f}s")

        # Test 5: Index performance validation
        print("\n🔍 Test 5: Testing index performance...")

        # Create indexes
        await db_manager.create_indexes()

        # Test index usage with explain
        explain_result = await users_collection.find({"trusted_user_agent_lockdown": True}).explain()
        execution_stats = explain_result.get("executionStats", {})
        if execution_stats:
            examined_docs = execution_stats.get("totalDocsExamined", 0)
            returned_docs = execution_stats.get("totalDocsReturned", 0)
            print(f"✅ Index performance: examined {examined_docs} docs, returned {returned_docs} docs")
        else:
            print("✅ Index performance validation completed (explain format may vary)")

        # Test 6: Concurrent operations simulation
        print("\n🔍 Test 6: Testing concurrent operations...")

        async def concurrent_update(user_id, user_agent):
            """Simulate concurrent User Agent updates."""
            return await users_collection.update_one(
                {"_id": user_id}, {"$addToSet": {"trusted_user_agents": user_agent}}
            )

        # Run concurrent updates
        start_time = time.time()
        concurrent_tasks = [concurrent_update(user2_id, f"ConcurrentApp/{i}") for i in range(5)]
        results = await asyncio.gather(*concurrent_tasks)
        concurrent_time = time.time() - start_time

        successful_updates = sum(1 for result in results if result.modified_count > 0)
        print(f"✅ Concurrent operations completed in {concurrent_time:.3f}s ({successful_updates} successful updates)")

        # Test 7: Data integrity validation
        print("\n🔍 Test 7: Testing data integrity...")

        # Verify all users have required fields
        all_users = await users_collection.find({"_id": {"$in": test_users}}).to_list(length=10)
        for user in all_users:
            # Check that all User Agent lockdown fields exist or have defaults
            assert "trusted_user_agent_lockdown" in user or user.get("trusted_user_agent_lockdown", False) is not None
            assert isinstance(user.get("trusted_user_agents", []), list)
            assert isinstance(user.get("trusted_user_agent_lockdown_codes", []), list)
        print("✅ Data integrity validation passed")

        # Test 8: Performance with large dataset simulation
        print("\n🔍 Test 8: Testing performance with larger dataset...")

        # Create additional test users for performance testing
        bulk_users = []
        bulk_user_ids = []
        for i in range(50):
            user_id = ObjectId()
            bulk_user_ids.append(user_id)
            bulk_users.append(
                {
                    "_id": user_id,
                    "username": f"perf_test_user_{i}",
                    "email": f"perf_test_{i}@example.com",
                    "hashed_password": "test_hash",
                    "created_at": datetime.utcnow(),
                    "is_active": True,
                    "trusted_user_agent_lockdown": i % 3 == 0,  # Every 3rd user has lockdown
                    "trusted_user_agents": [f"TestBrowser/{i}", f"TestApp/{i}"] if i % 3 == 0 else [],
                    "trusted_user_agent_lockdown_codes": [],
                }
            )

        # Bulk insert
        start_time = time.time()
        await users_collection.insert_many(bulk_users)
        insert_time = time.time() - start_time
        print(f"✅ Bulk insert of 50 users completed in {insert_time:.3f}s")

        # Performance query on larger dataset
        start_time = time.time()
        large_query_result = await users_collection.find(
            {"trusted_user_agent_lockdown": True, "trusted_user_agents": {"$exists": True, "$ne": []}}
        ).to_list(length=100)
        query_time = time.time() - start_time
        print(
            f"✅ Performance query on larger dataset completed in {query_time:.3f}s (found {len(large_query_result)} users)"
        )

        # Test 9: Edge cases and error handling
        print("\n🔍 Test 9: Testing edge cases...")

        # Test with null/undefined values
        edge_case_user_id = ObjectId()
        edge_case_doc = {
            "_id": edge_case_user_id,
            "username": "edge_case_user",
            "email": "edge_case@example.com",
            "hashed_password": "test_hash",
            "created_at": datetime.utcnow(),
            "is_active": True,
            # Intentionally missing User Agent lockdown fields
        }
        await users_collection.insert_one(edge_case_doc)

        # Query with missing fields should work with defaults
        edge_user = await users_collection.find_one({"_id": edge_case_user_id})
        assert edge_user.get("trusted_user_agent_lockdown", False) == False
        assert edge_user.get("trusted_user_agents", []) == []
        assert edge_user.get("trusted_user_agent_lockdown_codes", []) == []
        print("✅ Edge case handling with missing fields works correctly")

        # Cleanup: Remove all test users
        print("\n🧹 Cleaning up test data...")
        all_test_ids = test_users + bulk_user_ids + [edge_case_user_id]
        cleanup_result = await users_collection.delete_many({"_id": {"$in": all_test_ids}})
        print(f"✅ Test data cleaned up ({cleanup_result.deleted_count} users removed)")

        print("\n🎉 All User Agent lockdown database operations tests passed!")
        return True

    except Exception as e:
        print(f"\n❌ Database operations test failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        await db_manager.disconnect()


async def main():
    """Main test runner."""
    print("🚀 Starting User Agent lockdown database operations validation tests...")

    success = await test_user_agent_database_operations()

    if success:
        print("\n✅ All User Agent lockdown database operations validation tests completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ User Agent lockdown database operations validation tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
