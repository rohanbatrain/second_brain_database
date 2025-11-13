"""Request and response models for chat API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .chat_models import ToolInvocation, TokenUsageInfo
from .enums import ChatSessionType, MessageRole, MessageStatus, VoteType


class ChatSessionCreate(BaseModel):
    """Request model for creating a chat session."""

    session_type: ChatSessionType = ChatSessionType.GENERAL
    title: Optional[str] = None
    knowledge_base_ids: List[str] = Field(default_factory=list)


class ChatMessageCreate(BaseModel):
    """Request model for creating a chat message."""

    content: str
    state: Optional[str] = None  # Override routing: sql, rag, vector
    model_id: Optional[str] = None  # Override default model
    web_search_enabled: bool = False
    structured_knowledge_base_id: Optional[str] = None
    vector_knowledge_base_id: Optional[str] = None


class ChatSessionResponse(BaseModel):
    """Response model for chat session."""

    id: str
    user_id: str
    session_type: ChatSessionType
    title: str
    message_count: int
    total_tokens: int = 0
    total_cost: float = 0.0
    last_message_at: Optional[datetime] = None
    knowledge_base_ids: List[str]
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


class ChatMessageResponse(BaseModel):
    """Response model for chat message."""

    id: str
    session_id: str
    user_id: str
    role: MessageRole
    content: str
    status: MessageStatus
    tool_invocations: List[ToolInvocation] = Field(default_factory=list)
    sql_queries: List[str] = Field(default_factory=list)
    token_usage: Optional[TokenUsageInfo] = None
    created_at: datetime
    updated_at: datetime


class MessageVoteCreate(BaseModel):
    """Request model for voting on a message."""

    vote_type: VoteType


class TokenUsageSummaryResponse(BaseModel):
    """Response model for token usage summary."""

    total_tokens: int
    total_cost: float
    total_messages: int
    model_breakdown: Dict[str, Any]
    date_range: Dict[str, Optional[str]]
