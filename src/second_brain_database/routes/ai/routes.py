"""
AI agent orchestration routes for chat sessions and real-time communication.

This module provides REST API endpoints for AI agent interactions including:
- AI session creation and management
- Real-time chat messaging with streaming support
- Agent switching and configuration
- Voice message handling and processing
- Tool execution tracking and results
- Session history and conversation management

All endpoints require authentication and follow the established security patterns.
"""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse

from second_brain_database.managers.ai_session_manager import (
    AISessionError,
    InvalidAgentType,
    MessageLimitExceeded,
    SessionExpired,
    SessionLimitExceeded,
    SessionNotFound,
    ai_session_manager,
    AgentType,
    MessageType,
    MessageRole,
    SessionStatus,
)
from second_brain_database.utils.error_handling import (
    ErrorContext, ErrorSeverity, create_user_friendly_error, sanitize_sensitive_data
)
from second_brain_database.utils.error_monitoring import record_error_event
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.managers.ai_analytics_manager import ai_analytics_manager
from second_brain_database.routes.auth import enforce_all_lockdowns
from second_brain_database.utils.ai_metrics import ai_performance_monitor, performance_timer, PerformanceTimer
from second_brain_database.models.ai_models import (
    CreateAISessionRequest,
    SendMessageRequest,
    SwitchAgentRequest,
    UpdateSessionPreferencesRequest,
    AISessionResponse,
    MessageResponse,
    ChatMessageResponse,
    AgentConfigResponse,
    AIHealthResponse,
    AIErrorResponse,
)
from .monitoring import router as monitoring_router

logger = get_logger(prefix="[AI Routes]")

router = APIRouter(prefix="/ai", tags=["AI"])

# Include monitoring routes
router.include_router(monitoring_router)


