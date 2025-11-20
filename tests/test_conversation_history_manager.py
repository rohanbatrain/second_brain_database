"""Tests for ConversationHistoryManager."""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from second_brain_database.chat.services.history_manager import ConversationHistoryManager


@pytest.mark.asyncio
async def test_conversation_history_manager_init():
    """Test ConversationHistoryManager initialization."""
    redis_manager = MagicMock()
    manager = ConversationHistoryManager(redis_manager, max_history=20)
    
    assert manager.redis_manager == redis_manager
    assert manager.max_history == 20
    assert manager.cache_ttl == 3600


@pytest.mark.asyncio
async def test_get_history_from_cache():
    """Test retrieving conversation history from Redis cache."""
    redis_manager = MagicMock()
    cached_history = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    redis_manager.get = AsyncMock(return_value=cached_history)
    
    manager = ConversationHistoryManager(redis_manager)
    db = MagicMock()
    
    result = await manager.get_history("session_123", db)
    
    assert result == cached_history
    redis_manager.get.assert_called_once_with("chat:history:session_123")


@pytest.mark.asyncio
async def test_get_history_from_database():
    """Test retrieving conversation history from MongoDB when cache misses."""
    redis_manager = MagicMock()
    redis_manager.get = AsyncMock(return_value=None)
    redis_manager.set_json = AsyncMock()
    
    # Mock MongoDB
    db = MagicMock()
    mock_cursor = MagicMock()
    mock_messages = [
        {"role": "assistant", "content": "Hi there!", "created_at": datetime(2025, 1, 1, 12, 1)},
        {"role": "user", "content": "Hello", "created_at": datetime(2025, 1, 1, 12, 0)},
    ]
    mock_cursor.to_list = AsyncMock(return_value=mock_messages)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    db.chat_messages.find = MagicMock(return_value=mock_cursor)
    
    manager = ConversationHistoryManager(redis_manager, max_history=20)
    result = await manager.get_history("session_123", db)
    
    # Should be reversed (oldest first)
    expected = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    assert result == expected
    
    # Should cache the result
    redis_manager.set_json.assert_called_once()


@pytest.mark.asyncio
async def test_invalidate_cache():
    """Test cache invalidation."""
    redis_manager = MagicMock()
    redis_manager.delete = AsyncMock()
    
    manager = ConversationHistoryManager(redis_manager)
    await manager.invalidate_cache("session_123")
    
    redis_manager.delete.assert_called_once_with("chat:history:session_123")


@pytest.mark.asyncio
async def test_format_for_llm():
    """Test formatting history for LLM consumption."""
    redis_manager = MagicMock()
    manager = ConversationHistoryManager(redis_manager)
    
    history = [
        {"role": "USER", "content": "Hello"},
        {"role": "ASSISTANT", "content": "Hi there!"}
    ]
    
    result = manager.format_for_llm(history)
    
    expected = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"}
    ]
    assert result == expected


@pytest.mark.asyncio
async def test_get_history_database_error():
    """Test handling database errors gracefully."""
    redis_manager = MagicMock()
    redis_manager.get = AsyncMock(return_value=None)
    
    # Mock MongoDB to raise an error
    db = MagicMock()
    db.chat_messages.find = MagicMock(side_effect=Exception("Database error"))
    
    manager = ConversationHistoryManager(redis_manager)
    result = await manager.get_history("session_123", db)
    
    # Should return empty list on error
    assert result == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
