"""
AI Integration MCP Tools

MCP tools for AI session management, agent interaction, and conversation handling
following the established shop_tools.py patterns and FastMCP 2.x compliance.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field

from ....managers.logging_manager import get_logger
from ....config import settings
from ..security import authenticated_tool, get_mcp_user_context
from ..modern_server import mcp
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError, MCPToolError

logger = get_logger(prefix="[MCP_AITools]")

# Import manager instances and utilities
from ....database import db_manager
from ....managers.security_manager import security_manager
from ....managers.redis_manager import redis_manager
from ....managers.ai_session_manager import ai_session_manager, AgentType, MessageType, MessageRole, SessionStatus
from ....managers.family_manager import family_manager

# Pydantic models for MCP tool parameters and responses

class AISession(BaseModel):
    """AI session information model."""
    session_id: str
    agent_type: str
    session_name: str
    status: str
    created_at: datetime
    last_activity: datetime
    expires_at: datetime
    voice_enabled: bool = False
    message_count: int = 0
    context: Optional[Dict[str, Any]] = None

class AIMessage(BaseModel):
    """AI message information model."""
    message_id: str
    session_id: str
    content: str
    message_type: str
    role: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class AgentCapability(BaseModel):
    """Agent capability information."""
    name: str
    description: str
    capabilities: List[str]
    tools: List[str]
    voice_enabled: bool = False

# AI Session Management Tools (Task 6.1)

@authenticated_tool(
    name="create_ai_session",
    description="Create a new AI chat session with specified agent type",
    permissions=["ai:session:create"],
    rate_limit_action="ai_session_create"
)
async def create_ai_session(
    agent_type: str = "personal",
    session_name: Optional[str] = None,
    voice_enabled: bool = False,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a new AI chat session with the specified agent type.
    
    Args:
        agent_type: Type of AI agent (personal, family, workspace, commerce, security, voice)
        session_name: Optional custom session name
        voice_enabled: Whether voice features are enabled
        context: Optional session context and metadata
        
    Returns:
        Dictionary containing session information
    """
    user_context = get_mcp_user_context()
    
    # Validate agent type
    valid_agent_types = [agent.value for agent in AgentType]
    if agent_type not in valid_agent_types:
        raise MCPValidationError(f"Invalid agent type. Must be one of: {valid_agent_types}")
    
    try:
        # Create AI session using the AI session manager
        session = await ai_session_manager.create_session(
            user_id=user_context.user_id,
            agent_type=AgentType(agent_type),
            session_name=session_name,
            voice_enabled=voice_enabled,
            context=context or {}
        )
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="create_ai_session",
            resource_type="ai_session",
            resource_id=session["session_id"],
            metadata={
                "agent_type": agent_type,
                "voice_enabled": voice_enabled,
                "session_name": session_name
            },
            user_context=user_context
        )
        
        logger.info(
            "User %s created AI session: %s (%s)",
            user_context.username, session["session_id"], agent_type
        )
        
        return {
            "status": "success",
            "session": {
                "session_id": session["session_id"],
                "agent_type": session["agent_type"],
                "session_name": session["session_name"],
                "status": "active",
                "created_at": session["created_at"].isoformat(),
                "expires_at": session["expires_at"].isoformat(),
                "voice_enabled": session["voice_enabled"],
                "agent_config": session["agent_config"]
            }
        }
        
    except Exception as e:
        logger.error("Failed to create AI session for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to create AI session: {str(e)}")