@router.post("/sessions", response_model=AISessionResponse, status_code=status.HTTP_201_CREATED)
async def create_ai_session(
    request: Request,
    session_request: CreateAISessionRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> AISessionResponse:
    """
    Create a new AI chat session with the specified agent.
    
    Creates a new AI session with the selected agent type and returns session details.
    The session will be active for the configured timeout period and supports real-time
    communication via WebSocket connections.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Requirements:**
    - User must not have reached their maximum concurrent session limit
    - Agent type must be valid and accessible to the user
    - Security agent requires admin permissions
    
    **Returns:**
    - Session information including ID, agent config, and expiration details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request, 
        f"ai_session_create_{user_id}", 
        rate_limit_requests=10, 
        rate_limit_period=3600
    )
    
    # Create error context for comprehensive error handling
    error_context = ErrorContext(
        operation="create_ai_session_api",
        user_id=user_id,
        request_id=getattr(request.state, "request_id", None) if hasattr(request, "state") else None,
        ip_address=getattr(request.client, "host", "unknown") if request.client else "unknown",
        metadata={
            "agent_type": session_request.agent_type,
            "voice_enabled": session_request.voice_enabled,
            "endpoint": "/ai/sessions"
        }
    )
    
    try:
        # Track AI operation with metrics
        with PerformanceTimer(ai_performance_monitor, "create_session", metadata={
            "agent_type": session_request.agent_type,
            "user_id": user_id
        }):
            # Check if security agent requires admin permissions
            if session_request.agent_type == "security":
                user_role = current_user.get("role", "user")
                if user_role != "admin":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "error": "INSUFFICIENT_PERMISSIONS",
                            "message": "Security agent requires admin permissions"
                        }
                    )
            
            # Create AI session
            session_data = await ai_session_manager.create_session(
                user_id=user_id,
                agent_type=AgentType(session_request.agent_type),
                voice_enabled=session_request.voice_enabled,
                context=session_request.preferences
            )
            
            # Record analytics event
            await ai_analytics_manager.record_usage_event(
                user_id=user_id,
                session_id=session_data["session_id"],
                agent_type=session_request.agent_type,
                event_type="session_created",
                metadata={
                    "voice_enabled": session_request.voice_enabled,
                    "preferences": session_request.preferences
                }
            )
            
            # Record session start in metrics
            ai_performance_monitor.start_session(session_data["session_id"])
        
        logger.info("AI session created successfully: %s by user %s with agent %s", 
                   session_data["session_id"], user_id, session_request.agent_type)
        
        # Build agent config response
        agent_config = session_data.get("agent_config", {})
        agent_config_response = AgentConfigResponse(
            agent_type=session_request.agent_type,
            name=agent_config.get("name", "Unknown Agent"),
            description=agent_config.get("description", ""),
            capabilities=agent_config.get("capabilities", []),
            tools=agent_config.get("tools", []),
            voice_enabled=agent_config.get("voice_enabled", False),
            admin_only=agent_config.get("admin_only", False)
        )
        
        return AISessionResponse(
            session_id=session_data["session_id"],
            user_id=user_id,
            agent_type=session_data["agent_type"],
            status=session_data["status"],
            created_at=session_data["created_at"],
            last_activity=session_data["created_at"],
            expires_at=session_data["expires_at"],
            websocket_connected=False,
            voice_enabled=session_data["voice_enabled"],
            message_count=0,
            preferences=session_data.get("context", {}),
            metadata={},
            agent_config=agent_config_response
        )
        
    except SessionLimitExceeded as e:
        # Record error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.HIGH)
        
        logger.warning("AI session creation failed - limit exceeded for user %s: %s", user_id, e)
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "SESSION_LIMIT_EXCEEDED",
                "message": str(e),
                "current_count": e.context.get("current_count"),
                "max_allowed": e.context.get("max_allowed")
            }
        )
            
    except InvalidAgentType as e:
        # Record error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.MEDIUM)
        
        logger.warning("AI session creation failed - invalid agent type for user %s: %s", user_id, e)
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_AGENT_TYPE",
                "message": str(e),
                "valid_types": e.context.get("valid_types", [])
            }
        )
        
    except AISessionError as e:
        # Record error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.HIGH)
        
        logger.error("AI session creation failed for user %s: %s", user_id, e)
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": str(e)
            }
        )
            
    except Exception as e:
        # Record unexpected error for monitoring
        await record_error_event(e, error_context, ErrorSeverity.CRITICAL)
        
        logger.error("Unexpected error in AI session creation for user %s: %s", user_id, e, exc_info=True)
        
        # Create user-friendly error response for unexpected errors
        user_friendly_error = create_user_friendly_error(e, error_context)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=user_friendly_error['error']
        )


@router.get("/sessions", response_model=List[AISessionResponse])
async def list_ai_sessions(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
    status_filter: Optional[str] = Query(None, description="Filter by session status"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip")
) -> List[AISessionResponse]:
    """
    Get all AI sessions for the current user.
    
    Returns a list of AI sessions with detailed information including agent configuration,
    message counts, and connection status. Supports filtering and pagination.
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Returns:**
    - List of AI sessions with detailed information
    - Empty list if user has no sessions
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_sessions_list_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        # Parse status filter
        status_enum = None
        if status_filter:
            try:
                status_enum = SessionStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_STATUS_FILTER",
                        "message": f"Invalid status '{status_filter}'. Valid values: {[s.value for s in SessionStatus]}"
                    }
                )
        
        # Get user sessions
        sessions_data = await ai_session_manager.list_user_sessions(
            user_id=user_id,
            status=status_enum,
            limit=limit,
            offset=offset
        )
        
        sessions = sessions_data.get("sessions", [])
        
        logger.debug("Retrieved %d AI sessions for user %s", len(sessions), user_id)
        
        session_responses = []
        for session in sessions:
            # Build agent config response
            agent_config = session.get("agent_config", {})
            agent_config_response = AgentConfigResponse(
                agent_type=session.get("agent_type", "unknown"),
                name=agent_config.get("name", "Unknown Agent"),
                description=agent_config.get("description", ""),
                capabilities=agent_config.get("capabilities", []),
                tools=agent_config.get("tools", []),
                voice_enabled=agent_config.get("voice_enabled", False),
                admin_only=agent_config.get("admin_only", False)
            )
            
            session_responses.append(AISessionResponse(
                session_id=session["session_id"],
                user_id=session["user_id"],
                agent_type=session["agent_type"],
                status=session["status"],
                created_at=session["created_at"],
                last_activity=session.get("last_activity", session["created_at"]),
                expires_at=session.get("expires_at"),
                websocket_connected=session.get("websocket_connected", False),
                voice_enabled=session.get("voice_enabled", False),
                message_count=session.get("message_count", 0),
                preferences=session.get("context", {}),
                metadata=session.get("metadata", {}),
                agent_config=agent_config_response
            ))
        
        return session_responses
        
    except AISessionError as e:
        logger.error("Failed to get AI sessions for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "SESSION_RETRIEVAL_FAILED",
                "message": "Failed to retrieve AI session information"
            }
        )


