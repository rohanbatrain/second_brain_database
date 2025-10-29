"""
AI Session Models

This module contains models for AI session management, including session context,
conversation history, and session state management.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from enum import Enum
from pydantic import BaseModel, Field
from bson import ObjectId


class SessionStatus(str, Enum):
    """AI session status values."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


class AgentType(str, Enum):
    """Available AI agent types."""
    FAMILY = "family"
    PERSONAL = "personal"
    WORKSPACE = "workspace"
    COMMERCE = "commerce"
    SECURITY = "security"
    VOICE = "voice"


class MessageRole(str, Enum):
    """Message roles in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageType(str, Enum):
    """Message types."""
    TEXT = "text"
    VOICE = "voice"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    STATUS = "status"


class ConversationMessage(BaseModel):
    """
    Individual message in an AI conversation.
    """
    id: str = Field(..., description="Unique message identifier")
    session_id: str = Field(..., description="AI session identifier")
    content: str = Field(..., description="Message content")
    role: MessageRole = Field(..., description="Message role (user, assistant, system, tool)")
    message_type: MessageType = Field(default=MessageType.TEXT, description="Type of message")
    agent_type: Optional[str] = Field(None, description="AI agent that generated this message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Message timestamp")
    
    # Tool-specific fields
    tool_name: Optional[str] = Field(None, description="Tool name for tool messages")
    tool_parameters: Optional[Dict[str, Any]] = Field(None, description="Tool parameters")
    tool_result: Optional[Any] = Field(None, description="Tool execution result")
    
    # Voice-specific fields
    audio_data: Optional[str] = Field(None, description="Base64-encoded audio data")
    transcription: Optional[str] = Field(None, description="Voice transcription")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SessionContext(BaseModel):
    """
    AI session context containing user information, conversation state,
    and agent-specific context data.
    """
    session_id: str = Field(..., description="Unique session identifier")
    user_id: str = Field(..., description="User identifier")
    agent_type: AgentType = Field(..., description="Primary AI agent type for this session")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="Session status")
    
    # Context data
    user_context: Dict[str, Any] = Field(default_factory=dict, description="User-specific context")
    family_context: Optional[Dict[str, Any]] = Field(None, description="Family context if applicable")
    workspace_context: Optional[Dict[str, Any]] = Field(None, description="Workspace context if applicable")
    
    # Session state
    conversation_history: List[ConversationMessage] = Field(default_factory=list, description="Conversation messages")
    current_workflow: Optional[str] = Field(None, description="Currently executing workflow")
    workflow_state: Dict[str, Any] = Field(default_factory=dict, description="Workflow execution state")
    
    # Memory and context
    short_term_memory: Dict[str, Any] = Field(default_factory=dict, description="Session-specific memory")
    loaded_context: Dict[str, Any] = Field(default_factory=dict, description="Preloaded context data")
    
    # Communication channels
    websocket_connected: bool = Field(default=False, description="WebSocket connection status")
    voice_enabled: bool = Field(default=False, description="Voice communication enabled")
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Session creation time")
    last_activity: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last activity time")
    expires_at: Optional[datetime] = Field(None, description="Session expiration time")
    
    # Configuration
    preferences: Dict[str, Any] = Field(default_factory=dict, description="Session preferences")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Session settings")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def update_activity(self) -> None:
        """Update the last activity timestamp."""
        self.last_activity = datetime.now(timezone.utc)
    
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at
    
    def add_message(self, message: ConversationMessage) -> None:
        """Add a message to the conversation history."""
        self.conversation_history.append(message)
        self.update_activity()
    
    def get_recent_messages(self, limit: int = 10) -> List[ConversationMessage]:
        """Get the most recent messages from the conversation."""
        return self.conversation_history[-limit:] if self.conversation_history else []
    
    def set_expiration(self, hours: int = 24) -> None:
        """Set session expiration time."""
        self.expires_at = datetime.now(timezone.utc) + timedelta(hours=hours)


class SessionCreateRequest(BaseModel):
    """Request model for creating a new AI session."""
    agent_type: AgentType = Field(..., description="Primary AI agent type")
    voice_enabled: bool = Field(default=False, description="Enable voice communication")
    preferences: Dict[str, Any] = Field(default_factory=dict, description="Session preferences")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Session settings")
    expiration_hours: int = Field(default=24, description="Session expiration in hours", ge=1, le=168)  # Max 1 week


class SessionResponse(BaseModel):
    """Response model for session operations."""
    session_id: str = Field(..., description="Session identifier")
    agent_type: AgentType = Field(..., description="Primary AI agent type")
    status: SessionStatus = Field(..., description="Session status")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity time")
    expires_at: Optional[datetime] = Field(None, description="Session expiration time")
    websocket_connected: bool = Field(..., description="WebSocket connection status")
    voice_enabled: bool = Field(..., description="Voice communication enabled")
    message_count: int = Field(..., description="Number of messages in conversation")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MessageRequest(BaseModel):
    """Request model for sending a message to an AI agent."""
    content: str = Field(..., description="Message content", min_length=1, max_length=10000)
    message_type: MessageType = Field(default=MessageType.TEXT, description="Type of message")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional message metadata")
    
    # Voice-specific fields
    audio_data: Optional[str] = Field(None, description="Base64-encoded audio data for voice messages")
    
    # Agent switching
    switch_to_agent: Optional[AgentType] = Field(None, description="Switch to a different agent for this message")


class MessageResponse(BaseModel):
    """Response model for message operations."""
    message_id: str = Field(..., description="Message identifier")
    session_id: str = Field(..., description="Session identifier")
    agent_type: str = Field(..., description="AI agent that processed the message")
    processing_started: bool = Field(..., description="Whether message processing has started")
    estimated_response_time: Optional[float] = Field(None, description="Estimated response time in seconds")
    
    class Config:
        use_enum_values = True


class SessionListResponse(BaseModel):
    """Response model for listing user sessions."""
    sessions: List[SessionResponse] = Field(..., description="List of user sessions")
    total_count: int = Field(..., description="Total number of sessions")
    active_count: int = Field(..., description="Number of active sessions")
    
    class Config:
        use_enum_values = True


class SessionStatsResponse(BaseModel):
    """Response model for session statistics."""
    total_sessions: int = Field(..., description="Total number of sessions")
    active_sessions: int = Field(..., description="Number of active sessions")
    total_messages: int = Field(..., description="Total number of messages")
    average_session_duration: Optional[float] = Field(None, description="Average session duration in minutes")
    most_used_agent: Optional[str] = Field(None, description="Most frequently used agent type")
    
    class Config:
        use_enum_values = True