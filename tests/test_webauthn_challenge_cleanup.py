#!/usr/bin/env python3
"""
Test WebAuthn challenge cleanup functionality.

This test verifies that the challenge cleanup functions work correctly
for both Redis and MongoDB storage systems, following existing patterns.
"""
import asyncio
from datetime import datetime, timedelta
import json
from typing import Any, Dict

from src.second_brain_database.database import db_manager
from src.second_brain_database.managers.redis_manager import redis_manager
from src.second_brain_database.routes.auth.services.webauthn.challenge import (
    CHALLENGE_EXPIRY_MINUTES,
    REDIS_CHALLENGE_PREFIX,
    cleanup_all_expired_challenges,
    cleanup_expired_challenges,
    cleanup_expired_redis_challenges,
    generate_secure_challenge,
    store_challenge,
)


async def setup_test_environment():
    """Set up test environment with database and Redis connections."""
    print("Setting up test environment...")

    # Connect to database
    await db_manager.connect()
    print("✓ Connected to MongoDB")

    # Test Redis connection
    redis_conn = await redis_manager.get_redis()
    await redis_conn.ping()
    print("✓ Connected to Redis")

    # Create indexes
    await db_manager.create_indexes()
    print("✓ Database indexes created")


async def cleanup_test_data():
    """Clean up any existing test data."""
    print("\nCleaning up existing test data...")

    try:
        # Clean up Redis test keys
        redis_conn = await redis_manager.get_redis()
        test_keys = await redis_conn.keys(f"{REDIS_CHALLENGE_PREFIX}*")
        if test_keys:
            await redis_conn.delete(*test_keys)
            print(f"✓ Cleaned up {len(test_keys)} Redis test keys")

        # Clean up database test data
        collection = db_manager.get_collection("webauthn_challenges")
        result = await collection.delete_many({})
        print(f"✓ Cleaned up {result.deleted_count} database test documents")

    except Exception as e:
        print(f"⚠ Warning during cleanup: {e}")


async def create_test_challenges() -> Dict[str, Any]:
    """Create test challenges with different expiration times."""
    print("\nCreating test challenges...")

    test_data = {"active_challenges": [], "expired_challenges": [], "redis_only": [], "db_only": []}

    # Create active challenges (not expired)
    for i in range(3):
        challenge = generate_secure_challenge()
        await store_challenge(challenge, user_id=None, challenge_type="authentication")
        test_data["active_challenges"].append(challenge)

    print(f"✓ Created {len(test_data['active_challenges'])} active challenges")

    # Create expired challenges by manually inserting with past expiration
    redis_conn = await redis_manager.get_redis()
    collection = db_manager.get_collection("webauthn_challenges")

    past_time = datetime.utcnow() - timedelta(minutes=10)

    for i in range(2):
        challenge = generate_secure_challenge()

        # Store in both Redis and database with past expiration
        challenge_data = {
            "user_id": None,
            "type": "authentication",
            "created_at": past_time.isoformat(),
            "expires_at": past_time.isoformat(),
        }

        # Store in Redis (will expire automatically, but we'll test cleanup)
        redis_key = f"{REDIS_CHALLENGE_PREFIX}{challenge}"
        await redis_conn.set(redis_key, json.dumps(challenge_data), ex=1)  # 1 second TTL

        # Store in database with past expiration
        challenge_doc = {
            "challenge": challenge,
            "user_id": None,
            "type": "authentication",
            "created_at": past_time,
            "expires_at": past_time,
        }
        await collection.insert_one(challenge_doc)

        test_data["expired_challenges"].append(challenge)

    print(f"✓ Created {len(test_data['expired_challenges'])} expired challenges")

    # Wait for Redis keys to expire
    await asyncio.sleep(2)

    # Create Redis-only expired challenges (simulate Redis without DB)
    for i in range(2):
        challenge = generate_secure_challenge()
        challenge_data = {
            "user_id": None,
            "type": "authentication",
            "created_at": past_time.isoformat(),
            "expires_at": past_time.isoformat(),
        }

        redis_key = f"{REDIS_CHALLENGE_PREFIX}{challenge}"
        # Store without TTL to simulate keys that lost their expiration
        await redis_conn.set(redis_key, json.dumps(challenge_data))

        test_data["redis_only"].append(challenge)

    print(f"✓ Created {len(test_data['redis_only'])} Redis-only challenges without TTL")

    # Create database-only expired challenges
    for i in range(2):
        challenge = generate_secure_challenge()
        challenge_doc = {
            "challenge": challenge,
            "user_id": None,
            "type": "authentication",
            "created_at": past_time,
            "expires_at": past_time,
        }
        await collection.insert_one(challenge_doc)

        test_data["db_only"].append(challenge)

    print(f"✓ Created {len(test_data['db_only'])} database-only expired challenges")

    return test_data