@authenticated_tool(
    name="list_ai_sessions",
    description="List user's AI chat sessions",
    permissions=["ai:session:read"],
    rate_limit_action="ai_session_read"
)
async def list_ai_sessions(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0
) -> Dict[str, Any]:
    """
    List user's AI chat sessions with optional filtering.
    
    Args:
        status: Optional status filter (active, inactive, expired, terminated)
        limit: Maximum number of sessions to return
        offset: Number of sessions to skip for pagination
        
    Returns:
        Dictionary containing sessions list and pagination info
    """
    user_context = get_mcp_user_context()
    
    # Validate parameters
    if limit > 100:
        limit = 100
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0
    
    # Validate status if provided
    if status:
        valid_statuses = [s.value for s in SessionStatus]
        if status not in valid_statuses:
            raise MCPValidationError(f"Invalid status. Must be one of: {valid_statuses}")
    
    try:
        # Get user sessions
        sessions_result = await ai_session_manager.list_user_sessions(
            user_id=user_context.user_id,
            status=SessionStatus(status) if status else None,
            limit=limit,
            offset=offset
        )
        
        # Format sessions for response
        formatted_sessions = []
        for session in sessions_result["sessions"]:
            formatted_sessions.append({
                "session_id": session["session_id"],
                "agent_type": session["agent_type"],
                "session_name": session["session_name"],
                "status": session["status"],
                "created_at": session["created_at"].isoformat(),
                "last_activity": session["last_activity"].isoformat(),
                "expires_at": session.get("expires_at", {}).isoformat() if session.get("expires_at") else None,
                "voice_enabled": session.get("voice_enabled", False),
                "message_count": session.get("message_count", 0),
                "websocket_connected": session.get("websocket_connected", False)
            })
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="list_ai_sessions",
            resource_type="ai_sessions",
            resource_id=user_context.user_id,
            metadata={
                "status_filter": status,
                "limit": limit,
                "offset": offset,
                "total_found": sessions_result["pagination"]["total"]
            },
            user_context=user_context
        )
        
        logger.info(
            "User %s listed AI sessions: %d found",
            user_context.username, sessions_result["pagination"]["total"]
        )
        
        return {
            "status": "success",
            "sessions": formatted_sessions,
            "pagination": sessions_result["pagination"]
        }
        
    except Exception as e:
        logger.error("Failed to list AI sessions for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to list AI sessions: {str(e)}")

