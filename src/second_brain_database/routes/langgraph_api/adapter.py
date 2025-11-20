"""Adapter service to convert between ChatService and LangGraph formats.

This service bridges the existing ChatService implementation with the
LangGraph SDK expectations, converting data models and streaming formats.
"""

from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

from second_brain_database.chat.models.chat_models import ChatMessage, ChatSession
from second_brain_database.chat.services.chat_service import ChatService
from second_brain_database.managers.logging_manager import get_logger

from .models import Thread, ThreadMetadata, ThreadValues

logger = get_logger(prefix="[LangGraph Adapter]")


class LangGraphAdapter:
    """Adapter to convert ChatService data to LangGraph SDK format."""

    def __init__(self, chat_service: ChatService):
        """Initialize adapter with ChatService instance.

        Args:
            chat_service: The ChatService instance to adapt
        """
        self.chat_service = chat_service

    def session_to_thread(self, session: ChatSession) -> Thread:
        """Convert ChatSession to LangGraph Thread format.

        Args:
            session: ChatSession to convert

        Returns:
            Thread in LangGraph SDK format
        """
        metadata = ThreadMetadata(
            user_id=session.user_id,
            session_type=session.session_type,
            graph_id=session.session_type.lower()
            if session.session_type
            else "general",
        )

        return Thread(
            thread_id=str(session.session_id),
            created_at=session.created_at,
            updated_at=session.updated_at,
            metadata=metadata,
        )

    def message_to_langgraph_format(self, message: ChatMessage) -> Dict[str, Any]:
        """Convert ChatMessage to LangGraph message format.

        Args:
            message: ChatMessage to convert

        Returns:
            Message in LangGraph format
        """
        # Map role to LangGraph message types
        role_map = {
            "user": "human",
            "assistant": "ai",
            "system": "system",
        }

        return {
            "id": str(message.message_id),
            "type": role_map.get(message.role, message.role),
            "content": message.content,
            "created_at": message.created_at.isoformat() if message.created_at else None,
        }

    async def get_thread_values(self, session_id: str) -> ThreadValues:
        """Get current thread state values.

        Args:
            session_id: Session/thread ID

        Returns:
            ThreadValues with current messages
        """
        messages = await self.chat_service.get_messages(session_id, skip=0, limit=100)
        langgraph_messages = [
            self.message_to_langgraph_format(msg) for msg in messages
        ]

        return ThreadValues(messages=langgraph_messages)

    async def stream_event_to_langgraph_format(
        self, event_type: str, data: Any
    ) -> Dict[str, Any]:
        """Convert ChatService stream event to LangGraph streaming format.

        Args:
            event_type: Type of event (token, error, done, etc.)
            data: Event data

        Returns:
            LangGraph-formatted stream event
        """
        # LangGraph SDK expects events in this format:
        # event: <event_type>
        # data: <json_data>
        #
        # Event types: metadata, values, updates, error, end

        if event_type == "token":
            # Token events become "updates" in LangGraph
            return {
                "event": "updates",
                "data": {"messages": [{"type": "ai", "content": data}]},
            }
        elif event_type == "error":
            return {"event": "error", "data": {"error": data}}
        elif event_type == "done":
            return {"event": "end", "data": {}}
        elif event_type == "metadata":
            return {"event": "metadata", "data": data}
        else:
            # Pass through unknown event types
            return {"event": event_type, "data": data}

    async def adapt_stream_response(
        self, stream: AsyncGenerator
    ) -> AsyncGenerator[str, None]:
        """Adapt ChatService streaming response to LangGraph format.

        Args:
            stream: ChatService stream generator

        Yields:
            LangGraph-formatted SSE events
        """
        try:
            async for chunk in stream:
                # ChatService streams in AI SDK Data Stream Protocol
                # We need to convert to LangGraph streaming format
                if isinstance(chunk, str):
                    # This is a token chunk
                    event = await self.stream_event_to_langgraph_format("token", chunk)
                    yield f"event: {event['event']}\ndata: {event['data']}\n\n"
                elif isinstance(chunk, dict):
                    # This is a structured event
                    event_type = chunk.get("type", "updates")
                    event = await self.stream_event_to_langgraph_format(
                        event_type, chunk.get("data")
                    )
                    yield f"event: {event['event']}\ndata: {event['data']}\n\n"

        except Exception as e:
            logger.error(f"Error in stream adaptation: {e}")
            error_event = await self.stream_event_to_langgraph_format("error", str(e))
            yield f"event: {error_event['event']}\ndata: {error_event['data']}\n\n"
        finally:
            # Send end event
            end_event = await self.stream_event_to_langgraph_format("done", {})
            yield f"event: {end_event['event']}\ndata: {end_event['data']}\n\n"