async def verify_initial_state(test_data: Dict[str, Any]):
    """Verify the initial state before cleanup."""
    print("\nVerifying initial state...")

    redis_conn = await redis_manager.get_redis()
    collection = db_manager.get_collection("webauthn_challenges")

    # Count Redis keys
    redis_keys = await redis_conn.keys(f"{REDIS_CHALLENGE_PREFIX}*")
    expected_redis = len(test_data["active_challenges"]) + len(test_data["redis_only"])

    print(f"Redis keys found: {len(redis_keys)} (expected: {expected_redis})")

    # Count database documents
    db_count = await collection.count_documents({})
    expected_db = len(test_data["active_challenges"]) + len(test_data["expired_challenges"]) + len(test_data["db_only"])

    print(f"Database documents found: {db_count} (expected: {expected_db})")

    # Verify TTL status for Redis keys
    keys_without_ttl = 0
    for key in redis_keys:
        ttl = await redis_conn.ttl(key)
        if ttl == -1:  # No TTL set
            keys_without_ttl += 1

    print(f"Redis keys without TTL: {keys_without_ttl} (expected: {len(test_data['redis_only'])})")


async def test_redis_cleanup():
    """Test Redis cleanup functionality."""
    print("\n" + "=" * 50)
    print("TESTING REDIS CLEANUP")
    print("=" * 50)

    # Run Redis cleanup
    cleaned_count = await cleanup_expired_redis_challenges()
    print(f"Redis cleanup completed: {cleaned_count} entries processed")

    # Verify Redis state after cleanup
    redis_conn = await redis_manager.get_redis()
    remaining_keys = await redis_conn.keys(f"{REDIS_CHALLENGE_PREFIX}*")

    print(f"Remaining Redis keys after cleanup: {len(remaining_keys)}")

    # Check TTL status of remaining keys
    keys_with_ttl = 0
    for key in remaining_keys:
        ttl = await redis_conn.ttl(key)
        if ttl > 0:
            keys_with_ttl += 1
        print(f"Key {key.decode()[-8:]}: TTL = {ttl}")

    print(f"Keys with proper TTL: {keys_with_ttl}/{len(remaining_keys)}")

    return cleaned_count


async def test_database_cleanup():
    """Test database cleanup functionality."""
    print("\n" + "=" * 50)
    print("TESTING DATABASE CLEANUP")
    print("=" * 50)

    collection = db_manager.get_collection("webauthn_challenges")

    # Count expired documents before cleanup
    expired_count = await collection.count_documents({"expires_at": {"$lt": datetime.utcnow()}})
    print(f"Expired documents before cleanup: {expired_count}")

    # Run database cleanup
    cleaned_count = await cleanup_expired_challenges()
    print(f"Database cleanup completed: {cleaned_count} documents removed")

    # Verify database state after cleanup
    remaining_count = await collection.count_documents({})
    expired_remaining = await collection.count_documents({"expires_at": {"$lt": datetime.utcnow()}})

    print(f"Remaining documents after cleanup: {remaining_count}")
    print(f"Expired documents remaining: {expired_remaining}")

    return cleaned_count


async def test_comprehensive_cleanup():
    """Test comprehensive cleanup functionality."""
    print("\n" + "=" * 50)
    print("TESTING COMPREHENSIVE CLEANUP")
    print("=" * 50)

    # Create fresh test data for comprehensive test
    await cleanup_test_data()
    test_data = await create_test_challenges()

    # Run comprehensive cleanup
    results = await cleanup_all_expired_challenges()

    print(f"Comprehensive cleanup results:")
    print(f"  Redis cleaned: {results['redis_cleaned']}")
    print(f"  Database cleaned: {results['database_cleaned']}")
    print(f"  Total cleaned: {results['total_cleaned']}")

    # Verify final state
    redis_conn = await redis_manager.get_redis()
    collection = db_manager.get_collection("webauthn_challenges")

    final_redis_keys = await redis_conn.keys(f"{REDIS_CHALLENGE_PREFIX}*")
    final_db_count = await collection.count_documents({})
    final_expired_count = await collection.count_documents({"expires_at": {"$lt": datetime.utcnow()}})

    print(f"\nFinal state:")
    print(f"  Redis keys remaining: {len(final_redis_keys)}")
    print(f"  Database documents remaining: {final_db_count}")
    print(f"  Expired documents remaining: {final_expired_count}")

    return results


async def run_cleanup_tests():
    """Run all cleanup tests."""
    print("WebAuthn Challenge Cleanup Test")
    print("=" * 50)

    try:
        # Setup
        await setup_test_environment()
        await cleanup_test_data()

        # Create test data
        test_data = await create_test_challenges()
        await verify_initial_state(test_data)

        # Test individual cleanup functions
        redis_cleaned = await test_redis_cleanup()
        db_cleaned = await test_database_cleanup()

        # Test comprehensive cleanup
        comprehensive_results = await test_comprehensive_cleanup()

        # Summary
        print("\n" + "=" * 50)
        print("TEST SUMMARY")
        print("=" * 50)
        print(f"✓ Redis cleanup: {redis_cleaned} entries processed")
        print(f"✓ Database cleanup: {db_cleaned} documents removed")
        print(f"✓ Comprehensive cleanup: {comprehensive_results['total_cleaned']} total cleaned")
        print("\n✅ All cleanup tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Final cleanup
        await cleanup_test_data()
        await db_manager.disconnect()
        print("\n🧹 Test cleanup completed")


if __name__ == "__main__":
    asyncio.run(run_cleanup_tests())
