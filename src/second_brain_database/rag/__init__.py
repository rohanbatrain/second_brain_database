"""
Production-Ready RAG (Retrieval-Augmented Generation) System

A comprehensive, modular RAG system for the Second Brain Database application.
Provides advanced document processing, vector search, and AI-powered question answering.

Key Features:
- Multi-format document processing with Docling integration
- Advanced vector search with multiple backend support
- Streaming LLM responses with multiple provider support
- Production-ready monitoring and error handling
- Flexible configuration and extensibility

Architecture:
- Core: Configuration, types, and exceptions
- Document Processing: Parsing, extraction, and preprocessing pipeline
- Vector Stores: Abstracted vector database operations
- LLM: Language model providers and prompt management
- Query Engine: Retrieval, ranking, and answer generation
- Services: High-level business logic
- Models: Data models and schemas
- Utils: Utilities and helpers
- Routes: FastAPI routes and API endpoints

Example Usage:
    from second_brain_database.rag import RAGSystem
    
    # Initialize RAG system
    rag = RAGSystem()
    
    # Process and index documents
    await rag.index_document(file_path="document.pdf", user_id="user123")
    
    # Query with AI
    response = await rag.query(
        query="What are the key findings?",
        user_id="user123",
        use_llm=True,
        streaming=True
    )
"""

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.rag.core.config import RAGConfig
from second_brain_database.rag.core.exceptions import (
    DocumentProcessingError,
    LLMError,
    QueryEngineError,
    RAGError,
    VectorStoreError,
)
from second_brain_database.rag.core.types import QueryRequest, QueryResponse, QueryType
from second_brain_database.rag.document_processing import RAGDocumentService
from second_brain_database.rag.llm import RAGLLMService
from second_brain_database.rag.query_engine import RAGQueryEngine
from second_brain_database.rag.vector_stores import RAGVectorStoreService

logger = get_logger()

