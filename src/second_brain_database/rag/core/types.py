"""
RAG Core Types and Schemas

Type definitions, data models, and schemas for the RAG system.
Provides consistent type safety and validation across all components.
"""

from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Union
import uuid

from pydantic import BaseModel, Field, validator


# Enums
class DocumentStatus(str, Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    DELETED = "deleted"


class QueryType(str, Enum):
    """Types of queries."""
    SEMANTIC = "semantic"  # Semantic/vector search
    VECTOR = "vector"      # Alias for semantic
    KEYWORD = "keyword"    # Keyword-based search
    HYBRID = "hybrid"      # Combined semantic + keyword
    CHAT = "chat"          # Conversational queries


class ResponseType(str, Enum):
    """Types of responses."""
    DIRECT = "direct"
    STREAMING = "streaming"
    BATCH = "batch"


# Base Models
class BaseRAGModel(BaseModel):
    """Base model for all RAG data structures."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Document Models
class DocumentMetadata(BaseModel):
    """Document metadata structure."""
    
    title: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    
    # Processing metadata
    processing_time: Optional[float] = None
    chunk_count: Optional[int] = None
    extracted_images: Optional[int] = None
    extracted_tables: Optional[int] = None
    
    # Custom metadata
    tags: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """Document chunk structure."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    chunk_index: int
    content: str
    
    # Position information
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    page_number: Optional[int] = None
    
    # Embedding information
    embedding: Optional[List[float]] = None
    embedding_model: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @validator('content')
    def validate_content(cls, v):
        """Validate that content is not empty."""
        if not v or not v.strip():
            raise ValueError("Chunk content cannot be empty")
        return v.strip()


class Document(BaseRAGModel):
    """Document model."""
    
    # Basic information
    filename: str
    user_id: str
    file_path: Optional[str] = None
    
    # Content
    content: Optional[str] = None
    chunks: List[DocumentChunk] = Field(default_factory=list)
    
    # Status and processing
    status: DocumentStatus = DocumentStatus.PENDING
    processing_error: Optional[str] = None
    
    # Metadata
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    
    # Vector store information
    vector_store_id: Optional[str] = None
    collection_name: Optional[str] = None
    
    @validator('filename')
    def validate_filename(cls, v):
        """Validate filename."""
        if not v or not v.strip():
            raise ValueError("Filename cannot be empty")
        return v.strip()


# Query Models
class QueryContext(BaseModel):
    """Query context information."""
    
    # User information
    user_id: str
    conversation_id: Optional[str] = None
    
    # Query parameters
    top_k: int = Field(default=5, ge=1, le=100)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    # Filtering
    document_filters: Dict[str, Any] = Field(default_factory=dict)
    metadata_filters: Dict[str, Any] = Field(default_factory=dict)
    
    # Processing options
    use_llm: bool = True
    streaming: bool = False
    include_citations: bool = True
    
    # Advanced options
    rerank_results: bool = True
    expand_query: bool = False
    custom_prompt: Optional[str] = None


class SearchResult(BaseModel):
    """Search result structure."""
    
    # Document information
    document_id: str
    chunk_id: str
    content: str
    
    # Relevance information
    score: float = Field(ge=0.0, le=1.0)
    rank: int = Field(ge=1)
    
    # Position information
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    page_number: Optional[int] = None
    
    # Metadata
    document_metadata: Dict[str, Any] = Field(default_factory=dict)
    chunk_metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    """Query request structure."""
    
    query: str
    context: QueryContext
    query_type: QueryType = QueryType.HYBRID
    
    @validator('query')
    def validate_query(cls, v):
        """Validate query is not empty."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")
        return v.strip()


# Response Models
class CitationInfo(BaseModel):
    """Citation information."""
    
    document_id: str
    document_title: Optional[str] = None
    page_number: Optional[int] = None
    chunk_id: str
    relevance_score: float


class QueryResponse(BaseModel):
    """Query response structure."""
    
    # Request information
    query: str
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    
    # Response content
    answer: Optional[str] = None
    chunks: List[SearchResult] = Field(default_factory=list)
    citations: List[CitationInfo] = Field(default_factory=list)
    
    # Response metadata
    response_type: ResponseType = ResponseType.DIRECT
    processing_time: Optional[float] = None
    token_usage: Optional[Dict[str, int]] = None
    
    # Quality metrics
    confidence_score: Optional[float] = None
    chunk_count: int = 0
    
    # Status information
    success: bool = True
    error: Optional[str] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Streaming Models
class StreamingChunk(BaseModel):
    """Streaming response chunk."""
    
    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    chunk_type: str = "text"  # text, citation, metadata
    is_final: bool = False
    
    # Optional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Chat Models
class ChatMessage(BaseModel):
    """Chat message structure."""
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # user, assistant, system
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Optional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Conversation(BaseRAGModel):
    """Conversation structure."""
    
    user_id: str
    title: Optional[str] = None
    messages: List[ChatMessage] = Field(default_factory=list)
    
    # Context information
    document_context: List[str] = Field(default_factory=list)  # Document IDs
    
    # Status
    is_active: bool = True
    
    @validator('messages')
    def validate_messages_order(cls, v):
        """Validate messages are in chronological order."""
        if len(v) > 1:
            for i in range(1, len(v)):
                if v[i].timestamp < v[i-1].timestamp:
                    raise ValueError("Messages must be in chronological order")
        return v


# System Models
class SystemStatus(BaseModel):
    """System status information."""
    
    # Service status
    vector_store_status: str = "unknown"
    llm_status: str = "unknown"
    document_processing_status: str = "unknown"
    
    # Statistics
    total_documents: int = 0
    total_chunks: int = 0
    total_queries_today: int = 0
    
    # Performance metrics
    avg_query_time: Optional[float] = None
    avg_processing_time: Optional[float] = None
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HealthCheck(BaseModel):
    """Health check response."""
    
    status: str = "healthy"  # healthy, degraded, unhealthy
    services: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: Optional[str] = None


# Type aliases for common types
DocumentList = List[Document]
ChunkList = List[DocumentChunk]
ResultList = List[SearchResult]
MessageList = List[ChatMessage]

# Union types for flexible inputs
DocumentInput = Union[str, bytes, Dict[str, Any]]
QueryInput = Union[str, QueryRequest]
ResponseOutput = Union[QueryResponse, AsyncIterator[StreamingChunk]]

# Configuration types
ConfigDict = Dict[str, Any]
MetadataDict = Dict[str, Any]
FilterDict = Dict[str, Any]