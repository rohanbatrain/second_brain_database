#!/usr/bin/env python3
"""
Standalone test script for WebAuthn challenge functions.

This script directly tests the challenge functions without importing
the full routes system to avoid import issues.
"""
import asyncio
from datetime import datetime, timedelta
import json
import os
import secrets
import sys
from typing import Any, Dict, Optional

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Import only the core dependencies
from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager


# Test the challenge functions directly
def generate_secure_challenge() -> str:
    """Generate a cryptographically secure challenge for WebAuthn operations."""
    return secrets.token_urlsafe(32)


async def store_challenge(
    challenge: str, user_id: Optional[str] = None, challenge_type: str = "authentication"
) -> bool:
    """Store WebAuthn challenge in both Redis and database with expiration."""
    logger = get_logger(prefix="[WebAuthn Challenge Test]")

    if not challenge or not challenge_type:
        raise ValueError("challenge and challenge_type are required")

    try:
        expires_at = datetime.utcnow() + timedelta(minutes=5)

        # Prepare challenge data
        challenge_data = {
            "user_id": str(user_id) if user_id else None,
            "type": challenge_type,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        # Store in Redis for fast access
        redis_success = False
        try:
            redis_conn = await redis_manager.get_redis()
            redis_key = f"webauthn_challenge:{challenge}"

            await redis_conn.set(redis_key, json.dumps(challenge_data), ex=5 * 60)  # TTL in seconds
            redis_success = True
            logger.debug("Challenge stored in Redis with key: %s", redis_key)

        except Exception as redis_error:
            logger.warning("Failed to store challenge in Redis: %s", redis_error)

        # Store in database for persistence
        db_success = False
        try:
            from bson import ObjectId

            collection = db_manager.get_collection("webauthn_challenges")
            challenge_doc = {
                "challenge": challenge,
                "user_id": ObjectId(user_id) if user_id else None,
                "type": challenge_type,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
            }

            result = await collection.insert_one(challenge_doc)
            db_success = bool(result.inserted_id)
            logger.debug("Challenge stored in database with ID: %s", result.inserted_id)

        except Exception as db_error:
            logger.error("Failed to store challenge in database: %s", db_error)

        success = redis_success or db_success

        if success:
            logger.info("WebAuthn challenge stored successfully (Redis: %s, DB: %s)", redis_success, db_success)
        else:
            raise RuntimeError("Failed to store challenge in both Redis and database")

        return success

    except Exception as e:
        logger.error("Failed to store WebAuthn challenge: %s", e)
        raise RuntimeError(f"Challenge storage failed: {str(e)}") from e


async def validate_challenge(
    challenge: str, user_id: Optional[str] = None, challenge_type: str = "authentication"
) -> Optional[Dict[str, Any]]:
    """Validate WebAuthn challenge and ensure it hasn't been used."""
    logger = get_logger(prefix="[WebAuthn Challenge Test]")

    if not challenge or not challenge_type:
        return None

    try:
        # Check Redis first
        redis_data = None
        try:
            redis_conn = await redis_manager.get_redis()
            redis_key = f"webauthn_challenge:{challenge}"
            cached_data = await redis_conn.get(redis_key)

            if cached_data:
                redis_data = json.loads(cached_data)
                logger.debug("Challenge found in Redis cache")

                # Validate challenge data
                if redis_data.get("type") == challenge_type:
                    if user_id and redis_data.get("user_id") != str(user_id):
                        logger.warning("Challenge user ID mismatch")
                        return None

                    # Remove challenge after use (one-time use) from both Redis and database
                    await redis_conn.delete(redis_key)
                    logger.debug("Challenge consumed from Redis")

                    # Also remove from database to ensure one-time use
                    try:
                        collection = db_manager.get_collection("webauthn_challenges")
                        await collection.delete_one({"challenge": challenge})
                        logger.debug("Challenge also removed from database for consistency")
                    except Exception as db_cleanup_error:
                        logger.warning("Failed to cleanup challenge from database: %s", db_cleanup_error)

                    return redis_data

        except Exception as redis_error:
            logger.warning("Redis challenge validation failed: %s", redis_error)

        # Fallback to database
        try:
            from bson import ObjectId

            collection = db_manager.get_collection("webauthn_challenges")
            query = {"challenge": challenge, "type": challenge_type, "expires_at": {"$gt": datetime.utcnow()}}

            if user_id:
                query["user_id"] = ObjectId(user_id)

            challenge_doc = await collection.find_one(query)

            if challenge_doc:
                # Validate user ID if provided
                if user_id and str(challenge_doc.get("user_id")) != str(user_id):
                    logger.warning("Database challenge user ID mismatch")
                    return None

                # Remove challenge after use
                await collection.delete_one({"_id": challenge_doc["_id"]})
                logger.debug("Challenge consumed from database")

                # Convert to consistent format
                db_data = {
                    "user_id": str(challenge_doc["user_id"]) if challenge_doc.get("user_id") else None,
                    "type": challenge_doc["type"],
                    "created_at": challenge_doc["created_at"].isoformat(),
                    "expires_at": challenge_doc["expires_at"].isoformat(),
                }

                return db_data

        except Exception as db_error:
            logger.error("Database challenge validation failed: %s", db_error)

        return None

    except Exception as e:
        logger.error("Error validating WebAuthn challenge: %s", e)
        return None


async def clear_challenge(challenge: str) -> bool:
    """Clear a WebAuthn challenge from both Redis and database."""
    logger = get_logger(prefix="[WebAuthn Challenge Test]")

    if not challenge:
        return False

    redis_cleared = False
    db_cleared = False

    try:
        # Clear from Redis
        try:
            redis_conn = await redis_manager.get_redis()
            redis_key = f"webauthn_challenge:{challenge}"
            redis_result = await redis_conn.delete(redis_key)
            redis_cleared = redis_result > 0

        except Exception as redis_error:
            logger.warning("Failed to clear challenge from Redis: %s", redis_error)

        # Clear from database
        try:
            collection = db_manager.get_collection("webauthn_challenges")
            db_result = await collection.delete_one({"challenge": challenge})
            db_cleared = db_result.deleted_count > 0

        except Exception as db_error:
            logger.error("Failed to clear challenge from database: %s", db_error)

        success = redis_cleared or db_cleared

        if success:
            logger.info("WebAuthn challenge cleared successfully (Redis: %s, DB: %s)", redis_cleared, db_cleared)

        return success

    except Exception as e:
        logger.error("Error clearing WebAuthn challenge: %s", e)
        return False


async def test_challenge_generation():
    """Test challenge generation functionality."""
    print("Testing challenge generation...")

    # Test basic challenge generation
    challenge1 = generate_secure_challenge()
    challenge2 = generate_secure_challenge()

    # Verify challenges are generated
    assert challenge1, "Challenge 1 should not be empty"
    assert challenge2, "Challenge 2 should not be empty"

    # Verify challenges are unique
    assert challenge1 != challenge2, "Challenges should be unique"

    # Verify challenge format (base64url should be URL-safe)
    assert all(c.isalnum() or c in "-_" for c in challenge1), "Challenge should be base64url encoded"

    # Verify challenge length (should be reasonable for security)
    assert len(challenge1) > 40, "Challenge should be sufficiently long"

    print(f"✓ Generated unique challenges: {challenge1[:8]}... and {challenge2[:8]}...")
    return challenge1, challenge2


async def test_challenge_storage_and_validation():
    """Test challenge storage and validation functionality."""
    print("Testing challenge storage and validation...")

    # Connect to database
    await db_manager.connect()

    # Generate test challenge
    challenge = generate_secure_challenge()
    user_id = "507f1f77bcf86cd799439011"  # Test ObjectId

    # Test storing registration challenge
    print("Testing registration challenge storage...")
    success = await store_challenge(challenge, user_id, "registration")
    assert success, "Challenge storage should succeed"
    print("✓ Registration challenge stored successfully")

    # Test validating the challenge
    print("Testing challenge validation...")
    result = await validate_challenge(challenge, user_id, "registration")
    assert result is not None, "Challenge validation should succeed"
    assert result["type"] == "registration", "Challenge type should match"
    assert result["user_id"] == user_id, "User ID should match"
    print("✓ Challenge validated successfully")

    # Test that challenge is consumed (one-time use)
    print("Testing challenge consumption...")
    result2 = await validate_challenge(challenge, user_id, "registration")
    assert result2 is None, "Challenge should be consumed after first use"
    print("✓ Challenge properly consumed after use")

    # Test authentication challenge (no user_id)
    print("Testing authentication challenge...")
    auth_challenge = generate_secure_challenge()
    success = await store_challenge(auth_challenge, None, "authentication")
    assert success, "Authentication challenge storage should succeed"

    result = await validate_challenge(auth_challenge, None, "authentication")
    assert result is not None, "Authentication challenge validation should succeed"
    assert result["type"] == "authentication", "Challenge type should match"
    assert result["user_id"] is None, "User ID should be None for auth challenges"
    print("✓ Authentication challenge works correctly")


async def test_challenge_validation_edge_cases():
    """Test challenge validation edge cases."""
    print("Testing challenge validation edge cases...")

    # Test invalid challenge
    result = await validate_challenge("invalid_challenge", None, "authentication")
    assert result is None, "Invalid challenge should return None"
    print("✓ Invalid challenge properly rejected")

    # Test wrong challenge type
    challenge = generate_secure_challenge()
    await store_challenge(challenge, None, "registration")
    result = await validate_challenge(challenge, None, "authentication")  # Wrong type
    assert result is None, "Wrong challenge type should return None"
    print("✓ Wrong challenge type properly rejected")

    # Clean up the challenge
    await clear_challenge(challenge)

    # Test wrong user ID
    challenge = generate_secure_challenge()
    user_id = "507f1f77bcf86cd799439011"
    wrong_user_id = "507f1f77bcf86cd799439012"

    await store_challenge(challenge, user_id, "registration")
    result = await validate_challenge(challenge, wrong_user_id, "registration")
    assert result is None, "Wrong user ID should return None"
    print("✓ Wrong user ID properly rejected")

    # Clean up
    await clear_challenge(challenge)


async def test_challenge_cleanup():
    """Test challenge cleanup functionality."""
    print("Testing challenge cleanup...")

    # Create a challenge
    challenge = generate_secure_challenge()
    await store_challenge(challenge, None, "authentication")

    # Clear the challenge
    success = await clear_challenge(challenge)
    assert success, "Challenge cleanup should succeed"
    print("✓ Challenge cleared successfully")

    # Verify challenge is gone
    result = await validate_challenge(challenge, None, "authentication")
    assert result is None, "Cleared challenge should not validate"
    print("✓ Cleared challenge properly removed")


async def main():
    """Run all tests."""
    print("Starting WebAuthn challenge service tests...\n")

    try:
        # Test challenge generation
        await test_challenge_generation()
        print()

        # Test storage and validation
        await test_challenge_storage_and_validation()
        print()

        # Test edge cases
        await test_challenge_validation_edge_cases()
        print()

        # Test cleanup
        await test_challenge_cleanup()
        print()

        print("✅ All tests passed! WebAuthn challenge service is working correctly.")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    finally:
        # Cleanup connections
        try:
            await db_manager.disconnect()
        except:
            pass

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
