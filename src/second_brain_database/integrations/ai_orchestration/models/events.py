"""
AI Event Models

This module contains models for AI agent events and real-time communication
with frontend clients through WebSocket and other channels.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of AI events that can be emitted."""
    
    # Response events
    TOKEN = "token"  # Streaming token from AI model
    RESPONSE = "response"  # Complete AI response
    
    # Tool and workflow events
    TOOL_CALL = "tool_call"  # MCP tool execution
    TOOL_RESULT = "tool_result"  # MCP tool result
    WORKFLOW_START = "workflow_start"  # Workflow execution started
    WORKFLOW_STEP = "workflow_step"  # Workflow step completed
    WORKFLOW_END = "workflow_end"  # Workflow execution completed
    
    # Voice events
    TTS = "tts"  # Text-to-speech audio chunk
    STT = "stt"  # Speech-to-text result
    VOICE_START = "voice_start"  # Voice processing started
    VOICE_END = "voice_end"  # Voice processing completed
    
    # Session events
    SESSION_START = "session_start"  # AI session started
    SESSION_END = "session_end"  # AI session ended
    AGENT_SWITCH = "agent_switch"  # Switched to different agent
    
    # Context events
    CONTEXT_LOAD = "context_load"  # Context loading started
    CONTEXT_READY = "context_ready"  # Context loaded and ready
    MEMORY_UPDATE = "memory_update"  # Memory/context updated
    
    # Error events
    ERROR = "error"  # Error occurred
    WARNING = "warning"  # Warning message
    
    # Status events
    THINKING = "thinking"  # AI is processing/thinking
    TYPING = "typing"  # AI is generating response
    WAITING = "waiting"  # Waiting for user input or external resource


class AIEvent(BaseModel):
    """
    AI event model for real-time communication with frontend clients.
    
    Events are streamed through WebSocket connections and can include
    various types of AI agent updates, responses, and status information.
    """
    
    type: EventType = Field(..., description="Type of AI event")
    data: Any = Field(..., description="Event data payload")
    session_id: str = Field(..., description="AI session ID")
    agent_type: str = Field(..., description="Type of AI agent that generated the event")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Event timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional event metadata")
    
    # Optional fields for specific event types
    workflow_id: Optional[str] = Field(None, description="Workflow ID for workflow events")
    tool_name: Optional[str] = Field(None, description="Tool name for tool events")
    error_code: Optional[str] = Field(None, description="Error code for error events")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_websocket_message(self) -> Dict[str, Any]:
        """Convert event to WebSocket message format."""
        return {
            "type": self.type,
            "data": self.data,
            "session_id": self.session_id,
            "agent_type": self.agent_type,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "workflow_id": self.workflow_id,
            "tool_name": self.tool_name,
            "error_code": self.error_code
        }
    
    @classmethod
    def create_token_event(
        cls,
        session_id: str,
        agent_type: str,
        token: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "AIEvent":
        """Create a token streaming event."""
        return cls(
            type=EventType.TOKEN,
            data={"token": token},
            session_id=session_id,
            agent_type=agent_type,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_response_event(
        cls,
        session_id: str,
        agent_type: str,
        response: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "AIEvent":
        """Create a complete response event."""
        return cls(
            type=EventType.RESPONSE,
            data={"response": response},
            session_id=session_id,
            agent_type=agent_type,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_tool_call_event(
        cls,
        session_id: str,
        agent_type: str,
        tool_name: str,
        parameters: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> "AIEvent":
        """Create a tool call event."""
        return cls(
            type=EventType.TOOL_CALL,
            data={"tool_name": tool_name, "parameters": parameters},
            session_id=session_id,
            agent_type=agent_type,
            tool_name=tool_name,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_tool_result_event(
        cls,
        session_id: str,
        agent_type: str,
        tool_name: str,
        result: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "AIEvent":
        """Create a tool result event."""
        return cls(
            type=EventType.TOOL_RESULT,
            data={"tool_name": tool_name, "result": result},
            session_id=session_id,
            agent_type=agent_type,
            tool_name=tool_name,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_tts_event(
        cls,
        session_id: str,
        agent_type: str,
        audio_data: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "AIEvent":
        """Create a TTS audio event."""
        return cls(
            type=EventType.TTS,
            data={"audio": audio_data, "format": "base64"},
            session_id=session_id,
            agent_type=agent_type,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_error_event(
        cls,
        session_id: str,
        agent_type: str,
        error_message: str,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "AIEvent":
        """Create an error event."""
        return cls(
            type=EventType.ERROR,
            data={"error": error_message},
            session_id=session_id,
            agent_type=agent_type,
            error_code=error_code,
            metadata=metadata or {}
        )
    
    @classmethod
    def create_status_event(
        cls,
        session_id: str,
        agent_type: str,
        status: EventType,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "AIEvent":
        """Create a status event (thinking, typing, waiting)."""
        data = {"status": status.value}
        if message:
            data["message"] = message
            
        return cls(
            type=status,
            data=data,
            session_id=session_id,
            agent_type=agent_type,
            metadata=metadata or {}
        )