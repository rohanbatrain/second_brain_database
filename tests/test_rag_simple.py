#!/usr/bin/env python3
"""
Simple RAG Service Tests.

Basic tests for the RAG service functionality without complex mocking.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from second_brain_database.services.rag_service import RAGService, rag_service


class TestRAGServiceSimple:
    """Simple test cases for RAG service functionality."""

    def test_rag_service_initialization(self):
        """Test RAG service initialization."""
        rag = RAGService()
        assert rag.top_k == 5
        assert rag.similarity_threshold == 0.7
        assert rag.max_context_length == 8000

    def test_global_rag_service_instance(self):
        """Test that global rag_service instance exists."""
        assert isinstance(rag_service, RAGService)
        assert rag_service.top_k == 5
        assert rag_service.similarity_threshold == 0.7

    def test_build_context_method(self):
        """Test _build_context method."""
        rag = RAGService()

        chunks = [
            {"text": "Climate change is a major issue.", "score": 0.9, "metadata": {}},
            {"text": "Global warming affects weather patterns.", "score": 0.8, "metadata": {}},
            {"text": "Renewable energy is a solution.", "score": 0.7, "metadata": {}},
        ]

        context = rag._build_context(chunks)

        # Verify context format
        assert "[Source 1, Relevance: 0.90]" in context
        assert "[Source 2, Relevance: 0.80]" in context
        assert "[Source 3, Relevance: 0.70]" in context
        assert "Climate change is a major issue." in context
        assert "Global warming affects weather patterns." in context
        assert "Renewable energy is a solution." in context

    def test_build_context_empty_chunks(self):
        """Test _build_context with empty chunks."""
        rag = RAGService()
        context = rag._build_context([])
        assert context == ""

    def test_build_context_length_limit(self):
        """Test _build_context respects max context length."""
        rag = RAGService()

        # Create a chunk that would exceed max length
        long_text = "x" * 4000
        chunks = [
            {"text": long_text, "score": 0.9, "metadata": {}},
            {"text": "Short chunk that should not be included", "score": 0.8, "metadata": {}},
        ]

        # Set a smaller max length to force truncation - account for formatting overhead (~60 chars)
        rag.max_context_length = 4050  # Just enough for first chunk + formatting, not enough for both

        context = rag._build_context(chunks)

        # Verify context is truncated appropriately
        # Should have first chunk but not the second
        assert "Source 1" in context
        assert "Source 2" not in context
        assert len(context) <= rag.max_context_length

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    async def test_query_document_error_handling(self, mock_vector_search):
        """Test query_document error handling."""
        rag = RAGService()

        # Test with invalid parameters - should raise specific error
        with pytest.raises(Exception, match="Vector search manager not initialized"):
            await rag.query_document(query="", user_id="user_789")  # Empty query to trigger error

    @patch("second_brain_database.services.rag_service.ollama_manager")
    async def test_generate_answer_error_handling(self, mock_ollama):
        """Test error handling in _generate_answer."""
        rag = RAGService()

        # Setup mock to raise exception
        mock_ollama.generate.side_effect = Exception("LLM generation failed")

        # Execute generation and expect error
        with pytest.raises(Exception, match="LLM generation failed"):
            await rag._generate_answer(query="Test query", context="Test context")

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    @patch("second_brain_database.services.rag_service.ollama_manager")
    @patch("second_brain_database.managers.llamaindex_vector_manager.llamaindex_vector_manager")
    async def test_query_document_basic_flow(self, mock_llamaindex, mock_ollama, mock_vector_search):
        """Test basic query_document flow with mocked dependencies."""
        rag = RAGService()

        # Setup mocks for both vector search paths
        mock_search_results = [
            {
                "text": "Climate change causes rising temperatures.",
                "score": 0.85,
                "metadata": {"document_id": "doc_123", "filename": "climate_report.pdf"},
            }
        ]

        # Mock both vector search managers - make sure async methods return awaitable values
        mock_vector_search.semantic_search.return_value = mock_search_results
        mock_llamaindex.search = AsyncMock(return_value=mock_search_results)
        mock_ollama.generate = AsyncMock(
            return_value="Climate change is causing significant temperature increases globally."
        )

        # Execute query
        result = await rag.query_document(query="What causes rising temperatures?", user_id="user_123", use_llm=True)

        # Verify result structure
        assert result["query"] == "What causes rising temperatures?"
        assert result["answer"] == "Climate change is causing significant temperature increases globally."
        assert len(result["chunks"]) == 1
        assert len(result["sources"]) == 1
        assert result["sources"][0]["document_id"] == "doc_123"
        assert result["chunk_count"] == 1
        assert "timestamp" in result

        # Verify mocks were called (service should use LlamaIndex path by default)
        mock_llamaindex.search.assert_called_once()
        mock_ollama.generate.assert_called_once()

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    @patch("second_brain_database.managers.llamaindex_vector_manager.llamaindex_vector_manager")
    async def test_query_document_without_llm(self, mock_llamaindex, mock_vector_search):
        """Test query_document without LLM generation."""
        rag = RAGService()

        # Setup mocks
        mock_search_results = [
            {
                "text": "Solar energy is renewable.",
                "score": 0.75,
                "metadata": {"document_id": "doc_456", "filename": "energy_report.pdf"},
            }
        ]
        mock_vector_search.semantic_search.return_value = mock_search_results
        mock_llamaindex.search = AsyncMock(return_value=mock_search_results)

        # Execute query without LLM
        result = await rag.query_document(query="What is solar energy?", user_id="user_123", use_llm=False)

        # Verify result structure
        assert result["query"] == "What is solar energy?"
        assert result["answer"] is None  # No LLM generation
        assert len(result["chunks"]) == 1
        assert len(result["sources"]) == 1
        assert result["chunk_count"] == 1

        # Verify vector search was called but not ollama (LlamaIndex path)
        mock_llamaindex.search.assert_called_once()

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    @patch("second_brain_database.managers.llamaindex_vector_manager.llamaindex_vector_manager")
    async def test_query_document_low_similarity_filter(self, mock_llamaindex, mock_vector_search):
        """Test that chunks below similarity threshold are filtered out."""
        rag = RAGService()

        # Setup mocks with low similarity scores
        mock_search_results = [
            {
                "text": "Irrelevant chunk",
                "score": 0.3,  # Below threshold
                "metadata": {"document_id": "doc_123", "filename": "test.pdf"},
            },
            {
                "text": "Relevant chunk",
                "score": 0.8,  # Above threshold
                "metadata": {"document_id": "doc_456", "filename": "relevant.pdf"},
            },
        ]
        mock_vector_search.semantic_search.return_value = mock_search_results
        mock_llamaindex.search = AsyncMock(return_value=mock_search_results)

        # Execute query
        result = await rag.query_document(query="Test query", user_id="user_123", use_llm=False)

        # Verify only high-similarity chunks are included
        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["score"] == 0.8
        assert result["sources"][0]["document_id"] == "doc_456"

    def test_rag_service_attributes(self):
        """Test RAG service has expected attributes."""
        rag = RAGService()

        # Test default values
        assert hasattr(rag, "top_k")
        assert hasattr(rag, "similarity_threshold")
        assert hasattr(rag, "max_context_length")

        # Test methods exist
        assert hasattr(rag, "query_document")
        assert hasattr(rag, "chat_with_documents")
        assert hasattr(rag, "analyze_document_with_llm")
        assert hasattr(rag, "_build_context")
        assert hasattr(rag, "_generate_answer")

    def test_rag_service_constants_are_reasonable(self):
        """Test that RAG service constants have reasonable values."""
        rag = RAGService()

        # Test reasonable ranges
        assert 1 <= rag.top_k <= 20
        assert 0.0 <= rag.similarity_threshold <= 1.0
        assert rag.max_context_length > 1000  # Should be large enough for meaningful context


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
