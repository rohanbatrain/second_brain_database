"""
Security manager for IP rate limiting and abuse prevention using Redis.
Provides per-route rate limiting, IP blacklisting, and abuse tracking.

Logging:
    - Uses the centralized logging manager.
    - Logs all rate limit, blacklist, and abuse events.
    - All exceptions are logged with full traceback.
"""

from typing import Optional

from fastapi import HTTPException, Request, status

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[SecurityManager]")

BLACKLISTED_MSG: str = "Your IP has been temporarily blacklisted due to excessive abuse."
RATE_LIMITED_MSG: str = "Too many requests. Please try again later."


class SecurityManager:
    """
    Manages rate limiting and blacklisting for API endpoints using Redis.
    """

    def __init__(self) -> None:
        self.rate_limit_requests: int = settings.RATE_LIMIT_REQUESTS
        self.rate_limit_period: int = settings.RATE_LIMIT_PERIOD_SECONDS
        self.blacklist_threshold: int = settings.BLACKLIST_THRESHOLD
        self.blacklist_duration: int = settings.BLACKLIST_DURATION
        self.logger = logger
        self.env_prefix: str = getattr(settings, "ENV_PREFIX", "dev")
        self.logger.debug(
            "Initialized with rate_limit_requests=%d, rate_limit_period=%d, blacklist_threshold=%d, blacklist_duration=%d, env_prefix=%s",
            self.rate_limit_requests,
            self.rate_limit_period,
            self.blacklist_threshold,
            self.blacklist_duration,
            self.env_prefix,
        )

    async def get_redis(self):
        """
        Proxy to RedisManager's get_redis for backward compatibility.
        Returns:
            Redis connection instance.
        """
        return await redis_manager.get_redis()

    def get_client_ip(self, request: Request) -> str:
        """
        Extract the client IP address from the request headers or connection info.
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

    def get_client_user_agent(self, request: Request) -> str:
        """
        Extract the User-Agent header from the request.
        Args:
            request (Request): The FastAPI request object.
        Returns:
            str: The User-Agent string, or empty string if not present.
        """
        return request.headers.get("user-agent", "")

    def is_trusted_ip(self, ip: str) -> bool:
        """
        Return True if the IP is localhost or a trusted range.
        Args:
            ip (str): The IP address to check.
        Returns:
            bool: True if trusted, False otherwise.
        """
        if ip in ("127.0.0.1", "::1", "0.0.0.0"):
            return True
        return False

    async def check_ip_lockdown(self, request: Request, user: dict) -> None:
        """
        Check IP lockdown for any endpoint (not just login).
        Raises HTTPException if IP lockdown is enabled and request IP is not trusted.
        Args:
            request (Request): The FastAPI request object.
            user (dict): The user document from database.
        Raises:
            HTTPException: If IP lockdown blocks the request.
        """
        if not user.get("trusted_ip_lockdown", False):
            return

        request_ip = self.get_client_ip(request)
        request_user_agent = self.get_client_user_agent(request)
        endpoint = f"{request.method} {request.url.path}"
        
        if not request_ip:
            self.logger.warning(
                "IP lockdown: could not determine request IP for user %s, endpoint: %s, user_agent: %s", 
                user.get("_id"), endpoint, request_user_agent
            )
            raise HTTPException(
                status_code=403, 
                detail="Access denied: IP address not in trusted list (IP Lockdown enabled)"
            )

        trusted_ips = user.get("trusted_ips", [])
        
        # Check if IP is in permanent trusted list
        if request_ip in trusted_ips:
            self.logger.debug(
                "IP lockdown: IP %s is in trusted list for user %s, endpoint: %s, user_agent: %s", 
                request_ip, user.get("_id"), endpoint, request_user_agent
            )
            return
        
        # Check for temporary IP bypasses (allow once functionality)
        from datetime import datetime
        temporary_bypasses = user.get("temporary_ip_bypasses", [])
        current_time = datetime.utcnow().isoformat()
        
        for bypass in temporary_bypasses:
            if (bypass.get("ip_address") == request_ip and 
                bypass.get("expires_at", "") > current_time):
                self.logger.info(
                    "IP lockdown: IP %s allowed via temporary bypass for user %s, endpoint: %s, expires: %s", 
                    request_ip, user.get("_id"), endpoint, bypass.get("expires_at")
                )
                return
        
        # IP is not trusted and has no valid bypass
        request_headers = dict(request.headers)
        self.logger.warning(
            "IP lockdown violation: request from disallowed IP %s for user %s (trusted: %s), "
            "endpoint: %s, user_agent: %s, headers: %s",
            request_ip,
            user.get("_id"),
            trusted_ips,
            endpoint,
            request_user_agent,
            request_headers,
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied: IP address not in trusted list (IP Lockdown enabled)"
        )

    async def check_user_agent_lockdown(self, request: Request, user: dict) -> None:
        """
        Check User Agent lockdown for any endpoint.
        Raises HTTPException if User Agent lockdown is enabled and request User Agent is not trusted.
        Args:
            request (Request): The FastAPI request object.
            user (dict): The user document from database.
        Raises:
            HTTPException: If User Agent lockdown blocks the request.
        """
        if not user.get("trusted_user_agent_lockdown", False):
            return

        request_user_agent = self.get_client_user_agent(request)
        request_ip = self.get_client_ip(request)
        endpoint = f"{request.method} {request.url.path}"
        
        if not request_user_agent:
            self.logger.warning(
                "User Agent lockdown: could not determine request User Agent for user %s, endpoint: %s, ip: %s", 
                user.get("_id"), endpoint, request_ip
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: User Agent not in trusted list (User Agent Lockdown enabled)"
            )

        trusted_user_agents = user.get("trusted_user_agents", [])
        
        # Check if User Agent is in permanent trusted list
        if request_user_agent in trusted_user_agents:
            self.logger.debug(
                "User Agent lockdown: User Agent %s is in trusted list for user %s, endpoint: %s, ip: %s", 
                request_user_agent, user.get("_id"), endpoint, request_ip
            )
            return
        
        # Check for temporary User Agent bypasses (allow once functionality)
        from datetime import datetime
        temporary_bypasses = user.get("temporary_user_agent_bypasses", [])
        current_time = datetime.utcnow().isoformat()
        
        for bypass in temporary_bypasses:
            if (bypass.get("user_agent") == request_user_agent and 
                bypass.get("expires_at", "") > current_time):
                self.logger.info(
                    "User Agent lockdown: User Agent %s allowed via temporary bypass for user %s, endpoint: %s, expires: %s", 
                    request_user_agent, user.get("_id"), endpoint, bypass.get("expires_at")
                )
                return
        
        # User Agent is not trusted and has no valid bypass
        request_headers = dict(request.headers)
        self.logger.warning(
            "User Agent lockdown violation: request from disallowed User Agent %s for user %s (trusted: %s), "
            "endpoint: %s, ip: %s, headers: %s",
            request_user_agent,
            user.get("_id"),
            trusted_user_agents,
            endpoint,
            request_ip,
            request_headers,
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied: User Agent not in trusted list (User Agent Lockdown enabled)"
        )

    async def is_blacklisted(self, ip: str) -> bool:
        """
        Check if the given IP address is currently blacklisted.
        Args:
            ip (str): The IP address to check.
        Returns:
            bool: True if blacklisted, False otherwise.
        """
        redis_conn = await self.get_redis()
        return await redis_conn.exists(f"{self.env_prefix}:blacklist:{ip}")

    async def blacklist_ip(self, ip: str, request: Optional[Request] = None) -> None:
        """
        Blacklist the given IP address for a configured duration.
        Args:
            ip (str): The IP address to blacklist.
            request (Optional[Request]): The FastAPI request object for context logging.
        Side-effects:
            Sets a key in Redis and logs the event.
        """
        redis_conn = await self.get_redis()
        await redis_conn.set(f"{self.env_prefix}:blacklist:{ip}", 1, ex=self.blacklist_duration)
        
        if request:
            user_agent = self.get_client_user_agent(request)
            endpoint = f"{request.method} {request.url.path}"
            request_headers = dict(request.headers)
            self.logger.warning(
                "IP %s has been blacklisted for %d seconds, endpoint: %s, user_agent: %s, headers: %s", 
                ip, self.blacklist_duration, endpoint, user_agent, request_headers
            )
        else:
            self.logger.warning("IP %s has been blacklisted for %d seconds.", ip, self.blacklist_duration)

    async def check_rate_limit(
        self,
        request: Request,
        action: str = "default",
        rate_limit_requests: Optional[int] = None,
        rate_limit_period: Optional[int] = None,
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
        Side-effects:
            Logs all rate limit, blacklist, and abuse events.
        """
        lua_script = """
        local rate_key = KEYS[1]
        local abuse_key = KEYS[2]
        local blacklist_key = KEYS[3]
        local requests_allowed = tonumber(ARGV[1])
        local period = tonumber(ARGV[2])
        local blacklist_threshold = tonumber(ARGV[3])
        local blacklist_duration = tonumber(ARGV[4])
        local count = redis.call('INCR', rate_key)
        if count == 1 then
            redis.call('EXPIRE', rate_key, period)
        end
        if count > requests_allowed then
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
            self.logger.debug("Trusted IP %s bypassed rate limiting.", ip)
            return
        if await self.is_blacklisted(ip):
            user_agent = self.get_client_user_agent(request)
            endpoint = f"{request.method} {request.url.path}"
            self.logger.warning(
                "Blocked request from blacklisted IP: %s, endpoint: %s, user_agent: %s", 
                ip, endpoint, user_agent
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=BLACKLISTED_MSG)
        key = f"{self.env_prefix}:ratelimit:{action}:{ip}"
        abuse_key = f"{self.env_prefix}:abuse:{ip}"
        blacklist_key = f"{self.env_prefix}:blacklist:{ip}"
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
                blacklist_duration,
            )
            count, abuse_count, status_flag = result
        except RuntimeError as lua_exc:
            self.logger.error(
                "Lua script failed for rate limiting: %s. Falling back to Python logic.", lua_exc, exc_info=True
            )
            count = await redis_conn.incr(key)
            if count == 1:
                await redis_conn.expire(key, period)
            if count > requests_allowed:
                abuse_count = await redis_conn.incr(abuse_key)
                if abuse_count == 1:
                    await redis_conn.expire(abuse_key, blacklist_duration)
                if abuse_count >= blacklist_threshold:
                    await redis_conn.set(blacklist_key, 1, ex=blacklist_duration)
                    status_flag = "BLACKLISTED"
                else:
                    status_flag = "RATE_LIMITED"
            else:
                abuse_count = 0
                status_flag = "OK"
        if status_flag == "BLACKLISTED":
            user_agent = self.get_client_user_agent(request)
            endpoint = f"{request.method} {request.url.path}"
            request_headers = dict(request.headers)
            self.logger.error(
                "IP %s has been blacklisted after %d abuses, endpoint: %s, user_agent: %s, headers: %s", 
                ip, abuse_count, endpoint, user_agent, request_headers
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=BLACKLISTED_MSG)
        if status_flag == "RATE_LIMITED":
            user_agent = self.get_client_user_agent(request)
            endpoint = f"{request.method} {request.url.path}"
            request_headers = dict(request.headers)
            self.logger.warning(
                "Rate limit exceeded for IP %s (action: %s). Abuse count: %d, endpoint: %s, user_agent: %s, headers: %s", 
                ip, action, abuse_count, endpoint, user_agent, request_headers
            )
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMITED_MSG)


security_manager = SecurityManager()
