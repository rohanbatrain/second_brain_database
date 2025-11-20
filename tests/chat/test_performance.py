"""Performance tests for chat system.

Tests performance metrics including:
- Time-to-first-token (TTFT)
- Tokens-per-second throughput
- End-to-end response time
- Concurrent streaming sessions
"""

import asyncio
import time
import uuid
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from second_brain_database.chat.models.chat_models import ChatSessionType
from second_brain_database.chat.models.request_models import (
    ChatMessageCreate,
    ChatSessionCreate,
)
from second_brain_database.chat.services.chat_service import ChatService


@pytest.fixture
async def test_db():
    """Create test database connection."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_chat_performance"]
    
    # Clean up collections before test
    await db.chat_sessions.delete_many({})
    await db.chat_messages.delete_many({})
    await db.token_usage.delete_many({})
    
    yield db
    
    # Clean up after test
    await db.chat_sessions.delete_many({})
    await db.chat_messages.delete_many({})
    await db.token_usage.delete_many({})
    client.close()


@pytest.fixture
def mock_redis():
    """Mock Redis manager for testing."""
    from second_brain_database.managers.redis_manager import RedisManager
    
    redis_manager = AsyncMock(spec=RedisManager)
    redis_manager.get = AsyncMock(return_value=None)
    redis_manager.set = AsyncMock()
    redis_manager.setex = AsyncMock()
    redis_manager.delete = AsyncMock()
    redis_manager.exists = AsyncMock(return_value=False)
    return redis_manager


@pytest.fixture
def mock_streaming_llm():
    """Mock Ollama LLM with realistic streaming behavior."""
    llm_mock = Mock()
    
    async def mock_astream(*args, **kwargs):
        """Mock streaming tokens with realistic delays."""
        tokens = [
            "The", " ", "quick", " ", "brown", " ", "fox", " ",
            "jumps", " ", "over", " ", "the", " ", "lazy", " ", "dog", ".",
            " ", "This", " ", "is", " ", "a", " ", "test", " ", "response", " ",
            "with", " ", "multiple", " ", "tokens", " ", "to", " ", "measure", " ",
            "streaming", " ", "performance", "."
        ]
        for token in tokens:
            # Simulate realistic token generation delay (10-20ms per token)
            await asyncio.sleep(0.015)
            yield {"content": token}
    
    llm_mock.astream = mock_astream
    return llm_mock


class TestChatPerformance:
    """Performance tests for chat system."""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_time_to_first_token(self, test_db, mock_redis, mock_streaming_llm):
        """Measure time-to-first-token (TTFT) for streaming responses."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_streaming_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_manager=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="TTFT Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send message and measure TTFT
            message_data = ChatMessageCreate(content="Tell me a story")
            
            start_time = time.time()
            first_token_time = None
            token_count = 0
            
            async for token in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                if first_token_time is None:
                    first_token_time = time.time()
                token_count += 1
            
            # Calculate TTFT
            ttft = first_token_time - start_time if first_token_time else 0
            
            # Assertions
            assert ttft > 0, "TTFT should be measured"
            assert ttft < 5.0, f"TTFT too high: {ttft:.3f}s (should be < 5s)"
            assert token_count > 0, "Should receive tokens"
            
            print(f"\n✓ Time-to-first-token: {ttft:.3f}s")
            print(f"✓ Total tokens received: {token_count}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_tokens_per_second(self, test_db, mock_redis, mock_streaming_llm):
        """Measure tokens-per-second throughput."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_streaming_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_manager=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="TPS Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send message and measure throughput
            message_data = ChatMessageCreate(content="Generate a long response")
            
            start_time = time.time()
            token_count = 0
            
            async for token in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                token_count += 1
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Calculate tokens per second
            tokens_per_second = token_count / duration if duration > 0 else 0
            
            # Assertions
            assert tokens_per_second > 0, "Should have positive throughput"
            assert tokens_per_second > 10, f"Throughput too low: {tokens_per_second:.2f} tokens/s"
            
            print(f"\n✓ Tokens per second: {tokens_per_second:.2f}")
            print(f"✓ Total duration: {duration:.3f}s")
            print(f"✓ Total tokens: {token_count}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_end_to_end_response_time(self, test_db, mock_redis, mock_streaming_llm):
        """Measure end-to-end response time for complete chat interaction."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_streaming_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_manager=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="E2E Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Measure complete interaction
            message_data = ChatMessageCreate(content="What is the meaning of life?")
            
            start_time = time.time()
            
            # Consume entire stream
            token_count = 0
            async for token in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                token_count += 1
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Verify message saved
            messages = await test_db.chat_messages.find(
                {"session_id": session.id}
            ).to_list(None)
            
            # Assertions
            assert total_time > 0, "Should measure response time"
            assert total_time < 10.0, f"Response time too high: {total_time:.3f}s"
            assert len(messages) >= 2, "Should have user and assistant messages"
            assert token_count > 0, "Should receive tokens"
            
            print(f"\n✓ End-to-end response time: {total_time:.3f}s")
            print(f"✓ Messages saved: {len(messages)}")
            print(f"✓ Tokens streamed: {token_count}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_concurrent_streaming_sessions(self, test_db, mock_redis, mock_streaming_llm):
        """Test performance with concurrent streaming sessions."""
        num_concurrent = 5
        user_ids = [str(uuid.uuid4()) for _ in range(num_concurrent)]
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_streaming_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_manager=mock_redis)
            
            # Create sessions for each user
            sessions = []
            for user_id in user_ids:
                session_data = ChatSessionCreate(
                    session_type=ChatSessionType.GENERAL,
                    title=f"Concurrent Test {user_id[:8]}"
                )
                session = await chat_service.create_session(user_id=user_id, session_data=session_data)
                sessions.append((user_id, session))
            
            async def stream_message(user_id: str, session_id: str) -> dict:
                """Stream a message and collect metrics."""
                message_data = ChatMessageCreate(content=f"Test message from {user_id[:8]}")
                
                start_time = time.time()
                token_count = 0
                
                async for token in chat_service.stream_chat_response(
                    session_id=session_id,
                    user_id=user_id,
                    message=message_data
                ):
                    token_count += 1
                
                end_time = time.time()
                
                return {
                    "user_id": user_id,
                    "session_id": session_id,
                    "duration": end_time - start_time,
                    "token_count": token_count
                }
            
            # Execute concurrent streams
            start_time = time.time()
            
            tasks = [
                stream_message(user_id, session.id)
                for user_id, session in sessions
            ]
            results = await asyncio.gather(*tasks)
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Analyze results
            durations = [r["duration"] for r in results]
            token_counts = [r["token_count"] for r in results]
            
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            total_tokens = sum(token_counts)
            
            # Assertions
            assert len(results) == num_concurrent, "All sessions should complete"
            assert all(r["token_count"] > 0 for r in results), "All sessions should receive tokens"
            assert total_duration < 15.0, f"Concurrent execution too slow: {total_duration:.3f}s"
            
            # Verify all messages saved
            for user_id, session in sessions:
                messages = await test_db.chat_messages.find(
                    {"session_id": session.id}
                ).to_list(None)
                assert len(messages) >= 2, f"Session {session.id} should have messages"
            
            print(f"\n✓ Concurrent sessions: {num_concurrent}")
            print(f"✓ Total duration: {total_duration:.3f}s")
            print(f"✓ Average session duration: {avg_duration:.3f}s")
            print(f"✓ Min/Max duration: {min_duration:.3f}s / {max_duration:.3f}s")
            print(f"✓ Total tokens: {total_tokens}")
            print(f"✓ Throughput: {total_tokens/total_duration:.2f} tokens/s")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_conversation_history_performance(self, test_db, mock_redis, mock_streaming_llm):
        """Test performance with large conversation history."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_streaming_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_manager=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="History Performance Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Build up conversation history (25 messages = 12 exchanges + 1)
            for i in range(12):
                message = ChatMessageCreate(content=f"Message {i+1}")
                async for _ in chat_service.stream_chat_response(
                    session_id=session.id,
                    user_id=user_id,
                    message=message
                ):
                    pass
            
            # Measure performance with large history
            message_data = ChatMessageCreate(content="Final message with large history")
            
            start_time = time.time()
            token_count = 0
            
            async for token in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                token_count += 1
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Verify history loaded correctly
            history = await chat_service.get_conversation_history(session_id=session.id)
            
            # Assertions
            assert duration < 10.0, f"Response with history too slow: {duration:.3f}s"
            assert len(history) <= 20, "History should be limited to 20 messages"
            assert token_count > 0, "Should receive tokens"
            
            print(f"\n✓ Response time with history: {duration:.3f}s")
            print(f"✓ History size: {len(history)} messages")
            print(f"✓ Tokens streamed: {token_count}")

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_session_statistics_calculation_performance(self, test_db, mock_redis, mock_streaming_llm):
        """Test performance of session statistics calculation."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_streaming_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_manager=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="Statistics Performance Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Add multiple messages
            for i in range(10):
                message = ChatMessageCreate(content=f"Test message {i+1}")
                async for _ in chat_service.stream_chat_response(
                    session_id=session.id,
                    user_id=user_id,
                    message=message
                ):
                    pass
            
            # Measure statistics calculation
            start_time = time.time()
            
            session_with_stats = await chat_service.get_session(session_id=session.id)
            
            end_time = time.time()
            calc_time = end_time - start_time
            
            # Assertions
            assert calc_time < 2.0, f"Statistics calculation too slow: {calc_time:.3f}s"
            assert session_with_stats.message_count > 0, "Should have message count"
            assert session_with_stats.last_message_at is not None, "Should have last message time"
            
            print(f"\n✓ Statistics calculation time: {calc_time:.3f}s")
            print(f"✓ Message count: {session_with_stats.message_count}")
            print(f"✓ Total tokens: {session_with_stats.total_tokens}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "slow"])
