"""
AI Request and Response Models

This module contains Pydantic models for AI agent requests, responses,
and communication between frontend clients and AI agents.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from enum import Enum


class InputType(str, Enum):
    """Types of input that can be sent to AI agents."""
    
    TEXT = "text"  # Text message
    VOICE = "voice"  # Voice/audio input
    COMMAND = "command"  # System command
    FILE = "file"  # File upload
    IMAGE = "image"  # Image input


class InputData(BaseModel):
    """
    Input data model for AI agent requests.
    
    Represents user input that will be processed by AI agents,
    including text messages, voice input, commands, and files.
    """
    
    content: str = Field(..., description="Input content (text, file path, etc.)")
    input_type: InputType = Field(InputType.TEXT, description="Type of input")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional input metadata")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Input timestamp")
    
    # Optional fields for specific input types
    file_data: Optional[bytes] = Field(None, description="File data for file inputs")
    file_name: Optional[str] = Field(None, description="Original file name")
    file_type: Optional[str] = Field(None, description="MIME type of file")
    
    # Voice-specific fields
    audio_format: Optional[str] = Field(None, description="Audio format (wav, mp3, etc.)")
    sample_rate: Optional[int] = Field(None, description="Audio sample rate")
    duration: Optional[float] = Field(None, description="Audio duration in seconds")
    
    class Config:
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentRequest(BaseModel):
    """
    Request model for AI agent operations.
    
    Represents a complete request to an AI agent including input data,
    session information, and processing preferences.
    """
    
    session_id: str = Field(..., description="AI session ID")
    agent_type: str = Field(..., description="Target AI agent type")
    input_data: InputData = Field(..., description="Input data to process")
    
    # Processing preferences
    stream_response: bool = Field(True, description="Enable streaming response")
    include_context: bool = Field(True, description="Include conversation context")
    max_tokens: Optional[int] = Field(None, description="Maximum response tokens")
    temperature: Optional[float] = Field(None, description="Model temperature override")
    
    # Workflow and tool preferences
    preferred_workflow: Optional[str] = Field(None, description="Preferred workflow to use")
    allowed_tools: Optional[List[str]] = Field(None, description="List of allowed MCP tools")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AgentResponse(BaseModel):
    """
    Response model for AI agent operations.
    
    Represents the complete response from an AI agent including
    the generated content, metadata, and processing information.
    """
    
    session_id: str = Field(..., description="AI session ID")
    agent_type: str = Field(..., description="AI agent type that generated response")
    content: str = Field(..., description="Generated response content")
    
    # Response metadata
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Response timestamp")
    processing_time: float = Field(..., description="Processing time in seconds")
    token_count: Optional[int] = Field(None, description="Number of tokens in response")
    
    # Tool and workflow information
    tools_used: List[str] = Field(default_factory=list, description="List of MCP tools used")
    workflow_executed: Optional[str] = Field(None, description="Workflow that was executed")
    
    # Context and memory updates
    context_updated: bool = Field(False, description="Whether context was updated")
    memory_stored: bool = Field(False, description="Whether response was stored in memory")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional response metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SessionRequest(BaseModel):
    """Request model for creating AI sessions."""
    
    agent_type: str = Field(..., description="Type of AI agent to create session for")
    config: Optional[Dict[str, Any]] = Field(None, description="Session configuration overrides")
    initial_context: Optional[Dict[str, Any]] = Field(None, description="Initial context to load")
    
    class Config:
        extra = "allow"


class SessionResponse(BaseModel):
    """Response model for AI session operations."""
    
    session_id: str = Field(..., description="Created session ID")
    agent_type: str = Field(..., description="AI agent type")
    status: str = Field(..., description="Session status")
    created_at: datetime = Field(..., description="Session creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Session expiration timestamp")
    websocket_url: Optional[str] = Field(None, description="WebSocket URL for real-time communication")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConversationMessage(BaseModel):
    """Model for conversation messages in session history."""
    
    role: str = Field(..., description="Message role (user, assistant, system)")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    agent_type: Optional[str] = Field(None, description="AI agent type for assistant messages")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Message metadata")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ConversationHistory(BaseModel):
    """Model for conversation history in AI sessions."""
    
    session_id: str = Field(..., description="AI session ID")
    messages: List[ConversationMessage] = Field(..., description="List of conversation messages")
    total_messages: int = Field(..., description="Total number of messages in conversation")
    agent_type: str = Field(..., description="Primary AI agent type for session")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }