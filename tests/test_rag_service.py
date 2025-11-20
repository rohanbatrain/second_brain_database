#!/usr/bin/env python3
"""
Tests for RAG (Retrieval Augmented Generation) Service.

Tests the RAG service functionality including document querying,
chat with documents, and document analysis using mocked dependencies.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from second_brain_database.services.rag_service import RAGService, rag_service


class TestRAGService:
    """Test cases for RAG service functionality."""

    @pytest.fixture
    def rag_service_instance(self):
        """Create a fresh RAG service instance for testing."""
        return RAGService()

    @pytest.fixture
    def mock_search_results(self):
        """Mock vector search results."""
        return [
            {
                "text": "This is a test document chunk about climate change.",
                "score": 0.85,
                "metadata": {
                    "document_id": "doc_123",
                    "filename": "climate_report.pdf",
                    "chunk_index": 0,
                },
            },
            {
                "text": "Another chunk discussing environmental impacts.",
                "score": 0.72,
                "metadata": {
                    "document_id": "doc_123",
                    "filename": "climate_report.pdf",
                    "chunk_index": 1,
                },
            },
        ]

    @pytest.fixture
    def mock_ollama_response(self):
        """Mock Ollama LLM response."""
        return "Based on the provided context, climate change is causing significant environmental impacts including rising temperatures and extreme weather events."

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    @patch("second_brain_database.services.rag_service.ollama_manager")
    async def test_query_document_with_llm(
        self, mock_ollama, mock_vector_search, rag_service_instance, mock_search_results, mock_ollama_response
    ):
        """Test query_document with LLM generation enabled."""
        # Setup mocks
        mock_vector_search.semantic_search.return_value = mock_search_results
        mock_ollama.generate.return_value = mock_ollama_response

        # Execute query
        result = await rag_service_instance.query_document(
            query="What are the effects of climate change?", user_id="user_123", use_llm=True
        )

        # Verify vector search was called
        mock_vector_search.semantic_search.assert_called_once()
        call_args = mock_vector_search.semantic_search.call_args
        assert call_args[1]["query_text"] == "What are the effects of climate change?"
        assert call_args[1]["limit"] == 5
        assert call_args[1]["filter_dict"] == {"user_id": "user_123"}

        # Verify LLM was called
        mock_ollama.generate.assert_called_once()
        llm_call_args = mock_ollama.generate.call_args
        assert "climate change" in llm_call_args[1]["prompt"].lower()
        assert "Question: What are the effects of climate change?" in llm_call_args[1]["prompt"]

        # Verify result structure
        assert result["query"] == "What are the effects of climate change?"
        assert result["answer"] == mock_ollama_response
        assert len(result["chunks"]) == 2
        assert len(result["sources"]) == 1
        assert result["sources"][0]["document_id"] == "doc_123"
        assert result["sources"][0]["filename"] == "climate_report.pdf"
        assert result["chunk_count"] == 2
        assert "timestamp" in result

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    async def test_query_document_without_llm(self, mock_vector_search, rag_service_instance, mock_search_results):
        """Test query_document with LLM generation disabled."""
        # Setup mocks
        mock_vector_search.semantic_search.return_value = mock_search_results

        # Execute query
        result = await rag_service_instance.query_document(
            query="What are the effects of climate change?", user_id="user_123", use_llm=False
        )

        # Verify vector search was called
        mock_vector_search.semantic_search.assert_called_once()

        # Verify no LLM call
        # (ollama_manager.generate should not be called)

        # Verify result structure
        assert result["query"] == "What are the effects of climate change?"
        assert result["answer"] is None
        assert len(result["chunks"]) == 2
        assert len(result["sources"]) == 1
        assert result["chunk_count"] == 2

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    async def test_query_document_with_document_filter(
        self, mock_vector_search, rag_service_instance, mock_search_results
    ):
        """Test query_document with specific document ID filter."""
        # Setup mocks
        mock_vector_search.semantic_search.return_value = mock_search_results

        # Execute query
        result = await rag_service_instance.query_document(
            query="What are the effects of climate change?", document_id="doc_123", user_id="user_123", use_llm=False
        )

        # Verify vector search was called with document filter
        mock_vector_search.semantic_search.assert_called_once()
        call_args = mock_vector_search.search.call_args
        assert call_args[1]["filter_dict"] == {"document_id": "doc_123", "user_id": "user_123"}

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    async def test_query_document_with_low_similarity_filter(self, mock_vector_search, rag_service_instance):
        """Test that chunks below similarity threshold are filtered out."""
        # Setup mocks with low similarity scores
        low_similarity_results = [
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
        mock_vector_search.semantic_search.return_value = low_similarity_results

        # Execute query
        result = await rag_service_instance.query_document(query="Test query", user_id="user_123", use_llm=False)

        # Verify only high-similarity chunks are included
        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["score"] == 0.8
        assert result["sources"][0]["document_id"] == "doc_456"

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    @patch("second_brain_database.services.rag_service.ollama_manager")
    async def test_chat_with_documents(
        self, mock_ollama, mock_vector_search, rag_service_instance, mock_search_results
    ):
        """Test chat_with_documents functionality."""
        # Setup mocks
        mock_vector_search.semantic_search.return_value = mock_search_results
        mock_ollama.chat.return_value = "The documents show that climate change is a significant concern."

        # Execute chat
        messages = [{"role": "user", "content": "What do the documents say about climate change?"}]
        result = await rag_service_instance.chat_with_documents(messages=messages, user_id="user_123", stream=False)

        # Verify vector search was called
        mock_vector_search.semantic_search.assert_called_once()

        # Verify chat was called with proper context
        mock_ollama.chat.assert_called_once()
        chat_call_args = mock_ollama.chat.call_args
        assert len(chat_call_args[1]["messages"]) >= 2  # System message + user message
        assert "climate change" in chat_call_args[1]["messages"][0]["content"].lower()  # Context in system message

        # Verify result structure
        assert "response" in result
        assert "sources" in result
        assert "chunk_count" in result
        assert "timestamp" in result

    @patch("second_brain_database.services.rag_service.db_manager")
    @patch("second_brain_database.services.rag_service.ollama_manager")
    async def test_analyze_document_with_llm(self, mock_ollama, mock_db, rag_service_instance):
        """Test analyze_document_with_llm functionality."""
        # Setup mocks
        mock_doc = {
            "_id": "doc_123",
            "content": "This is a test document about artificial intelligence and machine learning.",
            "filename": "ai_report.pdf",
        }
        mock_db.get_collection.return_value.find_one.return_value = mock_doc
        mock_ollama.generate.return_value = "This document discusses AI and ML technologies."

        # Execute analysis
        result = await rag_service_instance.analyze_document_with_llm(document_id="doc_123", analysis_type="summary")

        # Verify database was queried
        mock_db.get_collection.assert_called_once_with("documents")
        mock_db.get_collection.return_value.find_one.assert_called_once_with({"_id": "doc_123"})

        # Verify LLM was called
        mock_ollama.generate.assert_called_once()
        llm_call_args = mock_ollama.generate.call_args
        assert "artificial intelligence" in llm_call_args[1]["prompt"]
        assert "summary" in llm_call_args[1]["prompt"]

        # Verify result structure
        assert result["document_id"] == "doc_123"
        assert result["analysis_type"] == "summary"
        assert result["analysis"] == "This document discusses AI and ML technologies."
        assert "timestamp" in result

    @patch("second_brain_database.services.rag_service.db_manager")
    async def test_analyze_document_not_found(self, mock_db, rag_service_instance):
        """Test analyze_document_with_llm when document doesn't exist."""
        # Setup mocks
        mock_db.get_collection.return_value.find_one.return_value = None

        # Execute analysis and expect error
        with pytest.raises(ValueError, match="Document doc_123 not found"):
            await rag_service_instance.analyze_document_with_llm(document_id="doc_123", analysis_type="summary")

    async def test_build_context(self, rag_service_instance):
        """Test _build_context method."""
        chunks = [
            {"text": "Chunk 1", "score": 0.9, "metadata": {}},
            {"text": "Chunk 2", "score": 0.8, "metadata": {}},
            {"text": "Chunk 3", "score": 0.7, "metadata": {}},
        ]

        context = rag_service_instance._build_context(chunks)

        # Verify context format
        assert "[Source 1, Relevance: 0.90]" in context
        assert "[Source 2, Relevance: 0.80]" in context
        assert "[Source 3, Relevance: 0.70]" in context
        assert "Chunk 1" in context
        assert "Chunk 2" in context
        assert "Chunk 3" in context

    async def test_build_context_length_limit(self, rag_service_instance):
        """Test _build_context respects max context length."""
        # Create chunks that would exceed max length
        long_text = "x" * 4000
        chunks = [
            {"text": long_text, "score": 0.9, "metadata": {}},
            {"text": "Short chunk", "score": 0.8, "metadata": {}},
        ]

        # Set max length to force truncation
        rag_service_instance.max_context_length = 5000

        context = rag_service_instance._build_context(chunks)

        # Verify context is truncated appropriately
        assert len(context) <= rag_service_instance.max_context_length + 1000  # Allow some buffer

    @patch("second_brain_database.services.rag_service.vector_search_manager")
    async def test_query_document_error_handling(self, mock_vector_search, rag_service_instance):
        """Test error handling in query_document."""
        # Setup mock to raise exception
        mock_vector_search.search.side_effect = Exception("Vector search failed")

        # Execute query and expect error
        with pytest.raises(Exception, match="Vector search failed"):
            await rag_service_instance.query_document(query="Test query", user_id="user_123")

    @patch("second_brain_database.services.rag_service.ollama_manager")
    async def test_generate_answer_error_handling(self, mock_ollama, rag_service_instance):
        """Test error handling in _generate_answer."""
        # Setup mock to raise exception
        mock_ollama.generate.side_effect = Exception("LLM generation failed")

        # Execute generation and expect error
        with pytest.raises(Exception, match="LLM generation failed"):
            await rag_service_instance._generate_answer(query="Test query", context="Test context")

    async def test_service_initialization(self, rag_service_instance):
        """Test RAG service initialization."""
        assert rag_service_instance.top_k == 5
        assert rag_service_instance.similarity_threshold == 0.7
        assert rag_service_instance.max_context_length == 8000

    async def test_global_instance(self):
        """Test that global rag_service instance exists."""
        assert isinstance(rag_service, RAGService)
        assert rag_service.top_k == 5
        assert rag_service.similarity_threshold == 0.7


