"""Pydantic models for chat system."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .enums import ChatSessionType, MessageRole, MessageStatus


class ToolInvocation(BaseModel):
    """Model for tool invocation metadata."""

    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Any] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None


class TaskSequence(BaseModel):
    """Model for task execution sequence."""

    tasks: List[str]
    current_task: Optional[str] = None
    completed_tasks: List[str] = Field(default_factory=list)


class TokenUsageInfo(BaseModel):
    """Model for token usage information."""

    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cost: float = 0.0


class ChatSession(BaseModel):
    """MongoDB document model for chat sessions."""

    id: str
    user_id: str
    session_type: ChatSessionType
    title: str
    message_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    last_message_at: Optional[datetime] = None
    knowledge_base_ids: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


class ChatMessage(BaseModel):
    """MongoDB document model for chat messages."""

    id: str
    session_id: str
    user_id: str
    role: MessageRole
    content: str
    status: MessageStatus
    tool_invocations: List[ToolInvocation] = Field(default_factory=list)
    sql_queries: List[str] = Field(default_factory=list)
    task_sequence: Optional[TaskSequence] = None
    token_usage: Optional[TokenUsageInfo] = None
    created_at: datetime
    updated_at: datetime


class TokenUsage(BaseModel):
    """MongoDB document model for token usage tracking."""

    id: str
    message_id: str
    session_id: str
    endpoint: str
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    cost: float
    model: str
    created_at: datetime


class MessageVote(BaseModel):
    """MongoDB document model for message votes."""

    id: str
    message_id: str
    user_id: str
    vote_type: str  # "up" or "down"
    created_at: datetime
    updated_at: datetime
