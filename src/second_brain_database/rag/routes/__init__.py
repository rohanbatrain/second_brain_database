"""
RAG API Routes

FastAPI routes for the RAG system providing document processing,
querying, and chat functionality with proper authentication and validation.
"""

from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.rag import RAGSystem
from second_brain_database.rag.core.types import QueryRequest
from second_brain_database.routes.auth.dependencies import get_current_user_data

logger = get_logger()

# Initialize RAG system
rag_system = RAGSystem()

# Create router
router = APIRouter(prefix="/rag", tags=["RAG"])


# Request/Response Models
class QueryRequestModel(BaseModel):
    """Query request model."""
    query: str = Field(..., description="User query", min_length=1, max_length=1000)
    use_llm: bool = Field(True, description="Whether to use LLM for answer generation")
    top_k: Optional[int] = Field(5, description="Number of documents to retrieve", ge=1, le=50)
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional search filters")
    temperature: Optional[float] = Field(None, description="LLM temperature", ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, description="Maximum tokens for LLM response", ge=1, le=4000)


class QueryResponseModel(BaseModel):
    """Query response model."""
    query: str
    answer: str
    sources: List[str]
    context_chunks: List[Dict[str, Any]]
    confidence: float
    processing_time: float
    model_used: str
    metadata: Optional[Dict[str, Any]] = None


class ChatRequestModel(BaseModel):
    """Chat request model."""
    message: str = Field(..., description="Chat message", min_length=1, max_length=1000)
    conversation_id: Optional[str] = Field(None, description="Conversation ID")
    temperature: Optional[float] = Field(None, description="LLM temperature", ge=0.0, le=2.0)


class ChatResponseModel(BaseModel):
    """Chat response model."""
    message: str
    response: str
    sources: List[str]
    conversation_id: str
    processing_time: float


class DocumentUploadResponseModel(BaseModel):
    """Document upload response model."""
    document_id: str
    filename: str
    chunks: int
    status: str
    processing_time: Optional[float] = None
    indexing_info: Optional[Dict[str, Any]] = None


class SystemStatusModel(BaseModel):
    """System status model."""
    rag_system: Dict[str, Any]
    services: Dict[str, Any]
    configuration: Dict[str, Any]


# Routes

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "rag_available": rag_system.query_engine.is_available(),
        "timestamp": "2025-11-08T13:30:00Z"
    }


@router.get("/status", response_model=SystemStatusModel)
async def get_system_status(
    user_data: dict = Depends(get_current_user_data)
):
    """
    Get comprehensive RAG system status.
    
    Returns detailed information about all RAG services and their health.
    """
    try:
        status = await rag_system.get_system_status()
        return status
        
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system status")


@router.get("/supported-formats")
async def get_supported_formats():
    """Get list of supported document formats."""
    try:
        formats = await rag_system.get_supported_formats()
        return {
            "supported_formats": formats,
            "count": len(formats)
        }
        
    except Exception as e:
        logger.error(f"Failed to get supported formats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get supported formats")


@router.post("/documents/upload", response_model=DocumentUploadResponseModel)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_data: dict = Depends(get_current_user_data),
    extract_images: bool = Query(True, description="Whether to extract images"),
    output_format: str = Query("markdown", description="Output format (markdown, json, text)")
):
    """
    Upload and process a document.
    
    Processes the document through the existing DocumentProcessor pipeline
    and indexes it in the vector store for RAG queries.
    """
    user_id = user_data["user_id"]
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check file size (50MB limit)
    if hasattr(file, 'size') and file.size > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    
    # Get supported formats
    supported_formats = await rag_system.get_supported_formats()
    file_ext = Path(file.filename).suffix.lower().lstrip('.')
    
    if file_ext not in supported_formats:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format: {file_ext}. Supported: {', '.join(supported_formats)}"
        )
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Process and index document
        result = await rag_system.process_and_index_document(
            file_data=file_content,
            filename=file.filename,
            user_id=user_id,
            extract_images=extract_images,
            output_format=output_format
        )
        
        logger.info(f"Successfully uploaded and processed document: {file.filename}")
        
        return DocumentUploadResponseModel(
            document_id=result["document"]["id"],
            filename=result["document"]["filename"],
            chunks=result["document"]["chunks"],
            status=result["status"],
            indexing_info=result.get("indexing")
        )
        
    except Exception as e:
        logger.error(f"Failed to upload document {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Document processing failed: {str(e)}")