@router.get("/sessions/{session_id}", response_model=AISessionResponse)
async def get_ai_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> AISessionResponse:
    """
    Get detailed information about a specific AI session.
    
    Returns comprehensive session information including agent configuration,
    conversation statistics, and current connection status.
    
    **Rate Limiting:** 60 requests per hour per user
    
    **Requirements:**
    - User must own the session or have appropriate permissions
    - Session must exist and not be expired
    
    **Returns:**
    - Detailed session information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_session_get_{user_id}",
        rate_limit_requests=60,
        rate_limit_period=3600
    )
    
    try:
        # Get session data
        session = await ai_session_manager.get_session(session_id, user_id)
        
        # Build agent config response
        agent_config = session.get("agent_config", {})
        agent_config_response = AgentConfigResponse(
            agent_type=session.get("agent_type", "unknown"),
            name=agent_config.get("name", "Unknown Agent"),
            description=agent_config.get("description", ""),
            capabilities=agent_config.get("capabilities", []),
            tools=agent_config.get("tools", []),
            voice_enabled=agent_config.get("voice_enabled", False),
            admin_only=agent_config.get("admin_only", False)
        )
        
        return AISessionResponse(
            session_id=session["session_id"],
            user_id=session["user_id"],
            agent_type=session["agent_type"],
            status=session["status"],
            created_at=session["created_at"],
            last_activity=session.get("last_activity", session["created_at"]),
            expires_at=session.get("expires_at"),
            websocket_connected=session.get("websocket_connected", False),
            voice_enabled=session.get("voice_enabled", False),
            message_count=session.get("message_count", 0),
            preferences=session.get("context", {}),
            metadata=session.get("metadata", {}),
            agent_config=agent_config_response
        )
        
    except SessionNotFound as e:
        logger.warning("AI session not found: %s for user %s", session_id, user_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SESSION_NOT_FOUND",
                "message": str(e)
            }
        )
    except SessionExpired as e:
        logger.warning("AI session expired: %s for user %s", session_id, user_id)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": "SESSION_EXPIRED",
                "message": str(e),
                "expired_at": e.context.get("expired_at")
            }
        )
    except AISessionError as e:
        logger.error("Failed to get AI session %s for user %s: %s", session_id, user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": str(e)
            }
        )


@router.post("/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    request: Request,
    session_id: str,
    message_request: SendMessageRequest,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> MessageResponse:
    """
    Send a message to an AI session.
    
    Sends a message to the specified AI session and triggers agent processing.
    The response will be delivered via WebSocket for real-time streaming.
    
    **Rate Limiting:** 60 messages per hour per user
    
    **Requirements:**
    - User must own the session
    - Session must be active and not expired
    - Message content must be within limits
    
    **Returns:**
    - Message confirmation with processing details
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_message_send_{user_id}",
        rate_limit_requests=60,
        rate_limit_period=3600
    )
    
    try:
        # Track message sending operation
        with PerformanceTimer(ai_performance_monitor, "send_message", session_id, metadata={
            "user_id": user_id
        }):
            # Send message to session
            message_data = await ai_session_manager.send_message(
                session_id=session_id,
                content=message_request.content,
                message_type=MessageType(message_request.message_type),
                role=MessageRole.USER,
                metadata=message_request.metadata,
                user_id=user_id
            )
            
            # Get session info for analytics
            session_info = await ai_session_manager.get_session(session_id, user_id)
            agent_type = session_info.get("agent_type", "unknown")
            
            # Record analytics event
            await ai_analytics_manager.record_usage_event(
                user_id=user_id,
                session_id=session_id,
                agent_type=agent_type,
                event_type="message_sent",
                metadata={
                    "message_type": message_request.message_type,
                    "content_length": len(message_request.content)
                }
            )
            
            # Record message metrics
            ai_performance_monitor.record_metric("message_sent", 1, {
                "agent_type": agent_type,
                "message_type": message_request.message_type,
                "role": "user",
                "token_count": len(message_request.content.split())
            })
        
        logger.info("Message sent to AI session %s: %s", session_id, message_request.message_type)
        
        return MessageResponse(
            message_id=message_data["message_id"],
            session_id=session_id,
            status="sent",
            timestamp=message_data["timestamp"],
            processing_time_ms=None  # Will be updated when processing completes
        )
        
    except SessionNotFound as e:
        logger.warning("AI session not found for message: %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SESSION_NOT_FOUND",
                "message": str(e)
            }
        )
    except SessionExpired as e:
        logger.warning("AI session expired for message: %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "error": "SESSION_EXPIRED",
                "message": str(e)
            }
        )
    except MessageLimitExceeded as e:
        logger.warning("Message limit exceeded for session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "MESSAGE_LIMIT_EXCEEDED",
                "message": str(e),
                "current_count": e.context.get("current_count"),
                "max_allowed": e.context.get("max_allowed")
            }
        )
    except AISessionError as e:
        logger.error("Failed to send message to session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": e.error_code,
                "message": str(e)
            }
        )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_session_messages(
    request: Request,
    session_id: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip")
) -> List[ChatMessageResponse]:
    """
    Get conversation history for an AI session.
    
    Returns the conversation history with pagination support. Messages are returned
    in chronological order (oldest first).
    
    **Rate Limiting:** 30 requests per hour per user
    
    **Requirements:**
    - User must own the session
    - Session must exist
    
    **Returns:**
    - List of conversation messages with metadata
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_messages_get_{user_id}",
        rate_limit_requests=30,
        rate_limit_period=3600
    )
    
    try:
        # Get session history
        messages = await ai_session_manager.get_session_history(
            session_id=session_id,
            limit=limit,
            offset=offset,
            user_id=user_id
        )
        
        logger.debug("Retrieved %d messages for AI session %s", len(messages), session_id)
        
        message_responses = []
        for message in messages:
            message_responses.append(ChatMessageResponse(
                message_id=message["message_id"],
                session_id=message["session_id"],
                content=message["content"],
                role=message["role"],
                agent_type=message.get("agent_type"),
                timestamp=message["timestamp"],
                message_type=message["message_type"],
                metadata=message.get("metadata", {}),
                audio_data=message.get("audio_data")
            ))
        
        return message_responses
        
    except SessionNotFound as e:
        logger.warning("AI session not found for messages: %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SESSION_NOT_FOUND",
                "message": str(e)
            }
        )
    except AISessionError as e:
        logger.error("Failed to get messages for session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": str(e)
            }
        )


@router.delete("/sessions/{session_id}")
async def end_ai_session(
    request: Request,
    session_id: str,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> JSONResponse:
    """
    End an AI session and clean up resources.
    
    Terminates the AI session, closes any WebSocket connections, and cleans up
    associated resources. The session cannot be resumed after termination.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Requirements:**
    - User must own the session
    - Session must exist
    
    **Returns:**
    - Success confirmation
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_session_end_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        # Get session info before ending
        session_info = await ai_session_manager.get_session(session_id, user_id)
        agent_type = session_info.get("agent_type", "unknown")
        
        # Track session end operation
        with PerformanceTimer(ai_performance_monitor, "end_session", session_id, metadata={
            "agent_type": agent_type,
            "user_id": user_id
        }):
            # End the session
            await ai_session_manager.end_session(session_id, user_id)
            
            # Record analytics event
            await ai_analytics_manager.record_usage_event(
                user_id=user_id,
                session_id=session_id,
                agent_type=agent_type,
                event_type="session_ended"
            )
            
            # Record session end in metrics
            ai_performance_monitor.end_session(session_id)
        
        logger.info("AI session ended: %s by user %s", session_id, user_id)
        
        return JSONResponse(
            content={
                "status": "success",
                "message": "AI session ended successfully",
                "session_id": session_id
            },
            status_code=status.HTTP_200_OK
        )
        
    except SessionNotFound as e:
        logger.warning("AI session not found for termination: %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SESSION_NOT_FOUND",
                "message": str(e)
            }
        )
    except AISessionError as e:
        logger.error("Failed to end AI session %s: %s", session_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": e.error_code,
                "message": str(e)
            }
        )


