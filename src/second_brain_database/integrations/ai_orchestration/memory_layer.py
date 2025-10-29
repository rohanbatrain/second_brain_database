"""
AI Memory Layer with Intelligent Context Management

This module provides intelligent memory and context management for AI agents
with Redis caching, MongoDB persistence, and performance optimization.

Features:
- Short-term memory with Redis caching
- Long-term memory with MongoDB persistence
- Context preloading for faster responses
- Intelligent cache invalidation
- Conversation history management
- User and family context integration
"""

from typing import Dict, Any, List, Optional, AsyncGenerator, Union
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
import json
import hashlib
import asyncio

from ...managers.redis_manager import redis_manager
from ...database import db_manager
from ...managers.logging_manager import get_logger
from ...config import settings
from .security import ai_privacy_manager, ConversationPrivacyMode

logger = get_logger(prefix="[MemoryLayer]")


@dataclass
class ContextItem:
    """Individual context item with metadata."""
    key: str
    value: Any
    context_type: str  # user, family, workspace, conversation, system
    user_id: str
    session_id: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.updated_at is None:
            self.updated_at = self.created_at


@dataclass
class ConversationMessage:
    """Conversation message with metadata."""
    message_id: str
    session_id: str
    user_id: str
    role: str  # user, assistant, system
    content: str
    agent_type: str
    timestamp: datetime
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class UserContext:
    """User context with preferences and knowledge."""
    user_id: str
    username: str
    preferences: Dict[str, Any]
    knowledge_items: List[Dict[str, Any]]
    conversation_style: str
    privacy_settings: Dict[str, Any]
    last_updated: datetime
    
    def __post_init__(self):
        if self.preferences is None:
            self.preferences = {}
        if self.knowledge_items is None:
            self.knowledge_items = []
        if self.privacy_settings is None:
            self.privacy_settings = {}


@dataclass
class FamilyContext:
    """Family context with relationships and shared data."""
    family_id: str
    family_name: str
    user_role: str
    members: List[Dict[str, Any]]
    shared_memory: Dict[str, Any]
    permissions: List[str]
    last_updated: datetime
    
    def __post_init__(self):
        if self.members is None:
            self.members = []
        if self.shared_memory is None:
            self.shared_memory = {}
        if self.permissions is None:
            self.permissions = []


