"""ChatService for orchestrating chat sessions and LangGraph workflows.

This module provides the ChatService class that manages chat sessions,
coordinates workflow execution, and handles conversation history. It serves
as the main entry point for chat operations in the Second Brain system.

Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.3, 7.4, 8.3
"""

import time
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from second_brain_database.chat.graphs.general_response_graph import GeneralResponseGraph
from second_brain_database.chat.graphs.master_workflow_graph import MasterWorkflowGraph
from second_brain_database.chat.graphs.vector_rag_graph import VectorRAGGraph
from second_brain_database.chat.models.chat_models import (
    ChatMessage,
    ChatSession,
    TokenUsage,
    TokenUsageInfo,
)
from second_brain_database.chat.models.enums import MessageRole, MessageStatus
from second_brain_database.chat.models.request_models import (
    ChatMessageCreate,
    ChatSessionCreate,
)
from second_brain_database.chat.services.cache_manager import QueryCacheManager
from second_brain_database.chat.services.history_manager import ConversationHistoryManager
from second_brain_database.chat.services.statistics_manager import SessionStatisticsManager
from second_brain_database.chat.utils.logging_utils import (
    log_conversation_history,
    log_session_operation,
    log_streaming_error,
    log_token_usage,
)
from second_brain_database.chat.utils.metrics_tracker import get_metrics_tracker
from second_brain_database.chat.utils.ollama_manager import OllamaLLMManager
from second_brain_database.config import Settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import RedisManager

logger = get_logger()


