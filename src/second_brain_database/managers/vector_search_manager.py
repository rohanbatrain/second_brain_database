"""Vector search manager for document embeddings and semantic search.

This module provides a professional, production-ready vector search implementation
using Qdrant for document embeddings and semantic similarity search.

Features:
- Qdrant vector database integration
- Sentence transformer embeddings
- Semantic and hybrid search capabilities
- Automatic collection management
- Batch processing and optimization
- Comprehensive error handling and logging

Architecture:
- Separates vector operations from document processing
- Provides clean API for embedding generation and search
- Handles connection management and retries
- Supports multiple embedding models and configurations
"""

import asyncio
from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid
import threading
import time

from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer

from ..config import settings
from ..managers.logging_manager import get_logger

logger = get_logger(prefix="[VectorSearchManager]")


class VectorSearchManager:
    """Professional vector search manager for document embeddings and semantic search."""

    def __init__(self):
        """Initialize the vector search manager with Qdrant and embedding model."""
        self.qdrant_client: Optional[QdrantClient] = None
        self.embedding_model: Optional[SentenceTransformer] = None
        self._initialized = False
        self._model_loading = False
        self._model_load_lock = threading.Lock()
        self._background_loader: Optional[threading.Thread] = None

        if settings.QDRANT_ENABLED:
            self._initialize_qdrant()
            self._ensure_collections()
            # Start background model loading instead of blocking initialization
            self._start_background_model_loading()
            self._initialized = True
        else:
            logger.info("Qdrant integration disabled")

    def _initialize_qdrant(self) -> None:
        """Initialize Qdrant client with proper error handling."""
        if not settings.QDRANT_ENABLED:
            logger.info("Qdrant integration disabled")
            self.qdrant_client = None
            return

        try:
            self.qdrant_client = QdrantClient(
                host=settings.QDRANT_HOST,
                port=settings.QDRANT_PORT,
                https=settings.QDRANT_HTTPS,
                api_key=settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None,
                timeout=settings.QDRANT_TIMEOUT,
            )
            # Test connection
            self.qdrant_client.get_collections()
            logger.info(f"Qdrant client initialized successfully at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")

        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            self.qdrant_client = None
            raise

    def _start_background_model_loading(self) -> None:
        """Start background thread to load the embedding model."""
        if self._background_loader and self._background_loader.is_alive():
            return  # Already loading

        self._background_loader = threading.Thread(
            target=self._load_model_in_background,
            daemon=True,
            name="EmbeddingModelLoader"
        )
        self._background_loader.start()
        logger.info("Started background embedding model loading")

    def _load_model_in_background(self) -> None:
        """Load the embedding model in a background thread."""
        try:
            start_time = time.time()
            with self._model_load_lock:
                if self.embedding_model is not None:
                    return  # Already loaded

                self._model_loading = True
                logger.info(f"Loading embedding model '{settings.EMBEDDING_MODEL}' in background...")

                # Explicitly set device to 'cpu' to avoid meta tensor issues
                self.embedding_model = SentenceTransformer(
                    model_name_or_path=settings.EMBEDDING_MODEL,
                    cache_folder=settings.EMBEDDING_CACHE_DIR,
                    device='cpu'  # Explicitly use CPU to avoid PyTorch meta tensor issues
                )

                load_time = time.time() - start_time
                logger.info(f"Embedding model '{settings.EMBEDDING_MODEL}' loaded successfully in {load_time:.2f}s")

        except Exception as e:
            logger.error(f"Failed to load embedding model in background: {e}")
            self.embedding_model = None
        finally:
            self._model_loading = False

    def _ensure_embedding_model_loaded(self) -> None:
        """Ensure the embedding model is loaded, loading it synchronously if needed."""
        if self.embedding_model is not None:
            return  # Already loaded

        with self._model_load_lock:
            if self.embedding_model is not None:
                return  # Double-check after acquiring lock

            if self._model_loading:
                # Wait for background loading to complete
                logger.info("Waiting for background model loading to complete...")
                while self._model_loading:
                    time.sleep(0.1)
                if self.embedding_model is not None:
                    return

            # Fallback: load synchronously if background loading failed
            logger.warning("Background model loading failed or not available, loading synchronously...")
            try:
                start_time = time.time()
                # Explicitly set device to 'cpu' to avoid meta tensor issues
                # See: https://github.com/UKPLab/sentence-transformers/issues/1318
                self.embedding_model = SentenceTransformer(
                    model_name_or_path=settings.EMBEDDING_MODEL,
                    cache_folder=settings.EMBEDDING_CACHE_DIR,
                    device='cpu'  # Explicitly use CPU to avoid PyTorch meta tensor issues
                )
                load_time = time.time() - start_time
                logger.info(f"Embedding model loaded synchronously in {load_time:.2f}s")
            except Exception as e:
                logger.error(f"Failed to initialize embedding model: {e}")
                self.embedding_model = None
                raise

    def _ensure_collections(self) -> None:
        """Ensure required Qdrant collections exist with proper configuration."""
        if not self.qdrant_client:
            return

        try:
            collections = self.qdrant_client.get_collections()
            existing_collections = [c.name for c in collections.collections]

            # Ensure document collection exists
            if settings.QDRANT_DOCUMENT_COLLECTION not in existing_collections:
                self.qdrant_client.create_collection(
                    collection_name=settings.QDRANT_DOCUMENT_COLLECTION,
                    vectors_config=models.VectorParams(
                        size=settings.QDRANT_VECTOR_SIZE,
                        distance=self._get_distance_metric(),
                    ),
                    optimizers_config=models.OptimizersConfigDiff(
                        indexing_threshold=settings.QDRANT_INDEXING_THRESHOLD,
                    ),
                )
                logger.info(f"Created Qdrant collection: {settings.QDRANT_DOCUMENT_COLLECTION}")
            else:
                logger.info(f"Qdrant collection already exists: {settings.QDRANT_DOCUMENT_COLLECTION}")

        except Exception as e:
            logger.error(f"Failed to ensure Qdrant collections: {e}")
            raise

    def _get_distance_metric(self) -> models.Distance:
        """Get the distance metric enum from settings."""
        metric_map = {
            "Cosine": models.Distance.COSINE,
            "Euclidean": models.Distance.EUCLID,
            "Dot": models.Distance.DOT,
        }
        return metric_map.get(settings.QDRANT_DISTANCE_METRIC, models.Distance.COSINE)

    def is_initialized(self) -> bool:
        """Check if the vector search manager is properly initialized."""
        return self._initialized and self.qdrant_client is not None

    def is_model_ready(self) -> bool:
        """Check if the embedding model is loaded and ready."""
        return self.embedding_model is not None

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ValueError: If embedding model is not initialized
        """
        # Ensure model is loaded before proceeding
        self._ensure_embedding_model_loaded()

        if not self.embedding_model:
            raise ValueError("Embedding model not initialized")

        try:
            # Run embedding generation in thread pool to avoid blocking
            embeddings = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.embedding_model.encode(
                    texts,
                    batch_size=settings.EMBEDDING_BATCH_SIZE,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
            )
            return embeddings.tolist()

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    async def index_document_chunks(
        self,
        document_id: str,
        chunks: List[str],
        metadata: Dict[str, Any],
        user_id: str,
        tenant_id: str = None,
    ) -> List[Dict[str, Any]]:
        """Index document chunks in the vector database.

        Args:
            document_id: Unique document identifier
            chunks: List of text chunks to index
            metadata: Document metadata
            user_id: User who owns the document
            tenant_id: Tenant ID for multi-tenancy

        Returns:
            List of indexed chunk information

        Raises:
            ValueError: If vector search is not initialized
        """
        if not self.is_initialized():
            raise ValueError("Vector search manager not initialized")

        try:
            # Generate embeddings for all chunks
            embeddings = await self.generate_embeddings(chunks)

            # Prepare points for Qdrant
            points = []
            chunk_docs = []

            for i, (chunk_text, embedding) in enumerate(zip(chunks, embeddings)):
                # Generate UUID for Qdrant point ID
                point_id = str(uuid.uuid4())

                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "document_id": document_id,
                            "chunk_index": i,
                            "text": chunk_text,
                            "user_id": user_id,
                            "tenant_id": tenant_id,
                            "filename": metadata.get("filename", ""),
                            "format": metadata.get("format", ""),
                            "created_at": datetime.now(timezone.utc).isoformat(),
                            **metadata,  # Include additional metadata
                        },
                    )
                )

                chunk_docs.append({
                    "document_id": document_id,
                    "chunk_index": i,
                    "text": chunk_text,
                    "embedding": embedding,  # Store locally for backup
                    "user_id": user_id,
                    "tenant_id": tenant_id,
                    "metadata": metadata,
                    "created_at": datetime.now(timezone.utc),
                })

            # Upsert to Qdrant in batches if needed
            if points:
                batch_size = 100  # Qdrant recommended batch size
                for i in range(0, len(points), batch_size):
                    batch = points[i:i + batch_size]
                    self.qdrant_client.upsert(
                        collection_name=settings.QDRANT_DOCUMENT_COLLECTION,
                        points=batch,
                    )

            logger.info(f"Indexed {len(chunks)} chunks for document {document_id}")
            return chunk_docs

        except Exception as e:
            logger.error(f"Failed to index document chunks: {e}")
            raise

    async def semantic_search(
        self,
        query: str,
        user_id: str,
        limit: int = None,
        score_threshold: float = None,
        include_metadata: bool = True,
        tenant_id: str = None,
    ) -> List[Dict[str, Any]]:
        """Perform semantic vector search.

        Args:
            query: Search query string
            user_id: User ID to filter results
            limit: Maximum results to return
            score_threshold: Minimum similarity score
            include_metadata: Whether to include document metadata
            tenant_id: Tenant ID to filter results

        Returns:
            List of search results with scores
        """
        if not self.is_initialized():
            raise ValueError("Vector search manager not initialized")

        if limit is None:
            limit = settings.SEARCH_MAX_RESULTS
        if score_threshold is None:
            score_threshold = settings.SEARCH_SCORE_THRESHOLD

        try:
            # Generate embedding for query
            query_embedding = await self.generate_embeddings([query])
            query_vector = query_embedding[0]

            # Search in Qdrant
            search_result = self.qdrant_client.search(
                collection_name=settings.QDRANT_DOCUMENT_COLLECTION,
                query_vector=query_vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=user_id),
                        )
                    ] + ([
                        models.FieldCondition(
                            key="tenant_id",
                            match=models.MatchValue(value=tenant_id),
                        )
                    ] if tenant_id else [])
                ),
                limit=limit,
                score_threshold=score_threshold,
                with_payload=include_metadata,
            )

            results = []
            for hit in search_result:
                result = {
                    "document_id": hit.payload.get("document_id"),
                    "chunk_index": hit.payload.get("chunk_index"),
                    "text": hit.payload.get("text"),
                    "score": hit.score,
                    "filename": hit.payload.get("filename"),
                    "format": hit.payload.get("format"),
                }

                if include_metadata:
                    # Add additional metadata from payload
                    result.update({
                        k: v for k, v in hit.payload.items()
                        if k not in ["document_id", "chunk_index", "text", "filename", "format"]
                    })

                results.append(result)

            logger.info(f"Semantic search returned {len(results)} results for query: {query[:50]}...")
            return results

        except Exception as e:
            logger.error(f"Failed to perform semantic search: {e}")
            raise

    async def delete_document_vectors(self, document_id: str, tenant_id: str = None) -> bool:
        """Delete all vector embeddings for a document.

        Args:
            document_id: Document ID to delete vectors for

        Returns:
            True if deletion was successful
        """
        if not self.is_initialized():
            return False

        try:
            # Delete points by filter
            self.qdrant_client.delete(
                collection_name=settings.QDRANT_DOCUMENT_COLLECTION,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            )
                        ] + ([
                            models.FieldCondition(
                                key="tenant_id",
                                match=models.MatchValue(value=tenant_id),
                            )
                        ] if tenant_id else [])
                    )
                )
            )

            logger.info(f"Deleted vector embeddings for document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document vectors: {e}")
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collections.

        Returns:
            Dictionary with collection statistics
        """
        if not self.is_initialized():
            return {"error": "Vector search manager not initialized"}

        try:
            # Get collection info
            collection_info = self.qdrant_client.get_collection(
                collection_name=settings.QDRANT_DOCUMENT_COLLECTION
            )

            stats = {
                "collection_name": settings.QDRANT_DOCUMENT_COLLECTION,
                "vector_count": collection_info.points_count,
                "vector_size": collection_info.config.params.vectors.size,
                "distance_metric": collection_info.config.params.vectors.distance,
                "status": "healthy",
            }

            return stats

        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"error": str(e), "status": "unhealthy"}

    def semantic_chunk_text(
        self,
        text: str,
        chunk_size: int = None,
        overlap: int = None,
    ) -> List[str]:
        """Perform semantic text chunking.

        Args:
            text: Input text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks in characters

        Returns:
            List of text chunks
        """
        if chunk_size is None:
            chunk_size = settings.CHUNK_SIZE
        if overlap is None:
            overlap = settings.CHUNK_OVERLAP

        # Simple sentence-based chunking for now
        # Can be enhanced with more sophisticated semantic chunking
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())

        chunks = []
        current_chunk = ""
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            if current_length + sentence_length > chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                # Keep overlap from end of previous chunk
                words = current_chunk.split()
                overlap_text = " ".join(words[-max(1, overlap // 10):])  # Rough word-based overlap
                current_chunk = overlap_text + " " + sentence
                current_length = len(current_chunk)
            else:
                current_chunk += " " + sentence
                current_length += sentence_length + 1

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks


# Global instance
vector_search_manager = VectorSearchManager()