@router.get("/agents", response_model=List[AgentConfigResponse])
async def get_available_agents(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> List[AgentConfigResponse]:
    """
    Get list of available AI agents and their configurations.
    
    Returns information about all AI agents available to the current user,
    including their capabilities, tools, and access requirements.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Returns:**
    - List of available agents with configuration details
    """
    user_id = str(current_user["_id"])
    user_role = current_user.get("role", "user")
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_agents_list_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        # Get all agent configurations
        agent_configs = []
        
        for agent_type in AgentType:
            # Get agent config from session manager
            config = ai_session_manager._get_agent_config(agent_type)
            
            # Check if user has access to this agent
            if config.get("admin_only", False) and user_role != "admin":
                continue
            
            agent_configs.append(AgentConfigResponse(
                agent_type=agent_type.value,
                name=config.get("name", "Unknown Agent"),
                description=config.get("description", ""),
                capabilities=config.get("capabilities", []),
                tools=config.get("tools", []),
                voice_enabled=config.get("voice_enabled", False),
                admin_only=config.get("admin_only", False)
            ))
        
        logger.debug("Retrieved %d available agents for user %s", len(agent_configs), user_id)
        
        return agent_configs
        
    except Exception as e:
        logger.error("Failed to get available agents for user %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "AGENTS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve available agents"
            }
        )


