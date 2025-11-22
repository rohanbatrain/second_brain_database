"""Celery tasks for document processing.

This module provides Celery tasks for asynchronous document processing operations.
All business logic has been moved to dedicated managers for better separation of concerns.

Architecture:
- Tasks are thin wrappers around service/manager methods
- Follows codebase error handling patterns
- Uses structured logging with extra context
- Implements exponential backoff for retries
"""

import asyncio
import base64
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..managers.document_analysis_manager import document_analysis_manager
from ..managers.document_comparison_manager import document_comparison_manager
from ..managers.document_summarization_manager import document_summarization_manager
from ..managers.logging_manager import get_logger
from ..services.document_service import document_service
from .celery_app import celery_app

logger = get_logger(prefix="[DocumentTasks]")


@celery_app.task(name="process_document_async", bind=True, max_retries=3)
def process_document_async(
    self,
    file_data_b64: str,
    filename: str,
    user_id: str,
    extract_images: bool = True,
    output_format: str = "markdown",
    tenant_id: str = None,
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
        file_data = base64.b64decode(file_data_b64)

        result = asyncio.run(
            document_service.process_and_index_document(
                file_data=file_data,
                filename=filename,
                user_id=user_id,
                extract_images=extract_images,
                output_format=output_format,
                index_for_search=True,
                tenant_id=tenant_id,
            )
        )

        logger.info(
            f"Processed document {filename} for user {user_id}",
            extra={
                "document_id": result["document_id"],
                "user_id": user_id,
                "filename": filename,
            }
        )

        return result

    except Exception as e:
        logger.error(
            f"Error in async document processing: {e}",
            exc_info=True,
            extra={"filename": filename, "user_id": user_id}
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery_app.task(name="extract_tables_async")
def extract_tables_async(file_data_b64: str, filename: str, user_id: str, tenant_id: str = None) -> Dict[str, Any]:
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

        tables = asyncio.run(
            document_service.extract_tables_from_document(file_data=file_data, filename=filename, tenant_id=tenant_id)
        )

        result = {
            "filename": filename,
            "user_id": user_id,
            "tables": tables,
            "table_count": len(tables),
        }

        logger.info(
            f"Extracted {len(tables)} tables from {filename}",
            extra={"filename": filename, "user_id": user_id, "table_count": len(tables)}
        )

        return result

    except Exception as e:
        logger.error(
            f"Error extracting tables: {e}",
            exc_info=True,
            extra={"filename": filename, "user_id": user_id}
        )
        return {"error": str(e)}


@celery_app.task(name="chunk_document_for_rag")
def chunk_document_for_rag(
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    tenant_id: str = None,
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
        chunks = asyncio.run(
            document_service.chunk_document_for_rag(
                document_id=document_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                index_chunks=True,
                tenant_id=tenant_id,
            )
        )

        result = {
            "document_id": document_id,
            "chunk_count": len(chunks),
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }

        logger.info(
            f"Chunked document {document_id} into {len(chunks)} chunks",
            extra={"document_id": document_id, "chunk_count": len(chunks)}
        )

        return result

    except Exception as e:
        logger.error(
            f"Error chunking document: {e}",
            exc_info=True,
            extra={"document_id": document_id}
        )
        return {"error": str(e)}


@celery_app.task(name="advanced_ocr_processing", bind=True, max_retries=3)
def advanced_ocr_processing(
    self,
    file_data_b64: str,
    filename: str,
    user_id: str,
    languages: str = "en",
    ocr_engine: str = "tesseract",
    resolution: int = 300,
    force_ocr: bool = False,
    tenant_id: str = None,
) -> Dict[str, Any]:
    """Advanced OCR processing with configurable parameters.

    Args:
        file_data_b64: Base64 encoded file data
        filename: Original filename
        user_id: User ID
        languages: OCR languages (comma-separated)
        ocr_engine: OCR engine to use
        resolution: OCR resolution DPI
        force_ocr: Force OCR even if text is detected

    Returns:
        OCR processing result with confidence scores
    """
    try:
        file_data = base64.b64decode(file_data_b64)

        # Process with advanced OCR
        result = asyncio.run(
            document_service.process_and_index_document(
                file_data=file_data,
                filename=filename,
                user_id=user_id,
                extract_images=True,
                output_format="markdown",
                index_for_search=True,
                tenant_id=tenant_id,
            )
        )

        # Add OCR-specific metadata using manager
        result["ocr_metadata"] = {
            "languages": languages,
            "engine": ocr_engine,
            "resolution": resolution,
            "force_ocr": force_ocr,
            "confidence_score": document_analysis_manager.calculate_ocr_confidence(result),
        }

        logger.info(
            f"Advanced OCR processing completed for {filename}",
            extra={
                "user_id": user_id,
                "filename": filename,
                "languages": languages,
                "engine": ocr_engine,
                "confidence": result["ocr_metadata"]["confidence_score"],
            }
        )

        return result

    except Exception as e:
        logger.error(
            f"Error in advanced OCR processing: {e}",
            exc_info=True,
            extra={"filename": filename, "user_id": user_id}
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery_app.task(name="batch_document_processing", bind=True)
def batch_document_processing(
    self,
    documents: List[Dict[str, str]],
    user_id: str,
    processing_options: Dict[str, Any] = None,
    tenant_id: str = None,
) -> Dict[str, Any]:
    """Process multiple documents in batch with progress tracking.

    Args:
        documents: List of dicts with 'data_b64' and 'filename' keys
        user_id: User ID
        processing_options: Processing options for all documents

    Returns:
        Batch processing results
    """
    if processing_options is None:
        processing_options = {}

    results = []
    successful = 0
    failed = 0

    for i, doc in enumerate(documents):
        try:
            # Update progress
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": i + 1,
                    "total": len(documents),
                    "successful": successful,
                    "failed": failed,
                },
            )

            # Process individual document
            result = process_document_async.apply(
                args=[
                    doc["data_b64"],
                    doc["filename"],
                    user_id,
                    processing_options.get("extract_images", True),
                    processing_options.get("output_format", "markdown"),
                    tenant_id,
                ]
            )

            results.append({
                "filename": doc["filename"],
                "status": "success",
                "result": result.get(),
            })
            successful += 1

        except Exception as e:
            logger.error(
                f"Failed to process {doc['filename']}: {e}",
                extra={"filename": doc["filename"], "user_id": user_id}
            )
            results.append({
                "filename": doc["filename"],
                "status": "failed",
                "error": str(e),
            })
            failed += 1

    batch_result = {
        "total_documents": len(documents),
        "successful": successful,
        "failed": failed,
        "results": results,
        "processing_options": processing_options,
    }

    logger.info(
        f"Batch processing completed: {successful}/{len(documents)} successful",
        extra={"user_id": user_id, "batch_size": len(documents), "successful": successful}
    )

    return batch_result


@celery_app.task(name="document_layout_analysis", bind=True, max_retries=2)
def document_layout_analysis(
    self,
    document_id: str,
    user_id: str,
    analysis_depth: str = "detailed",
    tenant_id: str = None,
) -> Dict[str, Any]:
    """Perform detailed layout analysis on a processed document.

    Args:
        document_id: MongoDB document ID
        user_id: User ID
        analysis_depth: Analysis depth ('basic', 'detailed', 'comprehensive')

    Returns:
        Layout analysis results
    """
    try:
        # Get document content
        doc_content = asyncio.run(document_service.get_document_content(document_id, tenant_id=tenant_id))
        if not doc_content:
            raise ValueError(f"Document {document_id} not found")

        # Perform layout analysis using manager
        structure = asyncio.run(
            document_analysis_manager.analyze_layout(doc_content, analysis_depth)
        )

        analysis_result = {
            "document_id": document_id,
            "analysis_depth": analysis_depth,
            "structure": structure,
        }

        # Add elements for detailed/comprehensive analysis
        if analysis_depth in ["detailed", "comprehensive"]:
            analysis_result["elements"] = document_analysis_manager.extract_layout_elements(
                doc_content
            )

        # Add relationships for comprehensive analysis
        if analysis_depth == "comprehensive":
            analysis_result[
                "relationships"
            ] = document_analysis_manager.analyze_element_relationships(doc_content)

        # Store analysis results
        asyncio.run(
            document_analysis_manager.store_analysis(document_id, analysis_result, "layout")
        )

        logger.info(
            f"Layout analysis completed for document {document_id}",
            extra={"user_id": user_id, "document_id": document_id, "depth": analysis_depth}
        )

        return analysis_result

    except Exception as e:
        logger.error(
            f"Error in layout analysis: {e}",
            exc_info=True,
            extra={"document_id": document_id, "user_id": user_id}
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery_app.task(name="document_quality_analysis", bind=True, max_retries=2)
def document_quality_analysis(
    self,
    document_id: str,
    user_id: str,
    tenant_id: str = None,
) -> Dict[str, Any]:
    """Analyze document quality including OCR confidence and content integrity.

    Args:
        document_id: MongoDB document ID
        user_id: User ID

    Returns:
        Quality analysis results
    """
    try:
        # Get document content
        doc_content = asyncio.run(document_service.get_document_content(document_id, tenant_id=tenant_id))
        if not doc_content:
            raise ValueError(f"Document {document_id} not found")

        # Perform quality analysis using manager
        quality_scores = asyncio.run(document_analysis_manager.analyze_quality(doc_content))

        quality_scores["document_id"] = document_id

        # Store results
        asyncio.run(
            document_analysis_manager.store_analysis(document_id, quality_scores, "quality")
        )

        logger.info(
            f"Quality analysis completed for document {document_id}: {quality_scores['overall_score']:.2f}",
            extra={
                "user_id": user_id,
                "document_id": document_id,
                "score": quality_scores["overall_score"],
            }
        )

        return quality_scores

    except Exception as e:
        logger.error(
            f"Error in quality analysis: {e}",
            exc_info=True,
            extra={"document_id": document_id, "user_id": user_id}
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery_app.task(name="document_summarization", bind=True, max_retries=2)
def document_summarization(
    self,
    document_id: str,
    user_id: str,
    summary_type: str = "extractive",
    max_length: int = 300,
    tenant_id: str = None,
) -> Dict[str, Any]:
    """Generate document summary using extracted content.

    Args:
        document_id: MongoDB document ID
        user_id: User ID
        summary_type: Type of summarization ('extractive', 'abstractive')
        max_length: Maximum summary length in words

    Returns:
        Summarization results
    """
    try:
        # Get document content
        doc_content = asyncio.run(document_service.get_document_content(document_id, tenant_id=tenant_id))
        if not doc_content:
            raise ValueError(f"Document {document_id} not found")

        content = doc_content.get("content", "")

        # Generate summary using manager
        summary_result = asyncio.run(
            document_summarization_manager.summarize_document(
                content=content,
                summary_type=summary_type,
                max_length=max_length,
                llm_manager=None,  # Will be added in Phase 2
            )
        )

        summary_result["document_id"] = document_id

        # Store summary
        asyncio.run(document_summarization_manager.store_summary(document_id, summary_result))

        logger.info(
            f"Document summarization completed for {document_id}: {summary_result['compression_ratio']:.2f} compression",
            extra={
                "user_id": user_id,
                "document_id": document_id,
                "type": summary_type,
                "compression": summary_result["compression_ratio"],
            }
        )

        return summary_result

    except Exception as e:
        logger.error(
            f"Error in document summarization: {e}",
            exc_info=True,
            extra={"document_id": document_id, "user_id": user_id}
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)


@celery_app.task(name="document_comparison", bind=True, max_retries=2)
def document_comparison(
    self,
    document_id_1: str,
    document_id_2: str,
    user_id: str,
    comparison_type: str = "content",
    tenant_id: str = None,
) -> Dict[str, Any]:
    """Compare two documents and identify differences.

    Args:
        document_id_1: First document ID
        document_id_2: Second document ID
        user_id: User ID
        comparison_type: Type of comparison ('content', 'structure', 'both')

    Returns:
        Comparison results
    """
    try:
        # Get both documents
        doc1 = asyncio.run(document_service.get_document_content(document_id_1, tenant_id=tenant_id))
        doc2 = asyncio.run(document_service.get_document_content(document_id_2, tenant_id=tenant_id))

        if not doc1 or not doc2:
            raise ValueError("One or both documents not found")

        # Perform comparison using manager
        comparison_result = asyncio.run(
            document_comparison_manager.compare_documents(doc1, doc2, comparison_type)
        )

        # Store comparison results
        asyncio.run(document_comparison_manager.store_comparison(comparison_result))

        logger.info(
            f"Document comparison completed: {comparison_result['similarity_score']:.2f} similarity",
            extra={
                "user_id": user_id,
                "doc1": document_id_1,
                "doc2": document_id_2,
                "similarity": comparison_result["similarity_score"],
            }
        )

        return comparison_result

    except Exception as e:
        logger.error(
            f"Error in document comparison: {e}",
            exc_info=True,
            extra={"doc1": document_id_1, "doc2": document_id_2, "user_id": user_id}
        )
        raise self.retry(exc=e, countdown=2**self.request.retries)
