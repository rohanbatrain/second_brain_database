"""Integration tests for VectorRAG functionality.

Tests vector knowledge base integration including:
- Query with existing vector knowledge base
- Context retrieval from Qdrant
- Response generation with citations
- Fallback to general response on vector search failure
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from second_brain_database.chat.models.chat_models import ChatSessionType
from second_brain_database.chat.models.request_models import (
    ChatMessageCreate,
    ChatSessionCreate,
)
from second_brain_database.chat.services.chat_service import ChatService


@pytest.fixture
async def test_db():
    """Create test database connection."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_chat_vector_rag"]
    
    # Clean up collections before test
    await db.chat_sessions.delete_many({})
    await db.chat_messages.delete_many({})
    await db.token_usage.delete_many({})
    
    yield db
    
    # Clean up after test
    await db.chat_sessions.delete_many({})
    await db.chat_messages.delete_many({})
    await db.token_usage.delete_many({})
    client.close()


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    redis_mock.delete = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_ollama_llm():
    """Mock Ollama LLM for testing."""
    llm_mock = Mock()
    
    # Mock streaming response with citations
    async def mock_astream(*args, **kwargs):
        """Mock streaming tokens with citation."""
        tokens = [
            "Based", " ", "on", " ", "the", " ", "documents", ",", " ",
            "the", " ", "answer", " ", "is", ":", " ",
            "Test", " ", "content", ".", " ",
            "[Source:", " ", "test.pdf", "]"
        ]
        for token in tokens:
            yield {"content": token}
    
    llm_mock.astream = mock_astream
    return llm_mock


@pytest.fixture
def mock_vector_service():
    """Mock vector knowledge base service with realistic responses."""
    service_mock = AsyncMock()
    
    # Mock successful vector search
    service_mock.query_vector_kb = AsyncMock(return_value=[
        {
            "content": "Python is a high-level programming language.",
            "metadata": {"source": "python_intro.pdf", "page": 1},
            "score": 0.95
        },
        {
            "content": "Python was created by Guido van Rossum.",
            "metadata": {"source": "python_history.pdf", "page": 3},
            "score": 0.89
        },
        {
            "content": "Python is widely used for data science and machine learning.",
            "metadata": {"source": "python_applications.pdf", "page": 5},
            "score": 0.87
        }
    ])
    
    return service_mock


