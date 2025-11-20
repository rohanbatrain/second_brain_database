"""Enum definitions for chat system."""

from enum import Enum


class ChatSessionType(str, Enum):
    """Type of chat session."""

    GENERAL = "GENERAL"
    SQL = "SQL"
    VECTOR = "VECTOR"


class MessageRole(str, Enum):
    """Role of message sender."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageStatus(str, Enum):
    """Status of message processing."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VoteType(str, Enum):
    """Type of vote on a message."""

    UP = "up"
    DOWN = "down"
