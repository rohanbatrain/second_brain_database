"""Integration tests for rate limiting functionality.

Tests rate limiting enforcement including:
- Message rate limit enforcement (20/min)
- Session creation rate limit enforcement (5/hour)
- 429 response with reset time
"""

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from motor.motor_asyncio import AsyncIOMotorClient

from second_brain_database.chat.models.chat_models import ChatSessionType
from second_brain_database.chat.models.request_models import (
    ChatMessageCreate,
    ChatSessionCreate,
)
from second_brain_database.chat.services.chat_service import ChatService
from second_brain_database.chat.utils.rate_limiter import ChatRateLimiter


@pytest.fixture
async def test_db():
    """Create test database connection."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_chat_rate_limiting"]
    
    # Clean up collections before test
    await db.chat_sessions.delete_many({})
    await db.chat_messages.delete_many({})
    
    yield db
    
    # Clean up after test
    await db.chat_sessions.delete_many({})
    await db.chat_messages.delete_many({})
    client.close()


@pytest.fixture
def mock_redis_with_rate_limit():
    """Mock Redis client with rate limiting support."""
    redis_mock = AsyncMock()
    
    # Track rate limit counters
    counters = {}
    
    async def mock_incr(key):
        """Mock increment operation."""
        if key not in counters:
            counters[key] = 0
        counters[key] += 1
        return counters[key]
    
    async def mock_expire(key, ttl):
        """Mock expire operation."""
        return True
    
    async def mock_ttl(key):
        """Mock TTL operation."""
        return 60  # Return 60 seconds remaining
    
    async def mock_delete(key):
        """Mock delete operation."""
        if key in counters:
            del counters[key]
        return True
    
    async def mock_get(key):
        """Mock get operation."""
        return None
    
    async def mock_setex(key, ttl, value):
        """Mock setex operation."""
        return True
    
    redis_mock.incr = mock_incr
    redis_mock.expire = mock_expire
    redis_mock.ttl = mock_ttl
    redis_mock.delete = mock_delete
    redis_mock.get = mock_get
    redis_mock.setex = mock_setex
    redis_mock._counters = counters  # Expose for testing
    
    return redis_mock


@pytest.fixture
def mock_ollama_llm():
    """Mock Ollama LLM for testing."""
    llm_mock = Mock()
    
    async def mock_astream(*args, **kwargs):
        """Mock streaming tokens."""
        tokens = ["Test", " ", "response"]
        for token in tokens:
            yield {"content": token}
    
    llm_mock.astream = mock_astream
    return llm_mock


class TestRateLimitingIntegration:
    """Integration tests for rate limiting."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_message_rate_limit_enforcement(
        self, test_db, mock_redis_with_rate_limit, mock_ollama_llm
    ):
        """Test that message rate limit (20/min) is enforced."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service and rate limiter
            chat_service = ChatService(db=test_db, redis_client=mock_redis_with_rate_limit)
            rate_limiter = ChatRateLimiter(redis_client=mock_redis_with_rate_limit)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="Rate Limit Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send messages up to limit
            message_count = 0
            for i in range(25):  # Try to send 25 messages (limit is 20)
                try:
                    # Check rate limit before sending
                    await rate_limiter.check_message_rate_limit(user_id)
                    
                    message = ChatMessageCreate(content=f"Message {i+1}")
                    async for _ in chat_service.stream_chat_response(
                        session_id=session.id,
                        user_id=user_id,
                        message=message
                    ):
                        pass
                    
                    message_count += 1
                except HTTPException as e:
                    # Should get 429 after hitting limit
                    assert e.status_code == 429
                    assert "rate limit" in str(e.detail).lower()
                    break
            
            # Should have sent some messages but not all 25
            assert message_count < 25
            assert message_count <= 20  # Should not exceed limit

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_creation_rate_limit_enforcement(
        self, test_db, mock_redis_with_rate_limit
    ):
        """Test that session creation rate limit (5/hour) is enforced."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=Mock())
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service and rate limiter
            chat_service = ChatService(db=test_db, redis_client=mock_redis_with_rate_limit)
            rate_limiter = ChatRateLimiter(redis_client=mock_redis_with_rate_limit)
            
            # Try to create sessions up to limit
            session_count = 0
            for i in range(10):  # Try to create 10 sessions (limit is 5)
                try:
                    # Check rate limit before creating
                    await rate_limiter.check_session_create_rate_limit(user_id)
                    
                    session_data = ChatSessionCreate(
                        session_type=ChatSessionType.GENERAL,
                        title=f"Session {i+1}"
                    )
                    session = await chat_service.create_session(user_id=user_id, session_data=session_data)
                    session_count += 1
                except HTTPException as e:
                    # Should get 429 after hitting limit
                    assert e.status_code == 429
                    assert "rate limit" in str(e.detail).lower()
                    break
            
            # Should have created some sessions but not all 10
            assert session_count < 10
            assert session_count <= 5  # Should not exceed limit

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_rate_limit_429_response_with_reset_time(
        self, test_db, mock_redis_with_rate_limit, mock_ollama_llm
    ):
        """Test that 429 response includes reset time."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create rate limiter
            rate_limiter = ChatRateLimiter(redis_client=mock_redis_with_rate_limit)
            
            # Exhaust rate limit
            for i in range(25):
                try:
                    await rate_limiter.check_message_rate_limit(user_id)
                except HTTPException as e:
                    # Verify 429 response structure
                    assert e.status_code == 429
                    
                    # Check that detail contains rate limit info
                    detail = str(e.detail)
                    assert "rate limit" in detail.lower() or "too many" in detail.lower()
                    
                    # Get remaining quota to verify reset time info
                    quota = await rate_limiter.get_remaining_quota(user_id, "message")
                    assert "reset_in_seconds" in quota
                    assert quota["reset_in_seconds"] > 0
                    break

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_rate_limit_per_user_isolation(
        self, test_db, mock_redis_with_rate_limit, mock_ollama_llm
    ):
        """Test that rate limits are isolated per user."""
        user1_id = str(uuid.uuid4())
        user2_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service and rate limiter
            chat_service = ChatService(db=test_db, redis_client=mock_redis_with_rate_limit)
            rate_limiter = ChatRateLimiter(redis_client=mock_redis_with_rate_limit)
            
            # Create sessions for both users
            session1_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="User 1 Session"
            )
            session1 = await chat_service.create_session(user_id=user1_id, session_data=session1_data)
            
            session2_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="User 2 Session"
            )
            session2 = await chat_service.create_session(user_id=user2_id, session_data=session2_data)
            
            # Exhaust rate limit for user 1
            user1_messages = 0
            for i in range(25):
                try:
                    await rate_limiter.check_message_rate_limit(user1_id)
                    user1_messages += 1
                except HTTPException:
                    break
            
            # User 2 should still be able to send messages
            user2_can_send = False
            try:
                await rate_limiter.check_message_rate_limit(user2_id)
                user2_can_send = True
            except HTTPException:
                pass
            
            # User 2 should not be affected by user 1's rate limit
            assert user2_can_send, "User 2 should be able to send messages"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_rate_limit_quota_tracking(
        self, test_db, mock_redis_with_rate_limit
    ):
        """Test that remaining quota is tracked correctly."""
        user_id = str(uuid.uuid4())
        
        # Create rate limiter
        rate_limiter = ChatRateLimiter(redis_client=mock_redis_with_rate_limit)
        
        # Check initial quota
        initial_quota = await rate_limiter.get_remaining_quota(user_id, "message")
        assert initial_quota["limit"] == 20
        assert initial_quota["used"] == 0
        assert initial_quota["remaining"] == 20
        
        # Use some quota
        for i in range(5):
            try:
                await rate_limiter.check_message_rate_limit(user_id)
            except HTTPException:
                break
        
        # Check updated quota
        updated_quota = await rate_limiter.get_remaining_quota(user_id, "message")
        assert updated_quota["used"] == 5
        assert updated_quota["remaining"] == 15

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_rate_limit_reset_after_window(
        self, test_db, mock_redis_with_rate_limit
    ):
        """Test that rate limit resets after time window."""
        user_id = str(uuid.uuid4())
        
        # Create rate limiter
        rate_limiter = ChatRateLimiter(redis_client=mock_redis_with_rate_limit)
        
        # Use some quota
        for i in range(5):
            await rate_limiter.check_message_rate_limit(user_id)
        
        # Check quota used
        quota_before = await rate_limiter.get_remaining_quota(user_id, "message")
        assert quota_before["used"] == 5
        
        # Simulate time passing by clearing Redis counters
        # (In real scenario, Redis would expire the key)
        key = f"chat:rate_limit:message:{user_id}"
        await mock_redis_with_rate_limit.delete(key)
        
        # Check quota reset
        quota_after = await rate_limiter.get_remaining_quota(user_id, "message")
        assert quota_after["used"] == 0
        assert quota_after["remaining"] == 20

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_rate_limit_checks(
        self, test_db, mock_redis_with_rate_limit
    ):
        """Test rate limiting under concurrent requests."""
        user_id = str(uuid.uuid4())
        
        # Create rate limiter
        rate_limiter = ChatRateLimiter(redis_client=mock_redis_with_rate_limit)
        
        # Simulate concurrent requests
        async def check_rate_limit():
            try:
                await rate_limiter.check_message_rate_limit(user_id)
                return True
            except HTTPException:
                return False
        
        # Run 30 concurrent checks (limit is 20)
        results = await asyncio.gather(*[check_rate_limit() for _ in range(30)])
        
        # Count successful checks
        successful = sum(1 for r in results if r)
        
        # Should allow up to limit
        assert successful <= 20

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_rate_limit_different_operations(
        self, test_db, mock_redis_with_rate_limit
    ):
        """Test that different operations have separate rate limits."""
        user_id = str(uuid.uuid4())
        
        # Create rate limiter
        rate_limiter = ChatRateLimiter(redis_client=mock_redis_with_rate_limit)
        
        # Use message rate limit
        for i in range(10):
            await rate_limiter.check_message_rate_limit(user_id)
        
        # Check message quota
        message_quota = await rate_limiter.get_remaining_quota(user_id, "message")
        assert message_quota["used"] == 10
        
        # Session creation should have separate limit
        for i in range(3):
            await rate_limiter.check_session_create_rate_limit(user_id)
        
        # Check session quota
        session_quota = await rate_limiter.get_remaining_quota(user_id, "session")
        assert session_quota["used"] == 3
        
        # Message quota should be unchanged
        message_quota_after = await rate_limiter.get_remaining_quota(user_id, "message")
        assert message_quota_after["used"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
