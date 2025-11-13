"""
Chat API routes for LangGraph-based chat system.

This module provides FastAPI routes for chat session management, message streaming,
voting, token usage tracking, and health checks.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from second_brain_database.chat.models.enums import ChatSessionType, VoteType
from second_brain_database.chat.models.request_models import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionCreate,
    ChatSessionResponse,
    MessageVoteCreate,
    TokenUsageSummaryResponse,
)
from second_brain_database.chat.services.chat_service import ChatService
from second_brain_database.chat.services.statistics_manager import SessionStatisticsManager
from second_brain_database.chat.services.vote_manager import MessageVoteManager
from second_brain_database.chat.utils.input_sanitizer import InputSanitizer
from second_brain_database.chat.utils.rate_limiter import ChatRateLimiter
from second_brain_database.chat.utils.stream_processor import StreamProcessor
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_error_with_context,
    request_id_context,
    user_id_context,
)

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = get_logger(prefix="[CHAT]")


# Dependency functions
async def get_chat_service() -> ChatService:
    """Get ChatService instance with database connection."""
    db = db_manager.get_database()
    redis_client = redis_manager.get_client()
    return ChatService(db=db, redis_client=redis_client)


async def get_rate_limiter() -> ChatRateLimiter:
    """Get ChatRateLimiter instance with Redis connection."""
    return ChatRateLimiter(redis_manager=redis_manager)


async def get_statistics_manager() -> SessionStatisticsManager:
    """Get SessionStatisticsManager instance with database connection."""
    db = db_manager.get_database()
    return SessionStatisticsManager(db=db)


async def get_vote_manager() -> MessageVoteManager:
    """Get MessageVoteManager instance with database connection."""
    db = db_manager.get_database()
    return MessageVoteManager(db=db)


# Helper function for request logging
def setup_request_context(request: Request, current_user: dict) -> str:
    """Setup logging context for request."""
    request_id = str(datetime.now(timezone.utc).timestamp()).replace(".", "")[-8:]
    client_ip = security_manager.get_client_ip(request)
    username = current_user["username"]

    request_id_context.set(request_id)
    user_id_context.set(username)
    ip_address_context.set(client_ip)

    return request_id



# Session Management Endpoints


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
    description="""
    Create a new chat session for the authenticated user.
    
    **Session Types:**
    - `GENERAL`: General conversational chat with AI assistant
    - `VECTOR`: Vector RAG chat with document knowledge bases
    - `SQL`: SQL query generation (Phase 2 - not yet implemented)
    
    **Rate Limiting:**
    - Maximum 5 sessions per hour per user
    - Returns 429 Too Many Requests if limit exceeded
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - Format: `Bearer <token>`
    """,
    responses={
        201: {
            "description": "Session created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_id": "507f1f77bcf86cd799439011",
                        "session_type": "GENERAL",
                        "title": "New Chat",
                        "message_count": 0,
                        "total_tokens": 0,
                        "total_cost": 0.0,
                        "last_message_at": None,
                        "knowledge_base_ids": [],
                        "created_at": "2024-01-15T10:30:00Z",
                        "updated_at": "2024-01-15T10:30:00Z",
                        "is_active": True
                    }
                }
            }
        },
        400: {
            "description": "Invalid session data",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid knowledge base ID format: invalid-kb-123"}
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {"detail": "Session creation rate limit exceeded. Resets in 3600 seconds."}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to create chat session"}
                }
            }
        }
    }
)
async def create_chat_session(
    request: Request,
    session_data: ChatSessionCreate = Body(
        ...,
        example={
            "session_type": "GENERAL",
            "title": "My Chat Session",
            "knowledge_base_ids": []
        }
    ),
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    rate_limiter: ChatRateLimiter = Depends(get_rate_limiter),
):
    """
    Create a new chat session.

    Args:
        request: FastAPI request object
        session_data: Session creation data (type, title, knowledge_base_ids)
        current_user: Authenticated user from JWT
        chat_service: ChatService instance
        rate_limiter: Rate limiter instance

    Returns:
        ChatSessionResponse: Created session with metadata

    Raises:
        HTTPException 429: Rate limit exceeded (5 sessions per hour)
        HTTPException 400: Invalid session data
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] POST /chat/sessions - User: %s, Type: %s",
        request_id,
        username,
        session_data.session_type,
    )

    try:
        # Check rate limit
        if not await rate_limiter.check_session_create_rate_limit(user_id):
            quota = await rate_limiter.get_remaining_quota(user_id, "session")
            logger.warning(
                "[%s] Session creation rate limit exceeded for user: %s",
                request_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Session creation rate limit exceeded. Resets in {quota['reset_in_seconds']} seconds.",
            )

        # Validate knowledge base IDs if provided
        if session_data.knowledge_base_ids:
            for kb_id in session_data.knowledge_base_ids:
                if not InputSanitizer.validate_knowledge_base_id(kb_id):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid knowledge base ID format: {kb_id}",
                    )

        # Create session
        session = await chat_service.create_session(user_id=user_id, session_data=session_data)

        logger.info(
            "[%s] Chat session created - ID: %s, User: %s, Type: %s",
            request_id,
            session.id,
            username,
            session.session_type,
        )

        return session

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to create chat session for user: %s, Error: %s",
            request_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id},
            operation="create_chat_session",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create chat session",
        )


