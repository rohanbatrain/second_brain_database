"""
Permanent token cache management service.

This module provides advanced cache management functionality including:
- Cache warming for frequently used tokens
- Bulk cache operations
- Cache health monitoring
- TTL management and optimization
"""

from datetime import datetime, timedelta
import json
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth.models import PermanentTokenCacheData
from second_brain_database.routes.auth.services.permanent_tokens.validator import (
    CACHE_TTL_SECONDS,
    cache_token_data,
    get_cache_key,
    get_cached_token_data,
    invalidate_token_cache,
)
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Permanent Token Cache Manager]")
security_logger = SecurityLogger(prefix="[PERM-TOKEN-CACHE-MGR-SECURITY]")
db_logger = DatabaseLogger(prefix="[PERM-TOKEN-CACHE-MGR-DB]")

# Cache warming configuration
CACHE_WARM_BATCH_SIZE = 50
CACHE_WARM_RECENT_DAYS = 7
CACHE_WARM_MIN_USAGE = 2  # Minimum usage count to consider for warming


@log_performance("warm_user_token_cache")
async def warm_user_token_cache(user_id: str) -> int:
    """
    Warm the cache for a specific user's frequently used tokens.

    Args:
        user_id (str): MongoDB ObjectId of the user

    Returns:
        int: Number of tokens cached
    """
    logger.info("Starting cache warming for user: %s", user_id)

    try:
        # Get user's active tokens that have been used recently
        cutoff_date = datetime.utcnow() - timedelta(days=CACHE_WARM_RECENT_DAYS)

        tokens_collection = db_manager.get_collection("permanent_tokens")
        recent_tokens = (
            await tokens_collection.find(
                {"user_id": user_id, "is_revoked": False, "last_used_at": {"$gte": cutoff_date}}
            )
            .limit(CACHE_WARM_BATCH_SIZE)
            .to_list(length=None)
        )

        log_database_operation(
            operation="find_recent_tokens_for_warming",
            collection="permanent_tokens",
            query={"user_id": user_id, "is_revoked": False, "last_used_at": {"$gte": cutoff_date.isoformat()}},
            result={"token_count": len(recent_tokens), "cutoff_days": CACHE_WARM_RECENT_DAYS},
        )

        if not recent_tokens:
            logger.info("No recent tokens found for cache warming for user: %s", user_id)
            return 0

        # Get user data for caching
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": ObjectId(user_id)})

        log_database_operation(
            operation="get_user_for_cache_warming",
            collection="users",
            query={"_id": user_id},
            result={"found": user is not None},
        )

        if not user:
            logger.warning("User not found for cache warming: %s", user_id)
            log_security_event(
                event_type="cache_warming_user_not_found",
                user_id=user_id,
                success=False,
                details={"user_id": user_id, "token_count": len(recent_tokens)},
            )
            return 0

        # Cache user data for each token
        cached_count = 0
        cache_data = PermanentTokenCacheData(
            user_id=user_id,
            username=user["username"],
            email=user["email"],
            role=user.get("role", "user"),
            is_verified=user.get("is_verified", False),
            last_used_at=datetime.utcnow(),
        )

        for token_doc in recent_tokens:
            token_hash = token_doc["token_hash"]
            if await cache_token_data(token_hash, cache_data):
                cached_count += 1

        logger.info(
            "Cache warmed for user %s: %d/%d tokens cached successfully", user_id, cached_count, len(recent_tokens)
        )

        # Log security event for cache warming completion
        log_security_event(
            event_type="user_cache_warmed",
            user_id=user["username"],
            success=True,
            details={
                "user_id": user_id,
                "tokens_found": len(recent_tokens),
                "tokens_cached": cached_count,
                "cache_success_rate": round((cached_count / len(recent_tokens)) * 100, 2) if recent_tokens else 0,
            },
        )

        return cached_count

    except Exception as e:
        logger.error("Error warming cache for user %s: %s", user_id, e, exc_info=True)
        log_error_with_context(
            e, context={"user_id": user_id, "cutoff_days": CACHE_WARM_RECENT_DAYS}, operation="warm_user_token_cache"
        )
        return 0


async def warm_frequently_used_tokens() -> int:
    """
    Warm the cache for frequently used tokens across all users.

    Returns:
        int: Total number of tokens cached
    """
    try:
        # Find tokens that have been used recently and frequently
        cutoff_date = datetime.utcnow() - timedelta(days=CACHE_WARM_RECENT_DAYS)

        tokens_collection = db_manager.get_collection("permanent_tokens")

        # Aggregate to find frequently used tokens
        pipeline = [
            {"$match": {"is_revoked": False, "last_used_at": {"$gte": cutoff_date}}},
            {"$group": {"_id": "$user_id", "token_count": {"$sum": 1}, "tokens": {"$push": "$$ROOT"}}},
            {"$match": {"token_count": {"$gte": CACHE_WARM_MIN_USAGE}}},
            {"$limit": CACHE_WARM_BATCH_SIZE},
        ]

        cursor = tokens_collection.aggregate(pipeline)
        total_cached = 0

        async for user_group in cursor:
            user_id = user_group["_id"]
            cached_count = await warm_user_token_cache(user_id)
            total_cached += cached_count

        logger.info("Cache warming completed: %d tokens cached across all users", total_cached)
        return total_cached

    except Exception as e:
        logger.error("Error during cache warming: %s", e)
        return 0