class TestRAGToolsIntegration:
    """Integration tests for RAG MCP tools."""

    @patch("second_brain_database.tools.rag_tools.document_service")
    async def test_query_documents_tool_success(self, mock_document_service):
        """Test query_documents_tool success case."""
        from second_brain_database.tools.rag_tools import query_documents_tool

        # Setup mock
        mock_result = {
            "answer": "Test answer",
            "sources": [{"document_id": "doc_123", "filename": "test.pdf"}],
            "chunk_count": 2,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        mock_document_service.query_document.return_value = mock_result

        # Execute tool
        result = await query_documents_tool(query="Test query", user_id="user_123")

        # Verify result
        assert result["status"] == "success"
        assert result["query"] == "Test query"
        assert result["answer"] == "Test answer"
        assert len(result["sources"]) == 1

    @patch("second_brain_database.tools.rag_tools.document_service")
    async def test_query_documents_tool_error(self, mock_document_service):
        """Test query_documents_tool error handling."""
        from second_brain_database.tools.rag_tools import query_documents_tool

        # Setup mock to raise exception
        mock_document_service.query_document.side_effect = Exception("Query failed")

        # Execute tool
        result = await query_documents_tool(query="Test query", user_id="user_123")

        # Verify error result
        assert result["status"] == "error"
        assert "Query failed" in result["error"]

    @patch("second_brain_database.tools.rag_tools.document_service")
    async def test_chat_with_documents_tool_success(self, mock_document_service):
        """Test chat_with_documents_tool success case."""
        from second_brain_database.tools.rag_tools import chat_with_documents_tool

        # Setup mock
        mock_result = {
            "response": "Test chat response",
            "sources": [{"document_id": "doc_123", "filename": "test.pdf"}],
            "chunk_count": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        mock_document_service.chat_with_documents.return_value = mock_result

        # Execute tool
        messages = [{"role": "user", "content": "Hello"}]
        result = await chat_with_documents_tool(messages=messages, user_id="user_123")

        # Verify result
        assert result["status"] == "success"
        assert result["response"] == "Test chat response"
        assert len(result["sources"]) == 1

    @patch("second_brain_database.tools.rag_tools.document_service")
    async def test_summarize_document_tool_success(self, mock_document_service):
        """Test summarize_document_tool success case."""
        from second_brain_database.tools.rag_tools import summarize_document_tool

        # Setup mock
        mock_result = {
            "analysis": "Test summary",
            "model": "llama3.2",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        mock_document_service.analyze_document_with_llm.return_value = mock_result

        # Execute tool
        result = await summarize_document_tool(document_id="doc_123", user_id="user_123", analysis_type="summary")

        # Verify result
        assert result["status"] == "success"
        assert result["analysis"] == "Test summary"
        assert result["analysis_type"] == "summary"

    @patch("second_brain_database.tools.rag_tools.document_service")
    async def test_compare_documents_tool_success(self, mock_document_service):
        """Test compare_documents_tool success case."""
        from second_brain_database.tools.rag_tools import compare_documents_tool

        # Setup mock
        mock_result = {
            "comparison": "Documents are similar in topic but differ in conclusions.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        mock_document_service.compare_documents_with_llm.return_value = mock_result

        # Execute tool
        result = await compare_documents_tool(document_id_1="doc_1", document_id_2="doc_2", user_id="user_123")

        # Verify result
        assert result["status"] == "success"
        assert "comparison" in result
        assert "Documents are similar" in result["comparison"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