@router.get(
    "/sessions",
    response_model=List[ChatSessionResponse],
    summary="List chat sessions",
    description="""
    Retrieve a paginated list of chat sessions for the authenticated user.
    
    **Filtering:**
    - Filter by session type (GENERAL, VECTOR, SQL)
    - Filter by active status (active or archived sessions)
    
    **Pagination:**
    - Use `skip` and `limit` parameters for pagination
    - Maximum limit: 100 sessions per request
    - Default limit: 50 sessions
    
    **Sorting:**
    - Sessions are sorted by `created_at` in descending order (newest first)
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    """,
    responses={
        200: {
            "description": "List of chat sessions",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "user_id": "507f1f77bcf86cd799439011",
                            "session_type": "GENERAL",
                            "title": "My Chat Session",
                            "message_count": 5,
                            "total_tokens": 1250,
                            "total_cost": 0.0,
                            "last_message_at": "2024-01-15T10:35:00Z",
                            "knowledge_base_ids": [],
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T10:35:00Z",
                            "is_active": True
                        },
                        {
                            "id": "660e8400-e29b-41d4-a716-446655440001",
                            "user_id": "507f1f77bcf86cd799439011",
                            "session_type": "VECTOR",
                            "title": "Document Q&A",
                            "message_count": 3,
                            "total_tokens": 850,
                            "total_cost": 0.0,
                            "last_message_at": "2024-01-14T15:20:00Z",
                            "knowledge_base_ids": ["kb_abc123"],
                            "created_at": "2024-01-14T15:00:00Z",
                            "updated_at": "2024-01-14T15:20:00Z",
                            "is_active": True
                        }
                    ]
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to retrieve chat sessions"}
                }
            }
        }
    }
)
async def list_chat_sessions(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    session_type: Optional[ChatSessionType] = Query(None, description="Filter by session type (GENERAL, VECTOR, SQL)"),
    is_active: Optional[bool] = Query(True, description="Filter by active status (default: True)"),
    skip: int = Query(0, ge=0, description="Number of sessions to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of sessions to return (max: 100)"),
):
    """
    List chat sessions for the authenticated user.

    Args:
        request: FastAPI request object
        current_user: Authenticated user from JWT
        chat_service: ChatService instance
        session_type: Optional filter by session type (GENERAL, VECTOR, SQL)
        is_active: Filter by active status (default: True)
        skip: Pagination offset
        limit: Maximum results per page

    Returns:
        List[ChatSessionResponse]: List of chat sessions

    Raises:
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] GET /chat/sessions - User: %s, Type: %s, Active: %s",
        request_id,
        username,
        session_type,
        is_active,
    )

    try:
        sessions = await chat_service.list_sessions(
            user_id=user_id,
            session_type=session_type,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )

        logger.info(
            "[%s] Retrieved %d chat sessions for user: %s",
            request_id,
            len(sessions),
            username,
        )

        return sessions

    except Exception as e:
        logger.error(
            "[%s] Failed to list chat sessions for user: %s, Error: %s",
            request_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id},
            operation="list_chat_sessions",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat sessions",
        )


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    summary="Get a chat session",
    description="""
    Retrieve a specific chat session with updated statistics.
    
    **Statistics Included:**
    - Message count
    - Total tokens consumed
    - Total cost (currently $0.00 for Ollama)
    - Last message timestamp
    - Session creation and update times
    
    **Statistics Update:**
    - Statistics are automatically recalculated when retrieving the session
    - Ensures up-to-date token usage and message counts
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - User must own the session (403 Forbidden if not)
    """,
    responses={
        200: {
            "description": "Chat session with statistics",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_id": "507f1f77bcf86cd799439011",
                        "session_type": "VECTOR",
                        "title": "Document Q&A Session",
                        "message_count": 8,
                        "total_tokens": 2450,
                        "total_cost": 0.0,
                        "last_message_at": "2024-01-15T10:35:00Z",
                        "knowledge_base_ids": ["kb_abc123", "kb_def456"],
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:35:00Z",
                        "is_active": True
                    }
                }
            }
        },
        400: {
            "description": "Invalid session ID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid session ID format"}
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        403: {
            "description": "Not authorized to access this session",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authorized to access this session"}
                }
            }
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Session not found"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to retrieve chat session"}
                }
            }
        }
    }
)
async def get_chat_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    statistics_manager: SessionStatisticsManager = Depends(get_statistics_manager),
):
    """
    Get a specific chat session with statistics.

    Args:
        request: FastAPI request object
        session_id: Session UUID
        current_user: Authenticated user from JWT
        chat_service: ChatService instance
        statistics_manager: Statistics manager instance

    Returns:
        ChatSessionResponse: Session with updated statistics

    Raises:
        HTTPException 400: Invalid session ID format
        HTTPException 404: Session not found
        HTTPException 403: Not authorized to access session
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] GET /chat/sessions/%s - User: %s",
        request_id,
        session_id,
        username,
    )

    try:
        # Validate session ID format
        if not InputSanitizer.validate_session_id(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format",
            )

        # Get session
        session = await chat_service.get_session(session_id=session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Verify ownership
        if session.user_id != user_id:
            logger.warning(
                "[%s] Unauthorized access attempt to session %s by user: %s",
                request_id,
                session_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this session",
            )

        # Update statistics
        await statistics_manager.update_session_statistics(session_id)

        # Reload session with updated stats
        session = await chat_service.get_session(session_id=session_id)

        logger.info(
            "[%s] Retrieved chat session %s for user: %s",
            request_id,
            session_id,
            username,
        )

        return session

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to get chat session %s for user: %s, Error: %s",
            request_id,
            session_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "session_id": session_id, "request_id": request_id},
            operation="get_chat_session",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat session",
        )


