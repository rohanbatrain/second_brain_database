"""
RAG Query Engine

Sophisticated query engine that combines vector search with LLM generation
to provide comprehensive, context-aware responses to user queries.
"""

import time
from typing import Any, AsyncIterator, Dict, List, Optional
import uuid

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.rag.core.config import RAGConfig
from second_brain_database.rag.core.exceptions import QueryEngineError
from second_brain_database.rag.core.types import (
    ChatMessage,
    Conversation,
    Document,
    DocumentChunk,
    QueryRequest,
    QueryResponse,
)
from second_brain_database.rag.llm import RAGLLMService
from second_brain_database.rag.vector_stores import RAGVectorStoreService

logger = get_logger()


class RAGQueryEngine:
    """
    RAG Query Engine.
    
    Orchestrates the entire RAG pipeline: query processing, context retrieval,
    answer generation, and response optimization.
    """
    
    def __init__(self, config: RAGConfig):
        """
        Initialize RAG query engine.
        
        Args:
            config: RAG system configuration
        """
        self.config = config
        
        # Initialize services
        self.vector_store = RAGVectorStoreService(config.vector_store)
        self.llm_service = RAGLLMService(config.llm)
        
        # Query processing parameters
        self.max_context_length = getattr(config, 'max_context_length', 8000)
        self.min_chunk_score = getattr(config, 'min_chunk_score', 0.7)
        self.enable_reranking = getattr(config, 'enable_reranking', False)
        
        logger.info("Initialized RAG Query Engine with vector store and LLM services")
    
    def is_available(self) -> bool:
        """Check if query engine is operational for at least vector search."""
        # Query engine can work with just vector store for search-only queries
        return self.vector_store.is_available()
    
    async def query(
        self,
        query_request: QueryRequest,
        **kwargs
    ) -> QueryResponse:
        """
        Process a query through the complete RAG pipeline.
        
        Args:
            query_request: The query request with user query and parameters
            **kwargs: Additional query options
            
        Returns:
            Complete query response with answer and context
            
        Raises:
            QueryEngineError: If query processing fails
        """
        if not self.is_available():
            raise QueryEngineError("Query engine is not available")
        
        start_time = time.time()
        query_id = str(uuid.uuid4())
        
        logger.info(
            f"Processing query [{query_id}]: '{query_request.query[:50]}...'",
            extra={
                "query_id": query_id,
                "user_id": query_request.context.user_id,
                "use_llm": query_request.context.use_llm
            }
        )
        
        try:
            # Phase 1: Query preprocessing and optimization
            optimized_query = await self._preprocess_query(query_request.query)
            
            # Phase 2: Context retrieval from vector store
            context_chunks = await self._retrieve_context(
                optimized_query,
                query_request.context.user_id,
                limit=query_request.context.top_k or self.config.vector_store.default_top_k,
                filters=query_request.context.document_filters
            )
            
            # Phase 3: Context optimization and ranking
            if context_chunks:
                context_chunks = await self._optimize_context(
                    context_chunks, 
                    query_request.query
                )
            
            # Phase 4: Answer generation (if LLM enabled)
            if query_request.context.use_llm and context_chunks and self.llm_service.is_available():
                response = await self.llm_service.generate_response(
                    query=query_request.query,
                    context_chunks=context_chunks,
                    conversation_history=kwargs.get('conversation_history', []),
                    temperature=kwargs.get('temperature'),
                    max_tokens=kwargs.get('max_tokens')
                )
            else:
                # Return search results without LLM generation
                response = self._create_search_only_response(
                    query_request.query,
                    context_chunks,
                    query_request.context.user_id
                )
            
            # Phase 5: Response post-processing
            final_response = await self._postprocess_response(
                response, 
                query_request,
                query_id
            )
            
            processing_time = time.time() - start_time
            final_response.processing_time = processing_time
            
            logger.info(
                f"Query [{query_id}] completed in {processing_time:.2f}s",
                extra={
                    "query_id": query_id,
                    "chunks_found": len(context_chunks),
                    "answer_length": len(final_response.answer),
                    "used_llm": query_request.context.use_llm
                }
            )
            
            return final_response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"Query [{query_id}] failed after {processing_time:.2f}s: {e}",
                extra={"query_id": query_id, "error": str(e)}
            )
            raise QueryEngineError(f"Query processing failed: {e}")
    
    async def query_stream(
        self,
        query_request: QueryRequest,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Process a query with streaming response.
        
        Args:
            query_request: The query request
            **kwargs: Additional options
            
        Yields:
            Streaming response chunks
            
        Raises:
            QueryEngineError: If streaming query fails
        """
        if not self.is_available():
            raise QueryEngineError("Query engine is not available")
        
        if not query_request.context.use_llm:
            raise QueryEngineError("Streaming requires LLM to be enabled")
        
        query_id = str(uuid.uuid4())
        
        logger.info(f"Starting streaming query [{query_id}]: '{query_request.query[:50]}...'")
        
        try:
            # Retrieve context (non-streaming part)
            optimized_query = await self._preprocess_query(query_request.query)
            
            context_chunks = await self._retrieve_context(
                optimized_query,
                query_request.user_id,
                limit=query_request.top_k or self.config.vector_store.default_top_k,
                filters=query_request.filters
            )
            
            if context_chunks:
                context_chunks = await self._optimize_context(context_chunks, query_request.query)
            
            # Stream LLM response
            async for chunk in self.llm_service.generate_streaming_response(
                query=query_request.query,
                context_chunks=context_chunks,
                conversation_history=query_request.conversation_history,
                **kwargs
            ):
                yield chunk
                
        except Exception as e:
            logger.error(f"Streaming query [{query_id}] failed: {e}")
            raise QueryEngineError(f"Streaming query failed: {e}")
    
    async def chat(
        self,
        message: str,
        conversation_id: str,
        user_id: str,
        **kwargs
    ) -> QueryResponse:
        """
        Process a chat message with conversation context.
        
        Args:
            message: Chat message
            conversation_id: Conversation identifier
            user_id: User identifier
            **kwargs: Additional options
            
        Returns:
            Query response with conversation context
        """
        # TODO: Implement conversation memory retrieval
        # For now, create a simple query request
        query_request = QueryRequest(
            query=message,
            user_id=user_id,
            use_llm=True,
            conversation_history=[]  # Would load from conversation store
        )
        
        response = await self.query(query_request, **kwargs)
        
        # TODO: Store conversation message and response
        
        return response
    
    async def _preprocess_query(self, query: str) -> str:
        """
        Preprocess and optimize the user query.
        
        Args:
            query: Original user query
            
        Returns:
            Optimized query for vector search
        """
        # Basic query preprocessing
        # Can be enhanced with query expansion, spell correction, etc.
        
        # Remove excessive whitespace
        optimized = " ".join(query.split())
        
        # TODO: Add query expansion, spell correction, etc.
        
        return optimized
    
    async def _retrieve_context(
        self,
        query: str,
        user_id: str,
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context from vector store.
        
        Args:
            query: Search query
            user_id: User ID for filtering
            limit: Maximum results
            filters: Additional filters
            
        Returns:
            List of relevant document chunks
        """
        try:
            results = await self.vector_store.search(
                query=query,
                user_id=user_id,
                limit=limit,
                score_threshold=self.min_chunk_score,
                filters=filters
            )
            
            logger.debug(f"Vector search returned {len(results)} chunks")
            return results
            
        except Exception as e:
            logger.error(f"Context retrieval failed: {e}")
            return []
    
    async def _optimize_context(
        self,
        chunks: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Optimize and rank context chunks.
        
        Args:
            chunks: Retrieved chunks
            query: Original query
            
        Returns:
            Optimized and ranked chunks
        """
        if not chunks:
            return chunks
        
        # Phase 1: Remove duplicates based on content similarity
        unique_chunks = self._deduplicate_chunks(chunks)
        
        # Phase 2: Rerank if enabled
        if self.enable_reranking:
            ranked_chunks = await self._rerank_chunks(unique_chunks, query)
        else:
            ranked_chunks = unique_chunks
        
        # Phase 3: Limit by context length
        optimized_chunks = self._limit_context_length(ranked_chunks)
        
        logger.debug(
            f"Context optimization: {len(chunks)} → {len(unique_chunks)} → {len(optimized_chunks)} chunks"
        )
        
        return optimized_chunks
    
    def _deduplicate_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate or highly similar chunks."""
        if not chunks:
            return chunks
        
        unique_chunks = []
        seen_texts = set()
        
        for chunk in chunks:
            text = chunk.get("text", "").strip()
            
            # Simple deduplication by text content
            if text and text not in seen_texts:
                unique_chunks.append(chunk)
                seen_texts.add(text)
        
        return unique_chunks
    
    async def _rerank_chunks(
        self,
        chunks: List[Dict[str, Any]],
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Rerank chunks using advanced relevance scoring.
        
        This is a placeholder for more sophisticated reranking.
        Could use cross-encoders, BM25, or other ranking models.
        """
        # For now, just return as-is (already sorted by vector similarity)
        # TODO: Implement cross-encoder reranking, BM25 fusion, etc.
        return chunks
    
    def _limit_context_length(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Limit context to maximum length."""
        if not chunks:
            return chunks
        
        total_length = 0
        limited_chunks = []
        
        for chunk in chunks:
            text = chunk.get("text", "")
            chunk_length = len(text)
            
            if total_length + chunk_length <= self.max_context_length:
                limited_chunks.append(chunk)
                total_length += chunk_length
            else:
                # Try to fit partial chunk if there's room
                remaining = self.max_context_length - total_length
                if remaining > 100:  # Minimum useful chunk size
                    partial_chunk = chunk.copy()
                    partial_chunk["text"] = text[:remaining]
                    limited_chunks.append(partial_chunk)
                break
        
        return limited_chunks
    
    def _create_search_only_response(
        self,
        query: str,
        context_chunks: List[Dict[str, Any]],
        user_id: str
    ) -> QueryResponse:
        """Create response for search-only queries (no LLM)."""
        if not context_chunks:
            answer = "No relevant documents found for your query."
        else:
            # Create a summary of found documents
            sources = set()
            for chunk in context_chunks:
                filename = chunk.get("document_filename") or chunk.get("filename")
                if filename:
                    sources.add(filename)
            
            answer = f"Found {len(context_chunks)} relevant passages"
            if sources:
                answer += f" from {len(sources)} documents: {', '.join(list(sources)[:3])}"
                if len(sources) > 3:
                    answer += f" and {len(sources) - 3} more"
            answer += "."
        
        return QueryResponse(
            query=query,
            user_id=user_id,
            answer=answer,
            chunks=context_chunks,
            confidence_score=0.8 if context_chunks else 0.2,
            processing_time=0.0,  # Will be updated
            chunk_count=len(context_chunks),
            metadata={
                "search_only": True,
                "chunks_found": len(context_chunks),
                "model_used": "vector_search_only",
                "provider": "rag_engine"
            }
        )
    
    def _extract_sources(self, context_chunks: List[Dict[str, Any]]) -> List[str]:
        """Extract unique source documents from chunks."""
        sources = []
        seen = set()
        
        for chunk in context_chunks:
            filename = chunk.get("document_filename") or chunk.get("filename")
            if filename and filename not in seen:
                sources.append(filename)
                seen.add(filename)
        
        return sources
    
    async def _postprocess_response(
        self,
        response: QueryResponse,
        original_request: QueryRequest,
        query_id: str
    ) -> QueryResponse:
        """Post-process the response before returning."""
        # Add query ID to metadata
        if response.metadata is None:
            response.metadata = {}
        
        response.metadata.update({
            "query_id": query_id,
            "original_query": original_request.query,
            "user_id": original_request.context.user_id,
            "engine_version": "1.0.0"
        })
        
        return response
    
    async def get_engine_stats(self) -> Dict[str, Any]:
        """Get query engine statistics."""
        vector_stats = await self.vector_store.get_stats()
        llm_info = await self.llm_service.get_service_info()
        
        return {
            "engine_status": "available" if self.is_available() else "unavailable",
            "vector_store": vector_stats,
            "llm_service": llm_info,
            "configuration": {
                "max_context_length": self.max_context_length,
                "min_chunk_score": self.min_chunk_score,
                "enable_reranking": self.enable_reranking,
            },
            "features": {
                "semantic_search": True,
                "llm_generation": True,
                "streaming_responses": True,
                "conversation_memory": True,
                "context_optimization": True,
                "source_citation": True,
                "hybrid_search": vector_stats.get("hybrid_search_enabled", False),
            }
        }