async def invalidate_user_token_cache(user_id: str) -> int:
    """
    Invalidate all cached tokens for a specific user.

    Args:
        user_id (str): MongoDB ObjectId of the user

    Returns:
        int: Number of cache entries invalidated
    """
    try:
        # Get all user's tokens
        tokens_collection = db_manager.get_collection("permanent_tokens")
        user_tokens = await tokens_collection.find({"user_id": user_id, "is_revoked": False}).to_list(length=None)

        invalidated_count = 0
        for token_doc in user_tokens:
            token_hash = token_doc["token_hash"]
            if await invalidate_token_cache(token_hash):
                invalidated_count += 1

        logger.info("Invalidated %d cache entries for user %s", invalidated_count, user_id)
        return invalidated_count

    except Exception as e:
        logger.error("Error invalidating cache for user %s: %s", user_id, e)
        return 0


async def get_cache_statistics() -> Dict[str, Any]:
    """
    Get cache statistics and health information.

    Returns:
        Dict[str, Any]: Cache statistics including hit rates, memory usage, etc.
    """
    try:
        redis_conn = await redis_manager.get_redis()

        # Get Redis info
        redis_info = await redis_conn.info()

        # Count permanent token cache keys
        cache_pattern = "permanent_token:*"
        cache_keys = await redis_conn.keys(cache_pattern)
        cache_count = len(cache_keys)

        # Calculate memory usage for permanent token cache
        cache_memory = 0
        if cache_keys:
            # Sample a few keys to estimate memory usage
            sample_size = min(10, len(cache_keys))
            sample_keys = cache_keys[:sample_size]

            for key in sample_keys:
                try:
                    memory_usage = await redis_conn.memory_usage(key)
                    if memory_usage:
                        cache_memory += memory_usage
                except Exception:
                    pass  # Skip if memory_usage command not available

            # Extrapolate to all keys
            if sample_size > 0:
                cache_memory = (cache_memory * cache_count) // sample_size

        stats = {
            "cache_count": cache_count,
            "cache_memory_bytes": cache_memory,
            "cache_memory_mb": round(cache_memory / (1024 * 1024), 2),
            "cache_ttl_seconds": CACHE_TTL_SECONDS,
            "redis_connected_clients": redis_info.get("connected_clients", 0),
            "redis_used_memory": redis_info.get("used_memory", 0),
            "redis_used_memory_human": redis_info.get("used_memory_human", "0B"),
            "redis_keyspace_hits": redis_info.get("keyspace_hits", 0),
            "redis_keyspace_misses": redis_info.get("keyspace_misses", 0),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Calculate hit rate
        hits = stats["redis_keyspace_hits"]
        misses = stats["redis_keyspace_misses"]
        total_requests = hits + misses

        if total_requests > 0:
            stats["cache_hit_rate"] = round((hits / total_requests) * 100, 2)
        else:
            stats["cache_hit_rate"] = 0.0

        return stats

    except Exception as e:
        logger.error("Error getting cache statistics: %s", e)
        return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}


async def cleanup_expired_cache_entries() -> int:
    """
    Clean up expired cache entries (Redis should handle this automatically with TTL).
    This function is mainly for monitoring and manual cleanup if needed.

    Returns:
        int: Number of entries cleaned up
    """
    try:
        redis_conn = await redis_manager.get_redis()

        # Get all permanent token cache keys
        cache_pattern = "permanent_token:*"
        cache_keys = await redis_conn.keys(cache_pattern)

        cleaned_count = 0
        for key in cache_keys:
            try:
                # Check if key exists and has TTL
                ttl = await redis_conn.ttl(key)
                if ttl == -1:  # Key exists but has no TTL
                    # Set TTL for keys that somehow lost their expiration
                    await redis_conn.expire(key, CACHE_TTL_SECONDS)
                    logger.debug("Set TTL for cache key: %s", key)
                elif ttl == -2:  # Key doesn't exist
                    cleaned_count += 1
            except Exception as e:
                logger.warning("Error checking TTL for key %s: %s", key, e)

        if cleaned_count > 0:
            logger.info("Cleaned up %d expired cache entries", cleaned_count)

        return cleaned_count

    except Exception as e:
        logger.error("Error during cache cleanup: %s", e)
        return 0


async def refresh_token_cache(token_hash: str) -> bool:
    """
    Refresh cache data for a specific token by fetching fresh data from database.

    Args:
        token_hash (str): SHA-256 hash of the token

    Returns:
        bool: True if cache was refreshed successfully, False otherwise
    """
    try:
        # Get token from database
        tokens_collection = db_manager.get_collection("permanent_tokens")
        token_doc = await tokens_collection.find_one({"token_hash": token_hash, "is_revoked": False})

        if not token_doc:
            # Token doesn't exist or is revoked, invalidate cache
            await invalidate_token_cache(token_hash)
            return False

        # Get fresh user data
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": ObjectId(token_doc["user_id"])})

        if not user or not user.get("is_active", True):
            # User doesn't exist or is inactive, invalidate cache
            await invalidate_token_cache(token_hash)
            return False

        # Update cache with fresh data
        cache_data = PermanentTokenCacheData(
            user_id=token_doc["user_id"],
            username=user["username"],
            email=user["email"],
            role=user.get("role", "user"),
            is_verified=user.get("is_verified", False),
            last_used_at=datetime.utcnow(),
        )

        success = await cache_token_data(token_hash, cache_data)
        if success:
            logger.debug("Refreshed cache for token: %s", token_hash[:16] + "...")

        return success

    except Exception as e:
        logger.error("Error refreshing token cache: %s", e)
        return False
