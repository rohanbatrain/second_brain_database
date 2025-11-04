"""Pydantic models for AI features."""
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class AgentType(str, Enum):
    """AI agent types."""
    GENERAL = "general"
    FAMILY = "family"
    SHOP = "shop"
    WORKSPACE = "workspace"
    VOICE = "voice"
    SECURITY = "security"


class SessionStatus(str, Enum):
    """AI session status."""
    ACTIVE = "active"
    IDLE = "idle"
    ENDED = "ended"
    ERROR = "error"


class MessageType(str, Enum):
    """Message types."""
    TEXT = "text"
    VOICE = "voice"
    COMMAND = "command"


class AgentConfig(BaseModel):
    """Agent configuration."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    agent_type: AgentType = Field(description="Type of agent")
    model_name: str = Field(description="LLM model name")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, gt=0)
    system_prompt: Optional[str] = Field(default=None)
    tools_enabled: List[str] = Field(default_factory=list)


class AISessionContext(BaseModel):
    """AI session context."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    session_id: str = Field(description="Unique session identifier")
    user_id: str = Field(description="User ID")
    agent_type: AgentType = Field(description="Active agent type")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    message_count: int = Field(default=0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MCPToolExecutionResult(BaseModel):
    """Result of MCP tool execution."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    tool_name: str = Field(description="Tool that was executed")
    success: bool = Field(description="Execution success status")
    result: Any = Field(description="Tool execution result")
    error: Optional[str] = Field(default=None)
    execution_time: float = Field(description="Execution time in seconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    """Agent response."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    content: str = Field(description="Response content")
    agent_type: AgentType = Field(description="Agent that generated response")
    message_type: MessageType = Field(default=MessageType.TEXT)
    tool_calls: List[MCPToolExecutionResult] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = Field(default=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AIConversationDocument(BaseModel):
    """MongoDB document for AI conversations."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    session_id: str = Field(description="Session ID")
    user_id: str = Field(description="User ID")
    agent_type: AgentType = Field(description="Agent type")
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    tool_executions: List[MCPToolExecutionResult] = Field(default_factory=list)
    total_tokens: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VoiceSessionConfig(BaseModel):
    """Voice session configuration."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    session_id: str = Field(description="Voice session ID")
    user_id: str = Field(description="User ID")
    sample_rate: int = Field(default=16000)
    language: str = Field(default="en-US")
    enable_tts: bool = Field(default=True)
    enable_stt: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LangGraphWorkflowConfig(BaseModel):
    """LangGraph workflow configuration."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    workflow_name: str = Field(description="Workflow name")
    nodes: List[str] = Field(description="Workflow nodes")
    edges: Dict[str, List[str]] = Field(description="Node connections")
    entry_point: str = Field(description="Entry node")
    max_iterations: int = Field(default=10)
    timeout: int = Field(default=60, description="Timeout in seconds")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StreamingChunk(BaseModel):
    """Streaming response chunk."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    chunk_type: str = Field(description="Type: text, audio, tool_call")
    content: Any = Field(description="Chunk content")
    sequence: int = Field(description="Sequence number")
    is_final: bool = Field(default=False)
    metadata: Dict[str, Any] = Field(default_factory=dict)