class ContextCache:
    """
    High-performance context caching system using Redis.
    
    Provides intelligent caching with TTL management and
    automatic invalidation for context data.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[ContextCache]")
        self.cache_prefix = "ai:context"
        
    def _generate_cache_key(self, context_type: str, identifier: str, sub_key: str = None) -> str:
        """Generate cache key for context data."""
        if sub_key:
            return f"{self.cache_prefix}:{context_type}:{identifier}:{sub_key}"
        return f"{self.cache_prefix}:{context_type}:{identifier}"
    
    async def get_context(
        self, 
        context_type: str, 
        identifier: str, 
        sub_key: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get context data from cache.
        
        Args:
            context_type: Type of context (user, family, workspace, etc.)
            identifier: Context identifier (user_id, family_id, etc.)
            sub_key: Optional sub-key for nested data
            
        Returns:
            Context data or None if not found
        """
        try:
            redis = await redis_manager.get_redis()
            cache_key = self._generate_cache_key(context_type, identifier, sub_key)
            
            cached_data = await redis.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
                
        except Exception as e:
            self.logger.error("Failed to get context from cache: %s", e)
            
        return None
    
    async def set_context(
        self,
        context_type: str,
        identifier: str,
        data: Dict[str, Any],
        ttl: int = None,
        sub_key: str = None
    ) -> bool:
        """
        Set context data in cache.
        
        Args:
            context_type: Type of context
            identifier: Context identifier
            data: Context data to cache
            ttl: Time to live in seconds
            sub_key: Optional sub-key for nested data
            
        Returns:
            True if cached successfully, False otherwise
        """
        try:
            redis = await redis_manager.get_redis()
            cache_key = self._generate_cache_key(context_type, identifier, sub_key)
            
            cache_ttl = ttl or settings.AI_CONVERSATION_CACHE_TTL
            await redis.setex(cache_key, cache_ttl, json.dumps(data, default=str))
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to set context in cache: %s", e)
            return False
    
    async def invalidate_context(
        self, 
        context_type: str, 
        identifier: str, 
        sub_key: str = None
    ) -> bool:
        """
        Invalidate context data in cache.
        
        Args:
            context_type: Type of context
            identifier: Context identifier
            sub_key: Optional sub-key for nested data
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        try:
            redis = await redis_manager.get_redis()
            
            if sub_key:
                cache_key = self._generate_cache_key(context_type, identifier, sub_key)
                await redis.delete(cache_key)
            else:
                # Invalidate all sub-keys for this context
                pattern = self._generate_cache_key(context_type, identifier, "*")
                keys = await redis.keys(pattern)
                if keys:
                    await redis.delete(*keys)
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to invalidate context cache: %s", e)
            return False
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        try:
            redis = await redis_manager.get_redis()
            
            # Count cache entries by type
            stats = {}
            for context_type in ["user", "family", "workspace", "conversation", "system"]:
                pattern = f"{self.cache_prefix}:{context_type}:*"
                keys = await redis.keys(pattern)
                stats[f"{context_type}_entries"] = len(keys)
            
            # Total entries
            all_keys = await redis.keys(f"{self.cache_prefix}:*")
            stats["total_entries"] = len(all_keys)
            
            return stats
            
        except Exception as e:
            self.logger.error("Failed to get cache stats: %s", e)
            return {"error": str(e)}


class MemoryLayer:
    """
    Intelligent memory and context management system for AI agents.
    
    Provides unified access to short-term (Redis) and long-term (MongoDB)
    memory with intelligent caching and context preloading.
    """
    
    def __init__(self):
        """Initialize the memory layer."""
        self.logger = get_logger(prefix="[MemoryLayer]")
        self.cache = ContextCache()
        
        # Context preloading configuration
        self.preload_enabled = settings.AI_CONTEXT_PRELOAD_ENABLED
        self.preload_cache: Dict[str, Dict[str, Any]] = {}
        self.preload_lock = asyncio.Lock()
        
        # Start background tasks
        if self.preload_enabled:
            asyncio.create_task(self._context_preload_task())
    
    async def _context_preload_task(self):
        """Background task for context preloading."""
        while True:
            try:
                await asyncio.sleep(300)  # Preload every 5 minutes
                await self._preload_frequent_contexts()
                
            except Exception as e:
                self.logger.error("Context preload task error: %s", e)
    
    async def _preload_frequent_contexts(self):
        """Preload frequently accessed contexts."""
        try:
            # Get active sessions to determine which contexts to preload
            redis = await redis_manager.get_redis()
            session_keys = await redis.keys("ai:session:*")
            
            user_ids = set()
            for key in session_keys:
                try:
                    session_data = await redis.get(key)
                    if session_data:
                        session = json.loads(session_data)
                        user_ids.add(session.get("user_id"))
                except:
                    continue
            
            # Preload user contexts for active users
            async with self.preload_lock:
                for user_id in user_ids:
                    if user_id and user_id not in self.preload_cache:
                        context = await self._load_user_context_from_db(user_id)
                        if context:
                            self.preload_cache[user_id] = asdict(context)
                            self.logger.debug("Preloaded context for user %s", user_id)
            
            self.logger.debug("Preloaded contexts for %d users", len(user_ids))
            
        except Exception as e:
            self.logger.error("Failed to preload contexts: %s", e)
    
    async def load_user_context(self, user_id: str) -> Optional[UserContext]:
        """
        Load user context with caching and preloading.
        
        Args:
            user_id: User identifier
            
        Returns:
            UserContext or None if not found
        """
        try:
            # Check preload cache first
            if self.preload_enabled and user_id in self.preload_cache:
                cached_data = self.preload_cache[user_id]
                return UserContext(**cached_data)
            
            # Check Redis cache
            cached_context = await self.cache.get_context("user", user_id)
            if cached_context:
                return UserContext(**cached_context)
            
            # Load from database
            context = await self._load_user_context_from_db(user_id)
            if context:
                # Cache the context
                await self.cache.set_context("user", user_id, asdict(context))
                return context
            
        except Exception as e:
            self.logger.error("Failed to load user context for %s: %s", user_id, e)
        
        return None
    
    async def _load_user_context_from_db(self, user_id: str) -> Optional[UserContext]:
        """Load user context from MongoDB."""
        try:
            users_collection = db_manager.get_collection("users")
            user_doc = await users_collection.find_one({"_id": user_id})
            
            if user_doc:
                return UserContext(
                    user_id=user_id,
                    username=user_doc.get("username", ""),
                    preferences=user_doc.get("preferences", {}),
                    knowledge_items=user_doc.get("knowledge_items", []),
                    conversation_style=user_doc.get("conversation_style", "friendly"),
                    privacy_settings=user_doc.get("privacy_settings", {}),
                    last_updated=user_doc.get("updated_at", datetime.now(timezone.utc))
                )
                
        except Exception as e:
            self.logger.error("Failed to load user context from DB for %s: %s", user_id, e)
        
        return None
    
    async def load_family_context(self, family_id: str, user_id: str) -> Optional[FamilyContext]:
        """
        Load family context for a user.
        
        Args:
            family_id: Family identifier
            user_id: User identifier
            
        Returns:
            FamilyContext or None if not found
        """
        try:
            # Check cache first
            cache_key = f"{family_id}:{user_id}"
            cached_context = await self.cache.get_context("family", cache_key)
            if cached_context:
                return FamilyContext(**cached_context)
            
            # Load from database
            context = await self._load_family_context_from_db(family_id, user_id)
            if context:
                # Cache the context
                await self.cache.set_context("family", cache_key, asdict(context))
                return context
            
        except Exception as e:
            self.logger.error("Failed to load family context for %s/%s: %s", family_id, user_id, e)
        
        return None
    
    async def _load_family_context_from_db(self, family_id: str, user_id: str) -> Optional[FamilyContext]:
        """Load family context from MongoDB."""
        try:
            families_collection = db_manager.get_collection("families")
            family_doc = await families_collection.find_one({"_id": family_id})
            
            if family_doc:
                # Find user's role in the family
                user_role = "member"
                for member in family_doc.get("members", []):
                    if member.get("user_id") == user_id:
                        user_role = member.get("role", "member")
                        break
                
                return FamilyContext(
                    family_id=family_id,
                    family_name=family_doc.get("name", ""),
                    user_role=user_role,
                    members=family_doc.get("members", []),
                    shared_memory=family_doc.get("shared_memory", {}),
                    permissions=family_doc.get("permissions", []),
                    last_updated=family_doc.get("updated_at", datetime.now(timezone.utc))
                )
                
        except Exception as e:
            self.logger.error("Failed to load family context from DB for %s: %s", family_id, e)
        
        return None
    
    async def store_conversation_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        agent_type: str,
        metadata: Dict[str, Any] = None,
        privacy_mode: ConversationPrivacyMode = ConversationPrivacyMode.PRIVATE,
        family_id: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> bool:
        """
        Store a conversation message with privacy protection and caching.
        
        Args:
            session_id: AI session identifier
            user_id: User identifier
            role: Message role (user, assistant, system)
            content: Message content
            agent_type: Agent type that handled the message
            metadata: Additional message metadata
            privacy_mode: Privacy mode for the conversation
            family_id: Optional family ID for family-shared conversations
            workspace_id: Optional workspace ID for workspace conversations
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            message = ConversationMessage(
                message_id=f"{session_id}_{datetime.now(timezone.utc).timestamp()}",
                session_id=session_id,
                user_id=user_id,
                role=role,
                content=content,
                agent_type=agent_type,
                timestamp=datetime.now(timezone.utc),
                metadata=metadata or {}
            )
            
            # Create user context for privacy manager
            from ...integrations.mcp.context import MCPUserContext
            user_context = MCPUserContext(
                user_id=user_id,
                username="",  # Would be populated from user data
                permissions=[]
            )
            
            # Store conversation with privacy protection
            conversation_data = {
                "messages": [asdict(message)],
                "session_metadata": {
                    "agent_type": agent_type,
                    "last_updated": datetime.now(timezone.utc).isoformat()
                }
            }
            
            # Use privacy manager for secure storage
            privacy_stored = await ai_privacy_manager.store_conversation(
                conversation_id=session_id,
                user_context=user_context,
                conversation_data=conversation_data,
                privacy_mode=privacy_mode,
                agent_type=agent_type,
                family_id=family_id,
                workspace_id=workspace_id
            )
            
            if privacy_stored:
                # Also store in cache for quick access (if not ephemeral)
                if privacy_mode != ConversationPrivacyMode.EPHEMERAL:
                    await self._cache_conversation_message(message)
                
                # Store in database for persistence (if not ephemeral)
                if privacy_mode != ConversationPrivacyMode.EPHEMERAL:
                    await self._persist_conversation_message(message)
            
            return privacy_stored
            
        except Exception as e:
            self.logger.error("Failed to store conversation message: %s", e)
            return False
    
    async def _cache_conversation_message(self, message: ConversationMessage):
        """Cache conversation message in Redis."""
        try:
            redis = await redis_manager.get_redis()
            
            # Add to session conversation list
            conversation_key = f"ai:conversation:{message.session_id}"
            message_data = asdict(message)
            message_data["timestamp"] = message.timestamp.isoformat()
            
            await redis.lpush(conversation_key, json.dumps(message_data, default=str))
            
            # Keep only recent messages in cache
            await redis.ltrim(conversation_key, 0, settings.AI_MEMORY_CONVERSATION_HISTORY - 1)
            
            # Set TTL for conversation cache
            await redis.expire(conversation_key, settings.AI_CONVERSATION_CACHE_TTL)
            
        except Exception as e:
            self.logger.error("Failed to cache conversation message: %s", e)
    
    async def _persist_conversation_message(self, message: ConversationMessage):
        """Persist conversation message to MongoDB."""
        try:
            conversations_collection = db_manager.get_collection("ai_conversations")
            
            message_doc = asdict(message)
            await conversations_collection.insert_one(message_doc)
            
        except Exception as e:
            self.logger.error("Failed to persist conversation message: %s", e)
    
    async def get_conversation_history(
        self,
        session_id: str,
        user_id: str,
        limit: int = None,
        requesting_user_id: Optional[str] = None
    ) -> List[ConversationMessage]:
        """
        Get conversation history for a session with privacy protection.
        
        Args:
            session_id: AI session identifier
            user_id: User ID who owns the conversation
            limit: Maximum number of messages to return
            requesting_user_id: Optional different user requesting access
            
        Returns:
            List of ConversationMessage objects
        """
        try:
            # Create user context for privacy manager
            from ...integrations.mcp.context import MCPUserContext
            user_context = MCPUserContext(
                user_id=user_id,
                username="",  # Would be populated from user data
                permissions=[]
            )
            
            # Try to retrieve conversation with privacy protection
            conversation_data = await ai_privacy_manager.retrieve_conversation(
                conversation_id=session_id,
                user_context=user_context,
                requesting_user_id=requesting_user_id
            )
            
            if conversation_data and "data" in conversation_data:
                messages_data = conversation_data["data"].get("messages", [])
                messages = []
                
                for msg_data in messages_data:
                    try:
                        message = ConversationMessage(**msg_data)
                        messages.append(message)
                    except Exception as e:
                        self.logger.warning("Failed to parse message data: %s", e)
                        continue
                
                # Apply limit if specified
                if limit and len(messages) > limit:
                    messages = messages[-limit:]
                
                return messages
            
            # Fallback to cache/database if privacy manager doesn't have the conversation
            messages = await self._get_cached_conversation_history(session_id, limit)
            if messages:
                return messages
            
            # Final fallback to database
            return await self._get_persisted_conversation_history(session_id, limit)
            
        except Exception as e:
            self.logger.error("Failed to get conversation history for %s: %s", session_id, e)
            return []
    
    async def _get_cached_conversation_history(
        self,
        session_id: str,
        limit: int = None
    ) -> List[ConversationMessage]:
        """Get conversation history from Redis cache."""
        try:
            redis = await redis_manager.get_redis()
            conversation_key = f"ai:conversation:{session_id}"
            
            message_limit = limit or settings.AI_MEMORY_CONVERSATION_HISTORY
            cached_messages = await redis.lrange(conversation_key, 0, message_limit - 1)
            
            messages = []
            for msg_data in cached_messages:
                try:
                    msg_dict = json.loads(msg_data)
                    msg_dict["timestamp"] = datetime.fromisoformat(msg_dict["timestamp"])
                    messages.append(ConversationMessage(**msg_dict))
                except:
                    continue
            
            # Reverse to get chronological order (Redis stores newest first)
            return list(reversed(messages))
            
        except Exception as e:
            self.logger.error("Failed to get cached conversation history: %s", e)
            return []
    
    async def _get_persisted_conversation_history(
        self,
        session_id: str,
        limit: int = None
    ) -> List[ConversationMessage]:
        """Get conversation history from MongoDB."""
        try:
            conversations_collection = db_manager.get_collection("ai_conversations")
            
            message_limit = limit or settings.AI_MEMORY_CONVERSATION_HISTORY
            cursor = conversations_collection.find(
                {"session_id": session_id}
            ).sort("timestamp", 1).limit(message_limit)
            
            messages = []
            async for doc in cursor:
                messages.append(ConversationMessage(**doc))
            
            return messages
            
        except Exception as e:
            self.logger.error("Failed to get persisted conversation history: %s", e)
            return []
    
    async def search_knowledge(
        self,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search user's knowledge base.
        
        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of knowledge items
        """
        try:
            # For now, implement simple text search
            # In the future, this could be enhanced with semantic search
            
            user_context = await self.load_user_context(user_id)
            if not user_context or not user_context.knowledge_items:
                return []
            
            # Simple text matching
            query_lower = query.lower()
            matching_items = []
            
            for item in user_context.knowledge_items:
                content = str(item.get("content", "")).lower()
                title = str(item.get("title", "")).lower()
                
                if query_lower in content or query_lower in title:
                    # Add relevance score based on position of match
                    score = 1.0
                    if query_lower in title:
                        score += 0.5  # Title matches are more relevant
                    
                    item_with_score = dict(item)
                    item_with_score["relevance_score"] = score
                    matching_items.append(item_with_score)
            
            # Sort by relevance score
            matching_items.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
            
            return matching_items[:limit]
            
        except Exception as e:
            self.logger.error("Failed to search knowledge for %s: %s", user_id, e)
            return []
    
    async def add_knowledge_item(
        self,
        user_id: str,
        title: str,
        content: str,
        tags: List[str] = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Add a knowledge item to user's knowledge base.
        
        Args:
            user_id: User identifier
            title: Knowledge item title
            content: Knowledge item content
            tags: Optional tags for categorization
            metadata: Additional metadata
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            knowledge_item = {
                "id": f"{user_id}_{datetime.now(timezone.utc).timestamp()}",
                "title": title,
                "content": content,
                "tags": tags or [],
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Add to user's knowledge items in database
            users_collection = db_manager.get_collection("users")
            await users_collection.update_one(
                {"_id": user_id},
                {
                    "$push": {"knowledge_items": knowledge_item},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            
            # Invalidate user context cache
            await self.cache.invalidate_context("user", user_id)
            
            # Remove from preload cache
            if user_id in self.preload_cache:
                async with self.preload_lock:
                    del self.preload_cache[user_id]
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to add knowledge item for %s: %s", user_id, e)
            return False
    
    async def update_user_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any]
    ) -> bool:
        """
        Update user preferences.
        
        Args:
            user_id: User identifier
            preferences: Updated preferences
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            users_collection = db_manager.get_collection("users")
            await users_collection.update_one(
                {"_id": user_id},
                {
                    "$set": {
                        "preferences": preferences,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            
            # Invalidate caches
            await self.cache.invalidate_context("user", user_id)
            if user_id in self.preload_cache:
                async with self.preload_lock:
                    del self.preload_cache[user_id]
            
            return True
            
        except Exception as e:
            self.logger.error("Failed to update user preferences for %s: %s", user_id, e)
            return False
    
    async def cleanup_old_conversations(self, days: int = 30) -> int:
        """
        Clean up old conversation data.
        
        Args:
            days: Number of days to keep conversations
            
        Returns:
            Number of conversations cleaned up
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            conversations_collection = db_manager.get_collection("ai_conversations")
            result = await conversations_collection.delete_many(
                {"timestamp": {"$lt": cutoff_date}}
            )
            
            self.logger.info("Cleaned up %d old conversation messages", result.deleted_count)
            return result.deleted_count
            
        except Exception as e:
            self.logger.error("Failed to cleanup old conversations: %s", e)
            return 0
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory layer statistics."""
        try:
            cache_stats = await self.cache.get_cache_stats()
            
            # Get conversation stats
            conversations_collection = db_manager.get_collection("ai_conversations")
            total_messages = await conversations_collection.count_documents({})
            
            # Get knowledge stats
            users_collection = db_manager.get_collection("users")
            users_with_knowledge = await users_collection.count_documents(
                {"knowledge_items": {"$exists": True, "$ne": []}}
            )
            
            return {
                "cache": cache_stats,
                "conversations": {
                    "total_messages": total_messages
                },
                "knowledge": {
                    "users_with_knowledge": users_with_knowledge
                },
                "preload": {
                    "enabled": self.preload_enabled,
                    "cached_users": len(self.preload_cache)
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            self.logger.error("Failed to get memory stats: %s", e)
            return {"error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the memory layer."""
        health_status = {
            "status": "healthy",
            "cache_enabled": True,
            "preload_enabled": self.preload_enabled,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            # Test Redis connection
            redis = await redis_manager.get_redis()
            await redis.ping()
            health_status["redis_available"] = True
            
            # Test MongoDB connection
            users_collection = db_manager.get_collection("users")
            await users_collection.find_one({}, {"_id": 1})
            health_status["mongodb_available"] = True
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    async def get_user_privacy_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get privacy settings for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary of privacy settings
        """
        try:
            return await ai_privacy_manager.get_user_privacy_settings(user_id)
        except Exception as e:
            self.logger.error("Failed to get privacy settings for user %s: %s", user_id, e)
            return {}
    
    async def update_user_privacy_settings(
        self, 
        user_id: str, 
        settings_update: Dict[str, Any]
    ) -> bool:
        """
        Update privacy settings for a user.
        
        Args:
            user_id: User identifier
            settings_update: Settings to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return await ai_privacy_manager.update_user_privacy_settings(user_id, settings_update)
        except Exception as e:
            self.logger.error("Failed to update privacy settings for user %s: %s", user_id, e)
            return False
    
    async def validate_conversation_privacy(
        self,
        user_id: str,
        privacy_mode: ConversationPrivacyMode,
        family_id: Optional[str] = None
    ) -> bool:
        """
        Validate if a user can use a specific privacy mode.
        
        Args:
            user_id: User identifier
            privacy_mode: Requested privacy mode
            family_id: Family ID for family-shared conversations
            
        Returns:
            True if privacy mode is valid for user, False otherwise
        """
        try:
            from ...integrations.mcp.context import MCPUserContext
            user_context = MCPUserContext(
                user_id=user_id,
                username="",
                permissions=[]
            )
            
            return await ai_privacy_manager.validate_conversation_privacy(
                user_context, privacy_mode, family_id
            )
        except Exception as e:
            self.logger.error("Failed to validate conversation privacy for user %s: %s", user_id, e)
            return False
    
    async def cleanup_expired_conversations(self) -> int:
        """
        Clean up expired conversations based on privacy settings.
        
        Returns:
            Number of conversations cleaned up
        """
        try:
            cleaned_count = 0
            redis = await redis_manager.get_redis()
            
            # Get all conversation keys
            conversation_keys = await redis.keys("ai:conversation:*")
            
            for key in conversation_keys:
                try:
                    # Check if conversation has expired
                    ttl = await redis.ttl(key)
                    if ttl == -2:  # Key doesn't exist
                        continue
                    elif ttl == -1:  # Key exists but has no expiration
                        continue
                    elif ttl <= 0:  # Key has expired
                        await redis.delete(key)
                        cleaned_count += 1
                        
                except Exception as e:
                    self.logger.warning("Failed to check expiration for key %s: %s", key, e)
                    continue
            
            if cleaned_count > 0:
                self.logger.info("Cleaned up %d expired conversations", cleaned_count)
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error("Failed to cleanup expired conversations: %s", e)
            return 0