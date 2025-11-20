"""
WebRTC Rate Limiter

Redis-based distributed rate limiting using sliding window algorithm.
Prevents abuse and ensures fair resource usage across all server instances.
"""

import time
from typing import Optional
from dataclasses import dataclass

from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[WebRTC-RateLimit]")


@dataclass
class RateLimitConfig:
    """Configuration for a rate limit."""
    max_requests: int
    window_seconds: int
    
    @property
    def window_ms(self) -> int:
        """Window size in milliseconds."""
        return self.window_seconds * 1000


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, limit_type: str, retry_after: int, current: int, max_allowed: int):
        self.limit_type = limit_type
        self.retry_after = retry_after
        self.current = current
        self.max_allowed = max_allowed
        super().__init__(
            f"Rate limit exceeded for {limit_type}: {current}/{max_allowed}. "
            f"Retry after {retry_after} seconds."
        )


class WebRtcRateLimiter:
    """
    Distributed rate limiter using Redis sorted sets and sliding window algorithm.
    
    Each rate limit is tracked in a Redis sorted set where:
    - Member: Unique request ID (timestamp + random)
    - Score: Timestamp in milliseconds
    
    The sliding window algorithm:
    1. Remove entries older than the window
    2. Count remaining entries
    3. If count < limit, allow and add new entry
    4. If count >= limit, reject and calculate retry_after
    """
    
    # Rate limit configurations
    LIMITS = {
        "websocket_message": RateLimitConfig(max_requests=100, window_seconds=60),
        "hand_raise": RateLimitConfig(max_requests=5, window_seconds=60),
        "reaction": RateLimitConfig(max_requests=20, window_seconds=60),
        "file_share": RateLimitConfig(max_requests=10, window_seconds=3600),
        "room_create": RateLimitConfig(max_requests=10, window_seconds=3600),
        "settings_update": RateLimitConfig(max_requests=30, window_seconds=60),
        "chat_message": RateLimitConfig(max_requests=60, window_seconds=60),
        "api_call": RateLimitConfig(max_requests=300, window_seconds=60),
    }
    
    def __init__(self):
        """Initialize rate limiter."""
        self.redis = redis_manager
        self.RATE_LIMIT_PREFIX = "webrtc:ratelimit:"
        
        logger.info("Rate limiter initialized with sliding window algorithm")
    
    def _get_rate_limit_key(self, limit_type: str, identifier: str) -> str:
        """
        Get Redis key for rate limit tracking.
        
        Args:
            limit_type: Type of rate limit (e.g., "websocket_message")
            identifier: Unique identifier (username, user_id, or IP)
            
        Returns:
            Redis key for this rate limit
        """
        return f"{self.RATE_LIMIT_PREFIX}{limit_type}:{identifier}"
    
    async def check_rate_limit(
        self,
        limit_type: str,
        identifier: str,
        increment: bool = True
    ) -> bool:
        """
        Check if request is within rate limit using sliding window.
        
        Args:
            limit_type: Type of rate limit to check
            identifier: Unique identifier (username, user_id, or IP)
            increment: Whether to increment the counter
            
        Returns:
            True if within limit, False if exceeded
            
        Raises:
            RateLimitExceeded: If rate limit is exceeded
        """
        if limit_type not in self.LIMITS:
            logger.warning(f"Unknown rate limit type: {limit_type}")
            return True  # Don't block unknown limit types
        
        config = self.LIMITS[limit_type]
        key = self._get_rate_limit_key(limit_type, identifier)
        
        try:
            redis_client = await self.redis.get_redis()
            current_time_ms = int(time.time() * 1000)
            window_start_ms = current_time_ms - config.window_ms
            
            # Start pipeline for atomic operations
            pipe = redis_client.pipeline()
            
            # Remove entries older than the window
            pipe.zremrangebyscore(key, 0, window_start_ms)
            
            # Count entries in current window
            pipe.zcard(key)
            
            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]
            
            if current_count >= config.max_requests:
                # Rate limit exceeded - calculate retry_after
                oldest_entries = await redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_entries:
                    oldest_timestamp_ms = int(oldest_entries[0][1])
                    retry_after_ms = (oldest_timestamp_ms + config.window_ms) - current_time_ms
                    retry_after = max(1, int(retry_after_ms / 1000))
                else:
                    retry_after = config.window_seconds
                
                logger.warning(
                    f"Rate limit exceeded",
                    extra={
                        "limit_type": limit_type,
                        "identifier": identifier,
                        "current": current_count,
                        "max": config.max_requests,
                        "retry_after": retry_after
                    }
                )
                
                raise RateLimitExceeded(
                    limit_type=limit_type,
                    retry_after=retry_after,
                    current=current_count,
                    max_allowed=config.max_requests
                )
            
            if increment:
                # Add current request to the set
                request_id = f"{current_time_ms}:{id(object())}"
                await redis_client.zadd(key, {request_id: current_time_ms})
                
                # Set expiration to window size + buffer
                await redis_client.expire(key, config.window_seconds + 60)
            
            return True
            
        except RateLimitExceeded:
            raise
        except Exception as e:
            logger.error(
                f"Rate limit check failed: {e}",
                extra={"limit_type": limit_type, "identifier": identifier, "error": str(e)}
            )
            # On Redis errors, fail open (allow request) to maintain availability
            return True
    
    async def get_rate_limit_status(
        self,
        limit_type: str,
        identifier: str
    ) -> dict:
        """
        Get current rate limit status for an identifier.
        
        Args:
            limit_type: Type of rate limit
            identifier: Unique identifier
            
        Returns:
            Dictionary with rate limit status
        """
        if limit_type not in self.LIMITS:
            return {
                "limit_type": limit_type,
                "error": "Unknown limit type"
            }
        
        config = self.LIMITS[limit_type]
        key = self._get_rate_limit_key(limit_type, identifier)
        
        try:
            redis_client = await self.redis.get_redis()
            current_time_ms = int(time.time() * 1000)
            window_start_ms = current_time_ms - config.window_ms
            
            # Remove stale entries and count
            await redis_client.zremrangebyscore(key, 0, window_start_ms)
            current_count = await redis_client.zcard(key)
            
            remaining = max(0, config.max_requests - current_count)
            
            # Calculate reset time
            if current_count > 0:
                oldest_entries = await redis_client.zrange(key, 0, 0, withscores=True)
                if oldest_entries:
                    oldest_timestamp_ms = int(oldest_entries[0][1])
                    reset_timestamp = (oldest_timestamp_ms + config.window_ms) / 1000
                else:
                    reset_timestamp = (current_time_ms + config.window_ms) / 1000
            else:
                reset_timestamp = (current_time_ms + config.window_ms) / 1000
            
            return {
                "limit_type": limit_type,
                "limit": config.max_requests,
                "remaining": remaining,
                "used": current_count,
                "reset_at": int(reset_timestamp),
                "window_seconds": config.window_seconds
            }
            
        except Exception as e:
            logger.error(
                f"Failed to get rate limit status: {e}",
                extra={"limit_type": limit_type, "identifier": identifier}
            )
            return {
                "limit_type": limit_type,
                "error": str(e)
            }
    
    async def reset_rate_limit(
        self,
        limit_type: str,
        identifier: str
    ) -> bool:
        """
        Reset rate limit for an identifier (admin function).
        
        Args:
            limit_type: Type of rate limit
            identifier: Unique identifier
            
        Returns:
            True if reset successful
        """
        key = self._get_rate_limit_key(limit_type, identifier)
        
        try:
            redis_client = await self.redis.get_redis()
            await redis_client.delete(key)
            
            logger.info(
                f"Rate limit reset",
                extra={"limit_type": limit_type, "identifier": identifier}
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to reset rate limit: {e}",
                extra={"limit_type": limit_type, "identifier": identifier}
            )
            return False


# Global rate limiter instance
rate_limiter = WebRtcRateLimiter()