@router.get("/analytics/user", response_model=dict)
async def get_user_ai_analytics(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze")
) -> dict:
    """
    Get AI usage analytics for the current user.
    
    Returns comprehensive analytics including usage patterns, agent preferences,
    and performance metrics for the specified time period.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Returns:**
    - User-specific AI analytics and usage patterns
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_analytics_user_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        from datetime import timedelta
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        analytics = await ai_analytics_manager.get_user_analytics(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        logger.debug("Retrieved user AI analytics for %s (%d days)", user_id, days)
        return analytics
        
    except Exception as e:
        logger.error("Failed to get user AI analytics for %s: %s", user_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ANALYTICS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve user analytics"
            }
        )


@router.get("/analytics/system", response_model=dict)
async def get_system_ai_analytics(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze")
) -> dict:
    """
    Get system-wide AI analytics (admin only).
    
    Returns comprehensive system analytics including usage trends, performance metrics,
    and error analysis for the specified time period.
    
    **Rate Limiting:** 5 requests per hour per user
    **Permissions:** Admin role required
    
    **Returns:**
    - System-wide AI analytics and performance data
    """
    user_id = str(current_user["_id"])
    user_role = current_user.get("role", "user")
    
    # Check admin permissions
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": "System analytics requires admin permissions"
            }
        )
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_analytics_system_{user_id}",
        rate_limit_requests=5,
        rate_limit_period=3600
    )
    
    try:
        from datetime import timedelta
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        analytics = await ai_analytics_manager.get_system_analytics(
            start_date=start_date,
            end_date=end_date
        )
        
        logger.debug("Retrieved system AI analytics (%d days)", days)
        return analytics
        
    except Exception as e:
        logger.error("Failed to get system AI analytics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ANALYTICS_RETRIEVAL_FAILED",
                "message": "Failed to retrieve system analytics"
            }
        )


@router.get("/analytics/performance", response_model=dict)
async def get_ai_performance_metrics(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns),
    agent_type: Optional[str] = Query(None, description="Specific agent type to analyze"),
    hours: int = Query(24, ge=1, le=168, description="Number of hours to analyze")
) -> dict:
    """
    Get AI performance metrics and monitoring data.
    
    Returns detailed performance metrics including response times, error rates,
    and system health indicators for the specified time period.
    
    **Rate Limiting:** 20 requests per hour per user
    
    **Returns:**
    - AI performance metrics and monitoring data
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_performance_{user_id}",
        rate_limit_requests=20,
        rate_limit_period=3600
    )
    
    try:
        from datetime import timedelta
        
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(hours=hours)
        
        performance_data = await ai_analytics_manager.get_agent_performance(
            agent_type=agent_type,
            start_date=start_date,
            end_date=end_date
        )
        
        logger.debug("Retrieved AI performance metrics for %s (%d hours)", 
                    agent_type or "all agents", hours)
        return performance_data
        
    except Exception as e:
        logger.error("Failed to get AI performance metrics: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "PERFORMANCE_RETRIEVAL_FAILED",
                "message": "Failed to retrieve performance metrics"
            }
        )


