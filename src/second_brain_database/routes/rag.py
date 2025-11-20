"""
Consolidated RAG API Routes

Complete REST API endpoints for RAG system with Celery integration for async processing.
Combines document upload, processing, querying, and system management in a unified interface.

Features:
- Document upload with sync/async processing
- RAG queries with conversation support  
- Vector search capabilities
- Batch processing via Celery
- System health monitoring
- Cache management
- Analytics and reporting

Usage:
    from .routes import rag
    app.include_router(rag.router, prefix="/api")
"""

from datetime import datetime
from enum import Enum
import time
from typing import Any, Dict, List, Optional, Union
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, status, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from ..managers.logging_manager import get_logger
# Lazy import to avoid loading embedding model at startup
# from ..rag import RAGSystem
from ..rag.core.types import DocumentStatus, QueryType
from ..services.document_service import document_service
from ..tasks.celery_app import celery_app

# Import consolidated Celery tasks
from ..tasks.rag_tasks import (
    batch_process_documents_for_rag,
    cancel_rag_task,
    cleanup_expired_rag_data,
    generate_rag_analytics,
    get_rag_task_status,
    optimize_conversation_memory,
    process_document_for_rag,
    warm_rag_cache,
)
from .auth.dependencies import get_current_user_dep as get_current_user

router = APIRouter(prefix="/rag", tags=["RAG System"])
logger = get_logger(prefix="[RAGRoutes]")

# Lazy RAG system initialization
_rag_system = None

def get_rag_system():
    """Get RAG system instance (lazy loading)."""
    global _rag_system
    if _rag_system is None:
        from ..rag import RAGSystem
        _rag_system = RAGSystem()
        logger.info("RAG system initialized on demand")
    return _rag_system


# Enhanced Pydantic Models for Request/Response
class TaskStatus(str, Enum):
    """Task status enumeration."""
    PENDING = "pending"
    STARTED = "started"
    RETRY = "retry"
    FAILURE = "failure"
    SUCCESS = "success"
    REVOKED = "revoked"

class DocumentUploadRequest(BaseModel):
    """Request model for document upload with Celery processing."""
    content: str = Field(..., description="Document content to process")
    filename: Optional[str] = Field(None, description="Original filename")
    content_type: Optional[str] = Field("text/plain", description="MIME type")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    process_async: bool = Field(True, description="Use Celery for async processing")
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v):
        if not v or not v.strip():
            raise ValueError("Document content cannot be empty")
        return v.strip()

class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    document_id: str = Field(..., description="Unique document identifier")
    status: str = Field(..., description="Processing status")
    task_id: Optional[str] = Field(None, description="Celery task ID for async processing")
    chunks_created: Optional[int] = Field(None, description="Number of chunks created")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    message: str = Field(..., description="Status message")

class RAGQueryRequest(BaseModel):
    """Enhanced request model for RAG queries."""
    query: str = Field(..., description="The question or search query", min_length=1, max_length=1000)
    use_llm: bool = Field(True, description="Whether to generate an AI answer")
    max_results: int = Field(5, description="Maximum number of results to return", ge=1, le=20)
    similarity_threshold: float = Field(0.7, description="Minimum similarity score", ge=0.0, le=1.0)
    query_type: QueryType = Field(QueryType.SEMANTIC, description="Type of query to perform")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for context")
    collection_name: Optional[str] = Field("documents", description="Collection to search")
    include_metadata: bool = Field(True, description="Include document metadata")
    model: Optional[str] = Field(None, description="Specific LLM model to use")
    temperature: float = Field(0.7, description="Temperature for LLM generation", ge=0.0, le=2.0)

class BatchProcessingRequest(BaseModel):
    """Request model for batch document processing."""
    document_ids: List[str] = Field(..., description="List of document IDs to process")
    processing_options: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Processing options")
    priority: int = Field(5, ge=1, le=10, description="Processing priority")
    
    @field_validator('document_ids')
    @classmethod
    def validate_document_ids(cls, v):
        if not v:
            raise ValueError("At least one document ID is required")
        if len(v) > 100:
            raise ValueError("Cannot process more than 100 documents at once")
        return v

class TaskStatusResponse(BaseModel):
    """Response model for task status."""
    task_id: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="Current task status")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result if completed")
    progress: Optional[Dict[str, Any]] = Field(None, description="Task progress information")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: Optional[datetime] = Field(None, description="Task creation time")

class CacheOperationRequest(BaseModel):
    """Request model for cache operations."""
    operation: str = Field(..., description="Cache operation (warm, clear, status)")
    cache_type: Optional[str] = Field("all", description="Type of cache to operate on")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Operation parameters")
    
    @field_validator('operation')
    @classmethod
    def validate_operation(cls, v):
        allowed_ops = ['warm', 'clear', 'status']
        if v not in allowed_ops:
            raise ValueError(f"Operation must be one of: {allowed_ops}")
        return v