@authenticated_tool(
    name="get_ai_session",
    description="Get detailed information about a specific AI session",
    permissions=["ai:session:read"],
    rate_limit_action="ai_session_read"
)
async def get_ai_session(session_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific AI session.
    
    Args:
        session_id: ID of the AI session to retrieve
        
    Returns:
        Dictionary containing detailed session information
    """
    user_context = get_mcp_user_context()
    
    if not session_id:
        raise MCPValidationError("session_id is required")
    
    try:
        # Get session information
        session = await ai_session_manager.get_session(session_id, user_context.user_id)
        
        # Format session for response
        formatted_session = {
            "session_id": session["session_id"],
            "agent_type": session["agent_type"],
            "session_name": session["session_name"],
            "status": session["status"],
            "created_at": session["created_at"].isoformat(),
            "last_activity": session["last_activity"].isoformat(),
            "expires_at": session.get("expires_at", {}).isoformat() if session.get("expires_at") else None,
            "voice_enabled": session.get("voice_enabled", False),
            "message_count": session.get("message_count", 0),
            "websocket_connected": session.get("websocket_connected", False),
            "context": session.get("context", {}),
            "agent_config": session.get("agent_config", {}),
            "metadata": session.get("metadata", {})
        }
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_ai_session",
            resource_type="ai_session",
            resource_id=session_id,
            metadata={"agent_type": session["agent_type"]},
            user_context=user_context
        )
        
        logger.info(
            "User %s retrieved AI session: %s (%s)",
            user_context.username, session_id, session["agent_type"]
        )
        
        return {
            "status": "success",
            "session": formatted_session
        }
        
    except Exception as e:
        logger.error("Failed to get AI session %s for user %s: %s", session_id, user_context.username, e)
        raise MCPToolError(f"Failed to get AI session: {str(e)}")

@authenticated_tool(
    name="end_ai_session",
    description="End an AI chat session",
    permissions=["ai:session:manage"],
    rate_limit_action="ai_session_manage"
)
async def end_ai_session(session_id: str) -> Dict[str, Any]:
    """
    End an AI chat session and clean up resources.
    
    Args:
        session_id: ID of the AI session to end
        
    Returns:
        Dictionary containing operation confirmation
    """
    user_context = get_mcp_user_context()
    
    if not session_id:
        raise MCPValidationError("session_id is required")
    
    try:
        # End the AI session
        await ai_session_manager.end_session(session_id, user_context.user_id)
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="end_ai_session",
            resource_type="ai_session",
            resource_id=session_id,
            metadata={"ended_by": user_context.user_id},
            user_context=user_context
        )
        
        logger.info(
            "User %s ended AI session: %s",
            user_context.username, session_id
        )
        
        return {
            "status": "success",
            "message": "AI session ended successfully",
            "session_id": session_id,
            "ended_at": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error("Failed to end AI session %s for user %s: %s", session_id, user_context.username, e)
        raise MCPToolError(f"Failed to end AI session: {str(e)}")

# AI Message Management Tools (Task 6.2)

@authenticated_tool(
    name="send_ai_message",
    description="Send a message to an AI session",
    permissions=["ai:message:send"],
    rate_limit_action="ai_message_send"
)
async def send_ai_message(
    session_id: str,
    content: str,
    message_type: str = "text",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send a message to an AI session.
    
    Args:
        session_id: ID of the AI session
        content: Message content
        message_type: Type of message (text, voice, tool_call, tool_result, system)
        metadata: Optional message metadata
        
    Returns:
        Dictionary containing message information
    """
    user_context = get_mcp_user_context()
    
    if not session_id or not content:
        raise MCPValidationError("session_id and content are required")
    
    # Validate message type
    valid_message_types = [mt.value for mt in MessageType]
    if message_type not in valid_message_types:
        raise MCPValidationError(f"Invalid message type. Must be one of: {valid_message_types}")
    
    try:
        # Send message to AI session
        message = await ai_session_manager.send_message(
            session_id=session_id,
            content=content,
            message_type=MessageType(message_type),
            role=MessageRole.USER,
            metadata=metadata or {},
            user_id=user_context.user_id
        )
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="send_ai_message",
            resource_type="ai_message",
            resource_id=message["message_id"],
            metadata={
                "session_id": session_id,
                "message_type": message_type,
                "content_length": len(content)
            },
            user_context=user_context
        )
        
        logger.info(
            "User %s sent message to AI session %s: %s",
            user_context.username, session_id, message_type
        )
        
        return {
            "status": "success",
            "message": {
                "message_id": message["message_id"],
                "session_id": message["session_id"],
                "content": message["content"],
                "message_type": message["message_type"],
                "role": message["role"],
                "timestamp": message["timestamp"].isoformat(),
                "metadata": message["metadata"]
            }
        }
        
    except Exception as e:
        logger.error("Failed to send AI message for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to send AI message: {str(e)}")

