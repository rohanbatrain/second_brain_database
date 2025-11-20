"""MCP Tools for RAG (Retrieval Augmented Generation) Operations.

This module provides MCP tools for intelligent document querying, chat,
and analysis using RAG with Ollama LLMs.

Features:
- Semantic document search with LLM answers
- Multi-turn document chat with context
- Document summarization using LLMs
- Document analysis and comparison
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...config import settings
from ...managers.logging_manager import get_logger
from ...services.document_service import document_service

logger = get_logger(prefix="[RAGTools]")


async def query_documents_tool(
    query: str,
    user_id: str,
    document_id: Optional[str] = None,
    top_k: int = 5,
    use_llm: bool = True,
) -> Dict[str, Any]:
    """Query documents using semantic search and LLM.

    Searches your documents semantically and optionally generates an AI answer
    using the most relevant content chunks.

    Args:
        query: Your question or search query
        user_id: Your user ID for access control
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
        logger.info(
            f"RAG query: {query[:100]}...",
            extra={"user_id": user_id, "use_llm": use_llm}
        )

        result = await document_service.query_document(
            query=query,
            document_id=document_id,
            user_id=user_id,
            top_k=min(max(top_k, 1), 20),  # Clamp between 1-20
            use_llm=use_llm,
        )

        # Format response
        return {
            "status": "success",
            "query": query,
            "answer": result.get("answer"),
            "sources": [
                {
                    "document": s.get("filename", "Unknown"),
                    "document_id": s.get("document_id"),
                }
                for s in result.get("sources", [])
            ],
            "chunk_count": result.get("chunk_count", 0),
            "timestamp": result.get("timestamp"),
        }

    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "query": query,
        }


async def chat_with_documents_tool(
    messages: List[Dict[str, str]],
    user_id: str,
    document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Multi-turn chat with your documents.

    Have a conversation with your documents where each message has context
    from relevant document content. Maintains conversation history.

    Args:
        messages: Conversation history as list of {role, content} dicts
                 Role should be 'user' or 'assistant'
        user_id: Your user ID for access control
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
        logger.info(
            f"Chat with documents: {len(messages)} messages",
            extra={"user_id": user_id, "message_count": len(messages)}
        )

        result = await document_service.chat_with_documents(
            messages=messages,
            document_id=document_id,
            user_id=user_id,
            stream=False,
        )

        return {
            "status": "success",
            "response": result.get("response"),
            "sources": [
                {
                    "document": s.get("filename", "Unknown"),
                    "document_id": s.get("document_id"),
                }
                for s in result.get("sources", [])
            ],
            "chunks_used": result.get("chunk_count", 0),
            "timestamp": result.get("timestamp"),
        }

    except Exception as e:
        logger.error(f"Chat failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }


async def summarize_document_tool(
    document_id: str,
    user_id: str,
    analysis_type: str = "summary",
) -> Dict[str, Any]:
    """Summarize or analyze a document using AI.

    Generates intelligent summaries, key insights, or bullet-point takeaways
    from your documents using Ollama LLMs.

    Args:
        document_id: Document ID to analyze
        user_id: Your user ID for access control
        analysis_type: Type of analysis - 'summary', 'insights', or 'key_points'

    Returns:
        Analysis result with AI-generated content

    Example:
        For analysis_type='summary': Comprehensive paragraph summary
        For analysis_type='insights': Key findings and actionable insights
        For analysis_type='key_points': Bulleted list of main points
    """
    try:
        logger.info(
            f"Document analysis: {document_id} ({analysis_type})",
            extra={"user_id": user_id, "document_id": document_id}
        )

        result = await document_service.analyze_document_with_llm(
            document_id=document_id,
            analysis_type=analysis_type,
        )

        return {
            "status": "success",
            "document_id": document_id,
            "analysis_type": analysis_type,
            "analysis": result.get("analysis"),
            "model": result.get("model"),
            "timestamp": result.get("timestamp"),
        }

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "document_id": document_id,
        }


async def compare_documents_tool(
    document_id_1: str,
    document_id_2: str,
    user_id: str,
) -> Dict[str, Any]:
    """Compare two documents using AI analysis.

    Uses Ollama LLM to identify similarities, differences, and unique aspects
    of two documents.

    Args:
        document_id_1: First document ID
        document_id_2: Second document ID
        user_id: Your user ID for access control

    Returns:
        Comparison analysis with similarities, differences, and assessment

    Example:
        Compares two research papers, contracts, or reports and highlights
        key similarities, differences, and unique aspects of each.
    """
    try:
        logger.info(
            f"Comparing documents: {document_id_1} vs {document_id_2}",
            extra={"user_id": user_id}
        )

        result = await document_service.compare_documents_with_llm(
            document_id_1=document_id_1,
            document_id_2=document_id_2,
        )

        return {
            "status": "success",
            "document_1": result.get("document_1"),
            "document_2": result.get("document_2"),
            "comparison": result.get("analysis"),
            "timestamp": result.get("timestamp"),
        }

    except Exception as e:
        logger.error(f"Comparison failed: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
        }


# Tool metadata for MCP registration
RAG_TOOLS = [
    {
        "name": "query_documents",
        "description": "Search documents semantically and get AI-generated answers",
        "function": query_documents_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Your question or search query",
                },
                "user_id": {
                    "type": "string",
                    "description": "Your user ID for access control",
                },
                "document_id": {
                    "type": "string",
                    "description": "Optional specific document ID to search within",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of relevant chunks to retrieve (1-20)",
                    "default": 5,
                },
                "use_llm": {
                    "type": "boolean",
                    "description": "Generate AI answer using LLM",
                    "default": True,
                },
            },
            "required": ["query", "user_id"],
        },
    },
    {
        "name": "chat_with_documents",
        "description": "Multi-turn conversational chat with document context",
        "function": chat_with_documents_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "description": "Conversation history with role and content",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "enum": ["user", "assistant"]},
                            "content": {"type": "string"},
                        },
                    },
                },
                "user_id": {
                    "type": "string",
                    "description": "Your user ID for access control",
                },
                "document_id": {
                    "type": "string",
                    "description": "Optional specific document ID for context",
                },
            },
            "required": ["messages", "user_id"],
        },
    },
    {
        "name": "summarize_document",
        "description": "Generate AI summary or analysis of a document",
        "function": summarize_document_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "Document ID to analyze",
                },
                "user_id": {
                    "type": "string",
                    "description": "Your user ID for access control",
                },
                "analysis_type": {
                    "type": "string",
                    "description": "Type of analysis",
                    "enum": ["summary", "insights", "key_points"],
                    "default": "summary",
                },
            },
            "required": ["document_id", "user_id"],
        },
    },
    {
        "name": "compare_documents",
        "description": "AI-powered comparison of two documents",
        "function": compare_documents_tool,
        "parameters": {
            "type": "object",
            "properties": {
                "document_id_1": {
                    "type": "string",
                    "description": "First document ID",
                },
                "document_id_2": {
                    "type": "string",
                    "description": "Second document ID",
                },
                "user_id": {
                    "type": "string",
                    "description": "Your user ID for access control",
                },
            },
            "required": ["document_id_1", "document_id_2", "user_id"],
        },
    },
]
