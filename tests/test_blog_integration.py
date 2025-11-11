"""
Comprehensive integration test for the blog system.

Tests the complete blog functionality including:
- Redis caching layer
- Celery background tasks
- Security features (rate limiting, XSS protection, audit logging)
- Multi-tenant blog operations
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
from httpx import AsyncClient

from second_brain_database.routes.blog import router as blog_router
from second_brain_database.managers.blog_cache_manager import BlogCacheManager
from second_brain_database.tasks.blog_tasks import (
    process_content_seo_metadata,
    aggregate_blog_analytics,
    warm_blog_cache,
    send_blog_notification
)
from second_brain_database.managers.blog_security import (
    BlogRateLimiter,
    BlogXSSProtection,
    BlogAuditLogger,
    BlogSecurityMiddleware
)


class TestBlogSystemIntegration:
    """Integration tests for the complete blog system."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app with blog routes."""
        app = FastAPI()
        app.include_router(blog_router, prefix="/api/blog")
        return app

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    async def async_client(self, app):
        """Create async test client."""
        async with AsyncClient(app=app, base_url="http://testserver") as client:
            yield client

    @pytest.fixture
    def cache_manager(self):
        """Create blog cache manager."""
        return BlogCacheManager()

    @pytest.fixture
    def rate_limiter(self):
        """Create rate limiter."""
        return BlogRateLimiter()

    @pytest.fixture
    def xss_protection(self):
        """Create XSS protection."""
        return BlogXSSProtection()

    @pytest.fixture
    def audit_logger(self):
        """Create audit logger."""
        return BlogAuditLogger()

    def test_blog_components_initialization(self, cache_manager, rate_limiter, xss_protection, audit_logger):
        """Test that all blog components can be initialized."""
        assert cache_manager is not None
        assert rate_limiter is not None
        assert xss_protection is not None
        assert audit_logger is not None

    def test_xss_protection_sanitization(self, xss_protection):
        """Test XSS protection sanitizes malicious content."""
        malicious_content = '<script>alert("xss")</script><p>Hello</p>'
        sanitized = xss_protection.sanitize_post_content(malicious_content)

        assert "<script>" not in sanitized
        assert "<p>Hello</p>" in sanitized

    def test_xss_protection_url_validation(self, xss_protection):
        """Test URL validation blocks malicious URLs."""
        assert xss_protection.validate_url("https://example.com/image.jpg")
        assert not xss_protection.validate_url("javascript:alert('xss')")
        assert not xss_protection.validate_url("data:text/html,<script>alert('xss')</script>")

    @pytest.mark.asyncio
    async def test_rate_limiting_logic(self, rate_limiter):
        """Test rate limiting logic."""
        # Mock Redis
        rate_limiter.redis = AsyncMock()
        rate_limiter.redis.zremrangebyscore = AsyncMock()
        rate_limiter.redis.zcard = AsyncMock(return_value=5)
        rate_limiter.redis.zadd = AsyncMock()
        rate_limiter.redis.expire = AsyncMock()

        # Mock request
        request = MagicMock()

        allowed, info = await rate_limiter.check_rate_limit("test_key", 10, 60, request)

        assert allowed is True
        assert info["current_count"] == 6
        assert info["limit"] == 10

    @pytest.mark.asyncio
    async def test_audit_logging(self, audit_logger):
        """Test audit logging functionality."""
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

    @pytest.mark.asyncio
    async def test_cache_operations(self, cache_manager):
        """Test cache operations."""
        # Mock Redis
        cache_manager.redis = AsyncMock()
        cache_manager.redis.setex = AsyncMock()
        cache_manager.redis.get = AsyncMock(return_value=None)
        cache_manager.redis.delete = AsyncMock(return_value=1)

        website_id = "test_website"
        post_id = "test_post"

        # Test cache key generation
        cache_key = cache_manager._get_post_cache_key(website_id, post_id)
        assert website_id in cache_key
        assert post_id in cache_key

        # Test cache invalidation
        await cache_manager.invalidate_post_cache(website_id, post_id)
        cache_manager.redis.delete.assert_called()

    @pytest.mark.asyncio
    async def test_celery_tasks(self):
        """Test Celery task definitions exist and are callable."""
        # Test that tasks can be imported and called (without actual execution)
        assert callable(process_content_seo_metadata)
        assert callable(aggregate_blog_analytics)
        assert callable(warm_blog_cache)
        assert callable(send_blog_notification)

        # Test task signatures
        import inspect
        sig = inspect.signature(process_content_seo_metadata)
        assert 'website_id' in sig.parameters
        assert 'post_id' in sig.parameters

    def test_security_middleware_initialization(self):
        """Test security middleware can be initialized."""
        app = MagicMock()
        middleware = BlogSecurityMiddleware(app)
        assert middleware.app == app
        assert middleware.rate_limiter is not None
        assert middleware.audit_logger is not None

    @pytest.mark.asyncio
    async def test_security_middleware_processing(self):
        """Test security middleware request processing."""
        app = MagicMock()
        middleware = BlogSecurityMiddleware(app)

        # Mock components
        middleware.rate_limiter = MagicMock()
        middleware.rate_limiter.check_website_access_limit = AsyncMock(return_value=(True, {}))
        middleware.audit_logger = MagicMock()

        # Mock request and response
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "192.168.1.1"
        request.url.path = "/api/blog/websites/test/posts"
        request.method = "GET"
        request.headers = {}

        response = MagicMock()
        response.status_code = 200
        response.headers = {}

        call_next = AsyncMock(return_value=response)

        # Process request
        result = await middleware.dispatch(request, call_next)

        # Verify middleware processed the request
        assert result == response
        call_next.assert_called_once()

    def test_blog_routes_registration(self, app):
        """Test that blog routes are properly registered."""
        routes = [route.path for route in app.routes]
        assert any("/api/blog/websites/{website_id}/posts" in route for route in routes)
        assert any("/api/blog/websites/{website_id}/categories" in route for route in routes)
        assert any("/api/blog/websites/{website_id}/posts/{post_id}/comments" in route for route in routes)

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_simulation(self):
        """Simulate end-to-end blog workflow."""
        # This test simulates the complete workflow without actual database calls

        # 1. User creates a post (with XSS protection)
        xss_protection = BlogXSSProtection()
        malicious_title = '<script>alert("xss")</script>Blog Post'
        sanitized_title = xss_protection.sanitize_html(malicious_title, allow_html=False)
        assert sanitized_title == "Blog Post"

        # 2. Content is processed by Celery task
        # (We can't actually run Celery tasks in unit tests, but we verify they exist)
        assert callable(process_content_seo_metadata)

        # 3. Post is cached
        cache_manager = BlogCacheManager()
        cache_manager.redis = AsyncMock()
        # Cache operations would happen here

        # 4. Analytics are aggregated
        assert callable(aggregate_blog_analytics)

        # 5. Security events are logged
        audit_logger = BlogAuditLogger()
        audit_logger.logger = MagicMock()

        await audit_logger.log_content_event(
            event_type="post_created",
            user_id="test_user",
            website_id="test_website",
            content_type="post",
            content_id="test_post",
            action="create",
            ip_address="127.0.0.1",
            details={"title": sanitized_title}
        )

        audit_logger.logger.info.assert_called_once()

    def test_multi_tenant_isolation(self):
        """Test that multi-tenant isolation is maintained."""
        cache_manager = BlogCacheManager()

        # Different websites should have different cache keys
        key1 = cache_manager._get_website_posts_cache_key("website1")
        key2 = cache_manager._get_website_posts_cache_key("website2")

        assert key1 != key2
        assert "website1" in key1
        assert "website2" in key2

    def test_error_handling_robustness(self, xss_protection):
        """Test that components handle errors gracefully."""
        # Test XSS protection with malformed input
        result = xss_protection.sanitize_html(None, allow_html=False)
        assert result == ""

        # Test URL validation with invalid input
        result = xss_protection.validate_url("")
        assert result is False

        result = xss_protection.validate_url(None)
        assert result is False


