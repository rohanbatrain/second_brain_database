"""Unit tests for ChatRateLimiter."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from second_brain_database.chat.utils.rate_limiter import ChatRateLimiter, RateLimitExceeded


class TestChatRateLimiter:
    """Test ChatRateLimiter functionality."""

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_initialization(self, mock_settings):
        """Test ChatRateLimiter initialization."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        limiter = ChatRateLimiter(redis_manager)
        
        assert limiter.redis == redis_manager
        assert limiter.MESSAGE_LIMIT == 20
        assert limiter.MESSAGE_WINDOW == 60
        assert limiter.SESSION_LIMIT == 5
        assert limiter.SESSION_WINDOW == 3600

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_check_message_rate_limit_allowed(self, mock_settings):
        """Test message rate limit when under limit."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 5])  # 5 requests in window
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        result = await limiter.check_message_rate_limit("user_123")
        
        assert result is True

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_check_message_rate_limit_exceeded(self, mock_settings):
        """Test message rate limit when limit exceeded."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = MagicMock()
        
        # Create async mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock(return_value=mock_pipeline)
        mock_pipeline.zcard = MagicMock(return_value=mock_pipeline)
        mock_pipeline.execute = AsyncMock(return_value=[None, 21])  # 21 requests in window
        
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_redis.zrange = AsyncMock(return_value=[(b"req", 1000000)])
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        
        with pytest.raises(RateLimitExceeded):
            await limiter.check_message_rate_limit("user_123")

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_check_message_rate_limit_at_boundary(self, mock_settings):
        """Test message rate limit at exact boundary (20 messages)."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 19])  # 19 requests, next will be 20th
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        result = await limiter.check_message_rate_limit("user_123")
        
        # At limit should still be allowed
        assert result is True

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_check_session_create_rate_limit_allowed(self, mock_settings):
        """Test session creation rate limit when under limit."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        mock_pipeline.execute = AsyncMock(return_value=[None, 3])
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        result = await limiter.check_session_create_rate_limit("user_123")
        
        assert result is True

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_check_session_create_rate_limit_exceeded(self, mock_settings):
        """Test session creation rate limit when limit exceeded."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = MagicMock()
        
        # Create async mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore = MagicMock(return_value=mock_pipeline)
        mock_pipeline.zcard = MagicMock(return_value=mock_pipeline)
        mock_pipeline.execute = AsyncMock(return_value=[None, 6])
        
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)
        mock_redis.zrange = AsyncMock(return_value=[(b"req", 1000000)])
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        
        with pytest.raises(RateLimitExceeded):
            await limiter.check_session_create_rate_limit("user_123")

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_get_remaining_quota_messages(self, mock_settings):
        """Test getting remaining message quota."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=15)
        mock_redis.zrange = AsyncMock(return_value=[(b"req", 1000000)])
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        quota = await limiter.get_remaining_quota("message", "user_123")
        
        assert quota.limit == 20
        assert quota.used == 15
        assert quota.remaining == 5

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_get_remaining_quota_sessions(self, mock_settings):
        """Test getting remaining session creation quota."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=2)
        mock_redis.zrange = AsyncMock(return_value=[(b"req", 1000000)])
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        quota = await limiter.get_remaining_quota("session", "user_123")
        
        assert quota.limit == 5
        assert quota.used == 2
        assert quota.remaining == 3

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_get_remaining_quota_no_usage(self, mock_settings):
        """Test getting quota when user hasn't used any yet."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = AsyncMock()
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        quota = await limiter.get_remaining_quota("message", "user_123")
        
        assert quota.limit == 20
        assert quota.used == 0
        assert quota.remaining == 20

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_rate_limit_key_format_messages(self, mock_settings):
        """Test rate limit key format for messages."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        limiter = ChatRateLimiter(redis_manager)
        
        key = limiter._get_rate_limit_key("message", "user_123")
        assert "chat:ratelimit:message:user_123" in key

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_rate_limit_key_format_sessions(self, mock_settings):
        """Test rate limit key format for sessions."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        limiter = ChatRateLimiter(redis_manager)
        
        key = limiter._get_rate_limit_key("session", "user_123")
        assert "chat:ratelimit:session:user_123" in key

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_different_users_independent_limits(self, mock_settings):
        """Test that different users have independent rate limits."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        mock_redis = AsyncMock()
        mock_pipeline = AsyncMock()
        
        # User 1 at boundary
        mock_pipeline.execute = AsyncMock(return_value=[None, 19])
        mock_redis.pipeline.return_value = mock_pipeline
        mock_redis.zadd = AsyncMock()
        mock_redis.expire = AsyncMock()
        redis_manager.get_redis = AsyncMock(return_value=mock_redis)
        
        limiter = ChatRateLimiter(redis_manager)
        result1 = await limiter.check_message_rate_limit("user_1")
        
        # User 2 under limit
        mock_pipeline.execute = AsyncMock(return_value=[None, 5])
        result2 = await limiter.check_message_rate_limit("user_2")
        
        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_rate_limit_window_expiry(self, mock_settings):
        """Test that rate limit window expiry is set correctly."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        limiter = ChatRateLimiter(redis_manager)
        
        # Verify window settings
        assert limiter.MESSAGE_WINDOW == 60
        assert limiter.SESSION_WINDOW == 3600

    @pytest.mark.asyncio
    @patch("second_brain_database.chat.utils.rate_limiter.settings")
    async def test_redis_error_handling(self, mock_settings):
        """Test handling Redis errors gracefully."""
        mock_settings.CHAT_MESSAGE_RATE_LIMIT = 20
        mock_settings.CHAT_SESSION_CREATE_LIMIT = 5
        mock_settings.CHAT_ENABLE_RATE_LIMITING = True
        
        redis_manager = MagicMock()
        redis_manager.get_redis = AsyncMock(side_effect=Exception("Redis error"))
        
        limiter = ChatRateLimiter(redis_manager)
        
        # Should fail open (allow request) on Redis errors
        result = await limiter.check_message_rate_limit("user_123")
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
