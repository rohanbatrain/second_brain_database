#!/usr/bin/env python3
"""
Manual integration test for permanent tokens with existing authentication flows.
Manually handles database connection and cleanup.
"""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from second_brain_database.config import settings
from second_brain_database.database import db_manager


async def test_permanent_token_integration():
    """Test permanent token integration with existing authentication flows."""
    print("🚀 Starting Manual Permanent Token Integration Test")
    print("=" * 60)

    # Check if permanent tokens are enabled
    if not settings.PERMANENT_TOKENS_ENABLED:
        print("❌ Permanent tokens are disabled in configuration")
        print("   Set PERMANENT_TOKENS_ENABLED=true to run tests")
        return False

    try:
        # Connect to database
        print("🔧 Connecting to database...")
        await db_manager.connect()
        await db_manager.create_indexes()
        print("✅ Database connected and indexes created")

        # Test database operations directly
        print("\n📊 Testing database operations...")

        # Test 1: Check permanent token collection exists
        collection = db_manager.get_collection("permanent_tokens")
        count = await collection.count_documents({})
        print(f"✅ Permanent tokens collection accessible, {count} existing tokens")

        # Test 2: Create test user first
        print("\n� Creatning test user...")
        from bson import ObjectId

        test_user_id = str(ObjectId())  # Generate new ObjectId
        import time

        test_username = f"test_user_integration_{int(time.time())}"  # Make username unique
        test_email = f"test_{int(time.time())}@integration.com"
        test_description = "Integration Test Token"

        # Create test user in database
        user_doc = {
            "_id": ObjectId(test_user_id),
            "username": test_username,
            "email": test_email,
            "role": "user",
            "is_verified": True,
            "created_at": "2025-01-01T00:00:00Z",
        }

        users_collection = db_manager.get_collection("users")
        await users_collection.insert_one(user_doc)
        print("✅ Test user created")

        # Test 3: Test token generation service
        print("\n🔑 Testing token generation service...")
        from second_brain_database.routes.auth.services.permanent_tokens.generator import create_permanent_token

        token_data = await create_permanent_token(
            user_id=test_user_id, username=test_username, email=test_email, description=test_description
        )

        if not token_data or not token_data.token:
            print("❌ Token generation failed")
            return False

        print("✅ Token generation successful")
        print(f"   Token ID: {token_data.token_id}")

        # Test 3: Test token validation service
        print("\n🔐 Testing token validation service...")
        from second_brain_database.routes.auth.services.permanent_tokens.validator import validate_permanent_token

        validation_result = await validate_permanent_token(token_data.token)

        if not validation_result or validation_result.get("username") != test_username:
            print("❌ Token validation failed")
            return False

        print("✅ Token validation successful")

        # Test 4: Test cache operations
        print("\n💾 Testing cache operations...")
        from second_brain_database.routes.auth.services.permanent_tokens.cache_manager import get_cache_statistics

        # Test cache statistics
        cache_stats = await get_cache_statistics()

        if not cache_stats or "cache_count" not in cache_stats:
            print("❌ Cache operations failed")
            return False

        print("✅ Cache operations successful")
        print(f"   Cache keys: {cache_stats.get('cache_count', 0)}")
        print(f"   Hit rate: {cache_stats.get('cache_hit_rate', 0)}%")

        # Test 5: Test token revocation
        print("\n🗑️ Testing token revocation...")
        from second_brain_database.routes.auth.services.permanent_tokens.generator import hash_token
        from second_brain_database.routes.auth.services.permanent_tokens.revocation import revoke_token_by_hash

        # Hash the token for revocation
        token_hash = hash_token(token_data.token)
        revocation_result = await revoke_token_by_hash(token_hash)

        if not revocation_result:
            print("❌ Token revocation failed")
            return False

        print("✅ Token revocation successful")

        # Test 6: Verify revoked token doesn't validate
        print("\n🚫 Testing revoked token validation...")

        validation_result = await validate_permanent_token(token_data.token)

        if validation_result:
            print("❌ Revoked token still validates")
            return False

        print("✅ Revoked token properly rejected")

        # Test 7: Test audit logging
        print("\n📝 Testing audit logging...")
        from second_brain_database.routes.auth.services.permanent_tokens.audit_logger import log_token_created
        from second_brain_database.routes.auth.services.permanent_tokens.generator import hash_token

        # Log token creation event
        token_hash = hash_token(token_data.token)
        await log_token_created(
            user_id=test_user_id,
            username=test_username,
            token_id=token_data.token_id,
            token_hash=token_hash,
            description=test_description,
            ip_address="127.0.0.1",
            user_agent="Test Agent",
        )

        # Check if audit log was created
        audit_collection = db_manager.get_collection("permanent_token_audit_logs")
        audit_count = await audit_collection.count_documents({"username": test_username})

        if audit_count == 0:
            print("❌ Audit logging failed")
            return False

        print("✅ Audit logging successful")

        # Test 8: Test analytics
        print("\n📊 Testing analytics...")
        from second_brain_database.routes.auth.services.permanent_tokens.analytics import track_token_usage

        # Track token usage
        await track_token_usage(
            token_hash=token_hash, user_id=test_user_id, ip_address="127.0.0.1", user_agent="Test Agent"
        )

        # Check if analytics were recorded
        analytics_collection = db_manager.get_collection("permanent_token_usage_analytics")
        analytics_count = await analytics_collection.count_documents({"user_id": test_user_id})

        if analytics_count == 0:
            print("❌ Analytics recording failed")
            return False

        print("✅ Analytics recording successful")

        # Test 9: Test maintenance operations
        print("\n🔧 Testing maintenance operations...")
        from second_brain_database.routes.auth.services.permanent_tokens.maintenance import get_database_health

        health_data = await get_database_health()

        if not health_data or not hasattr(health_data, "active_tokens"):
            print("❌ Health check failed")
            return False

        print("✅ Health check successful")
        print(f"   Active tokens: {health_data.active_tokens}")
        print(f"   Revoked tokens: {health_data.revoked_tokens}")

        # Cleanup test data
        print("\n🧹 Cleaning up test data...")

        # Remove test user
        await db_manager.get_collection("users").delete_many({"_id": ObjectId(test_user_id)})

        # Remove test tokens
        await db_manager.get_collection("permanent_tokens").delete_many({"user_id": test_user_id})

        # Remove test audit logs
        await db_manager.get_collection("permanent_token_audit_logs").delete_many({"username": test_username})

        # Remove test analytics
        await db_manager.get_collection("permanent_token_usage_analytics").delete_many({"user_id": test_user_id})

        # Clear test cache (if any cache keys were created)
        from second_brain_database.routes.auth.services.permanent_tokens.cache_manager import (
            cleanup_expired_cache_entries,
        )

        await cleanup_expired_cache_entries()

        print("✅ Test data cleaned up")

        # All tests passed
        print("\n" + "=" * 60)
        print("🏁 Integration Test Summary")
        print("✅ Passed: 9")
        print("❌ Failed: 0")
        print("📊 Success Rate: 100.0%")
        print("\n🎉 All integration tests passed!")
        print("✅ Permanent token services are working correctly")
        print("✅ Database operations are functional")
        print("✅ Cache operations are functional")
        print("✅ Audit logging is functional")
        print("✅ Analytics are functional")
        print("✅ Maintenance operations are functional")

        return True

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Disconnect from database
        await db_manager.disconnect()
        print("🔌 Database disconnected")


async def main():
    """Main test runner."""
    success = await test_permanent_token_integration()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
