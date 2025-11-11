"""
Test blog security features including rate limiting, XSS protection, and audit logging.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import Request
from fastapi.testclient import TestClient

from second_brain_database.managers.blog_security import (
    BlogRateLimiter,
    BlogXSSProtection,
    BlogAuditLogger,
    BlogSecurityMiddleware,
)


class TestBlogRateLimiter:
    """Test rate limiting functionality."""

    @pytest.fixture
    def rate_limiter(self):
        return BlogRateLimiter()

    def test_rate_limit_check_allowed(self, rate_limiter):
        """Test rate limit check when under limit."""
        # Mock Redis operations
        rate_limiter.redis = AsyncMock()
        rate_limiter.redis.zremrangebyscore = AsyncMock()
        rate_limiter.redis.zcard = AsyncMock(return_value=5)
        rate_limiter.redis.zadd = AsyncMock()
        rate_limiter.redis.expire = AsyncMock()

        # Mock request
        request = MagicMock()

        import asyncio
        async def run_test():
            allowed, info = await rate_limiter.check_rate_limit("test_key", 10, 60, request)
            assert allowed is True
            assert info["current_count"] == 6

        asyncio.run(run_test())

    def test_rate_limit_check_blocked(self, rate_limiter):
        """Test rate limit check when over limit."""
        # Mock Redis operations
        rate_limiter.redis = AsyncMock()
        rate_limiter.redis.zremrangebyscore = AsyncMock()
        rate_limiter.redis.zcard = AsyncMock(return_value=15)

        # Mock request
        request = MagicMock()

        import asyncio
        async def run_test():
            allowed, info = await rate_limiter.check_rate_limit("test_key", 10, 60, request)
            assert allowed is False
            assert info["current_count"] == 15

        asyncio.run(run_test())


class TestBlogXSSProtection:
    """Test XSS protection functionality."""

    @pytest.fixture
    def xss_protection(self):
        return BlogXSSProtection()

    def test_sanitize_html_no_html(self, xss_protection):
        """Test sanitizing plain text."""
        result = xss_protection.sanitize_html("Hello World", allow_html=False)
        assert result == "Hello World"

    def test_sanitize_html_with_script(self, xss_protection):
        """Test sanitizing HTML with script tags."""
        malicious = '<script>alert("xss")</script>Hello'
        result = xss_protection.sanitize_html(malicious, allow_html=False)
        assert "<script>" not in result
        assert "Hello" in result

    def test_sanitize_post_content(self, xss_protection):
        """Test sanitizing post content with allowed HTML."""
        content = '<p>Hello <strong>world</strong></p><script>alert("xss")</script>'
        result = xss_protection.sanitize_post_content(content)
        assert "<p>" in result
        assert "<strong>" in result
        assert "<script>" not in result

    def test_validate_url_valid(self, xss_protection):
        """Test validating valid URLs."""
        assert xss_protection.validate_url("https://example.com/image.jpg")
        assert xss_protection.validate_url("http://example.com/image.png")

    def test_validate_url_invalid(self, xss_protection):
        """Test validating invalid URLs."""
        assert not xss_protection.validate_url("javascript:alert('xss')")
        assert not xss_protection.validate_url("data:text/html,<script>alert('xss')</script>")


class TestBlogAuditLogger:
    """Test audit logging functionality."""

    @pytest.fixture
    def audit_logger(self):
        return BlogAuditLogger()

    @pytest.mark.asyncio
    async def test_log_security_event(self, audit_logger):
        """Test logging security events."""
        audit_logger.logger = MagicMock()

        await audit_logger.log_security_event(
            event_type="login_attempt",
            severity="low",
            user_id="user123",
            website_id=None,
            ip_address="192.168.1.1",
            description="Login attempt",
            details={"method": "password"}
        )

        audit_logger.logger.warning.assert_called_once()
        call_args = audit_logger.logger.warning.call_args
        assert "login_attempt" in str(call_args)
        assert "user123" in str(call_args)

    @pytest.mark.asyncio
    async def test_log_content_event(self, audit_logger):
        """Test logging content events."""
        audit_logger.logger = MagicMock()

        await audit_logger.log_content_event(
            event_type="post_created",
            user_id="user123",
            website_id="website456",
            content_type="post",
            content_id="post789",
            action="create",
            ip_address="192.168.1.1",
            details={"title": "Test Post"}
        )

        audit_logger.logger.info.assert_called_once()
        call_args = audit_logger.logger.info.call_args
        assert "post_created" in str(call_args)
        assert "post789" in str(call_args)


class TestBlogSecurityMiddleware:
    """Test security middleware functionality."""

    @pytest.fixture
    def middleware(self):
        # Mock app for middleware
        app = MagicMock()
        return BlogSecurityMiddleware(app)

    def test_security_headers(self, middleware):
        """Test that security headers are added."""
        headers = middleware._get_security_headers()

        # Check that security headers were added
        assert "X-Content-Type-Options" in headers
        assert "X-Frame-Options" in headers
        assert "X-XSS-Protection" in headers
        assert "Content-Security-Policy" in headers

    @pytest.mark.asyncio
    async def test_middleware_call(self, middleware):
        """Test middleware call with rate limiting."""
        # Mock request and call_next
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.url.path = "/api/blog/websites/test/posts"
        request.method = "GET"
        request.headers = {}

        call_next = AsyncMock()
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        call_next.return_value = response

        # Mock rate limiter to allow request
        middleware.rate_limiter = MagicMock()
        middleware.rate_limiter.check_website_access_limit = AsyncMock(return_value=(True, {}))
        middleware.rate_limiter.check_api_access_limit = AsyncMock(return_value=(True, {}))

        # Call middleware
        result = await middleware.dispatch(request, call_next)

        # Verify call_next was called
        call_next.assert_called_once()

        # Verify security headers were added
        assert "X-Content-Type-Options" in result.headers


if __name__ == "__main__":
    pytest.main([__file__])