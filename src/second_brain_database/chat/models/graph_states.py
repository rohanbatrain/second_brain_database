"""Graph state models for LangGraph workflows."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    """Model for document metadata in graph state."""

    id: str
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    score: Optional[float] = None


class GraphState(BaseModel):
    """Base state model for LangGraph workflows.
    
    This model represents the state passed between graph nodes during execution.
    It tracks the question, retrieved documents, generated contexts, final response,
    execution status, and performance metrics.
    
    Requirements: 2.1, 2.3, 2.4, 2.5
    """

    question: str
    session_id: str
    documents: List[Document] = Field(default_factory=list)
    contexts: List[str] = Field(default_factory=list)
    generation: str = ""
    success: bool = False
    error: Optional[str] = None
    token_usage: Dict[str, int] = Field(default_factory=dict)
    execution_time: float = 0.0


class MasterGraphState(GraphState):
    """State model for master workflow orchestration.
    
    Extends GraphState with additional fields for conversation history management,
    routing decisions, and workflow state tracking. Used by MasterWorkflowGraph
    to coordinate between VectorRAG and General Chat workflows.
    
    Requirements: 2.2, 5.2
    """

    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    state: str = "normal"  # sql, rag, vector, normal
    web_search_enabled: bool = False
    knowledge_base_id: Optional[str] = None
    route_decision: Optional[str] = None
