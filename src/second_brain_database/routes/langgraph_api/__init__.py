"""LangGraph API compatibility layer for Second Brain Database.

This module provides LangGraph Cloud API-compatible endpoints that adapt
the existing ChatService to work with the @langchain/langgraph-sdk frontend.
"""

from .routes import router

__all__ = ["router"]