@router.patch(
    "/sessions/{session_id}",
    response_model=ChatSessionResponse,
    summary="Update a chat session",
    description="""
    Update properties of a chat session.
    
    **Updatable Fields:**
    - `title`: Session title (max 200 characters)
    - More fields may be added in future versions
    
    **Title Validation:**
    - Must be a string
    - Maximum length: 200 characters
    - Automatically sanitized (whitespace trimmed, unicode normalized)
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - User must own the session (403 Forbidden if not)
    """,
    responses={
        200: {
            "description": "Session updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "user_id": "507f1f77bcf86cd799439011",
                        "session_type": "GENERAL",
                        "title": "Updated Session Title",
                        "message_count": 5,
                        "total_tokens": 1250,
                        "total_cost": 0.0,
                        "last_message_at": "2024-01-15T10:35:00Z",
                        "knowledge_base_ids": [],
                        "created_at": "2024-01-15T10:00:00Z",
                        "updated_at": "2024-01-15T10:40:00Z",
                        "is_active": True
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_session_id": {
                            "summary": "Invalid session ID format",
                            "value": {"detail": "Invalid session ID format"}
                        },
                        "invalid_title_type": {
                            "summary": "Title must be a string",
                            "value": {"detail": "Title must be a string"}
                        },
                        "title_too_long": {
                            "summary": "Title exceeds maximum length",
                            "value": {"detail": "Title must be 200 characters or less"}
                        }
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        403: {
            "description": "Not authorized to update this session",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authorized to update this session"}
                }
            }
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Session not found"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to update chat session"}
                }
            }
        }
    }
)
async def update_chat_session(
    request: Request,
    session_id: str,
    update_data: dict = Body(
        ...,
        example={"title": "My Updated Session Title"}
    ),
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Update a chat session (currently supports title updates).

    Args:
        request: FastAPI request object
        session_id: Session UUID
        update_data: Fields to update (e.g., {"title": "New Title"})
        current_user: Authenticated user from JWT
        chat_service: ChatService instance

    Returns:
        ChatSessionResponse: Updated session

    Raises:
        HTTPException 400: Invalid session ID or update data
        HTTPException 404: Session not found
        HTTPException 403: Not authorized to update session
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] PATCH /chat/sessions/%s - User: %s, Updates: %s",
        request_id,
        session_id,
        username,
        list(update_data.keys()),
    )

    try:
        # Validate session ID format
        if not InputSanitizer.validate_session_id(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format",
            )

        # Get session to verify ownership
        session = await chat_service.get_session(session_id=session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Verify ownership
        if session.user_id != user_id:
            logger.warning(
                "[%s] Unauthorized update attempt to session %s by user: %s",
                request_id,
                session_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this session",
            )

        # Validate and sanitize title if provided
        if "title" in update_data:
            title = update_data["title"]
            if not isinstance(title, str):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Title must be a string",
                )
            if len(title) > 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Title must be 200 characters or less",
                )
            update_data["title"] = InputSanitizer.sanitize_message_content(title)

        # Update session
        updated_session = await chat_service.update_session(
            session_id=session_id,
            update_data=update_data,
        )

        logger.info(
            "[%s] Updated chat session %s for user: %s",
            request_id,
            session_id,
            username,
        )

        return updated_session

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to update chat session %s for user: %s, Error: %s",
            request_id,
            session_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "session_id": session_id, "request_id": request_id},
            operation="update_chat_session",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chat session",
        )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat session",
    description="""
    Permanently delete a chat session and all associated data.
    
    **Deleted Data:**
    - Chat session record
    - All messages in the session
    - Token usage records
    - Message votes
    - Conversation history cache
    
    **Warning:**
    - This operation is irreversible
    - All data associated with the session will be permanently deleted
    - Consider archiving sessions instead of deleting them
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - User must own the session (403 Forbidden if not)
    """,
    responses={
        204: {
            "description": "Session deleted successfully (no content returned)"
        },
        400: {
            "description": "Invalid session ID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid session ID format"}
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        403: {
            "description": "Not authorized to delete this session",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authorized to delete this session"}
                }
            }
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Session not found"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to delete chat session"}
                }
            }
        }
    }
)
async def delete_chat_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Delete a chat session and all associated messages.

    Args:
        request: FastAPI request object
        session_id: Session UUID
        current_user: Authenticated user from JWT
        chat_service: ChatService instance

    Returns:
        204 No Content on success

    Raises:
        HTTPException 400: Invalid session ID format
        HTTPException 404: Session not found
        HTTPException 403: Not authorized to delete session
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] DELETE /chat/sessions/%s - User: %s",
        request_id,
        session_id,
        username,
    )

    try:
        # Validate session ID format
        if not InputSanitizer.validate_session_id(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format",
            )

        # Get session to verify ownership
        session = await chat_service.get_session(session_id=session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Verify ownership
        if session.user_id != user_id:
            logger.warning(
                "[%s] Unauthorized delete attempt to session %s by user: %s",
                request_id,
                session_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this session",
            )

        # Delete session
        await chat_service.delete_session(session_id=session_id)

        logger.info(
            "[%s] Deleted chat session %s for user: %s",
            request_id,
            session_id,
            username,
        )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to delete chat session %s for user: %s, Error: %s",
            request_id,
            session_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "session_id": session_id, "request_id": request_id},
            operation="delete_chat_session",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat session",
        )



# Message Endpoints


