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
        
        # Immediate Features
        self.ROOM_SETTINGS_PREFIX = "webrtc:settings:"
        self.HAND_RAISE_QUEUE_PREFIX = "webrtc:hand-raise:"
        self.PARTICIPANT_INFO_PREFIX = "webrtc:participant-info:"
        
        # Short Term Features
        self.WAITING_ROOM_PREFIX = "webrtc:waiting-room:"
        
        # Medium Term Features
        self.BREAKOUT_ROOMS_PREFIX = "webrtc:breakout-rooms:"
        self.LIVE_STREAMS_PREFIX = "webrtc:live-streams:"
        
        # Long Term Features
        self.E2EE_KEYS_PREFIX = "webrtc:e2ee-keys:"
        
        # TTL for presence keys (heartbeat timeout)
        self.PRESENCE_TTL = 30  # seconds
        
        logger.info("WebRTC manager initialized with Redis Pub/Sub")
    
    def _get_room_channel(self, room_id: str) -> str:
        """Get Redis channel name for a room."""
        return f"{self.ROOM_CHANNEL_PREFIX}{room_id}"
    
    def _get_participants_key(self, room_id: str) -> str:
        """Get Redis key for room participants set."""
        return f"{self.ROOM_PARTICIPANTS_PREFIX}{room_id}"
    
    def _get_presence_key(self, room_id: str, username: str) -> str:
        """Get Redis key for user presence in a room."""
        return f"{self.USER_PRESENCE_PREFIX}{room_id}:{username}"
    
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
    
    async def add_participant(self, room_id: str, username: str) -> int:
        """
        Add a participant to a room.
        
        Args:
            room_id: The room identifier
            username: The username (used as identifier throughout the system)
            
        Returns:
            Number of participants in the room after adding
        """
        try:
            redis_client = await self.redis.get_redis()
            participants_key = self._get_participants_key(room_id)
            presence_key = self._get_presence_key(room_id, username)
            
            # Store participant info as JSON
            participant_data = json.dumps({
                "username": username,
                "joined_at": datetime.now(timezone.utc).isoformat()
            })
            
            # Add to participants set using Redis SADD
            await redis_client.sadd(participants_key, participant_data)
            
            # Set presence with TTL using Redis SETEX
            await redis_client.setex(presence_key, self.PRESENCE_TTL, "1")
            
            # Get participant count using Redis SCARD
            count = await redis_client.scard(participants_key)
            
            # Auto-assign host role to first participant
            if count == 1:
                await self.set_user_role(room_id, username, "host")
                logger.info(
                    f"Auto-assigned host role to first participant {username} in room {room_id}",
                    extra={"room_id": room_id, "username": username}
                )
            
            logger.info(
                f"Added participant {username} to room {room_id}",
                extra={
                    "room_id": room_id,
                    "username": username,
                    "participant_count": count
                }
            )
            
            return count
            
        except Exception as e:
            logger.error(
                f"Failed to add participant to room {room_id}: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)},
                exc_info=True
            )
            raise
    
    async def remove_participant(self, room_id: str, username: str) -> int:
        """
        Remove a participant from a room.
        
        Args:
            room_id: The room identifier
            username: The username (used as identifier throughout the system)
            
        Returns:
            Number of participants remaining in the room
        """
        try:
            redis_client = await self.redis.get_redis()
            participants_key = self._get_participants_key(room_id)
            presence_key = self._get_presence_key(room_id, username)
            
            # Get all participants to find the matching one using Redis SMEMBERS
            participants = await redis_client.smembers(participants_key)
            
            # Find and remove the participant
            for participant_json in participants:
                try:
                    participant = json.loads(participant_json)
                    if participant.get("username") == username:
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
                f"Removed participant {username} from room {room_id}",
                extra={
                    "room_id": room_id,
                    "username": username,
                    "remaining_participants": count
                }
            )
            
            return count
            
        except Exception as e:
            logger.error(
                f"Failed to remove participant from room {room_id}: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)},
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
    
    async def update_presence(self, room_id: str, username: str) -> None:
        """
        Update user presence (heartbeat) in a room.
        
        Args:
            room_id: The room identifier
            username: The username (used as identifier throughout the system)
        """
        try:
            redis_client = await self.redis.get_redis()
            presence_key = self._get_presence_key(room_id, username)
            # Update presence using Redis SETEX
            await redis_client.setex(presence_key, self.PRESENCE_TTL, "1")
        except Exception as e:
            logger.warning(
                f"Failed to update presence for user {username} in room {room_id}: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
    
    # ========================================================================
    # Phase 1: Room Permissions & Roles
    # ========================================================================
    
    async def set_user_role(self, room_id: str, username: str, role: str) -> None:
        """Set a user's role in a room."""
        try:
            redis_client = await self.redis.get_redis()
            role_key = f"{self.ROOM_ROLES_PREFIX}{room_id}:{username}"
            await redis_client.setex(role_key, 3600, role)  # 1 hour TTL
            
            logger.info(
                f"SET_ROLE: room={room_id}, username={username}, role_key={role_key}, role={role}",
                extra={"room_id": room_id, "username": username, "role": role}
            )
        except Exception as e:
            logger.error(
                f"Failed to set role: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)},
                exc_info=True
            )
    
    async def get_user_role(self, room_id: str, username: str) -> str:
        """Get a user's role in a room."""
        try:
            redis_client = await self.redis.get_redis()
            role_key = f"{self.ROOM_ROLES_PREFIX}{room_id}:{username}"
            role = await redis_client.get(role_key)
            
            # Handle both bytes and string returns from Redis
            if role:
                result = role if isinstance(role, str) else role.decode("utf-8")
            else:
                result = "participant"
            
            # Temporary debug logging
            logger.info(
                f"GET_ROLE: room={room_id}, username={username}, role_key={role_key}, result={result}",
                extra={"room_id": room_id, "username": username, "role": result}
            )
            
            return result
        except Exception as e:
            logger.error(
                f"Failed to get role: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
            return "participant"
    
    async def set_user_permissions(self, room_id: str, username: str, permissions: Dict[str, bool]) -> None:
        """Set a user's permissions in a room."""
        try:
            redis_client = await self.redis.get_redis()
            perm_key = f"{self.ROOM_PERMISSIONS_PREFIX}{room_id}:{username}"
            await redis_client.hset(perm_key, mapping=permissions)
            await redis_client.expire(perm_key, 3600)  # 1 hour TTL
            
            logger.info(
                f"Set permissions for user {username} in room {room_id}",
                extra={"room_id": room_id, "username": username, "permissions": permissions}
            )
        except Exception as e:
            logger.error(
                f"Failed to set permissions: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)},
                exc_info=True
            )
    
    async def get_user_permissions(self, room_id: str, username: str) -> Dict[str, bool]:
        """Get a user's permissions in a room."""
        try:
            redis_client = await self.redis.get_redis()
            perm_key = f"{self.ROOM_PERMISSIONS_PREFIX}{room_id}:{username}"
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
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
            return {}
    
    # ========================================================================
    # Phase 2: Analytics
    # ========================================================================
    
    async def track_analytics_event(self, room_id: str, event_type: str, username: str, data: Dict[str, Any]) -> None:
        """Track an analytics event."""
        try:
            redis_client = await self.redis.get_redis()
            analytics_key = f"{self.ROOM_ANALYTICS_PREFIX}{room_id}"
            
            event = {
                "event_type": event_type,
                "username": username,
                "data": json.dumps(data),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Store in Redis stream
            await redis_client.xadd(analytics_key, event, maxlen=1000)
            
            logger.debug(
                f"Tracked analytics event: {event_type}",
                extra={"room_id": room_id, "username": username, "event_type": event_type}
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
    
    # ========================================================================
    # Immediate Features: Participant Info Management
    # ========================================================================
    
    async def update_participant_info(self, room_id: str, username: str, info: Dict[str, Any]) -> None:
        """Update enhanced participant information."""
        try:
            redis_client = await self.redis.get_redis()
            info_key = f"{self.PARTICIPANT_INFO_PREFIX}{room_id}:{username}"
            
            await redis_client.hset(info_key, mapping={k: str(v) for k, v in info.items()})
            await redis_client.expire(info_key, 3600)  # 1 hour TTL
            
            logger.debug(
                f"Updated participant info for {username}",
                extra={"room_id": room_id, "username": username}
            )
        except Exception as e:
            logger.error(
                f"Failed to update participant info: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
    
    async def get_participant_info(self, room_id: str, username: str) -> Dict[str, Any]:
        """Get enhanced participant information."""
        try:
            redis_client = await self.redis.get_redis()
            info_key = f"{self.PARTICIPANT_INFO_PREFIX}{room_id}:{username}"
            
            info = await redis_client.hgetall(info_key)
            return {k.decode("utf-8"): v.decode("utf-8") for k, v in info.items()} if info else {}
        except Exception as e:
            logger.error(
                f"Failed to get participant info: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
            return {}
    
    # ========================================================================
    # Immediate Features: Room Settings Management
    # ========================================================================
    
    async def set_room_settings(self, room_id: str, settings: Dict[str, Any]) -> None:
        """Set room settings."""
        try:
            redis_client = await self.redis.get_redis()
            settings_key = f"{self.ROOM_SETTINGS_PREFIX}{room_id}"
            
            await redis_client.hset(settings_key, mapping={k: str(v) for k, v in settings.items()})
            await redis_client.expire(settings_key, 86400)  # 24 hour TTL
            
            logger.info(
                f"Updated room settings",
                extra={"room_id": room_id, "settings": settings}
            )
        except Exception as e:
            logger.error(
                f"Failed to set room settings: {e}",
                extra={"room_id": room_id, "error": str(e)},
                exc_info=True
            )
    
    async def get_room_settings(self, room_id: str) -> Dict[str, Any]:
        """Get room settings."""
        try:
            redis_client = await self.redis.get_redis()
            settings_key = f"{self.ROOM_SETTINGS_PREFIX}{room_id}"
            
            settings = await redis_client.hgetall(settings_key)
            if not settings:
                # Return default settings
                return {
                    "lock_room": False,
                    "enable_waiting_room": False,
                    "mute_on_entry": False,
                    "disable_video_on_entry": False,
                    "enable_chat": True,
                    "enable_screen_share": True,
                    "enable_reactions": True,
                    "enable_file_sharing": True,
                    "enable_recording": True,
                    "max_participants": None,
                    "require_host_to_start": False,
                    "allow_participants_rename": True,
                    "allow_participants_unmute": True
                }
            
            # Convert bytes/strings to appropriate types
            result = {}
            for k, v in settings.items():
                # Handle both bytes and string keys/values
                key = k if isinstance(k, str) else k.decode("utf-8")
                value = v if isinstance(v, str) else v.decode("utf-8")
                
                # Convert boolean strings
                if value in ("True", "False"):
                    result[key] = value == "True"
                # Convert None string
                elif value == "None":
                    result[key] = None
                # Convert numbers
                elif value.isdigit():
                    result[key] = int(value)
                else:
                    result[key] = value
            
            return result
        except Exception as e:
            logger.error(
                f"Failed to get room settings: {e}",
                extra={"room_id": room_id, "error": str(e)},
                exc_info=True
            )
            return {}
    
    # ========================================================================
    # Immediate Features: Hand Raise Queue Management
    # ========================================================================
    
    async def add_to_hand_raise_queue(self, room_id: str, username: str, timestamp: str) -> int:
        """Add user to hand raise queue."""
        try:
            redis_client = await self.redis.get_redis()
            queue_key = f"{self.HAND_RAISE_QUEUE_PREFIX}{room_id}"
            
            entry = json.dumps({
                "username": username,
                "raised_at": timestamp
            })
            
            # Add to sorted set with timestamp as score
            score = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
            await redis_client.zadd(queue_key, {entry: score})
            await redis_client.expire(queue_key, 3600)  # 1 hour TTL
            
            # Get position in queue
            position = await redis_client.zrank(queue_key, entry)
            
            logger.info(
                f"Added {username} to hand raise queue",
                extra={"room_id": room_id, "username": username, "position": position}
            )
            
            return position + 1 if position is not None else 1
        except Exception as e:
            logger.error(
                f"Failed to add to hand raise queue: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)},
                exc_info=True
            )
            raise
            return 0
    
    async def remove_from_hand_raise_queue(self, room_id: str, username: str) -> None:
        """Remove user from hand raise queue."""
        try:
            redis_client = await self.redis.get_redis()
            queue_key = f"{self.HAND_RAISE_QUEUE_PREFIX}{room_id}"
            
            # Get all entries and find the one with matching username
            entries = await redis_client.zrange(queue_key, 0, -1)
            for entry in entries:
                data = json.loads(entry)
                if data.get("username") == username:
                    await redis_client.zrem(queue_key, entry)
                    logger.info(
                        f"Removed {username} from hand raise queue",
                        extra={"room_id": room_id, "username": username}
                    )
                    break
        except Exception as e:
            logger.error(
                f"Failed to remove from hand raise queue: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
    
    async def get_hand_raise_queue(self, room_id: str) -> list[Dict[str, Any]]:
        """Get hand raise queue."""
        try:
            redis_client = await self.redis.get_redis()
            queue_key = f"{self.HAND_RAISE_QUEUE_PREFIX}{room_id}"
            
            entries = await redis_client.zrange(queue_key, 0, -1)
            
            queue = []
            for i, entry in enumerate(entries):
                data = json.loads(entry)
                data["position"] = i + 1
                queue.append(data)
            
            return queue
        except Exception as e:
            logger.error(
                f"Failed to get hand raise queue: {e}",
                extra={"room_id": room_id, "error": str(e)}
            )
            return []
    
    # ========================================================================
    # Short Term: Waiting Room Management
    # ========================================================================
    
    async def add_to_waiting_room(self, room_id: str, username: str, timestamp: str) -> None:
        """Add user to waiting room."""
        try:
            redis_client = await self.redis.get_redis()
            waiting_key = f"{self.WAITING_ROOM_PREFIX}{room_id}"
            
            participant = json.dumps({
                "username": username,
                "joined_at": timestamp
            })
            
            await redis_client.sadd(waiting_key, participant)
            await redis_client.expire(waiting_key, 3600)  # 1 hour TTL
            
            logger.info(
                f"Added {username} to waiting room",
                extra={"room_id": room_id, "username": username}
            )
        except Exception as e:
            logger.error(
                f"Failed to add to waiting room: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)},
                exc_info=True
            )
    
    async def remove_from_waiting_room(self, room_id: str, username: str) -> None:
        """Remove user from waiting room."""
        try:
            redis_client = await self.redis.get_redis()
            waiting_key = f"{self.WAITING_ROOM_PREFIX}{room_id}"
            
            # Get all participants and find the one with matching username
            participants = await redis_client.smembers(waiting_key)
            for participant_json in participants:
                participant = json.loads(participant_json)
                if participant.get("username") == username:
                    await redis_client.srem(waiting_key, participant_json)
                    logger.info(
                        f"Removed {username} from waiting room",
                        extra={"room_id": room_id, "username": username}
                    )
                    break
        except Exception as e:
            logger.error(
                f"Failed to remove from waiting room: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
    
    async def get_waiting_room_participants(self, room_id: str) -> list[Dict[str, Any]]:
        """Get waiting room participants."""
        try:
            redis_client = await self.redis.get_redis()
            waiting_key = f"{self.WAITING_ROOM_PREFIX}{room_id}"
            
            participants_json = await redis_client.smembers(waiting_key)
            
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
                f"Failed to get waiting room participants: {e}",
                extra={"room_id": room_id, "error": str(e)}
            )
            return []
    
    # ========================================================================
    # Medium Term: Breakout Rooms Management
    # ========================================================================
    
    async def create_breakout_room(self, room_id: str, breakout_room_id: str, config: Dict[str, Any]) -> None:
        """Create a breakout room."""
        try:
            redis_client = await self.redis.get_redis()
            breakout_key = f"{self.BREAKOUT_ROOMS_PREFIX}{room_id}:{breakout_room_id}"
            
            await redis_client.hset(breakout_key, mapping={k: str(v) for k, v in config.items()})
            await redis_client.expire(breakout_key, 86400)  # 24 hour TTL
            
            logger.info(
                f"Created breakout room {breakout_room_id}",
                extra={"room_id": room_id, "breakout_room_id": breakout_room_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to create breakout room: {e}",
                extra={"room_id": room_id, "breakout_room_id": breakout_room_id, "error": str(e)},
                exc_info=True
            )
    
    async def assign_to_breakout_room(self, room_id: str, username: str, breakout_room_id: str) -> None:
        """Assign user to breakout room."""
        try:
            redis_client = await self.redis.get_redis()
            assignment_key = f"{self.BREAKOUT_ROOMS_PREFIX}{room_id}:assignments"
            
            await redis_client.hset(assignment_key, username, breakout_room_id)
            await redis_client.expire(assignment_key, 86400)  # 24 hour TTL
            
            logger.info(
                f"Assigned {username} to breakout room {breakout_room_id}",
                extra={"room_id": room_id, "username": username, "breakout_room_id": breakout_room_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to assign to breakout room: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
    
    async def get_user_breakout_room(self, room_id: str, username: str) -> Optional[str]:
        """Get user's assigned breakout room."""
        try:
            redis_client = await self.redis.get_redis()
            assignment_key = f"{self.BREAKOUT_ROOMS_PREFIX}{room_id}:assignments"
            
            breakout_room_id = await redis_client.hget(assignment_key, username)
            return breakout_room_id.decode("utf-8") if breakout_room_id else None
        except Exception as e:
            logger.error(
                f"Failed to get breakout room assignment: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
            return None
    
    async def close_breakout_room(self, room_id: str, breakout_room_id: str) -> None:
        """Close a breakout room."""
        try:
            redis_client = await self.redis.get_redis()
            breakout_key = f"{self.BREAKOUT_ROOMS_PREFIX}{room_id}:{breakout_room_id}"
            
            await redis_client.delete(breakout_key)
            
            logger.info(
                f"Closed breakout room {breakout_room_id}",
                extra={"room_id": room_id, "breakout_room_id": breakout_room_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to close breakout room: {e}",
                extra={"room_id": room_id, "breakout_room_id": breakout_room_id, "error": str(e)}
            )
    
    # ========================================================================
    # Medium Term: Live Streaming Management
    # ========================================================================
    
    async def start_live_stream(self, room_id: str, stream_id: str, config: Dict[str, Any]) -> None:
        """Start a live stream."""
        try:
            redis_client = await self.redis.get_redis()
            stream_key = f"{self.LIVE_STREAMS_PREFIX}{room_id}:{stream_id}"
            
            stream_data = {
                "stream_id": stream_id,
                "status": "streaming",
                "started_at": datetime.now(timezone.utc).isoformat(),
                **config
            }
            
            await redis_client.hset(stream_key, mapping={k: str(v) for k, v in stream_data.items()})
            await redis_client.expire(stream_key, 86400)  # 24 hour TTL
            
            logger.info(
                f"Started live stream {stream_id}",
                extra={"room_id": room_id, "stream_id": stream_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to start live stream: {e}",
                extra={"room_id": room_id, "stream_id": stream_id, "error": str(e)},
                exc_info=True
            )
    
    async def stop_live_stream(self, room_id: str, stream_id: str) -> None:
        """Stop a live stream."""
        try:
            redis_client = await self.redis.get_redis()
            stream_key = f"{self.LIVE_STREAMS_PREFIX}{room_id}:{stream_id}"
            
            await redis_client.hset(stream_key, "status", "stopped")
            await redis_client.hset(stream_key, "stopped_at", datetime.now(timezone.utc).isoformat())
            
            logger.info(
                f"Stopped live stream {stream_id}",
                extra={"room_id": room_id, "stream_id": stream_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to stop live stream: {e}",
                extra={"room_id": room_id, "stream_id": stream_id, "error": str(e)}
            )
    
    async def get_active_live_streams(self, room_id: str) -> list[str]:
        """Get active live streams for a room."""
        try:
            redis_client = await self.redis.get_redis()
            pattern = f"{self.LIVE_STREAMS_PREFIX}{room_id}:*"
            
            stream_ids = []
            async for key in redis_client.scan_iter(match=pattern):
                status = await redis_client.hget(key, "status")
                if status and status.decode("utf-8") == "streaming":
                    stream_id = key.decode("utf-8").split(":")[-1]
                    stream_ids.append(stream_id)
            
            return stream_ids
        except Exception as e:
            logger.error(
                f"Failed to get active live streams: {e}",
                extra={"room_id": room_id, "error": str(e)}
            )
            return []
    
    # ========================================================================
    # Long Term: E2EE Key Management
    # ========================================================================
    
    async def store_e2ee_key(self, room_id: str, username: str, key_id: str, key_data: Dict[str, Any]) -> None:
        """Store E2EE public key."""
        try:
            redis_client = await self.redis.get_redis()
            key_key = f"{self.E2EE_KEYS_PREFIX}{room_id}:{username}:{key_id}"
            
            await redis_client.hset(key_key, mapping={k: str(v) for k, v in key_data.items()})
            await redis_client.expire(key_key, 86400)  # 24 hour TTL
            
            logger.debug(
                f"Stored E2EE key",
                extra={"room_id": room_id, "username": username, "key_id": key_id}
            )
        except Exception as e:
            logger.error(
                f"Failed to store E2EE key: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
    
    async def get_e2ee_keys(self, room_id: str, username: str) -> list[Dict[str, Any]]:
        """Get all E2EE keys for a user in a room."""
        try:
            redis_client = await self.redis.get_redis()
            pattern = f"{self.E2EE_KEYS_PREFIX}{room_id}:{username}:*"
            
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                key_data = await redis_client.hgetall(key)
                if key_data:
                    keys.append({k.decode("utf-8"): v.decode("utf-8") for k, v in key_data.items()})
            
            return keys
        except Exception as e:
            logger.error(
                f"Failed to get E2EE keys: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
            )
            return []


# Global instance
webrtc_manager = WebRtcManager()
