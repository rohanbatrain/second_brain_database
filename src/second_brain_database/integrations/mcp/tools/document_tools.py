"""
Document Processing MCP Tools

MCP tools for comprehensive document processing using Docling, including
upload, analysis, search, chunking, and collaboration features.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ....config import settings
from ....database import db_manager
from ....managers.logging_manager import get_logger
from ..context import create_mcp_audit_trail
from ..exceptions import MCPAuthorizationError, MCPValidationError
from ..modern_server import mcp
from ..security import authenticated_tool, get_mcp_user_context

logger = get_logger(prefix="[MCP_DocumentTools]")

# Import document service
try:
    from ....services.document_service import document_service
except ImportError:
    logger.warning("Document service not available")
    document_service = None

# Pydantic models for MCP tool parameters and responses
class DocumentInfo(BaseModel):
    """Document information response model."""

    document_id: str
    filename: str
    file_type: str
    file_size: int
    status: str
    created_at: datetime
    updated_at: datetime
    user_id: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    processing_stats: Dict[str, Any] = Field(default_factory=dict)


class DocumentUploadRequest(BaseModel):
    """Request model for document upload."""

    filename: str = Field(..., description="Name of the document file")
    content: str = Field(..., description="Base64 encoded file content")
    file_type: Optional[str] = Field(None, description="File type override")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class DocumentSearchRequest(BaseModel):
    """Request model for document search."""

    query: str = Field(..., description="Search query")
    file_types: Optional[List[str]] = Field(None, description="Filter by file types")
    date_from: Optional[str] = Field(None, description="Start date (ISO format)")
    date_to: Optional[str] = Field(None, description="End date (ISO format)")
    limit: int = Field(50, description="Maximum results to return")


class DocumentChunkRequest(BaseModel):
    """Request model for document chunking."""

    document_id: str = Field(..., description="Document ID to chunk")
    chunk_strategy: str = Field("semantic", description="Chunking strategy (semantic, fixed, paragraph)")
    chunk_size: int = Field(1000, description="Target chunk size in characters")
    overlap: int = Field(200, description="Overlap between chunks")


class DocumentAnalysisRequest(BaseModel):
    """Request model for document analysis."""

    document_id: str = Field(..., description="Document ID to analyze")
    analysis_types: List[str] = Field(..., description="Types of analysis to perform")


# Core Document Management Tools

@authenticated_tool(
    name="upload_document",
    description="Upload and process a document using Docling",
    permissions=["documents:upload"],
    rate_limit_action="document_upload",
)
async def upload_document(
    filename: str,
    content: str,
    file_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Upload and process a document using Docling for comprehensive document understanding.

    Args:
        filename: Name of the document file
        content: Base64 encoded file content
        file_type: Optional file type override
        metadata: Additional metadata for the document

    Returns:
        Dictionary containing upload confirmation and processing status

    Raises:
        MCPValidationError: If upload or processing fails
    """
    user_context = get_mcp_user_context()

    if not document_service:
        raise MCPValidationError("Document service is not available")

    try:
        # Validate file size
        import base64
        file_size = len(base64.b64decode(content))
        max_size = getattr(settings, 'DOCLING_MAX_FILE_SIZE', 50 * 1024 * 1024)  # 50MB default

        if file_size > max_size:
            raise MCPValidationError(f"File size {file_size} exceeds maximum allowed size {max_size}")

        # Validate file type
        supported_types = getattr(settings, 'DOCLING_SUPPORTED_FORMATS', 'pdf,docx,pptx,html,txt,xlsx').split(',')
        if file_type and file_type.lower() not in supported_types:
            raise MCPValidationError(f"Unsupported file type: {file_type}. Supported: {supported_types}")

        # Process and index document with Docling and vector search
        result = await document_service.process_and_index_document(
            file_data=base64.b64decode(content),
            filename=filename,
            user_id=user_context.user_id,
            index_for_search=True,  # Enable vector indexing
        )

        document_id = result.get("document_id")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="upload_document",
            user_context=user_context,
            resource_type="document",
            resource_id=document_id,
            changes={"filename": filename, "file_size": file_size, "file_type": file_type},
            metadata={"processing_status": "completed", "vector_chunks": result.get("vector_chunks", 0)},
        )

        logger.info("Uploaded and processed document %s for user %s", document_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to upload document for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to upload document: {str(e)}")


@authenticated_tool(
    name="get_document",
    description="Retrieve document information and content",
    permissions=["documents:read"],
    rate_limit_action="document_read",
)
async def get_document(document_id: str) -> Dict[str, Any]:
    """
    Retrieve comprehensive document information including metadata and processed content.

    Args:
        document_id: The ID of the document to retrieve

    Returns:
        Dictionary containing document information, metadata, and processed content

    Raises:
        MCPAuthorizationError: If user doesn't have access to the document
        MCPValidationError: If document retrieval fails
    """
    user_context = get_mcp_user_context()

    try:
        # Get document from database
        documents_collection = mongodb_manager.get_collection("documents")
        document = await documents_collection.find_one({
            "document_id": document_id,
            "user_id": user_context.user_id
        })

        if not document:
            raise MCPValidationError("Document not found or access denied")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_document",
            user_context=user_context,
            resource_type="document",
            resource_id=document_id,
            metadata={"filename": document.get("filename")},
        )

        # Format response
        result = {
            "document_id": document.get("document_id"),
            "filename": document.get("filename"),
            "file_type": document.get("file_type"),
            "file_size": document.get("file_size"),
            "status": document.get("status"),
            "created_at": document.get("created_at"),
            "updated_at": document.get("updated_at"),
            "user_id": document.get("user_id"),
            "metadata": document.get("metadata", {}),
            "processing_stats": document.get("processing_stats", {}),
            "content": document.get("content", {}),
            "chunks": document.get("chunks", []),
        }

        logger.info("Retrieved document %s for user %s", document_id, user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to get document %s: %s", document_id, e)
        raise MCPValidationError(f"Failed to retrieve document: {str(e)}")


@authenticated_tool(
    name="list_user_documents",
    description="List all documents for the current user",
    permissions=["documents:read"],
    rate_limit_action="document_read",
)
async def list_user_documents(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    file_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List all documents for the current user with optional filtering.

    Args:
        limit: Maximum number of documents to return (default 50, max 100)
        offset: Number of documents to skip (for pagination)
        status: Filter by processing status
        file_type: Filter by file type

    Returns:
        List of documents with basic information

    Raises:
        MCPValidationError: If query parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if limit <= 0 or limit > 100:
        raise MCPValidationError("Limit must be between 1 and 100")
    if offset < 0:
        raise MCPValidationError("Offset must be non-negative")

    try:
        # Build query
        query = {"user_id": user_context.user_id}
        if status:
            query["status"] = status
        if file_type:
            query["file_type"] = file_type

        # Get documents from database
        documents_collection = mongodb_manager.get_collection("documents")
        cursor = documents_collection.find(query).sort("created_at", -1).skip(offset).limit(limit)
        documents = await cursor.to_list(length=None)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="list_user_documents",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"document_count": len(documents), "limit": limit, "offset": offset},
        )

        # Format response
        result = []
        for doc in documents:
            result.append({
                "document_id": doc.get("document_id"),
                "filename": doc.get("filename"),
                "file_type": doc.get("file_type"),
                "file_size": doc.get("file_size"),
                "status": doc.get("status"),
                "created_at": doc.get("created_at"),
                "updated_at": doc.get("updated_at"),
                "metadata": doc.get("metadata", {}),
            })

        logger.info("Listed %d documents for user %s", len(result), user_context.user_id)
        return result

    except Exception as e:
        logger.error("Failed to list documents for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to list documents: {str(e)}")