@router.post(
    "/sessions/{session_id}/messages",
    summary="Send a chat message",
    description="""
    Send a message to a chat session and receive a streaming AI response.
    
    **Streaming Protocol:**
    This endpoint returns a streaming response using the AI SDK Data Stream Protocol:
    - `0:` - Text tokens (streaming response content)
    - `2:` - Metadata (message_id, session info)
    - `g:` - Progress indicators (e.g., "Searching vector database...")
    - `e:` - Completion/error markers with finish reason
    
    **Message Processing:**
    1. User message is saved to database
    2. Conversation history (last 20 messages) is loaded
    3. Message is routed to appropriate workflow (Vector RAG or General Chat)
    4. AI response is streamed back in real-time
    5. Assistant message is saved with token usage tracking
    
    **Rate Limiting:**
    - Maximum 20 messages per minute per user
    - Returns 429 Too Many Requests if limit exceeded
    
    **Content Limits:**
    - Maximum message length: 50,000 characters
    - Content is automatically sanitized (whitespace, unicode normalization)
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - User must own the session
    """,
    responses={
        200: {
            "description": "Streaming response in AI SDK Data Stream Protocol format",
            "content": {
                "text/event-stream": {
                    "example": """0:"Hello"
0:" there"
0:"!"
2:[{"message_id":"550e8400-e29b-41d4-a716-446655440000"}]
e:{"finishReason":"stop","usage":null,"isContinued":false}"""
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_session_id": {
                            "summary": "Invalid session ID format",
                            "value": {"detail": "Invalid session ID format"}
                        },
                        "message_too_long": {
                            "summary": "Message exceeds length limit",
                            "value": {"detail": "Message content exceeds maximum length of 50000 characters"}
                        },
                        "invalid_kb_id": {
                            "summary": "Invalid knowledge base ID",
                            "value": {"detail": "Invalid knowledge base ID format"}
                        }
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        403: {
            "description": "Not authorized to access this session",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authorized to send messages to this session"}
                }
            }
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Session not found"}
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {"detail": "Message rate limit exceeded. Resets in 45 seconds."}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to process chat message"}
                }
            }
        }
    }
)
async def create_chat_message(
    request: Request,
    session_id: str,
    message: ChatMessageCreate = Body(
        ...,
        example={
            "content": "What is the capital of France?",
            "state": None,
            "model_id": None,
            "web_search_enabled": False,
            "structured_knowledge_base_id": None,
            "vector_knowledge_base_id": None
        }
    ),
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    rate_limiter: ChatRateLimiter = Depends(get_rate_limiter),
):
    """
    Send a message to a chat session and receive streaming response.

    This endpoint returns a streaming response in AI SDK Data Stream Protocol format.
    The stream includes:
    - Text tokens (0: prefix)
    - Metadata like message_id (2: prefix)
    - Progress indicators (g: prefix)
    - Completion/error markers (e: prefix)

    Args:
        request: FastAPI request object
        session_id: Session UUID
        message: Message content and optional parameters
        current_user: Authenticated user from JWT
        chat_service: ChatService instance
        rate_limiter: Rate limiter instance

    Returns:
        StreamingResponse: AI SDK protocol formatted stream

    Raises:
        HTTPException 400: Invalid session ID or message content
        HTTPException 404: Session not found
        HTTPException 403: Not authorized to access session
        HTTPException 429: Rate limit exceeded (20 messages per minute)
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] POST /chat/sessions/%s/messages - User: %s, Content length: %d",
        request_id,
        session_id,
        username,
        len(message.content),
    )

    try:
        # Validate session ID format
        if not InputSanitizer.validate_session_id(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format",
            )

        # Check rate limit
        if not await rate_limiter.check_message_rate_limit(user_id):
            quota = await rate_limiter.get_remaining_quota(user_id, "message")
            logger.warning(
                "[%s] Message rate limit exceeded for user: %s",
                request_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Message rate limit exceeded. Resets in {quota['reset_in_seconds']} seconds.",
            )

        # Get session to verify ownership
        session = await chat_service.get_session(session_id=session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Verify ownership
        if session.user_id != user_id:
            logger.warning(
                "[%s] Unauthorized message attempt to session %s by user: %s",
                request_id,
                session_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to send messages to this session",
            )

        # Sanitize message content
        try:
            sanitized_content = InputSanitizer.sanitize_message_content(message.content)
            message.content = sanitized_content
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        # Validate knowledge base ID if provided
        if message.vector_knowledge_base_id:
            if not InputSanitizer.validate_knowledge_base_id(message.vector_knowledge_base_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid knowledge base ID format",
                )

        logger.info(
            "[%s] Starting streaming response for session %s, user: %s",
            request_id,
            session_id,
            username,
        )

        # Stream chat response
        async def generate_stream():
            """Generate streaming response with AI SDK protocol formatting."""
            try:
                # Get raw stream from chat service
                raw_stream = chat_service.stream_chat_response(
                    session_id=session_id,
                    user_id=user_id,
                    message=message,
                )

                # Format stream with AI SDK protocol
                async for chunk in StreamProcessor.format_stream(raw_stream):
                    yield chunk

            except Exception as e:
                logger.error(
                    "[%s] Streaming error for session %s: %s",
                    request_id,
                    session_id,
                    str(e),
                )
                # Yield error in AI SDK format
                import json

                error_chunk = f'e:{{"finishReason":"error","error":{json.dumps(str(e))}}}\n'
                yield error_chunk

        # Create streaming response with special headers
        response = StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
        )

        # Add AI SDK protocol headers
        response = StreamProcessor.add_special_headers(response)

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to create chat message for session %s, user: %s, Error: %s",
            request_id,
            session_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "session_id": session_id, "request_id": request_id},
            operation="create_chat_message",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message",
        )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=List[ChatMessageResponse],
    summary="Get chat messages",
    description="""
    Retrieve messages for a chat session with pagination.
    
    **Message Ordering:**
    - Messages are ordered by creation time (oldest first)
    - Use pagination to load messages in chunks
    
    **Pagination:**
    - Use `skip` parameter to offset results
    - Use `limit` parameter to control page size (max: 100)
    - Default limit: 50 messages
    
    **Message Content:**
    - Includes user and assistant messages
    - Includes token usage information
    - Includes message status (PENDING, COMPLETED, FAILED)
    - Includes tool invocations and SQL queries (if applicable)
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - User must own the session (403 Forbidden if not)
    """,
    responses={
        200: {
            "description": "List of chat messages",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "660e8400-e29b-41d4-a716-446655440001",
                            "session_id": "550e8400-e29b-41d4-a716-446655440000",
                            "user_id": "507f1f77bcf86cd799439011",
                            "role": "USER",
                            "content": "What is the capital of France?",
                            "status": "COMPLETED",
                            "tool_invocations": [],
                            "sql_queries": [],
                            "token_usage": {
                                "prompt_tokens": 25,
                                "completion_tokens": 0,
                                "total_tokens": 25
                            },
                            "created_at": "2024-01-15T10:30:00Z",
                            "updated_at": "2024-01-15T10:30:00Z"
                        },
                        {
                            "id": "770e8400-e29b-41d4-a716-446655440002",
                            "session_id": "550e8400-e29b-41d4-a716-446655440000",
                            "user_id": "507f1f77bcf86cd799439011",
                            "role": "ASSISTANT",
                            "content": "The capital of France is Paris.",
                            "status": "COMPLETED",
                            "tool_invocations": [],
                            "sql_queries": [],
                            "token_usage": {
                                "prompt_tokens": 25,
                                "completion_tokens": 12,
                                "total_tokens": 37
                            },
                            "created_at": "2024-01-15T10:30:05Z",
                            "updated_at": "2024-01-15T10:30:05Z"
                        }
                    ]
                }
            }
        },
        400: {
            "description": "Invalid session ID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid session ID format"}
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        403: {
            "description": "Not authorized to access messages for this session",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authorized to access messages for this session"}
                }
            }
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Session not found"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to retrieve chat messages"}
                }
            }
        }
    }
)
async def get_chat_messages(
    request: Request,
    session_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    skip: int = Query(0, ge=0, description="Number of messages to skip for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of messages to return (max: 100)"),
):
    """
    Get messages for a chat session with pagination.

    Args:
        request: FastAPI request object
        session_id: Session UUID
        current_user: Authenticated user from JWT
        chat_service: ChatService instance
        skip: Pagination offset
        limit: Maximum results per page

    Returns:
        List[ChatMessageResponse]: List of messages ordered by creation time

    Raises:
        HTTPException 400: Invalid session ID format
        HTTPException 404: Session not found
        HTTPException 403: Not authorized to access session
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] GET /chat/sessions/%s/messages - User: %s, Skip: %d, Limit: %d",
        request_id,
        session_id,
        username,
        skip,
        limit,
    )

    try:
        # Validate session ID format
        if not InputSanitizer.validate_session_id(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format",
            )

        # Get session to verify ownership
        session = await chat_service.get_session(session_id=session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Verify ownership
        if session.user_id != user_id:
            logger.warning(
                "[%s] Unauthorized access attempt to messages for session %s by user: %s",
                request_id,
                session_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access messages for this session",
            )

        # Get messages
        messages = await chat_service.get_messages(
            session_id=session_id,
            skip=skip,
            limit=limit,
        )

        logger.info(
            "[%s] Retrieved %d messages for session %s, user: %s",
            request_id,
            len(messages),
            session_id,
            username,
        )

        return messages

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to get messages for session %s, user: %s, Error: %s",
            request_id,
            session_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "session_id": session_id, "request_id": request_id},
            operation="get_chat_messages",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat messages",
        )



# Voting Endpoints