class AnalyticsRequest(BaseModel):
    """Request model for analytics generation."""
    report_type: str = Field(..., description="Type of analytics report")
    time_period_hours: int = Field(24, ge=1, le=168, description="Time period in hours")
    
    @field_validator('report_type')
    @classmethod
    def validate_report_type(cls, v):
        allowed_types = ['usage', 'performance', 'system']
        if v not in allowed_types:
            raise ValueError(f"Report type must be one of: {allowed_types}")
        return v


class DocumentChunk(BaseModel):
    """Model for document chunks in search results."""
    text: str
    score: float
    metadata: Dict[str, Any]


class RAGQueryResponse(BaseModel):
    """Response model for RAG queries."""
    query: str
    answer: Optional[str] = None
    chunks: List[DocumentChunk]
    sources: List[Dict[str, Any]]
    chunk_count: int
    timestamp: str
    processing_time_ms: Optional[float] = None


class RAGStatusResponse(BaseModel):
    """Response model for RAG system status."""
    status: str
    llamaindex_enabled: bool
    vector_search_available: bool
    ollama_available: bool
    document_count: Optional[int] = None
    last_index_update: Optional[str] = None
    version: str = "1.0.0"


class VectorSearchRequest(BaseModel):
    """Request model for vector-only search."""
    query: str = Field(..., description="The search query", min_length=1, max_length=1000)
    max_results: int = Field(5, description="Maximum number of results to return", ge=1, le=20)
    similarity_threshold: float = Field(0.7, description="Minimum similarity score for results", ge=0.0, le=1.0)
    metadata_filter: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filters")


# Enhanced API Endpoints with Celery Integration

