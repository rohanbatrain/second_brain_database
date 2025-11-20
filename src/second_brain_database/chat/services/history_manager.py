"""Conversation history manager for chat system."""

import json
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import RedisManager

logger = get_logger()


class ConversationHistoryManager:
    """
    Manages conversation history with sliding window and Redis caching.
    
    This manager retrieves recent conversation history from MongoDB,
    caches it in Redis for performance, and formats it for LLM consumption.
    """

    def __init__(self, redis_manager: RedisManager, max_history: int = 20):
        """
        Initialize the conversation history manager.
        
        Args:
            redis_manager: Redis manager instance for caching
            max_history: Maximum number of messages to retrieve (default: 20)
        """
        self.redis_manager = redis_manager
        self.max_history = max_history
        self.cache_ttl = 3600  # 1 hour TTL for Redis cache
        self.logger = logger

    async def get_history(
        self, session_id: str, db: AsyncIOMotorDatabase
    ) -> List[Dict[str, str]]:
        """
        Get conversation history with Redis caching.
        
        This method first checks Redis cache for the conversation history.
        If not found, it loads from MongoDB, caches the result, and returns it.
        
        Args:
            session_id: The chat session ID
            db: MongoDB database instance
            
        Returns:
            List of message dictionaries with 'role' and 'content' keys,
            ordered from oldest to newest (last max_history messages)
        """
        # 1. Check Redis cache
        cache_key = f"chat:history:{session_id}"
        
        try:
            cached = await self.redis_manager.get(cache_key)
            if cached:
                self.logger.debug(f"[ConversationHistoryManager] Cache hit for session {session_id}")
                return cached if isinstance(cached, list) else json.loads(cached)
        except Exception as e:
            self.logger.warning(
                f"[ConversationHistoryManager] Failed to retrieve from cache: {e}. "
                "Falling back to database."
            )
        
        # 2. Load from MongoDB
        try:
            messages = await db.chat_messages.find(
                {"session_id": session_id},
                {"role": 1, "content": 1, "created_at": 1}
            ).sort("created_at", -1).limit(self.max_history).to_list(None)
            
            # 3. Format and reverse (oldest first for conversation flow)
            history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in reversed(messages)
            ]
            
            self.logger.debug(
                f"[ConversationHistoryManager] Loaded {len(history)} messages "
                f"from database for session {session_id}"
            )
            
            # 4. Cache in Redis
            try:
                await self.redis_manager.set_json(cache_key, history, expiry=self.cache_ttl)
                self.logger.debug(
                    f"[ConversationHistoryManager] Cached history for session {session_id} "
                    f"with TTL {self.cache_ttl}s"
                )
            except Exception as e:
                self.logger.warning(
                    f"[ConversationHistoryManager] Failed to cache history: {e}. "
                    "Continuing without cache."
                )
            
            return history
            
        except Exception as e:
            self.logger.error(
                f"[ConversationHistoryManager] Failed to load history from database "
                f"for session {session_id}: {e}",
                exc_info=True
            )
            # Return empty history on error to allow conversation to continue
            return []

    async def invalidate_cache(self, session_id: str) -> None:
        """
        Invalidate cache when new message is added.
        
        This should be called after adding a new message to ensure
        the next history retrieval gets fresh data.
        
        Args:
            session_id: The chat session ID
        """
        cache_key = f"chat:history:{session_id}"
        
        try:
            await self.redis_manager.delete(cache_key)
            self.logger.debug(
                f"[ConversationHistoryManager] Invalidated cache for session {session_id}"
            )
        except Exception as e:
            self.logger.warning(
                f"[ConversationHistoryManager] Failed to invalidate cache "
                f"for session {session_id}: {e}"
            )

    def format_for_llm(self, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Format history for LLM consumption.
        
        Ensures proper role formatting (lowercase) for LangChain/Ollama compatibility.
        
        Args:
            history: List of message dictionaries with 'role' and 'content' keys
            
        Returns:
            Formatted list of messages with lowercase roles
        """
        return [
            {"role": msg["role"].lower(), "content": msg["content"]}
            for msg in history
        ]
