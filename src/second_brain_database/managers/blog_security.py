"""
Blog Security Features: Rate Limiting, XSS Protection, and Audit Logging.

This module provides comprehensive security features for the blog system:
- Rate limiting for API endpoints
- XSS protection and input sanitization
- Audit logging for security events
- Content security policy headers
"""

import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[BlogSecurity]")


class BlogRateLimiter:
    """
    Rate limiter for blog API endpoints.

    Supports different rate limits for different operations:
    - Post creation: 10 per hour per user
    - Comment creation: 30 per hour per user/IP
    - API access: 1000 per hour per user
    """

    def __init__(self, redis_manager=None):
        self.redis = redis_manager or globals().get("redis_manager")
        self.logger = logger

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        request: Request
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is within rate limit.

        Args:
            key: Rate limit key (user_id, IP, etc.)
            limit: Maximum requests allowed
            window_seconds: Time window in seconds
            request: FastAPI request object

        Returns:
            Tuple of (allowed: bool, info: dict)
        """
        try:
            now = time.time()
            window_start = now - window_seconds

            # Use Redis sorted set to track requests
            redis_key = f"blog:ratelimit:{key}"

            # Remove old entries
            await self.redis.zremrangebyscore(redis_key, 0, window_start)

            # Count current requests in window
            current_count = await self.redis.zcard(redis_key)

            # Check if limit exceeded
            allowed = current_count < limit

            if allowed:
                # Add current request
                await self.redis.zadd(redis_key, {str(now): now})
                # Set expiration on the key
                await self.redis.expire(redis_key, window_seconds)

            # Calculate reset time
            reset_time = now + window_seconds

            info = {
                "allowed": allowed,
                "current_count": current_count + (1 if allowed else 0),
                "limit": limit,
                "reset_time": reset_time,
                "window_seconds": window_seconds
            }

            if not allowed:
                self.logger.warning("Rate limit exceeded for key: %s", key)

            return allowed, info

        except Exception as e:
            self.logger.error("Rate limit check failed: %s", e)
            # Allow request on error to avoid blocking legitimate traffic
            return True, {"allowed": True, "error": str(e)}

    async def check_post_creation_limit(self, user_id: str, request: Request) -> Tuple[bool, Dict[str, Any]]:
        """Check post creation rate limit (10 per hour per user)."""
        key = f"user:{user_id}:posts"
        return await self.check_rate_limit(key, 10, 3600, request)

    async def check_comment_creation_limit(self, identifier: str, request: Request) -> Tuple[bool, Dict[str, Any]]:
        """Check comment creation rate limit (30 per hour per identifier)."""
        key = f"comment:{identifier}"
        return await self.check_rate_limit(key, 30, 3600, request)

    async def check_api_access_limit(self, user_id: str, request: Request) -> Tuple[bool, Dict[str, Any]]:
        """Check general API access rate limit (1000 per hour per user)."""
        key = f"user:{user_id}:api"
        return await self.check_rate_limit(key, 1000, 3600, request)

    async def check_website_access_limit(self, ip_address: str, request: Request) -> Tuple[bool, Dict[str, Any]]:
        """Check website access rate limit (10000 per hour per IP)."""
        key = f"ip:{ip_address}:website"
        return await self.check_rate_limit(key, 10000, 3600, request)


class BlogXSSProtection:
    """
    XSS protection and input sanitization for blog content.

    Provides comprehensive protection against:
    - Script injection
    - HTML injection
    - Event handler injection
    - CSS injection
    """

    def __init__(self):
        self.logger = logger

        # XSS patterns to detect and block
        self.xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>',
            r'<form[^>]*>.*?</form>',
            r'<input[^>]*>.*?>',
            r'<meta[^>]*>.*?>',
            r'expression\s*\(',
            r'vbscript\s*:',
            r'data\s*:',
        ]

        # Allowed HTML tags for rich content
        self.allowed_tags = {
            'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img', 'hr', 'div', 'span'
        }

        # Allowed attributes
        self.allowed_attributes = {
            'href', 'src', 'alt', 'title', 'class', 'id', 'target', 'rel'
        }

    def sanitize_html(self, content: str, allow_html: bool = False) -> str:
        """
        Sanitize HTML content to prevent XSS attacks.

        Args:
            content: Raw content to sanitize
            allow_html: Whether to allow basic HTML tags

        Returns:
            Sanitized content
        """
        if not content:
            return content

        try:
            # First, check for obvious XSS patterns
            for pattern in self.xss_patterns:
                if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                    self.logger.warning("XSS pattern detected in content: %s", pattern)
                    # Remove malicious content
                    content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)

            if not allow_html:
                # Escape HTML characters
                content = self._escape_html(content)
            else:
                # Sanitize HTML tags and attributes
                content = self._sanitize_html_tags(content)

            return content

        except Exception as e:
            self.logger.error("HTML sanitization failed: %s", e)
            # Return escaped content as fallback
            return self._escape_html(content)

    def _escape_html(self, content: str) -> str:
        """Escape HTML special characters."""
        return (content
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;')
                .replace('/', '&#x2F;'))

    def _sanitize_html_tags(self, content: str) -> str:
        """Sanitize HTML tags and attributes."""
        try:
            # Simple HTML sanitization - remove dangerous tags and attributes
            # This is a basic implementation; consider using bleach library for production

            # Remove dangerous tags
            dangerous_tags = ['script', 'style', 'iframe', 'object', 'embed', 'form', 'input', 'meta']
            for tag in dangerous_tags:
                content = re.sub(rf'<{tag}[^>]*>.*?</{tag}>', '', content, flags=re.IGNORECASE | re.DOTALL)
                content = re.sub(rf'<{tag}[^>]*/>', '', content, flags=re.IGNORECASE)

            # Remove event handlers and dangerous attributes
            dangerous_attrs = [r'on\w+', 'javascript:', 'vbscript:', 'data:', 'style']
            for attr in dangerous_attrs:
                content = re.sub(rf'\s{attr}\s*=\s*["\'][^"\']*["\']', '', content, flags=re.IGNORECASE)

            return content

        except Exception as e:
            self.logger.error("HTML tag sanitization failed: %s", e)
            return self._escape_html(content)

    def validate_url(self, url: str) -> bool:
        """
        Validate URL for security.

        Args:
            url: URL to validate

        Returns:
            True if URL is safe
        """
        try:
            parsed = urlparse(url)

            # Only allow http and https
            if parsed.scheme not in ['http', 'https']:
                return False

            # Check for suspicious patterns
            suspicious_patterns = [
                r'javascript:',
                r'vbscript:',
                r'data:',
                r'file:',
                r'ftp:',
            ]

            for pattern in suspicious_patterns:
                if pattern in url.lower():
                    return False

            return True

        except Exception:
            return False

    def sanitize_comment_content(self, content: str) -> str:
        """Sanitize comment content with basic HTML support."""
        return self.sanitize_html(content, allow_html=True)

    def sanitize_post_content(self, content: str) -> str:
        """Sanitize post content with full HTML support."""
        return self.sanitize_html(content, allow_html=True)


class BlogAuditLogger:
    """
    Audit logging for blog security events.

    Logs security-relevant events for compliance and monitoring:
    - Authentication attempts
    - Content modifications
    - Permission changes
    - Suspicious activities
    """

    def __init__(self):
        self.logger = logger

    async def log_auth_event(
        self,
        event_type: str,
        user_id: Optional[str],
        website_id: Optional[str],
        ip_address: str,
        user_agent: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log authentication-related events."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "website_id": website_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success,
            "details": details or {}
        }

        self.logger.info("AUTH_EVENT: %s", event)

    async def log_content_event(
        self,
        event_type: str,
        user_id: str,
        website_id: str,
        content_type: str,
        content_id: str,
        action: str,
        ip_address: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log content-related events."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "website_id": website_id,
            "content_type": content_type,
            "content_id": content_id,
            "action": action,
            "ip_address": ip_address,
            "details": details or {}
        }

        self.logger.info("CONTENT_EVENT: %s", event)

    async def log_security_event(
        self,
        event_type: str,
        severity: str,
        user_id: Optional[str],
        website_id: Optional[str],
        ip_address: str,
        description: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log security events."""
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "severity": severity,
            "user_id": user_id,
            "website_id": website_id,
            "ip_address": ip_address,
            "description": description,
            "details": details or {}
        }

        if severity in ['high', 'critical']:
            self.logger.error("SECURITY_EVENT: %s", event)
        else:
            self.logger.warning("SECURITY_EVENT: %s", event)

    async def log_rate_limit_event(
        self,
        user_id: Optional[str],
        ip_address: str,
        endpoint: str,
        limit_type: str
    ):
        """Log rate limit violations."""
        await self.log_security_event(
            event_type="rate_limit_exceeded",
            severity="medium",
            user_id=user_id,
            website_id=None,
            ip_address=ip_address,
            description=f"Rate limit exceeded for {limit_type} on {endpoint}",
            details={"endpoint": endpoint, "limit_type": limit_type}
        )

    async def log_xss_attempt(
        self,
        user_id: Optional[str],
        ip_address: str,
        content_type: str,
        pattern: str
    ):
        """Log XSS attack attempts."""
        await self.log_security_event(
            event_type="xss_attempt",
            severity="high",
            user_id=user_id,
            website_id=None,
            ip_address=ip_address,
            description=f"XSS pattern detected in {content_type}",
            details={"content_type": content_type, "pattern": pattern}
        )


class BlogSecurityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for blog security features.

    Provides:
    - Rate limiting
    - Request logging
    - Security headers
    - Basic attack detection
    """

    def __init__(self, app, rate_limiter=None, audit_logger=None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or BlogRateLimiter()
        self.audit_logger = audit_logger or BlogAuditLogger()
        self.logger = logger

    async def dispatch(self, request: Request, call_next):
        """Process request through security middleware."""
        start_time = time.time()

        try:
            # Get client information
            client_ip = self._get_client_ip(request)
            user_agent = request.headers.get("user-agent", "")
            user_id = getattr(request.state, "user_id", None) if hasattr(request, "state") else None

            # Check rate limits
            if request.url.path.startswith("/blog/"):
                rate_limit_ok, rate_info = await self._check_blog_rate_limits(
                    request, client_ip, user_id
                )

                if not rate_limit_ok:
                    await self.audit_logger.log_rate_limit_event(
                        user_id, client_ip, request.url.path, "blog_api"
                    )

                    return JSONResponse(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        content={
                            "error": "rate_limit_exceeded",
                            "message": "Too many requests. Please try again later.",
                            "reset_time": rate_info.get("reset_time"),
                            "limit": rate_info.get("limit")
                        },
                        headers={
                            "Retry-After": str(int(rate_info.get("reset_time", 0) - time.time())),
                            "X-RateLimit-Limit": str(rate_info.get("limit", 0)),
                            "X-RateLimit-Remaining": "0",
                            "X-RateLimit-Reset": str(int(rate_info.get("reset_time", 0)))
                        }
                    )

            # Process request
            response = await call_next(request)

            # Add security headers
            response.headers.update(self._get_security_headers())

            # Log request (async, don't wait)
            processing_time = time.time() - start_time
            # Only log slow requests or errors
            if processing_time > 5.0 or response.status_code >= 400:
                self.logger.info(
                    "Request: %s %s - Status: %d - Time: %.2fs - IP: %s - User: %s",
                    request.method, request.url.path, response.status_code,
                    processing_time, client_ip, user_id
                )

            return response

        except Exception as e:
            self.logger.error("Security middleware error: %s", e, exc_info=True)
            # Return generic error response
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "internal_server_error", "message": "An error occurred"}
            )

    def _get_client_ip(self, request: Request) -> str:
        """Get real client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Take first IP if multiple
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct IP
        return request.client.host if request.client else "unknown"

    async def _check_blog_rate_limits(self, request: Request, client_ip: str, user_id: Optional[str]) -> Tuple[bool, Dict[str, Any]]:
        """Check blog-specific rate limits."""
        try:
            # Website access limit (very permissive)
            allowed, info = await self.rate_limiter.check_website_access_limit(client_ip, request)
            if not allowed:
                return False, info

            # API access limit for authenticated users
            if user_id:
                allowed, info = await self.rate_limiter.check_api_access_limit(user_id, request)
                if not allowed:
                    return False, info

                # Specific limits for content creation
                if request.method == "POST":
                    if "/posts" in request.url.path:
                        allowed, info = await self.rate_limiter.check_post_creation_limit(user_id, request)
                        if not allowed:
                            return False, info
                    elif "/comments" in request.url.path:
                        identifier = user_id  # Could also use IP
                        allowed, info = await self.rate_limiter.check_comment_creation_limit(identifier, request)
                        if not allowed:
                            return False, info

            return True, {}

        except Exception as e:
            self.logger.error("Rate limit check failed: %s", e)
            return True, {}  # Allow on error

    def _get_security_headers(self) -> Dict[str, str]:
        """Get security headers for responses."""
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:;",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        }


# Global instances
blog_rate_limiter = BlogRateLimiter()
blog_xss_protection = BlogXSSProtection()
blog_audit_logger = BlogAuditLogger()
blog_security_middleware = BlogSecurityMiddleware(None)