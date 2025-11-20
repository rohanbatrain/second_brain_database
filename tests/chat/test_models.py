"""Unit tests for chat data models."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from second_brain_database.chat.models.chat_models import (
    ChatSession,
    ChatMessage,
    TokenUsage,
    MessageVote,
)
from second_brain_database.chat.models.enums import (
    ChatSessionType,
    MessageRole,
    MessageStatus,
    VoteType,
)


class TestChatSessionType:
    """Test ChatSessionType enum."""

    def test_enum_values(self):
        """Test that enum has correct values."""
        assert ChatSessionType.GENERAL == "GENERAL"
        assert ChatSessionType.VECTOR == "VECTOR"
        assert ChatSessionType.SQL == "SQL"

    def test_enum_members(self):
        """Test that all expected members exist."""
        assert len(ChatSessionType) == 3
        assert "GENERAL" in ChatSessionType.__members__
        assert "VECTOR" in ChatSessionType.__members__
        assert "SQL" in ChatSessionType.__members__


class TestMessageRole:
    """Test MessageRole enum."""

    def test_enum_values(self):
        """Test that enum has correct values."""
        assert MessageRole.USER == "USER"
        assert MessageRole.ASSISTANT == "ASSISTANT"
        assert MessageRole.SYSTEM == "SYSTEM"

    def test_enum_members(self):
        """Test that all expected members exist."""
        assert len(MessageRole) == 3
        assert "USER" in MessageRole.__members__
        assert "ASSISTANT" in MessageRole.__members__
        assert "SYSTEM" in MessageRole.__members__


class TestMessageStatus:
    """Test MessageStatus enum."""

    def test_enum_values(self):
        """Test that enum has correct values."""
        assert MessageStatus.PENDING == "PENDING"
        assert MessageStatus.COMPLETED == "COMPLETED"
        assert MessageStatus.FAILED == "FAILED"

    def test_enum_members(self):
        """Test that all expected members exist."""
        assert len(MessageStatus) == 3
        assert "PENDING" in MessageStatus.__members__
        assert "COMPLETED" in MessageStatus.__members__
        assert "FAILED" in MessageStatus.__members__


class TestChatSession:
    """Test ChatSession model."""

    def test_valid_chat_session(self):
        """Test creating a valid chat session."""
        session = ChatSession(
            id="session_123",
            user_id="user_456",
            session_type=ChatSessionType.GENERAL,
            title="Test Session",
            message_count=5,
            total_tokens=1000,
            total_cost=0.0,
            knowledge_base_ids=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True,
        )
        
        assert session.id == "session_123"
        assert session.user_id == "user_456"
        assert session.session_type == ChatSessionType.GENERAL
        assert session.title == "Test Session"
        assert session.message_count == 5
        assert session.total_tokens == 1000
        assert session.is_active is True

    def test_chat_session_defaults(self):
        """Test default values for chat session."""
        session = ChatSession(
            id="session_123",
            user_id="user_456",
            session_type=ChatSessionType.GENERAL,
            title="Test Session",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        assert session.message_count == 0
        assert session.total_tokens == 0
        assert session.total_cost == 0.0
        assert session.knowledge_base_ids == []
        assert session.is_active is True
        assert session.last_message_at is None

    def test_chat_session_with_knowledge_bases(self):
        """Test chat session with knowledge base IDs."""
        session = ChatSession(
            id="session_123",
            user_id="user_456",
            session_type=ChatSessionType.VECTOR,
            title="Vector Session",
            knowledge_base_ids=["kb_1", "kb_2"],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        assert len(session.knowledge_base_ids) == 2
        assert "kb_1" in session.knowledge_base_ids
        assert "kb_2" in session.knowledge_base_ids


class TestChatMessage:
    """Test ChatMessage model."""

    def test_valid_chat_message(self):
        """Test creating a valid chat message."""
        message = ChatMessage(
            id="msg_123",
            session_id="session_456",
            user_id="user_789",
            role=MessageRole.USER,
            content="Hello, world!",
            status=MessageStatus.COMPLETED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        assert message.id == "msg_123"
        assert message.session_id == "session_456"
        assert message.user_id == "user_789"
        assert message.role == MessageRole.USER
        assert message.content == "Hello, world!"
        assert message.status == MessageStatus.COMPLETED

    def test_chat_message_defaults(self):
        """Test default values for chat message."""
        message = ChatMessage(
            id="msg_123",
            session_id="session_456",
            user_id="user_789",
            role=MessageRole.USER,
            content="Hello",
            status=MessageStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        assert message.status == MessageStatus.PENDING
        assert message.tool_invocations == []
        assert message.sql_queries == []
        assert message.token_usage is None

    def test_assistant_message(self):
        """Test creating an assistant message."""
        message = ChatMessage(
            id="msg_123",
            session_id="session_456",
            user_id="user_789",
            role=MessageRole.ASSISTANT,
            content="I can help you with that.",
            status=MessageStatus.COMPLETED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        assert message.role == MessageRole.ASSISTANT
        assert message.status == MessageStatus.COMPLETED


class TestTokenUsage:
    """Test TokenUsage model."""

    def test_valid_token_usage(self):
        """Test creating valid token usage record."""
        usage = TokenUsage(
            id="usage_123",
            message_id="msg_456",
            session_id="session_789",
            endpoint="ollama",
            total_tokens=150,
            prompt_tokens=100,
            completion_tokens=50,
            cost=0.0,
            model="llama3.2",
            created_at=datetime.utcnow(),
        )
        
        assert usage.id == "usage_123"
        assert usage.message_id == "msg_456"
        assert usage.total_tokens == 150
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.cost == 0.0
        assert usage.model == "llama3.2"

    def test_token_usage_calculation(self):
        """Test that token counts are consistent."""
        usage = TokenUsage(
            id="usage_123",
            message_id="msg_456",
            session_id="session_789",
            endpoint="ollama",
            total_tokens=150,
            prompt_tokens=100,
            completion_tokens=50,
            cost=0.0,
            model="llama3.2",
            created_at=datetime.utcnow(),
        )
        
        # Verify total equals prompt + completion
        assert usage.total_tokens == usage.prompt_tokens + usage.completion_tokens


class TestMessageVote:
    """Test MessageVote model."""

    def test_valid_upvote(self):
        """Test creating an upvote."""
        vote = MessageVote(
            id="vote_123",
            message_id="msg_456",
            user_id="user_789",
            vote_type=VoteType.UP,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        assert vote.id == "vote_123"
        assert vote.message_id == "msg_456"
        assert vote.user_id == "user_789"
        assert vote.vote_type == VoteType.UP

    def test_valid_downvote(self):
        """Test creating a downvote."""
        vote = MessageVote(
            id="vote_123",
            message_id="msg_456",
            user_id="user_789",
            vote_type=VoteType.DOWN,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        assert vote.vote_type == VoteType.DOWN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