@router.patch(
    "/sessions/{session_id}/messages/{message_id}/vote",
    summary="Vote on a message",
    description="""
    Provide feedback on an AI assistant message by voting thumbs up or down.
    
    **Vote Types:**
    - `up`: Positive feedback (thumbs up)
    - `down`: Negative feedback (thumbs down)
    
    **Vote Behavior:**
    - If user has already voted, the vote is updated
    - Only one vote per user per message
    - Votes are stored for future model improvement
    
    **Use Cases:**
    - Collect user feedback on response quality
    - Identify problematic responses
    - Track model performance over time
    - Train future models with RLHF (Reinforcement Learning from Human Feedback)
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - User must have access to the session
    """,
    responses={
        200: {
            "description": "Vote recorded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Vote recorded successfully",
                        "vote_type": "up",
                        "message_id": "770e8400-e29b-41d4-a716-446655440002",
                        "updated": False
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_session_id": {
                            "summary": "Invalid session ID format",
                            "value": {"detail": "Invalid session ID format"}
                        },
                        "invalid_message_id": {
                            "summary": "Invalid message ID format",
                            "value": {"detail": "Invalid message ID format"}
                        }
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        403: {
            "description": "Not authorized to vote on messages in this session",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authorized to vote on messages in this session"}
                }
            }
        },
        404: {
            "description": "Session or message not found",
            "content": {
                "application/json": {
                    "examples": {
                        "session_not_found": {
                            "summary": "Session not found",
                            "value": {"detail": "Session not found"}
                        },
                        "message_not_found": {
                            "summary": "Message not found in session",
                            "value": {"detail": "Message not found in this session"}
                        }
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to record vote"}
                }
            }
        }
    }
)
async def vote_on_message(
    request: Request,
    session_id: str,
    message_id: str,
    vote_data: MessageVoteCreate = Body(
        ...,
        example={"vote_type": "up"}
    ),
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    vote_manager: MessageVoteManager = Depends(get_vote_manager),
):
    """
    Vote on a message (thumbs up or down).

    Args:
        request: FastAPI request object
        session_id: Session UUID
        message_id: Message UUID
        vote_data: Vote type (up or down)
        current_user: Authenticated user from JWT
        chat_service: ChatService instance
        vote_manager: Vote manager instance

    Returns:
        dict: Vote confirmation with status and vote type

    Raises:
        HTTPException 400: Invalid session/message ID or vote type
        HTTPException 404: Session or message not found
        HTTPException 403: Not authorized to vote on message
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] PATCH /chat/sessions/%s/messages/%s/vote - User: %s, Vote: %s",
        request_id,
        session_id,
        message_id,
        username,
        vote_data.vote_type,
    )

    try:
        # Validate session ID format
        if not InputSanitizer.validate_session_id(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format",
            )

        # Validate message ID format
        if not InputSanitizer.validate_session_id(message_id):  # Same UUID format
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid message ID format",
            )

        # Get session to verify ownership
        session = await chat_service.get_session(session_id=session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Verify ownership
        if session.user_id != user_id:
            logger.warning(
                "[%s] Unauthorized vote attempt on session %s by user: %s",
                request_id,
                session_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to vote on messages in this session",
            )

        # Verify message belongs to session
        db = db_manager.get_database()
        message = await db.chat_messages.find_one({"id": message_id, "session_id": session_id})

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found in this session",
            )

        # Record vote
        result = await vote_manager.vote_message(
            message_id=message_id,
            user_id=user_id,
            vote_type=vote_data.vote_type.value,
        )

        logger.info(
            "[%s] Vote recorded for message %s by user: %s, Vote: %s",
            request_id,
            message_id,
            username,
            vote_data.vote_type,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to vote on message %s for user: %s, Error: %s",
            request_id,
            message_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "session_id": session_id, "message_id": message_id, "request_id": request_id},
            operation="vote_on_message",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record vote",
        )


@router.get(
    "/sessions/{session_id}/votes",
    summary="Get session votes",
    description="""
    Retrieve all votes for messages in a chat session.
    
    **Response Includes:**
    - List of all votes in the session
    - Vote details (message_id, user_id, vote_type, timestamp)
    - Total vote count
    
    **Use Cases:**
    - View feedback on all messages in a session
    - Analyze user satisfaction with responses
    - Identify patterns in positive/negative feedback
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - User must own the session
    """,
    responses={
        200: {
            "description": "List of votes for the session",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "votes": [
                            {
                                "id": "880e8400-e29b-41d4-a716-446655440003",
                                "message_id": "770e8400-e29b-41d4-a716-446655440002",
                                "user_id": "507f1f77bcf86cd799439011",
                                "vote_type": "up",
                                "created_at": "2024-01-15T10:31:00Z",
                                "updated_at": "2024-01-15T10:31:00Z"
                            },
                            {
                                "id": "990e8400-e29b-41d4-a716-446655440004",
                                "message_id": "770e8400-e29b-41d4-a716-446655440005",
                                "user_id": "507f1f77bcf86cd799439011",
                                "vote_type": "down",
                                "created_at": "2024-01-15T10:35:00Z",
                                "updated_at": "2024-01-15T10:35:00Z"
                            }
                        ],
                        "total_votes": 2
                    }
                }
            }
        },
        400: {
            "description": "Invalid session ID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid session ID format"}
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        403: {
            "description": "Not authorized to access votes for this session",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authorized to access votes for this session"}
                }
            }
        },
        404: {
            "description": "Session not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Session not found"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to retrieve votes"}
                }
            }
        }
    }
)
async def get_session_votes(
    request: Request,
    session_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    vote_manager: MessageVoteManager = Depends(get_vote_manager),
):
    """
    Get all votes for messages in a session.

    Args:
        request: FastAPI request object
        session_id: Session UUID
        current_user: Authenticated user from JWT
        chat_service: ChatService instance
        vote_manager: Vote manager instance

    Returns:
        dict: Votes grouped by message with statistics

    Raises:
        HTTPException 400: Invalid session ID format
        HTTPException 404: Session not found
        HTTPException 403: Not authorized to access session
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] GET /chat/sessions/%s/votes - User: %s",
        request_id,
        session_id,
        username,
    )

    try:
        # Validate session ID format
        if not InputSanitizer.validate_session_id(session_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID format",
            )

        # Get session to verify ownership
        session = await chat_service.get_session(session_id=session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found",
            )

        # Verify ownership
        if session.user_id != user_id:
            logger.warning(
                "[%s] Unauthorized access attempt to votes for session %s by user: %s",
                request_id,
                session_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access votes for this session",
            )

        # Get votes
        votes = await vote_manager.get_votes_for_session(session_id=session_id)

        logger.info(
            "[%s] Retrieved %d votes for session %s, user: %s",
            request_id,
            len(votes),
            session_id,
            username,
        )

        return {"session_id": session_id, "votes": votes, "total_votes": len(votes)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to get votes for session %s, user: %s, Error: %s",
            request_id,
            session_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "session_id": session_id, "request_id": request_id},
            operation="get_session_votes",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve votes",
        )



# Token Usage Endpoints


