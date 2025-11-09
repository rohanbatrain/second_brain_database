"""File upload routes with Docling integration.

Handles:
- Document uploads (PDF, DOCX, PPTX, etc.)
- Async processing with Celery
- Document search and retrieval
"""

import base64
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..database import db_manager
from ..integrations.mcp.context import MCPUserContext
from ..managers.logging_manager import get_logger
from ..services.document_service import document_service
from ..tasks.document_tasks import chunk_document_for_rag, extract_tables_async, process_document_async
from .auth.services.auth.login import get_current_user

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = get_logger(prefix="[DocumentRoutes]")


class DocumentUploadResponse(BaseModel):
    """Response for document upload."""

    task_id: str
    filename: str
    file_size: int
    status: str
    message: str


class DocumentProcessingStatus(BaseModel):
    """Document processing status."""

    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    extract_images: bool = Form(True),
    output_format: str = Form("markdown"),
    async_processing: bool = Form(True),
    current_user: dict = Depends(get_current_user),
):
    """Upload and process document.

    **Supported Formats**: PDF, DOCX, PPTX, HTML, TXT

    **Processing Options**:
    - `extract_images`: Extract images from document
    - `output_format`: markdown, json, or text
    - `async_processing`: Process in background (recommended for large files)

    **Returns**: Task ID for async processing or immediate result
    """
    try:
        user_id = str(current_user["_id"])

        # Read file data
        file_data = await file.read()
        file_size = len(file_data)

        # Validate file size (max 50MB)
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size: {max_size / 1024 / 1024}MB")

        # Validate file type
        allowed_extensions = {".pdf", ".docx", ".pptx", ".html", ".txt", ".md"}
        file_ext = "." + file.filename.split(".")[-1].lower() if "." in file.filename else ""

        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
            )

        if async_processing:
            # Process asynchronously
            file_data_b64 = base64.b64encode(file_data).decode()

            task = process_document_async.delay(
                file_data_b64=file_data_b64,
                filename=file.filename,
                user_id=user_id,
                extract_images=extract_images,
                output_format=output_format,
            )

            logger.info(
                f"Queued document {file.filename} for processing", extra={"user_id": user_id, "task_id": task.id}
            )

            return DocumentUploadResponse(
                task_id=task.id,
                filename=file.filename,
                file_size=file_size,
                status="processing",
                message="Document queued for processing. Check status with task_id.",
            )
        else:
            # Process synchronously
            result = await document_service.process_and_index_document(
                file_data=file_data,
                filename=file.filename,
                user_id=user_id,
                extract_images=extract_images,
                output_format=output_format,
                index_for_search=True,
            )

            return DocumentUploadResponse(
                task_id="sync",
                filename=file.filename,
                file_size=file_size,
                status="completed",
                message=f"Document processed. ID: {result['document_id']}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{task_id}", response_model=DocumentProcessingStatus)
async def get_processing_status(task_id: str, current_user: dict = Depends(get_current_user)):
    """Get document processing status.

    **Args**:
    - `task_id`: Task ID from upload response

    **Returns**: Processing status and result if completed
    """
    try:
        from celery.result import AsyncResult

        task_result = AsyncResult(task_id)

        status = task_result.status
        result = None
        error = None

        if status == "SUCCESS":
            result = task_result.result
        elif status == "FAILURE":
            error = str(task_result.info)

        return DocumentProcessingStatus(task_id=task_id, status=status.lower(), result=result, error=error)

    except Exception as e:
        logger.error(f"Error getting task status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract-tables")
async def extract_tables(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Extract tables from document.

    **Supported**: PDF, DOCX, PPTX

    **Returns**: Extracted tables with structure
    """
    try:
        user_id = str(current_user["_id"])

        file_data = await file.read()
        file_data_b64 = base64.b64encode(file_data).decode()

        # Process async
        task = extract_tables_async.delay(file_data_b64=file_data_b64, filename=file.filename, user_id=user_id)

        logger.info(f"Queued table extraction for {file.filename}", extra={"user_id": user_id, "task_id": task.id})

        return {"task_id": task.id, "filename": file.filename, "status": "processing"}

    except Exception as e:
        logger.error(f"Error extracting tables: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_documents(limit: int = 50, skip: int = 0, current_user: dict = Depends(get_current_user)):
    """List user's processed documents.

    **Pagination**: Use limit and skip parameters

    **Returns**: List of documents with metadata
    """
    try:
        user_id = str(current_user["_id"])

        # Use document service to get document list
        documents = await document_service.get_document_list(
            user_id=user_id,
            limit=limit,
            offset=skip,
            include_content=False,
        )

        # Get total count
        collection = db_manager.get_collection("processed_documents")
        total = await collection.count_documents({"user_id": user_id})

        return {"documents": documents, "total": total, "limit": limit, "skip": skip}

    except Exception as e:
        logger.error(f"Error listing documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}")
async def get_document(document_id: str, current_user: dict = Depends(get_current_user)):
    """Get processed document by ID.

    **Returns**: Full document content and metadata
    """
    try:
        user_id = str(current_user["_id"])

        # Use document service to get document content
        doc = await document_service.get_document_content(document_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Format response
        return {
            "document_id": doc["document_id"],
            "filename": doc["filename"],
            "content": doc["content"],
            "metadata": doc["metadata"],
            "images": doc.get("images", []),
            "indexed": doc.get("indexed", False),
            "chunk_count": doc.get("chunk_count", 0),
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/chunk")
async def chunk_document(
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    background_tasks: BackgroundTasks = None,
    current_user: dict = Depends(get_current_user),
):
    """Chunk document for RAG/vector search.

    **Args**:
    - `chunk_size`: Characters per chunk (default: 1000)
    - `chunk_overlap`: Overlap between chunks (default: 200)

    **Returns**: Chunking task ID
    """
    try:
        from bson import ObjectId

        user_id = str(current_user["_id"])

        # Verify ownership
        collection = db_manager.get_collection("processed_documents")
        doc = await collection.find_one({"_id": ObjectId(document_id), "user_id": user_id})

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Queue chunking task
        task = chunk_document_for_rag.delay(document_id=document_id, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        logger.info(f"Queued chunking for document {document_id}", extra={"user_id": user_id, "task_id": task.id})

        return {"task_id": task.id, "document_id": document_id, "status": "chunking"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error chunking document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(document_id: str, current_user: dict = Depends(get_current_user)):
    """Delete processed document.

    **Note**: Also deletes associated chunks
    """
    try:
        from bson import ObjectId

        user_id = str(current_user["_id"])

        # Delete document
        collection = db_manager.get_collection("processed_documents")
        result = await collection.delete_one({"_id": ObjectId(document_id), "user_id": user_id})

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete chunks
        chunks_collection = db_manager.get_collection("document_chunks")
        await chunks_collection.delete_many({"document_id": document_id})

        logger.info(f"Deleted document {document_id}", extra={"user_id": user_id})

        return {"message": "Document deleted successfully", "document_id": document_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
