"""
Permanent token validation service.

This module provides Redis cache-first validation for permanent tokens
with database fallback and user metadata caching for optimal performance.
"""

from datetime import datetime, timedelta
import json
from typing import Any, Dict, Optional

from bson import ObjectId
from jose import JWTError, jwt

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth.models import PermanentTokenCacheData
from second_brain_database.routes.auth.services.permanent_tokens.generator import hash_token, update_last_used
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Permanent Token Validator]")
security_logger = SecurityLogger(prefix="[PERM-TOKEN-VALIDATOR-SECURITY]")
db_logger = DatabaseLogger(prefix="[PERM-TOKEN-VALIDATOR-DB]")

# Cache TTL for permanent token data (24 hours)
CACHE_TTL_SECONDS = 24 * 60 * 60


def get_cache_key(token_hash: str) -> str:
    """
    Generate Redis cache key for permanent token data.

    Args:
        token_hash (str): SHA-256 hash of the token

    Returns:
        str: Redis cache key
    """
    return f"permanent_token:{token_hash}"


@log_performance("cache_token_data")
async def cache_token_data(token_hash: str, user_data: PermanentTokenCacheData) -> bool:
    """
    Cache permanent token user data in Redis.

    Args:
        token_hash (str): SHA-256 hash of the token
        user_data (PermanentTokenCacheData): User data to cache

    Returns:
        bool: True if caching was successful, False otherwise
    """
    start_time = datetime.utcnow()
    logger.debug("Caching permanent token data for user: %s", user_data.username)

    try:
        cache_key = get_cache_key(token_hash)
        cache_data = user_data.model_dump_json()

        redis_conn = await redis_manager.get_redis()
        await redis_conn.setex(cache_key, CACHE_TTL_SECONDS, cache_data)

        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.info(
            "Successfully cached permanent token data for hash: %s (%.2fms)", token_hash[:16] + "...", response_time
        )

        # Log security event for token caching
        log_security_event(
            event_type="permanent_token_cached",
            user_id=user_data.username,
            success=True,
            details={
                "token_hash_prefix": token_hash[:8],
                "cache_ttl_seconds": CACHE_TTL_SECONDS,
                "response_time_ms": response_time,
            },
        )

        # Record cache set for monitoring
        try:
            from .monitoring import record_cache_set

            record_cache_set(response_time, token_hash, True)
        except ImportError:
            logger.debug("Monitoring module not available for cache metrics")

        return True
    except Exception as e:
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.error("Failed to cache permanent token data: %s", e, exc_info=True)

        log_error_with_context(
            e,
            context={
                "token_hash_prefix": token_hash[:8],
                "username": user_data.username,
                "response_time_ms": response_time,
            },
            operation="cache_token_data",
        )

        # Record failed cache set for monitoring
        try:
            from .monitoring import record_cache_set

            record_cache_set(response_time, token_hash, False)
        except ImportError:
            logger.debug("Monitoring module not available for cache metrics")

        return False


@log_performance("get_cached_token_data")
async def get_cached_token_data(token_hash: str) -> Optional[PermanentTokenCacheData]:
    """
    Retrieve cached permanent token data from Redis.

    Args:
        token_hash (str): SHA-256 hash of the token

    Returns:
        Optional[PermanentTokenCacheData]: Cached user data if found, None otherwise
    """
    start_time = datetime.utcnow()
    logger.debug("Retrieving cached token data for hash: %s", token_hash[:16] + "...")

    try:
        cache_key = get_cache_key(token_hash)
        redis_conn = await redis_manager.get_redis()
        cached_data = await redis_conn.get(cache_key)

        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000

        if cached_data:
            data_dict = json.loads(cached_data)
            logger.info("Cache hit for permanent token: %s (%.2fms)", token_hash[:16] + "...", response_time)

            # Log security event for cache hit
            log_security_event(
                event_type="permanent_token_cache_hit",
                user_id=data_dict.get("username", "unknown"),
                success=True,
                details={"token_hash_prefix": token_hash[:8], "response_time_ms": response_time},
            )

            # Record cache hit for monitoring
            try:
                from .monitoring import record_cache_hit

                record_cache_hit(response_time, token_hash)
            except ImportError:
                logger.debug("Monitoring module not available for cache metrics")

            return PermanentTokenCacheData(**data_dict)

        logger.debug("Cache miss for permanent token: %s (%.2fms)", token_hash[:16] + "...", response_time)

        # Record cache miss for monitoring
        try:
            from .monitoring import record_cache_miss

            record_cache_miss(response_time, token_hash)
        except ImportError:
            logger.debug("Monitoring module not available for cache metrics")

        return None
    except Exception as e:
        response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.error("Failed to retrieve cached token data: %s", e, exc_info=True)

        log_error_with_context(
            e,
            context={"token_hash_prefix": token_hash[:8], "response_time_ms": response_time},
            operation="get_cached_token_data",
        )

        # Record cache miss with error for monitoring
        try:
            from .monitoring import record_cache_miss

            record_cache_miss(response_time, token_hash)
        except ImportError:
            logger.debug("Monitoring module not available for cache metrics")

        return None


