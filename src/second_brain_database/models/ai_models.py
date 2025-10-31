"""
Pydantic models for AI agent orchestration system.

This module contains all request/response models, validation schemas,
and data transfer objects for the AI agent functionality.
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, validator


# Constants for validation
AGENT_TYPES = ["family", "personal", "workspace", "commerce", "security", "voice"]
SESSION_STATUSES = ["active", "inactive", "expired", "terminated"]
MESSAGE_ROLES = ["user", "assistant", "system", "tool"]
MESSAGE_TYPES = ["text", "voice", "tool_call", "tool_result", "thinking", "typing"]
AI_EVENT_TYPES = ["token", "response", "tool_call", "tool_result", "tts", "stt", "thinking", "typing", "error"]


# Request Models
class CreateAISessionRequest(BaseModel):
    """Request model for creating a new AI session."""
    agent_type: str = Field(..., description="Type of AI agent to create session with")
    voice_enabled: bool = Field(False, description="Enable voice capabilities for this session")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="Session preferences and settings")
    
    @validator('agent_type')
    def validate_agent_type(cls, v):
        v = v.lower().strip()
        if v not in AGENT_TYPES:
            valid_types = ", ".join(AGENT_TYPES)
            raise ValueError(f"Invalid agent type. Valid types: {valid_types}")
        return v


class SendMessageRequest(BaseModel):
    """Request model for sending a message to an AI session."""
    content: str = Field(..., description="Message content")
    message_type: str = Field("text", description="Type of message being sent")
    audio_data: Optional[str] = Field(None, description="Base64 encoded audio data for voice messages")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    
    @validator('message_type')
    def validate_message_type(cls, v):
        v = v.lower().strip()
        if v not in MESSAGE_TYPES:
            valid_types = ", ".join(MESSAGE_TYPES)
            raise ValueError(f"Invalid message type. Valid types: {valid_types}")
        return v
    
    @validator('content')
    def validate_content(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message content cannot be empty")
        if len(v) > 10000:
            raise ValueError("Message content cannot exceed 10,000 characters")
        return v


class SwitchAgentRequest(BaseModel):
    """Request model for switching agents within a session."""
    new_agent_type: str = Field(..., description="New agent type to switch to")
    preserve_context: bool = Field(True, description="Whether to preserve conversation context")
    
    @validator('new_agent_type')
    def validate_new_agent_type(cls, v):
        v = v.lower().strip()
        if v not in AGENT_TYPES:
            valid_types = ", ".join(AGENT_TYPES)
            raise ValueError(f"Invalid agent type. Valid types: {valid_types}")
        return v


class UpdateSessionPreferencesRequest(BaseModel):
    """Request model for updating session preferences."""
    voice_enabled: Optional[bool] = Field(None, description="Enable/disable voice capabilities")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="Updated preferences")


# Response Models
class ChatMessageResponse(BaseModel):
    """Response model for chat message information."""
    message_id: str
    session_id: str
    content: str
    role: str
    agent_type: Optional[str] = None
    timestamp: datetime
    message_type: str
    metadata: Dict[str, Any] = {}
    audio_data: Optional[str] = None


class AgentConfigResponse(BaseModel):
    """Response model for agent configuration information."""
    agent_type: str
    name: str
    description: str
    capabilities: List[str]
    tools: List[str]
    voice_enabled: bool
    admin_only: bool = False


class AISessionResponse(BaseModel):
    """Response model for AI session information."""
    session_id: str
    user_id: str
    agent_type: str
    status: str
    created_at: datetime
    last_activity: datetime
    expires_at: Optional[datetime] = None
    websocket_connected: bool = False
    voice_enabled: bool = False
    message_count: int = 0
    preferences: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    agent_config: AgentConfigResponse


class MessageResponse(BaseModel):
    """Response model for message sending operations."""
    message_id: str
    session_id: str
    status: str
    timestamp: datetime
    processing_time_ms: Optional[int] = None


class AIHealthResponse(BaseModel):
    """Response model for AI system health check."""
    status: str
    active_sessions: int
    available_agents: List[str]
    system_load: Dict[str, Any]
    timestamp: datetime


class AIEventResponse(BaseModel):
    """Response model for AI events (WebSocket)."""
    event_type: str
    session_id: str
    agent_type: str
    data: Dict[str, Any]
    timestamp: datetime
    
    @validator('event_type')
    def validate_event_type(cls, v):
        if v not in AI_EVENT_TYPES:
            valid_types = ", ".join(AI_EVENT_TYPES)
            raise ValueError(f"Invalid event type. Valid types: {valid_types}")
        return v


# Database Schema Models (for internal use)
class AISessionDocument(BaseModel):
    """Database document model for ai_sessions collection."""
    session_id: str
    user_id: str
    agent_type: str
    status: str
    created_at: datetime
    last_activity: datetime
    expires_at: Optional[datetime] = None
    websocket_connected: bool = False
    voice_enabled: bool = False
    message_count: int = 0
    preferences: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}
    
    @validator('agent_type')
    def validate_agent_type(cls, v):
        if v not in AGENT_TYPES:
            raise ValueError(f"Invalid agent type: {v}")
        return v
    
    @validator('status')
    def validate_status(cls, v):
        if v not in SESSION_STATUSES:
            raise ValueError(f"Invalid session status: {v}")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "ai_sess_abc123def456",
                "user_id": "user_123",
                "agent_type": "personal",
                "status": "active",
                "created_at": "2025-10-30T12:00:00Z",
                "last_activity": "2025-10-30T12:30:00Z",
                "expires_at": "2025-10-30T16:00:00Z",
                "websocket_connected": True,
                "voice_enabled": False,
                "message_count": 5,
                "preferences": {
                    "response_style": "concise",
                    "language": "en"
                },
                "metadata": {
                    "client_version": "1.0.0",
                    "platform": "flutter"
                }
            }
        }


class ChatMessageDocument(BaseModel):
    """Database document model for ai_chat_messages collection."""
    message_id: str
    session_id: str
    content: str
    role: str
    agent_type: Optional[str] = None
    timestamp: datetime
    message_type: str
    metadata: Dict[str, Any] = {}
    audio_data: Optional[str] = None
    processing_time_ms: Optional[int] = None
    
    @validator('role')
    def validate_role(cls, v):
        if v not in MESSAGE_ROLES:
            raise ValueError(f"Invalid message role: {v}")
        return v
    
    @validator('message_type')
    def validate_message_type(cls, v):
        if v not in MESSAGE_TYPES:
            raise ValueError(f"Invalid message type: {v}")
        return v
    
    @validator('content')
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "message_id": "msg_abc123def456",
                "session_id": "ai_sess_abc123def456",
                "content": "Hello, how can I help you today?",
                "role": "assistant",
                "agent_type": "personal",
                "timestamp": "2025-10-30T12:00:00Z",
                "message_type": "text",
                "metadata": {
                    "model_used": "gemma3:1b",
                    "tokens_used": 15
                },
                "audio_data": None,
                "processing_time_ms": 250
            }
        }


class AgentConfigDocument(BaseModel):
    """Database document model for ai_agent_configs collection."""
    agent_type: str
    name: str
    description: str
    capabilities: List[str]
    tools: List[str]
    voice_enabled: bool
    admin_only: bool = False
    system_prompt: str
    model_config: Dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    
    @validator('agent_type')
    def validate_agent_type(cls, v):
        if v not in AGENT_TYPES:
            raise ValueError(f"Invalid agent type: {v}")
        return v
    
    @validator('name', 'description', 'system_prompt')
    def validate_text_fields(cls, v):
        if not v or not v.strip():
            raise ValueError("Text fields cannot be empty")
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "agent_type": "personal",
                "name": "Personal Assistant",
                "description": "Your personal AI assistant for daily tasks and questions",
                "capabilities": [
                    "general_conversation",
                    "task_management",
                    "information_retrieval",
                    "calendar_integration"
                ],
                "tools": [
                    "get_user_profile",
                    "update_user_preferences",
                    "search_knowledge_base"
                ],
                "voice_enabled": True,
                "admin_only": False,
                "system_prompt": "You are a helpful personal assistant...",
                "model_config": {
                    "temperature": 0.7,
                    "max_tokens": 2048,
                    "model": "gemma3:1b"
                },
                "created_at": "2025-10-30T12:00:00Z",
                "updated_at": "2025-10-30T12:00:00Z"
            }
        }


# Error Response Models
class AIErrorResponse(BaseModel):
    """Error response model for AI operations."""
    error: Dict[str, Any]
    
    class Config:
        schema_extra = {
            "example": {
                "error": {
                    "code": "AI_SESSION_NOT_FOUND",
                    "message": "AI session not found or expired",
                    "details": {
                        "session_id": "ai_sess_abc123def456"
                    },
                    "suggested_actions": [
                        "Create a new AI session",
                        "Check session ID format"
                    ]
                }
            }
        }


class AIValidationErrorResponse(BaseModel):
    """Validation error response model for AI operations."""
    detail: List[Dict[str, Any]]
    
    class Config:
        schema_extra = {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "agent_type"],
                        "msg": "Invalid agent type. Valid types: family, personal, workspace, commerce, security, voice",
                        "type": "value_error"
                    }
                ]
            }
        }