class TestVectorRAGIntegration:
    """Integration tests for VectorRAG functionality."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_query_with_vector_knowledge_base(
        self, test_db, mock_redis, mock_ollama_llm, mock_vector_service
    ):
        """Test query with existing vector knowledge base."""
        user_id = str(uuid.uuid4())
        kb_id = "test_kb_123"
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager, \
             patch("second_brain_database.chat.graphs.vector_rag_graph.VectorKnowledgeBaseService", return_value=mock_vector_service):
            
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create vector session with knowledge base
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.VECTOR,
                title="Vector RAG Test",
                knowledge_base_ids=[kb_id]
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send query
            message_data = ChatMessageCreate(content="What is Python?")
            
            # Collect streaming response
            response_tokens = []
            async for token in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                response_tokens.append(token)
            
            # Verify response received
            assert len(response_tokens) > 0
            
            # Verify vector service was called
            mock_vector_service.query_vector_kb.assert_called()
            
            # Verify messages saved
            messages = await test_db.chat_messages.find(
                {"session_id": session.id}
            ).sort("created_at", 1).to_list(None)
            
            assert len(messages) >= 2
            
            # Verify assistant response contains content
            assistant_message = messages[1]
            assert len(assistant_message["content"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_context_retrieval_from_qdrant(
        self, test_db, mock_redis, mock_ollama_llm, mock_vector_service
    ):
        """Test that contexts are retrieved from Qdrant."""
        user_id = str(uuid.uuid4())
        kb_id = "test_kb_456"
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager, \
             patch("second_brain_database.chat.graphs.vector_rag_graph.VectorKnowledgeBaseService", return_value=mock_vector_service):
            
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create vector session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.VECTOR,
                title="Context Retrieval Test",
                knowledge_base_ids=[kb_id]
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send query
            message_data = ChatMessageCreate(content="Tell me about Python programming")
            
            # Consume streaming response
            async for _ in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                pass
            
            # Verify vector service was called with correct parameters
            mock_vector_service.query_vector_kb.assert_called()
            call_args = mock_vector_service.query_vector_kb.call_args
            
            # Verify knowledge base ID was passed
            assert kb_id in str(call_args)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_response_generation_with_citations(
        self, test_db, mock_redis, mock_ollama_llm, mock_vector_service
    ):
        """Test that response includes citations from sources."""
        user_id = str(uuid.uuid4())
        kb_id = "test_kb_789"
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager, \
             patch("second_brain_database.chat.graphs.vector_rag_graph.VectorKnowledgeBaseService", return_value=mock_vector_service):
            
            # Configure mock LLM manager with citation-aware response
            mock_manager_instance = Mock()
            
            # Mock LLM that includes citations
            citation_llm = Mock()
            async def mock_astream_with_citations(*args, **kwargs):
                tokens = [
                    "According", " ", "to", " ", "the", " ", "documents", ",", " ",
                    "Python", " ", "is", " ", "a", " ", "programming", " ", "language", ".", " ",
                    "[Source:", " ", "python_intro.pdf", "]"
                ]
                for token in tokens:
                    yield {"content": token}
            
            citation_llm.astream = mock_astream_with_citations
            mock_manager_instance.create_llm = Mock(return_value=citation_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create vector session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.VECTOR,
                title="Citation Test",
                knowledge_base_ids=[kb_id]
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send query
            message_data = ChatMessageCreate(content="What is Python?")
            
            # Consume streaming response
            async for _ in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                pass
            
            # Verify assistant message contains citation
            messages = await test_db.chat_messages.find(
                {"session_id": session.id, "role": "assistant"}
            ).to_list(None)
            
            assert len(messages) > 0
            assistant_content = messages[0]["content"]
            
            # Check for citation markers
            assert "Source" in assistant_content or "source" in assistant_content.lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fallback_to_general_response_on_vector_failure(
        self, test_db, mock_redis, mock_ollama_llm
    ):
        """Test fallback to general response when vector search fails."""
        user_id = str(uuid.uuid4())
        kb_id = "test_kb_fail"
        
        # Mock vector service that raises exception
        failing_vector_service = AsyncMock()
        failing_vector_service.query_vector_kb = AsyncMock(
            side_effect=Exception("Vector search failed")
        )
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager, \
             patch("second_brain_database.chat.graphs.vector_rag_graph.VectorKnowledgeBaseService", return_value=failing_vector_service):
            
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create vector session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.VECTOR,
                title="Fallback Test",
                knowledge_base_ids=[kb_id]
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send query
            message_data = ChatMessageCreate(content="What is Python?")
            
            # Should not raise exception - should fallback gracefully
            response_tokens = []
            try:
                async for token in chat_service.stream_chat_response(
                    session_id=session.id,
                    user_id=user_id,
                    message=message_data
                ):
                    response_tokens.append(token)
            except Exception as e:
                pytest.fail(f"Should not raise exception on vector failure: {e}")
            
            # Verify some response was generated (fallback)
            assert len(response_tokens) > 0
            
            # Verify message was saved even with fallback
            messages = await test_db.chat_messages.find(
                {"session_id": session.id}
            ).to_list(None)
            
            assert len(messages) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vector_rag_with_multiple_knowledge_bases(
        self, test_db, mock_redis, mock_ollama_llm, mock_vector_service
    ):
        """Test VectorRAG with multiple knowledge bases."""
        user_id = str(uuid.uuid4())
        kb_ids = ["kb_1", "kb_2", "kb_3"]
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager, \
             patch("second_brain_database.chat.graphs.vector_rag_graph.VectorKnowledgeBaseService", return_value=mock_vector_service):
            
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create vector session with multiple KBs
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.VECTOR,
                title="Multi-KB Test",
                knowledge_base_ids=kb_ids
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Verify session has all knowledge bases
            assert len(session.knowledge_base_ids) == 3
            assert all(kb_id in session.knowledge_base_ids for kb_id in kb_ids)
            
            # Send query
            message_data = ChatMessageCreate(content="Search across all knowledge bases")
            
            # Consume streaming response
            async for _ in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                pass
            
            # Verify vector service was called
            mock_vector_service.query_vector_kb.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_vector_rag_empty_results(
        self, test_db, mock_redis, mock_ollama_llm
    ):
        """Test VectorRAG behavior when no relevant documents found."""
        user_id = str(uuid.uuid4())
        kb_id = "test_kb_empty"
        
        # Mock vector service that returns empty results
        empty_vector_service = AsyncMock()
        empty_vector_service.query_vector_kb = AsyncMock(return_value=[])
        
        with patch("second_brain_database.chat.services.chat_service.OllamaLLMManager") as mock_llm_manager, \
             patch("second_brain_database.chat.graphs.vector_rag_graph.VectorKnowledgeBaseService", return_value=empty_vector_service):
            
            # Configure mock LLM manager
            mock_manager_instance = Mock()
            mock_manager_instance.create_llm = Mock(return_value=mock_ollama_llm)
            mock_manager_instance.count_tokens = Mock(return_value=10)
            mock_manager_instance.estimate_cost = Mock(return_value=0.0)
            mock_llm_manager.return_value = mock_manager_instance
            
            # Create chat service
            chat_service = ChatService(db=test_db, redis_client=mock_redis)
            
            # Create vector session
            session_data = ChatSessionCreate(
                session_type=ChatSessionType.VECTOR,
                title="Empty Results Test",
                knowledge_base_ids=[kb_id]
            )
            session = await chat_service.create_session(user_id=user_id, session_data=session_data)
            
            # Send query
            message_data = ChatMessageCreate(content="Query with no results")
            
            # Should handle gracefully
            response_tokens = []
            async for token in chat_service.stream_chat_response(
                session_id=session.id,
                user_id=user_id,
                message=message_data
            ):
                response_tokens.append(token)
            
            # Verify response generated (fallback or "no results" message)
            assert len(response_tokens) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