async def invalidate_token_cache(token_hash: str) -> bool:
    """
    Remove permanent token data from Redis cache.

    Args:
        token_hash (str): SHA-256 hash of the token

    Returns:
        bool: True if invalidation was successful, False otherwise
    """
    try:
        cache_key = get_cache_key(token_hash)
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.delete(cache_key)
        logger.debug("Invalidated cache for permanent token: %s", token_hash[:16] + "...")
        return result > 0
    except Exception as e:
        logger.error("Failed to invalidate token cache: %s", e)
        return False


async def validate_permanent_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate a permanent JWT token with Redis cache-first approach.

    This function:
    1. Decodes and validates the JWT structure
    2. Checks Redis cache for user data
    3. Falls back to database if cache miss
    4. Updates last_used timestamp
    5. Caches user data for future requests

    Args:
        token (str): The permanent JWT token to validate

    Returns:
        Optional[Dict[str, Any]]: User data if token is valid, None otherwise
    """
    try:
        # First, decode and validate JWT structure
        secret_key = getattr(settings, "SECRET_KEY", None)
        if hasattr(secret_key, "get_secret_value"):
            secret_key = secret_key.get_secret_value()

        if not isinstance(secret_key, (str, bytes)) or not secret_key:
            logger.error("JWT secret key is missing or invalid")
            return None

        # Decode JWT without expiration verification for permanent tokens
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False},  # Skip expiration check for permanent tokens
        )

        # Verify this is a permanent token
        if payload.get("token_type") != "permanent":
            logger.warning("Token is not a permanent token type")
            return None

        # Extract token info
        username = payload.get("username") or payload.get("sub")
        token_id = payload.get("token_id")

        if not username or not token_id:
            logger.warning("Permanent token missing required claims")
            return None

        # Hash token for database/cache lookup
        token_hash = hash_token(token)

        # Try Redis cache first
        cached_data = await get_cached_token_data(token_hash)
        if cached_data:
            # Update last used timestamp asynchronously
            await update_last_used(token_hash)

            # Return user data from cache
            return {
                "_id": cached_data.user_id,
                "username": cached_data.username,
                "email": cached_data.email,
                "role": cached_data.role,
                "is_verified": cached_data.is_verified,
                "is_active": True,  # Permanent tokens are only for active users
                "token_type": "permanent",
            }

        # Cache miss - check database
        logger.debug("Cache miss, checking database for permanent token")

        # Check token exists and is not revoked
        tokens_collection = db_manager.get_collection("permanent_tokens")
        token_doc = await tokens_collection.find_one({"token_hash": token_hash, "is_revoked": False})

        if not token_doc:
            logger.warning("Permanent token not found or revoked")
            return None

        # Get user data
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": ObjectId(token_doc["user_id"])})

        if not user:
            logger.warning("User not found for permanent token")
            return None

        # Check if user is still active
        if not user.get("is_active", True):
            logger.warning("User account is inactive for permanent token")
            return None

        # Update last used timestamp
        await update_last_used(token_hash)

        # Cache user data for future requests
        cache_data = PermanentTokenCacheData(
            user_id=str(user["_id"]),
            username=user["username"],
            email=user["email"],
            role=user.get("role", "user"),
            is_verified=user.get("is_verified", False),
            last_used_at=datetime.utcnow(),
        )
        await cache_token_data(token_hash, cache_data)

        logger.debug("Permanent token validated successfully for user: %s", username)

        # Return user data
        return {
            "_id": user["_id"],
            "username": user["username"],
            "email": user["email"],
            "role": user.get("role", "user"),
            "is_verified": user.get("is_verified", False),
            "is_active": user.get("is_active", True),
            "token_type": "permanent",
        }

    except JWTError as e:
        logger.warning("Invalid permanent token JWT: %s", e)
        return None
    except Exception as e:
        logger.error("Error validating permanent token: %s", e)
        return None


def is_permanent_token(token: str) -> bool:
    """
    Check if a JWT token is a permanent token without full validation.

    Args:
        token (str): JWT token to check

    Returns:
        bool: True if token is permanent type, False otherwise
    """
    try:
        # Decode without verification to check token type
        # Get the actual secret key but disable signature verification
        secret_key = getattr(settings, "SECRET_KEY", None)
        if hasattr(secret_key, "get_secret_value"):
            secret_key = secret_key.get_secret_value()

        payload = jwt.decode(
            token,
            key=secret_key,
            algorithms=[settings.ALGORITHM],
            options={"verify_signature": False, "verify_exp": False},
        )
        return payload.get("token_type") == "permanent"
    except Exception:
        return False
