"""
Club WebRTC Router

FastAPI router providing WebRTC signaling endpoint and REST API
for club event rooms with membership validation and role-based permissions.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Body, Query
from fastapi.responses import JSONResponse

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.webrtc.schemas import WebRtcMessage, MessageType
from second_brain_database.webrtc.dependencies import get_current_user_ws, validate_room_id
from second_brain_database.webrtc.connection_manager import webrtc_manager
from second_brain_database.routes.auth.dependencies import get_current_user_dep as get_current_user
from second_brain_database.webrtc.monitoring import webrtc_monitoring
from second_brain_database.webrtc.rate_limiter import rate_limiter, RateLimitExceeded
from second_brain_database.webrtc.persistence import webrtc_persistence
from second_brain_database.webrtc.reconnection import reconnection_manager
from second_brain_database.webrtc.file_transfer import file_transfer_manager
from second_brain_database.webrtc.recording import recording_manager, RecordingFormat, RecordingQuality
from second_brain_database.webrtc.e2ee import e2ee_manager, KeyType
from second_brain_database.webrtc.security import (
    sanitize_html, sanitize_text, validate_file_upload,
    get_security_headers
)
from second_brain_database.webrtc.errors import (
    WebRtcError, RateLimitError, RoomFullError, PermissionDeniedError,
    get_error_status_code
)
from second_brain_database.models.club_models import ClubMemberDocument, ClubRole

logger = get_logger(prefix="[Club-WebRTC-Router]")

router = APIRouter(prefix="/clubs/webrtc", tags=["Club WebRTC"])


class ClubEventWebRTCManager:
    """Manager for club-specific WebRTC event rooms."""

    @staticmethod
    async def validate_club_membership(club_id: str, user_id: str) -> ClubMemberDocument:
        """Validate user is a member of the club."""
        try:
            from second_brain_database.managers.club_manager import ClubManager
            club_manager = ClubManager()
            member = await club_manager.check_club_access(user_id, club_id, ClubRole.MEMBER)
            if not member:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User is not a member of this club"
                )
            return member
        except Exception as e:
            logger.error(f"Failed to validate club membership: {e}", extra={"club_id": club_id, "user_id": user_id})
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Failed to validate club membership"
            )

    @staticmethod
    async def check_event_permissions(club_id: str, user_id: str, required_role: Optional[str] = None) -> ClubMemberDocument:
        """Check if user has permissions for club events."""
        member = await ClubEventWebRTCManager.validate_club_membership(club_id, user_id)

        if required_role and member.role not in ["Owner", "Admin", "Lead"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )

        return member

    @staticmethod
    def generate_event_room_id(club_id: str, event_id: str) -> str:
        """Generate a unique room ID for a club event."""
        return f"club_{club_id}_event_{event_id}"


@router.websocket("/events/{club_id}/{event_id}")
async def club_event_websocket_endpoint(
    websocket: WebSocket,
    club_id: str,
    event_id: str,
):
    """
    WebSocket endpoint for club event WebRTC signaling.

    Clients connect to this endpoint to join club event rooms.
    Membership validation and role-based permissions are enforced.

    **Authentication**: Token must be provided as query parameter: ?token=<jwt_token>

    **Club Membership**: User must be a member of the club to join event rooms
    """
    # Generate room ID for this club event
    room_id = ClubEventWebRTCManager.generate_event_room_id(club_id, event_id)

    # Validate room ID
    room_id = validate_room_id(room_id)

    # Authenticate the WebSocket connection
    user = await get_current_user_ws(websocket)
    username = user.get("username") or user.get("email")

    # Validate club membership
    try:
        member = await ClubEventWebRTCManager.validate_club_membership(club_id, username)
    except HTTPException:
        # Send error message and close connection
        error_message = WebRtcMessage.create_error(
            code="CLUB_MEMBERSHIP_REQUIRED",
            message="You must be a member of this club to join event rooms"
        )
        await websocket.send_json(error_message.model_dump())
        await websocket.close(code=1008, reason="Club membership required")
        return

    # Accept the WebSocket connection
    await websocket.accept()

    logger.info(
        f"Club event WebSocket connected: user {username} (role: {member.role}) joined club {club_id} event {event_id}",
        extra={"club_id": club_id, "event_id": event_id, "room_id": room_id, "username": username, "role": member.role}
    )

    # Subscribe to room's Redis channel
    subscription_task = None
    receive_task = None

    try:
        # Check room capacity before adding participant
        current_participants = await webrtc_manager.get_participants(room_id)
        if len(current_participants) >= settings.WEBRTC_MAX_PARTICIPANTS_PER_ROOM:
            error_message = WebRtcMessage.create_error(
                code="ROOM_FULL",
                message=f"Event room has reached maximum capacity of {settings.WEBRTC_MAX_PARTICIPANTS_PER_ROOM} participants"
            )
            await websocket.send_json(error_message.model_dump())
            await websocket.close(code=1008, reason="Room full")
            return

        # Add user to room participants
        participant_count = await webrtc_manager.add_participant(room_id, username)

        # Get current participants
        participants = await webrtc_manager.get_participants(room_id)

        # Create or update room session in MongoDB
        try:
            session_id = await webrtc_persistence.create_room_session(
                room_id=room_id,
                creator=username,
                participants=[username],
                metadata={
                    "club_id": club_id,
                    "event_id": event_id,
                    "initial_participant_count": participant_count
                }
            )
            logger.debug(f"Club event room session created/updated: {session_id}", extra={"club_id": club_id, "event_id": event_id, "room_id": room_id})
        except Exception as persist_error:
            logger.error(f"Failed to persist club event room session: {persist_error}", exc_info=True)

        # Handle reconnection and state recovery
        try:
            reconnect_info = await reconnection_manager.handle_reconnect(room_id, username)

            if reconnect_info.get("is_reconnect"):
                logger.info(
                    f"User {username} reconnected to club event {club_id}/{event_id}",
                    extra={"club_id": club_id, "event_id": event_id, "username": username}
                )

                reconnect_msg = WebRtcMessage(
                    type=MessageType.ROOM_STATE,
                    payload={
                        "reconnected": True,
                        "club_id": club_id,
                        "event_id": event_id,
                        "missed_message_count": len(reconnect_info.get("missed_messages", [])),
                        "last_sequence": reconnect_info.get("last_sequence", 0)
                    },
                    room_id=room_id,
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
                await websocket.send_json(reconnect_msg.model_dump())

                # Replay missed messages
                for missed_msg in reconnect_info.get("missed_messages", []):
                    try:
                        await websocket.send_json(missed_msg["message"])
                        await asyncio.sleep(0.01)
                    except Exception as replay_error:
                        logger.warning(f"Failed to replay message: {replay_error}")
        except Exception as reconnect_error:
            logger.error(f"Reconnection handling failed: {reconnect_error}", exc_info=True)

        # Send room state to the newly connected user
        room_state_message = WebRtcMessage(
            type=MessageType.ROOM_STATE,
            payload={
                "room_id": room_id,
                "club_id": club_id,
                "event_id": event_id,
                "participants": participants,
                "participant_count": participant_count,
                "user_role": member.role
            },
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await websocket.send_json(room_state_message.model_dump())

        # Small delay to ensure room state is processed
        await asyncio.sleep(0.1)

        # Send updated room state to all existing participants
        updated_participants = await webrtc_manager.get_participants(room_id)
        updated_room_state_message = WebRtcMessage(
            type=MessageType.ROOM_STATE,
            payload={
                "room_id": room_id,
                "club_id": club_id,
                "event_id": event_id,
                "participants": updated_participants,
                "participant_count": len(updated_participants)
            },
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, updated_room_state_message)

        # Send user-joined message
        join_message = WebRtcMessage.create_user_joined(
            user_id=username,
            username=username,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, join_message)

        # Create tasks for bidirectional communication
        async def receive_from_client():
            """Receive messages from client and publish to Redis."""
            try:
                while True:
                    data = await websocket.receive_json()
                    message = WebRtcMessage.model_validate(data)

                    # Add sender info and room
                    message.sender_id = username
                    message.room_id = room_id

                    # Apply rate limiting
                    try:
                        if message.type == MessageType.CHAT:
                            await rate_limiter.check_rate_limit("chat_message", username)
                        else:
                            await rate_limiter.check_rate_limit("websocket_message", username)
                    except RateLimitExceeded as rle:
                        error_msg = WebRtcMessage.create_error(
                            code="RATE_LIMIT_EXCEEDED",
                            message=f"Rate limit exceeded for {message.type}. Retry after {rle.retry_after}s"
                        )
                        await websocket.send_json(error_msg.model_dump())
                        continue

                    # Content security validation
                    try:
                        if message.type == MessageType.CHAT and message.payload:
                            chat_text = message.payload.get("text", "")
                            if chat_text:
                                sanitized_text = sanitize_html(chat_text)
                                if not sanitized_text and chat_text:
                                    error_msg = WebRtcMessage.create_error(
                                        code="MALICIOUS_CONTENT",
                                        message="Message contains potentially malicious content"
                                    )
                                    await websocket.send_json(error_msg.model_dump())
                                    continue
                                message.payload["text"] = sanitized_text
                    except Exception as security_error:
                        logger.warning(f"Content security validation failed: {security_error}")
                        continue

                    # Persist chat messages
                    if message.type == MessageType.CHAT:
                        try:
                            await webrtc_persistence.save_chat_message(
                                room_id=room_id,
                                sender=username,
                                message=message.payload.get("text", ""),
                                metadata={
                                    "club_id": club_id,
                                    "event_id": event_id,
                                    "message_id": message.payload.get("id"),
                                    "timestamp": message.timestamp or datetime.now(timezone.utc).isoformat()
                                }
                            )
                        except Exception as persist_error:
                            logger.error(f"Failed to persist chat message: {persist_error}", exc_info=True)

                    logger.debug(
                        f"Received {message.type} from user {username} in club event {club_id}/{event_id}",
                        extra={"club_id": club_id, "event_id": event_id, "username": username, "message_type": message.type}
                    )

                    # Buffer message for reconnection replay
                    try:
                        await reconnection_manager.buffer_message(room_id, message)
                    except Exception as buffer_error:
                        logger.warning(f"Failed to buffer message: {buffer_error}")

                    # Publish to Redis
                    await webrtc_manager.publish_to_room(room_id, message)

                    # Update user presence
                    await webrtc_manager.update_presence(room_id, username)

            except WebSocketDisconnect:
                logger.info(f"Client {username} disconnected from club event {club_id}/{event_id}")
            except Exception as e:
                logger.error(
                    f"Error receiving from client {username}: {e}",
                    extra={"club_id": club_id, "event_id": event_id, "username": username, "error": str(e)},
                    exc_info=True
                )

        async def receive_from_redis():
            """Subscribe to Redis and forward messages to client."""
            try:
                async for message in webrtc_manager.subscribe_to_room(room_id):
                    if message.sender_id != username:
                        await websocket.send_json(message.model_dump())

                        logger.debug(
                            f"Forwarded {message.type} to user {username} in club event {club_id}/{event_id}",
                            extra={"club_id": club_id, "event_id": event_id, "username": username, "message_type": message.type}
                        )

            except Exception as e:
                logger.error(
                    f"Error receiving from Redis for user {username}: {e}",
                    extra={"club_id": club_id, "event_id": event_id, "username": username, "error": str(e)},
                    exc_info=True
                )

        # Run both tasks concurrently
        receive_task = asyncio.create_task(receive_from_client())
        subscription_task = asyncio.create_task(receive_from_redis())

        done, pending = await asyncio.wait(
            [receive_task, subscription_task],
            return_when=asyncio.FIRST_COMPLETED
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info(
            f"WebSocket disconnected: user {username} left club event {club_id}/{event_id}",
            extra={"club_id": club_id, "event_id": event_id, "username": username}
        )

    except Exception as e:
        logger.error(
            f"WebSocket error for user {username} in club event {club_id}/{event_id}: {e}",
            extra={"club_id": club_id, "event_id": event_id, "username": username, "error": str(e)},
            exc_info=True
        )

        try:
            error_message = WebRtcMessage.create_error(
                code="INTERNAL_ERROR",
                message=str(e)
            )
            await websocket.send_json(error_message.model_dump())
        except:
            pass

    finally:
        # Track disconnection for reconnection support
        try:
            await reconnection_manager.track_user_state(
                room_id=room_id,
                user_id=username,
                is_connected=False
            )
        except Exception as tracking_error:
            logger.warning(f"Failed to track disconnection: {tracking_error}")

        # Cleanup: remove user from room
        try:
            remaining = await webrtc_manager.remove_participant(room_id, username)

            # Update room session in MongoDB
            try:
                if remaining == 0:
                    await webrtc_persistence.end_room_session(
                        room_id=room_id,
                        metadata={"club_id": club_id, "event_id": event_id, "last_participant": username}
                    )

                    # Cleanup reconnection state
                    try:
                        await reconnection_manager.cleanup_room(room_id)
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup reconnection state: {cleanup_error}")

                    logger.debug(f"Club event room session ended: {club_id}/{event_id}", extra={"club_id": club_id, "event_id": event_id})
            except Exception as persist_error:
                logger.error(f"Failed to end room session: {persist_error}", exc_info=True)

            # Send updated room state to remaining participants
            remaining_participants = await webrtc_manager.get_participants(room_id)
            updated_room_state_message = WebRtcMessage(
                type=MessageType.ROOM_STATE,
                payload={
                    "room_id": room_id,
                    "club_id": club_id,
                    "event_id": event_id,
                    "participants": remaining_participants,
                    "participant_count": len(remaining_participants)
                },
                room_id=room_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await webrtc_manager.publish_to_room(room_id, updated_room_state_message)

            # Send user-left message
            leave_message = WebRtcMessage.create_user_left(
                user_id=username,
                username=username,
                room_id=room_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await webrtc_manager.publish_to_room(room_id, leave_message)

            logger.info(
                f"User {username} left club event {club_id}/{event_id}, {remaining} participants remaining",
                extra={"club_id": club_id, "event_id": event_id, "username": username, "remaining_participants": remaining}
            )

        except Exception as e:
            logger.error(
                f"Error during WebSocket cleanup: {e}",
                extra={"club_id": club_id, "event_id": event_id, "username": username, "error": str(e)}
            )

        # Close WebSocket connection
        try:
            await websocket.close()
        except:
            pass

        # Cancel tasks if still running
        if subscription_task and not subscription_task.done():
            subscription_task.cancel()
        if receive_task and not receive_task.done():
            receive_task.cancel()


@router.get("/events/{club_id}/{event_id}/participants")
async def get_club_event_participants(
    club_id: str,
    event_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get list of participants currently in a club event room.

    **Authentication**: Requires valid JWT token.
    **Club Membership**: User must be a member of the club.
    """
    try:
        # Validate club membership
        username = current_user.get("username") or current_user.get("email")
        await ClubEventWebRTCManager.validate_club_membership(club_id, username)

        # Generate room ID and get participants
        room_id = ClubEventWebRTCManager.generate_event_room_id(club_id, event_id)
        room_id = validate_room_id(room_id)
        participants = await webrtc_manager.get_participants(room_id)

        return {
            "club_id": club_id,
            "event_id": event_id,
            "room_id": room_id,
            "participants": participants,
            "participant_count": len(participants)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get participants for club event {club_id}/{event_id}: {e}",
            extra={"club_id": club_id, "event_id": event_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve event participants"
        )


@router.post("/events/{club_id}/{event_id}/create-room")
async def create_club_event_room(
    club_id: str,
    event_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a WebRTC room for a club event.

    **Authentication**: Requires valid JWT token.
    **Permissions**: Only club admins/leads can create event rooms.
    """
    try:
        # Validate permissions (admin/lead required)
        username = current_user.get("username") or current_user.get("email")
        member = await ClubEventWebRTCManager.check_event_permissions(club_id, username, "Admin")

        # Generate room ID
        room_id = ClubEventWebRTCManager.generate_event_room_id(club_id, event_id)

        # Initialize room settings
        await webrtc_manager.set_room_settings(room_id, {
            "club_id": club_id,
            "event_id": event_id,
            "created_by": username,
            "max_participants": settings.WEBRTC_MAX_PARTICIPANTS_PER_ROOM,
            "enable_chat": True,
            "enable_recording": True
        })

        logger.info(
            f"Club event room created: {club_id}/{event_id} by {username}",
            extra={"club_id": club_id, "event_id": event_id, "room_id": room_id, "created_by": username}
        )

        return {
            "success": True,
            "club_id": club_id,
            "event_id": event_id,
            "room_id": room_id,
            "message": "Club event room created successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to create club event room {club_id}/{event_id}: {e}",
            extra={"club_id": club_id, "event_id": event_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create event room"
        )