@authenticated_tool(
    name="delete_document",
    description="Delete a document and all associated data",
    permissions=["documents:delete"],
    rate_limit_action="document_delete",
)
async def delete_document(document_id: str, confirm: bool = False) -> Dict[str, Any]:
    """
    Delete a document and all associated processed content, chunks, and metadata.

    Args:
        document_id: The ID of the document to delete
        confirm: Confirmation flag to prevent accidental deletion

    Returns:
        Dictionary containing deletion confirmation

    Raises:
        MCPAuthorizationError: If user doesn't own the document
        MCPValidationError: If deletion fails or confirmation not provided
    """
    user_context = get_mcp_user_context()

    if not confirm:
        raise MCPValidationError("Document deletion requires explicit confirmation (confirm=true)")

    try:
        # Get document first to validate ownership
        documents_collection = mongodb_manager.get_collection("documents")
        document = await documents_collection.find_one({
            "document_id": document_id,
            "user_id": user_context.user_id
        })

        if not document:
            raise MCPValidationError("Document not found or access denied")

        # Delete document
        await documents_collection.delete_one({"document_id": document_id})

        # Create audit trail
        await create_mcp_audit_trail(
            operation="delete_document",
            user_context=user_context,
            resource_type="document",
            resource_id=document_id,
            changes={"deleted": True},
            metadata={"filename": document.get("filename")},
        )

        logger.info("Deleted document %s for user %s", document_id, user_context.user_id)
        return {
            "document_id": document_id,
            "deleted": True,
            "deleted_at": datetime.now(),
        }

    except Exception as e:
        logger.error("Failed to delete document %s: %s", document_id, e)
        raise MCPValidationError(f"Failed to delete document: {str(e)}")


# Document Processing and Analysis Tools

@authenticated_tool(
    name="extract_document_tables",
    description="Extract tables from a processed document",
    permissions=["documents:read"],
    rate_limit_action="document_process",
)
async def extract_document_tables(document_id: str) -> Dict[str, Any]:
    """
    Extract and return all tables found in a processed document.

    Args:
        document_id: The ID of the document to extract tables from

    Returns:
        Dictionary containing extracted tables with metadata

    Raises:
        MCPAuthorizationError: If user doesn't have access to the document
        MCPValidationError: If table extraction fails
    """
    user_context = get_mcp_user_context()

    if not document_service:
        raise MCPValidationError("Document service is not available")

    try:
        # Extract tables using the document service
        tables = await document_service.extract_tables_from_document(
            document_id=document_id
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="extract_document_tables",
            user_context=user_context,
            resource_type="document",
            resource_id=document_id,
            metadata={"table_count": len(tables)},
        )

        logger.info("Extracted %d tables from document %s", len(tables), document_id)
        return {"tables": tables}

    except Exception as e:
        logger.error("Failed to extract tables from document %s: %s", document_id, e)
        raise MCPValidationError(f"Failed to extract tables: {str(e)}")