@router.post("/documents/upload", response_model=DocumentUploadResponse, summary="Upload Document with Async Processing",
description="""
Upload and process a document with optional asynchronous processing via Celery.

This endpoint is designed for flexibility, allowing for both immediate processing for smaller documents and robust, scalable background processing for larger files.

**Key Features:**
- **Sync & Async Processing:** Choose between immediate results or background processing with Celery.
- **Progress Tracking:** Asynchronous tasks return a `task_id` for monitoring progress.
- **Automatic Indexing:** Documents are automatically chunked and indexed for RAG queries.
- **Use Cases:** Ideal for user-facing document uploads, data ingestion pipelines, and content management systems.
"""
)
async def upload_document(
    request: DocumentUploadRequest,
    current_user: dict = Depends(get_current_user),
    rag_system = Depends(get_rag_system)
):
    """
    Upload and process a document with optional async processing via Celery.
    
    **Features:**
    - Synchronous processing for immediate results
    - Asynchronous processing via Celery for large documents
    - Progress tracking with task IDs
    - Automatic chunking and indexing
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/documents/upload" \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "content": "Document text content...",
        "filename": "example.txt",
        "process_async": true
      }'
    ```
    """
    try:
        start_time = time.time()
        document_id = f"doc_{uuid.uuid4().hex[:8]}"
        user_id = str(current_user["_id"])
        
        logger.info(
            f"Document upload requested",
            extra={
                "document_id": document_id,
                "user_id": user_id,
                "async": request.process_async,
                "filename": request.filename
            }
        )
        
        if request.process_async:
            # Async processing via Celery
            task = process_document_for_rag.delay(
                document_id=document_id,
                user_id=user_id,
                processing_options={
                    "content": request.content,
                    "filename": request.filename,
                    "content_type": request.content_type,
                    "metadata": request.metadata
                }
            )
            
            return DocumentUploadResponse(
                document_id=document_id,
                status="processing",
                task_id=task.id,
                chunks_created=None,
                processing_time=None,
                message=f"Document queued for async processing. Task ID: {task.id}"
            )
        else:
            # Synchronous processing
            from ..rag.core.types import Document, DocumentChunk, DocumentMetadata
            
            # Create document chunks (simplified for this example)
            chunks: List[DocumentChunk] = []
            chunk_size = 1000
            content = request.content
            
            for i in range(0, len(content), chunk_size):
                chunk_content = content[i:i + chunk_size]
                chunks.append(DocumentChunk(
                    document_id=document_id,
                    chunk_index=len(chunks),
                    content=chunk_content,
                    start_char=i,
                    end_char=min(i + chunk_size, len(content)),
                    metadata={"chunk_id": len(chunks) + 1}
                ))
            
            # Create document
            document = Document(
                id=document_id,
                filename=request.filename or "unknown.txt",
                user_id=user_id,
                content=request.content,
                chunks=chunks,
                status=DocumentStatus.PROCESSED,
                metadata=DocumentMetadata(
                    title=request.filename or "Uploaded Document",
                    mime_type=request.content_type or "text/plain",
                    file_size=len(request.content),
                    processing_time=0.0,
                    word_count=len(request.content.split()),
                    page_count=1,
                    extracted_tables=0,
                    extracted_images=0
                )
            )
            
            # Index document
            result = await rag_system.vector_store_service.index_document(document)
            
            processing_time = time.time() - start_time
            
            return DocumentUploadResponse(
                document_id=document_id,
                status="completed",
                task_id=None,
                chunks_created=len(chunks),
                processing_time=processing_time,
                message="Document processed successfully"
            )
    except Exception as e:
        logger.error(f"Document upload failed: {e}", extra={"document_id": document_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document upload failed: {str(e)}"
        )


@router.post("/upload", response_model=DocumentUploadResponse, summary="Upload File (Multipart Form)",
description="""
Upload a file using multipart/form-data. This endpoint is designed for file uploads from web forms and Streamlit apps.

**Accepts:**
- Binary file data via multipart/form-data
- Form field: `file` (the uploaded file)
- Form field: `async_processing` (optional, default: true)

**Features:**
- Supports PDF, DOCX, PPTX, TXT, MD, and image files
- Automatic content extraction
- Async or sync processing
- Progress tracking via task_id
"""
)
async def upload_file(
    file: UploadFile = File(...),
    async_processing: bool = True,
    current_user: dict = Depends(get_current_user),
    rag_system = Depends(get_rag_system)
):
    """
    Upload a file for RAG processing via multipart/form-data.
    
    This endpoint accepts file uploads and converts them for processing.
    It's designed to work with web forms and Streamlit file uploaders.
    
    **Example Usage (curl):**
    ```bash
    curl -X POST "/rag/upload" \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -F "file=@document.pdf" \\
      -F "async_processing=true"
    ```
    """
    try:
        start_time = time.time()
        document_id = f"doc_{uuid.uuid4().hex[:8]}"
        user_id = str(current_user["_id"])
        
        # Read file content
        file_content = await file.read()
        filename = file.filename or "uploaded_file"
        content_type = file.content_type or "application/octet-stream"
        
        logger.info(
            f"File upload via multipart: {filename}",
            extra={
                "document_id": document_id,
                "user_id": user_id,
                "uploaded_file": filename,
                "size_bytes": len(file_content),
                "content_type": content_type,
                "async": async_processing
            }
        )
        
        # Process the uploaded file using the RAG system
        try:
            import io
            file_data = io.BytesIO(file_content)
            file_data.name = filename
            
            # Use RAG system to handle the upload
            result = await rag_system.process_and_index_document(
                file_data=file_data,
                filename=filename,
                user_id=user_id,
                content_type=content_type
            )
            
            processing_time = time.time() - start_time
            
            logger.info(
                f"Upload successful: {filename}",
                extra={
                    "document_id": result.get("document", {}).get("id"),
                    "chunks": result.get("document", {}).get("chunks"),
                    "processing_time": processing_time
                }
            )
            
            return DocumentUploadResponse(
                document_id=result.get("document", {}).get("id", document_id),
                status="completed",
                task_id=None,
                chunks_created=result.get("document", {}).get("chunks", 0),
                processing_time=processing_time,
                message=f"File '{filename}' processed and indexed successfully"
            )
            
        except Exception as e:
            logger.error(
                f"File processing failed: {e}",
                exc_info=True,
                extra={"uploaded_file": filename, "user_id": user_id}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to process file '{filename}': {str(e)}"
            )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"File upload failed: {e}",
            exc_info=True,
            extra={"uploaded_file": filename, "user_id": user_id}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.post("/query", response_model=RAGQueryResponse, summary="Query Documents with AI",
description="""
The core endpoint for interacting with the RAG system. 

This endpoint leverages the full power of the RAG pipeline to provide intelligent, context-aware answers to user queries. It supports conversation history, multiple query strategies, and real-time AI-powered answer generation.

**Key Features:**
- **Natural Language Queries:** Ask questions in plain English.
- **Conversation Memory:** Maintain context across multiple queries using a `conversation_id`.
- **Multiple Query Types:** Supports `semantic`, `keyword`, and `hybrid` search.
- **AI-Powered Answers:** Generates human-like answers based on the retrieved documents.
- **Real-Time & Responsive:** Optimized for fast, interactive applications.
"""
)
async def query_documents(
    request: RAGQueryRequest,
    current_user: dict = Depends(get_current_user),
    rag_system = Depends(get_rag_system)
):
    """
    Enhanced RAG query with conversation support and advanced features.
    
    **Features:**
    - Natural language queries with context
    - Conversation memory integration
    - Multiple query types (semantic, keyword, hybrid)
    - AI-powered answer generation
    - Real-time processing (not via Celery for responsiveness)
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/query" \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "query": "What are the key features of machine learning?",
        "use_llm": true,
        "query_type": "semantic",
        "conversation_id": "conv_123",
        "max_results": 5
      }'
    ```
    """
    start_time = time.time()
    
    try:
        user_id = str(current_user["_id"])
        query_id = f"query_{uuid.uuid4().hex[:8]}"
        
        logger.info(
            f"RAG query from user {user_id}: {request.query[:100]}...",
            extra={
                "query_id": query_id,
                "user_id": user_id,
                "query_type": request.query_type.value,
                "conversation_id": request.conversation_id
            }
        )
        
        # Execute RAG query using the consolidated system
        from ..rag.core.types import QueryContext, QueryRequest as CoreQueryRequest
        
        query_context = QueryContext(
            user_id=user_id,
            conversation_id=request.conversation_id,
            use_llm=request.use_llm,
        )
        
        core_request = CoreQueryRequest(
            query=request.query,
            query_type=request.query_type,
            context=query_context
        )
        
        result = await rag_system.query(
            query=request.query,
            user_id=user_id,
            conversation_id=request.conversation_id,
            use_llm=request.use_llm,
            max_results=request.max_results,
            similarity_threshold=request.similarity_threshold,
            query_type=request.query_type,
            collection_name=request.collection_name,
            include_metadata=request.include_metadata,
            model=request.model,
            temperature=request.temperature,
        )
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Convert chunks to proper format
        # RAG system returns "context_chunks", not "chunks"
        context_chunks = result.get("context_chunks", [])
        chunks = [
            DocumentChunk(
                text=chunk.get("text", chunk.get("content", "")),
                score=chunk.get("score", 0.0), 
                metadata=chunk.get("metadata", chunk.get("document_metadata", {}))
            )
            for chunk in context_chunks
        ]
        
        # Get timestamp from result or generate new one
        timestamp = result.get("timestamp", datetime.now().isoformat())
        
        response = RAGQueryResponse(
            query=result["query"],
            answer=result.get("answer"),
            chunks=chunks,
            sources=result.get("sources", []),
            chunk_count=len(chunks),
            timestamp=timestamp,
            processing_time_ms=processing_time
        )
        
        logger.info(
            f"RAG query completed: {len(chunks)} chunks, {processing_time:.1f}ms",
            extra={
                "user_id": user_id,
                "chunk_count": len(chunks),
                "processing_time_ms": processing_time,
                "has_answer": bool(result.get("answer")),
                "confidence": result.get("confidence", 0.0),
                "model_used": result.get("model_used", "unknown")
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"RAG query failed: {e}", exc_info=True, extra={"query_id": query_id, "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/batch/process", response_model=Dict[str, Any], summary="Batch Process Documents",
description="""
Process a large number of documents in a single, efficient operation using background workers.

This endpoint is a perfect use case for Celery, offloading long-running tasks from the main application thread to ensure the API remains responsive.

**Key Features:**
- **High-Throughput Processing:** Ingest hundreds of documents with a single API call.
- **Background Execution:** Powered by Celery for robust, asynchronous processing.
- **Progress Tracking:** Returns a `task_id` to monitor the status of the batch job.
- **Use Cases:** Ideal for large-scale data ingestion, backfill operations, and periodic indexing tasks.
"""
)
async def batch_process_documents_endpoint(
    request: BatchProcessingRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Process multiple documents in batch via Celery.
    
    **Perfect use case for Celery:**
    - Long-running batch operations
    - Progress tracking
    - Retry logic for failed documents
    - Queue management for high throughput
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/batch/process" \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "document_ids": ["doc1", "doc2", "doc3"],
        "priority": 5
      }'
    ```
    """
    try:
        user_id = str(current_user["_id"])
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        
        logger.info(
            f"Batch processing requested",
            extra={
                "batch_id": batch_id,
                "user_id": user_id,
                "document_count": len(request.document_ids),
                "priority": request.priority
            }
        )
        
        # Queue batch processing task
        task = batch_process_documents_for_rag.delay(
            document_ids=request.document_ids,
            user_id=user_id,
            processing_options=request.processing_options
        )
        
        # Estimate processing time (rough calculation)
        estimated_time = len(request.document_ids) * 5.0  # 5 seconds per document estimate
        
        return {
            "batch_id": batch_id,
            "task_id": task.id,
            "document_count": len(request.document_ids),
            "estimated_time": estimated_time,
            "status": "queued",
            "message": f"Batch processing queued with task ID: {task.id}"
        }
    
    except Exception as e:
        logger.error(f"Batch processing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch processing failed: {str(e)}"
        )


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse, summary="Get Task Status",
description="""
Monitor the status of an asynchronous task (e.g., document upload, batch processing) initiated via Celery.

This endpoint is crucial for building responsive applications that rely on background processing, providing clients with real-time updates on long-running operations.

**Returned Information:**
- **Task Status:** `pending`, `started`, `success`, `failure`, etc.
- **Progress:** Custom progress information for long-running tasks.
- **Result:** The output of the task once it completes successfully.
- **Error:** Detailed error information if the task fails.
"""
)
async def get_task_status_endpoint(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get status of a Celery task with comprehensive information.
    
    **Returns:**
    - Task status (pending, started, success, failure, etc.)
    - Progress information for long-running tasks
    - Results when completed
    - Error details if failed
    
    **Example Usage:**
    ```bash
    curl -X GET "/api/rag/tasks/celery_task_123/status" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        task_status = get_rag_task_status(task_id)
        
        if not task_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        
        return TaskStatusResponse(
            task_id=task_id,
            status=TaskStatus(task_status["status"]),
            result=task_status.get("result"),
            progress=task_status.get("info"),
            error=task_status.get("error") if task_status["failed"] else None,
            created_at=None  # Would need to be tracked in task metadata
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task status check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task status check failed: {str(e)}"
        )


@router.post("/tasks/{task_id}/cancel", summary="Cancel Task",
description="""
Request the cancellation of a running asynchronous task.

This endpoint provides users with more control over background processes, allowing them to stop tasks that are no longer needed.

**Note:** Cancellation is a request and may not be immediate, depending on the state of the task.
"""
)
async def cancel_task_endpoint(
    task_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a running Celery task.
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/tasks/celery_task_123/cancel" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        success = cancel_rag_task(task_id)
        
        if success:
            return {
                "task_id": task_id,
                "status": "cancelled",
                "message": "Task cancellation requested"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to cancel task {task_id}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Task cancellation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task cancellation failed: {str(e)}"
        )


@router.post("/cache/operations", summary="Cache Operations",
description="""
Perform administrative operations on the RAG system's cache to manage performance and resources.

This endpoint provides powerful tools for cache management, which should be used with care in a production environment.

**Available Operations:**
- **`warm`:** Pre-populate the cache with popular queries or documents to improve initial response times.
- **`clear`:** Purge the cache of all or expired entries to free up resources.
- **`status`:** Get real-time statistics on cache performance, including hit rate and size.
"""
)
async def cache_operations(
    request: CacheOperationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Perform cache operations via Celery for optimal performance.
    
    **Operations:**
    - `warm`: Pre-populate cache with popular queries
    - `clear`: Clear expired or all cache entries
    - `status`: Get cache performance statistics
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/cache/operations" \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "operation": "warm",
        "cache_type": "query_result"
      }'
    ```
    """
    try:
        user_id = str(current_user["_id"])
        
        logger.info(
            f"Cache operation requested",
            extra={
                "operation": request.operation,
                "user_id": user_id,
                "cache_type": request.cache_type
            }
        )
        
        if request.operation == "warm":
            # Queue cache warming task
            task = warm_rag_cache.delay(
                user_id=user_id,
                cache_levels=request.parameters.get("cache_levels")
            )
            
            return {
                "operation": request.operation,
                "status": "processing",
                "task_id": task.id,
                "message": "Cache warming queued"
            }
        
        elif request.operation == "clear":
            # Queue cache clearing task
            task = cleanup_expired_rag_data.delay(
                max_age_days=request.parameters.get("max_age_days", 30)
            )
            
            return {
                "operation": request.operation,
                "status": "processing", 
                "task_id": task.id,
                "message": "Cache clearing queued"
            }
        
        elif request.operation == "status":
            # Get immediate cache status (sync operation)
            from ..rag.advanced.result_caching import get_monitoring_system
            
            monitoring = get_monitoring_system()
            cache_stats = await monitoring.alerts.get_cache_stats()
            
            return {
                "operation": request.operation,
                "status": "completed",
                "result": {
                    "total_entries": cache_stats.total_entries,
                    "hit_rate": cache_stats.hit_rate,
                    "size_mb": cache_stats.total_size_bytes / (1024 * 1024),
                    "cache_levels": cache_stats.cache_levels
                },
                "message": "Cache status retrieved"
            }
        
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported cache operation: {request.operation}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cache operation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cache operation failed: {str(e)}"
        )


@router.post("/analytics/generate", summary="Generate Analytics",
description="""
Trigger the generation of comprehensive analytics reports for the RAG system.

This is an asynchronous operation that returns a `task_id` for tracking the report generation process. The generated reports provide valuable insights into system health, performance, and usage patterns.

**Report Types:**
- **`usage`:** Insights into user activity, popular queries, and document access patterns.
- **`performance`:** Metrics on query latency, indexing speed, and resource utilization.
- **`system`:** Overall system health, error rates, and cache performance.
"""
)
async def generate_analytics(
    request: AnalyticsRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Generate comprehensive analytics reports via Celery.
    
    **Report Types:**
    - `usage`: User activity and query patterns
    - `performance`: System performance metrics
    - `system`: Overall system health and statistics
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/analytics/generate" \\
      -H "Authorization: Bearer YOUR_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "report_type": "usage",
        "time_period_hours": 24
      }'
    ```
    """
    try:
        user_id = str(current_user["_id"])
        report_id = f"report_{uuid.uuid4().hex[:8]}"
        
        logger.info(
            f"Analytics generation requested",
            extra={
                "report_id": report_id,
                "user_id": user_id,
                "report_type": request.report_type,
                "time_period": request.time_period_hours
            }
        )
        
        # Queue analytics generation task
        task = generate_rag_analytics.delay(
            user_id=user_id,
            time_period_hours=request.time_period_hours
        )
        
        return {
            "report_id": report_id,
            "task_id": task.id,
            "report_type": request.report_type,
            "status": "generating",
            "message": f"Analytics report queued with task ID: {task.id}"
        }
    
    except Exception as e:
        logger.error(f"Analytics generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analytics generation failed: {str(e)}"
        )


@router.post("/search", response_model=RAGQueryResponse, summary="Vector Search Only",
description="""
Perform a direct vector search on the indexed documents, bypassing the AI answer generation step.

This endpoint provides a fast and efficient way to find relevant document chunks based on semantic similarity. It's ideal for applications that need to build custom workflows on top of the search results.

**Use Cases:**
- **Fast Document Discovery:** Quickly find documents related to a query.
- **Semantic Search:** Go beyond keywords to find conceptually similar content.
- **Building Custom Workflows:** Use the raw search results as input for other processes.
"""
)
async def vector_search(
    request: VectorSearchRequest,
    current_user: dict = Depends(get_current_user),
    rag_system = Depends(get_rag_system)
):
    """
    Perform vector search without AI generation.
    
    This endpoint provides direct access to the vector search functionality,
    returning relevant document chunks without LLM processing.
    
    **Use Cases:**
    - Fast document discovery
    - Semantic search
    - Finding similar content
    - Building custom workflows
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/search" \\
      -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
      -H "Content-Type: application/json" \\
      -d '{
        "query": "neural networks",
        "max_results": 10,
        "similarity_threshold": 0.6
      }'
    ```
    """
    try:
        user_id = str(current_user["_id"])
        
        # Use RAG system for vector search
        result = await rag_system.query(
            query=request.query,
            user_id=user_id,
            use_llm=False,  # Vector search only
            top_k=request.max_results,
            similarity_threshold=request.similarity_threshold
        )
        
        # Convert chunks to proper format
        context_chunks = result.get("context_chunks", [])
        chunks = [
            DocumentChunk(
                text=chunk.get("text", chunk.get("content", "")),
                score=chunk.get("score", 0.0),
                metadata=chunk.get("metadata", chunk.get("document_metadata", {}))
            )
            for chunk in context_chunks
        ]
        
        return RAGQueryResponse(
            query=result["query"],
            answer=None,  # No LLM answer for vector search
            chunks=chunks,
            sources=result.get("sources", []),
            chunk_count=len(chunks),
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/memory/optimize", summary="Optimize Conversation Memory",
description="""
Trigger a background task to optimize the storage of conversation memory.

This is a maintenance operation designed to manage resources and improve the performance of conversation-aware queries over time.

**Optimization Strategies:**
- **`adaptive`:** Automatically selects the best optimization approach.
- **`sliding_window`:** Retains only the most recent turns of a conversation.
- **`summarization`:** Compresses older parts of a conversation into summaries.
- **`hierarchical`:** Organizes conversations based on importance or topic.
"""
)
async def optimize_conversation_memory_endpoint(
    current_user: dict = Depends(get_current_user),
    strategy: str = Query("adaptive", description="Optimization strategy")
):
    """
    Optimize conversation memory storage via Celery background task.
    
    **Strategies:**
    - `adaptive`: Automatically choose best optimization approach
    - `sliding_window`: Keep only recent conversation turns
    - `summarization`: Compress old conversations into summaries
    - `hierarchical`: Organize conversations by importance
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/memory/optimize?strategy=adaptive" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        user_id = str(current_user["_id"])
        
        logger.info(
            f"Memory optimization requested",
            extra={
                "user_id": user_id,
                "strategy": strategy
            }
        )
        
        # Queue memory optimization task
        task = optimize_conversation_memory.delay(
            user_id=user_id,
            optimization_strategy=strategy
        )
        
        return {
            "operation": "memory_optimization",
            "strategy": strategy,
            "status": "processing",
            "task_id": task.id,
            "message": f"Memory optimization queued with strategy: {strategy}"
        }
    
    except Exception as e:
        logger.error(f"Memory optimization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Memory optimization failed: {str(e)}"
        )


@router.get("/status", response_model=RAGStatusResponse, summary="Get Enhanced RAG System Status",
description="""
Get a comprehensive, real-time overview of the RAG system's health and operational status.

This endpoint is essential for monitoring, debugging, and ensuring the system is running optimally.

**Status Information Provided:**
- **Core Services:** Health of the RAG pipeline, including document processing, vector store, and LLM services.
- **Celery Workers:** Status of the background task processing system.
- **Document Statistics:** Total number of indexed documents for the current user.
- **Cache Performance:** Insights into cache hit rate, size, and total entries.
"""
)
async def get_rag_status(
    current_user: dict = Depends(get_current_user),
    rag_system = Depends(get_rag_system)
):
    """
    Get comprehensive RAG system status including Celery workers.
    
    **Enhanced Status Information:**
    - RAG system components health
    - Celery worker status and queues
    - Document statistics
    - Performance metrics
    - Cache status
    
    **Example Usage:**
    ```bash
    curl -X GET "/api/rag/status" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        user_id = str(current_user["_id"])
        
        # Get RAG system status
        system_status = await rag_system.get_system_status()
        
        # Check Celery worker status
        try:
            inspect = celery_app.control.inspect()
            worker_stats = inspect.stats()
            active_queues = inspect.active_queues()
            
            celery_status = {
                "workers_online": len(worker_stats) if worker_stats else 0,
                "rag_queues": len([q for queues in (active_queues or {}).values() for q in queues if 'rag' in q.get('name', '')]),
                "total_queues": sum(len(queues) for queues in (active_queues or {}).values()),
                "status": "healthy" if worker_stats else "no_workers"
            }
        except Exception as e:
            celery_status = {
                "workers_online": 0,
                "status": "unavailable",
                "error": str(e)
            }
        
        # Get document count
        try:
            from ..database import db_manager
            await db_manager.connect()
            collection = db_manager.get_collection("documents")
            doc_count = await collection.count_documents({"user_id": user_id})
        except Exception:
            doc_count = 0
        
        # Get cache statistics
        try:
            from ..rag.monitoring import get_monitoring_system
            monitoring = get_monitoring_system()
            cache_stats = await monitoring.alerts.get_cache_stats()
            cache_status = {
                "hit_rate": cache_stats.hit_rate,
                "total_entries": cache_stats.total_entries,
                "size_mb": cache_stats.total_size_bytes / (1024 * 1024)
            }
        except Exception:
            cache_status = {"status": "unavailable"}
        
        # Enhanced status response
        enhanced_status = {
            **system_status,
            "celery": celery_status,
            "user_documents": doc_count,
            "cache": cache_status,
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0"  # Updated version with Celery integration
        }
        
        return RAGStatusResponse(
            status=enhanced_status.get("rag_system", {}).get("status", "unknown"),
            llamaindex_enabled=enhanced_status.get("services", {}).get("document_processing", {}).get("status") == "available",
            vector_search_available=enhanced_status.get("services", {}).get("vector_store", {}).get("status") == "available",
            ollama_available=enhanced_status.get("services", {}).get("llm_service", {}).get("status") == "available",
            document_count=doc_count,
            last_index_update=enhanced_status.get("timestamp")
        )
        
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


@router.get("/documents", summary="List Indexed Documents",
description="""
Retrieve a paginated list of the user's indexed documents that are available for RAG queries.

This endpoint is useful for building user interfaces that allow users to browse and manage their document library.

**Pagination:**
- **`limit`:** The maximum number of documents to return in a single request.
- **`offset`:** The number of documents to skip, for fetching subsequent pages.
"""
)
async def list_indexed_documents(
    limit: int = Query(20, description="Maximum number of documents to return", ge=1, le=100),
    offset: int = Query(0, description="Number of documents to skip", ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    List documents available for RAG queries.
    
    **Parameters:**
    - `limit`: Maximum number of documents to return (1-100)
    - `offset`: Number of documents to skip for pagination
    
    **Returns:**
    - List of documents with metadata
    - Total count
    - Processing status
    
    **Example Usage:**
    ```bash
    curl -X GET "/api/rag/documents?limit=10&offset=0" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        user_id = str(current_user["_id"])
        
        # Get user's documents
        documents = await document_service.get_document_list(
            user_id=user_id,
            limit=limit,
            offset=offset,
            include_content=False
        )
        
        # Get total count
        try:
            from ..database import db_manager
            collection = db_manager.get_collection("processed_documents")
            total = await collection.count_documents({"user_id": user_id})
        except Exception:
            total = len(documents)
        
        return {
            "documents": documents,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": total > (offset + len(documents))
        }
        
    except Exception as e:
        logger.error(f"Document listing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Document listing failed: {str(e)}")


@router.get("/health", summary="Health Check",
description="""
A simple, unauthenticated health check endpoint for the RAG service.

This endpoint is primarily intended for use by monitoring systems and load balancers to verify that the service is running and responsive. It does not perform a deep check of all system components.
"""
)
async def rag_health_check():
    """
    Simple health check for the RAG system.
    
    Returns basic system health without requiring authentication.
    Useful for monitoring and load balancer health checks.
    """
    try:
        # Basic health check
        health_status = {
            "status": "healthy",
            "service": "rag",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "document_service": bool(document_service)
            }
        }
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "service": "rag", 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.delete("/documents/{document_id}", response_model=dict, summary="Delete Document",
description="""
Delete a document and its associated vectors from the RAG system.

This is a permanent operation that removes the document and all of its indexed chunks from the vector store, making it unavailable for future queries. A background task is also triggered to ensure all related data is cleaned up.
"""
)
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    rag_system = Depends(get_rag_system)
):
    """
    Delete a document and its associated vectors.
    
    **Parameters:**
    - `document_id`: ID of the document to delete
    
    **Returns:**
    - Deletion confirmation with cleanup details
    
    **Example Usage:**
    ```bash
    curl -X DELETE "/api/rag/documents/doc123" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        user_id = str(current_user["_id"])
        
        # Delete from RAG system (this handles vector store cleanup)
        success = await rag_system.delete_document(
            document_id=document_id,
            user_id=user_id
        )
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Document not found or already deleted"
            )
        
        # Schedule cleanup of any remaining references
        cleanup_task = cleanup_expired_rag_data.delay(
            user_id=user_id,
            document_ids=[document_id]
        )
        
        return {
            "success": True,
            "document_id": document_id,
            "message": "Document deleted successfully",
            "cleanup_task_id": cleanup_task.id,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete document: {str(e)}"
        )


@router.post("/documents/{document_id}/reindex", response_model=dict, summary="Reindex Document",
description="""
Trigger an asynchronous reindexing of a specific document.

This is useful if the document's content has been updated or if there was an issue with the initial indexing process. The `force` parameter can be used to bypass checks and reindex the document regardless of its current state.
"""
)
async def reindex_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
    force: bool = Query(False, description="Force reindexing even if up to date")
):
    """
    Reindex a specific document in the vector store.
    
    **Parameters:**
    - `document_id`: ID of the document to reindex
    - `force`: Force reindexing even if document appears up to date
    
    **Returns:**
    - Reindexing task information
    
    **Example Usage:**
    ```bash
    curl -X POST "/api/rag/documents/doc123/reindex?force=true" \\
      -H "Authorization: Bearer YOUR_TOKEN"
    ```
    """
    try:
        user_id = str(current_user["_id"])
        
        # Submit reindexing task
        task = process_document_for_rag.delay(
            document_id=document_id,
            user_id=user_id,
            force_reindex=force
        )
        
        return {
            "task_id": task.id,
            "document_id": document_id,
            "status": "submitted",
            "force_reindex": force,
            "message": "Document reindexing started",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error reindexing document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start reindexing: {str(e)}"
        )


# Example usage documentation
@router.get("/examples", summary="API Usage Examples",
description="""
A developer-friendly endpoint that provides practical, copy-paste-ready examples of how to use the RAG API.

This endpoint makes it easier for developers to integrate the API into their applications by providing examples for various programming languages and tools.
"""
)
async def get_usage_examples():
    """
    Get example API calls and usage patterns.
    
    Returns practical examples of how to use the RAG API endpoints
    with different programming languages and tools.
    """
    examples = {
        "curl_examples": {
            "basic_query": """curl -X POST "http://localhost:8000/api/rag/query" \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "What are the main concepts in machine learning?",
    "use_llm": true,
    "max_results": 5
  }'""",
            
            "vector_search": """curl -X POST "http://localhost:8000/api/rag/search" \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "neural networks",
    "max_results": 10,
    "similarity_threshold": 0.6
  }'""",
            
            "status_check": """curl -X GET "http://localhost:8000/api/rag/status" \\
  -H "Authorization: Bearer YOUR_JWT_TOKEN\""""
        },
        
        "python_examples": {
            "basic_usage": """
import requests

# RAG Query
response = requests.post(
    "http://localhost:8000/api/rag/query",
    headers={"Authorization": "Bearer YOUR_JWT_TOKEN"},
    json={
        "query": "Explain deep learning",
        "use_llm": True,
        "max_results": 5
    }
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Sources: {len(result['sources'])}")
""",
            
            "async_usage": """
import httpx
import asyncio

async def query_rag(query: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/rag/query",
            headers={"Authorization": "Bearer YOUR_JWT_TOKEN"},
            json={"query": query, "use_llm": True}
        )
        return response.json()

# Usage
result = asyncio.run(query_rag("What is machine learning?"))
"""
        },
        
        "javascript_examples": {
            "fetch_api": """
// RAG Query with Fetch API
const response = await fetch('http://localhost:8000/api/rag/query', {
    method: 'POST',
    headers: {
        'Authorization': 'Bearer YOUR_JWT_TOKEN',
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        query: 'Explain artificial intelligence',
        use_llm: true,
        max_results: 5
    })
});

const result = await response.json();
console.log('Answer:', result.answer);
console.log('Sources:', result.sources.length);
""",
            
            "axios": """
// RAG Query with Axios
const axios = require('axios');

const response = await axios.post(
    'http://localhost:8000/api/rag/query',
    {
        query: 'What is natural language processing?',
        use_llm: true
    },
    {
        headers: {
            'Authorization': 'Bearer YOUR_JWT_TOKEN',
            'Content-Type': 'application/json'
        }
    }
);

console.log(response.data);
"""
        }
    }
    
    return {
        "description": "RAG API Usage Examples",
        "endpoints": {
            "/api/rag/query": "Query documents with AI generation and conversation support",
            "/api/rag/search": "Vector search without AI",
            "/api/rag/upload": "Upload and process documents (sync/async)",
            "/api/rag/batch-process": "Batch process multiple documents",
            "/api/rag/status": "Get comprehensive system status",
            "/api/rag/documents": "List user documents with pagination",
            "/api/rag/documents/{id}": "Delete specific document",
            "/api/rag/documents/{id}/reindex": "Reindex specific document",
            "/api/rag/tasks/{task_id}": "Get task status and results",
            "/api/rag/tasks/{task_id}/cancel": "Cancel running task",
            "/api/rag/cache": "Manage RAG cache operations",
            "/api/rag/analytics": "Generate usage analytics",
            "/api/rag/memory/optimize": "Optimize conversation memory",
            "/api/rag/health": "Quick health check"
        },
        "examples": examples,
        "authentication": "All endpoints except /health require JWT authentication",
        "rate_limits": "Standard API rate limits apply",
        "documentation": "See /docs for interactive API documentation"
    }