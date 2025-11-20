"""
WebRTC MongoDB Persistence

Background tasks to persist WebRTC data from Redis to MongoDB for:
- Historical room sessions
- Chat history archival
- Analytics events
- Recording metadata
- Audit trail

Enables recovery, compliance, and long-term analytics.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum

from motor.motor_asyncio import AsyncIOMotorCollection
from pydantic import BaseModel, Field

from second_brain_database.database import db_manager
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[WebRTC-Persistence]")


class RoomSessionStatus(str, Enum):
    """Room session status."""
    ACTIVE = "active"
    ENDED = "ended"
    ARCHIVED = "archived"


class RoomSession(BaseModel):
    """Room session document for MongoDB."""
    room_id: str = Field(..., description="Room identifier")
    created_at: datetime = Field(..., description="When room was created")
    ended_at: Optional[datetime] = Field(None, description="When room ended")
    status: RoomSessionStatus = Field(RoomSessionStatus.ACTIVE, description="Session status")
    
    # Participants
    participants: List[str] = Field(default_factory=list, description="List of usernames who joined")
    peak_participants: int = Field(0, description="Maximum concurrent participants")
    
    # Duration
    duration_seconds: Optional[int] = Field(None, description="Total session duration")
    
    # Settings
    settings: Dict[str, Any] = Field(default_factory=dict, description="Room settings snapshot")
    
    # Statistics
    total_messages: int = Field(0, description="Total chat messages")
    total_files_shared: int = Field(0, description="Total files shared")
    total_reactions: int = Field(0, description="Total reactions")
    recordings: List[str] = Field(default_factory=list, description="Recording IDs")
    
    # Metadata
    created_by: Optional[str] = Field(None, description="Username who created the room")
    host_username: Optional[str] = Field(None, description="Primary host username")
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("room_id", 1)], "unique": True},
                {"keys": [("created_at", -1)]},
                {"keys": [("status", 1)]},
                {"keys": [("participants", 1)]},
            ]
        }


class ChatMessage(BaseModel):
    """Chat message document for MongoDB."""
    message_id: str = Field(..., description="Unique message ID")
    room_id: str = Field(..., description="Room identifier")
    sender_username: str = Field(..., description="Sender username")
    sender_name: str = Field(..., description="Sender display name")
    message: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="When message was sent")
    
    # Message type
    is_system_message: bool = Field(False, description="System message flag")
    target_username: Optional[str] = Field(None, description="Direct message target")
    
    # Metadata
    edited_at: Optional[datetime] = Field(None, description="When message was edited")
    deleted_at: Optional[datetime] = Field(None, description="When message was deleted")
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("room_id", 1), ("timestamp", -1)]},
                {"keys": [("sender_username", 1)]},
                {"keys": [("message_id", 1)], "unique": True},
            ]
        }


class AnalyticsEvent(BaseModel):
    """Analytics event document for MongoDB."""
    event_id: str = Field(..., description="Unique event ID")
    room_id: str = Field(..., description="Room identifier")
    event_type: str = Field(..., description="Event type")
    username: str = Field(..., description="User who triggered event")
    timestamp: datetime = Field(..., description="When event occurred")
    
    # Event data
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    
    # Session tracking
    session_id: Optional[str] = Field(None, description="User session ID")
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("room_id", 1), ("timestamp", -1)]},
                {"keys": [("event_type", 1)]},
                {"keys": [("username", 1)]},
                {"keys": [("timestamp", -1)]},
            ]
        }


class RecordingMetadata(BaseModel):
    """Recording metadata document for MongoDB."""
    recording_id: str = Field(..., description="Unique recording ID")
    room_id: str = Field(..., description="Room identifier")
    started_at: datetime = Field(..., description="Recording start time")
    stopped_at: Optional[datetime] = Field(None, description="Recording stop time")
    
    # Recording details
    started_by: str = Field(..., description="Username who started recording")
    stopped_by: Optional[str] = Field(None, description="Username who stopped recording")
    duration_seconds: Optional[int] = Field(None, description="Recording duration")
    
    # Storage
    file_path: Optional[str] = Field(None, description="File storage path")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    storage_provider: Optional[str] = Field(None, description="Storage provider (s3, local, etc)")
    
    # Status
    status: str = Field("active", description="Recording status")
    processing_status: Optional[str] = Field(None, description="Processing status")
    
    # Participants snapshot
    participants: List[str] = Field(default_factory=list, description="Participants during recording")
    
    class Config:
        json_schema_extra = {
            "indexes": [
                {"keys": [("recording_id", 1)], "unique": True},
                {"keys": [("room_id", 1), ("started_at", -1)]},
                {"keys": [("started_by", 1)]},
            ]
        }


class WebRtcPersistence:
    """
    Manages persistence of WebRTC data from Redis to MongoDB.
    
    Provides methods to:
    - Archive room sessions
    - Store chat history
    - Persist analytics events
    - Save recording metadata
    - Create audit trails
    """
    
    def __init__(self):
        """Initialize persistence manager."""
        self.mongodb = db_manager
        self.redis = redis_manager
        
        # Collection names
        self.ROOM_SESSIONS_COLLECTION = "webrtc_room_sessions"
        self.CHAT_MESSAGES_COLLECTION = "webrtc_chat_messages"
        self.ANALYTICS_EVENTS_COLLECTION = "webrtc_analytics_events"
        self.RECORDINGS_COLLECTION = "webrtc_recordings"
        
        logger.info("WebRTC persistence manager initialized")
    
    async def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """Get MongoDB collection."""
        db = await self.mongodb.get_database()
        return db[collection_name]
    
    async def create_indexes(self):
        """Create MongoDB indexes for all collections."""
        try:
            # Room sessions indexes
            sessions_col = await self.get_collection(self.ROOM_SESSIONS_COLLECTION)
            await sessions_col.create_index("room_id", unique=True)
            await sessions_col.create_index([("created_at", -1)])
            await sessions_col.create_index("status")
            await sessions_col.create_index("participants")
            
            # Chat messages indexes
            chat_col = await self.get_collection(self.CHAT_MESSAGES_COLLECTION)
            await chat_col.create_index([("room_id", 1), ("timestamp", -1)])
            await chat_col.create_index("sender_username")
            await chat_col.create_index("message_id", unique=True)
            
            # Analytics events indexes
            analytics_col = await self.get_collection(self.ANALYTICS_EVENTS_COLLECTION)
            await analytics_col.create_index([("room_id", 1), ("timestamp", -1)])
            await analytics_col.create_index("event_type")
            await analytics_col.create_index("username")
            await analytics_col.create_index([("timestamp", -1)])
            
            # Recordings indexes
            recordings_col = await self.get_collection(self.RECORDINGS_COLLECTION)
            await recordings_col.create_index("recording_id", unique=True)
            await recordings_col.create_index([("room_id", 1), ("started_at", -1)])
            await recordings_col.create_index("started_by")
            
            logger.info("MongoDB indexes created successfully")
            
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")
    
    async def save_room_session(self, session: RoomSession) -> bool:
        """
        Save or update room session.
        
        Args:
            session: RoomSession model
            
        Returns:
            True if successful
        """
        try:
            collection = await self.get_collection(self.ROOM_SESSIONS_COLLECTION)
            
            session_dict = session.model_dump(exclude_none=True)
            
            # Upsert (update or insert)
            result = await collection.update_one(
                {"room_id": session.room_id},
                {"$set": session_dict},
                upsert=True
            )
            
            logger.debug(
                f"Room session saved",
                extra={"room_id": session.room_id, "status": session.status}
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to save room session: {e}",
                extra={"room_id": session.room_id}
            )
            return False
    
    async def save_chat_message(self, message: ChatMessage) -> bool:
        """
        Save chat message to MongoDB.
        
        Args:
            message: ChatMessage model
            
        Returns:
            True if successful
        """
        try:
            collection = await self.get_collection(self.CHAT_MESSAGES_COLLECTION)
            
            message_dict = message.model_dump(exclude_none=True)
            
            await collection.insert_one(message_dict)
            
            logger.debug(
                f"Chat message saved",
                extra={"room_id": message.room_id, "sender": message.sender_username}
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to save chat message: {e}",
                extra={"room_id": message.room_id, "message_id": message.message_id}
            )
            return False
    
    async def save_analytics_event(self, event: AnalyticsEvent) -> bool:
        """
        Save analytics event to MongoDB.
        
        Args:
            event: AnalyticsEvent model
            
        Returns:
            True if successful
        """
        try:
            collection = await self.get_collection(self.ANALYTICS_EVENTS_COLLECTION)
            
            event_dict = event.model_dump(exclude_none=True)
            
            await collection.insert_one(event_dict)
            
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to save analytics event: {e}",
                extra={"room_id": event.room_id, "event_type": event.event_type}
            )
            return False
    
    async def save_recording_metadata(self, recording: RecordingMetadata) -> bool:
        """
        Save or update recording metadata.
        
        Args:
            recording: RecordingMetadata model
            
        Returns:
            True if successful
        """
        try:
            collection = await self.get_collection(self.RECORDINGS_COLLECTION)
            
            recording_dict = recording.model_dump(exclude_none=True)
            
            result = await collection.update_one(
                {"recording_id": recording.recording_id},
                {"$set": recording_dict},
                upsert=True
            )
            
            logger.debug(
                f"Recording metadata saved",
                extra={"recording_id": recording.recording_id, "room_id": recording.room_id}
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to save recording metadata: {e}",
                extra={"recording_id": recording.recording_id}
            )
            return False
    
    async def get_room_session(self, room_id: str) -> Optional[RoomSession]:
        """Get room session from MongoDB."""
        try:
            collection = await self.get_collection(self.ROOM_SESSIONS_COLLECTION)
            doc = await collection.find_one({"room_id": room_id})
            
            if doc:
                doc.pop("_id", None)  # Remove MongoDB _id
                return RoomSession(**doc)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get room session: {e}", extra={"room_id": room_id})
            return None
    
    async def get_chat_history(
        self,
        room_id: str,
        limit: int = 100,
        before_timestamp: Optional[datetime] = None
    ) -> List[ChatMessage]:
        """
        Get chat history for a room.
        
        Args:
            room_id: Room identifier
            limit: Maximum messages to return
            before_timestamp: Get messages before this timestamp
            
        Returns:
            List of ChatMessage objects
        """
        try:
            collection = await self.get_collection(self.CHAT_MESSAGES_COLLECTION)
            
            query = {"room_id": room_id, "deleted_at": None}
            if before_timestamp:
                query["timestamp"] = {"$lt": before_timestamp}
            
            cursor = collection.find(query).sort("timestamp", -1).limit(limit)
            messages = []
            
            async for doc in cursor:
                doc.pop("_id", None)
                messages.append(ChatMessage(**doc))
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get chat history: {e}", extra={"room_id": room_id})
            return []
    
    async def get_room_analytics(
        self,
        room_id: str,
        event_types: Optional[List[str]] = None
    ) -> List[AnalyticsEvent]:
        """
        Get analytics events for a room.
        
        Args:
            room_id: Room identifier
            event_types: Filter by specific event types
            
        Returns:
            List of AnalyticsEvent objects
        """
        try:
            collection = await self.get_collection(self.ANALYTICS_EVENTS_COLLECTION)
            
            query = {"room_id": room_id}
            if event_types:
                query["event_type"] = {"$in": event_types}
            
            cursor = collection.find(query).sort("timestamp", -1)
            events = []
            
            async for doc in cursor:
                doc.pop("_id", None)
                events.append(AnalyticsEvent(**doc))
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get room analytics: {e}", extra={"room_id": room_id})
            return []


# Global persistence instance
webrtc_persistence = WebRtcPersistence()
