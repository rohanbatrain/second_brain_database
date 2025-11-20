"""RAG (Retrieval Augmented Generation) Service.

This module provides RAG capabilities combining vector search with LLM generation
for intelligent document querying, chat, and analysis.

Features:
- Semantic search with vector similarity
- LLM-powered question answering
- Multi-turn conversation with context
- Document analysis and summarization
- Source citation and attribution
"""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from ..config import settings
from ..database import db_manager
from ..managers.logging_manager import get_logger
from ..managers.ollama_manager import ollama_manager
from ..managers.vector_search_manager import vector_search_manager

logger = get_logger(prefix="[RAGService]")


class RAGService:
    """Service for RAG operations.

    This service combines vector search with LLM generation to provide
    intelligent document querying and analysis capabilities.

    Attributes:
        top_k: Number of top similar chunks to retrieve
        similarity_threshold: Minimum similarity score
        max_context_length: Maximum context length in chars
    """

    def __init__(self):
        """Initialize RAG service."""
        self.top_k = 5
        self.similarity_threshold = 0.7
        self.max_context_length = 8000

        logger.info(
            "RAG service initialized",
            extra={
                "top_k": self.top_k,
                "threshold": self.similarity_threshold,
            }
        )

    async def query_document(
        self,
        query: str,
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        top_k: Optional[int] = None,
        use_llm: bool = True,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Query documents using RAG.

        Args:
            query: User query
            document_id: Optional document ID to search within
            user_id: Optional user ID for scoping
            top_k: Number of results to retrieve
            use_llm: Use LLM for answer generation
            model: LLM model to use
            temperature: LLM temperature

        Returns:
            Query result with answer and sources

        Raises:
            Exception: If query fails
        """
        top_k = top_k or self.top_k

        try:
            # Build filters
            filters = {}
            if document_id:
                filters["document_id"] = document_id
            if user_id:
                filters["user_id"] = user_id

                        # Use LlamaIndex vector manager if available, otherwise fallback to basic vector search
            if hasattr(settings, 'LLAMAINDEX_ENABLED') and settings.LLAMAINDEX_ENABLED:
                from ..managers.llamaindex_vector_manager import llamaindex_vector_manager
                search_results = await llamaindex_vector_manager.search(
                    query_text=query,
                    limit=top_k,
                    filter_dict=filters,
                )
            else:
                # Fallback to basic vector search
                search_results = await vector_search_manager.semantic_search(
                    query=query,
                    user_id=user_id,
                    limit=top_k,
                    score_threshold=self.similarity_threshold,
                )

            # Extract chunks and metadata
            chunks = []
            sources = []

            for result in search_results:
                chunk_text = result.get("text", "")
                score = result.get("score", 0.0)

                if score >= self.similarity_threshold:
                    chunks.append({
                        "text": chunk_text,
                        "score": score,
                        "metadata": result.get("metadata", {}),
                    })

                    # Track unique sources
                    doc_id = result.get("metadata", {}).get("document_id")
                    if doc_id and doc_id not in [s["document_id"] for s in sources]:
                        sources.append({
                            "document_id": doc_id,
                            "filename": result.get("metadata", {}).get("filename", ""),
                        })

            # Build context from chunks
            context = self._build_context(chunks)

            # Generate answer with LLM if requested
            answer = None
            if use_llm and chunks:
                answer = await self._generate_answer(
                    query=query,
                    context=context,
                    model=model,
                    temperature=temperature,
                )

            result = {
                "query": query,
                "answer": answer,
                "chunks": chunks,
                "sources": sources,
                "chunk_count": len(chunks),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                f"Query completed: {len(chunks)} chunks, LLM={'enabled' if use_llm else 'disabled'}",
                extra={
                    "query_length": len(query),
                    "chunk_count": len(chunks),
                    "use_llm": use_llm,
                }
            )

            return result

        except Exception as e:
            logger.error(
                f"Query failed: {e}",
                exc_info=True,
                extra={"query": query[:100]}
            )
            raise

    async def chat_with_documents(
        self,
        messages: List[Dict[str, str]],
        document_id: Optional[str] = None,
        user_id: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> Dict[str, Any] | AsyncGenerator[str, None]:
        """Multi-turn chat with document context.

        Args:
            messages: Conversation history (list of {role, content})
            document_id: Optional document ID
            user_id: Optional user ID
            model: LLM model
            temperature: Temperature
            stream: Enable streaming

        Returns:
            Chat response or async generator if streaming

        Raises:
            Exception: If chat fails
        """
        try:
            # Get last user message as query
            user_messages = [m for m in messages if m.get("role") == "user"]
            if not user_messages:
                raise ValueError("No user messages in conversation")

            last_query = user_messages[-1].get("content", "")

            # Retrieve relevant context
            query_result = await self.query_document(
                query=last_query,
                document_id=document_id,
                user_id=user_id,
                use_llm=False,  # Don't generate answer yet
            )

            context = self._build_context(query_result["chunks"])

            # Build chat messages with context
            chat_messages = []

            # System message with context
            if context:
                system_msg = {
                    "role": "system",
                    "content": (
                        f"You are a helpful assistant with access to document content. "
                        f"Use the following context to answer questions:\n\n{context}\n\n"
                        f"If the context doesn't contain relevant information, say so."
                    ),
                }
                chat_messages.append(system_msg)

            # Add conversation history
            chat_messages.extend(messages)

            # Generate response
            if stream:
                return ollama_manager.chat(
                    messages=chat_messages,
                    model=model,
                    temperature=temperature,
                    stream=True,
                )
            else:
                response = await ollama_manager.chat(
                    messages=chat_messages,
                    model=model,
                    temperature=temperature,
                    stream=False,
                )

                result = {
                    "response": response,
                    "sources": query_result["sources"],
                    "chunk_count": query_result["chunk_count"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                logger.info(
                    f"Chat completed: {query_result['chunk_count']} chunks used",
                    extra={
                        "message_count": len(messages),
                        "chunk_count": query_result["chunk_count"],
                    }
                )

                return result

        except Exception as e:
            logger.error(
                f"Chat failed: {e}",
                exc_info=True,
                extra={"message_count": len(messages)}
            )
            raise

    async def analyze_document_with_llm(
        self,
        document_id: str,
        analysis_type: str = "summary",
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """Analyze document using LLM.

        Args:
            document_id: Document ID
            analysis_type: Type of analysis (summary, insights, key_points)
            model: LLM model
            temperature: Temperature

        Returns:
            Analysis result

        Raises:
            Exception: If analysis fails
        """
        try:
            # Get document content
            collection = db_manager.get_collection("documents")
            doc = await collection.find_one({"_id": document_id})

            if not doc:
                raise ValueError(f"Document {document_id} not found")

            content = doc.get("content", "")

            # Truncate if needed
            if len(content) > self.max_context_length:
                content = content[:self.max_context_length] + "\n\n[Content truncated...]"

            # Build prompt based on analysis type
            prompts = {
                "summary": (
                    "Please provide a comprehensive summary of the following document. "
                    "Include the main topics, key points, and conclusions:\n\n{content}"
                ),
                "insights": (
                    "Analyze the following document and provide key insights, "
                    "important findings, and actionable takeaways:\n\n{content}"
                ),
                "key_points": (
                    "Extract the key points from the following document as a bulleted list. "
                    "Focus on the most important information:\n\n{content}"
                ),
            }

            prompt = prompts.get(analysis_type, prompts["summary"]).format(content=content)

            # Generate analysis
            analysis = await ollama_manager.generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
            )

            result = {
                "document_id": document_id,
                "analysis_type": analysis_type,
                "analysis": analysis,
                "model": model or ollama_manager.default_model,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(
                f"Document analysis completed: {analysis_type}",
                extra={
                    "document_id": document_id,
                    "analysis_type": analysis_type,
                    "content_length": len(content),
                }
            )

            return result

        except Exception as e:
            logger.error(
                f"Document analysis failed: {e}",
                exc_info=True,
                extra={"document_id": document_id, "analysis_type": analysis_type}
            )
            raise

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context string from chunks.

        Args:
            chunks: List of chunk dicts

        Returns:
            Context string
        """
        if not chunks:
            return ""

        context_parts = []
        current_length = 0

        for i, chunk in enumerate(chunks, 1):
            text = chunk.get("text", "")
            score = chunk.get("score", 0.0)

            # Add chunk with metadata
            part = f"[Source {i}, Relevance: {score:.2f}]\n{text}\n"

            # Check length
            if current_length + len(part) > self.max_context_length:
                break

            context_parts.append(part)
            current_length += len(part)

        return "\n".join(context_parts)

    async def _generate_answer(
        self,
        query: str,
        context: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """Generate answer using LLM.

        Args:
            query: User query
            context: Context from retrieved chunks
            model: LLM model
            temperature: Temperature

        Returns:
            Generated answer

        Raises:
            Exception: If generation fails
        """
        prompt = f"""Based on the following context, please answer the question. If the context doesn't contain enough information to answer the question, say so clearly.

Context:
{context}

Question: {query}

Answer:"""

        try:
            answer = await ollama_manager.generate(
                prompt=prompt,
                model=model,
                temperature=temperature,
            )

            return answer

        except Exception as e:
            logger.error(f"Answer generation failed: {e}", exc_info=True)
            raise


# Global instance
rag_service = RAGService()
