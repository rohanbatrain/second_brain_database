"""Integration tests for chat system.

Tests end-to-end chat flows including:
- Session creation and message streaming
- Message persistence in MongoDB
- Token usage tracking
- Conversation history management
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import AsyncGenerator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from second_brain_database.chat.models.chat_models import (
    ChatMessage,
    ChatSession,
    ChatSessionType,
    MessageRole,
    MessageStatus,
    TokenUsage,
)
from second_brain_database.chat.models.request_models import (
    ChatMessageCreate,
    ChatSessionCreate,
)
from second_brain_database.chat.services.chat_service import ChatService


@pytest.fixture
async def test_db():
    """Create test database connection."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_chat_integration"]
    
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
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    redis_mock.delete = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_ollama_llm():
    """Mock Ollama LLM for testing."""
    llm_mock = Mock()
    
    # Mock streaming response
    async def mock_astream(*args, **kwargs):
        """Mock streaming tokens."""
        tokens = ["Hello", " ", "world", "!", " ", "This", " ", "is", " ", "a", " ", "test", "."]
        for token in tokens:
            yield {"content": token}
    
    llm_mock.astream = mock_astream
    return llm_mock


@pytest.fixture
def mock_vector_service():
    """Mock vector knowledge base service."""
    service_mock = AsyncMock()
    service_mock.query_vector_kb = AsyncMock(return_value=[
        {
            "content": "Test document content",
            "metadata": {"source": "test.pdf", "page": 1},
            "score": 0.95
        }
    ])
    return service_mock


class TestChatIntegration:
    """Integration tests for chat system."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_session_and_send_message(self, test_db, mock_redis, mock_ollama_llm):
        """Test complete flow: create session → send message → receive streaming response."""
        # Setup
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="Test Session"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Verify session created
            assert session is not None
            assert session.user_id == user_id
            assert session.session_type == ChatSessionType.GENERAL
            assert session.title == "Test Session"
            
            # Verify session in database
            db_session = await test_db.chat_sessions.find_one({"id": session.id})
            assert db_session is not None
            assert db_session["user_id"] == user_id
            
            # Send message
            message_data = ChatMessageCreate(content="Hello, how are you?")
            
            # Collect streaming response
            response_tokens = []
            async for token in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                response_tokens.append(token)
            
            # Verify streaming response received
            assert len(response_tokens) > 0
            
            # Verify messages saved to MongoDB
            messages = await test_db.chat_messages.find(
                {"session_id": session.id}
            ).sort("created_at", 1).to_list(None)
            
            assert len(messages) >= 2  # User message + assistant message
            
            # Verify user message
            user_message = messages[0]
            assert user_message["role"] == MessageRole.USER
            assert user_message["content"] == "Hello, how are you?"
            assert user_message["user_id"] == user_id
            
            # Verify assistant message
            assistant_message = messages[1]
            assert assistant_message["role"] == MessageRole.ASSISTANT
            assert assistant_message["status"] == MessageStatus.COMPLETED
            assert len(assistant_message["content"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_token_usage_recorded(self, test_db, mock_redis, mock_ollama_llm):
        """Test that token usage is recorded for messages."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager with token counting
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(side_effect=lambda text: len(text.split()))
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="Token Test Session"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send message
            message_data = ChatMessageCreate(content="What is the weather today?")
            
            # Consume streaming response
            async for _ in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                pass
            
            # Verify token usage recorded
            token_records = await test_db.token_usage.find(
                {"session_id": session.id}
            ).to_list(None)
            
            # Should have at least one token usage record
            assert len(token_records) > 0
            
            # Verify token usage structure
            token_record = token_records[0]
            assert "message_id" in token_record
            assert "session_id" in token_record
            assert token_record["session_id"] == session.id
            assert "total_tokens" in token_record
            assert "prompt_tokens" in token_record
            assert "completion_tokens" in token_record
            assert "model" in token_record
            assert token_record["total_tokens"] > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_conversation_history_maintained(self, test_db, mock_redis, mock_ollama_llm):
        """Test that conversation history is maintained across messages."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="History Test Session"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send first message
            message1 = ChatMessageCreate(content="My name is Alice")
            async for _ in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message1
            ):
                pass
            
            # Send second message
            message2 = ChatMessageCreate(content="What is my name?")
            async for _ in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message2
            ):
                pass
            
            # Verify conversation history
            history = await chat_service.get_conversation_history(session_id=session.id)
            
            # Should have messages from both exchanges
            assert len(history) >= 4  # 2 user messages + 2 assistant messages
            
            # Verify history format
            for msg in history:
                assert "role" in msg
                assert "content" in msg
                assert msg["role"] in ["user", "assistant", "system"]
            
            # Verify first user message in history
            user_messages = [m for m in history if m["role"] == "user"]
            assert len(user_messages) >= 2
            assert any("Alice" in m["content"] for m in user_messages)
            assert any("What is my name" in m["content"] for m in user_messages)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_messages_pagination(self, test_db, mock_redis, mock_ollama_llm):
        """Test message retrieval with pagination."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="Pagination Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send multiple messages
            for i in range(5):
                message = ChatMessageCreate(content=f"Message {i+1}")
                async for _ in chat_service.stream_chat_response(
                    session_id=session.id,
                    user_id=user_id,
                    message=message
                ):
                    pass
            
            # Test pagination
            page1 = await chat_service.get_messages(session_id=session.id, skip=0, limit=5)
            assert len(page1) == 5
            
            page2 = await chat_service.get_messages(session_id=session.id, skip=5, limit=5)
            assert len(page2) >= 0  # May have more messages
            
            # Verify no overlap
            page1_ids = {msg.id for msg in page1}
            page2_ids = {msg.id for msg in page2}
            assert len(page1_ids.intersection(page2_ids)) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_session_statistics_updated(self, test_db, mock_redis, mock_ollama_llm):
        """Test that session statistics are updated after messages."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="Statistics Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Initial statistics
            initial_session = await chat_service.get_session(session_id=session.id)
            assert initial_session.message_count == 0
            
            # Send message
            message = ChatMessageCreate(content="Test message")
            async for _ in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message
            ):
                pass
            
            # Verify statistics updated
            updated_session = await chat_service.get_session(session_id=session.id)
            assert updated_session.message_count > initial_session.message_count
            assert updated_session.last_message_at is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delete_session_cascade(self, test_db, mock_redis, mock_ollama_llm):
        """Test that deleting a session removes all associated messages."""
        user_id = str(uuid.uuid4())
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager:
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.GENERAL,
                title="Delete Test"
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send message
            message = ChatMessageCreate(content="Test message")
            async for _ in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message
            ):
                pass
            
            # Verify messages exist
            messages_before = await test_db.chat_messages.count_documents({"session_id": session.id})
            assert messages_before > 0
            
            # Delete session
            await chat_service.delete_session(session_id=session.id)
            
            # Verify session deleted
            deleted_session = await chat_service.get_session(session_id=session.id)
            assert deleted_session is None
            
            # Verify messages deleted
            messages_after = await test_db.chat_messages.count_documents({"session_id": session.id})
            assert messages_after == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
