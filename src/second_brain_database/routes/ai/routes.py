"""
AI Orchestration Routes

This module provides FastAPI routes for AI agent orchestration, including
session management, WebSocket communication, and real-time AI interactions.
"""

import uuid
import json
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from second_brain_database.routes.auth.services.auth.login import get_current_user
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import SecurityManager
from second_brain_database.integrations.ai_orchestration.models.session import (
    SessionCreateRequest,
    SessionResponse,
    MessageRequest,
    MessageResponse,
    SessionListResponse,
    SessionStatsResponse,
    SessionContext,
    ConversationMessage,
    MessageRole,
    SessionStatus,
    AgentType
)
from second_brain_database.integrations.ai_orchestration.event_bus import get_ai_event_bus
from second_brain_database.integrations.ai_orchestration.models.events import EventType
from second_brain_database.integrations.ai_orchestration.orchestrator import AgentOrchestrator
from second_brain_database.integrations.mcp.context import MCPUserContext
from second_brain_database.integrations.ai_orchestration.security import (
    ai_security_integration,
    ai_security_manager,
    ConversationPrivacyMode,
    AIPermission
)
from second_brain_database.integrations.ai_orchestration.errors import (
    AIOrchestrationError,
    AIErrorContext,
    AIErrorCategory,
    AIErrorSeverity,
    SessionManagementError,
    CommunicationError,
    handle_ai_errors,
    create_ai_error_context,
    log_ai_error
)

logger = get_logger(prefix="[AI_Routes]")
security_manager = SecurityManager()

# Create router with AI orchestration prefix
router = APIRouter(prefix="/ai", tags=["AI Orchestration"])

# In-memory session storage (in production, this would be Redis/MongoDB)
active_sessions: Dict[str, SessionContext] = {}

# Global AI orchestrator instance
ai_orchestrator: Optional[AgentOrchestrator] = None

def get_ai_orchestrator() -> Optional[AgentOrchestrator]:
    """Get the AI orchestrator instance from app state."""
    from fastapi import Request
    from starlette.requests import Request as StarletteRequest
    
    # Try to get from app state if available
    try:
        from second_brain_database.main import app
        if hasattr(app.state, 'ai_orchestrator'):
            return app.state.ai_orchestrator
    except:
        pass
    
    # Fallback to global instance
    return ai_orchestrator


def get_ai_orchestrator_dependency() -> AgentOrchestrator:
    """Get the global AI orchestrator instance."""
    global ai_orchestrator
    if ai_orchestrator is None:
        ai_orchestrator = AgentOrchestrator()
    return ai_orchestrator


async def get_current_user_ws(token: Optional[str] = Query(None)):
    """
    Dependency function to retrieve the current authenticated user for WebSocket connections.
    The token is passed as a query parameter.
    """
    if token is None:
        return None
    return await get_current_user(token)


def get_user_sessions(user_id: str) -> List[SessionContext]:
    """Get all sessions for a specific user."""
    return [session for session in active_sessions.values() if session.user_id == user_id]


def cleanup_expired_sessions():
    """Clean up expired sessions."""
    expired_sessions = [
        session_id for session_id, session in active_sessions.items()
        if session.is_expired()
    ]
    
    for session_id in expired_sessions:
        logger.info(f"Cleaning up expired session: {session_id}")
        del active_sessions[session_id]
    
    return len(expired_sessions)


