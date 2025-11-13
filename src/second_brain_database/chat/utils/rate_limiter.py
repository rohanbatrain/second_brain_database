"""
Chat Rate Limiter

Redis-based distributed rate limiting for chat operations using sliding window algorithm.
Prevents abuse and ensures fair resource usage across all server instances.
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass

from second_brain_database.managers.redis_manager import RedisManager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.config import settings

logger = get_logger(prefix="[Chat-RateLimit]")


@dataclass
class RateLimitQuota:
    """Rate limit quota information."""

    limit: int
    used: int
    remaining: int
    reset_in_seconds: int


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, limit_type: str, retry_after: int, current: int, max_allowed: int):
        self.limit_type = limit_type
        self.retry_after = retry_after
        self.current = current
        self.max_allowed = max_allowed
        super().__init__(
            f"Rate limit exceeded for {limit_type}: {current}/{max_allowed}. " f"Retry after {retry_after} seconds."
        )


class ChatRateLimiter:
    """
    Rate limiter for chat operations using Redis sorted sets and sliding window algorithm.

    Each rate limit is tracked in a Redis sorted set where:
    - Member: Unique request ID (timestamp + random)
    - Score: Timestamp in milliseconds

    The sliding window algorithm:
    1. Remove entries older than the window
    2. Count remaining entries
    3. If count < limit, allow and add new entry
    4. If count >= limit, reject and calculate retry_after
    """

    def __init__(self, redis_manager: RedisManager):
        """
        Initialize ChatRateLimiter.

        Args:
            redis_manager: RedisManager instance for Redis operations
        """
        self.redis = redis_manager
        self.RATE_LIMIT_PREFIX = "chat:ratelimit:"

        # Rate limit configurations from settings
        self.MESSAGE_LIMIT = settings.CHAT_MESSAGE_RATE_LIMIT  # 20 per minute
        self.MESSAGE_WINDOW = 60  # 1 minute in seconds

        self.SESSION_LIMIT = settings.CHAT_SESSION_CREATE_LIMIT  # 5 per hour
        self.SESSION_WINDOW = 3600  # 1 hour in seconds

        self.enabled = settings.CHAT_ENABLE_RATE_LIMITING

        logger.info(
            "Chat rate limiter initialized",
            extra={
                "message_limit": self.MESSAGE_LIMIT,
                "message_window": self.MESSAGE_WINDOW,
                "session_limit": self.SESSION_LIMIT,
                "session_window": self.SESSION_WINDOW,
                "enabled": self.enabled,
            },
        )

    def _get_rate_limit_key(self, limit_type: str, user_id: str) -> str:
        """
        Get Redis key for rate limit tracking.

        Args:
            limit_type: Type of rate limit ("message" or "session")
            user_id: User identifier

        Returns:
            Redis key for this rate limit
        """
        return f"{self.RATE_LIMIT_PREFIX}{limit_type}:{user_id}"

    async def check_message_rate_limit(self, user_id: str, increment: bool = True) -> bool:
        """
        Check if user is within message rate limit (20 messages per minute).

        Args:
            user_id: User identifier
            increment: Whether to increment the counter

        Returns:
            True if within limit

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        if not self.enabled:
            return True

        return await self._check_rate_limit(
            limit_type="message",
            user_id=user_id,
            max_requests=self.MESSAGE_LIMIT,
            window_seconds=self.MESSAGE_WINDOW,
            increment=increment,
        )

    async def check_session_create_rate_limit(self, user_id: str, increment: bool = True) -> bool:
        """
        Check if user is within session creation rate limit (5 sessions per hour).

        Args:
            user_id: User identifier
            increment: Whether to increment the counter

        Returns:
            True if within limit

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        if not self.enabled:
            return True

        return await self._check_rate_limit(
            limit_type="session",
            user_id=user_id,
            max_requests=self.SESSION_LIMIT,
            window_seconds=self.SESSION_WINDOW,
            increment=increment,
        )

    async def _check_rate_limit(
        self, limit_type: str, user_id: str, max_requests: int, window_seconds: int, increment: bool = True
    ) -> bool:
        """
        Internal method to check rate limit using sliding window algorithm.

        Args:
            limit_type: Type of rate limit ("message" or "session")
            user_id: User identifier
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
            increment: Whether to increment the counter

        Returns:
            True if within limit

        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        key = self._get_rate_limit_key(limit_type, user_id)

        try:
            redis_client = await self.redis.get_redis()
            current_time_ms = int(time.time() * 1000)
            window_start_ms = current_time_ms - (window_seconds * 1000)

            # Start pipeline for atomic operations
            pipe = redis_client.pipeline()

            # Remove entries older than the window
            pipe.zremrangebyscore(key, 0, window_start_ms)

            # Count entries in current window
            pipe.zcard(key)

            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]

            if current_count >= max_requests:
                # Rate limit exceeded - calculate retry_after
                oldest_entries = await redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_entries:
                    oldest_timestamp_ms = int(oldest_entries[0][1])
                    retry_after_ms = (oldest_timestamp_ms + (window_seconds * 1000)) - current_time_ms
                    retry_after = max(1, int(retry_after_ms / 1000))
                else:
                    retry_after = window_seconds

                logger.warning(
                    f"Rate limit exceeded for {limit_type}",
                    extra={
                        "limit_type": limit_type,
                        "user_id": user_id,
                        "current": current_count,
                        "max": max_requests,
                        "retry_after": retry_after,
                    },
                )

                raise RateLimitExceeded(
                    limit_type=limit_type, retry_after=retry_after, current=current_count, max_allowed=max_requests
                )

            if increment:
                # Add current request to the set
                request_id = f"{current_time_ms}:{id(object())}"
                await redis_client.zadd(key, {request_id: current_time_ms})

                # Set expiration to window size + buffer
                await redis_client.expire(key, window_seconds + 60)

            return True

        except RateLimitExceeded:
            raise
        except Exception as e:
            logger.error(
                f"Rate limit check failed: {e}",
                extra={"limit_type": limit_type, "user_id": user_id, "error": str(e)},
            )
            # On Redis errors, fail open (allow request) to maintain availability
            return True

    async def get_remaining_quota(self, limit_type: str, user_id: str) -> RateLimitQuota:
        """
        Get remaining quota for a user.

        Args:
            limit_type: Type of rate limit ("message" or "session")
            user_id: User identifier

        Returns:
            RateLimitQuota with limit, used, remaining, and reset_in_seconds
        """
        if not self.enabled:
            # Return unlimited quota when rate limiting is disabled
            return RateLimitQuota(limit=999999, used=0, remaining=999999, reset_in_seconds=0)

        # Determine limit and window based on type
        if limit_type == "message":
            max_requests = self.MESSAGE_LIMIT
            window_seconds = self.MESSAGE_WINDOW
        elif limit_type == "session":
            max_requests = self.SESSION_LIMIT
            window_seconds = self.SESSION_WINDOW
        else:
            logger.warning(f"Unknown rate limit type: {limit_type}")
            return RateLimitQuota(limit=0, used=0, remaining=0, reset_in_seconds=0)

        key = self._get_rate_limit_key(limit_type, user_id)

        try:
            redis_client = await self.redis.get_redis()
            current_time_ms = int(time.time() * 1000)
            window_start_ms = current_time_ms - (window_seconds * 1000)

            # Remove stale entries and count
            await redis_client.zremrangebyscore(key, 0, window_start_ms)
            current_count = await redis_client.zcard(key)

            remaining = max(0, max_requests - current_count)

            # Calculate reset time
            if current_count > 0:
                oldest_entries = await redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_entries:
                    oldest_timestamp_ms = int(oldest_entries[0][1])
                    reset_timestamp_ms = oldest_timestamp_ms + (window_seconds * 1000)
                    reset_in_seconds = max(0, int((reset_timestamp_ms - current_time_ms) / 1000))
                else:
                    reset_in_seconds = window_seconds
            else:
                reset_in_seconds = 0

            return RateLimitQuota(
                limit=max_requests, used=current_count, remaining=remaining, reset_in_seconds=reset_in_seconds
            )

        except Exception as e:
            logger.error(
                f"Failed to get remaining quota: {e}", extra={"limit_type": limit_type, "user_id": user_id}
            )
            # On error, return conservative quota
            return RateLimitQuota(limit=max_requests, used=0, remaining=max_requests, reset_in_seconds=window_seconds)