class ChatService:
    """Service for managing chat sessions and orchestrating LangGraph workflows.
    
    This service provides the main interface for chat operations:
    - Session management (create, get, list, delete)
    - Message handling (create, stream, retrieve)
    - Ollama LLM initialization with token tracking
    - Conversation history management with Redis caching
    - Workflow orchestration (VectorRAG, General Chat, Master Workflow)
    
    The service integrates with Second Brain's existing infrastructure:
    - MongoDB for persistent storage
    - Redis for caching and rate limiting
    - Ollama for LLM inference
    - Qdrant for vector search (via VectorRAGGraph)
    
    Attributes:
        db: MongoDB database instance
        redis_manager: Redis manager for caching
        settings: Application settings
        model_id: Default model ID for LLM operations
        ollama_manager: Manager for Ollama LLM instances
        conversation_manager: Manager for conversation history
        cache_manager: Manager for query response caching
        statistics_manager: Manager for session statistics
        vector_rag_graph: Graph for vector RAG workflows
        general_response_graph: Graph for general chat workflows
        master_workflow_graph: Master orchestrator graph
    """
    
    def __init__(
        self,
        db: AsyncIOMotorDatabase,
        redis_manager: RedisManager,
        model_id: Optional[str] = None,
        settings: Optional[Settings] = None
    ):
        """Initialize ChatService with database and optional model override.
        
        Args:
            db: AsyncIOMotor database instance
            redis_manager: Redis manager for caching
            model_id: Optional model ID override. If None, uses settings default.
            settings: Optional settings instance. If None, creates new Settings.
        """
        self.db = db
        self.redis_manager = redis_manager
        self.settings = settings or Settings()
        self.model_id = model_id or self.settings.OLLAMA_CHAT_MODEL
        
        # Initialize managers
        self.ollama_manager = OllamaLLMManager(self.settings)
        self.conversation_manager = ConversationHistoryManager(
            redis_manager=redis_manager,
            max_history=self.settings.CHAT_MAX_HISTORY_LENGTH
        )
        self.cache_manager = QueryCacheManager(redis_manager=redis_manager)
        self.statistics_manager = SessionStatisticsManager(db=db)
        self.metrics_tracker = get_metrics_tracker(redis_manager=redis_manager, db=db)
        
        # Initialize LLM for graphs (without callbacks - will be added per request)
        base_llm = self.ollama_manager.create_llm(
            model=self.model_id,
            streaming=True
        )
        
        # Initialize graphs
        self.vector_rag_graph = VectorRAGGraph(llm=base_llm)
        self.general_response_graph = GeneralResponseGraph(llm=base_llm)
        self.master_workflow_graph = MasterWorkflowGraph(
            vector_rag_graph=self.vector_rag_graph,
            general_response_graph=self.general_response_graph,
            cache_manager=self.cache_manager
        )
        
        logger.info(
            f"ChatService initialized with model: {self.model_id}, "
            f"max_history: {self.settings.CHAT_MAX_HISTORY_LENGTH}"
        )

    async def create_session(
        self,
        user_id: str,
        session_data: ChatSessionCreate
    ) -> ChatSession:
        """Create new chat session with auto-generated title.
        
        Creates a new chat session in MongoDB with the specified type and
        knowledge base IDs. If no title is provided, it will be auto-generated
        from the first user message.
        
        Args:
            user_id: ID of the user creating the session
            session_data: Session creation data (type, title, knowledge_base_ids)
            
        Returns:
            ChatSession: Created session with generated ID and timestamps
            
        Raises:
            Exception: If session creation fails
        """
        try:
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Generate default title if not provided
            title = session_data.title or "New Chat"
            
            # Create session document
            now = datetime.utcnow()
            session = ChatSession(
                id=session_id,
                user_id=user_id,
                session_type=session_data.session_type,
                title=title,
                message_count=0,
                total_tokens=0,
                total_cost=0.0,
                last_message_at=None,
                knowledge_base_ids=session_data.knowledge_base_ids,
                created_at=now,
                updated_at=now,
                is_active=True
            )
            
            # Insert into MongoDB
            await self.db.chat_sessions.insert_one(session.model_dump())
            
            # Log session operation
            log_session_operation(
                operation="create",
                session_id=session_id,
                user_id=user_id,
                session_type=session_data.session_type.value,
                details={"kb_count": len(session_data.knowledge_base_ids)}
            )
            
            logger.info(
                f"Created chat session {session_id} for user {user_id} "
                f"(type: {session_data.session_type})"
            )
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session for user {user_id}: {e}", exc_info=True)
            raise
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Retrieve session by ID.
        
        Args:
            session_id: ID of the session to retrieve
            
        Returns:
            ChatSession if found, None otherwise
        """
        try:
            session_doc = await self.db.chat_sessions.find_one({"id": session_id})
            
            if not session_doc:
                logger.debug(f"Session {session_id} not found")
                return None
            
            return ChatSession(**session_doc)
            
        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id}: {e}", exc_info=True)
            return None
    
    async def list_sessions(
        self,
        user_id: str,
        session_type: Optional[str] = None,
        is_active: Optional[bool] = True,
        skip: int = 0,
        limit: int = 50
    ) -> List[ChatSession]:
        """List chat sessions for a user with optional filtering.
        
        Args:
            user_id: ID of the user
            session_type: Optional filter by session type (GENERAL, VECTOR, SQL)
            is_active: Optional filter by active status
            skip: Number of sessions to skip (pagination)
            limit: Maximum number of sessions to return
            
        Returns:
            List of ChatSession objects ordered by last_message_at (newest first)
        """
        try:
            # Build query
            query = {"user_id": user_id}
            
            if session_type is not None:
                query["session_type"] = session_type
            
            if is_active is not None:
                query["is_active"] = is_active
            
            # Query sessions with pagination
            cursor = self.db.chat_sessions.find(query).sort(
                "last_message_at", -1
            ).skip(skip).limit(limit)
            
            session_docs = await cursor.to_list(length=limit)
            
            # Convert to ChatSession objects
            sessions = [ChatSession(**doc) for doc in session_docs]
            
            logger.debug(
                f"Retrieved {len(sessions)} sessions for user {user_id} "
                f"(type: {session_type}, active: {is_active})"
            )
            
            return sessions
            
        except Exception as e:
            logger.error(
                f"Failed to list sessions for user {user_id}: {e}",
                exc_info=True
            )
            return []
    
    async def update_session(
        self,
        session_id: str,
        update_data: Dict[str, Any]
    ) -> Optional[ChatSession]:
        """Update a chat session.
        
        Args:
            session_id: ID of the session to update
            update_data: Dictionary of fields to update
            
        Returns:
            Updated ChatSession if successful, None otherwise
        """
        try:
            # Add updated_at timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            # Update session
            result = await self.db.chat_sessions.update_one(
                {"id": session_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(
                    f"Updated session {session_id} with fields: {list(update_data.keys())}"
                )
                # Return updated session
                return await self.get_session(session_id)
            else:
                logger.warning(f"No session found to update: {session_id}")
                return None
            
        except Exception as e:
            logger.error(
                f"Failed to update session {session_id}: {e}",
                exc_info=True
            )
            return None
    
    async def get_messages(
        self,
        session_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> List[ChatMessage]:
        """Get paginated messages for session.
        
        Retrieves messages for a session with pagination support, ordered by
        creation time (oldest first).
        
        Args:
            session_id: ID of the session
            skip: Number of messages to skip (for pagination)
            limit: Maximum number of messages to return
            
        Returns:
            List of ChatMessage objects
        """
        try:
            messages = await self.db.chat_messages.find(
                {"session_id": session_id}
            ).sort("created_at", 1).skip(skip).limit(limit).to_list(None)
            
            return [ChatMessage(**msg) for msg in messages]
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve messages for session {session_id}: {e}",
                exc_info=True
            )
            return []
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session and all associated messages.
        
        Removes the session and all its messages from MongoDB. Also invalidates
        any cached conversation history in Redis.
        
        Args:
            session_id: ID of the session to delete
            
        Returns:
            bool: True if deletion was successful, False otherwise
        """
        try:
            # Delete all messages for the session
            messages_result = await self.db.chat_messages.delete_many(
                {"session_id": session_id}
            )
            
            # Delete the session
            session_result = await self.db.chat_sessions.delete_one(
                {"id": session_id}
            )
            
            # Invalidate conversation history cache
            await self.conversation_manager.invalidate_cache(session_id)
            
            logger.info(
                f"Deleted session {session_id} and {messages_result.deleted_count} messages"
            )
            
            return session_result.deleted_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}", exc_info=True)
            return False

    async def get_conversation_history(
        self,
        session_id: str,
        max_messages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get conversation history formatted for LLM.
        
        Retrieves recent conversation history from MongoDB (with Redis caching)
        and formats it for LLM consumption. Returns the last N messages ordered
        from oldest to newest.
        
        Args:
            session_id: ID of the session
            max_messages: Optional override for max history length.
                         If None, uses settings default (20).
            
        Returns:
            List of message dictionaries with 'role' and 'content' keys,
            formatted for LLM consumption (lowercase roles)
        """
        try:
            # Get history from conversation manager (handles caching)
            history = await self.conversation_manager.get_history(
                session_id=session_id,
                db=self.db
            )
            
            # Apply max_messages limit if specified
            if max_messages is not None and len(history) > max_messages:
                history = history[-max_messages:]
            
            # Format for LLM (ensure lowercase roles)
            formatted_history = self.conversation_manager.format_for_llm(history)
            
            # Log conversation history retrieval
            log_conversation_history(
                session_id=session_id,
                message_count=len(formatted_history),
                source="redis_or_mongodb"
            )
            
            logger.debug(
                f"Retrieved {len(formatted_history)} messages from history "
                f"for session {session_id}"
            )
            
            return formatted_history
            
        except Exception as e:
            logger.error(
                f"Failed to get conversation history for session {session_id}: {e}",
                exc_info=True
            )
            # Return empty history on error to allow conversation to continue
            return []

    async def stream_chat_response(
        self,
        session_id: str,
        user_id: str,
        message: ChatMessageCreate
    ) -> AsyncGenerator[Any, None]:
        """Stream chat response through appropriate workflow.
        
        This method orchestrates the complete chat flow:
        1. Save user message to MongoDB with PENDING status
        2. Load conversation history (last 20 messages)
        3. Initialize Ollama LLM with token tracking callback
        4. Call MasterWorkflowGraph.astream() with query, history, kb_id
        5. Yield tokens from graph execution
        6. Collect tokens for final assistant message
        7. Save assistant message with COMPLETED status
        8. Track token usage in TokenUsage collection
        9. Update session statistics
        10. Invalidate conversation history cache
        
        Args:
            session_id: ID of the chat session
            user_id: ID of the user sending the message
            message: Message creation data (content, state, model_id, kb_ids)
            
        Yields:
            Tokens from the LLM response, progress indicators, or metadata.
            Yields in the following formats:
            - str: Text tokens from the response
            - dict: Metadata (type: "start", "progress", "metadata", "error")
            
        Raises:
            Exception: If critical errors occur during streaming
        """
        user_message_id = None
        assistant_message_id = None
        collected_tokens = []
        stream_start_time = time.time()
        
        try:
            # Track message for metrics
            await self.metrics_tracker.track_message(session_id, user_id)
            
            # 1. Save user message to MongoDB with PENDING status
            user_message_id = str(uuid.uuid4())
            now = datetime.utcnow()
            
            user_message = ChatMessage(
                id=user_message_id,
                session_id=session_id,
                user_id=user_id,
                role=MessageRole.USER,
                content=message.content,
                status=MessageStatus.COMPLETED,  # User messages are immediately completed
                created_at=now,
                updated_at=now
            )
            
            await self.db.chat_messages.insert_one(user_message.model_dump())
            
            logger.info(
                f"Saved user message {user_message_id} for session {session_id}"
            )
            
            # 2. Load conversation history (last 20 messages)
            conversation_history = await self.get_conversation_history(session_id)
            
            logger.debug(
                f"Loaded {len(conversation_history)} messages from history "
                f"for session {session_id}"
            )
            
            # 3. Token tracking will be done manually by counting tokens in the response
            # (The graphs already have LLM instances initialized)
            
            # 4. Create assistant message with PENDING status
            assistant_message_id = str(uuid.uuid4())
            assistant_message = ChatMessage(
                id=assistant_message_id,
                session_id=session_id,
                user_id=user_id,  # System user or same user
                role=MessageRole.ASSISTANT,
                content="",  # Will be updated with final content
                status=MessageStatus.PENDING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            await self.db.chat_messages.insert_one(assistant_message.model_dump())
            
            # Yield message ID at start
            yield {"type": "start", "message_id": assistant_message_id}
            
            logger.info(
                f"Created assistant message {assistant_message_id} with PENDING status"
            )
            
            # 5. Determine knowledge base ID from message or session
            knowledge_base_id = message.vector_knowledge_base_id
            if not knowledge_base_id:
                # Try to get from session's knowledge_base_ids
                session = await self.get_session(session_id)
                if session and session.knowledge_base_ids:
                    knowledge_base_id = session.knowledge_base_ids[0]
            
            # 6. Call MasterWorkflowGraph.astream() and yield tokens
            async for chunk in self.master_workflow_graph.astream(
                question=message.content,
                conversation_history=conversation_history,
                knowledge_base_id=knowledge_base_id,
                session_id=session_id,
                user_id=user_id,
                state_override=message.state
            ):
                # Yield the chunk to the client
                yield chunk
                
                # Collect text tokens for final message
                if isinstance(chunk, str):
                    collected_tokens.append(chunk)
                elif isinstance(chunk, dict) and chunk.get("type") == "progress":
                    # Progress indicators don't need to be collected
                    pass
            
            # 7. Collect tokens for final assistant message
            final_content = "".join(collected_tokens) if collected_tokens else ""
            
            if not final_content:
                final_content = (
                    "I apologize, but I couldn't generate a response. "
                    "Please try again."
                )
            
            # 8. Save assistant message with COMPLETED status
            await self.db.chat_messages.update_one(
                {"id": assistant_message_id},
                {
                    "$set": {
                        "content": final_content,
                        "status": MessageStatus.COMPLETED,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(
                f"Updated assistant message {assistant_message_id} with COMPLETED status "
                f"({len(final_content)} chars)"
            )
            
            # 9. Track token usage in TokenUsage collection
            # Count tokens for prompt and completion
            prompt_tokens = self.ollama_manager.count_tokens(message.content)
            completion_tokens = self.ollama_manager.count_tokens(final_content)
            total_tokens = prompt_tokens + completion_tokens
            cost = self.ollama_manager.estimate_cost(
                prompt_tokens, completion_tokens, self.model_id
            )
            
            token_usage_id = str(uuid.uuid4())
            token_usage = TokenUsage(
                id=token_usage_id,
                message_id=assistant_message_id,
                session_id=session_id,
                endpoint=self.settings.OLLAMA_HOST,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost=cost,
                model=self.model_id,
                created_at=datetime.utcnow()
            )
            
            await self.db.token_usage.insert_one(token_usage.model_dump())
            
            # Log token usage
            log_token_usage(
                session_id=session_id,
                message_id=assistant_message_id,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                model=self.model_id,
                cost=cost
            )
            
            # Track token usage metrics
            await self.metrics_tracker.track_token_usage(
                session_id=session_id,
                user_id=user_id,
                total_tokens=total_tokens,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cost=cost
            )
            
            logger.debug(
                f"Tracked token usage: {total_tokens} tokens "
                f"(prompt: {prompt_tokens}, completion: {completion_tokens})"
            )
            
            # 10. Update session statistics
            await self.statistics_manager.update_session_statistics(session_id)
            
            # 11. Invalidate conversation history cache
            await self.conversation_manager.invalidate_cache(session_id)
            
            # Track response time metrics
            response_time = time.time() - stream_start_time
            await self.metrics_tracker.track_response_time(
                session_id=session_id,
                user_id=user_id,
                response_time=response_time
            )
            
            logger.info(
                f"Completed streaming response for session {session_id} "
                f"(message: {assistant_message_id}, time: {response_time:.3f}s)"
            )
            
        except Exception as e:
            # Error handling (subtask 17.5)
            
            # Track error metrics
            error_type = type(e).__name__
            await self.metrics_tracker.track_error(
                error_type=error_type,
                session_id=session_id,
                user_id=user_id
            )
            
            # Log streaming error with context
            log_streaming_error(
                session_id=session_id,
                error=e,
                context={
                    "user_id": user_id,
                    "message_id": assistant_message_id,
                    "user_message_id": user_message_id
                }
            )
            
            logger.error(
                f"Error streaming chat response for session {session_id}: {e}",
                exc_info=True
            )
            
            # Update assistant message status to FAILED if it was created
            if assistant_message_id:
                try:
                    await self.db.chat_messages.update_one(
                        {"id": assistant_message_id},
                        {
                            "$set": {
                                "status": MessageStatus.FAILED,
                                "content": (
                                    "I apologize, but an error occurred while "
                                    "generating the response. Please try again."
                                ),
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    logger.info(f"Updated message {assistant_message_id} to FAILED status")
                except Exception as update_error:
                    logger.error(
                        f"Failed to update message status to FAILED: {update_error}"
                    )
            
            # Yield error message to client
            yield {
                "type": "error",
                "message": f"An error occurred: {str(e)}"
            }
            
            # Re-raise the exception for higher-level handling
            raise
