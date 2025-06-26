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
import redis.asyncio as redis
from fastapi import HTTPException, status
from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

REDIS_UNAVAILABLE_MSG: str = (
    "Rate limiting service unavailable. Please try again later."
)

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
                self._redis = await redis.from_url(
                    self.redis_url, decode_responses=True
                )
                self.logger.info("[RedisManager] Successfully connected to Redis at %s", self.redis_url)
            except Exception as conn_exc:
                self.logger.error(
                    "[RedisManager] Failed to connect to Redis: %s", conn_exc, exc_info=True
                )
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=REDIS_UNAVAILABLE_MSG,
                ) from conn_exc
        return self._redis

redis_manager = RedisManager()