@router.get(
    "/messages/{message_id}/token-usage",
    summary="Get message token usage",
    description="""
    Retrieve detailed token usage information for a specific message.
    
    **Token Information:**
    - Prompt tokens: Tokens in the input (user message + context)
    - Completion tokens: Tokens in the AI response
    - Total tokens: Sum of prompt and completion tokens
    - Cost: Calculated cost (currently $0.00 for Ollama)
    - Model: LLM model used for generation
    
    **Token Estimation:**
    - Tokens are estimated using tiktoken library
    - Ollama doesn't provide exact token counts
    - Estimates are close approximations for monitoring
    
    **Use Cases:**
    - Monitor token consumption per message
    - Analyze cost per interaction
    - Optimize prompt engineering
    - Track model usage patterns
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - User must own the message
    """,
    responses={
        200: {
            "description": "Token usage details",
            "content": {
                "application/json": {
                    "example": {
                        "message_id": "770e8400-e29b-41d4-a716-446655440002",
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "model": "llama3.2:latest",
                        "prompt_tokens": 125,
                        "completion_tokens": 87,
                        "total_tokens": 212,
                        "cost": 0.0,
                        "created_at": "2024-01-15T10:30:05Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid message ID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid message ID format"}
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        403: {
            "description": "Not authorized to access token usage for this message",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authorized to access token usage for this message"}
                }
            }
        },
        404: {
            "description": "Message or token usage not found",
            "content": {
                "application/json": {
                    "examples": {
                        "message_not_found": {
                            "summary": "Message not found",
                            "value": {"detail": "Message not found"}
                        },
                        "token_usage_not_found": {
                            "summary": "Token usage not found",
                            "value": {"detail": "Token usage not found for this message"}
                        }
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to retrieve token usage"}
                }
            }
        }
    }
)
async def get_message_token_usage(
    request: Request,
    message_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get token usage for a specific message.

    Args:
        request: FastAPI request object
        message_id: Message UUID
        current_user: Authenticated user from JWT

    Returns:
        dict: Token usage details (prompt_tokens, completion_tokens, total_tokens, cost, model)

    Raises:
        HTTPException 400: Invalid message ID format
        HTTPException 404: Message or token usage not found
        HTTPException 403: Not authorized to access message
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] GET /chat/messages/%s/token-usage - User: %s",
        request_id,
        message_id,
        username,
    )

    try:
        # Validate message ID format
        if not InputSanitizer.validate_session_id(message_id):  # Same UUID format
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid message ID format",
            )

        # Get message to verify ownership
        db = db_manager.get_database()
        message = await db.chat_messages.find_one({"id": message_id})

        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found",
            )

        # Verify ownership
        if message["user_id"] != user_id:
            logger.warning(
                "[%s] Unauthorized access attempt to token usage for message %s by user: %s",
                request_id,
                message_id,
                username,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access token usage for this message",
            )

        # Get token usage
        token_usage = await db.token_usage.find_one({"message_id": message_id})

        if not token_usage:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token usage not found for this message",
            )

        logger.info(
            "[%s] Retrieved token usage for message %s, user: %s",
            request_id,
            message_id,
            username,
        )

        # Format response
        return {
            "message_id": message_id,
            "session_id": token_usage.get("session_id"),
            "model": token_usage.get("model"),
            "prompt_tokens": token_usage.get("prompt_tokens", 0),
            "completion_tokens": token_usage.get("completion_tokens", 0),
            "total_tokens": token_usage.get("total_tokens", 0),
            "cost": token_usage.get("cost", 0.0),
            "created_at": token_usage.get("created_at"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[%s] Failed to get token usage for message %s, user: %s, Error: %s",
            request_id,
            message_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "message_id": message_id, "request_id": request_id},
            operation="get_message_token_usage",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve token usage",
        )


