"""Session statistics manager for chat system."""

from datetime import datetime
from typing import Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase


class SessionStatisticsManager:
    """Manager for calculating and updating session statistics."""

    def __init__(self, db: AsyncIOMotorDatabase):
        """Initialize with database connection.

        Args:
            db: AsyncIOMotor database instance
        """
        self.db = db
        self.sessions_collection = db.chat_sessions
        self.messages_collection = db.chat_messages
        self.token_usage_collection = db.token_usage

    async def calculate_session_statistics(self, session_id: str) -> Dict:
        """Calculate comprehensive statistics for a session.

        Args:
            session_id: ID of the chat session

        Returns:
            Dictionary containing session statistics:
            - message_count: Total number of messages
            - total_tokens: Sum of all tokens used
            - total_cost: Sum of all costs
            - last_message_at: Timestamp of last message
            - average_response_time: Average time between user and assistant messages
            - conversation_duration: Total duration of conversation
            - user_messages: Count of user messages
            - assistant_messages: Count of assistant messages
        """
        # Get all messages for the session
        messages = await self.messages_collection.find(
            {"session_id": session_id}
        ).sort("created_at", 1).to_list(None)

        if not messages:
            return {
                "message_count": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "last_message_at": None,
                "average_response_time": 0.0,
                "conversation_duration": 0.0,
                "user_messages": 0,
                "assistant_messages": 0,
            }

        # Get token usage for all messages
        message_ids = [msg["id"] for msg in messages]
        token_usage = await self.token_usage_collection.find(
            {"message_id": {"$in": message_ids}}
        ).to_list(None)

        total_tokens = sum(t["total_tokens"] for t in token_usage)
        total_cost = sum(t["cost"] for t in token_usage)

        # Calculate response times (time between user and assistant messages)
        response_times = []
        for i in range(len(messages) - 1):
            if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
                time_diff = (
                    messages[i + 1]["created_at"] - messages[i]["created_at"]
                ).total_seconds()
                response_times.append(time_diff)

        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        # Calculate conversation duration
        first_message = messages[0]["created_at"]
        last_message = messages[-1]["created_at"]
        conversation_duration = (last_message - first_message).total_seconds()

        # Count messages by role
        user_messages = sum(1 for m in messages if m["role"] == "user")
        assistant_messages = sum(1 for m in messages if m["role"] == "assistant")

        return {
            "message_count": len(messages),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "last_message_at": last_message,
            "average_response_time": avg_response_time,
            "conversation_duration": conversation_duration,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
        }

    async def update_session_statistics(self, session_id: str) -> Dict:
        """Update session with calculated statistics.

        Args:
            session_id: ID of the chat session

        Returns:
            Dictionary containing updated statistics
        """
        stats = await self.calculate_session_statistics(session_id)

        await self.sessions_collection.update_one(
            {"id": session_id},
            {
                "$set": {
                    "message_count": stats["message_count"],
                    "total_tokens": stats["total_tokens"],
                    "total_cost": stats["total_cost"],
                    "last_message_at": stats["last_message_at"],
                    "updated_at": datetime.utcnow(),
                }
            },
        )

        return stats

    async def generate_session_title(
        self, session_id: str, first_message: str
    ) -> str:
        """Generate title from first message.

        Args:
            session_id: ID of the chat session
            first_message: Content of the first user message

        Returns:
            Generated title (max 50 characters)
        """
        # Handle empty or very short messages
        if not first_message or len(first_message.strip()) < 3:
            return "New Chat"

        # Clean the message
        cleaned_message = first_message.strip()

        # If message is short enough, use it as-is
        if len(cleaned_message) <= 50:
            return cleaned_message

        # Truncate at word boundary
        title = cleaned_message[:50]
        last_space = title.rfind(" ")

        # Ensure minimum length before truncating at word boundary
        if last_space > 20:
            title = title[:last_space]

        return title + "..."