@authenticated_tool(
    name="chunk_document",
    description="Create chunks from a document for RAG applications",
    permissions=["documents:read"],
    rate_limit_action="document_process",
)
async def chunk_document(
    document_id: str,
    chunk_strategy: str = "semantic",
    chunk_size: int = 1000,
    overlap: int = 200,
) -> Dict[str, Any]:
    """
    Create intelligent chunks from a document for retrieval-augmented generation (RAG).

    Args:
        document_id: The ID of the document to chunk
        chunk_strategy: Chunking strategy (semantic, fixed, paragraph)
        chunk_size: Target chunk size in characters
        overlap: Overlap between chunks in characters

    Returns:
        Dictionary containing document chunks with metadata

    Raises:
        MCPAuthorizationError: If user doesn't have access to the document
        MCPValidationError: If chunking fails
    """
    user_context = get_mcp_user_context()

    if not document_service:
        raise MCPValidationError("Document service is not available")

    # Validate parameters
    if chunk_strategy not in ["semantic", "fixed", "paragraph"]:
        raise MCPValidationError("Invalid chunk strategy. Must be: semantic, fixed, or paragraph")

    if chunk_size <= 0 or chunk_size > 10000:
        raise MCPValidationError("Chunk size must be between 1 and 10000 characters")

    if overlap < 0 or overlap >= chunk_size:
        raise MCPValidationError("Overlap must be non-negative and less than chunk size")

    try:
        # Get document to validate access
        documents_collection = mongodb_manager.get_collection("documents")
        document = await documents_collection.find_one({
            "document_id": document_id,
            "user_id": user_context.user_id
        })

        if not document:
            raise MCPValidationError("Document not found or access denied")

        # Create chunks using document service
        chunks = await document_service.chunk_document_for_rag(
            document_id=document_id,
            chunk_size=chunk_size,
            index_chunks=True,  # Index for vector search
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="chunk_document",
            user_context=user_context,
            resource_type="document",
            resource_id=document_id,
            metadata={
                "chunk_strategy": chunk_strategy,
                "chunk_count": len(result.get("chunks", [])),
                "chunk_size": chunk_size,
            },
        )

        logger.info("Created %d chunks for document %s using %s strategy",
                   len(result.get("chunks", [])), document_id, chunk_strategy)
        return result

    except Exception as e:
        logger.error("Failed to chunk document %s: %s", document_id, e)
        raise MCPValidationError(f"Failed to chunk document: {str(e)}")


@authenticated_tool(
    name="analyze_document",
    description="Perform advanced analysis on a document",
    permissions=["documents:read"],
    rate_limit_action="document_process",
)
async def analyze_document(
    document_id: str,
    analysis_types: List[str],
) -> Dict[str, Any]:
    """
    Perform advanced analysis on a document including layout analysis, content structure, and metadata extraction.

    Args:
        document_id: The ID of the document to analyze
        analysis_types: List of analysis types to perform

    Returns:
        Dictionary containing analysis results

    Raises:
        MCPAuthorizationError: If user doesn't have access to the document
        MCPValidationError: If analysis fails
    """
    user_context = get_mcp_user_context()

    if not docling_processor:
        raise MCPValidationError("Docling processor is not available")

    # Validate analysis types
    valid_types = ["layout", "structure", "metadata", "content", "quality"]
    invalid_types = [t for t in analysis_types if t not in valid_types]
    if invalid_types:
        raise MCPValidationError(f"Invalid analysis types: {invalid_types}. Valid: {valid_types}")

    try:
        # Get document to validate access
        documents_collection = mongodb_manager.get_collection("documents")
        document = await documents_collection.find_one({
            "document_id": document_id,
            "user_id": user_context.user_id
        })

        if not document:
            raise MCPValidationError("Document not found or access denied")

        # Perform analysis
        result = await docling_processor.analyze_document(document_id, analysis_types)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="analyze_document",
            user_context=user_context,
            resource_type="document",
            resource_id=document_id,
            metadata={"analysis_types": analysis_types},
        )

        logger.info("Analyzed document %s with types: %s", document_id, analysis_types)
        return result

    except Exception as e:
        logger.error("Failed to analyze document %s: %s", document_id, e)
        raise MCPValidationError(f"Failed to analyze document: {str(e)}")


# Document Search and Discovery Tools

