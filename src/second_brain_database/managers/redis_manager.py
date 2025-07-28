"""
Redis manager for handling Redis connections and related utilities.

This module provides the RedisManager class, which manages
asynchronous Redis connections and exposes methods for
retrieving and interacting with Redis in a robust, production-ready way.

Logging:
    - Uses the centralized logging manager.
    - Logs connection attempts, successes, and failures.
    - All exceptions are logged with full traceback.
"""

from typing import Optional

from fastapi import HTTPException, status
import redis.asyncio as redis

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

REDIS_UNAVAILABLE_MSG: str = "Rate limiting service unavailable. Please try again later."


class RedisManager:
    """
    Manages a single Redis connection for the application.

    Attributes:
        redis_url: The Redis connection URL.
        _redis: The cached Redis connection instance.
        logger: The logger instance for this manager.
    """

    def __init__(self) -> None:
        """Initialize the RedisManager with config and logger."""
        self.redis_url: str = settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None
        self.logger = logger
        self.logger.debug("[RedisManager] Initialized with URL: %s", self.redis_url)

    async def get_redis(self) -> redis.Redis:
        """
        Get or create the Redis connection.

        Returns:
            An active redis.Redis connection.

        Raises:
            HTTPException: If Redis is unavailable.

        Side-effects:
            Logs connection attempts and errors.
        """
        if self._redis is None:
            try:
                self.logger.info("[RedisManager] Attempting to connect to Redis at %s", self.redis_url)
                self._redis = await redis.from_url(self.redis_url, decode_responses=True)
                self.logger.info("[RedisManager] Successfully connected to Redis at %s", self.redis_url)
            except Exception as conn_exc:
                self.logger.error("[RedisManager] Failed to connect to Redis: %s", conn_exc, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=REDIS_UNAVAILABLE_MSG,
                ) from conn_exc
        return self._redis

    async def get(self, key: str) -> Optional[str]:
        """
        Get value from Redis by key.
        
        Args:
            key: Redis key
            
        Returns:
            Value if found, None otherwise
        """
        try:
            redis_conn = await self.get_redis()
            return await redis_conn.get(key)
        except Exception as e:
            self.logger.error("[RedisManager] Failed to get key %s: %s", key, e)
            return None

    async def set(self, key: str, value: str) -> bool:
        """
        Set value in Redis.
        
        Args:
            key: Redis key
            value: Value to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            redis_conn = await self.get_redis()
            result = await redis_conn.set(key, value)
            return result is True
        except Exception as e:
            self.logger.error("[RedisManager] Failed to set key %s: %s", key, e)
            return False

    async def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        """
        Set value in Redis with expiration.
        
        Args:
            key: Redis key
            ttl_seconds: Time to live in seconds
            value: Value to store
            
        Returns:
            True if successful, False otherwise
        """
        try:
            redis_conn = await self.get_redis()
            result = await redis_conn.setex(key, ttl_seconds, value)
            return result is True
        except Exception as e:
            self.logger.error("[RedisManager] Failed to setex key %s: %s", key, e)
            return False

    async def delete(self, key: str) -> int:
        """
        Delete key from Redis.
        
        Args:
            key: Redis key to delete
            
        Returns:
            Number of keys deleted
        """
        try:
            redis_conn = await self.get_redis()
            return await redis_conn.delete(key)
        except Exception as e:
            self.logger.error("[RedisManager] Failed to delete key %s: %s", key, e)
            return 0

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in Redis.
        
        Args:
            key: Redis key to check
            
        Returns:
            True if key exists, False otherwise
        """
        try:
            redis_conn = await self.get_redis()
            result = await redis_conn.exists(key)
            return result > 0
        except Exception as e:
            self.logger.error("[RedisManager] Failed to check existence of key %s: %s", key, e)
            return False

    async def keys(self, pattern: str) -> list:
        """
        Get keys matching pattern.
        
        Args:
            pattern: Redis key pattern
            
        Returns:
            List of matching keys
        """
        try:
            redis_conn = await self.get_redis()
            return await redis_conn.keys(pattern)
        except Exception as e:
            self.logger.error("[RedisManager] Failed to get keys with pattern %s: %s", pattern, e)
            return []


redis_manager = RedisManager()
