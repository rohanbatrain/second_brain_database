"""
Club Event WebRTC Router for Second Brain Database.

Extends the existing WebRTC system to provide club-specific event rooms
with enhanced features for club meetings, presentations, and social events.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from second_brain_database.webrtc.connection_manager import webrtc_manager
from second_brain_database.routes.clubs import club_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.auth.login import get_current_user
from second_brain_database.config import settings
from second_brain_database.models.club_models import ClubMemberDocument
from second_brain_database.webrtc.schemas import (
    WebRtcMessage,
    MessageType,
    ParticipantInfo
)

logger = get_logger(prefix="[ClubWebRTC]")
router = APIRouter(prefix="/clubs/webrtc", tags=["club-webrtc"])


class ClubEventWebRTCManager:
    """
    Manages WebRTC functionality specifically for club events.

    Extends the base WebRTC manager with club-specific features:
    - Club membership validation
    - Event-based room management
    - Role-based permissions
    - Event recording and archiving
    """

    def __init__(self):
        self.webrtc_manager = webrtc_manager
        self.club_manager = club_manager
        self.logger = logger
        self.redis = redis.from_url(settings.REDIS_URL) if settings.REDIS_URL else None

    async def validate_club_membership(self, club_id: str, user_id: str) -> Optional[ClubMemberDocument]:
        """
        Validate that user is a member of the club.

        Args:
            club_id: Club ID
            user_id: User ID

        Returns:
            ClubMemberDocument if user is a member, None otherwise
        """
        try:
            # Get club details
            club = await self.club_manager.get_club(club_id)
            if not club:
                return None

            # Check if user is a member
            for member in club.members:
                if member.user_id == user_id:
                    return member

            return None

        except Exception as e:
            self.logger.error(f"Error validating club membership: {e}")
            return None

    async def create_event_room(self, club_id: str, event_id: str, creator_id: str) -> Optional[str]:
        """
        Create a WebRTC room for a club event.

        Args:
            club_id: Club ID
            event_id: Event ID
            creator_id: User ID of room creator

        Returns:
            Room ID if created successfully, None otherwise
        """
        try:
            # Validate club membership
            member = await self.validate_club_membership(club_id, creator_id)
            if not member:
                self.logger.warning(f"User {creator_id} is not a member of club {club_id}")
                return None

            # Create room ID with club and event context
            room_id = f"club_{club_id}_event_{event_id}"

            # Store room metadata in Redis
            if self.redis:
                room_metadata = {
                    "club_id": club_id,
                    "event_id": event_id,
                    "creator_id": creator_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "type": "club_event",
                    "max_participants": 50,  # Club event limit
                    "features": ["chat", "file_transfer", "recording", "breakout_rooms"]
                }

                await self.redis.setex(
                    f"webrtc:room:{room_id}:metadata",
                    86400,  # 24 hours
                    json.dumps(room_metadata)
                )

            self.logger.info(f"Created club event room {room_id} for club {club_id}, event {event_id}")
            return room_id

        except Exception as e:
            self.logger.error(f"Error creating event room: {e}")
            return None

    async def get_event_room_info(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about an event room.

        Args:
            room_id: Room ID

        Returns:
            Room information dict if found, None otherwise
        """
        try:
            if not self.redis:
                return None

            metadata = await self.redis.get(f"webrtc:room:{room_id}:metadata")
            if metadata:
                return json.loads(metadata)

            return None

        except Exception as e:
            self.logger.error(f"Error getting event room info: {e}")
            return None

    async def validate_event_room_access(self, room_id: str, user_id: str) -> bool:
        """
        Validate that user has access to the event room.

        Args:
            room_id: Room ID
            user_id: User ID

        Returns:
            True if access is granted, False otherwise
        """
        try:
            # Get room metadata
            room_info = await self.get_event_room_info(room_id)
            if not room_info:
                return False

            club_id = room_info.get("club_id")
            if not club_id:
                return False

            # Validate club membership
            member = await self.validate_club_membership(club_id, user_id)
            return member is not None

        except Exception as e:
            self.logger.error(f"Error validating event room access: {e}")
            return False


# Singleton instance
club_webrtc_manager = ClubEventWebRTCManager()