@authenticated_tool(
    name="search_documents",
    description="Search through document content and metadata",
    permissions=["documents:read"],
    rate_limit_action="document_search",
)
async def search_documents(
    query: str,
    file_types: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Search through document content, metadata, and extracted text using semantic search.

    Args:
        query: Search query string
        file_types: Optional list of file types to filter by
        date_from: Optional start date filter (ISO format)
        date_to: Optional end date filter (ISO format)
        limit: Maximum number of results to return

    Returns:
        List of matching documents with relevance scores

    Raises:
        MCPValidationError: If search parameters are invalid
    """
    user_context = get_mcp_user_context()

    # Validate parameters
    if not query or len(query.strip()) < 2:
        raise MCPValidationError("Search query must be at least 2 characters long")

    if limit <= 0 or limit > 100:
        raise MCPValidationError("Limit must be between 1 and 100")

    try:
        # Parse dates if provided
        date_from_parsed = None
        date_to_parsed = None

        if date_from:
            try:
                date_from_parsed = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            except ValueError:
                raise MCPValidationError("Invalid date_from format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")

        if date_to:
            try:
                date_to_parsed = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            except ValueError:
                raise MCPValidationError("Invalid date_to format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")

        # Perform search
        documents_collection = mongodb_manager.get_collection("documents")

        # Build search pipeline
        pipeline = [
            {"$match": {"user_id": user_context.user_id}},
        ]

        # Add file type filter
        if file_types:
            pipeline.append({"$match": {"file_type": {"$in": file_types}}})

        # Add date filters
        if date_from_parsed or date_to_parsed:
            date_filter = {}
            if date_from_parsed:
                date_filter["$gte"] = date_from_parsed
            if date_to_parsed:
                date_filter["$lte"] = date_to_parsed
            pipeline.append({"$match": {"created_at": date_filter}})

        # Add text search
        pipeline.extend([
            {
                "$addFields": {
                    "search_score": {
                        "$sum": [
                            {"$cond": [{"$regexMatch": {"input": "$filename", "regex": query, "options": "i"}}, 10, 0]},
                            {"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$content.text", ""]}, "regex": query, "options": "i"}}, 5, 0]},
                            {"$cond": [{"$regexMatch": {"input": {"$ifNull": ["$metadata.description", ""]}, "regex": query, "options": "i"}}, 3, 0]},
                        ]
                    }
                }
            },
            {"$match": {"search_score": {"$gt": 0}}},
            {"$sort": {"search_score": -1, "created_at": -1}},
            {"$limit": limit},
        ])

        # Execute search
        results = await documents_collection.aggregate(pipeline).to_list(length=None)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="search_documents",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"query": query, "result_count": len(results), "limit": limit},
        )

        # Format results
        formatted_results = []
        for doc in results:
            formatted_results.append({
                "document_id": doc.get("document_id"),
                "filename": doc.get("filename"),
                "file_type": doc.get("file_type"),
                "created_at": doc.get("created_at"),
                "search_score": doc.get("search_score", 0),
                "metadata": doc.get("metadata", {}),
                "snippet": doc.get("content", {}).get("text", "")[:200] + "..." if len(doc.get("content", {}).get("text", "")) > 200 else doc.get("content", {}).get("text", ""),
            })

        logger.info("Found %d documents matching query '%s' for user %s", len(formatted_results), query, user_context.user_id)
        return formatted_results

    except Exception as e:
        logger.error("Failed to search documents for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to search documents: {str(e)}")


@authenticated_tool(
    name="semantic_search_documents",
    description="Perform semantic vector search through document content",
    permissions=["documents:read"],
    rate_limit_action="document_search",
)
async def semantic_search_documents(
    query: str,
    limit: int = 20,
    score_threshold: float = 0.0,
    include_metadata: bool = True,
) -> List[Dict[str, Any]]:
    """
    Perform semantic vector search through document chunks using Qdrant.

    Args:
        query: Semantic search query
        limit: Maximum number of results to return
        score_threshold: Minimum similarity score (0.0-1.0)
        include_metadata: Whether to include document metadata

    Returns:
        List of semantically similar document chunks with scores

    Raises:
        MCPValidationError: If search fails or vector search unavailable
    """
    user_context = get_mcp_user_context()

    if not document_service:
        raise MCPValidationError("Document service is not available")

    # Validate parameters
    if not query or len(query.strip()) < 2:
        raise MCPValidationError("Search query must be at least 2 characters long")

    if limit <= 0 or limit > 50:
        raise MCPValidationError("Limit must be between 1 and 50")

    if not 0.0 <= score_threshold <= 1.0:
        raise MCPValidationError("Score threshold must be between 0.0 and 1.0")

    try:
        # Perform semantic search using document service
        results = await document_service.search_documents(
            query=query,
            user_id=user_context.user_id,
            limit=limit,
            score_threshold=score_threshold,
            search_type="semantic",
            include_metadata=include_metadata,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="semantic_search_documents",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"query": query, "result_count": len(results), "limit": limit},
        )

        logger.info("Performed semantic search for query '%s', found %d results for user %s",
                   query, len(results), user_context.user_id)
        return results

    except Exception as e:
        logger.error("Failed to perform semantic search for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to perform semantic search: {str(e)}")


@authenticated_tool(
    name="hybrid_search_documents",
    description="Perform hybrid search combining semantic and keyword search",
    permissions=["documents:read"],
    rate_limit_action="document_search",
)
async def hybrid_search_documents(
    query: str,
    keyword_query: Optional[str] = None,
    limit: int = 20,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> List[Dict[str, Any]]:
    """
    Perform hybrid search combining semantic vector search with keyword search.

    Args:
        query: Semantic search query
        keyword_query: Optional separate keyword query (uses semantic query if None)
        limit: Maximum number of results to return
        semantic_weight: Weight for semantic search results (0.0-1.0)
        keyword_weight: Weight for keyword search results (0.0-1.0)

    Returns:
        List of hybrid search results with combined scores

    Raises:
        MCPValidationError: If search fails or hybrid search unavailable
    """
    user_context = get_mcp_user_context()

    if not document_service:
        raise MCPValidationError("Document service is not available")

    # Validate parameters
    if not query or len(query.strip()) < 2:
        raise MCPValidationError("Search query must be at least 2 characters long")

    if limit <= 0 or limit > 50:
        raise MCPValidationError("Limit must be between 1 and 50")

    if not (0.0 <= semantic_weight <= 1.0) or not (0.0 <= keyword_weight <= 1.0):
        raise MCPValidationError("Weights must be between 0.0 and 1.0")

    if abs(semantic_weight + keyword_weight - 1.0) > 0.01:
        raise MCPValidationError("Semantic and keyword weights must sum to 1.0")

    try:
        # Perform hybrid search using document service
        results = await document_service.search_documents(
            query=query,
            user_id=user_context.user_id,
            limit=limit,
            search_type="hybrid",
            include_metadata=True,
        )

        # Create audit trail
        await create_mcp_audit_trail(
            operation="hybrid_search_documents",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={
                "query": query,
                "keyword_query": keyword_query,
                "result_count": len(results),
                "limit": limit,
                "semantic_weight": semantic_weight,
                "keyword_weight": keyword_weight,
            },
        )

        logger.info("Performed hybrid search for query '%s', found %d results for user %s",
                   query, len(results), user_context.user_id)
        return results

    except Exception as e:
        logger.error("Failed to perform hybrid search for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to perform hybrid search: {str(e)}")


@authenticated_tool(
    name="get_document_processing_status",
    description="Get the processing status of a document",
    permissions=["documents:read"],
    rate_limit_action="document_read",
)
async def get_document_processing_status(document_id: str) -> Dict[str, Any]:
    """
    Get detailed processing status and progress information for a document.

    Args:
        document_id: The ID of the document to check

    Returns:
        Dictionary containing processing status and statistics

    Raises:
        MCPAuthorizationError: If user doesn't have access to the document
        MCPValidationError: If status retrieval fails
    """
    user_context = get_mcp_user_context()

    try:
        # Get document status
        documents_collection = mongodb_manager.get_collection("documents")
        document = await documents_collection.find_one({
            "document_id": document_id,
            "user_id": user_context.user_id
        })

        if not document:
            raise MCPValidationError("Document not found or access denied")

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_document_processing_status",
            user_context=user_context,
            resource_type="document",
            resource_id=document_id,
            metadata={"status": document.get("status")},
        )

        # Format status response
        result = {
            "document_id": document_id,
            "status": document.get("status"),
            "filename": document.get("filename"),
            "file_type": document.get("file_type"),
            "created_at": document.get("created_at"),
            "updated_at": document.get("updated_at"),
            "processing_stats": document.get("processing_stats", {}),
            "error_message": document.get("error_message"),
            "progress": document.get("progress", {}),
        }

        logger.info("Retrieved processing status for document %s: %s", document_id, document.get("status"))
        return result

    except Exception as e:
        logger.error("Failed to get processing status for document %s: %s", document_id, e)
        raise MCPValidationError(f"Failed to get processing status: {str(e)}")


# Document Collaboration and Sharing Tools

@authenticated_tool(
    name="share_document",
    description="Share a document with another user",
    permissions=["documents:share"],
    rate_limit_action="document_share",
)
async def share_document(
    document_id: str,
    target_user_id: str,
    permissions: str = "read",
) -> Dict[str, Any]:
    """
    Share a document with another user with specified permissions.

    Args:
        document_id: The ID of the document to share
        target_user_id: The ID of the user to share with
        permissions: Permission level (read, write, admin)

    Returns:
        Dictionary containing sharing confirmation

    Raises:
        MCPAuthorizationError: If user doesn't own the document
        MCPValidationError: If sharing fails
    """
    user_context = get_mcp_user_context()

    # Validate permissions
    if permissions not in ["read", "write", "admin"]:
        raise MCPValidationError("Permissions must be 'read', 'write', or 'admin'")

    try:
        # Get document to validate ownership
        documents_collection = mongodb_manager.get_collection("documents")
        document = await documents_collection.find_one({
            "document_id": document_id,
            "user_id": user_context.user_id
        })

        if not document:
            raise MCPValidationError("Document not found or access denied")

        # Create sharing record
        shares_collection = mongodb_manager.get_collection("document_shares")
        share_record = {
            "share_id": f"share_{document_id}_{target_user_id}_{int(datetime.now().timestamp())}",
            "document_id": document_id,
            "owner_id": user_context.user_id,
            "target_user_id": target_user_id,
            "permissions": permissions,
            "shared_at": datetime.now(),
            "shared_by": user_context.user_id,
        }

        await shares_collection.insert_one(share_record)

        # Create audit trail
        await create_mcp_audit_trail(
            operation="share_document",
            user_context=user_context,
            resource_type="document",
            resource_id=document_id,
            changes={"shared_with": target_user_id, "permissions": permissions},
            metadata={"share_id": share_record["share_id"]},
        )

        logger.info("Shared document %s with user %s (permissions: %s)", document_id, target_user_id, permissions)
        return {
            "share_id": share_record["share_id"],
            "document_id": document_id,
            "shared_with": target_user_id,
            "permissions": permissions,
            "shared_at": share_record["shared_at"],
        }

    except Exception as e:
        logger.error("Failed to share document %s: %s", document_id, e)
        raise MCPValidationError(f"Failed to share document: {str(e)}")


@authenticated_tool(
    name="get_shared_documents",
    description="Get documents shared with the current user",
    permissions=["documents:read"],
    rate_limit_action="document_read",
)
async def get_shared_documents(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get all documents that have been shared with the current user.

    Args:
        limit: Maximum number of shared documents to return

    Returns:
        List of shared documents with permissions

    Raises:
        MCPValidationError: If query fails
    """
    user_context = get_mcp_user_context()

    if limit <= 0 or limit > 100:
        raise MCPValidationError("Limit must be between 1 and 100")

    try:
        # Get shared documents
        shares_collection = mongodb_manager.get_collection("document_shares")
        documents_collection = mongodb_manager.get_collection("documents")

        # Find shares for current user
        shares = await shares_collection.find(
            {"target_user_id": user_context.user_id}
        ).sort("shared_at", -1).limit(limit).to_list(length=None)

        # Get document details for each share
        shared_docs = []
        for share in shares:
            document = await documents_collection.find_one(
                {"document_id": share["document_id"]}
            )
            if document:
                shared_docs.append({
                    "share_id": share["share_id"],
                    "document_id": share["document_id"],
                    "filename": document.get("filename"),
                    "file_type": document.get("file_type"),
                    "owner_id": share["owner_id"],
                    "permissions": share["permissions"],
                    "shared_at": share["shared_at"],
                    "metadata": document.get("metadata", {}),
                })

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_shared_documents",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"shared_count": len(shared_docs)},
        )

        logger.info("Retrieved %d shared documents for user %s", len(shared_docs), user_context.user_id)
        return shared_docs

    except Exception as e:
        logger.error("Failed to get shared documents for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to get shared documents: {str(e)}")