@authenticated_tool(
    name="get_ai_conversation_history",
    description="Get conversation history for an AI session",
    permissions=["ai:message:read"],
    rate_limit_action="ai_message_read"
)
async def get_ai_conversation_history(
    session_id: str,
    limit: int = 50,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Get conversation history for an AI session.
    
    Args:
        session_id: ID of the AI session
        limit: Maximum number of messages to return
        offset: Number of messages to skip for pagination
        
    Returns:
        Dictionary containing conversation history
    """
    user_context = get_mcp_user_context()
    
    if not session_id:
        raise MCPValidationError("session_id is required")
    
    # Validate parameters
    if limit > 200:
        limit = 200
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0
    
    try:
        # Get conversation history
        history = await ai_session_manager.get_session_history(
            session_id=session_id,
            limit=limit,
            offset=offset,
            user_id=user_context.user_id
        )
        
        # Format messages for response
        formatted_messages = []
        for message in history:
            formatted_messages.append({
                "message_id": message["message_id"],
                "session_id": message["session_id"],
                "content": message["content"],
                "message_type": message["message_type"],
                "role": message["role"],
                "timestamp": message["timestamp"].isoformat(),
                "metadata": message.get("metadata", {})
            })
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_ai_conversation_history",
            resource_type="ai_conversation",
            resource_id=session_id,
            metadata={
                "limit": limit,
                "offset": offset,
                "messages_returned": len(formatted_messages)
            },
            user_context=user_context
        )
        
        logger.info(
            "User %s retrieved conversation history for session %s: %d messages",
            user_context.username, session_id, len(formatted_messages)
        )
        
        return {
            "status": "success",
            "session_id": session_id,
            "messages": formatted_messages,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned": len(formatted_messages)
            }
        }
        
    except Exception as e:
        logger.error("Failed to get conversation history for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get conversation history: {str(e)}")

# Agent Information and Capabilities Tools (Task 6.3)

@authenticated_tool(
    name="get_available_agents",
    description="Get list of available AI agent types and their capabilities",
    permissions=["ai:agent:read"],
    rate_limit_action="ai_agent_read"
)
async def get_available_agents() -> Dict[str, Any]:
    """
    Get list of available AI agent types and their capabilities.
    
    Returns:
        Dictionary containing available agents and their information
    """
    user_context = get_mcp_user_context()
    
    try:
        # Define available agents with their capabilities
        agents = []
        
        for agent_type in AgentType:
            # Get agent configuration (this would normally come from the AI session manager)
            agent_config = {
                AgentType.FAMILY: {
                    "name": "Family Assistant",
                    "description": "Helps with family management, relationships, and coordination",
                    "capabilities": ["family_management", "member_coordination", "event_planning", "token_management"],
                    "tools": ["create_family", "invite_member", "manage_permissions", "transfer_tokens"],
                    "voice_enabled": True,
                    "permissions_required": ["family:read", "family:manage"]
                },
                AgentType.PERSONAL: {
                    "name": "Personal Assistant",
                    "description": "Provides personal productivity and life management support",
                    "capabilities": ["task_management", "scheduling", "personal_insights", "profile_management"],
                    "tools": ["create_task", "schedule_event", "track_habits", "update_profile"],
                    "voice_enabled": True,
                    "permissions_required": ["profile:read", "profile:manage"]
                },
                AgentType.WORKSPACE: {
                    "name": "Workspace Assistant",
                    "description": "Assists with work-related tasks and team collaboration",
                    "capabilities": ["project_management", "team_coordination", "document_management"],
                    "tools": ["create_project", "assign_task", "share_document"],
                    "voice_enabled": True,
                    "permissions_required": ["workspace:read", "workspace:manage"]
                },
                AgentType.COMMERCE: {
                    "name": "Commerce Assistant",
                    "description": "Helps with shopping, purchases, and financial management",
                    "capabilities": ["shop_browsing", "purchase_management", "budget_tracking"],
                    "tools": ["browse_shop", "purchase_item", "track_spending"],
                    "voice_enabled": True,
                    "permissions_required": ["shop:read", "shop:purchase"]
                },
                AgentType.SECURITY: {
                    "name": "Security Assistant",
                    "description": "Provides security monitoring and access management",
                    "capabilities": ["security_monitoring", "access_control", "audit_review"],
                    "tools": ["review_access", "monitor_activity", "generate_report"],
                    "voice_enabled": False,
                    "admin_only": True,
                    "permissions_required": ["admin:security", "admin:audit"]
                },
                AgentType.VOICE: {
                    "name": "Voice Assistant",
                    "description": "Specialized voice interaction and audio processing",
                    "capabilities": ["voice_processing", "audio_transcription", "speech_synthesis"],
                    "tools": ["transcribe_audio", "synthesize_speech", "process_voice"],
                    "voice_enabled": True,
                    "voice_primary": True,
                    "permissions_required": ["voice:process", "voice:transcribe"]
                }
            }.get(agent_type, {})
            
            if agent_config:
                agents.append({
                    "agent_type": agent_type.value,
                    **agent_config
                })
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_available_agents",
            resource_type="ai_agents",
            resource_id="available_agents",
            metadata={"agents_count": len(agents)},
            user_context=user_context
        )
        
        logger.info(
            "User %s retrieved available agents: %d agents",
            user_context.username, len(agents)
        )
        
        return {
            "status": "success",
            "agents": agents,
            "total_count": len(agents)
        }
        
    except Exception as e:
        logger.error("Failed to get available agents for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get available agents: {str(e)}")

@authenticated_tool(
    name="get_agent_capabilities",
    description="Get detailed capabilities for a specific agent type",
    permissions=["ai:agent:read"],
    rate_limit_action="ai_agent_read"
)
async def get_agent_capabilities(agent_type: str) -> Dict[str, Any]:
    """
    Get detailed capabilities for a specific agent type.
    
    Args:
        agent_type: Type of AI agent to get capabilities for
        
    Returns:
        Dictionary containing detailed agent capabilities
    """
    user_context = get_mcp_user_context()
    
    # Validate agent type
    valid_agent_types = [agent.value for agent in AgentType]
    if agent_type not in valid_agent_types:
        raise MCPValidationError(f"Invalid agent type. Must be one of: {valid_agent_types}")
    
    try:
        # Get all available agents
        agents_result = await get_available_agents()
        
        # Find the specific agent
        agent_info = None
        for agent in agents_result["agents"]:
            if agent["agent_type"] == agent_type:
                agent_info = agent
                break
        
        if not agent_info:
            raise MCPValidationError(f"Agent type not found: {agent_type}")
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_agent_capabilities",
            resource_type="ai_agent",
            resource_id=agent_type,
            metadata={"capabilities_count": len(agent_info.get("capabilities", []))},
            user_context=user_context
        )
        
        logger.info(
            "User %s retrieved capabilities for agent: %s",
            user_context.username, agent_type
        )
        
        return {
            "status": "success",
            "agent": agent_info
        }
        
    except Exception as e:
        logger.error("Failed to get agent capabilities for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get agent capabilities: {str(e)}")

# Family Operations Integration Tools (Task 6.4)

@authenticated_tool(
    name="ai_create_family",
    description="Create a new family through AI assistant",
    permissions=["family:create", "ai:family:manage"],
    rate_limit_action="family_create"
)
async def ai_create_family(
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new family through the AI assistant interface.
    
    Args:
        name: Optional custom family name
        description: Optional family description
        
    Returns:
        Dictionary containing family creation result
    """
    user_context = get_mcp_user_context()
    
    try:
        # Create family using the family manager
        family = await family_manager.create_family(
            user_id=user_context.user_id,
            name=name
        )
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="ai_create_family",
            resource_type="family",
            resource_id=family["family_id"],
            metadata={
                "family_name": family["name"],
                "created_via": "ai_assistant"
            },
            user_context=user_context
        )
        
        logger.info(
            "User %s created family via AI: %s (%s)",
            user_context.username, family["family_id"], family["name"]
        )
        
        return {
            "status": "success",
            "family": {
                "family_id": family["family_id"],
                "name": family["name"],
                "admin_user_ids": family["admin_user_ids"],
                "member_count": family["member_count"],
                "created_at": family["created_at"].isoformat(),
                "sbd_account": family["sbd_account"]
            },
            "message": f"Family '{family['name']}' created successfully!"
        }
        
    except Exception as e:
        logger.error("Failed to create family via AI for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to create family: {str(e)}")

