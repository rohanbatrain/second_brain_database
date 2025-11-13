"""Logging utilities for chat components.

This module provides specialized logging utilities for chat operations including:
- Execution time tracking for graph nodes
- Token usage logging
- Streaming error logging with stack traces
- Structured logging for monitoring and observability

Requirements: Monitoring from design (task 24.1)
"""

import functools
import time
from typing import Any, Callable, Dict, Optional

from second_brain_database.managers.logging_manager import get_logger

# Get logger for chat components
chat_logger = get_logger("Second_Brain_Database.Chat")


def log_execution_time(node_name: str):
    """Decorator to log execution time for graph nodes.
    
    This decorator wraps graph node functions and logs their execution time
    along with success/failure status. It's designed for use with LangGraph nodes.
    
    Args:
        node_name: Name of the graph node for logging identification
        
    Returns:
        Decorator function that wraps the node function
        
    Example:
        @log_execution_time("retrieve_contexts")
        async def retrieve_contexts(self, state: GraphState) -> GraphState:
            # Node implementation
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            # Extract session_id from state if available
            session_id = "unknown"
            if args and len(args) > 1:
                state = args[1]
                if hasattr(state, "session_id"):
                    session_id = state.session_id
                elif isinstance(state, dict) and "session_id" in state:
                    session_id = state["session_id"]
            
            chat_logger.info(
                f"[{node_name}] Starting execution for session {session_id}"
            )
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Check if execution was successful
                success = True
                if hasattr(result, "success"):
                    success = result.success
                elif isinstance(result, dict) and "success" in result:
                    success = result["success"]
                
                status = "SUCCESS" if success else "FAILED"
                
                chat_logger.info(
                    f"[{node_name}] Completed execution for session {session_id} "
                    f"- Status: {status}, Time: {execution_time:.3f}s"
                )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                
                chat_logger.error(
                    f"[{node_name}] Execution failed for session {session_id} "
                    f"after {execution_time:.3f}s: {str(e)}",
                    exc_info=True
                )
                raise
        
        return wrapper
    return decorator


def log_token_usage(
    session_id: str,
    message_id: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    model: str,
    cost: float = 0.0
):
    """Log token usage for a chat request.
    
    This function logs detailed token usage information for monitoring and
    cost tracking purposes. It's called after each chat response is generated.
    
    Args:
        session_id: ID of the chat session
        message_id: ID of the message
        prompt_tokens: Number of tokens in the prompt
        completion_tokens: Number of tokens in the completion
        total_tokens: Total number of tokens used
        model: Model name used for generation
        cost: Estimated cost (0.0 for Ollama)
    """
    chat_logger.info(
        f"[TokenUsage] Session: {session_id}, Message: {message_id}, "
        f"Model: {model}, Tokens: {total_tokens} "
        f"(prompt: {prompt_tokens}, completion: {completion_tokens}), "
        f"Cost: ${cost:.4f}"
    )


def log_streaming_error(
    session_id: str,
    error: Exception,
    context: Optional[Dict[str, Any]] = None
):
    """Log streaming errors with full stack traces.
    
    This function logs streaming errors with comprehensive context information
    including session details, error type, and full stack trace for debugging.
    
    Args:
        session_id: ID of the chat session where error occurred
        error: Exception that was raised
        context: Optional dictionary with additional context (user_id, message_id, etc.)
    """
    context_str = ""
    if context:
        context_items = [f"{k}={v}" for k, v in context.items()]
        context_str = f", Context: {', '.join(context_items)}"
    
    chat_logger.error(
        f"[StreamingError] Session: {session_id}, "
        f"Error: {type(error).__name__}: {str(error)}{context_str}",
        exc_info=True
    )


def log_graph_execution(
    graph_name: str,
    session_id: str,
    question: str,
    execution_time: float,
    success: bool,
    error: Optional[str] = None
):
    """Log complete graph execution summary.
    
    This function logs a summary of graph execution including timing, success
    status, and any errors that occurred. It's called after graph execution completes.
    
    Args:
        graph_name: Name of the graph (VectorRAG, GeneralResponse, MasterWorkflow)
        session_id: ID of the chat session
        question: User's question (truncated for logging)
        execution_time: Total execution time in seconds
        success: Whether execution was successful
        error: Optional error message if execution failed
    """
    # Truncate question for logging
    question_preview = question[:100] + "..." if len(question) > 100 else question
    
    status = "SUCCESS" if success else "FAILED"
    error_str = f", Error: {error}" if error else ""
    
    chat_logger.info(
        f"[{graph_name}] Execution completed for session {session_id} "
        f"- Status: {status}, Time: {execution_time:.3f}s, "
        f"Question: '{question_preview}'{error_str}"
    )


def log_cache_operation(
    operation: str,
    session_id: str,
    cache_key: Optional[str] = None,
    hit: Optional[bool] = None,
    ttl: Optional[int] = None
):
    """Log cache operations (hit, miss, store).
    
    This function logs cache operations for monitoring cache effectiveness
    and debugging cache-related issues.
    
    Args:
        operation: Type of operation (check, hit, miss, store, invalidate)
        session_id: ID of the chat session
        cache_key: Optional cache key (hashed)
        hit: Optional boolean indicating cache hit/miss
        ttl: Optional TTL value for cache storage
    """
    details = []
    if cache_key:
        details.append(f"Key: {cache_key[:16]}...")
    if hit is not None:
        details.append(f"Hit: {hit}")
    if ttl is not None:
        details.append(f"TTL: {ttl}s")
    
    details_str = ", ".join(details) if details else "No details"
    
    chat_logger.debug(
        f"[Cache] Operation: {operation}, Session: {session_id}, {details_str}"
    )


def log_conversation_history(
    session_id: str,
    message_count: int,
    source: str = "mongodb"
):
    """Log conversation history retrieval.
    
    This function logs when conversation history is loaded, including the
    number of messages and the source (MongoDB or Redis cache).
    
    Args:
        session_id: ID of the chat session
        message_count: Number of messages retrieved
        source: Source of the history (mongodb, redis)
    """
    chat_logger.debug(
        f"[ConversationHistory] Session: {session_id}, "
        f"Messages: {message_count}, Source: {source}"
    )


def log_session_operation(
    operation: str,
    session_id: str,
    user_id: str,
    session_type: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
):
    """Log session management operations.
    
    This function logs session operations like create, update, delete for
    audit trail and monitoring purposes.
    
    Args:
        operation: Type of operation (create, update, delete, get)
        session_id: ID of the chat session
        user_id: ID of the user performing the operation
        session_type: Optional session type (GENERAL, VECTOR, SQL)
        details: Optional dictionary with additional details
    """
    details_str = ""
    if session_type:
        details_str += f", Type: {session_type}"
    if details:
        detail_items = [f"{k}={v}" for k, v in details.items()]
        details_str += f", {', '.join(detail_items)}"
    
    chat_logger.info(
        f"[Session] Operation: {operation}, Session: {session_id}, "
        f"User: {user_id}{details_str}"
    )


def log_rate_limit_check(
    user_id: str,
    limit_type: str,
    allowed: bool,
    remaining: Optional[int] = None,
    reset_in: Optional[int] = None
):
    """Log rate limit checks.
    
    This function logs rate limit checks for monitoring abuse and understanding
    usage patterns.
    
    Args:
        user_id: ID of the user being checked
        limit_type: Type of limit (message, session_create)
        allowed: Whether the request was allowed
        remaining: Optional remaining quota
        reset_in: Optional seconds until reset
    """
    status = "ALLOWED" if allowed else "BLOCKED"
    details = []
    if remaining is not None:
        details.append(f"Remaining: {remaining}")
    if reset_in is not None:
        details.append(f"Reset in: {reset_in}s")
    
    details_str = ", ".join(details) if details else ""
    
    log_level = "warning" if not allowed else "debug"
    log_func = getattr(chat_logger, log_level)
    
    log_func(
        f"[RateLimit] User: {user_id}, Type: {limit_type}, "
        f"Status: {status}{', ' + details_str if details_str else ''}"
    )


def log_vector_search(
    session_id: str,
    knowledge_base_id: str,
    query: str,
    chunks_found: int,
    execution_time: float,
    success: bool
):
    """Log vector search operations.
    
    This function logs vector search operations including query details,
    results count, and execution time for performance monitoring.
    
    Args:
        session_id: ID of the chat session
        knowledge_base_id: ID of the knowledge base searched
        query: Search query (truncated)
        chunks_found: Number of chunks retrieved
        execution_time: Execution time in seconds
        success: Whether search was successful
    """
    query_preview = query[:100] + "..." if len(query) > 100 else query
    status = "SUCCESS" if success else "FAILED"
    
    chat_logger.info(
        f"[VectorSearch] Session: {session_id}, KB: {knowledge_base_id}, "
        f"Status: {status}, Chunks: {chunks_found}, Time: {execution_time:.3f}s, "
        f"Query: '{query_preview}'"
    )
