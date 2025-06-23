"""
Redis manager for handling Redis connections and related utilities.
"""
import logging
from typing import Optional
import redis.asyncio as redis
from fastapi import HTTPException, status
from second_brain_database.config import settings

class RedisManager:
    def __init__(self):
        self.redis_url: str = settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None
        self.logger = logging.getLogger(__name__)

    async def get_redis(self) -> redis.Redis:
        """Get or create the Redis connection. Raises HTTPException if Redis is unavailable."""
        if self._redis is None:
            try:
                self._redis = await redis.from_url(self.redis_url, decode_responses=True)
            except Exception as e:
                self.logger.error("Failed to connect to Redis: %s", e)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Rate limiting service unavailable. Please try again later."
                ) from e
        return self._redis

redis_manager = RedisManager()
