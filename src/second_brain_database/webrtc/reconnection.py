"""
WebRTC Reconnection & State Recovery

Handles automatic reconnection, message buffering, and state recovery
for WebSocket connections that disconnect unexpectedly.

Features:
- Message buffering (last N messages per room)
- Automatic message replay on reconnect
- Connection quality tracking
- Missed message detection
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Deque
from collections import deque
from dataclasses import dataclass, field

from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.webrtc.schemas import WebRtcMessage

logger = get_logger(prefix="[WebRTC-Reconnection]")


@dataclass
class ConnectionState:
    """Track connection state for a user in a room."""
    user_id: str
    room_id: str
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_sequence: int = 0
    is_connected: bool = True
    reconnect_count: int = 0
    connection_quality: str = "good"  # good, fair, poor


class ReconnectionManager:
    """
    Manages reconnection state and message buffering for WebRTC rooms.
    
    Architecture:
    - Uses Redis for distributed state (works across multiple servers)
    - Buffers last N messages per room for replay
    - Tracks user connection state and sequence numbers
    - Provides automatic recovery on reconnect
    """
    
    def __init__(self, buffer_size: int = 50, buffer_ttl: int = 300):
        """
        Initialize reconnection manager.
        
        Args:
            buffer_size: Number of messages to buffer per room (default: 50)
            buffer_ttl: TTL for buffered messages in seconds (default: 5 minutes)
        """
        self.redis = redis_manager
        self.buffer_size = buffer_size
        self.buffer_ttl = buffer_ttl
        
        # Redis key prefixes
        self.MESSAGE_BUFFER_PREFIX = "webrtc:reconnect:buffer:"
        self.USER_STATE_PREFIX = "webrtc:reconnect:state:"
        self.SEQUENCE_PREFIX = "webrtc:reconnect:seq:"
        
        logger.info(f"Reconnection manager initialized (buffer_size={buffer_size}, ttl={buffer_ttl}s)")
    
    async def buffer_message(self, room_id: str, message: WebRtcMessage) -> None:
        """
        Buffer a message for potential replay on reconnect.
        
        Args:
            room_id: Room ID
            message: Message to buffer
        """
        try:
            redis_client = await self.redis.get_redis()
            
            # Add sequence number to message
            seq_key = f"{self.SEQUENCE_PREFIX}{room_id}"
            sequence = await redis_client.incr(seq_key)
            await redis_client.expire(seq_key, self.buffer_ttl)
            
            # Create buffered message with metadata
            buffered = {
                "sequence": sequence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": message.model_dump(),
            }
            
            # Add to buffer (Redis list, trimmed to buffer_size)
            buffer_key = f"{self.MESSAGE_BUFFER_PREFIX}{room_id}"
            await redis_client.lpush(buffer_key, json.dumps(buffered))
            await redis_client.ltrim(buffer_key, 0, self.buffer_size - 1)
            await redis_client.expire(buffer_key, self.buffer_ttl)
            
            logger.debug(f"Buffered message seq={sequence} for room {room_id}")
            
        except Exception as e:
            logger.error(f"Failed to buffer message: {e}", exc_info=True)
            # Don't fail the message send if buffering fails
    
    async def get_missed_messages(
        self, 
        room_id: str, 
        last_sequence: Optional[int] = None
    ) -> List[Dict]:
        """
        Get messages missed since last_sequence.
        
        Args:
            room_id: Room ID
            last_sequence: Last sequence number user received (None = get all buffered)
            
        Returns:
            List of missed messages
        """
        try:
            redis_client = await self.redis.get_redis()
            buffer_key = f"{self.MESSAGE_BUFFER_PREFIX}{room_id}"
            
            # Get all buffered messages (newest first)
            buffered_msgs = await redis_client.lrange(buffer_key, 0, -1)
            
            if not buffered_msgs:
                return []
            
            # Parse and filter messages
            missed = []
            for msg_str in buffered_msgs:
                try:
                    msg_data = json.loads(msg_str)
                    
                    # If last_sequence provided, only include newer messages
                    if last_sequence is None or msg_data["sequence"] > last_sequence:
                        missed.append(msg_data)
                except Exception as parse_error:
                    logger.warning(f"Failed to parse buffered message: {parse_error}")
            
            # Sort by sequence (oldest first)
            missed.sort(key=lambda x: x["sequence"])
            
            logger.info(f"Retrieved {len(missed)} missed messages for room {room_id}")
            return missed
            
        except Exception as e:
            logger.error(f"Failed to get missed messages: {e}", exc_info=True)
            return []
    
    async def track_user_state(
        self, 
        room_id: str, 
        user_id: str, 
        is_connected: bool,
        last_sequence: Optional[int] = None
    ) -> None:
        """
        Track user connection state.
        
        Args:
            room_id: Room ID
            user_id: User ID
            is_connected: Whether user is currently connected
            last_sequence: Last sequence number user received
        """
        try:
            redis_client = await self.redis.get_redis()
            state_key = f"{self.USER_STATE_PREFIX}{room_id}:{user_id}"
            
            state = {
                "user_id": user_id,
                "room_id": room_id,
                "is_connected": is_connected,
                "last_seen": datetime.now(timezone.utc).isoformat(),
                "last_sequence": last_sequence or 0,
            }
            
            # Store state with TTL
            await redis_client.setex(
                state_key,
                self.buffer_ttl,
                str(state)
            )
            
            logger.debug(f"Tracked state for {user_id} in {room_id}: connected={is_connected}")
            
        except Exception as e:
            logger.error(f"Failed to track user state: {e}", exc_info=True)
    
    async def get_user_state(self, room_id: str, user_id: str) -> Optional[Dict]:
        """
        Get user connection state.
        
        Args:
            room_id: Room ID
            user_id: User ID
            
        Returns:
            User state dict or None if not found
        """
        try:
            redis_client = await self.redis.get_redis()
            state_key = f"{self.USER_STATE_PREFIX}{room_id}:{user_id}"
            
            state_str = await redis_client.get(state_key)
            if state_str:
                return eval(state_str)  # Safe since we control the data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user state: {e}", exc_info=True)
            return None
    
    async def handle_reconnect(
        self, 
        room_id: str, 
        user_id: str
    ) -> Dict:
        """
        Handle user reconnection and return recovery information.
        
        Args:
            room_id: Room ID
            user_id: User ID
            
        Returns:
            Dict with missed messages and recovery info
        """
        try:
            # Get previous state
            state = await self.get_user_state(room_id, user_id)
            
            if not state:
                logger.info(f"No previous state for {user_id} in {room_id} - new connection")
                return {
                    "is_reconnect": False,
                    "missed_messages": [],
                    "last_sequence": 0
                }
            
            # Get missed messages since last sequence
            last_seq = state.get("last_sequence", 0)
            missed = await self.get_missed_messages(room_id, last_seq)
            
            # Update state to connected
            await self.track_user_state(room_id, user_id, is_connected=True, last_sequence=last_seq)
            
            logger.info(f"Reconnection handled for {user_id}: {len(missed)} missed messages")
            
            return {
                "is_reconnect": True,
                "missed_messages": missed,
                "last_sequence": last_seq,
                "disconnect_duration_seconds": self._calculate_disconnect_duration(state)
            }
            
        except Exception as e:
            logger.error(f"Failed to handle reconnect: {e}", exc_info=True)
            return {
                "is_reconnect": False,
                "missed_messages": [],
                "last_sequence": 0,
                "error": str(e)
            }
    
    def _calculate_disconnect_duration(self, state: Dict) -> Optional[float]:
        """Calculate how long user was disconnected."""
        try:
            last_seen_str = state.get("last_seen")
            if last_seen_str:
                last_seen = datetime.fromisoformat(last_seen_str.replace('Z', '+00:00'))
                duration = (datetime.now(timezone.utc) - last_seen).total_seconds()
                return duration
        except Exception as e:
            logger.warning(f"Failed to calculate disconnect duration: {e}")
        return None
    
    async def detect_connection_quality(
        self, 
        room_id: str, 
        user_id: str,
        metrics: Dict
    ) -> str:
        """
        Detect connection quality based on metrics.
        
        Args:
            room_id: Room ID
            user_id: User ID
            metrics: Dict with latency, packet_loss, jitter, etc.
            
        Returns:
            Quality string: "good", "fair", "poor"
        """
        try:
            latency = metrics.get("latency_ms", 0)
            packet_loss = metrics.get("packet_loss_percent", 0)
            jitter = metrics.get("jitter_ms", 0)
            
            # Simple heuristic (can be made more sophisticated)
            if latency > 300 or packet_loss > 5 or jitter > 50:
                quality = "poor"
            elif latency > 150 or packet_loss > 2 or jitter > 30:
                quality = "fair"
            else:
                quality = "good"
            
            # Track in user state
            state = await self.get_user_state(room_id, user_id)
            if state:
                redis_client = await self.redis.get_redis()
                state_key = f"{self.USER_STATE_PREFIX}{room_id}:{user_id}"
                state["connection_quality"] = quality
                await redis_client.setex(state_key, self.buffer_ttl, str(state))
            
            logger.debug(f"Connection quality for {user_id}: {quality} (latency={latency}ms)")
            return quality
            
        except Exception as e:
            logger.error(f"Failed to detect connection quality: {e}", exc_info=True)
            return "unknown"
    
    async def cleanup_room(self, room_id: str) -> None:
        """
        Clean up reconnection state for a room.
        
        Args:
            room_id: Room ID to clean up
        """
        try:
            redis_client = await self.redis.get_redis()
            
            # Delete message buffer
            buffer_key = f"{self.MESSAGE_BUFFER_PREFIX}{room_id}"
            await redis_client.delete(buffer_key)
            
            # Delete sequence counter
            seq_key = f"{self.SEQUENCE_PREFIX}{room_id}"
            await redis_client.delete(seq_key)
            
            # Delete all user states for this room
            pattern = f"{self.USER_STATE_PREFIX}{room_id}:*"
            cursor = 0
            while True:
                cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    await redis_client.delete(*keys)
                if cursor == 0:
                    break
            
            logger.info(f"Cleaned up reconnection state for room {room_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup room: {e}", exc_info=True)


# Global singleton instance
reconnection_manager = ReconnectionManager()
