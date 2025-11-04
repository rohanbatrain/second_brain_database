"""Production LangChain/LangGraph AI routes with MCP integration."""
import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, AsyncGenerator, Any, List, Optional, Union
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ...config import settings
from ...managers.logging_manager import get_logger
from ...managers.security_manager import SecurityManager
from ...managers.redis_manager import RedisManager
from second_brain_database.integrations.mcp.security import get_mcp_user_context
from second_brain_database.integrations.mcp.context import MCPUserContext
from ...config import Settings
from ..auth.services.auth.login import get_current_user

logger = get_logger(prefix="[LangGraphRoutes]")

router = APIRouter(prefix="/ai", tags=["ai"])

# Dependency injection
settings = Settings()
redis_manager = None
orchestrator = None
security_manager = SecurityManager()

def get_redis_manager():
    global redis_manager
    if redis_manager is None:
        redis_manager = RedisManager()  # RedisManager doesn't take settings parameter
    return redis_manager

def get_orchestrator_instance():
    # LangChain orchestrator removed - functionality disabled
    return None

# Request/Response Models
class CreateSessionRequest(BaseModel):
    agent_type: str = Field(default="general", description="Agent type: general, family, shop")

class MessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    agent_type: str = Field(default="general")

class SessionResponse(BaseModel):
    session_id: str
    status: str
    message: str

class MessageResponse(BaseModel):
    response: str
    session_id: str

# Endpoints
@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create new AI session."""
    try:
        # Check rate limit
        user_id = str(current_user["_id"])
        if not await security_manager.check_rate_limit(
            user_id, "ai_sessions", limit=50, window=3600
        ):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        session_id = str(uuid.uuid4())
        
        # Store session metadata in Redis
        redis = get_redis_manager()
        redis.set(
            f"ai:session:{session_id}",
            json.dumps({
                "user_id": user_id,
                "agent_type": request.agent_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }),
            ex=3600,  # 1 hour TTL
        )
        
        logger.info(f"Created AI session {session_id} for user {user_id}")
        
        return SessionResponse(
            session_id=session_id,
            status="created",
            message="Session created successfully",
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
async def chat(
    request: MessageRequest,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Send message to AI agent."""
    try:
        # Check rate limit
        user_id = str(current_user["_id"])
        if not await security_manager.check_rate_limit(
            user_id, "ai_messages", limit=100, window=3600
        ):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        
        # Create MCP user context
        user_context = MCPUserContext(
            user_id=user_id,
            username=current_user.get("username", ""),
            email=current_user.get("email", ""),
            role=current_user.get("role", "user"),
            permissions=current_user.get("permissions", []),
            family_memberships=current_user.get("family_memberships", []),
            workspaces=current_user.get("workspaces", []),
            ip_address="",
            user_agent="",
            token_type="jwt",
            token_id="",
            authenticated_at=datetime.now(timezone.utc),
        )
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Get orchestrator and process message
        orchestrator = get_orchestrator_instance()
        if orchestrator is None:
            raise HTTPException(status_code=503, detail="AI system is currently disabled")
        
        response = await orchestrator.chat(
            session_id=session_id,
            user_id=user_id,
            message=request.content,
            user_context=user_context,
            agent_type=request.agent_type,
        )
        
        if "error" in response:
            raise HTTPException(status_code=500, detail=response["error"])
        
        return MessageResponse(
            response=response["response"],
            session_id=response["session_id"],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get session info."""
    try:
        redis = get_redis_manager()
        data = redis.get(f"ai:session:{session_id}")
        
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = json.loads(data)
        
        # Verify user owns session
        if session_data["user_id"] != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return session_data
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Delete session."""
    try:
        redis = get_redis_manager()
        data = redis.get(f"ai:session:{session_id}")
        
        if not data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session_data = json.loads(data)
        
        # Verify user owns session
        if session_data["user_id"] != str(current_user["_id"]):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Clear session
        orchestrator = get_orchestrator_instance()
        if orchestrator:
            orchestrator.clear_session(session_id)
        redis.delete(f"ai:session:{session_id}")
        
        return {"status": "deleted", "session_id": session_id}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete session failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/workflows/multi-step")
async def run_multi_step_workflow(
    request: MessageRequest,
    user_context: MCPUserContext = Depends(get_mcp_user_context),
):
    """Run multi-step workflow for complex tasks.
    
    Note: Workflows are currently disabled.
    """
    raise HTTPException(status_code=503, detail="Workflow system is currently disabled")


@router.post("/workflows/shopping")
async def run_shopping_workflow(
    request: MessageRequest,
    user_context: MCPUserContext = Depends(get_mcp_user_context),
):
    """Run shopping workflow for purchases.
    
    Note: Workflows are currently disabled.
    """
    raise HTTPException(status_code=503, detail="Workflow system is currently disabled")


@router.get("/health")
async def health_check():
    """Health check for AI system."""
    return {
        "status": "healthy",
        "enabled": settings.LANGCHAIN_ENABLED,
        "provider": settings.LANGCHAIN_MODEL_PROVIDER,
        "model": settings.LANGCHAIN_DEFAULT_MODEL,
    }