# Document Analytics and Monitoring Tools

@authenticated_tool(
    name="get_document_analytics",
    description="Get usage analytics and statistics for documents",
    permissions=["documents:read"],
    rate_limit_action="document_read",
)
async def get_document_analytics(
    document_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get comprehensive analytics and usage statistics for documents.

    Args:
        document_id: Optional specific document ID to analyze
        date_from: Optional start date for analytics (ISO format)
        date_to: Optional end date for analytics (ISO format)

    Returns:
        Dictionary containing document analytics and statistics

    Raises:
        MCPValidationError: If analytics retrieval fails
    """
    user_context = get_mcp_user_context()

    try:
        # Parse dates if provided
        date_from_parsed = None
        date_to_parsed = None

        if date_from:
            try:
                date_from_parsed = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            except ValueError:
                raise MCPValidationError("Invalid date_from format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")

        if date_to:
            try:
                date_to_parsed = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            except ValueError:
                raise MCPValidationError("Invalid date_to format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")

        # Build analytics query
        documents_collection = mongodb_manager.get_collection("documents")

        match_conditions = {"user_id": user_context.user_id}

        if document_id:
            match_conditions["document_id"] = document_id

        if date_from_parsed or date_to_parsed:
            date_filter = {}
            if date_from_parsed:
                date_filter["$gte"] = date_from_parsed
            if date_to_parsed:
                date_filter["$lte"] = date_to_parsed
            match_conditions["created_at"] = date_filter

        # Aggregate analytics
        pipeline = [
            {"$match": match_conditions},
            {
                "$group": {
                    "_id": None,
                    "total_documents": {"$sum": 1},
                    "total_size": {"$sum": "$file_size"},
                    "file_types": {"$addToSet": "$file_type"},
                    "processing_statuses": {"$addToSet": "$status"},
                    "avg_processing_time": {"$avg": "$processing_stats.processing_time_seconds"},
                    "documents_by_type": {
                        "$push": {
                            "file_type": "$file_type",
                            "file_size": "$file_size",
                            "status": "$status",
                            "created_at": "$created_at",
                        }
                    },
                }
            }
        ]

        result = await documents_collection.aggregate(pipeline).to_list(length=1)

        if not result:
            analytics = {
                "total_documents": 0,
                "total_size_bytes": 0,
                "file_types": [],
                "processing_statuses": [],
                "avg_processing_time_seconds": 0,
                "documents_by_type": {},
            }
        else:
            analytics = result[0]
            analytics["total_size_bytes"] = analytics.pop("total_size", 0)
            analytics.pop("_id", None)

            # Group documents by type
            type_stats = {}
            for doc in analytics.get("documents_by_type", []):
                ftype = doc["file_type"]
                if ftype not in type_stats:
                    type_stats[ftype] = {"count": 0, "total_size": 0}
                type_stats[ftype]["count"] += 1
                type_stats[ftype]["total_size"] += doc["file_size"]

            analytics["documents_by_type"] = type_stats

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_document_analytics",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"document_id": document_id, "total_documents": analytics.get("total_documents", 0)},
        )

        logger.info("Retrieved document analytics for user %s", user_context.user_id)
        return analytics

    except Exception as e:
        logger.error("Failed to get document analytics for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to get document analytics: {str(e)}")


@authenticated_tool(
    name="get_document_health",
    description="Get system health and performance metrics for document processing",
    permissions=["documents:read"],
    rate_limit_action="document_read",
)
async def get_document_health() -> Dict[str, Any]:
    """
    Get comprehensive health and performance metrics for the document processing system.

    Returns:
        Dictionary containing system health and performance metrics

    Raises:
        MCPValidationError: If health check fails
    """
    user_context = get_mcp_user_context()

    try:
        # Get system health metrics
        documents_collection = mongodb_manager.get_collection("documents")

        # Aggregate health metrics
        pipeline = [
            {"$match": {"user_id": user_context.user_id}},
            {
                "$group": {
                    "_id": None,
                    "total_documents": {"$sum": 1},
                    "processed_documents": {"$sum": {"$cond": [{"$eq": ["$status", "completed"]}, 1, 0]}},
                    "failed_documents": {"$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}},
                    "processing_documents": {"$sum": {"$cond": [{"$eq": ["$status", "processing"]}, 1, 0]}},
                    "avg_file_size": {"$avg": "$file_size"},
                    "max_file_size": {"$max": "$file_size"},
                    "total_processing_time": {"$sum": "$processing_stats.processing_time_seconds"},
                }
            }
        ]

        result = await documents_collection.aggregate(pipeline).to_list(length=1)

        if not result:
            health = {
                "status": "healthy",
                "total_documents": 0,
                "processed_documents": 0,
                "failed_documents": 0,
                "processing_documents": 0,
                "success_rate": 1.0,
                "avg_file_size_bytes": 0,
                "max_file_size_bytes": 0,
                "avg_processing_time_seconds": 0,
            }
        else:
            stats = result[0]
            total = stats.get("total_documents", 0)
            processed = stats.get("processed_documents", 0)
            failed = stats.get("failed_documents", 0)

            health = {
                "status": "healthy" if failed == 0 else ("warning" if failed / total < 0.1 else "critical"),
                "total_documents": total,
                "processed_documents": processed,
                "failed_documents": failed,
                "processing_documents": stats.get("processing_documents", 0),
                "success_rate": processed / total if total > 0 else 1.0,
                "avg_file_size_bytes": stats.get("avg_file_size", 0),
                "max_file_size_bytes": stats.get("max_file_size", 0),
                "avg_processing_time_seconds": stats.get("total_processing_time", 0) / processed if processed > 0 else 0,
            }

        # Add system capabilities
        health["capabilities"] = {
            "docling_available": document_service is not None,
            "supported_formats": getattr(settings, 'DOCLING_SUPPORTED_FORMATS', []),
            "max_file_size": getattr(settings, 'DOCLING_MAX_FILE_SIZE', 50 * 1024 * 1024),
            "ocr_enabled": getattr(settings, 'DOCLING_OCR_ENABLED', True),
        }

        # Create audit trail
        await create_mcp_audit_trail(
            operation="get_document_health",
            user_context=user_context,
            resource_type="user",
            resource_id=user_context.user_id,
            metadata={"status": health.get("status"), "total_documents": health.get("total_documents", 0)},
        )

        logger.info("Retrieved document health metrics for user %s", user_context.user_id)
        return health

    except Exception as e:
        logger.error("Failed to get document health for user %s: %s", user_context.user_id, e)
        raise MCPValidationError(f"Failed to get document health: {str(e)}")


@mcp.tool()
async def advanced_ocr_processing(
    file_data: str,
    filename: str,
    languages: str = "en",
    ocr_engine: str = "tesseract",
    resolution: int = 300,
    force_ocr: bool = False,
) -> Dict[str, Any]:
    """Process document with advanced OCR settings.

    Args:
        file_data: Base64 encoded file data
        filename: Original filename
        languages: OCR languages (comma-separated)
        ocr_engine: OCR engine to use
        resolution: OCR resolution DPI
        force_ocr: Force OCR even if text is detected

    Returns:
        OCR processing result with confidence scores
    """
    try:
        from ..tasks.document_tasks import advanced_ocr_processing as ocr_task

        # Get current user from context
        user_id = get_current_user_id()

        # Start async task
        task = ocr_task.delay(
            file_data, filename, user_id, languages, ocr_engine, resolution, force_ocr
        )

        result = {
            "task_id": task.id,
            "status": "processing",
            "message": f"Advanced OCR processing started for {filename}",
            "languages": languages,
            "engine": ocr_engine,
        }

        logger.info(f"Advanced OCR task started: {task.id}", extra={"user_id": user_id})
        return result

    except Exception as e:
        logger.error(f"Error starting advanced OCR task: {e}")
        return {"error": str(e)}


@mcp.tool()
async def batch_document_processing(
    documents: List[Dict[str, str]],
    processing_options: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """Process multiple documents in batch.

    Args:
        documents: List of dicts with 'data' (base64) and 'filename' keys
        processing_options: Processing options for all documents

    Returns:
        Batch processing task information
    """
    try:
        from ..tasks.document_tasks import batch_document_processing as batch_task

        user_id = get_current_user_id()

        if processing_options is None:
            processing_options = {}

        # Start batch processing task
        task = batch_task.delay(documents, user_id, processing_options)

        result = {
            "task_id": task.id,
            "status": "processing",
            "message": f"Batch processing started for {len(documents)} documents",
            "document_count": len(documents),
            "processing_options": processing_options,
        }

        logger.info(f"Batch processing task started: {task.id}", extra={"user_id": user_id})
        return result

    except Exception as e:
        logger.error(f"Error starting batch processing task: {e}")
        return {"error": str(e)}


@mcp.tool()
async def analyze_document_layout(
    document_id: str,
    analysis_depth: str = "detailed",
) -> Dict[str, Any]:
    """Perform detailed layout analysis on a document.

    Args:
        document_id: MongoDB document ID
        analysis_depth: Analysis depth ('basic', 'detailed', 'comprehensive')

    Returns:
        Layout analysis task information
    """
    try:
        from ..tasks.document_tasks import document_layout_analysis as layout_task

        user_id = get_current_user_id()

        # Start layout analysis task
        task = layout_task.delay(document_id, user_id, analysis_depth)

        result = {
            "task_id": task.id,
            "status": "processing",
            "message": f"Layout analysis started for document {document_id}",
            "analysis_depth": analysis_depth,
        }

        logger.info(f"Layout analysis task started: {task.id}", extra={"user_id": user_id})
        return result

    except Exception as e:
        logger.error(f"Error starting layout analysis task: {e}")
        return {"error": str(e)}


@mcp.tool()
async def analyze_document_quality(document_id: str) -> Dict[str, Any]:
    """Analyze document quality including OCR confidence and content integrity.

    Args:
        document_id: MongoDB document ID

    Returns:
        Quality analysis task information
    """
    try:
        from ..tasks.document_tasks import document_quality_analysis as quality_task

        user_id = get_current_user_id()

        # Start quality analysis task
        task = quality_task.delay(document_id, user_id)

        result = {
            "task_id": task.id,
            "status": "processing",
            "message": f"Quality analysis started for document {document_id}",
        }

        logger.info(f"Quality analysis task started: {task.id}", extra={"user_id": user_id})
        return result

    except Exception as e:
        logger.error(f"Error starting quality analysis task: {e}")
        return {"error": str(e)}


@mcp.tool()
async def summarize_document(
    document_id: str,
    summary_type: str = "extractive",
    max_length: int = 300,
) -> Dict[str, Any]:
    """Generate document summary.

    Args:
        document_id: MongoDB document ID
        summary_type: Type of summarization ('extractive', 'abstractive')
        max_length: Maximum summary length in words

    Returns:
        Summarization task information
    """
    try:
        from ..tasks.document_tasks import document_summarization as summary_task

        user_id = get_current_user_id()

        # Start summarization task
        task = summary_task.delay(document_id, user_id, summary_type, max_length)

        result = {
            "task_id": task.id,
            "status": "processing",
            "message": f"Document summarization started for {document_id}",
            "summary_type": summary_type,
            "max_length": max_length,
        }

        logger.info(f"Summarization task started: {task.id}", extra={"user_id": user_id})
        return result

    except Exception as e:
        logger.error(f"Error starting summarization task: {e}")
        return {"error": str(e)}


@mcp.tool()
async def compare_documents(
    document_id_1: str,
    document_id_2: str,
    comparison_type: str = "content",
) -> Dict[str, Any]:
    """Compare two documents.

    Args:
        document_id_1: First document ID
        document_id_2: Second document ID
        comparison_type: Type of comparison ('content', 'structure', 'both')

    Returns:
        Comparison task information
    """
    try:
        from ..tasks.document_tasks import document_comparison as comparison_task

        user_id = get_current_user_id()

        # Start comparison task
        task = comparison_task.delay(document_id_1, document_id_2, user_id, comparison_type)

        result = {
            "task_id": task.id,
            "status": "processing",
            "message": f"Document comparison started between {document_id_1} and {document_id_2}",
            "comparison_type": comparison_type,
        }

        logger.info(f"Comparison task started: {task.id}", extra={"user_id": user_id})
        return result

    except Exception as e:
        logger.error(f"Error starting comparison task: {e}")
        return {"error": str(e)}


@mcp.tool()
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """Get the status of a background task.

    Args:
        task_id: Celery task ID

    Returns:
        Task status and result if completed
    """
    try:
        from ..tasks.celery_app import celery_app

        task_result = celery_app.AsyncResult(task_id)

        result = {
            "task_id": task_id,
            "status": task_result.status,
            "current": getattr(task_result, 'current', None),
            "total": getattr(task_result, 'total', None),
        }

        if task_result.state == "PROGRESS":
            result["progress"] = {
                "current": task_result.info.get("current", 0),
                "total": task_result.info.get("total", 0),
                "percentage": (
                    task_result.info.get("current", 0) / task_result.info.get("total", 1) * 100
                    if task_result.info.get("total", 0) > 0 else 0
                ),
            }

        elif task_result.state == "SUCCESS":
            result["result"] = task_result.result

        elif task_result.state == "FAILURE":
            result["error"] = str(task_result.info)

        return result

    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return {"error": str(e)}


@mcp.tool()
async def get_processing_analytics(user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get document processing analytics and statistics.

    Args:
        user_id: Optional user ID filter

    Returns:
        Document analytics data
    """
    try:
        from src.second_brain_database.database import db_manager

        user_filter = get_current_user_id()
        if user_id:
            user_filter = user_id

        # Get document statistics
        processed_collection = db_manager.get_collection("processed_documents")
        layout_collection = db_manager.get_collection("document_layout_analysis")
        quality_collection = db_manager.get_collection("document_quality_analysis")
        summary_collection = db_manager.get_collection("document_summaries")
        comparison_collection = db_manager.get_collection("document_comparisons")

        # Basic document stats
        total_docs = await processed_collection.count_documents({"user_id": user_filter})

        # Format distribution
        format_pipeline = [
            {"$match": {"user_id": user_filter}},
            {"$group": {"_id": "$metadata.format", "count": {"$sum": 1}}},
        ]
        format_stats = await processed_collection.aggregate(format_pipeline).to_list(None)

        # Processing analytics
        analytics = {
            "total_documents": total_docs,
            "format_distribution": {doc["_id"]: doc["count"] for doc in format_stats if doc["_id"]},
            "analysis_counts": {
                "layout_analyses": await layout_collection.count_documents({"user_id": user_filter}),
                "quality_analyses": await quality_collection.count_documents({"user_id": user_filter}),
                "summaries": await summary_collection.count_documents({"user_id": user_filter}),
                "comparisons": await comparison_collection.count_documents({"user_id": user_filter}),
            },
        }

        # Recent activity
        recent_docs = await processed_collection.find(
            {"user_id": user_filter},
            {"filename": 1, "created_at": 1, "metadata.format": 1}
        ).sort("created_at", -1).limit(5).to_list(None)

        analytics["recent_activity"] = [
            {
                "filename": doc["filename"],
                "created_at": doc["created_at"],
                "format": doc.get("metadata", {}).get("format"),
            }
            for doc in recent_docs
        ]

        return analytics

    except Exception as e:
        logger.error(f"Error getting document analytics: {e}")
        return {"error": str(e)}