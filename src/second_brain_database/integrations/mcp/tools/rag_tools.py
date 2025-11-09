"""
RAG (Retrieval Augmented Generation) MCP Tools

MCP tools for intelligent document querying, chat, and analysis using
RAG with Ollama LLMs and hybrid vector search.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ....config import settings
from ....managers.logging_manager import get_logger
from ....tools.rag_tools import (
    chat_with_documents_tool,
    compare_documents_tool,
    query_documents_tool,
    summarize_document_tool,
)
from ..modern_server import mcp
from ..security import authenticated_tool, get_mcp_user_context

logger = get_logger(prefix="[MCP_RAGTools]")


# Pydantic models for MCP tool parameters
class QueryDocumentsRequest(BaseModel):
    """Request model for document querying."""

    query: str = Field(..., description="Your question or search query")
    document_id: Optional[str] = Field(None, description="Optional specific document ID")
    top_k: int = Field(5, description="Number of relevant chunks to retrieve (1-20)")
    use_llm: bool = Field(True, description="Generate AI answer using LLM")


class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatWithDocumentsRequest(BaseModel):
    """Request model for document chat."""

    messages: List[ChatMessage] = Field(..., description="Conversation history")
    document_id: Optional[str] = Field(None, description="Optional specific document ID")


class SummarizeDocumentRequest(BaseModel):
    """Request model for document summarization."""

    document_id: str = Field(..., description="Document ID to analyze")
    analysis_type: str = Field(
        "summary",
        description="Type of analysis: 'summary', 'insights', or 'key_points'",
    )


class CompareDocumentsRequest(BaseModel):
    """Request model for document comparison."""

    document_id_1: str = Field(..., description="First document ID")
    document_id_2: str = Field(..., description="Second document ID")


# RAG Tools Registration
@authenticated_tool(mcp)
async def query_documents(
    query: str,
    document_id: Optional[str] = None,
    top_k: int = 5,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Search documents semantically and get AI-generated answers.

    Searches your documents using hybrid vector search (dense + sparse)
    and optionally generates an AI answer using Ollama LLM based on
    the most relevant content chunks.

    Args:
        query: Your question or search query
        document_id: Optional specific document ID to search within
        top_k: Number of relevant chunks to retrieve (1-20)
        use_llm: Generate AI answer using LLM (default: true)

    Returns:
        Query results with answer, relevant chunks, and sources

    Example:
        Query: "What are the main findings about climate change?"
        Response includes AI-generated answer and source citations
    """
    try:
        # Get authenticated user context
        user_context = await get_mcp_user_context()
        user_id = user_context.get("user_id")

        if not user_id:
            return {
                "status": "error",
                "error": "Authentication required",
            }

        result = await query_documents_tool(
            query=query,
            user_id=user_id,
            document_id=document_id,
            top_k=top_k,
            use_llm=use_llm,
        )

        logger.info(
            f"Query executed: {len(result.get('sources', []))} sources found",
            extra={"user_id": user_id, "query": query[:100]}
        )

        return result

    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }


@authenticated_tool(mcp)
async def chat_with_documents(
    messages: List[Dict[str, str]],
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Multi-turn conversational chat with your documents.

    Have a conversation with your documents where each message has context
    from relevant document content. Maintains conversation history and
    uses hybrid search for optimal context retrieval.

    Args:
        messages: Conversation history as list of {role, content} dicts
                 Role should be 'user' or 'assistant'
        document_id: Optional specific document ID for context

    Returns:
        Chat response with answer and source citations

    Example:
        Messages: [
            {"role": "user", "content": "What does the report say about sales?"},
            {"role": "assistant", "content": "The report shows 20% growth..."},
            {"role": "user", "content": "What regions drove that growth?"}
        ]
    """
    try:
        # Get authenticated user context
        user_context = await get_mcp_user_context()
        user_id = user_context.get("user_id")

        if not user_id:
            return {
                "status": "error",
                "error": "Authentication required",
            }

        result = await chat_with_documents_tool(
            messages=messages,
            user_id=user_id,
            document_id=document_id,
        )

        logger.info(
            f"Chat completed: {len(messages)} messages",
            extra={"user_id": user_id, "message_count": len(messages)}
        )

        return result

    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }


@authenticated_tool(mcp)
async def summarize_document(
    document_id: str,
    analysis_type: str = "summary",
) -> Dict[str, Any]:
    """Summarize or analyze a document using AI.

    Generates intelligent summaries, key insights, or bullet-point takeaways
    from your documents using Ollama LLMs.

    Args:
        document_id: Document ID to analyze
        analysis_type: Type of analysis - 'summary', 'insights', or 'key_points'

    Returns:
        Analysis result with AI-generated content

    Example:
        For analysis_type='summary': Comprehensive paragraph summary
        For analysis_type='insights': Key findings and actionable insights
        For analysis_type='key_points': Bulleted list of main points
    """
    try:
        # Get authenticated user context
        user_context = await get_mcp_user_context()
        user_id = user_context.get("user_id")

        if not user_id:
            return {
                "status": "error",
                "error": "Authentication required",
            }

        result = await summarize_document_tool(
            document_id=document_id,
            user_id=user_id,
            analysis_type=analysis_type,
        )

        logger.info(
            f"Document analysis completed: {analysis_type}",
            extra={"user_id": user_id, "document_id": document_id}
        )

        return result

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }


@authenticated_tool(mcp)
async def compare_documents(
    document_id_1: str,
    document_id_2: str,
) -> Dict[str, Any]:
    """Compare two documents using AI analysis.

    Uses Ollama LLM to identify similarities, differences, and unique aspects
    of two documents.

    Args:
        document_id_1: First document ID
        document_id_2: Second document ID

    Returns:
        Comparison analysis with similarities, differences, and assessment

    Example:
        Compares two research papers, contracts, or reports and highlights
        key similarities, differences, and unique aspects of each.
    """
    try:
        # Get authenticated user context
        user_context = await get_mcp_user_context()
        user_id = user_context.get("user_id")

        if not user_id:
            return {
                "status": "error",
                "error": "Authentication required",
            }

        result = await compare_documents_tool(
            document_id_1=document_id_1,
            document_id_2=document_id_2,
            user_id=user_id,
        )

        logger.info(
            f"Document comparison completed",
            extra={"user_id": user_id}
        )

        return result

    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }


logger.info("RAG MCP tools registered successfully")