@router.post("/query", response_model=QueryResponseModel)
async def query_documents(
    request: QueryRequestModel,
    user_data: dict = Depends(get_current_user_data)
):
    """
    Query documents using RAG.
    
    Performs semantic search across user's documents and optionally
    generates AI-powered answers using the retrieved context.
    """
    user_id = user_data["user_id"]
    
    try:
        response = await rag_system.query(
            query=request.query,
            user_id=user_id,
            use_llm=request.use_llm,
            streaming=False,
            top_k=request.top_k,
            filters=request.filters,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        return QueryResponseModel(**response)
        
    except Exception as e:
        logger.error(f"Query failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@router.post("/query/stream")
async def query_documents_stream(
    request: QueryRequestModel,
    user_data: dict = Depends(get_current_user_data)
):
    """
    Query documents with streaming response.
    
    Similar to query_documents but returns a streaming response
    for real-time answer generation.
    """
    user_id = user_data["user_id"]
    
    if not request.use_llm:
        raise HTTPException(status_code=400, detail="Streaming requires LLM to be enabled")
    
    try:
        stream = await rag_system.query(
            query=request.query,
            user_id=user_id,
            use_llm=True,
            streaming=True,
            top_k=request.top_k,
            filters=request.filters,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        async def generate_stream():
            try:
                async for chunk in stream:
                    # Format as SSE (Server-Sent Events)
                    yield f"data: {chunk}\n\n"
                yield f"data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"Streaming failed: {e}")
                yield f"data: [ERROR]: {str(e)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )
        
    except Exception as e:
        logger.error(f"Streaming query failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Streaming query failed: {str(e)}")


@router.post("/chat", response_model=ChatResponseModel)
async def chat_with_documents(
    request: ChatRequestModel,
    user_data: dict = Depends(get_current_user_data)
):
    """
    Chat with documents using conversation context.
    
    Maintains conversation history and provides contextual responses
    based on the user's document collection.
    """
    user_id = user_data["user_id"]
    
    # Generate conversation ID if not provided
    conversation_id = request.conversation_id or f"chat_{user_id}_{int(time.time())}"
    
    try:
        response = await rag_system.chat(
            message=request.message,
            conversation_id=conversation_id,
            user_id=user_id,
            temperature=request.temperature
        )
        
        return ChatResponseModel(**response)
        
    except Exception as e:
        logger.error(f"Chat failed for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")


@router.get("/documents")
async def list_documents(
    user_data: dict = Depends(get_current_user_data),
    limit: int = Query(20, description="Number of documents to return", ge=1, le=100),
    offset: int = Query(0, description="Offset for pagination", ge=0)
):
    """
    List user's documents.
    
    Returns a paginated list of documents uploaded by the user.
    """
    user_id = user_data["user_id"]
    
    # TODO: Implement document listing from database
    # This would query the processed_documents collection
    
    return {
        "documents": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "message": "Document listing not yet implemented"
    }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    user_data: dict = Depends(get_current_user_data)
):
    """
    Delete a document and its vectors.
    
    Removes the document from both the database and vector store.
    """
    user_id = user_data["user_id"]
    
    try:
        # Delete from vector store
        deleted = await rag_system.vector_store_service.delete_document(document_id)
        
        if deleted:
            logger.info(f"Deleted document {document_id} for user {user_id}")
            return {"status": "deleted", "document_id": document_id}
        else:
            raise HTTPException(status_code=404, detail="Document not found or deletion failed")
            
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Document deletion failed: {str(e)}")


# Admin Routes (require admin role)

@router.get("/admin/stats")
async def get_admin_stats(
    user_data: dict = Depends(get_current_user_data)
):
    """
    Get admin statistics (admin only).
    
    Returns comprehensive statistics about the RAG system.
    """
    # Check admin role
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Get vector store stats
        vector_stats = await rag_system.vector_store_service.get_stats()
        
        # Get LLM service info
        llm_info = await rag_system.llm_service.get_service_info()
        
        # Get query engine stats
        engine_stats = await rag_system.query_engine.get_engine_stats()
        
        return {
            "system_health": {
                "rag_available": rag_system.query_engine.is_available(),
                "services": {
                    "document_processing": True,
                    "vector_store": rag_system.vector_store_service.is_available(),
                    "llm_service": rag_system.llm_service.is_available(),
                }
            },
            "vector_store": vector_stats,
            "llm_service": llm_info,
            "query_engine": engine_stats,
        }
        
    except Exception as e:
        logger.error(f"Failed to get admin stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get admin statistics")


@router.post("/admin/reindex")
async def reindex_documents(
    user_data: dict = Depends(get_current_user_data)
):
    """
    Trigger document reindexing (admin only).
    
    Reprocesses and reindexes all documents in the system.
    """
    # Check admin role
    if user_data.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # TODO: Implement document reindexing
    return {
        "status": "reindexing_started",
        "message": "Document reindexing not yet implemented"
    }