"""
WebRTC Connection Manager

Stateless connection manager using Redis Pub/Sub for scalable,
multi-instance WebRTC signaling.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Optional, Set, Any

from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.webrtc.schemas import WebRtcMessage, MessageType

logger = get_logger(prefix="[WebRTC-Manager]")


class WebRtcManager:
    """
    WebRTC connection manager using Redis Pub/Sub for horizontal scalability.
    
    This manager is stateless regarding WebSocket connections - those are managed
    by the router instances. It provides methods for:
    - Publishing messages to Redis channels (rooms)
    - Subscribing to Redis channels for a room
    - Managing room state (participants) in Redis Sets
    """
    
    def __init__(self):
        """Initialize the WebRTC manager."""
        self.redis = redis_manager
        
        # Redis key prefixes
        self.ROOM_CHANNEL_PREFIX = "webrtc:room:"
        self.ROOM_PARTICIPANTS_PREFIX = "webrtc:participants:"
        self.USER_PRESENCE_PREFIX = "webrtc:presence:"
        self.ROOM_ROLES_PREFIX = "webrtc:roles:"
        self.ROOM_PERMISSIONS_PREFIX = "webrtc:permissions:"
        self.ROOM_ANALYTICS_PREFIX = "webrtc:analytics:"
        self.ROOM_RECORDINGS_PREFIX = "webrtc:recordings:"
        self.FILE_TRANSFERS_PREFIX = "webrtc:transfers:"
        
        # TTL for presence keys (heartbeat timeout)
        self.PRESENCE_TTL = 30  # seconds
        
        logger.info("WebRTC manager initialized with Redis Pub/Sub")
    
    def _get_room_channel(self, room_id: str) -> str:
        """Get Redis channel name for a room."""
        return f"{self.ROOM_CHANNEL_PREFIX}{room_id}"
    
    def _get_participants_key(self, room_id: str) -> str:
        """Get Redis key for room participants set."""
        return f"{self.ROOM_PARTICIPANTS_PREFIX}{room_id}"
    
    def _get_presence_key(self, room_id: str, user_id: str) -> str:
        """Get Redis key for user presence in a room."""
        return f"{self.USER_PRESENCE_PREFIX}{room_id}:{user_id}"
    
    async def publish_to_room(self, room_id: str, message: WebRtcMessage) -> int:
        """
        Publish a message to a room's Redis channel.
        
        Args:
            room_id: The room identifier
            message: The WebRTC message to publish
            
        Returns:
            Number of subscribers that received the message
        """
        try:
            redis_client = await self.redis.get_redis()
            channel = self._get_room_channel(room_id)
            
            # Add timestamp if not present
            if not message.timestamp:
                message.timestamp = datetime.now(timezone.utc).isoformat()
            
            # Serialize message to JSON
            message_json = message.model_dump_json()
            
            # Publish to Redis channel using Redis PUBLISH
            subscribers = await redis_client.publish(channel, message_json)
            
            logger.debug(
                f"Published {message.type} to room {room_id}",
                extra={
                    "room_id": room_id,
                    "message_type": message.type,
                    "subscribers": subscribers,
                    "sender_id": message.sender_id
                }
            )
            
            return subscribers
            
        except Exception as e:
            logger.error(
                f"Failed to publish message to room {room_id}: {e}",
                extra={"room_id": room_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def subscribe_to_room(self, room_id: str) -> AsyncIterator[WebRtcMessage]:
        """
        Subscribe to a room's Redis channel and yield messages.
        
        Args:
            room_id: The room identifier
            
        Yields:
            WebRtcMessage objects from the channel
        """
        redis_client = await self.redis.get_redis()
        channel = self._get_room_channel(room_id)
        pubsub = None
        
        try:
            # Create Redis pubsub instance using Redis PUBSUB
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(channel)
            
            logger.info(
                f"Subscribed to room {room_id}",
                extra={"room_id": room_id, "channel": channel}
            )
            
            # Listen for messages
            async for raw_message in pubsub.listen():
                if raw_message["type"] == "message":
                    try:
                        # Decode message
                        message_data = raw_message["data"]
                        if isinstance(message_data, bytes):
                            message_data = message_data.decode("utf-8")
                        
                        # Parse WebRTC message
                        message = WebRtcMessage.model_validate_json(message_data)
                        
                        logger.debug(
                            f"Received {message.type} in room {room_id}",
                            extra={
                                "room_id": room_id,
                                "message_type": message.type,
                                "sender_id": message.sender_id
                            }
                        )
                        
                        yield message
                        
                    except Exception as e:
                        logger.error(
                            f"Failed to parse message from room {room_id}: {e}",
                            extra={"room_id": room_id, "error": str(e)},
                            exc_info=True
                        )
                        
        except Exception as e:
            logger.error(
                f"Error in room subscription {room_id}: {e}",
                extra={"room_id": room_id, "error": str(e)},
                exc_info=True
            )
            raise
            
        finally:
            if pubsub:
                await pubsub.unsubscribe(channel)
                await pubsub.close()
                logger.info(
                    f"Unsubscribed from room {room_id}",
                    extra={"room_id": room_id}
                )
    
    async def add_participant(self, room_id: str, user_id: str, username: str) -> int:
        """
        Add a participant to a room.
        
        Args:
            room_id: The room identifier
            user_id: The user identifier
            username: The username
            
        Returns:
            Number of participants in the room after adding
        """
        try:
            redis_client = await self.redis.get_redis()
            participants_key = self._get_participants_key(room_id)
            presence_key = self._get_presence_key(room_id, user_id)
            
            # Store participant info as JSON
            participant_data = json.dumps({
                "user_id": user_id,
                "username": username,
                "joined_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Add to participants set using Redis SADD
            await redis_client.sadd(participants_key, participant_data)
            
            # Set presence with TTL using Redis SETEX
            await redis_client.setex(presence_key, self.PRESENCE_TTL, "1")
            
            # Get participant count using Redis SCARD
            count = await redis_client.scard(participants_key)
            
            logger.info(
                f"Added participant {user_id} to room {room_id}",
                extra={
                    "room_id": room_id,
                    "user_id": user_id,
                    "participant_count": count
                }
            )
            
            return count
            
        except Exception as e:
            logger.error(
                f"Failed to add participant to room {room_id}: {e}",
                extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def remove_participant(self, room_id: str, user_id: str) -> int:
        """
        Remove a participant from a room.
        
        Args:
            room_id: The room identifier
            user_id: The user identifier
            
        Returns:
            Number of participants remaining in the room
        """
        try:
            redis_client = await self.redis.get_redis()
            participants_key = self._get_participants_key(room_id)
            presence_key = self._get_presence_key(room_id, user_id)
            
            # Get all participants to find the matching one using Redis SMEMBERS
            participants = await redis_client.smembers(participants_key)
            
            # Find and remove the participant
            for participant_json in participants:
                try:
                    participant = json.loads(participant_json)
                    if participant.get("user_id") == user_id:
                        # Remove from set using Redis SREM
                        await redis_client.srem(participants_key, participant_json)
                        break
                except json.JSONDecodeError:
                    continue
            
            # Remove presence key using Redis DEL
            await redis_client.delete(presence_key)
            
            # Get remaining participant count using Redis SCARD
            count = await redis_client.scard(participants_key)
            
            # Clean up empty room
            if count == 0:
                await redis_client.delete(participants_key)
            
            logger.info(
                f"Removed participant {user_id} from room {room_id}",
                extra={
                    "room_id": room_id,
                    "user_id": user_id,
                    "remaining_participants": count
                }
            )
            
            return count
            
        except Exception as e:
            logger.error(
                f"Failed to remove participant from room {room_id}: {e}",
                extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def get_participants(self, room_id: str) -> list[Dict[str, str]]:
        """
        Get all participants in a room.
        
        Args:
            room_id: The room identifier
            
        Returns:
            List of participant dictionaries
        """
        try:
            redis_client = await self.redis.get_redis()
            participants_key = self._get_participants_key(room_id)
            # Get all participants using Redis SMEMBERS
            participants_json = await redis_client.smembers(participants_key)
            
            participants = []
            for participant_json in participants_json:
                try:
                    participant = json.loads(participant_json)
                    participants.append(participant)
                except json.JSONDecodeError:
                    continue
            
            return participants
            
        except Exception as e:
            logger.error(
                f"Failed to get participants for room {room_id}: {e}",
                extra={"room_id": room_id, "error": str(e)},
                exc_info=True
            )
            return []
    
    async def update_presence(self, room_id: str, user_id: str) -> None:
        """
        Update user presence (heartbeat) in a room.
        
        Args:
            room_id: The room identifier
            user_id: The user identifier
        """
        try:
            redis_client = await self.redis.get_redis()
            presence_key = self._get_presence_key(room_id, user_id)
            # Update presence using Redis SETEX
            await redis_client.setex(presence_key, self.PRESENCE_TTL, "1")
        except Exception as e:
            logger.warning(
                f"Failed to update presence for user {user_id} in room {room_id}: {e}",
                extra={"room_id": room_id, "user_id": user_id, "error": str(e)}
            )
    
    # ========================================================================
    # Phase 1: Room Permissions & Roles
    # ========================================================================
    
    async def set_user_role(self, room_id: str, user_id: str, role: str) -> None:
        """Set a user's role in a room."""
        try:
            redis_client = await self.redis.get_redis()
            role_key = f"{self.ROOM_ROLES_PREFIX}{room_id}:{user_id}"
            await redis_client.setex(role_key, 3600, role)  # 1 hour TTL
            
            logger.info(
                f"Set role {role} for user {user_id} in room {room_id}",
                extra={"room_id": room_id, "user_id": user_id, "role": role}
            )
        except Exception as e:
            logger.error(
                f"Failed to set role: {e}",
                extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
                exc_info=True
            )
    
    async def get_user_role(self, room_id: str, user_id: str) -> str:
        """Get a user's role in a room."""
        try:
            redis_client = await self.redis.get_redis()
            role_key = f"{self.ROOM_ROLES_PREFIX}{room_id}:{user_id}"
            role = await redis_client.get(role_key)
            return role.decode("utf-8") if role else "participant"
        except Exception as e:
            logger.error(
                f"Failed to get role: {e}",
                extra={"room_id": room_id, "user_id": user_id, "error": str(e)}
            )
            return "participant"
    
    async def set_user_permissions(self, room_id: str, user_id: str, permissions: Dict[str, bool]) -> None:
        """Set a user's permissions in a room."""
        try:
            redis_client = await self.redis.get_redis()
            perm_key = f"{self.ROOM_PERMISSIONS_PREFIX}{room_id}:{user_id}"
            await redis_client.hset(perm_key, mapping=permissions)
            await redis_client.expire(perm_key, 3600)  # 1 hour TTL
            
            logger.info(
                f"Set permissions for user {user_id} in room {room_id}",
                extra={"room_id": room_id, "user_id": user_id, "permissions": permissions}
            )
        except Exception as e:
            logger.error(
                f"Failed to set permissions: {e}",
                extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
                exc_info=True
            )
    
    async def get_user_permissions(self, room_id: str, user_id: str) -> Dict[str, bool]:
        """Get a user's permissions in a room."""
        try:
            redis_client = await self.redis.get_redis()
            perm_key = f"{self.ROOM_PERMISSIONS_PREFIX}{room_id}:{user_id}"
            permissions = await redis_client.hgetall(perm_key)
            
            if not permissions:
                # Return default permissions
                return {
                    "can_speak": True,
                    "can_share_video": True,
                    "can_share_screen": True,
                    "can_send_chat": True,
                    "can_share_files": True,
                    "can_manage_participants": False,
                    "can_record": False
                }
            
            # Convert bytes to bool
            return {k.decode("utf-8"): v.decode("utf-8") == "True" for k, v in permissions.items()}
        except Exception as e:
            logger.error(
                f"Failed to get permissions: {e}",
                extra={"room_id": room_id, "user_id": user_id, "error": str(e)}
            )
            return {}
    
    # ========================================================================
    # Phase 2: Analytics
    # ========================================================================
    
    async def track_analytics_event(self, room_id: str, event_type: str, user_id: str, data: Dict[str, Any]) -> None:
        """Track an analytics event."""
        try:
            redis_client = await self.redis.get_redis()
            analytics_key = f"{self.ROOM_ANALYTICS_PREFIX}{room_id}"
            
            event = {
                "event_type": event_type,
                "user_id": user_id,
                "data": json.dumps(data),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Store in Redis stream
            await redis_client.xadd(analytics_key, event, maxlen=1000)
            
            logger.debug(
                f"Tracked analytics event: {event_type}",
                extra={"room_id": room_id, "user_id": user_id, "event_type": event_type}
            )
        except Exception as e:
            logger.error(
                f"Failed to track analytics: {e}",
                extra={"room_id": room_id, "error": str(e)}
            )
    
    async def get_room_analytics(self, room_id: str, limit: int = 100) -> list[Dict[str, Any]]:
        """Get analytics events for a room."""
        try:
            redis_client = await self.redis.get_redis()
            analytics_key = f"{self.ROOM_ANALYTICS_PREFIX}{room_id}"
            
            # Get events from stream
            events = await redis_client.xrange(analytics_key, count=limit)
            
            result = []
            for event_id, event_data in events:
                event = dict(event_data)
                if b"data" in event:
                    event[b"data"] = json.loads(event[b"data"])
                # Convert bytes keys to strings
                result.append({k.decode("utf-8"): v.decode("utf-8") if isinstance(v, bytes) else v 
                              for k, v in event.items()})
            
            return result
        except Exception as e:
            logger.error(
                f"Failed to get analytics: {e}",
                extra={"room_id": room_id, "error": str(e)}
            )
            return []
    
    # ========================================================================
    # Phase 2: Recording Management
    # ========================================================================
    
    async def start_recording(self, room_id: str, recording_id: str, metadata: Dict[str, Any]) -> None:
        """Start a recording session."""
        try:
            redis_client = await self.redis.get_redis()
            recording_key = f"{self.ROOM_RECORDINGS_PREFIX}{room_id}:{recording_id}"
            
            recording_data = {
                "recording_id": recording_id,
                "room_id": room_id,
                "status": "recording",
                "started_at": datetime.now(timezone.utc).isoformat(),
                **metadata
            }
            
            await redis_client.hset(recording_key, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                                                            for k, v in recording_data.items()})
            await redis_client.expire(recording_key, 86400)  # 24 hour TTL
            
            logger.info(
                f"Started recording {recording_id} in room {room_id}",
                extra={"room_id": room_id, "recording_id": recording_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to start recording: {e}",
                extra={"room_id": room_id, "recording_id": recording_id, "error": str(e)},
                exc_info=True
            )
    
    async def stop_recording(self, room_id: str, recording_id: str) -> None:
        """Stop a recording session."""
        try:
            redis_client = await self.redis.get_redis()
            recording_key = f"{self.ROOM_RECORDINGS_PREFIX}{room_id}:{recording_id}"
            
            await redis_client.hset(recording_key, "status", "stopped")
            await redis_client.hset(recording_key, "stopped_at", datetime.now(timezone.utc).isoformat())
            
            logger.info(
                f"Stopped recording {recording_id} in room {room_id}",
                extra={"room_id": room_id, "recording_id": recording_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to stop recording: {e}",
                extra={"room_id": room_id, "recording_id": recording_id, "error": str(e)},
                exc_info=True
            )
    
    async def get_active_recordings(self, room_id: str) -> list[str]:
        """Get list of active recording IDs for a room."""
        try:
            redis_client = await self.redis.get_redis()
            pattern = f"{self.ROOM_RECORDINGS_PREFIX}{room_id}:*"
            
            recording_keys = []
            async for key in redis_client.scan_iter(match=pattern):
                status = await redis_client.hget(key, "status")
                if status and status.decode("utf-8") == "recording":
                    recording_id = key.decode("utf-8").split(":")[-1]
                    recording_keys.append(recording_id)
            
            return recording_keys
        except Exception as e:
            logger.error(
                f"Failed to get active recordings: {e}",
                extra={"room_id": room_id, "error": str(e)}
            )
            return []
    
    # ========================================================================
    # Phase 2: File Transfer Tracking
    # ========================================================================
    
    async def track_file_transfer(self, room_id: str, transfer_id: str, metadata: Dict[str, Any]) -> None:
        """Track a file transfer."""
        try:
            redis_client = await self.redis.get_redis()
            transfer_key = f"{self.FILE_TRANSFERS_PREFIX}{room_id}:{transfer_id}"
            
            await redis_client.hset(transfer_key, mapping={k: str(v) for k, v in metadata.items()})
            await redis_client.expire(transfer_key, 3600)  # 1 hour TTL
            
            logger.debug(
                f"Tracking file transfer {transfer_id}",
                extra={"room_id": room_id, "transfer_id": transfer_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to track file transfer: {e}",
                extra={"room_id": room_id, "transfer_id": transfer_id, "error": str(e)}
            )
    
    async def update_transfer_progress(self, room_id: str, transfer_id: str, chunks_received: int) -> None:
        """Update file transfer progress."""
        try:
            redis_client = await self.redis.get_redis()
            transfer_key = f"{self.FILE_TRANSFERS_PREFIX}{room_id}:{transfer_id}"
            await redis_client.hset(transfer_key, "chunks_received", str(chunks_received))
        except Exception as e:
            logger.error(
                f"Failed to update transfer progress: {e}",
                extra={"room_id": room_id, "transfer_id": transfer_id, "error": str(e)}
            )


# Global instance
webrtc_manager = WebRtcManager()