@router.get("/analytics/report/{report_type}", response_model=dict)
async def generate_ai_usage_report(
    request: Request,
    report_type: str,
    current_user: dict = Depends(enforce_all_lockdowns),
    target_date: Optional[str] = Query(None, description="Target date (YYYY-MM-DD)")
) -> dict:
    """
    Generate comprehensive AI usage report (admin only).
    
    Generates detailed usage reports with analytics, performance metrics,
    and recommendations for system optimization.
    
    **Rate Limiting:** 3 requests per hour per user
    **Permissions:** Admin role required
    
    **Report Types:**
    - daily: Daily usage report
    - weekly: Weekly usage report  
    - monthly: Monthly usage report
    
    **Returns:**
    - Comprehensive usage report with analytics and recommendations
    """
    user_id = str(current_user["_id"])
    user_role = current_user.get("role", "user")
    
    # Check admin permissions
    if user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "INSUFFICIENT_PERMISSIONS",
                "message": "Usage reports require admin permissions"
            }
        )
    
    # Validate report type
    if report_type not in ["daily", "weekly", "monthly"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_REPORT_TYPE",
                "message": f"Invalid report type '{report_type}'. Valid types: daily, weekly, monthly"
            }
        )
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_report_{user_id}",
        rate_limit_requests=3,
        rate_limit_period=3600
    )
    
    try:
        # Parse target date if provided
        report_date = None
        if target_date:
            try:
                from datetime import datetime
                report_date = datetime.fromisoformat(target_date).replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "INVALID_DATE_FORMAT",
                        "message": "Date must be in YYYY-MM-DD format"
                    }
                )
        
        report = await ai_analytics_manager.generate_usage_report(
            report_type=report_type,
            target_date=report_date
        )
        
        logger.info("Generated %s AI usage report for %s", report_type, 
                   report_date.date() if report_date else "current period")
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate AI usage report: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "REPORT_GENERATION_FAILED",
                "message": "Failed to generate usage report"
            }
        )


@router.get("/health", response_model=AIHealthResponse)
async def get_ai_health(
    request: Request,
    current_user: dict = Depends(enforce_all_lockdowns)
) -> AIHealthResponse:
    """
    Get AI system health status and statistics.
    
    Returns current system health including active sessions, available agents,
    and system load information. Useful for monitoring and diagnostics.
    
    **Rate Limiting:** 10 requests per hour per user
    
    **Returns:**
    - AI system health and status information
    """
    user_id = str(current_user["_id"])
    
    # Apply rate limiting
    await security_manager.check_rate_limit(
        request,
        f"ai_health_{user_id}",
        rate_limit_requests=10,
        rate_limit_period=3600
    )
    
    try:
        # Get system statistics from metrics collector
        system_metrics = ai_performance_monitor.get_performance_summary()
        
        # Get available agents
        available_agents = [agent.value for agent in AgentType]
        
        # Extract session metrics from performance summary
        session_metrics = system_metrics.get("session_metrics", {})
        active_sessions = session_metrics.get("active_sessions", 0)
        total_sessions = session_metrics.get("total_sessions", 0)
        total_messages = session_metrics.get("total_messages", 0)
        total_errors = session_metrics.get("total_errors", 0)
        
        # Calculate error rate
        overall_error_rate = (total_errors / max(total_messages, 1)) * 100 if total_messages > 0 else 0.0
        
        system_load = {
            "total_requests": total_messages,
            "total_errors": total_errors,
            "error_rate": overall_error_rate,
            "active_sessions": active_sessions,
            "total_sessions": total_sessions
        }
        
        # Determine overall health status
        health_status = "healthy"
        if overall_error_rate > 0.1:  # 10% error rate threshold
            health_status = "degraded"
        elif overall_error_rate > 0.2:  # 20% error rate threshold
            health_status = "unhealthy"
        
        return AIHealthResponse(
            status=health_status,
            active_sessions=active_sessions,
            available_agents=available_agents,
            system_load=system_load,
            timestamp=datetime.now(timezone.utc)
        )
        
    except Exception as e:
        logger.error("Failed to get AI health status: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "HEALTH_CHECK_FAILED",
                "message": "Failed to retrieve AI system health"
            }
        )