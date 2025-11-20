"""
Advanced RAG Features - Conversation Memory Management

Sophisticated conversation memory system that maintains context across interactions,
tracks conversation history, and provides intelligent context management for 
multi-turn conversations in the RAG system.
"""

import asyncio
from datetime import datetime, timedelta
from enum import Enum
import json
from typing import Any, Dict, List, Optional, Tuple

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.rag.core.exceptions import RAGError
from second_brain_database.rag.core.types import Conversation, ConversationTurn, QueryRequest, QueryResponse

logger = get_logger()


class ConversationStrategy(str, Enum):
    """Conversation memory strategies."""
    SLIDING_WINDOW = "sliding_window"  # Keep last N turns
    SUMMARIZATION = "summarization"    # Summarize older context
    HIERARCHICAL = "hierarchical"      # Important + recent context
    ADAPTIVE = "adaptive"              # Dynamic based on conversation


class ConversationMemoryManager:
    """
    Advanced conversation memory management for RAG system.
    
    Provides sophisticated conversation context management with multiple strategies
    for maintaining conversation history and optimizing context windows.
    """
    
    def __init__(
        self, 
        strategy: ConversationStrategy = ConversationStrategy.ADAPTIVE,
        max_turns: int = 10,
        max_context_tokens: int = 4000,
        memory_decay_hours: int = 24
    ):
        """
        Initialize conversation memory manager.
        
        Args:
            strategy: Memory management strategy
            max_turns: Maximum conversation turns to maintain
            max_context_tokens: Maximum tokens for context window
            memory_decay_hours: Hours after which old conversations decay
        """
        self.strategy = strategy
        self.max_turns = max_turns
        self.max_context_tokens = max_context_tokens
        self.memory_decay_hours = memory_decay_hours
        
        logger.info(f"Initialized conversation memory with {strategy} strategy")
    
    async def get_conversation(
        self, 
        conversation_id: str, 
        user_id: str
    ) -> Optional[Conversation]:
        """
        Retrieve conversation with all turns.
        
        Args:
            conversation_id: Unique conversation identifier
            user_id: User ID for security filtering
            
        Returns:
            Conversation object or None if not found
        """
        try:
            collection = db_manager.get_collection("conversations")
            
            conversation_data = await collection.find_one({
                "id": conversation_id,
                "user_id": user_id
            })
            
            if not conversation_data:
                return None
            
            # Convert to Conversation object
            return Conversation(**conversation_data)
            
        except Exception as e:
            logger.error(f"Failed to retrieve conversation {conversation_id}: {e}")
            raise RAGError(f"Conversation retrieval failed: {e}")
    
    async def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Conversation:
        """
        Create a new conversation.
        
        Args:
            user_id: User ID
            title: Optional conversation title
            metadata: Optional metadata
            
        Returns:
            New conversation object
        """
        try:
            conversation = Conversation(
                user_id=user_id,
                title=title or f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
                turns=[],
                metadata=metadata or {},
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            # Store in database
            collection = db_manager.get_collection("conversations")
            await collection.insert_one(conversation.dict())
            
            logger.info(f"Created conversation {conversation.id} for user {user_id}")
            return conversation
            
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            raise RAGError(f"Conversation creation failed: {e}")
    
    async def add_turn(
        self,
        conversation_id: str,
        user_id: str,
        query: str,
        response: str,
        context: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> ConversationTurn:
        """
        Add a new turn to the conversation.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User ID
            query: User query
            response: AI response
            context: Retrieved context chunks
            metadata: Optional turn metadata
            
        Returns:
            New conversation turn
        """
        try:
            # Create new turn
            turn = ConversationTurn(
                query=query,
                response=response,
                context=context,
                metadata=metadata or {},
                timestamp=datetime.utcnow()
            )
            
            # Update conversation in database
            collection = db_manager.get_collection("conversations")
            
            result = await collection.update_one(
                {"id": conversation_id, "user_id": user_id},
                {
                    "$push": {"turns": turn.dict()},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.matched_count == 0:
                raise RAGError(f"Conversation {conversation_id} not found")
            
            # Apply memory management strategy
            await self._apply_memory_strategy(conversation_id, user_id)
            
            logger.info(f"Added turn to conversation {conversation_id}")
            return turn
            
        except Exception as e:
            logger.error(f"Failed to add turn to conversation {conversation_id}: {e}")
            raise RAGError(f"Failed to add conversation turn: {e}")
    
    async def get_conversation_context(
        self,
        conversation_id: str,
        user_id: str,
        current_query: str
    ) -> List[str]:
        """
        Get optimized conversation context for current query.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User ID
            current_query: Current user query
            
        Returns:
            List of context strings from conversation history
        """
        try:
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                return []
            
            # Apply strategy-specific context optimization
            if self.strategy == ConversationStrategy.SLIDING_WINDOW:
                return self._get_sliding_window_context(conversation)
            elif self.strategy == ConversationStrategy.SUMMARIZATION:
                return await self._get_summarized_context(conversation)
            elif self.strategy == ConversationStrategy.HIERARCHICAL:
                return await self._get_hierarchical_context(conversation, current_query)
            elif self.strategy == ConversationStrategy.ADAPTIVE:
                return await self._get_adaptive_context(conversation, current_query)
            
            return []
            
        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return []
    
    def _get_sliding_window_context(self, conversation: Conversation) -> List[str]:
        """Get context using sliding window strategy."""
        recent_turns = conversation.turns[-self.max_turns:]
        context = []
        
        for turn in recent_turns:
            context.append(f"Q: {turn.query}")
            context.append(f"A: {turn.response}")
        
        return context
    
    async def _get_summarized_context(self, conversation: Conversation) -> List[str]:
        """Get context using summarization strategy."""
        if len(conversation.turns) <= self.max_turns:
            return self._get_sliding_window_context(conversation)
        
        # Keep recent turns as-is
        recent_turns = conversation.turns[-self.max_turns//2:]
        older_turns = conversation.turns[:-self.max_turns//2]
        
        context = []
        
        # Summarize older turns
        if older_turns:
            summary = await self._summarize_turns(older_turns)
            context.append(f"Previous conversation summary: {summary}")
        
        # Add recent turns
        for turn in recent_turns:
            context.append(f"Q: {turn.query}")
            context.append(f"A: {turn.response}")
        
        return context
    
    async def _get_hierarchical_context(
        self, 
        conversation: Conversation, 
        current_query: str
    ) -> List[str]:
        """Get context using hierarchical importance strategy."""
        context = []
        
        # Find important turns (those with high relevance scores)
        important_turns = await self._find_important_turns(conversation.turns, current_query)
        
        # Get recent turns
        recent_turns = conversation.turns[-3:] if conversation.turns else []
        
        # Combine important and recent (avoiding duplicates)
        all_turns = []
        turn_ids = set()
        
        for turn in important_turns + recent_turns:
            turn_id = f"{turn.timestamp}_{turn.query[:50]}"
            if turn_id not in turn_ids:
                all_turns.append(turn)
                turn_ids.add(turn_id)
        
        # Sort by timestamp
        all_turns.sort(key=lambda x: x.timestamp)
        
        for turn in all_turns:
            context.append(f"Q: {turn.query}")
            context.append(f"A: {turn.response}")
        
        return context
    
    async def _get_adaptive_context(
        self, 
        conversation: Conversation, 
        current_query: str
    ) -> List[str]:
        """Get context using adaptive strategy based on conversation characteristics."""
        if len(conversation.turns) <= 3:
            # Short conversation - use all turns
            return self._get_sliding_window_context(conversation)
        
        # Analyze conversation pattern
        query_similarity = await self._analyze_query_patterns(conversation.turns, current_query)
        
        if query_similarity > 0.7:
            # High similarity - use hierarchical approach
            return await self._get_hierarchical_context(conversation, current_query)
        else:
            # Low similarity - use recent context only
            return self._get_sliding_window_context(conversation)
    
    async def _apply_memory_strategy(self, conversation_id: str, user_id: str):
        """Apply memory management strategy to limit conversation size."""
        try:
            collection = db_manager.get_collection("conversations")
            conversation_data = await collection.find_one({
                "id": conversation_id,
                "user_id": user_id
            })
            
            if not conversation_data or len(conversation_data.get("turns", [])) <= self.max_turns:
                return
            
            turns = conversation_data["turns"]
            
            if self.strategy == ConversationStrategy.SLIDING_WINDOW:
                # Keep only recent turns
                new_turns = turns[-self.max_turns:]
            elif self.strategy == ConversationStrategy.SUMMARIZATION:
                # Summarize older turns and keep recent ones
                recent_turns = turns[-self.max_turns//2:]
                older_turns = turns[:-self.max_turns//2]
                
                if older_turns:
                    summary = await self._summarize_turns(older_turns)
                    # Store summary in conversation metadata
                    await collection.update_one(
                        {"id": conversation_id},
                        {"$set": {"metadata.summary": summary}}
                    )
                
                new_turns = recent_turns
            else:
                # For hierarchical and adaptive, use turn importance
                important_turns = await self._find_important_turns(turns, "")
                new_turns = important_turns[-self.max_turns:]
            
            # Update conversation with managed turns
            await collection.update_one(
                {"id": conversation_id},
                {"$set": {"turns": [turn.dict() if hasattr(turn, 'dict') else turn for turn in new_turns]}}
            )
            
        except Exception as e:
            logger.error(f"Failed to apply memory strategy: {e}")
    
    async def _summarize_turns(self, turns: List[ConversationTurn]) -> str:
        """Summarize conversation turns."""
        # Simple extractive summarization - in production, use LLM
        key_points = []
        
        for turn in turns:
            # Extract key information from queries and responses
            if len(turn.query) > 20:
                key_points.append(f"Asked about: {turn.query[:100]}")
            if len(turn.response) > 50:
                key_points.append(f"Discussed: {turn.response[:150]}")
        
        return " | ".join(key_points[:5])  # Limit summary length
    
    async def _find_important_turns(
        self, 
        turns: List[ConversationTurn], 
        current_query: str
    ) -> List[ConversationTurn]:
        """Find important conversation turns based on relevance."""
        # Simple importance scoring - in production, use semantic similarity
        important_turns = []
        
        for turn in turns:
            importance_score = 0
            
            # Score based on query length (longer queries often more important)
            if len(turn.query) > 50:
                importance_score += 0.3
            
            # Score based on response length (detailed responses often important)
            if len(turn.response) > 200:
                importance_score += 0.3
            
            # Score based on context richness
            if len(turn.context) > 2:
                importance_score += 0.2
            
            # Score based on recency (more recent = more important)
            hours_ago = (datetime.utcnow() - turn.timestamp).total_seconds() / 3600
            recency_score = max(0, 0.2 * (1 - hours_ago / 24))  # Decay over 24 hours
            importance_score += recency_score
            
            if importance_score > 0.5:  # Threshold for importance
                important_turns.append(turn)
        
        return sorted(important_turns, key=lambda x: x.timestamp)[-10:]  # Keep top 10
    
    async def _analyze_query_patterns(
        self, 
        turns: List[ConversationTurn], 
        current_query: str
    ) -> float:
        """Analyze similarity between current query and conversation history."""
        if not turns:
            return 0.0
        
        # Simple keyword-based similarity - in production, use embeddings
        current_words = set(current_query.lower().split())
        
        similarities = []
        for turn in turns[-5:]:  # Check last 5 turns
            turn_words = set(turn.query.lower().split())
            if turn_words:
                similarity = len(current_words & turn_words) / len(current_words | turn_words)
                similarities.append(similarity)
        
        return max(similarities) if similarities else 0.0
    
    async def cleanup_old_conversations(self, days_old: int = 30) -> int:
        """Clean up old conversations to manage storage."""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            collection = db_manager.get_collection("conversations")
            result = await collection.delete_many({
                "updated_at": {"$lt": cutoff_date}
            })
            
            logger.info(f"Cleaned up {result.deleted_count} old conversations")
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old conversations: {e}")
            return 0
    
    async def get_conversation_summary(
        self, 
        conversation_id: str, 
        user_id: str
    ) -> Dict[str, Any]:
        """Get conversation analytics and summary."""
        try:
            conversation = await self.get_conversation(conversation_id, user_id)
            if not conversation:
                return {}
            
            total_turns = len(conversation.turns)
            if total_turns == 0:
                return {"total_turns": 0, "duration_minutes": 0}
            
            # Calculate conversation duration
            first_turn = conversation.turns[0].timestamp
            last_turn = conversation.turns[-1].timestamp
            duration_minutes = (last_turn - first_turn).total_seconds() / 60
            
            # Calculate average response length
            avg_response_length = sum(len(turn.response) for turn in conversation.turns) / total_turns
            
            # Find most discussed topics (simple keyword extraction)
            all_queries = " ".join(turn.query for turn in conversation.turns)
            words = all_queries.lower().split()
            word_freq = {}
            for word in words:
                if len(word) > 3:  # Skip short words
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            top_topics = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                "conversation_id": conversation_id,
                "total_turns": total_turns,
                "duration_minutes": round(duration_minutes, 2),
                "avg_response_length": round(avg_response_length, 2),
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
                "top_topics": [{"word": word, "frequency": freq} for word, freq in top_topics],
                "strategy_used": self.strategy.value
            }
            
        except Exception as e:
            logger.error(f"Failed to get conversation summary: {e}")
            return {}