class TestBlogPerformance:
    """Performance tests for blog system."""

    @pytest.fixture
    def cache_manager(self):
        return BlogCacheManager()

    @pytest.mark.asyncio
    async def test_cache_performance(self, cache_manager):
        """Test cache operations are reasonably fast."""
        import time

        cache_manager.redis = AsyncMock()
        cache_manager.redis.setex = AsyncMock()
        cache_manager.redis.get = AsyncMock(return_value='{"test": "data"}')

        start_time = time.time()

        # Perform multiple cache operations
        for i in range(10):
            await cache_manager.cache_post("website1", f"post{i}", {"title": f"Post {i}"})
            await cache_manager.get_cached_post("website1", f"post{i}")

        end_time = time.time()
        duration = end_time - start_time

        # Should complete in reasonable time (less than 1 second for 20 operations)
        assert duration < 1.0

    def test_xss_protection_performance(self, xss_protection):
        """Test XSS protection performance."""
        import time

        test_content = "<p>This is a <strong>test</strong> post with <em>emphasis</em>.</p>" * 100

        start_time = time.time()

        # Process content multiple times
        for _ in range(100):
            xss_protection.sanitize_post_content(test_content)

        end_time = time.time()
        duration = end_time - start_time

        # Should complete in reasonable time (less than 2 seconds for 100 operations)
        assert duration < 2.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])