@authenticated_tool(
    name="ai_get_family_info",
    description="Get family information through AI assistant",
    permissions=["family:read", "ai:family:read"],
    rate_limit_action="family_read"
)
async def ai_get_family_info(family_id: str) -> Dict[str, Any]:
    """
    Get family information through the AI assistant interface.
    
    Args:
        family_id: ID of the family to get information for
        
    Returns:
        Dictionary containing family information
    """
    user_context = get_mcp_user_context()
    
    if not family_id:
        raise MCPValidationError("family_id is required")
    
    try:
        # Get family information using the family manager
        family = await family_manager.get_family_by_id(family_id, user_context.user_id)
        
        # Get family members
        members = await family_manager.get_family_members(family_id, user_context.user_id)
        
        # Get SBD account information
        sbd_account = await family_manager.get_family_sbd_account(family_id, user_context.user_id)
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="ai_get_family_info",
            resource_type="family",
            resource_id=family_id,
            metadata={"accessed_via": "ai_assistant"},
            user_context=user_context
        )
        
        logger.info(
            "User %s retrieved family info via AI: %s",
            user_context.username, family_id
        )
        
        return {
            "status": "success",
            "family": {
                "family_id": family["family_id"],
                "name": family["name"],
                "created_at": family["created_at"].isoformat(),
                "member_count": len(members),
                "members": [
                    {
                        "user_id": member["user_id"],
                        "username": member["username"],
                        "role": member["role"],
                        "joined_at": member["joined_at"].isoformat()
                    }
                    for member in members
                ],
                "sbd_account": {
                    "account_username": sbd_account["account_username"],
                    "balance": sbd_account["balance"],
                    "is_frozen": sbd_account["is_frozen"]
                }
            }
        }
        
    except Exception as e:
        logger.error("Failed to get family info via AI for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to get family information: {str(e)}")

