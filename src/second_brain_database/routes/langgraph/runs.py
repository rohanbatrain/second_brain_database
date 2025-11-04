"""Run management endpoints for LangGraph Platform API.

Implements run execution with streaming support via Server-Sent Events (SSE).
"""
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from uuid import uuid4
from datetime import datetime
import json

from ...managers.redis_manager import RedisManager
from ...managers.logging_manager import get_logger
from ...routes.auth.dependencies import get_current_user_dep
from ...config import settings

logger = get_logger(prefix="[LangGraphRuns]")
router = APIRouter(tags=["langgraph"])


class MessageInput(BaseModel):
    """Single message in the conversation."""
    role: str
    content: str


class RunInput(BaseModel):
    """Input for creating a run."""
    messages: List[MessageInput]
    metadata: Optional[Dict[str, Any]] = None


class RunCreate(BaseModel):
    """Request model for creating a run."""
    assistant_id: str = "sbd_agent"
    input: RunInput
    stream: bool = True
    metadata: Optional[Dict[str, Any]] = None


class RunStatus(BaseModel):
    """Run status response."""
    run_id: str
    thread_id: str
    assistant_id: str
    status: str  # "pending", "running", "completed", "failed"
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


def get_redis_manager():
    """Dependency to get Redis manager."""
    from ...managers.redis_manager import RedisManager
    return RedisManager()


def get_orchestrator():
    """Dependency to get LangChain orchestrator."""
    # LangChain orchestrator removed - functionality disabled
    return None


async def stream_graph_events(
    thread_id: str,
    graph,
    input_messages: List[MessageInput],
    checkpointer
) -> AsyncIterator[str]:
    """Stream events from graph execution.

    Note: LangGraph functionality disabled.
    """
    # This function is disabled
    raise HTTPException(status_code=503, detail="LangGraph functionality is disabled")


@router.post("/threads/{thread_id}/runs")
async def create_run(
    thread_id: str,
    run_data: RunCreate,
    current_user: Dict[str, Any] = Depends(get_current_user_dep),
    redis: RedisManager = Depends(get_redis_manager),
    orchestrator: Any = Depends(get_orchestrator)
):
    """Create and execute a run with streaming support.

    Note: LangGraph functionality is currently disabled.
    """
    raise HTTPException(
        status_code=503,
        detail="LangGraph AI system is currently disabled"
    )


@router.get("/threads/{thread_id}/runs/{run_id}", response_model=RunStatus)
async def get_run_status(
    thread_id: str,
    run_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_dep),
    redis: RedisManager = Depends(get_redis_manager)
):
    """Get the status of a specific run.

    Returns information about run execution including status,
    timing, and any errors.
    """
    try:
        # Verify thread access
        thread_key = f"thread:{thread_id}"
        thread_data = redis.client.get(thread_key)

        if not thread_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread {thread_id} not found"
            )

        thread_dict = json.loads(thread_data)
        if thread_dict.get("metadata", {}).get("user_id") != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this thread"
            )

        # Get run status
        run_key = f"run:{run_id}"
        run_data = redis.client.get(run_key)

        if not run_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} not found"
            )

        run_dict = json.loads(run_data)
        return RunStatus(**run_dict)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving run status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve run status: {str(e)}"
        )


@router.post("/threads/{thread_id}/runs/{run_id}/cancel")
async def cancel_run(
    thread_id: str,
    run_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user_dep),
    redis: RedisManager = Depends(get_redis_manager)
):
    """Cancel a running execution.

    Note: This is a placeholder. Actual cancellation requires
    implementing graph interruption logic.
    """
    try:
        # Verify access
        thread_key = f"thread:{thread_id}"
        thread_data = redis.client.get(thread_key)

        if not thread_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Thread {thread_id} not found"
            )

        thread_dict = json.loads(thread_data)
        if thread_dict.get("metadata", {}).get("user_id") != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this thread"
            )

        # Update run status
        run_key = f"run:{run_id}"
        run_data = redis.client.get(run_key)

        if not run_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} not found"
            )

        run_dict = json.loads(run_data)
        run_status = RunStatus(**run_dict)

        if run_status.status != "running":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel run with status: {run_status.status}"
            )

        # Mark as cancelled
        run_status.status = "cancelled"
        run_status.completed_at = datetime.utcnow()

        redis.client.setex(
            run_key,
            3600,
            json.dumps(run_status.dict(), default=str)
        )

        logger.info(f"Cancelled run {run_id}")
        return {"status": "cancelled"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling run: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel run: {str(e)}"
        )
