"""
WebAuthn challenge generation and storage service.

This module provides functionality to generate and manage WebAuthn challenges
for both registration and authentication flows. Challenges are stored in both
Redis (for fast access) and MongoDB (for persistence) with automatic expiration.
"""

from datetime import datetime, timedelta
import json
import secrets
from typing import Any, Dict, Optional

from bson import ObjectId

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[WebAuthn Challenge]")
security_logger = SecurityLogger(prefix="[WEBAUTHN-CHALLENGE-SECURITY]")
db_logger = DatabaseLogger(prefix="[WEBAUTHN-CHALLENGE-DB]")

# Challenge configuration
CHALLENGE_EXPIRY_MINUTES = 5
CHALLENGE_LENGTH_BYTES = 32  # 32 bytes = 256 bits of entropy
REDIS_CHALLENGE_PREFIX = "webauthn_challenge:"


def generate_secure_challenge() -> str:
    """
    Generate a cryptographically secure challenge for WebAuthn operations.

    Uses the same pattern as permanent token generator with secrets.token_urlsafe()
    to ensure cryptographic security and URL-safe encoding.

    Returns:
        str: A secure random challenge (base64url encoded, ~43 characters)
    """
    return secrets.token_urlsafe(CHALLENGE_LENGTH_BYTES)