# Main RAG system class
class RAGSystem:
    """
    Main RAG system orchestrator.
    
    Provides a high-level interface to all RAG functionality including
    document processing, vector search, and AI-powered querying.
    
    This simplified version focuses on leveraging the existing DocumentProcessor
    and will be extended with vector store and LLM capabilities.
    """
    
    def __init__(self, config: RAGConfig = None):
        """
        Initialize the RAG system.
        
        Args:
            config: Optional RAG configuration. Uses default if not provided.
        """
        self.config = config or RAGConfig()
        
        # Initialize services (lazy loading)
        self._document_service = None
        self._vector_store_service = None
        self._llm_service = None
        self._query_engine = None
        
        logger.info("Initialized comprehensive RAG system")
    
    @property
    def document_service(self) -> RAGDocumentService:
        """Get the document processing service (lazy initialization)."""
        if self._document_service is None:
            self._document_service = RAGDocumentService(self.config.document_processing)
        return self._document_service
    
    @property
    def vector_store_service(self) -> RAGVectorStoreService:
        """Get the vector store service (lazy initialization)."""
        if self._vector_store_service is None:
            self._vector_store_service = RAGVectorStoreService(self.config.vector_store)
        return self._vector_store_service
    
    @property
    def llm_service(self) -> RAGLLMService:
        """Get the LLM service (lazy initialization)."""
        if self._llm_service is None:
            self._llm_service = RAGLLMService(self.config.llm)
        return self._llm_service
    
    @property
    def query_engine(self) -> RAGQueryEngine:
        """Get the query engine (lazy initialization)."""
        if self._query_engine is None:
            self._query_engine = RAGQueryEngine(self.config)
        return self._query_engine
    
    async def process_and_index_document(
        self, 
        file_data, 
        filename: str, 
        user_id: str, 
        tenant_id: str = None,
        **kwargs
    ) -> dict:
        """
        Process and index a document in the RAG system.
        
        Args:
            file_data: Binary file data or file-like object
            filename: Name of the file
            user_id: ID of the user uploading the document
            tenant_id: ID of the tenant
            **kwargs: Additional processing options
        
        Returns:
            Complete processing and indexing result
        """
        try:
            # Step 1: Process document
            document = await self.document_service.process_document(
                file_data=file_data,
                filename=filename,
                user_id=user_id,
                tenant_id=tenant_id,
                **kwargs
            )
            
            # Step 2: Index in vector store
            indexing_result = await self.vector_store_service.index_document(
                document=document,
                tenant_id=tenant_id,
                **kwargs
            )
            
            logger.info(f"Successfully processed and indexed document '{filename}' for user '{user_id}'")
            
            return {
                "document": {
                    "id": str(document.id),
                    "filename": document.filename,
                    "chunks": len(document.chunks),
                    "status": str(document.status),
                },
                "processing": {
                    "chunks_created": len(document.chunks),
                    "metadata": document.metadata,
                },
                "indexing": indexing_result,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Failed to process and index document '{filename}': {e}")
            raise RAGError(f"Document processing and indexing failed: {e}")
    
    async def query(
        self, 
        query: str, 
        user_id: str,
        use_llm: bool = True,
        streaming: bool = False,
        tenant_id: str = None,
        **kwargs
    ) -> dict:
        """
        Query the RAG system.
        
        Args:
            query: User query
            user_id: User ID
            use_llm: Whether to use LLM for answer generation
            streaming: Whether to use streaming response
            tenant_id: Tenant ID
            **kwargs: Additional query options
            
        Returns:
            Query response
        """
        from .core.types import QueryContext
        
        context = QueryContext(
            user_id=user_id,
            tenant_id=tenant_id,
            conversation_id=kwargs.get('conversation_id'),
            top_k=kwargs.get('top_k', 5),
            use_llm=use_llm,
            streaming=streaming,
            document_filters=kwargs.get('filters', {}),
            metadata_filters=kwargs.get('metadata_filters', {}),
            include_citations=kwargs.get('include_citations', True)
        )
        
        query_request = QueryRequest(
            query=query,
            context=context,
            query_type=kwargs.get('query_type', QueryType.HYBRID)
        )
        
        if streaming and use_llm:
            # Return streaming generator
            return self.query_engine.query_stream(query_request, **kwargs)
        else:
            # Return complete response
            response = await self.query_engine.query(query_request, **kwargs)
            return {
                "query": response.query,
                "answer": response.answer,
                "sources": [citation.document_title or citation.document_id for citation in response.citations],
                "context_chunks": [
                    {
                        "text": chunk.content,
                        "score": chunk.score,
                        "document": chunk.document_metadata.get("filename", ""),
                    }
                    for chunk in response.chunks[:3]  # Show top 3
                ],
                "confidence": response.confidence_score,
                "processing_time": response.processing_time,
                "model_used": response.metadata.get("model_used", "vector_search_only"),
                "metadata": response.metadata,
            }
    
    async def chat(
        self,
        message: str,
        conversation_id: str,
        user_id: str,
        **kwargs
    ) -> dict:
        """
        Chat with the RAG system.
        
        Args:
            message: Chat message
            conversation_id: Conversation ID
            user_id: User ID
            **kwargs: Additional options
            
        Returns:
            Chat response
        """
        response = await self.query_engine.chat(
            message=message,
            conversation_id=conversation_id,
            user_id=user_id,
            **kwargs
        )
        
        return {
            "message": message,
            "response": response.answer,
            "sources": response.sources,
            "conversation_id": conversation_id,
            "processing_time": response.processing_time,
        }
    
    async def get_supported_formats(self) -> list:
        """Get list of supported document formats."""
        return self.document_service.get_supported_formats()
    
    async def get_system_status(self) -> dict:
        """Get comprehensive system status."""
        try:
            # Get service statuses
            document_info = await self.document_service.get_service_info()
            vector_stats = await self.vector_store_service.get_stats()
            llm_info = await self.llm_service.get_service_info()
            engine_stats = await self.query_engine.get_engine_stats()
            
            return {
                "rag_system": {
                    "version": "1.0.0",
                    "status": "operational" if self.query_engine.is_available() else "degraded",
                    "architecture": "production_ready_modular",
                },
                "services": {
                    "document_processing": {
                        "status": "available",
                        "info": document_info,
                    },
                    "vector_store": {
                        "status": "available" if self.vector_store_service.is_available() else "unavailable",
                        "stats": vector_stats,
                    },
                    "llm_service": {
                        "status": "available" if self.llm_service.is_available() else "unavailable", 
                        "info": llm_info,
                    },
                    "query_engine": {
                        "status": "available" if self.query_engine.is_available() else "unavailable",
                        "stats": engine_stats,
                    },
                },
                "configuration": {
                    "document_processing": {
                        "chunk_size": self.config.document_processing.chunk_size,
                        "chunk_overlap": self.config.document_processing.chunk_overlap,
                        "strategy": self.config.document_processing.chunk_strategy,
                    },
                    "vector_store": {
                        "provider": self.config.vector_store.provider.value,
                        "top_k": self.config.vector_store.default_top_k,
                        "similarity_threshold": self.config.vector_store.similarity_threshold,
                    },
                    "llm": {
                        "provider": self.config.llm.provider.value,
                        "model": self.config.llm.model_name,
                        "temperature": self.config.llm.temperature,
                    },
                },
            }
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {
                "rag_system": {
                    "version": "1.0.0", 
                    "status": "error",
                    "error": str(e),
                }
            }


# Export main classes and functions
__all__ = [
    "RAGSystem",
    "RAGConfig",
    "RAGDocumentService",
    "RAGError",
    "DocumentProcessingError",
    "VectorStoreError", 
    "LLMError",
    "QueryEngineError",
]

# Version info
__version__ = "1.0.0"
__author__ = "Second Brain Database Team"
__description__ = "Production-ready RAG system with advanced document processing and AI integration"