@authenticated_tool(
    name="ai_transfer_family_tokens",
    description="Transfer SBD tokens from family account through AI assistant",
    permissions=["family:sbd:transfer", "ai:family:manage"],
    rate_limit_action="sbd_transfer"
)
async def ai_transfer_family_tokens(
    family_id: str,
    to_username: str,
    amount: int,
    reason: Optional[str] = None
) -> Dict[str, Any]:
    """
    Transfer SBD tokens from family account through the AI assistant interface.
    
    Args:
        family_id: ID of the family account to transfer from
        to_username: Username of the recipient
        amount: Amount of tokens to transfer
        reason: Optional reason for the transfer
        
    Returns:
        Dictionary containing transfer result
    """
    user_context = get_mcp_user_context()
    
    if not family_id or not to_username or amount <= 0:
        raise MCPValidationError("family_id, to_username, and positive amount are required")
    
    try:
        # Transfer tokens using the family manager
        transfer_result = await family_manager.direct_transfer_tokens(
            family_id=family_id,
            admin_id=user_context.user_id,
            recipient_username=to_username,
            amount=amount,
            reason=reason or "Transfer via AI assistant"
        )
        
        # Create audit trail
        await create_mcp_audit_trail(
            operation="ai_transfer_family_tokens",
            resource_type="sbd_transfer",
            resource_id=transfer_result["transaction_id"],
            metadata={
                "family_id": family_id,
                "to_username": to_username,
                "amount": amount,
                "reason": reason,
                "transferred_via": "ai_assistant"
            },
            user_context=user_context
        )
        
        logger.info(
            "User %s transferred %d tokens via AI from family %s to %s",
            user_context.username, amount, family_id, to_username
        )
        
        return {
            "status": "success",
            "transfer": {
                "transaction_id": transfer_result["transaction_id"],
                "family_id": family_id,
                "to_username": to_username,
                "amount": amount,
                "reason": reason,
                "transferred_at": transfer_result["transferred_at"],
                "new_balance": transfer_result["new_balance"]
            },
            "message": f"Successfully transferred {amount} tokens to {to_username}"
        }
        
    except Exception as e:
        logger.error("Failed to transfer family tokens via AI for user %s: %s", user_context.username, e)
        raise MCPToolError(f"Failed to transfer tokens: {str(e)}")