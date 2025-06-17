"""
Security manager for IP rate limiting using Redis.
"""
import asyncio
from fastapi import Request, HTTPException, status
from .config import settings
from .database import db_manager
import redis.asyncio as redis

class SecurityManager:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.rate_limit_requests = settings.RATE_LIMIT_REQUESTS
        self.rate_limit_period = settings.RATE_LIMIT_PERIOD_SECONDS
        self.redis = None
        self.BLACKLIST_THRESHOLD = settings.BLACKLIST_THRESHOLD
        self.BLACKLIST_DURATION = settings.BLACKLIST_DURATION

    async def get_redis(self):
        if self.redis is None:
            self.redis = await redis.from_url(self.redis_url, decode_responses=True)
        return self.redis

    def get_client_ip(self, request: Request) -> str:
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host
        return ip

    async def is_blacklisted(self, ip: str) -> bool:
        redis_conn = await self.get_redis()
        return await redis_conn.exists(f"blacklist:{ip}")

    async def blacklist_ip(self, ip: str):
        redis_conn = await self.get_redis()
        await redis_conn.set(f"blacklist:{ip}", 1, ex=self.BLACKLIST_DURATION)

    async def check_rate_limit(self, request: Request, action: str = "default", rate_limit_requests: int = None, rate_limit_period: int = None):
        """
        Check rate limit for a given action and IP. Allows per-route customization.
        """
        redis_conn = await self.get_redis()
        ip = self.get_client_ip(request)
        # Check if IP is blacklisted
        if await self.is_blacklisted(ip):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your IP has been temporarily blacklisted due to excessive abuse."
            )
        key = f"ratelimit:{action}:{ip}"
        requests_allowed = rate_limit_requests if rate_limit_requests is not None else self.rate_limit_requests
        period = rate_limit_period if rate_limit_period is not None else self.rate_limit_period
        count = await redis_conn.incr(key)
        if count == 1:
            await redis_conn.expire(key, period)
        if count > requests_allowed:
            # Increment abuse counter
            abuse_key = f"abuse:{ip}"
            abuse_count = await redis_conn.incr(abuse_key)
            if abuse_count == 1:
                await redis_conn.expire(abuse_key, self.BLACKLIST_DURATION)
            if abuse_count >= self.BLACKLIST_THRESHOLD:
                await self.blacklist_ip(ip)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Your IP has been temporarily blacklisted due to excessive abuse."
                )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later."
            )

security_manager = SecurityManager()