@log_performance("store_webauthn_challenge", log_args=False)
async def store_challenge(
    challenge: str, user_id: Optional[str] = None, challenge_type: str = "authentication"
) -> bool:
    """
    Store WebAuthn challenge in both Redis and database with expiration.

    Follows existing Redis infrastructure patterns with TTL and database
    persistence for reliability. Uses the same dual-storage approach
    as other temporary data in the system.

    Args:
        challenge (str): The challenge string to store
        user_id (Optional[str]): User ID for registration challenges
        challenge_type (str): Type of challenge ("registration" or "authentication")

    Returns:
        bool: True if storage was successful, False otherwise

    Raises:
        RuntimeError: If storage fails in both Redis and database
    """
    logger.info("Storing WebAuthn challenge type: %s for user: %s", challenge_type, user_id or "anonymous")

    if not challenge or not challenge_type:
        logger.error("Missing required parameters: challenge=%s, type=%s", bool(challenge), bool(challenge_type))
        raise ValueError("challenge and challenge_type are required")

    try:
        expires_at = datetime.utcnow() + timedelta(minutes=CHALLENGE_EXPIRY_MINUTES)

        # Prepare challenge data
        challenge_data = {
            "user_id": str(user_id) if user_id else None,
            "type": challenge_type,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        # Log security event for challenge creation
        log_security_event(
            event_type="webauthn_challenge_created",
            user_id=user_id,
            success=False,  # Will be updated to True on success
            details={
                "challenge_type": challenge_type,
                "expires_at": expires_at.isoformat(),
                "challenge_prefix": challenge[:8] + "...",
            },
        )

        # Store in Redis for fast access (primary storage)
        redis_success = False
        try:
            redis_conn = await redis_manager.get_redis()
            redis_key = f"{REDIS_CHALLENGE_PREFIX}{challenge}"

            await redis_conn.set(
                redis_key, json.dumps(challenge_data), ex=CHALLENGE_EXPIRY_MINUTES * 60  # TTL in seconds
            )
            redis_success = True
            logger.debug("Challenge stored in Redis with key: %s", redis_key)

        except Exception as redis_error:
            logger.warning("Failed to store challenge in Redis: %s", redis_error)
            # Continue to database storage as fallback

        # Store in database for persistence (secondary storage)
        db_success = False
        try:
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

            log_database_operation(
                operation="insert_webauthn_challenge",
                collection="webauthn_challenges",
                query={},
                result={
                    "inserted_id": str(result.inserted_id),
                    "challenge_type": challenge_type,
                    "user_id": user_id,
                    "expires_at": expires_at.isoformat(),
                },
            )

            logger.debug("Challenge stored in database with ID: %s", result.inserted_id)

        except Exception as db_error:
            logger.error("Failed to store challenge in database: %s", db_error, exc_info=True)
            log_error_with_context(
                db_error,
                context={"challenge_type": challenge_type, "user_id": user_id, "challenge_prefix": challenge[:8]},
                operation="store_webauthn_challenge_db",
            )

        # Determine overall success
        success = redis_success or db_success

        if success:
            logger.info(
                "WebAuthn challenge stored successfully (Redis: %s, DB: %s) for type: %s",
                redis_success,
                db_success,
                challenge_type,
            )

            # Log successful challenge creation
            log_security_event(
                event_type="webauthn_challenge_stored",
                user_id=user_id,
                success=True,
                details={
                    "challenge_type": challenge_type,
                    "storage_redis": redis_success,
                    "storage_database": db_success,
                    "expires_at": expires_at.isoformat(),
                },
            )
        else:
            logger.error("Failed to store challenge in both Redis and database")
            log_security_event(
                event_type="webauthn_challenge_storage_failed",
                user_id=user_id,
                success=False,
                details={
                    "challenge_type": challenge_type,
                    "redis_error": not redis_success,
                    "database_error": not db_success,
                },
            )
            raise RuntimeError("Failed to store challenge in both Redis and database")

        return success

    except Exception as e:
        logger.error("Failed to store WebAuthn challenge: %s", e, exc_info=True)
        log_error_with_context(
            e,
            context={
                "challenge_type": challenge_type,
                "user_id": user_id,
                "challenge_prefix": challenge[:8] if challenge else None,
            },
            operation="store_webauthn_challenge",
        )
        raise RuntimeError(f"Challenge storage failed: {str(e)}") from e


@log_performance("validate_webauthn_challenge")
async def validate_challenge(
    challenge: str, user_id: Optional[str] = None, challenge_type: str = "authentication"
) -> Optional[Dict[str, Any]]:
    """
    Validate WebAuthn challenge and ensure it hasn't been used.

    Follows existing validation patterns with Redis-first lookup and database
    fallback. Challenges are consumed after validation (one-time use).

    Args:
        challenge (str): The challenge string to validate
        user_id (Optional[str]): Expected user ID for the challenge
        challenge_type (str): Expected challenge type

    Returns:
        Optional[Dict[str, Any]]: Challenge data if valid, None if invalid/expired
    """
    logger.debug("Validating WebAuthn challenge type: %s for user: %s", challenge_type, user_id or "anonymous")

    if not challenge or not challenge_type:
        logger.warning("Invalid validation parameters: challenge=%s, type=%s", bool(challenge), bool(challenge_type))
        return None

    try:
        # Check Redis first (primary storage)
        redis_data = None
        try:
            redis_conn = await redis_manager.get_redis()
            redis_key = f"{REDIS_CHALLENGE_PREFIX}{challenge}"
            cached_data = await redis_conn.get(redis_key)

            if cached_data:
                redis_data = json.loads(cached_data)
                logger.debug("Challenge found in Redis cache")

                # Validate challenge data
                if redis_data.get("type") == challenge_type:
                    if user_id and redis_data.get("user_id") != str(user_id):
                        logger.warning(
                            "Challenge user ID mismatch: expected %s, got %s", user_id, redis_data.get("user_id")
                        )
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

                    log_security_event(
                        event_type="webauthn_challenge_validated",
                        user_id=user_id,
                        success=True,
                        details={
                            "challenge_type": challenge_type,
                            "source": "redis",
                            "challenge_prefix": challenge[:8] + "...",
                        },
                    )

                    return redis_data
                else:
                    logger.warning(
                        "Challenge type mismatch in Redis: expected %s, got %s", challenge_type, redis_data.get("type")
                    )

        except Exception as redis_error:
            logger.warning("Redis challenge validation failed: %s", redis_error)
            # Continue to database fallback

        # Fallback to database if Redis failed or no data found
        try:
            collection = db_manager.get_collection("webauthn_challenges")
            query = {"challenge": challenge, "type": challenge_type, "expires_at": {"$gt": datetime.utcnow()}}

            if user_id:
                query["user_id"] = ObjectId(user_id)

            challenge_doc = await collection.find_one(query)

            log_database_operation(
                operation="validate_webauthn_challenge",
                collection="webauthn_challenges",
                query={
                    "challenge": challenge[:8] + "...",
                    "type": challenge_type,
                    "user_id": user_id,
                    "expires_at": "future",
                },
                result={"found": challenge_doc is not None},
            )

            if challenge_doc:
                # Validate user ID if provided
                if user_id and str(challenge_doc.get("user_id")) != str(user_id):
                    logger.warning(
                        "Database challenge user ID mismatch: expected %s, got %s",
                        user_id,
                        challenge_doc.get("user_id"),
                    )
                    return None

                # Remove challenge after use (one-time use)
                await collection.delete_one({"_id": challenge_doc["_id"]})
                logger.debug("Challenge consumed from database")

                # Convert to consistent format
                db_data = {
                    "user_id": str(challenge_doc["user_id"]) if challenge_doc.get("user_id") else None,
                    "type": challenge_doc["type"],
                    "created_at": challenge_doc["created_at"].isoformat(),
                    "expires_at": challenge_doc["expires_at"].isoformat(),
                }

                log_security_event(
                    event_type="webauthn_challenge_validated",
                    user_id=user_id,
                    success=True,
                    details={
                        "challenge_type": challenge_type,
                        "source": "database",
                        "challenge_prefix": challenge[:8] + "...",
                    },
                )

                return db_data
            else:
                logger.info("Challenge not found or expired in database")

        except Exception as db_error:
            logger.error("Database challenge validation failed: %s", db_error, exc_info=True)
            log_error_with_context(
                db_error,
                context={"challenge_type": challenge_type, "user_id": user_id, "challenge_prefix": challenge[:8]},
                operation="validate_webauthn_challenge_db",
            )

        # Challenge not found or validation failed
        log_security_event(
            event_type="webauthn_challenge_validation_failed",
            user_id=user_id,
            success=False,
            details={
                "challenge_type": challenge_type,
                "challenge_prefix": challenge[:8] + "...",
                "reason": "not_found_or_expired",
            },
        )

        return None

    except Exception as e:
        logger.error("Error validating WebAuthn challenge: %s", e, exc_info=True)
        log_error_with_context(
            e,
            context={
                "challenge_type": challenge_type,
                "user_id": user_id,
                "challenge_prefix": challenge[:8] if challenge else None,
            },
            operation="validate_webauthn_challenge",
        )
        return None


@log_performance("clear_webauthn_challenge")
async def clear_challenge(challenge: str) -> bool:
    """
    Clear a WebAuthn challenge from both Redis and database.

    Used for cleanup operations and explicit challenge invalidation.

    Args:
        challenge (str): The challenge string to clear

    Returns:
        bool: True if challenge was cleared from at least one storage
    """
    logger.debug("Clearing WebAuthn challenge: %s", challenge[:8] + "...")

    if not challenge:
        logger.warning("Cannot clear empty challenge")
        return False

    redis_cleared = False
    db_cleared = False

    try:
        # Clear from Redis
        try:
            redis_conn = await redis_manager.get_redis()
            redis_key = f"{REDIS_CHALLENGE_PREFIX}{challenge}"
            redis_result = await redis_conn.delete(redis_key)
            redis_cleared = redis_result > 0

            if redis_cleared:
                logger.debug("Challenge cleared from Redis")

        except Exception as redis_error:
            logger.warning("Failed to clear challenge from Redis: %s", redis_error)

        # Clear from database
        try:
            collection = db_manager.get_collection("webauthn_challenges")
            db_result = await collection.delete_one({"challenge": challenge})
            db_cleared = db_result.deleted_count > 0

            log_database_operation(
                operation="clear_webauthn_challenge",
                collection="webauthn_challenges",
                query={"challenge": challenge[:8] + "..."},
                result={"deleted_count": db_result.deleted_count},
            )

            if db_cleared:
                logger.debug("Challenge cleared from database")

        except Exception as db_error:
            logger.error("Failed to clear challenge from database: %s", db_error, exc_info=True)
            log_error_with_context(
                db_error, context={"challenge_prefix": challenge[:8]}, operation="clear_webauthn_challenge_db"
            )

        success = redis_cleared or db_cleared

        if success:
            logger.info("WebAuthn challenge cleared successfully (Redis: %s, DB: %s)", redis_cleared, db_cleared)
        else:
            logger.warning("Challenge not found in either Redis or database")

        return success

    except Exception as e:
        logger.error("Error clearing WebAuthn challenge: %s", e, exc_info=True)
        log_error_with_context(e, context={"challenge_prefix": challenge[:8]}, operation="clear_webauthn_challenge")
        return False


@log_performance("cleanup_expired_redis_challenges")
async def cleanup_expired_redis_challenges() -> int:
    """
    Clean up expired WebAuthn challenges from Redis.

    This function follows existing Redis cleanup patterns from the codebase,
    similar to permanent token cache cleanup. Redis should handle TTL automatically,
    but this provides monitoring and manual cleanup if needed.

    Returns:
        int: Number of Redis entries cleaned up
    """
    logger.info("Starting cleanup of expired WebAuthn challenges from Redis")

    try:
        redis_conn = await redis_manager.get_redis()

        # Get all WebAuthn challenge keys
        challenge_pattern = f"{REDIS_CHALLENGE_PREFIX}*"
        challenge_keys = await redis_conn.keys(challenge_pattern)

        cleaned_count = 0
        for key in challenge_keys:
            try:
                # Check if key exists and has TTL
                ttl = await redis_conn.ttl(key)
                if ttl == -1:  # Key exists but has no TTL
                    # Set TTL for keys that somehow lost their expiration
                    await redis_conn.expire(key, CHALLENGE_EXPIRY_MINUTES * 60)
                    logger.debug("Set TTL for challenge key: %s", key)
                elif ttl == -2:  # Key doesn't exist
                    cleaned_count += 1
            except Exception as e:
                logger.warning("Error checking TTL for challenge key %s: %s", key, e)

        if cleaned_count > 0:
            logger.info("Cleaned up %d expired Redis challenge entries", cleaned_count)

            log_security_event(
                event_type="webauthn_redis_challenges_cleanup",
                success=True,
                details={"cleaned_count": cleaned_count, "cleanup_time": datetime.utcnow().isoformat()},
            )
        else:
            logger.debug("No expired Redis challenge entries found during cleanup")

        return cleaned_count

    except Exception as e:
        logger.error("Failed to cleanup expired Redis challenges: %s", e, exc_info=True)
        log_error_with_context(e, context={}, operation="cleanup_expired_redis_challenges")
        return 0


@log_performance("cleanup_expired_challenges")
@log_database_operation("webauthn_challenges", "cleanup_expired")
async def cleanup_expired_challenges() -> int:
    """
    Clean up expired WebAuthn challenges from the database.

    This function is designed to be called periodically to remove expired
    challenges that weren't automatically cleaned up by TTL indexes.

    Returns:
        int: Number of expired challenges removed
    """
    logger.info("Starting cleanup of expired WebAuthn challenges")

    try:
        collection = db_manager.get_collection("webauthn_challenges")

        # Remove challenges that have expired
        result = await collection.delete_many({"expires_at": {"$lt": datetime.utcnow()}})

        deleted_count = result.deleted_count

        if deleted_count > 0:
            logger.info("Cleaned up %d expired WebAuthn challenges", deleted_count)

            log_security_event(
                event_type="webauthn_challenges_cleanup",
                success=True,
                details={"deleted_count": deleted_count, "cleanup_time": datetime.utcnow().isoformat()},
            )
        else:
            logger.debug("No expired challenges found during cleanup")

        return deleted_count

    except Exception as e:
        logger.error("Failed to cleanup expired challenges: %s", e, exc_info=True)
        log_error_with_context(e, context={}, operation="cleanup_expired_challenges")
        return 0


@log_performance("cleanup_all_expired_challenges")
async def cleanup_all_expired_challenges() -> Dict[str, int]:
    """
    Comprehensive cleanup of expired WebAuthn challenges from both Redis and database.

    This function combines both Redis and database cleanup operations following
    existing infrastructure patterns. It provides a single entry point for
    complete challenge cleanup operations.

    Returns:
        Dict[str, int]: Cleanup results with counts from both storage systems
    """
    logger.info("Starting comprehensive cleanup of expired WebAuthn challenges")

    results = {"redis_cleaned": 0, "database_cleaned": 0, "total_cleaned": 0}

    try:
        # Clean up Redis challenges first (faster operation)
        redis_cleaned = await cleanup_expired_redis_challenges()
        results["redis_cleaned"] = redis_cleaned

        # Clean up database challenges
        db_cleaned = await cleanup_expired_challenges()
        results["database_cleaned"] = db_cleaned

        # Calculate total
        results["total_cleaned"] = redis_cleaned + db_cleaned

        logger.info(
            "Comprehensive challenge cleanup completed: Redis=%d, DB=%d, Total=%d",
            redis_cleaned,
            db_cleaned,
            results["total_cleaned"],
        )

        # Log comprehensive cleanup event
        log_security_event(
            event_type="webauthn_comprehensive_cleanup",
            success=True,
            details={
                "redis_cleaned": redis_cleaned,
                "database_cleaned": db_cleaned,
                "total_cleaned": results["total_cleaned"],
                "cleanup_time": datetime.utcnow().isoformat(),
            },
        )

        return results

    except Exception as e:
        logger.error("Failed during comprehensive challenge cleanup: %s", e, exc_info=True)
        log_error_with_context(e, context=results, operation="cleanup_all_expired_challenges")
        return results