@router.post("/sessions", response_model=SessionResponse)
@handle_ai_errors(
    operation_name="create_ai_session_endpoint",
    enable_recovery=True,
    circuit_breaker="session_creation_api",
    bulkhead="session_api"
)
async def create_ai_session(
    request: SessionCreateRequest,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Create a new AI session with the specified agent type.
    
    This endpoint creates a new AI conversation session that can be used
    for real-time communication with AI agents through WebSocket connections.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Create MCP user context for security validation
        user_context = MCPUserContext(
            user_id=user_id,
            username=current_user.get("username", ""),
            permissions=current_user.get("permissions", [])
        )
        
        # Security validation - check AI permissions
        await ai_security_manager.check_ai_permissions(
            user_context,
            AIPermission.BASIC_CHAT
        )
        
        # Check voice permissions if voice is enabled
        if request.voice_enabled:
            await ai_security_manager.check_ai_permissions(
                user_context,
                AIPermission.VOICE_INTERACTION
            )
        
        # Check agent-specific permissions
        agent_permission_map = {
            AgentType.FAMILY: AIPermission.FAMILY_MANAGEMENT,
            AgentType.WORKSPACE: AIPermission.WORKSPACE_COLLABORATION,
            AgentType.COMMERCE: AIPermission.COMMERCE_ASSISTANCE,
            AgentType.SECURITY: AIPermission.SECURITY_MONITORING
        }
        
        if request.agent_type in agent_permission_map:
            await ai_security_manager.check_ai_permissions(
                user_context,
                agent_permission_map[request.agent_type]
            )
        
        # Check rate limits
        await security_manager.check_rate_limit(user_id, "ai_session_create", limit=10, window=3600)
        
        # Clean up expired sessions in background
        background_tasks.add_task(cleanup_expired_sessions)
        
        # Check if user has too many active sessions
        user_sessions = get_user_sessions(user_id)
        active_user_sessions = [s for s in user_sessions if s.status == SessionStatus.ACTIVE]
        
        if len(active_user_sessions) >= 5:  # Limit to 5 active sessions per user
            raise HTTPException(
                status_code=429,
                detail="Too many active sessions. Please close some sessions before creating new ones."
            )
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Create session context
        session_context = SessionContext(
            session_id=session_id,
            user_id=user_id,
            agent_type=request.agent_type,
            voice_enabled=request.voice_enabled,
            preferences=request.preferences,
            settings=request.settings
        )
        
        # Set expiration
        session_context.set_expiration(request.expiration_hours)
        
        # Load user context (this would integrate with existing user management)
        session_context.user_context = {
            "user_id": user_id,
            "username": current_user.get("username", ""),
            "email": current_user.get("email", ""),
            "preferences": current_user.get("preferences", {}),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Store session
        active_sessions[session_id] = session_context
        
        # Log session creation for audit trail
        await ai_security_manager.log_ai_audit_event(
            user_context=user_context,
            session_id=session_id,
            event_type="session_management",
            agent_type=request.agent_type.value,
            action="create_session",
            details={
                "voice_enabled": request.voice_enabled,
                "expiration_hours": request.expiration_hours,
                "preferences": request.preferences
            },
            privacy_mode=ConversationPrivacyMode.PRIVATE,
            success=True
        )
        
        logger.info(f"Created AI session {session_id} for user {user_id} with agent {request.agent_type}")
        
        # Emit session start event
        event_bus = get_ai_event_bus()
        await event_bus.emit_status_update(
            session_id=session_id,
            agent_type=request.agent_type.value,
            status=EventType.SESSION_START,
            message=f"AI session started with {request.agent_type.value} agent"
        )
        
        return SessionResponse(
            session_id=session_id,
            agent_type=request.agent_type,
            status=session_context.status,
            created_at=session_context.created_at,
            last_activity=session_context.last_activity,
            expires_at=session_context.expires_at,
            websocket_connected=session_context.websocket_connected,
            voice_enabled=session_context.voice_enabled,
            message_count=len(session_context.conversation_history)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating AI session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create AI session")


@router.get("/sessions", response_model=SessionListResponse)
async def list_ai_sessions(
    current_user: dict = Depends(get_current_user),
    status: Optional[SessionStatus] = Query(None, description="Filter by session status"),
    agent_type: Optional[AgentType] = Query(None, description="Filter by agent type"),
    limit: int = Query(50, description="Maximum number of sessions to return", ge=1, le=100)
):
    """
    List AI sessions for the current user.
    
    Returns a list of AI sessions with optional filtering by status and agent type.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Get user sessions
        user_sessions = get_user_sessions(user_id)
        
        # Apply filters
        if status:
            user_sessions = [s for s in user_sessions if s.status == status]
        
        if agent_type:
            user_sessions = [s for s in user_sessions if s.agent_type == agent_type]
        
        # Sort by last activity (most recent first)
        user_sessions.sort(key=lambda s: s.last_activity, reverse=True)
        
        # Apply limit
        user_sessions = user_sessions[:limit]
        
        # Convert to response format
        session_responses = [
            SessionResponse(
                session_id=session.session_id,
                agent_type=session.agent_type,
                status=session.status,
                created_at=session.created_at,
                last_activity=session.last_activity,
                expires_at=session.expires_at,
                websocket_connected=session.websocket_connected,
                voice_enabled=session.voice_enabled,
                message_count=len(session.conversation_history)
            )
            for session in user_sessions
        ]
        
        # Count active sessions
        all_user_sessions = get_user_sessions(user_id)
        active_count = len([s for s in all_user_sessions if s.status == SessionStatus.ACTIVE])
        
        return SessionListResponse(
            sessions=session_responses,
            total_count=len(all_user_sessions),
            active_count=active_count
        )
        
    except Exception as e:
        logger.error(f"Error listing AI sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list AI sessions")


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_ai_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific AI session.
    
    Returns detailed information about an AI session including conversation history
    and current status.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Check if session exists and belongs to user
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="AI session not found")
        
        session = active_sessions[session_id]
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this AI session")
        
        return SessionResponse(
            session_id=session.session_id,
            agent_type=session.agent_type,
            status=session.status,
            created_at=session.created_at,
            last_activity=session.last_activity,
            expires_at=session.expires_at,
            websocket_connected=session.websocket_connected,
            voice_enabled=session.voice_enabled,
            message_count=len(session.conversation_history)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting AI session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get AI session")


@router.post("/sessions/{session_id}/message", response_model=MessageResponse)
async def send_message_to_ai(
    session_id: str,
    request: MessageRequest,
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Send a message to an AI agent in the specified session.
    
    This endpoint accepts text or voice messages and processes them through
    the appropriate AI agent, streaming responses back through WebSocket.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Create MCP user context for security validation
        user_context = MCPUserContext(
            user_id=user_id,
            username=current_user.get("username", ""),
            permissions=current_user.get("permissions", [])
        )
        
        # Security validation - check basic chat permissions
        await ai_security_manager.check_ai_permissions(
            user_context,
            AIPermission.BASIC_CHAT
        )
        
        # Check rate limits (both base and AI-specific)
        await security_manager.check_rate_limit(user_id, "ai_message_send", limit=60, window=60)
        await ai_security_manager.check_ai_rate_limit(
            None,  # No request object available here
            user_context,
            "message_send"
        )
        
        # Check if session exists and belongs to user
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="AI session not found")
        
        session = active_sessions[session_id]
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this AI session")
        
        if session.status != SessionStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="AI session is not active")
        
        if session.is_expired():
            session.status = SessionStatus.COMPLETED
            raise HTTPException(status_code=400, detail="AI session has expired")
        
        # Generate message ID
        message_id = str(uuid.uuid4())
        
        # Create user message
        user_message = ConversationMessage(
            id=message_id,
            session_id=session_id,
            content=request.content,
            role=MessageRole.USER,
            message_type=request.message_type,
            metadata=request.metadata,
            audio_data=request.audio_data
        )
        
        # Add message to session
        session.add_message(user_message)
        
        # Log message for audit trail
        await ai_security_manager.log_ai_audit_event(
            user_context=user_context,
            session_id=session_id,
            event_type="conversation",
            agent_type=session.agent_type.value,
            action="send_message",
            details={
                "message_id": message_id,
                "message_type": request.message_type.value,
                "content_length": len(request.content),
                "has_audio": bool(request.audio_data),
                "has_metadata": bool(request.metadata)
            },
            privacy_mode=ConversationPrivacyMode.PRIVATE,
            success=True
        )
        
        # Handle agent switching if requested
        current_agent = session.agent_type
        if request.switch_to_agent and request.switch_to_agent != session.agent_type:
            session.agent_type = request.switch_to_agent
            logger.info(f"Switched session {session_id} from {current_agent} to {request.switch_to_agent}")
            
            # Emit agent switch event
            event_bus = get_ai_event_bus()
            await event_bus.emit_status_update(
                session_id=session_id,
                agent_type=request.switch_to_agent.value,
                status=EventType.AGENT_SWITCH,
                message=f"Switched from {current_agent.value} to {request.switch_to_agent.value} agent"
            )
        
        logger.info(f"Received message in session {session_id} from user {user_id}")
        
        # Process message in background (this would integrate with the AI orchestrator)
        background_tasks.add_task(process_ai_message, session_id, user_message)
        
        return MessageResponse(
            message_id=message_id,
            session_id=session_id,
            agent_type=session.agent_type.value,
            processing_started=True,
            estimated_response_time=2.0  # Estimated 2 seconds for response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message to AI session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message to AI")


@router.delete("/sessions/{session_id}")
async def end_ai_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    End an AI session and clean up resources.
    
    This endpoint terminates an AI session, saves conversation history,
    and cleans up associated resources.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Check if session exists and belongs to user
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="AI session not found")
        
        session = active_sessions[session_id]
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this AI session")
        
        # Update session status
        session.status = SessionStatus.COMPLETED
        session.update_activity()
        
        # Emit session end event
        event_bus = get_ai_event_bus()
        await event_bus.emit_status_update(
            session_id=session_id,
            agent_type=session.agent_type.value,
            status=EventType.SESSION_END,
            message="AI session ended by user"
        )
        
        # In production, save conversation history to database here
        logger.info(f"Ended AI session {session_id} for user {user_id} with {len(session.conversation_history)} messages")
        
        # Remove from active sessions
        del active_sessions[session_id]
        
        return JSONResponse(
            status_code=200,
            content={"message": "AI session ended successfully", "session_id": session_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending AI session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to end AI session")


@router.websocket("/ws/{session_id}")
async def ai_websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    current_user: dict = Depends(get_current_user_ws)
):
    """
    WebSocket endpoint for real-time AI communication.
    
    This endpoint provides real-time bidirectional communication with AI agents,
    including token streaming, tool execution updates, and voice coordination.
    """
    error_context = create_ai_error_context(
        operation="websocket_connection",
        session_id=session_id
    )
    
    try:
        if current_user is None:
            await websocket.close(code=1008, reason="Authentication required")
            return
        
        user_id = str(current_user["_id"])
        error_context.user_id = user_id
        
        # Check if session exists and belongs to user
        if session_id not in active_sessions:
            await websocket.close(code=1008, reason="AI session not found")
            return
        
        session = active_sessions[session_id]
        if session.user_id != user_id:
            await websocket.close(code=1008, reason="Access denied to this AI session")
            return
        
        if session.is_expired():
            await websocket.close(code=1008, reason="AI session has expired")
            return
        
        # Accept WebSocket connection
        await websocket.accept()
        
        # Update session WebSocket status
        session.websocket_connected = True
        session.update_activity()
        
        # Register with event bus
        event_bus = get_ai_event_bus()
        await event_bus.register_session(session_id, user_id, websocket)
        
        logger.info(f"WebSocket connected for AI session {session_id} (user: {user_id})")
        
    except Exception as e:
        comm_error = CommunicationError(
            f"WebSocket connection failed: {str(e)}",
            context=error_context
        )
        await log_ai_error(comm_error)
        
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except:
            pass
        return
    
    try:
        # Send welcome message
        welcome_event = {
            "type": "session_ready",
            "data": {
                "session_id": session_id,
                "agent_type": session.agent_type.value,
                "voice_enabled": session.voice_enabled,
                "message": f"Connected to {session.agent_type.value} agent"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send_text(json.dumps(welcome_event))
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive message from client
                data = await websocket.receive_text()
                
                # Parse incoming message
                try:
                    message_data = json.loads(data)
                    await handle_websocket_message(session_id, message_data, websocket)
                except json.JSONDecodeError:
                    # Handle plain text messages
                    await handle_websocket_text_message(session_id, data, websocket)
                
                # Update session activity
                session.update_activity()
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message for session {session_id}: {e}")
                # Send error to client
                error_event = {
                    "type": "error",
                    "data": {"error": "Failed to process message"},
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                await websocket.send_text(json.dumps(error_event))
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for AI session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for AI session {session_id}: {e}")
    finally:
        # Clean up
        session.websocket_connected = False
        await event_bus.unregister_session(session_id, user_id, websocket)
        logger.info(f"WebSocket cleanup completed for AI session {session_id}")


async def handle_websocket_message(session_id: str, message_data: dict, websocket: WebSocket):
    """Handle structured WebSocket messages."""
    message_type = message_data.get("type", "message")
    
    if message_type == "ping":
        # Handle ping/pong for connection health
        pong_response = {
            "type": "pong",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        await websocket.send_text(json.dumps(pong_response))
    
    elif message_type == "message":
        # Handle chat messages
        content = message_data.get("content", "")
        if content:
            await handle_websocket_text_message(session_id, content, websocket)
    
    elif message_type == "voice":
        # Handle voice messages
        audio_data = message_data.get("audio_data", "")
        if audio_data:
            # Process voice message through the voice processing pipeline
            logger.info(f"Received voice message for session {session_id}")
            
            # Get session and validate voice is enabled
            if session_id in active_sessions:
                session = active_sessions[session_id]
                if session.voice_enabled:
                    # Process voice input asynchronously
                    try:
                        # Decode base64 audio data
                        import base64
                        audio_bytes = base64.b64decode(audio_data)
                        
                        # Get AI orchestrator and voice agent
                        orchestrator = get_ai_orchestrator()
                        voice_agent = orchestrator.agents.get("voice")
                        
                        if voice_agent:
                            # Create MCP user context (simplified for WebSocket)
                            mcp_context = MCPUserContext(
                                user_id=session.user_id,
                                username="websocket_user",
                                email="",
                                role="user",
                                permissions=[]
                            )
                            
                            # Process voice input through orchestrator
                            asyncio.create_task(
                                process_voice_input_through_orchestrator(session_id, audio_bytes, orchestrator)
                            )
                        else:
                            logger.warning(f"Voice agent not available for session {session_id}")
                    except Exception as e:
                        logger.error(f"Error processing WebSocket voice message: {e}")
                else:
                    logger.warning(f"Voice not enabled for session {session_id}")
            else:
                logger.warning(f"Session {session_id} not found for voice message")
    
    else:
        logger.warning(f"Unknown WebSocket message type: {message_type}")


async def handle_websocket_text_message(session_id: str, content: str, websocket: WebSocket):
    """Handle plain text WebSocket messages."""
    if session_id not in active_sessions:
        return
    
    session = active_sessions[session_id]
    
    # Create message
    message_id = str(uuid.uuid4())
    user_message = ConversationMessage(
        id=message_id,
        session_id=session_id,
        content=content,
        role=MessageRole.USER,
        message_type="text"
    )
    
    # Add to session
    session.add_message(user_message)
    
    # Process message (this would integrate with AI orchestrator)
    await process_ai_message(session_id, user_message)


async def process_ai_message(session_id: str, message: ConversationMessage):
    """
    Process an AI message (placeholder for actual AI integration).
    
    This function would integrate with the AI orchestrator to process
    messages through the appropriate AI agent and stream responses.
    """
    try:
        if session_id not in active_sessions:
            return
        
        session = active_sessions[session_id]
        event_bus = get_ai_event_bus()
        
        # Emit thinking status
        await event_bus.emit_status_update(
            session_id=session_id,
            agent_type=session.agent_type.value,
            status=EventType.THINKING,
            message="Processing your message..."
        )
        
        # Simulate AI processing (in production, this would call the AI orchestrator)
        import asyncio
        await asyncio.sleep(1)  # Simulate processing time
        
        # Emit typing status
        await event_bus.emit_status_update(
            session_id=session_id,
            agent_type=session.agent_type.value,
            status=EventType.TYPING,
            message="Generating response..."
        )
        
        # Simulate streaming response
        response_text = f"Hello! I'm the {session.agent_type.value} agent. I received your message: '{message.content}'. How can I help you today?"
        
        # Stream tokens
        words = response_text.split()
        for i, word in enumerate(words):
            token = word + (" " if i < len(words) - 1 else "")
            await event_bus.emit_token_stream(
                session_id=session_id,
                agent_type=session.agent_type.value,
                token=token
            )
            await asyncio.sleep(0.1)  # Simulate streaming delay
        
        # Create assistant response message
        response_message = ConversationMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            content=response_text,
            role=MessageRole.ASSISTANT,
            agent_type=session.agent_type.value
        )
        
        # Add to session
        session.add_message(response_message)
        
        # Emit complete response
        await event_bus.emit_event(
            event_bus.ai_event_bus.create_response_event(
                session_id=session_id,
                agent_type=session.agent_type.value,
                response=response_text
            )
        )
        
        logger.info(f"Processed AI message for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error processing AI message for session {session_id}: {e}")
        
        # Emit error event
        event_bus = get_ai_event_bus()
        await event_bus.emit_error(
            session_id=session_id,
            agent_type=session.agent_type.value if session_id in active_sessions else "unknown",
            error_message="Failed to process message",
            error_code="PROCESSING_ERROR"
        )


@router.get("/stats", response_model=SessionStatsResponse)
async def get_ai_stats(current_user: dict = Depends(get_current_user)):
    """
    Get AI usage statistics for the current user.
    
    Returns statistics about AI session usage, message counts, and preferences.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Get user sessions
        user_sessions = get_user_sessions(user_id)
        
        # Calculate statistics
        total_sessions = len(user_sessions)
        active_sessions_count = len([s for s in user_sessions if s.status == SessionStatus.ACTIVE])
        total_messages = sum(len(s.conversation_history) for s in user_sessions)
        
        # Calculate average session duration
        completed_sessions = [s for s in user_sessions if s.status == SessionStatus.COMPLETED]
        if completed_sessions:
            durations = [
                (s.last_activity - s.created_at).total_seconds() / 60
                for s in completed_sessions
            ]
            average_duration = sum(durations) / len(durations)
        else:
            average_duration = None
        
        # Find most used agent
        agent_counts = {}
        for session in user_sessions:
            agent_type = session.agent_type.value
            agent_counts[agent_type] = agent_counts.get(agent_type, 0) + 1
        
        most_used_agent = max(agent_counts.items(), key=lambda x: x[1])[0] if agent_counts else None
        
        return SessionStatsResponse(
            total_sessions=total_sessions,
            active_sessions=active_sessions_count,
            total_messages=total_messages,
            average_session_duration=average_duration,
            most_used_agent=most_used_agent
        )
        
    except Exception as e:
        logger.error(f"Error getting AI stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get AI statistics")


@router.get("/health")
async def ai_health_check():
    """
    Health check endpoint for AI orchestration system.
    
    Returns the current status of the AI system including active sessions,
    event bus status, and system health metrics.
    """
    try:
        # Clean up expired sessions
        expired_count = cleanup_expired_sessions()
        
        # Get event bus stats
        event_bus = get_ai_event_bus()
        event_stats = event_bus.get_session_stats()
        
        # Calculate system stats
        total_sessions = len(active_sessions)
        active_sessions_count = len([s for s in active_sessions.values() if s.status == SessionStatus.ACTIVE])
        total_messages = sum(len(s.conversation_history) for s in active_sessions.values())
        
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sessions": {
                "total": total_sessions,
                "active": active_sessions_count,
                "expired_cleaned": expired_count
            },
            "messages": {
                "total": total_messages
            },
            "event_bus": event_stats,
            "system": {
                "version": "1.0.0",
                "uptime": "healthy"
            }
        }
        
    except Exception as e:
        logger.error(f"AI health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.post("/sessions/{session_id}/voice/setup")
async def setup_voice_session(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Set up voice capabilities for an AI session with LiveKit integration.
    
    This endpoint configures voice processing, creates LiveKit tokens,
    and prepares the session for real-time voice communication.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Check if session exists and belongs to user
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="AI session not found")
        
        session = active_sessions[session_id]
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this AI session")
        
        if session.status != SessionStatus.ACTIVE:
            raise HTTPException(status_code=400, detail="AI session is not active")
        
        # Get AI orchestrator and voice agent
        orchestrator = get_ai_orchestrator()
        voice_agent = orchestrator.agents.get("voice")
        
        if not voice_agent:
            raise HTTPException(status_code=503, detail="Voice agent not available")
        
        # Create MCP user context
        mcp_context = MCPUserContext(
            user_id=user_id,
            username=current_user.get("username", ""),
            email=current_user.get("email", ""),
            role=current_user.get("role", "user"),
            permissions=current_user.get("permissions", [])
        )
        
        # Enable voice for the session through orchestrator
        orchestrator = get_ai_orchestrator()
        voice_enabled = await orchestrator.enable_voice_for_session(session_id)
        
        if not voice_enabled:
            raise HTTPException(status_code=503, detail="Failed to enable voice for session")
        
        # Set up voice session configuration
        voice_config = await voice_agent.setup_voice_session(session_id, mcp_context)
        
        if not voice_config:
            raise HTTPException(status_code=503, detail="Failed to set up voice session")
        
        # Update session to enable voice
        session.voice_enabled = True
        session.update_activity()
        
        logger.info(f"Voice session setup completed for {session_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "message": "Voice session setup successful",
                "session_id": session_id,
                "voice_config": voice_config
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up voice session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to set up voice session")


@router.post("/sessions/{session_id}/voice/input")
async def process_voice_input(
    session_id: str,
    audio_data: str,  # Base64 encoded audio data
    current_user: dict = Depends(get_current_user)
):
    """
    Process voice input for an AI session.
    
    This endpoint accepts base64-encoded audio data, processes it through
    speech-to-text, and routes it to the appropriate AI agent.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Check rate limits
        await security_manager.check_rate_limit(user_id, "ai_voice_input", limit=30, window=60)
        
        # Check if session exists and belongs to user
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="AI session not found")
        
        session = active_sessions[session_id]
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this AI session")
        
        if not session.voice_enabled:
            raise HTTPException(status_code=400, detail="Voice not enabled for this session")
        
        # Get AI orchestrator and voice agent
        orchestrator = get_ai_orchestrator()
        voice_agent = orchestrator.agents.get("voice")
        
        if not voice_agent:
            raise HTTPException(status_code=503, detail="Voice agent not available")
        
        # Decode audio data
        import base64
        try:
            audio_bytes = base64.b64decode(audio_data)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid audio data format")
        
        # Create MCP user context
        mcp_context = MCPUserContext(
            user_id=user_id,
            username=current_user.get("username", ""),
            email=current_user.get("email", ""),
            role=current_user.get("role", "user"),
            permissions=current_user.get("permissions", [])
        )
        
        # Process voice input through orchestrator
        # The results will be streamed through WebSocket
        asyncio.create_task(
            process_voice_input_through_orchestrator(session_id, audio_bytes, orchestrator)
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Voice input processing started",
                "session_id": session_id,
                "processing": True
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing voice input for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process voice input")


async def process_voice_input_through_orchestrator(
    session_id: str, 
    audio_bytes: bytes, 
    orchestrator: AgentOrchestrator
):
    """Process voice input through orchestrator and stream results."""
    try:
        # Process voice input through the orchestrator
        async for event in orchestrator.process_voice_input(session_id, audio_bytes):
            # Events are automatically emitted through the event bus
            pass
            
    except Exception as e:
        logger.error(f"Orchestrator voice processing failed for session {session_id}: {e}")
        
        # Emit error event
        event_bus = get_ai_event_bus()
        await event_bus.emit_error(
            session_id=session_id,
            agent_type="voice",
            error_message="Voice processing failed",
            error_code="VOICE_PROCESSING_ERROR"
        )


@router.get("/sessions/{session_id}/voice/token")
async def get_voice_token(
    session_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a LiveKit access token for voice communication.
    
    This endpoint provides a LiveKit token that can be used by the frontend
    to establish real-time voice communication for the AI session.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Check if session exists and belongs to user
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="AI session not found")
        
        session = active_sessions[session_id]
        if session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this AI session")
        
        # Get AI orchestrator and voice agent
        orchestrator = get_ai_orchestrator()
        voice_agent = orchestrator.agents.get("voice")
        
        if not voice_agent:
            raise HTTPException(status_code=503, detail="Voice agent not available")
        
        # Create LiveKit token
        livekit_config = await voice_agent.create_livekit_token(
            user_id=user_id,
            room_name=f"ai_voice_{session_id}"
        )
        
        if not livekit_config:
            raise HTTPException(status_code=503, detail="LiveKit not configured or token creation failed")
        
        return JSONResponse(
            status_code=200,
            content={
                "session_id": session_id,
                "livekit": livekit_config,
                "voice_enabled": True
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting voice token for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get voice token")

# Performance and Monitoring Endpoints

@router.get("/performance/metrics")
async def get_performance_metrics(current_user: dict = Depends(get_current_user)):
    """
    Get comprehensive performance metrics for the AI orchestration system.
    
    Returns detailed metrics about model performance, caching, memory usage,
    and resource utilization. Requires admin role for full metrics.
    """
    try:
        user_role = current_user.get("role", "user")
        
        # Get AI orchestrator
        orchestrator = get_ai_orchestrator()
        if not orchestrator:
            raise HTTPException(status_code=503, detail="AI orchestrator not available")
        
        # Get performance metrics
        metrics = await orchestrator.get_performance_metrics()
        
        # Filter metrics based on user role
        if user_role != "admin":
            # Non-admin users get limited metrics
            filtered_metrics = {
                "sessions": metrics.get("sessions", {}),
                "timestamp": metrics.get("timestamp"),
                "model_engine": {
                    "requests": metrics.get("model_engine", {}).get("requests", {}),
                    "performance": {
                        "avg_response_time_ms": metrics.get("model_engine", {}).get("performance", {}).get("avg_response_time_ms"),
                        "target_latency_ms": metrics.get("model_engine", {}).get("performance", {}).get("target_latency_ms")
                    }
                }
            }
            return JSONResponse(content=filtered_metrics)
        
        return JSONResponse(content=metrics)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get performance metrics")


@router.get("/performance/health")
async def get_detailed_health_check(current_user: dict = Depends(get_current_user)):
    """
    Get detailed health check for all AI orchestration components.
    
    Returns comprehensive health status including model engine, memory layer,
    resource manager, and individual agent health.
    """
    try:
        # Get AI orchestrator
        orchestrator = get_ai_orchestrator()
        if not orchestrator:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": "AI orchestrator not available",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        # Get comprehensive health check
        health_status = await orchestrator.health_check()
        
        # Add route-level session info
        health_status["route_sessions"] = {
            "active_count": len(active_sessions),
            "total_messages": sum(len(s.conversation_history) for s in active_sessions.values())
        }
        
        # Determine HTTP status code based on health
        status_code = 200
        overall_status = health_status.get("orchestrator", "unknown")
        
        if overall_status == "unhealthy":
            status_code = 503
        elif overall_status in ["degraded", "under_pressure"]:
            status_code = 200  # Still operational but with warnings
        
        return JSONResponse(
            status_code=status_code,
            content=health_status
        )
        
    except Exception as e:
        logger.error(f"Error getting detailed health check: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.get("/health/error-handling")
async def ai_error_handling_health():
    """
    Get detailed health status of AI error handling and recovery systems.
    
    Returns comprehensive information about error handling components,
    recovery managers, circuit breakers, and system resilience.
    """
    try:
        orchestrator = get_ai_orchestrator()
        if not orchestrator:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": "AI orchestrator not initialized",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        # Get error handling health
        error_health = await orchestrator.get_error_handling_health()
        
        # Add additional system metrics
        error_health["system_metrics"] = {
            "active_sessions": len(active_sessions),
            "total_sessions_created": len(active_sessions),  # In production, this would be from metrics
            "error_handling_version": "1.0.0",
            "recovery_capabilities": [
                "session_recovery",
                "model_fallback",
                "voice_degradation",
                "communication_restoration",
                "comprehensive_recovery"
            ]
        }
        
        # Determine status
        overall_healthy = error_health.get("overall_healthy", False)
        status_code = 200 if overall_healthy else 503
        
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "healthy" if overall_healthy else "degraded",
                "error_handling": error_health,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error handling health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@router.post("/performance/cache/invalidate")
async def invalidate_caches(
    pattern: str = Query(default="*", description="Cache pattern to invalidate"),
    current_user: dict = Depends(get_current_user)
):
    """
    Invalidate AI system caches.
    
    Allows administrators to clear cached data for performance optimization
    or troubleshooting. Supports pattern matching for selective invalidation.
    """
    try:
        # Check admin permissions
        user_role = current_user.get("role", "user")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get AI orchestrator
        orchestrator = get_ai_orchestrator()
        if not orchestrator:
            raise HTTPException(status_code=503, detail="AI orchestrator not available")
        
        # Invalidate caches
        invalidation_results = await orchestrator.invalidate_caches(pattern)
        
        logger.info(f"Cache invalidation requested by user {current_user['_id']} with pattern '{pattern}'")
        
        return JSONResponse(
            content={
                "message": "Cache invalidation completed",
                "pattern": pattern,
                "results": invalidation_results,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invalidating caches: {e}")
        raise HTTPException(status_code=500, detail="Failed to invalidate caches")


@router.get("/performance/sessions")
async def get_session_performance(current_user: dict = Depends(get_current_user)):
    """
    Get performance information about active AI sessions.
    
    Returns resource usage, activity metrics, and performance data
    for all active sessions. Admin users see all sessions, regular users
    see only their own sessions.
    """
    try:
        user_id = str(current_user["_id"])
        user_role = current_user.get("role", "user")
        
        # Get AI orchestrator
        orchestrator = get_ai_orchestrator()
        if not orchestrator:
            raise HTTPException(status_code=503, detail="AI orchestrator not available")
        
        # Get session performance data from resource manager
        resource_manager = orchestrator.resource_manager
        all_sessions = resource_manager.list_active_sessions()
        
        # Filter sessions based on user role
        if user_role == "admin":
            # Admin sees all sessions
            sessions = all_sessions
        else:
            # Regular users see only their own sessions
            sessions = [s for s in all_sessions if s.get("user_id") == user_id]
        
        # Get resource status
        resource_status = resource_manager.get_resource_status()
        
        return JSONResponse(
            content={
                "sessions": sessions,
                "resource_status": resource_status,
                "summary": {
                    "total_sessions": len(sessions),
                    "user_sessions": len([s for s in sessions if s.get("user_id") == user_id]),
                    "system_health": resource_status.get("status", "unknown")
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session performance")


@router.post("/performance/cleanup")
async def trigger_cleanup(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Trigger manual cleanup of AI system resources.
    
    Allows administrators to manually trigger cleanup of expired sessions,
    old cache entries, and other maintenance tasks.
    """
    try:
        # Check admin permissions
        user_role = current_user.get("role", "user")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get AI orchestrator
        orchestrator = get_ai_orchestrator()
        if not orchestrator:
            raise HTTPException(status_code=503, detail="AI orchestrator not available")
        
        # Trigger cleanup in background
        async def perform_cleanup():
            try:
                # Cleanup expired sessions at route level
                expired_count = cleanup_expired_sessions()
                
                # Trigger resource manager cleanup
                resource_manager = orchestrator.resource_manager
                await resource_manager._perform_cleanup()
                
                # Cleanup old conversation data
                memory_layer = orchestrator.memory_layer
                old_conversations = await memory_layer.cleanup_old_conversations(days=30)
                
                logger.info(
                    f"Manual cleanup completed: {expired_count} expired sessions, "
                    f"{old_conversations} old conversations"
                )
                
            except Exception as e:
                logger.error(f"Manual cleanup failed: {e}")
        
        background_tasks.add_task(perform_cleanup)
        
        return JSONResponse(
            content={
                "message": "Cleanup task started",
                "status": "running",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering cleanup: {e}")
        raise HTTPException(status_code=500, detail="Failed to trigger cleanup")


@router.get("/performance/model/warmup")
async def get_model_warmup_status(current_user: dict = Depends(get_current_user)):
    """
    Get model warmup status and performance information.
    
    Returns information about which models are warmed up and their
    performance characteristics.
    """
    try:
        # Get AI orchestrator
        orchestrator = get_ai_orchestrator()
        if not orchestrator:
            raise HTTPException(status_code=503, detail="AI orchestrator not available")
        
        # Get model engine metrics
        model_metrics = await orchestrator.model_engine.get_performance_metrics()
        
        return JSONResponse(
            content={
                "warmup_status": model_metrics.get("models", {}),
                "performance": model_metrics.get("performance", {}),
                "cache": model_metrics.get("cache", {}),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model warmup status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get model warmup status")


@router.post("/performance/model/warmup/{model_name}")
async def warmup_model(
    model_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually warm up a specific model.
    
    Allows administrators to pre-warm models for better performance.
    """
    try:
        # Check admin permissions
        user_role = current_user.get("role", "user")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get AI orchestrator
        orchestrator = get_ai_orchestrator()
        if not orchestrator:
            raise HTTPException(status_code=503, detail="AI orchestrator not available")
        
        # Warm up the model
        success = await orchestrator.model_engine.warm_model(model_name)
        
        if success:
            return JSONResponse(
                content={
                    "message": f"Model '{model_name}' warmed up successfully",
                    "model": model_name,
                    "status": "warmed",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to warm up model '{model_name}'"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error warming up model {model_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to warm up model '{model_name}'")


# Performance Benchmark Endpoints

@router.post("/performance/benchmarks/run")
async def run_performance_benchmarks(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Run comprehensive performance benchmarks for the AI orchestration system.
    
    Executes a full suite of performance tests to ensure sub-300ms response times
    and optimal system performance. Results are stored for historical tracking.
    """
    try:
        # Check admin permissions for full benchmarks
        user_role = current_user.get("role", "user")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required to run benchmarks")
        
        # Import benchmark functions
        from second_brain_database.integrations.ai_orchestration.performance_benchmarks import (
            run_performance_benchmarks as run_benchmarks
        )
        
        # Run benchmarks in background
        async def execute_benchmarks():
            try:
                logger.info(f"Starting performance benchmarks requested by user {current_user['_id']}")
                benchmark_suite = await run_benchmarks()
                
                logger.info(
                    f"Performance benchmarks completed: {benchmark_suite.success_rate:.1f}% success rate, "
                    f"avg response time: {benchmark_suite.average_response_time:.2f}ms"
                )
                
            except Exception as e:
                logger.error(f"Performance benchmark execution failed: {e}")
        
        background_tasks.add_task(execute_benchmarks)
        
        return JSONResponse(
            content={
                "message": "Performance benchmark suite started",
                "status": "running",
                "target_latency_ms": 300,
                "estimated_duration_minutes": 5,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting performance benchmarks: {e}")
        raise HTTPException(status_code=500, detail="Failed to start performance benchmarks")


@router.get("/performance/benchmarks/results")
async def get_benchmark_results(current_user: dict = Depends(get_current_user)):
    """
    Get the latest performance benchmark results.
    
    Returns the most recent benchmark test results including response times,
    success rates, and performance analysis.
    """
    try:
        # Import benchmark functions
        from second_brain_database.integrations.ai_orchestration.performance_benchmarks import (
            get_benchmark_suite
        )
        
        # Get benchmark suite instance
        benchmark_suite = await get_benchmark_suite()
        
        # Get latest results
        latest_results = await benchmark_suite.get_latest_benchmark_results()
        
        if not latest_results:
            return JSONResponse(
                content={
                    "message": "No benchmark results available",
                    "status": "no_data",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
        
        # Add performance status
        meets_target = latest_results.get("meets_target", False)
        avg_response_time = latest_results.get("average_response_time", 0)
        target_latency = 300  # 300ms target
        
        performance_status = {
            "meets_target": meets_target,
            "performance_grade": "PASS" if meets_target else "FAIL",
            "target_latency_ms": target_latency,
            "actual_latency_ms": avg_response_time,
            "performance_ratio": avg_response_time / target_latency if target_latency > 0 else 0
        }
        
        return JSONResponse(
            content={
                "benchmark_results": latest_results,
                "performance_status": performance_status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting benchmark results: {e}")
        raise HTTPException(status_code=500, detail="Failed to get benchmark results")


@router.get("/performance/benchmarks/metrics")
async def get_benchmark_metrics(current_user: dict = Depends(get_current_user)):
    """
    Get current performance metrics from ongoing monitoring.
    
    Returns real-time performance metrics collected during normal operation,
    including response times, error rates, and operation counts.
    """
    try:
        # Import benchmark functions
        from second_brain_database.integrations.ai_orchestration.performance_benchmarks import (
            get_current_performance_metrics
        )
        
        # Get current metrics
        metrics = await get_current_performance_metrics()
        
        # Calculate performance summary
        avg_times = metrics.get("average_response_times", {})
        error_rates = metrics.get("error_rates", {})
        
        # Find overall performance status
        target_latency = 300  # 300ms target
        overall_performance = "GOOD"
        
        for operation, avg_time in avg_times.items():
            if avg_time > target_latency:
                overall_performance = "DEGRADED"
                break
            elif avg_time > target_latency * 0.8:  # 80% of target
                overall_performance = "WARNING"
        
        # Check error rates
        for operation, error_rate in error_rates.items():
            if error_rate > 10:  # More than 10% error rate
                overall_performance = "DEGRADED"
                break
            elif error_rate > 5:  # More than 5% error rate
                if overall_performance == "GOOD":
                    overall_performance = "WARNING"
        
        performance_summary = {
            "overall_status": overall_performance,
            "target_latency_ms": target_latency,
            "operations_monitored": len(avg_times),
            "total_operations": sum(metrics.get("operation_counts", {}).values()),
            "total_errors": sum(metrics.get("error_counts", {}).values())
        }
        
        return JSONResponse(
            content={
                "metrics": metrics,
                "performance_summary": performance_summary,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting benchmark metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get benchmark metrics")


@router.post("/performance/benchmarks/continuous/start")
async def start_continuous_monitoring(
    interval_minutes: int = Query(default=30, description="Monitoring interval in minutes", ge=5, le=1440),
    current_user: dict = Depends(get_current_user)
):
    """
    Start continuous performance monitoring.
    
    Begins automated performance monitoring that runs benchmarks at regular
    intervals to detect performance regressions and ensure consistent performance.
    """
    try:
        # Check admin permissions
        user_role = current_user.get("role", "user")
        if user_role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Import benchmark functions
        from second_brain_database.integrations.ai_orchestration.performance_benchmarks import (
            start_continuous_monitoring
        )
        
        # Start continuous monitoring (this runs in background)
        asyncio.create_task(start_continuous_monitoring(interval_minutes))
        
        logger.info(
            f"Continuous performance monitoring started by user {current_user['_id']} "
            f"with {interval_minutes} minute intervals"
        )
        
        return JSONResponse(
            content={
                "message": "Continuous performance monitoring started",
                "interval_minutes": interval_minutes,
                "status": "running",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting continuous monitoring: {e}")
        raise HTTPException(status_code=500, detail="Failed to start continuous monitoring")


@router.get("/performance/benchmarks/status")
async def get_benchmark_status(current_user: dict = Depends(get_current_user)):
    """
    Get the current status of performance benchmarking system.
    
    Returns information about benchmark configuration, recent results,
    and system performance status.
    """
    try:
        # Import benchmark functions
        from second_brain_database.integrations.ai_orchestration.performance_benchmarks import (
            get_benchmark_suite
        )
        
        # Get benchmark suite
        benchmark_suite = await get_benchmark_suite()
        
        # Get latest results
        latest_results = await benchmark_suite.get_latest_benchmark_results()
        
        # Get current metrics
        current_metrics = await benchmark_suite.get_performance_metrics()
        
        # Calculate status
        status = {
            "benchmark_system": "operational",
            "target_latency_ms": benchmark_suite.target_latency_ms,
            "last_benchmark": latest_results.get("timestamp") if latest_results else None,
            "meets_performance_target": latest_results.get("meets_target", False) if latest_results else None,
            "current_monitoring": {
                "active": len(current_metrics.get("operation_counts", {})) > 0,
                "operations_tracked": len(current_metrics.get("operation_counts", {})),
                "last_updated": current_metrics.get("last_updated")
            }
        }
        
        # Performance health check
        if latest_results:
            avg_response_time = latest_results.get("average_response_time", 0)
            success_rate = latest_results.get("success_rate", 0)
            
            if success_rate < 95:
                status["health"] = "degraded"
                status["health_reason"] = f"Low success rate: {success_rate:.1f}%"
            elif avg_response_time > benchmark_suite.target_latency_ms:
                status["health"] = "degraded"
                status["health_reason"] = f"High latency: {avg_response_time:.2f}ms"
            else:
                status["health"] = "healthy"
        else:
            status["health"] = "unknown"
            status["health_reason"] = "No benchmark data available"
        
        return JSONResponse(
            content={
                "status": status,
                "latest_results_summary": {
                    "average_response_time_ms": latest_results.get("average_response_time") if latest_results else None,
                    "success_rate_percent": latest_results.get("success_rate") if latest_results else None,
                    "total_tests": latest_results.get("total_tests") if latest_results else None,
                    "meets_target": latest_results.get("meets_target") if latest_results else None
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting benchmark status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get benchmark status")