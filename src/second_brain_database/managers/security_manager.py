"""
Security manager for IP rate limiting and abuse prevention using Redis.
Provides per-route rate limiting, IP blacklisting, and abuse tracking.
"""
import logging
from typing import Optional

from fastapi import Request, HTTPException, status
from second_brain_database.config import settings
from second_brain_database.managers.redis_manager import redis_manager

class SecurityManager:
    """Manages rate limiting and blacklisting for API endpoints using Redis."""
    def __init__(self) -> None:
        self.rate_limit_requests: int = settings.RATE_LIMIT_REQUESTS
        self.rate_limit_period: int = settings.RATE_LIMIT_PERIOD_SECONDS
        self.blacklist_threshold: int = settings.BLACKLIST_THRESHOLD
        self.blacklist_duration: int = settings.BLACKLIST_DURATION
        self.logger = logging.getLogger(__name__)
        self.env_prefix: str = getattr(settings, 'ENV_PREFIX', 'dev')

    async def get_redis(self):
        """Proxy to RedisManager's get_redis for backward compatibility."""
        return await redis_manager.get_redis()

    def get_client_ip(self, request: Request) -> str:
        """Extract the client IP address from the request headers or connection info.
        Args:
            request (Request): The FastAPI request object.
        Returns:
            str: The client IP address.
        """
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host
        return ip

    def is_trusted_ip(self, ip: str) -> bool:
        """Return True if the IP is localhost or a trusted range."""
        # Localhost IPv4 and IPv6
        if ip in ("127.0.0.1", "::1", "0.0.0.0"):
            return True
        # # Cloudflare Tunnel IPv4 range (100.96.0.0/12) or add more as needed
        # if ip.startswith("100.96.") or ip.startswith("100.97.") or ip.startswith("100.98.") or ip.startswith("100.99."):
        #     return True
        return False

    async def is_blacklisted(self, ip: str) -> bool:
        """Check if the given IP address is currently blacklisted.
        Args:
            ip (str): The IP address to check.
        Returns:
            bool: True if blacklisted, False otherwise.
        """
        redis_conn = await self.get_redis()
        return await redis_conn.exists(f"{self.env_prefix}:blacklist:{ip}")

    async def blacklist_ip(self, ip: str) -> None:
        """Blacklist the given IP address for a configured duration.
        Args:
            ip (str): The IP address to blacklist.
        """
        redis_conn = await self.get_redis()
        await redis_conn.set(f"{self.env_prefix}:blacklist:{ip}", 1, ex=self.blacklist_duration)
        self.logger.warning("IP %s has been blacklisted for %d seconds.", ip, self.blacklist_duration)

    async def check_rate_limit(
        self,
        request: Request,
        action: str = "default",
        rate_limit_requests: Optional[int] = None,
        rate_limit_period: Optional[int] = None
    ) -> None:
        """
        Check rate limit for a given action and IP. Allows per-route customization.
        Raises HTTPException if the rate limit or blacklist is exceeded.
        Args:
            request (Request): The FastAPI request object.
            action (str): The action/route name for rate limiting.
            rate_limit_requests (Optional[int]): Custom requests allowed.
            rate_limit_period (Optional[int]): Custom period in seconds.
        Raises:
            HTTPException: If blacklisted or rate limit exceeded.
        """
        # Use a Redis Lua script for atomic rate limiting and abuse logic
        lua_script = """
        local rate_key = KEYS[1]
        local abuse_key = KEYS[2]
        local blacklist_key = KEYS[3]
        local requests_allowed = tonumber(ARGV[1])
        local period = tonumber(ARGV[2])
        local blacklist_threshold = tonumber(ARGV[3])
        local blacklist_duration = tonumber(ARGV[4])
        -- Increment rate limit counter
        local count = redis.call('INCR', rate_key)
        if count == 1 then
            redis.call('EXPIRE', rate_key, period)
        end
        if count > requests_allowed then
            -- Increment abuse counter
            local abuse_count = redis.call('INCR', abuse_key)
            if abuse_count == 1 then
                redis.call('EXPIRE', abuse_key, blacklist_duration)
            end
            if abuse_count >= blacklist_threshold then
                redis.call('SET', blacklist_key, 1, 'EX', blacklist_duration)
                return {count, abuse_count, 'BLACKLISTED'}
            end
            return {count, abuse_count, 'RATE_LIMITED'}
        end
        return {count, 0, 'OK'}
        """
        redis_conn = await self.get_redis()
        ip = self.get_client_ip(request)
        if self.is_trusted_ip(ip):
            return  # Allow trusted IPs (localhost, Cloudflare Tunnel)
        if await self.is_blacklisted(ip):
            self.logger.warning("Blocked request from blacklisted IP: %s", ip)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your IP has been temporarily blacklisted due to excessive abuse."
            )
        key = f"{self.env_prefix}:ratelimit:{action}:{ip}"
        abuse_key = f"{self.env_prefix}:abuse:{ip}"
        blacklist_key = f"{self.env_prefix}:blacklist:{ip}"
        # Use config values from settings if not provided
        requests_allowed = rate_limit_requests if rate_limit_requests is not None else settings.RATE_LIMIT_REQUESTS
        period = rate_limit_period if rate_limit_period is not None else settings.RATE_LIMIT_PERIOD_SECONDS
        blacklist_threshold = settings.BLACKLIST_THRESHOLD
        blacklist_duration = settings.BLACKLIST_DURATION
        try:
            result = await redis_conn.eval(
                lua_script,
                3,
                key,
                abuse_key,
                blacklist_key,
                requests_allowed,
                period,
                blacklist_threshold,
                blacklist_duration
            )
            count, abuse_count, status_flag = result
        except Exception as lua_exc:  # Use generic Exception, as redis exceptions are handled in redis_manager
            self.logger.error("Lua script failed for rate limiting: %s. Falling back to Python logic.", lua_exc)
            # Failsafe: fallback to less efficient Python logic
            count = await redis_conn.incr(key)
            if count == 1:
                await redis_conn.expire(key, period)
            if count > requests_allowed:
                abuse_count = await redis_conn.incr(abuse_key)
                if abuse_count == 1:
                    await redis_conn.expire(abuse_key, blacklist_duration)
                if abuse_count >= blacklist_threshold:
                    await redis_conn.set(blacklist_key, 1, ex=blacklist_duration)
                    status_flag = 'BLACKLISTED'
                else:
                    status_flag = 'RATE_LIMITED'
            else:
                abuse_count = 0
                status_flag = 'OK'
        if status_flag == 'BLACKLISTED':
            self.logger.error("IP %s has been blacklisted after %d abuses.", ip, abuse_count)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your IP has been temporarily blacklisted due to excessive abuse."
            )
        if status_flag == 'RATE_LIMITED':
            self.logger.warning("Rate limit exceeded for IP %s (action: %s). Abuse count: %d", ip, action, abuse_count)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )

security_manager = SecurityManager()
