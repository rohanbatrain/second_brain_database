"""Celery tasks for document processing."""
from typing import Dict, Any
import base64

from .celery_app import celery_app
from ..managers.logging_manager import get_logger
from ..integrations.docling_processor import document_processor

logger = get_logger(prefix="[DocumentTasks]")


@celery_app.task(name="process_document_async", bind=True, max_retries=3)
def process_document_async(
    self,
    file_data_b64: str,
    filename: str,
    user_id: str,
    extract_images: bool = True,
    output_format: str = "markdown"
) -> Dict[str, Any]:
    """Process document asynchronously with Docling.
    
    Args:
        file_data_b64: Base64 encoded file data
        filename: Original filename
        user_id: User ID
        extract_images: Extract images
        output_format: Output format
        
    Returns:
        Processing result
    """
    try:
        # Decode file data
        file_data = base64.b64decode(file_data_b64)
        
        # Process document
        import asyncio
        result = asyncio.run(
            document_processor.process_document(
                file_data=file_data,
                filename=filename,
                user_id=user_id,
                extract_images=extract_images,
                output_format=output_format
            )
        )
        
        logger.info(
            f"Processed document {filename} for user {user_id}",
            extra={"document_id": result["document_id"]}
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in async document processing: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@celery_app.task(name="extract_tables_async")
def extract_tables_async(
    file_data_b64: str,
    filename: str,
    user_id: str
) -> Dict[str, Any]:
    """Extract tables from document asynchronously.
    
    Args:
        file_data_b64: Base64 encoded file
        filename: Filename
        user_id: User ID
        
    Returns:
        Extracted tables
    """
    try:
        file_data = base64.b64decode(file_data_b64)
        
        import asyncio
        tables = asyncio.run(
            document_processor.extract_tables(
                file_data=file_data,
                filename=filename
            )
        )
        
        result = {
            "filename": filename,
            "user_id": user_id,
            "tables": tables,
            "table_count": len(tables)
        }
        
        logger.info(f"Extracted {len(tables)} tables from {filename}")
        
        return result
        
    except Exception as e:
        logger.error(f"Error extracting tables: {e}", exc_info=True)
        return {"error": str(e)}


@celery_app.task(name="chunk_document_for_rag")
def chunk_document_for_rag(
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200
) -> Dict[str, Any]:
    """Chunk document for RAG/vector search.
    
    Args:
        document_id: Document ID
        chunk_size: Chunk size
        chunk_overlap: Overlap
        
    Returns:
        Chunking result
    """
    try:
        import asyncio
        chunks = asyncio.run(
            document_processor.chunk_for_rag(
                document_id=document_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
        )
        
        result = {
            "document_id": document_id,
            "chunk_count": len(chunks),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap
        }
        
        logger.info(f"Chunked document {document_id} into {len(chunks)} chunks")
        
        return result
        
    except Exception as e:
        logger.error(f"Error chunking document: {e}", exc_info=True)
        return {"error": str(e)}