@router.get(
    "/token-usage/summary",
    response_model=TokenUsageSummaryResponse,
    summary="Get token usage summary",
    description="""
    Retrieve comprehensive token usage statistics for the authenticated user.
    
    **Summary Includes:**
    - Total tokens consumed across all messages
    - Total cost (currently $0.00 for Ollama, but tracked for future)
    - Total number of messages
    - Breakdown by model (tokens, cost, message count per model)
    
    **Filtering:**
    - Filter by date range (start_date and/or end_date)
    - Filter by specific model name
    - Dates should be in ISO 8601 format (e.g., 2024-01-15T10:30:00Z)
    
    **Use Cases:**
    - Monitor token consumption over time
    - Track usage by model
    - Analyze cost trends (for future paid LLM providers)
    - Generate usage reports
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - Only returns data for the authenticated user
    """,
    responses={
        200: {
            "description": "Token usage summary",
            "content": {
                "application/json": {
                    "example": {
                        "total_tokens": 15750,
                        "total_cost": 0.0,
                        "total_messages": 42,
                        "model_breakdown": {
                            "llama3.2:latest": {
                                "total_tokens": 12500,
                                "total_cost": 0.0,
                                "message_count": 35
                            },
                            "mistral:latest": {
                                "total_tokens": 3250,
                                "total_cost": 0.0,
                                "message_count": 7
                            }
                        },
                        "date_range": {
                            "start": "2024-01-01T00:00:00Z",
                            "end": "2024-01-15T23:59:59Z"
                        }
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to retrieve token usage summary"}
                }
            }
        }
    }
)
async def get_token_usage_summary(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
    start_date: Optional[datetime] = Query(None, description="Start date for summary (ISO 8601 format)"),
    end_date: Optional[datetime] = Query(None, description="End date for summary (ISO 8601 format)"),
    model: Optional[str] = Query(None, description="Filter by model name (e.g., 'llama3.2:latest')"),
):
    """
    Get token usage summary for the authenticated user.

    Args:
        request: FastAPI request object
        current_user: Authenticated user from JWT
        start_date: Optional start date filter
        end_date: Optional end date filter
        model: Optional model name filter

    Returns:
        TokenUsageSummaryResponse: Summary statistics (total_tokens, total_cost, model_breakdown)

    Raises:
        HTTPException 500: Internal server error
    """
    request_id = setup_request_context(request, current_user)
    user_id = str(current_user["_id"])
    username = current_user["username"]

    logger.info(
        "[%s] GET /chat/token-usage/summary - User: %s, Start: %s, End: %s, Model: %s",
        request_id,
        username,
        start_date,
        end_date,
        model,
    )

    try:
        # Build query
        query = {"user_id": user_id}

        # Add date range filter
        if start_date or end_date:
            query["created_at"] = {}
            if start_date:
                query["created_at"]["$gte"] = start_date
            if end_date:
                query["created_at"]["$lte"] = end_date

        # Add model filter
        if model:
            query["model"] = model

        # Get token usage records
        db = db_manager.get_database()
        token_usage_records = await db.token_usage.find(query).to_list(None)

        # Calculate summary statistics
        total_tokens = sum(record.get("total_tokens", 0) for record in token_usage_records)
        total_cost = sum(record.get("cost", 0.0) for record in token_usage_records)
        total_messages = len(set(record.get("message_id") for record in token_usage_records))

        # Calculate model breakdown
        model_breakdown = {}
        for record in token_usage_records:
            model_name = record.get("model", "unknown")
            if model_name not in model_breakdown:
                model_breakdown[model_name] = {
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "message_count": set(),
                }

            model_breakdown[model_name]["total_tokens"] += record.get("total_tokens", 0)
            model_breakdown[model_name]["total_cost"] += record.get("cost", 0.0)
            model_breakdown[model_name]["message_count"].add(record.get("message_id"))

        # Convert sets to counts
        for model_name in model_breakdown:
            model_breakdown[model_name]["message_count"] = len(model_breakdown[model_name]["message_count"])

        logger.info(
            "[%s] Token usage summary for user: %s - Total tokens: %d, Total cost: %.4f, Messages: %d",
            request_id,
            username,
            total_tokens,
            total_cost,
            total_messages,
        )

        return TokenUsageSummaryResponse(
            total_tokens=total_tokens,
            total_cost=total_cost,
            total_messages=total_messages,
            model_breakdown=model_breakdown,
            date_range={
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
        )

    except Exception as e:
        logger.error(
            "[%s] Failed to get token usage summary for user: %s, Error: %s",
            request_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id},
            operation="get_token_usage_summary",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve token usage summary",
        )



# Health Check Endpoint


@router.get(
    "/health",
    summary="Chat system health check",
    description="""
    Comprehensive health check for the chat system and all dependencies.
    
    **Services Checked:**
    - **Ollama** (Critical): LLM inference service
    - **MongoDB** (Critical): Database for sessions and messages
    - **Redis** (Non-critical): Caching and rate limiting
    - **Qdrant** (Non-critical): Vector database for RAG
    
    **Status Levels:**
    - `healthy`: All critical services operational
    - `degraded`: Critical services OK, but non-critical services down
    - `unhealthy`: One or more critical services down
    
    **Response Times:**
    - Includes response time in milliseconds for each service
    - Total health check response time included
    
    **No Authentication Required:**
    - This endpoint is publicly accessible for monitoring
    """,
    responses={
        200: {
            "description": "System healthy or degraded",
            "content": {
                "application/json": {
                    "examples": {
                        "healthy": {
                            "summary": "All services healthy",
                            "value": {
                                "status": "healthy",
                                "timestamp": "2024-01-15T10:30:00Z",
                                "services": {
                                    "ollama": {
                                        "status": "healthy",
                                        "response_time_ms": 45.23,
                                        "host": "http://localhost:11434"
                                    },
                                    "mongodb": {
                                        "status": "healthy",
                                        "response_time_ms": 12.45
                                    },
                                    "redis": {
                                        "status": "healthy",
                                        "response_time_ms": 3.21
                                    },
                                    "qdrant": {
                                        "status": "healthy",
                                        "response_time_ms": 25.67,
                                        "host": "localhost",
                                        "port": 6333
                                    }
                                },
                                "response_time_ms": 86.56
                            }
                        },
                        "degraded": {
                            "summary": "Non-critical service down",
                            "value": {
                                "status": "degraded",
                                "timestamp": "2024-01-15T10:30:00Z",
                                "services": {
                                    "ollama": {
                                        "status": "healthy",
                                        "response_time_ms": 45.23,
                                        "host": "http://localhost:11434"
                                    },
                                    "mongodb": {
                                        "status": "healthy",
                                        "response_time_ms": 12.45
                                    },
                                    "redis": {
                                        "status": "unhealthy",
                                        "error": "Connection refused"
                                    },
                                    "qdrant": {
                                        "status": "healthy",
                                        "response_time_ms": 25.67,
                                        "host": "localhost",
                                        "port": 6333
                                    }
                                },
                                "response_time_ms": 83.35
                            }
                        }
                    }
                }
            }
        },
        503: {
            "description": "Critical service unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "services": {
                            "ollama": {
                                "status": "unhealthy",
                                "error": "Connection timeout"
                            },
                            "mongodb": {
                                "status": "healthy",
                                "response_time_ms": 12.45
                            },
                            "redis": {
                                "status": "healthy",
                                "response_time_ms": 3.21
                            },
                            "qdrant": {
                                "status": "disabled",
                                "message": "Qdrant is not enabled in configuration"
                            }
                        },
                        "response_time_ms": 5015.78
                    }
                }
            }
        }
    }
)
async def chat_health_check(request: Request):
    """
    Comprehensive health check for chat system.

    Checks connectivity and response times for:
    - Ollama (LLM service)
    - MongoDB (database)
    - Redis (caching and rate limiting)
    - Qdrant (vector database)

    Args:
        request: FastAPI request object

    Returns:
        dict: Health status with service details and response times

    Status Codes:
        200: All critical services healthy
        503: One or more critical services unhealthy
    """
    import time

    from second_brain_database.config import settings

    request_id = str(datetime.now(timezone.utc).timestamp()).replace(".", "")[-8:]
    request_id_context.set(request_id)

    logger.info("[%s] GET /chat/health - Health check requested", request_id)

    start_time = time.time()
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {},
    }

    # Check Ollama
    ollama_healthy = False
    ollama_response_time = 0.0
    try:
        ollama_start = time.time()

        # Try to import and check Ollama
        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.OLLAMA_HOST}/api/tags")
                if response.status_code == 200:
                    ollama_healthy = True
        except Exception as e:
            logger.warning("[%s] Ollama health check failed: %s", request_id, str(e))

        ollama_response_time = round((time.time() - ollama_start) * 1000, 2)

        health_status["services"]["ollama"] = {
            "status": "healthy" if ollama_healthy else "unhealthy",
            "response_time_ms": ollama_response_time,
            "host": settings.OLLAMA_HOST,
        }

    except Exception as e:
        logger.error("[%s] Ollama health check error: %s", request_id, str(e))
        health_status["services"]["ollama"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Check MongoDB
    mongodb_healthy = False
    mongodb_response_time = 0.0
    try:
        mongodb_start = time.time()

        db = db_manager.get_database()
        # Simple ping command
        await db.command("ping")
        mongodb_healthy = True

        mongodb_response_time = round((time.time() - mongodb_start) * 1000, 2)

        health_status["services"]["mongodb"] = {
            "status": "healthy" if mongodb_healthy else "unhealthy",
            "response_time_ms": mongodb_response_time,
        }

    except Exception as e:
        logger.error("[%s] MongoDB health check error: %s", request_id, str(e))
        health_status["services"]["mongodb"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Check Redis
    redis_healthy = False
    redis_response_time = 0.0
    try:
        redis_start = time.time()

        redis_client = redis_manager.get_client()
        # Simple ping command
        await redis_client.ping()
        redis_healthy = True

        redis_response_time = round((time.time() - redis_start) * 1000, 2)

        health_status["services"]["redis"] = {
            "status": "healthy" if redis_healthy else "unhealthy",
            "response_time_ms": redis_response_time,
        }

    except Exception as e:
        logger.error("[%s] Redis health check error: %s", request_id, str(e))
        health_status["services"]["redis"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Check Qdrant (optional - only if enabled)
    qdrant_healthy = False
    qdrant_response_time = 0.0
    if settings.QDRANT_ENABLED:
        try:
            qdrant_start = time.time()

            # Try to import and check Qdrant
            try:
                from qdrant_client import QdrantClient

                qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT, timeout=5.0)
                collections = qdrant_client.get_collections()
                qdrant_healthy = True
            except Exception as e:
                logger.warning("[%s] Qdrant health check failed: %s", request_id, str(e))

            qdrant_response_time = round((time.time() - qdrant_start) * 1000, 2)

            health_status["services"]["qdrant"] = {
                "status": "healthy" if qdrant_healthy else "unhealthy",
                "response_time_ms": qdrant_response_time,
                "host": settings.QDRANT_HOST,
                "port": settings.QDRANT_PORT,
            }

        except Exception as e:
            logger.error("[%s] Qdrant health check error: %s", request_id, str(e))
            health_status["services"]["qdrant"] = {
                "status": "unhealthy",
                "error": str(e),
            }
    else:
        health_status["services"]["qdrant"] = {
            "status": "disabled",
            "message": "Qdrant is not enabled in configuration",
        }

    # Calculate total response time
    total_response_time = round((time.time() - start_time) * 1000, 2)
    health_status["response_time_ms"] = total_response_time

    # Determine overall status
    # Critical services: Ollama and MongoDB
    if not ollama_healthy or not mongodb_healthy:
        health_status["status"] = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    # Degraded if Redis or Qdrant are down (non-critical)
    elif not redis_healthy or (settings.QDRANT_ENABLED and not qdrant_healthy):
        health_status["status"] = "degraded"
        status_code = status.HTTP_200_OK
    else:
        health_status["status"] = "healthy"
        status_code = status.HTTP_200_OK

    logger.info(
        "[%s] Health check complete - Status: %s, Response time: %.2fms",
        request_id,
        health_status["status"],
        total_response_time,
    )

    return JSONResponse(content=health_status, status_code=status_code)



# Metrics Endpoint


@router.get(
    "/metrics",
    summary="Get chat system metrics",
    description="""
    Retrieve comprehensive real-time metrics for the chat system.
    
    **Metrics Included:**
    - **Performance**: Messages per second, average response time
    - **Token Usage**: Total tokens, tokens per message, cost tracking
    - **Error Rates**: Error count and percentage by error type
    - **Cache Performance**: Cache hit rate, cache size
    - **Vector Search**: Search latency, results per query
    - **Graph Execution**: Node execution times, workflow statistics
    
    **Metric Types:**
    - **Counters**: Cumulative values (total messages, total tokens)
    - **Gauges**: Current values (messages per second, cache size)
    - **Histograms**: Distribution data (response times, token counts)
    
    **Time Windows:**
    - Most metrics are calculated over the last hour
    - Some metrics include all-time totals
    
    **Authentication:**
    - Requires valid JWT token in Authorization header
    - Returns system-wide metrics (not user-specific)
    """,
    responses={
        200: {
            "description": "Comprehensive metrics summary",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "timestamp": "2024-01-15T10:30:00Z",
                        "metrics": {
                            "performance": {
                                "messages_per_second": 2.5,
                                "average_response_time_ms": 1250.5,
                                "p95_response_time_ms": 2100.0,
                                "p99_response_time_ms": 3500.0
                            },
                            "token_usage": {
                                "total_tokens": 125000,
                                "tokens_per_message_avg": 350,
                                "total_cost": 0.0
                            },
                            "errors": {
                                "total_errors": 12,
                                "error_rate_percent": 0.5,
                                "errors_by_type": {
                                    "llm_timeout": 5,
                                    "vector_search_failed": 4,
                                    "rate_limit_exceeded": 3
                                }
                            },
                            "cache": {
                                "hit_rate_percent": 45.2,
                                "total_hits": 1250,
                                "total_misses": 1515,
                                "cache_size_mb": 12.5
                            },
                            "vector_search": {
                                "average_latency_ms": 85.3,
                                "average_results_per_query": 4.8,
                                "total_searches": 850
                            },
                            "graph_execution": {
                                "average_execution_time_ms": 1150.0,
                                "node_execution_times": {
                                    "detect_intent": 50.2,
                                    "retrieve_contexts": 85.3,
                                    "generate_response": 1014.5
                                }
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Not authenticated",
            "content": {
                "application/json": {
                    "example": {"detail": "Not authenticated"}
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to retrieve chat metrics"}
                }
            }
        }
    }
)
async def get_chat_metrics(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Get comprehensive metrics for chat system.

    Returns real-time metrics including:
    - Messages per second
    - Average response time
    - Token usage statistics
    - Error rates by type
    - Cache hit rate
    - Vector search performance
    - Graph execution statistics

    Args:
        request: FastAPI request object
        current_user: Authenticated user

    Returns:
        dict: Comprehensive metrics summary

    Raises:
        HTTPException 500: Failed to retrieve metrics
    """
    from second_brain_database.chat.utils.metrics_tracker import get_metrics_tracker

    request_id = setup_request_context(request, current_user)
    username = current_user["username"]

    logger.info(
        "[%s] GET /chat/metrics - User: %s",
        request_id,
        username,
    )

    try:
        # Get metrics tracker
        metrics_tracker = get_metrics_tracker(redis_manager=redis_manager)

        # Get comprehensive metrics summary
        metrics_summary = await metrics_tracker.get_metrics_summary()

        logger.info(
            "[%s] Retrieved chat metrics for user: %s",
            request_id,
            username,
        )

        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics_summary
        }

    except Exception as e:
        logger.error(
            "[%s] Failed to retrieve chat metrics for user: %s, Error: %s",
            request_id,
            username,
            str(e),
        )
        log_error_with_context(
            e,
            context={"user": username, "request_id": request_id},
            operation="get_chat_metrics",
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat metrics",
        )
