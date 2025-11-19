"""LangGraph Cloud API-compatible routes.

These routes provide a LangGraph SDK-compatible API layer on top of
the existing ChatService, enabling the frontend to use @langchain/langgraph-sdk.
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from second_brain_database.chat.models.request_models import (
    ChatMessageCreate,
    ChatSessionCreate,
)
from second_brain_database.chat.services.chat_service import ChatService
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth import enforce_all_lockdowns

from .adapter import LangGraphAdapter
from .models import (
    GraphInfo,
    InfoResponse,
    StreamRequest,
    Thread,
    ThreadCreate,
    ThreadSearchRequest,
    ThreadStateResponse,
)

router = APIRouter(tags=["LangGraph API"])
logger = get_logger(prefix="[LangGraph API]")


# Dependency functions
def get_chat_service() -> ChatService:
    """Get ChatService instance with database connection."""
    return ChatService(
        db=db_manager.get_db(), redis_manager=redis_manager.get_redis_manager()
    )


def get_adapter(chat_service: ChatService = Depends(get_chat_service)) -> LangGraphAdapter:
    """Get LangGraphAdapter instance."""
    return LangGraphAdapter(chat_service)


# ============================================================================
# Graph Information Endpoint
# ============================================================================


@router.get("/info", response_model=InfoResponse)
async def get_graph_info():
    """Get information about available graphs.

    This endpoint provides metadata about the LangGraph deployment,
    including available graphs and API version info.

    Returns:
        InfoResponse: Graph metadata and version information
    """
    graphs = [
        GraphInfo(
            graph_id="general",
            name="General Response",
            description="General-purpose conversational AI for answering questions",
        ),
        GraphInfo(
            graph_id="vector_rag",
            name="Vector RAG",
            description="Retrieval-augmented generation with vector search",
        ),
        GraphInfo(
            graph_id="master",
            name="Master Workflow",
            description="Intelligent workflow orchestrator that routes to appropriate graph",
        ),
    ]

    return InfoResponse(version="1.0.0", graphs=graphs)


# ============================================================================
# Thread Management Endpoints
# ============================================================================


@router.post("/threads", response_model=Thread, status_code=status.HTTP_201_CREATED)
async def create_thread(
    request: Request,
    thread_data: Optional[ThreadCreate] = None,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    adapter: LangGraphAdapter = Depends(get_adapter),
):
    """Create a new thread (chat session).

    Args:
        request: FastAPI request object
        thread_data: Thread creation data with metadata
        current_user: Authenticated user from JWT
        chat_service: ChatService instance
        adapter: LangGraphAdapter instance

    Returns:
        Thread: Created thread in LangGraph format

    Raises:
        HTTPException 500: If thread creation fails
    """
    try:
        user_id = current_user.get("user_id")

        # Extract metadata
        metadata = thread_data.metadata if thread_data else None
        session_type = metadata.session_type if metadata and metadata.session_type else "GENERAL"

        # Create session using existing ChatService
        session_create = ChatSessionCreate(
            session_type=session_type.upper(),
            title=None,  # Auto-generated on first message
            knowledge_base_ids=[],
        )

        session = await chat_service.create_session(user_id, session_create)

        # Convert to Thread format
        thread = adapter.session_to_thread(session)

        logger.info(f"Created thread {thread.thread_id} for user {user_id}")
        return thread

    except Exception as e:
        logger.error(f"Failed to create thread: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create thread: {str(e)}",
        ) from e


@router.get("/threads/{thread_id}", response_model=Thread)
async def get_thread(
    thread_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    adapter: LangGraphAdapter = Depends(get_adapter),
):
    """Get a specific thread by ID.

    Args:
        thread_id: Thread/session ID
        current_user: Authenticated user
        chat_service: ChatService instance
        adapter: LangGraphAdapter instance

    Returns:
        Thread: Thread details

    Raises:
        HTTPException 404: If thread not found
        HTTPException 403: If user doesn't own the thread
    """
    session = await chat_service.get_session(thread_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )

    # Verify ownership
    if session.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this thread"
        )

    return adapter.session_to_thread(session)


@router.post("/threads/search", response_model=list[Thread])
async def search_threads(
    search_request: ThreadSearchRequest,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    adapter: LangGraphAdapter = Depends(get_adapter),
):
    """Search/list threads for the authenticated user.

    Args:
        search_request: Search parameters with metadata filters
        current_user: Authenticated user
        chat_service: ChatService instance
        adapter: LangGraphAdapter instance

    Returns:
        List[Thread]: List of threads matching search criteria
    """
    user_id = current_user.get("user_id")

    # Extract filters from metadata
    session_type = None
    if search_request.metadata and search_request.metadata.session_type:
        session_type = search_request.metadata.session_type.upper()

    # Use existing list_sessions
    sessions = await chat_service.list_sessions(
        user_id=user_id,
        session_type=session_type,
        is_active=True,
        skip=search_request.offset,
        limit=search_request.limit,
    )

    # Convert to threads
    threads = [adapter.session_to_thread(session) for session in sessions]

    logger.info(f"Found {len(threads)} threads for user {user_id}")
    return threads


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
):
    """Delete a thread and all its messages.

    Args:
        thread_id: Thread/session ID to delete
        current_user: Authenticated user
        chat_service: ChatService instance

    Raises:
        HTTPException 404: If thread not found
        HTTPException 403: If user doesn't own the thread
    """
    # Verify ownership
    session = await chat_service.get_session(thread_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )

    if session.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this thread"
        )

    # Delete session
    success = await chat_service.delete_session(thread_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete thread",
        )

    logger.info(f"Deleted thread {thread_id}")


# ============================================================================
# Thread State Endpoints
# ============================================================================


@router.get("/threads/{thread_id}/state", response_model=ThreadStateResponse)
async def get_thread_state(
    thread_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    adapter: LangGraphAdapter = Depends(get_adapter),
):
    """Get current state of a thread.

    Args:
        thread_id: Thread/session ID
        current_user: Authenticated user
        chat_service: ChatService instance
        adapter: LangGraphAdapter instance

    Returns:
        ThreadStateResponse: Current thread state with messages

    Raises:
        HTTPException 404: If thread not found
        HTTPException 403: If user doesn't own the thread
    """
    # Verify ownership
    session = await chat_service.get_session(thread_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )

    if session.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this thread"
        )

    # Get thread values (messages)
    values = await adapter.get_thread_values(thread_id)

    return ThreadStateResponse(values=values, next=[])


# ============================================================================
# Streaming Endpoints
# ============================================================================


@router.post("/threads/{thread_id}/runs/stream")
async def stream_run(
    thread_id: str,
    stream_request: StreamRequest,
    current_user: dict = Depends(enforce_all_lockdowns),
    chat_service: ChatService = Depends(get_chat_service),
    adapter: LangGraphAdapter = Depends(get_adapter),
):
    """Stream a graph run for a thread.

    This endpoint streams the execution of a graph in LangGraph SDK format.

    Args:
        thread_id: Thread/session ID
        stream_request: Stream configuration and input
        current_user: Authenticated user
        chat_service: ChatService instance
        adapter: LangGraphAdapter instance

    Returns:
        StreamingResponse: SSE stream in LangGraph format

    Raises:
        HTTPException 404: If thread not found
        HTTPException 403: If user doesn't own the thread
    """
    # Verify ownership
    session = await chat_service.get_session(thread_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found"
        )

    if session.user_id != current_user.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this thread"
        )

    # Extract user message from input
    user_message = None
    if stream_request.input:
        if isinstance(stream_request.input, dict):
            # Handle RunInput format
            messages = stream_request.input.get("messages", [])
            if messages:
                # Get last human message
                for msg in reversed(messages):
                    if msg.get("type") == "human":
                        user_message = msg.get("content")
                        break

    if not user_message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No user message found in input",
        )

    # Create message using existing ChatService
    message_create = ChatMessageCreate(content=user_message)

    try:
        # Get streaming response from ChatService
        chat_stream = chat_service.stream_chat_response(
            session_id=thread_id, user_id=current_user.get("user_id"), message=message_create
        )

        # Adapt to LangGraph streaming format
        langgraph_stream = adapter.adapt_stream_response(chat_stream)

        return StreamingResponse(
            langgraph_stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except Exception as e:
        logger.error(f"Stream error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Streaming failed: {str(e)}",
        ) from e
