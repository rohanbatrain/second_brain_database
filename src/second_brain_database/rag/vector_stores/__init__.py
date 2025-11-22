"""
RAG Vector Store Service

Unified vector store service for RAG operations that leverages existing
vector search managers and provides a clean abstraction for document
indexing and retrieval in the RAG system.
"""

import time
from typing import Any, Dict, List, Optional, Union

# Lazy import to avoid loading embedding model at startup
# from second_brain_database.managers.vector_search_manager import vector_search_manager
# from second_brain_database.managers.llamaindex_vector_manager import llamaindex_vector_manager

from second_brain_database.rag.core.config import VectorStoreConfig
from second_brain_database.rag.core.exceptions import VectorStoreError
from second_brain_database.rag.core.types import Document, DocumentChunk, QueryRequest, QueryResponse
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()


class RAGVectorStoreService:
    """
    RAG Vector Store Service.
    
    Provides a unified interface to the existing vector search managers,
    abstracting away the complexity and providing RAG-specific operations.
    """
    
    def __init__(self, config: VectorStoreConfig):
        """
        Initialize RAG vector store service.
        
        Args:
            config: Vector store configuration
        """
        self.config = config
        self.provider = config.provider.value.lower()
        
        # Lazy initialization - managers will be loaded when first needed
        self._manager = None
        self._manager_type = None
        
        logger.info(f"Initialized RAG Vector Store Service (lazy loading enabled)")
    
    def _get_manager(self):
        """Lazy load the appropriate vector manager."""
        if self._manager is not None:
            return self._manager
            
        # Import here to avoid loading at startup
        from second_brain_database.managers.vector_search_manager import vector_search_manager
        
        # Temporarily disable LlamaIndex import to fix compatibility issues
        # from second_brain_database.managers.llamaindex_vector_manager import llamaindex_vector_manager
        llamaindex_vector_manager = None
        
        # Select the appropriate vector manager based on configuration
        if self.provider == "llamaindex" and llamaindex_vector_manager and llamaindex_vector_manager.is_initialized():
            self._manager = llamaindex_vector_manager
            self._manager_type = "llamaindex"
            logger.info("Using LlamaIndex vector manager with hybrid search")
        elif vector_search_manager.is_initialized():
            self._manager = vector_search_manager
            self._manager_type = "qdrant"
            logger.info("Using direct Qdrant vector manager")
        else:
            raise VectorStoreError("No vector store manager is available")
        
        return self._manager
    
    @property
    def manager(self):
        """Get the vector manager (lazy loaded)."""
        return self._get_manager()
    
    @property
    def manager_type(self):
        """Get the manager type (lazy loaded)."""
        if self._manager_type is None:
            self._get_manager()  # This will set the manager type
        return self._manager_type
    
    def is_available(self) -> bool:
        """Check if vector store service is available."""
        return hasattr(self.manager, 'is_initialized') and self.manager.is_initialized()
    
    async def index_document(
        self,
        document: Document,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Index a RAG document in the vector store.
        
        Args:
            document: RAG document to index
            **kwargs: Additional indexing options
            
        Returns:
            Dictionary with indexing results
            
        Raises:
            VectorStoreError: If indexing fails
        """
        if not self.is_available():
            raise VectorStoreError("Vector store service is not available")
        
        start_time = time.time()
        logger.info(f"Indexing document '{document.filename}' with {len(document.chunks)} chunks")
        
        try:
            if self.manager_type == "llamaindex":
                return await self._index_with_llamaindex(document, tenant_id=tenant_id, **kwargs)
            else:
                return await self._index_with_qdrant(document, tenant_id=tenant_id, **kwargs)
                
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Failed to index document '{document.filename}' after {processing_time:.2f}s: {e}"
            )
            raise VectorStoreError(f"Document indexing failed: {e}")
    
    async def _index_with_llamaindex(
        self,
        document: Document,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Index document using LlamaIndex vector manager."""
        # Convert RAG document chunks to LlamaIndex format
        llama_docs = []
        
        for chunk in document.chunks:
            chunk_doc = {
                "id": f"{document.id}_{chunk.index}",
                "text": chunk.content,
                "metadata": {
                    "document_id": str(document.id),
                    "document_filename": document.filename,
                    "chunk_index": chunk.index,
                    "chunk_start": chunk.start_char,
                    "chunk_end": chunk.end_char,
                    "token_count": chunk.token_count,
                    "chunk_metadata": chunk.metadata,
                    "document_metadata": document.metadata.model_dump() if document.metadata else {},
                    "status": document.status.value,
                    "created_at": document.created_at.isoformat() if document.created_at else None,
                    "updated_at": document.updated_at.isoformat() if document.updated_at else None,
                }
            }
            llama_docs.append(chunk_doc)
        
        # Index using LlamaIndex
        indexed_ids = await self.manager.index_documents(
            documents=llama_docs,
            user_id=document.user_id
        )
        
        processing_time = time.time() - time.time()
        
        return {
            "document_id": str(document.id),
            "indexed_chunks": len(indexed_ids),
            "chunk_ids": indexed_ids,
            "provider": "llamaindex",
            "hybrid_search_enabled": True,
            "processing_time": processing_time,
            "status": "success"
        }
    
    async def _index_with_qdrant(
        self,
        document: Document,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Index document using Qdrant vector manager."""
        # Extract text chunks for indexing
        chunk_texts = [chunk.content for chunk in document.chunks]
        
        # Prepare metadata
        doc_metadata = {
            "document_id": str(document.id),
            "filename": document.filename,
            "user_id": document.user_id,
            "status": document.status if isinstance(document.status, str) else document.status.value,
            "chunk_count": len(document.chunks),
            "total_tokens": sum(chunk.token_count for chunk in document.chunks if hasattr(chunk, 'token_count')) or len(document.chunks) * 100,  # Fallback estimate
            "created_at": document.created_at.isoformat() if document.created_at else None,
            "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        }
        
        # Add document metadata if available
        if document.metadata:
            doc_metadata.update({
                "title": document.metadata.title,
                "mime_type": document.metadata.mime_type,
                "file_size": document.metadata.file_size,
                "word_count": document.metadata.word_count,
                "page_count": document.metadata.page_count,
                "extracted_tables": document.metadata.extracted_tables,
                "extracted_images": document.metadata.extracted_images,
            })
        
        # Index using Qdrant
        indexed_chunks = await self.manager.index_document_chunks(
            document_id=str(document.id),
            chunks=chunk_texts,
            metadata=doc_metadata,
            user_id=document.user_id,
            tenant_id=tenant_id
        )
        
        processing_time = time.time() - time.time()
        
        return {
            "document_id": str(document.id),
            "indexed_chunks": len(indexed_chunks),
            "chunk_details": indexed_chunks,
            "provider": "qdrant",
            "hybrid_search_enabled": False,
            "processing_time": processing_time,
            "status": "success"
        }
    
    async def search(
        self,
        query: str,
        user_id: str,
        limit: Optional[int] = None,
        score_threshold: Optional[float] = None,
        filters: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant document chunks.
        
        Args:
            query: Search query
            user_id: User ID for filtering
            limit: Maximum number of results
            score_threshold: Minimum similarity score
            filters: Additional metadata filters
            **kwargs: Additional search options
            
        Returns:
            List of search results
            
        Raises:
            VectorStoreError: If search fails
        """
        if not self.is_available():
            raise VectorStoreError("Vector store service is not available")
        
        limit = limit or self.config.default_top_k
        score_threshold = score_threshold or self.config.similarity_threshold
        
        start_time = time.time()
        logger.info(f"Searching for query: '{query[:50]}...' (user: {user_id})")
        
        try:
            if self.manager_type == "llamaindex":
                return await self._search_with_llamaindex(
                    query, user_id, limit, score_threshold, filters, tenant_id=tenant_id, **kwargs
                )
            else:
                return await self._search_with_qdrant(
                    query, user_id, limit, score_threshold, filters, tenant_id=tenant_id, **kwargs
                )
                
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Search failed after {processing_time:.2f}s: {e}")
            raise VectorStoreError(f"Vector search failed: {e}")
    
    async def _search_with_llamaindex(
        self,
        query: str,
        user_id: str,
        limit: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search using LlamaIndex vector manager."""
        # Build filters including user ID
        search_filters = {"user_id": user_id}
        if filters:
            search_filters.update(filters)
        
        # Perform hybrid search
        results = await self.manager.search(
            query_text=query,
            limit=limit,
            filter_dict=search_filters,
            similarity_cutoff=score_threshold,
            alpha=kwargs.get('hybrid_alpha')  # Allow override of hybrid search alpha
        )
        
        # Convert to RAG format
        rag_results = []
        for result in results:
            metadata = result.get("metadata", {})
            rag_result = {
                "text": result["text"],
                "score": result["score"],
                "document_id": metadata.get("document_id"),
                "document_filename": metadata.get("document_filename"),
                "chunk_index": metadata.get("chunk_index"),
                "chunk_start": metadata.get("chunk_start"),
                "chunk_end": metadata.get("chunk_end"),
                "token_count": metadata.get("token_count"),
                "metadata": metadata,
                "provider": "llamaindex",
                "hybrid_search": True,
            }
            rag_results.append(rag_result)
        
        processing_time = time.time() - time.time()
        logger.info(f"LlamaIndex search returned {len(rag_results)} results in {processing_time:.2f}s")
        
        return rag_results
    
    async def _search_with_qdrant(
        self,
        query: str,
        user_id: str,
        limit: int,
        score_threshold: float,
        filters: Optional[Dict[str, Any]],
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Search using Qdrant vector manager."""
        results = await self.manager.semantic_search(
            query=query,
            user_id=user_id,
            limit=limit,
            score_threshold=score_threshold,
            include_metadata=True,
            tenant_id=tenant_id
        )
        
        # Convert to RAG format
        rag_results = []
        for result in results:
            rag_result = {
                "text": result["text"],
                "score": result["score"],
                "document_id": result["document_id"],
                "document_filename": result.get("filename"),
                "chunk_index": result["chunk_index"],
                "format": result.get("format"),
                "metadata": {k: v for k, v in result.items() if k not in ["text", "score"]},
                "provider": "qdrant",
                "hybrid_search": False,
            }
            rag_results.append(rag_result)
        
        processing_time = time.time() - time.time()
        logger.info(f"Qdrant search returned {len(rag_results)} results in {processing_time:.2f}s")
        
        return rag_results
    
    async def delete_document(
        self,
        document_id: str,
        tenant_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        """
        Delete a document from the vector store.
        
        Args:
            document_id: ID of document to delete
            **kwargs: Additional options
            
        Returns:
            True if successful
            
        Raises:
            VectorStoreError: If deletion fails
        """
        if not self.is_available():
            raise VectorStoreError("Vector store service is not available")
        
        logger.info(f"Deleting document vectors for document: {document_id}")
        
        try:
            if self.manager_type == "llamaindex":
                # For LlamaIndex, we need to delete by document ID
                # This might need to be adapted based on the actual LlamaIndex API
                return await self.manager.delete_documents([document_id])
            else:
                # For Qdrant, delete by document ID filter
                return await self.manager.delete_document_vectors(document_id, tenant_id=tenant_id)
                
        except Exception as e:
            logger.error(f"Failed to delete document vectors: {e}")
            raise VectorStoreError(f"Document deletion failed: {e}")
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get vector store statistics.
        
        Returns:
            Dictionary with statistics
        """
        if not self.is_available():
            return {"status": "unavailable", "error": "Vector store service not available"}
        
        try:
            if self.manager_type == "llamaindex":
                # For LlamaIndex, get basic stats
                return {
                    "provider": "llamaindex",
                    "hybrid_search_enabled": True,
                    "status": "available",
                    "features": {
                        "dense_vectors": True,
                        "sparse_vectors": True,
                        "hybrid_search": True,
                        "metadata_filtering": True,
                    }
                }
            else:
                # For Qdrant, get detailed collection stats
                stats = await self.manager.get_collection_stats()
                stats["provider"] = "qdrant"
                stats["hybrid_search_enabled"] = False
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get vector store stats: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_service_info(self) -> Dict[str, Any]:
        """Get information about the vector store service."""
        return {
            "name": "RAGVectorStoreService",
            "provider": self.provider,
            "manager_type": self.manager_type,
            "available": self.is_available(),
            "configuration": {
                "provider": self.config.provider.value,
                "default_top_k": self.config.default_top_k,
                "similarity_threshold": self.config.similarity_threshold,
                "enable_hybrid_search": self.config.enable_hybrid_search,
            },
            "features": {
                "document_indexing": True,
                "semantic_search": True,
                "metadata_filtering": True,
                "batch_operations": True,
                "hybrid_search": self.manager_type == "llamaindex",
                "sparse_vectors": self.manager_type == "llamaindex",
                "dense_vectors": True,
            }
        }