"""
Enhanced rate limiting for OAuth2 browser authentication endpoints.

This module provides comprehensive rate limiting with progressive delays,
IP-based tracking, and advanced threat mitigation for OAuth2 browser flows.
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[Enhanced Rate Limiting]")

# Rate limiting configuration
RATE_LIMIT_PREFIX = "oauth2:rate_limit:"
PROGRESSIVE_DELAY_PREFIX = "oauth2:progressive_delay:"

# Default rate limits
DEFAULT_RATE_LIMITS = {
    "authorization": {"requests": 60, "window": 300},
    "token": {"requests": 30, "window": 300},
    "consent": {"requests": 20, "window": 300},
    "login": {"requests": 10, "window": 300},
    "global": {"requests": 100, "window": 300}
}

# Progressive delay configuration
PROGRESSIVE_DELAY_BASE = 1.0
PROGRESSIVE_DELAY_MULTIPLIER = 2.0
MAX_PROGRESSIVE_DELAY = 300.0


class RateLimitType(Enum):
    """Types of rate limiting."""
    IP_BASED = "ip_based"
    CLIENT_BASED = "client_based"
    USER_BASED = "user_based"
    GLOBAL = "global"


class EnhancedRateLimiter:
    """Enhanced rate limiting system with progressive delays."""
    
    def __init__(self):
        """Initialize the enhanced rate limiter."""
        self.logger = logger
        self.stats = {
            "requests_processed": 0,
            "rate_limit_violations": 0,
            "progressive_delays_applied": 0
        }
        self.rate_limit_configs = DEFAULT_RATE_LIMITS.copy()
    
    async def check_rate_limit(
        self,
        request: Request,
        endpoint: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> bool:
        """Check rate limits with progressive delay enforcement."""
        client_ip = self._get_client_ip(request)
        
        try:
            self.stats["requests_processed"] += 1
            
            # Check IP-based rate limiting
            if await self._check_ip_rate_limit(client_ip, endpoint):
                return True
            
            # Rate limit exceeded - apply progressive delay
            violation_count = await self._get_violation_count(client_ip, endpoint)
            delay = self._calculate_progressive_delay(violation_count)
            
            self.stats["rate_limit_violations"] += 1
            if delay > 0:
                self.stats["progressive_delays_applied"] += 1
                await asyncio.sleep(delay)
            
            # Log violation
            self.logger.warning(
                "Rate limit exceeded for %s on %s (delay: %.2fs)",
                client_ip, endpoint, delay
            )
            
            # Raise HTTP exception
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {delay:.1f} seconds."
            )
            
        except HTTPException:
            raise
        except Exception as e:
            self.logger.error("Error in rate limit check: %s", e)
            return True  # Fail open
    
    async def _check_ip_rate_limit(self, client_ip: str, endpoint: str) -> bool:
        """Check IP-based rate limiting."""
        key = f"{RATE_LIMIT_PREFIX}ip:{client_ip}:{endpoint}"
        
        current_count = await redis_manager.get(key)
        current_count = int(current_count) if current_count else 0
        
        limit_config = self.rate_limit_configs.get(endpoint, self.rate_limit_configs["global"])
        threshold = limit_config["requests"]
        window = limit_config["window"]
        
        if current_count >= threshold:
            return False
        
        await redis_manager.incr(key)
        await redis_manager.expire(key, window)
        return True
    
    async def _get_violation_count(self, client_ip: str, endpoint: str) -> int:
        """Get violation count for progressive delay calculation."""
        key = f"{PROGRESSIVE_DELAY_PREFIX}{client_ip}:{endpoint}"
        count = await redis_manager.get(key)
        
        if count:
            new_count = await redis_manager.incr(key)
            await redis_manager.expire(key, 3600)
            return new_count
        else:
            await redis_manager.setex(key, 3600, "1")
            return 1
    
    def _calculate_progressive_delay(self, violation_count: int) -> float:
        """Calculate progressive delay based on violation history."""
        delay = PROGRESSIVE_DELAY_BASE * (PROGRESSIVE_DELAY_MULTIPLIER ** (violation_count - 1))
        return min(delay, MAX_PROGRESSIVE_DELAY)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
        
        return getattr(request.client, "host", "unknown")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        return self.stats


# Global enhanced rate limiter instance
enhanced_rate_limiter = EnhancedRateLimiter()