@router.post("/events/{club_id}/{event_id}/room")
async def create_event_room(
    club_id: str,
    event_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Create a WebRTC room for a club event.

    Requires club membership and appropriate permissions.
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Create the event room
        room_id = await club_webrtc_manager.create_event_room(club_id, event_id, user_id)
        if not room_id:
            raise HTTPException(
                status_code=403,
                detail="Cannot create event room. Check club membership and permissions."
            )

        return JSONResponse({
            "success": True,
            "room_id": room_id,
            "message": "Event room created successfully"
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating event room: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/events/{club_id}/{event_id}/room")
async def get_event_room(
    club_id: str,
    event_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get information about an event room.
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        room_id = f"club_{club_id}_event_{event_id}"
        room_info = await club_webrtc_manager.get_event_room_info(room_id)

        if not room_info:
            raise HTTPException(status_code=404, detail="Event room not found")

        # Validate access
        has_access = await club_webrtc_manager.validate_event_room_access(room_id, user_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to event room")

        return JSONResponse({
            "success": True,
            "room_id": room_id,
            "room_info": room_info
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event room: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.websocket("/events/{club_id}/{event_id}/room/{room_id}")
async def club_event_websocket(
    websocket: WebSocket,
    club_id: str,
    event_id: str,
    room_id: str,
    token: str = Query(..., description="JWT authentication token")
):
    """
    WebSocket endpoint for club event rooms.

    Extends the base WebRTC functionality with club-specific features.
    """
    try:
        # Authenticate user from token
        try:
            current_user = await get_current_user(token)
            user_id = current_user.get("user_id")
            username = current_user.get("username", "Unknown")
        except Exception as e:
            logger.warning(f"WebSocket authentication failed: {e}")
            await websocket.close(code=1008, reason="Authentication failed")
            return

        # Validate room access
        expected_room_id = f"club_{club_id}_event_{event_id}"
        if room_id != expected_room_id:
            await websocket.close(code=1008, reason="Invalid room ID")
            return

        has_access = await club_webrtc_manager.validate_event_room_access(room_id, user_id)
        if not has_access:
            await websocket.close(code=1008, reason="Access denied")
            return

        # Accept WebSocket connection
        await websocket.accept()
        logger.info(f"User {username} ({user_id}) joined club event room {room_id}")

        # Get user role in club for permissions
        member = await club_webrtc_manager.validate_club_membership(club_id, user_id)
        user_role = member.role if member else "member"

        # Add participant to room
        participant_info = ParticipantInfo(
            user_id=user_id,
            username=username,
            role=user_role,
            joined_at=datetime.now(timezone.utc).isoformat()
        )

        # Use the base WebRTC manager for core functionality
        await webrtc_manager.add_participant(room_id, participant_info)

        # Send welcome message
        welcome_msg = WebRtcMessage(
            type=MessageType.CHAT_MESSAGE,
            sender_id="system",
            room_id=room_id,
            payload={
                "message": f"Welcome to the club event, @{username}!",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_type": "system"
            }
        )
        await websocket.send_json(welcome_msg.model_dump())

        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                message = WebRtcMessage(**data)

                # Process message based on type
                if message.type == MessageType.OFFER:
                    # Handle WebRTC offer
                    await webrtc_manager.handle_offer(room_id, user_id, message)

                elif message.type == MessageType.ANSWER:
                    # Handle WebRTC answer
                    await webrtc_manager.handle_answer(room_id, user_id, message)

                elif message.type == MessageType.ICE_CANDIDATE:
                    # Handle ICE candidate
                    await webrtc_manager.handle_ice_candidate(room_id, user_id, message)

                elif message.type == MessageType.CHAT_MESSAGE:
                    # Handle chat message
                    await webrtc_manager.handle_chat_message(room_id, user_id, message)

                elif message.type == MessageType.FILE_SHARE_OFFER:
                    # Handle file transfer (with club permissions)
                    if user_role in ["admin", "moderator", "member"]:
                        await webrtc_manager.handle_file_transfer(room_id, user_id, message)
                    else:
                        # Send error message
                        error_msg = WebRtcMessage(
                            type=MessageType.ERROR,
                            sender_id="system",
                            room_id=room_id,
                            payload={
                                "code": "PERMISSION_DENIED",
                                "message": "Insufficient permissions for file transfer"
                            }
                        )
                        await websocket.send_json(error_msg.model_dump())

                elif message.type == MessageType.RECORDING_CONTROL:
                    # Handle recording control (admin/moderator only)
                    if user_role in ["admin", "moderator"]:
                        await webrtc_manager.handle_recording_control(room_id, user_id, message)
                    else:
                        error_msg = WebRtcMessage(
                            type=MessageType.ERROR,
                            sender_id="system",
                            room_id=room_id,
                            payload={
                                "code": "PERMISSION_DENIED",
                                "message": "Only admins and moderators can control recording"
                            }
                        )
                        await websocket.send_json(error_msg.model_dump())

                elif message.type == MessageType.BREAKOUT_ROOM_CREATE:
                    # Handle breakout rooms (admin/moderator only)
                    if user_role in ["admin", "moderator"]:
                        await webrtc_manager.handle_breakout_room(room_id, user_id, message)
                    else:
                        error_msg = WebRtcMessage(
                            type=MessageType.ERROR,
                            sender_id="system",
                            room_id=room_id,
                            payload={
                                "code": "PERMISSION_DENIED",
                                "message": "Only admins and moderators can manage breakout rooms"
                            }
                        )
                        await websocket.send_json(error_msg.model_dump())

                elif message.type == MessageType.LIVE_STREAM_START:
                    # Handle live streaming (admin only)
                    if user_role == "admin":
                        await webrtc_manager.handle_live_stream(room_id, user_id, message)
                    else:
                        error_msg = WebRtcMessage(
                            type=MessageType.ERROR,
                            sender_id="system",
                            room_id=room_id,
                            payload={
                                "code": "PERMISSION_DENIED",
                                "message": "Only admins can control live streaming"
                            }
                        )
                        await websocket.send_json(error_msg.model_dump())

                else:
                    # Unknown message type
                    logger.warning(f"Unknown message type from {user_id}: {message.type}")
                    error_msg = WebRtcMessage(
                        type=MessageType.ERROR,
                        sender_id="system",
                        room_id=room_id,
                        payload={
                            "code": "UNKNOWN_MESSAGE_TYPE",
                            "message": f"Unknown message type: {message.type}"
                        }
                    )
                    await websocket.send_json(error_msg.model_dump())

        except WebSocketDisconnect:
            logger.info(f"User {username} ({user_id}) disconnected from club event room {room_id}")

        except Exception as e:
            logger.error(f"Error in club event WebSocket: {e}")

        finally:
            # Remove participant from room
            await webrtc_manager.remove_participant(room_id, user_id)

    except Exception as e:
        logger.error(f"Error in club event WebSocket endpoint: {e}")
        if not websocket.client_state.name == "disconnected":
            await websocket.close(code=1011, reason="Internal server error")


@router.get("/events/{club_id}/{event_id}/participants")
async def get_event_participants(
    club_id: str,
    event_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Get list of participants in an event room.
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        room_id = f"club_{club_id}_event_{event_id}"

        # Validate access
        has_access = await club_webrtc_manager.validate_event_room_access(room_id, user_id)
        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to event room")

        # Get participants from base WebRTC manager
        participants = await webrtc_manager.get_room_participants(room_id)

        return JSONResponse({
            "success": True,
            "participants": participants
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting event participants: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/events/{club_id}/{event_id}/recording/start")
async def start_event_recording(
    club_id: str,
    event_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Start recording for a club event (admin/moderator only).
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Validate club membership and role
        member = await club_webrtc_manager.validate_club_membership(club_id, user_id)
        if not member or member.role not in ["admin", "moderator"]:
            raise HTTPException(status_code=403, detail="Only admins and moderators can control recording")

        room_id = f"club_{club_id}_event_{event_id}"

        # Start recording using base WebRTC manager
        success = await webrtc_manager.start_recording(room_id, user_id)

        if success:
            return JSONResponse({
                "success": True,
                "message": "Event recording started"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to start recording")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting event recording: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/events/{club_id}/{event_id}/recording/stop")
async def stop_event_recording(
    club_id: str,
    event_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Stop recording for a club event (admin/moderator only).
    """
    try:
        user_id = current_user.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="User not authenticated")

        # Validate club membership and role
        member = await club_webrtc_manager.validate_club_membership(club_id, user_id)
        if not member or member.role not in ["admin", "moderator"]:
            raise HTTPException(status_code=403, detail="Only admins and moderators can control recording")

        room_id = f"club_{club_id}_event_{event_id}"

        # Stop recording using base WebRTC manager
        recording_data = await webrtc_manager.stop_recording(room_id, user_id)

        if recording_data:
            return JSONResponse({
                "success": True,
                "message": "Event recording stopped",
                "recording": recording_data
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to stop recording")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping event recording: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")