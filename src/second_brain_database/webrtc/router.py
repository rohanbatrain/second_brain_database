"""
WebRTC Router

FastAPI router providing WebSocket signaling endpoint and REST API
for WebRTC configuration.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Body, Query
from fastapi.responses import JSONResponse

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.webrtc.schemas import WebRtcMessage, WebRtcConfig, IceServerConfig, MessageType
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

logger = get_logger(prefix="[WebRTC-Router]")

router = APIRouter(prefix="/webrtc", tags=["WebRTC"])


@router.websocket("/ws/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
):
    """
    WebSocket endpoint for WebRTC signaling.
    
    Clients connect to this endpoint to join a room and exchange signaling messages.
    Messages are published to Redis and distributed to all clients in the room across
    all server instances.
    
    **Authentication**: Token must be provided as query parameter: ?token=<jwt_token>
    
    **Message Flow**:
    1. Client sends signaling message (offer, answer, ICE candidate) to server
    2. Server validates and publishes message to Redis room channel
    3. All server instances subscribed to that room receive the message
    4. Each instance forwards the message to its connected WebSocket clients in that room
    """
    # Validate room ID
    room_id = validate_room_id(room_id)
    
    # Authenticate the WebSocket connection
    user = await get_current_user_ws(websocket)
    username = user.get("username") or user.get("email")  # Username-centric, consistent with codebase
    
    # Accept the WebSocket connection
    await websocket.accept()
    
    logger.info(
        f"WebSocket connected: user {username} joined room {room_id}",
        extra={"room_id": room_id, "username": username}
    )
    
    # Subscribe to room's Redis channel
    subscription_task = None
    receive_task = None
    
    try:
        # Check room capacity before adding participant (production capacity management)
        current_participants = await webrtc_manager.get_participants(room_id)
        if len(current_participants) >= settings.WEBRTC_MAX_PARTICIPANTS_PER_ROOM:
            # Room is full
            error_message = WebRtcMessage.create_error(
                code="ROOM_FULL",
                message=f"Room has reached maximum capacity of {settings.WEBRTC_MAX_PARTICIPANTS_PER_ROOM} participants"
            )
            await websocket.send_json(error_message.model_dump())
            await websocket.close(code=1008, reason="Room full")
            logger.warning(
                f"User {username} denied entry to room {room_id} - room full ({len(current_participants)}/{settings.WEBRTC_MAX_PARTICIPANTS_PER_ROOM})",
                extra={"room_id": room_id, "username": username, "capacity": settings.WEBRTC_MAX_PARTICIPANTS_PER_ROOM}
            )
            return
        
        # Add user to room participants
        participant_count = await webrtc_manager.add_participant(room_id, username)
        
        # Get current participants
        participants = await webrtc_manager.get_participants(room_id)
        
        # Create or update room session in MongoDB (production persistence)
        try:
            session_id = await webrtc_persistence.create_room_session(
                room_id=room_id,
                creator=username,
                participants=[username],
                metadata={"initial_participant_count": participant_count}
            )
            logger.debug(f"Room session created/updated: {session_id}", extra={"room_id": room_id})
        except Exception as persist_error:
            logger.error(f"Failed to persist room session: {persist_error}", exc_info=True)
            # Continue anyway - persistence failure shouldn't block WebRTC
        
        # Handle reconnection and state recovery (production feature)
        try:
            reconnect_info = await reconnection_manager.handle_reconnect(room_id, username)
            
            if reconnect_info.get("is_reconnect"):
                logger.info(
                    f"User {username} reconnected to {room_id} after {reconnect_info.get('disconnect_duration_seconds', 0):.1f}s",
                    extra={"room_id": room_id, "username": username, "missed_count": len(reconnect_info.get("missed_messages", []))}
                )
                
                # Send reconnection acknowledgment with recovery info
                reconnect_msg = WebRtcMessage(
                    type=MessageType.ROOM_STATE,
                    payload={
                        "reconnected": True,
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
                        await asyncio.sleep(0.01)  # Small delay to avoid overwhelming client
                    except Exception as replay_error:
                        logger.warning(f"Failed to replay message: {replay_error}")
        except Exception as reconnect_error:
            logger.error(f"Reconnection handling failed: {reconnect_error}", exc_info=True)
            # Continue anyway - reconnection failure shouldn't block connection
        
        # Send room state to the newly connected user first
        room_state_message = WebRtcMessage(
            type=MessageType.ROOM_STATE,
            payload={
                "room_id": room_id,
                "participants": participants,
                "participant_count": participant_count
            },
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await websocket.send_json(room_state_message.model_dump())
        
        # Small delay to ensure room state is processed first
        await asyncio.sleep(0.1)
        
        # Send updated room state to all existing participants (so they see the new user)
        updated_participants = await webrtc_manager.get_participants(room_id)
        updated_room_state_message = WebRtcMessage(
            type=MessageType.ROOM_STATE,
            payload={
                "room_id": room_id,
                "participants": updated_participants,
                "participant_count": len(updated_participants)
            },
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, updated_room_state_message)
        
        # Also notify with user-joined message for event tracking
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
                    # Receive message from client
                    data = await websocket.receive_json()
                    
                    # Parse and validate message
                    message = WebRtcMessage.model_validate(data)
                    
                    # Add sender info and room
                    message.sender_id = username
                    message.room_id = room_id
                    
                    # Apply rate limiting based on message type (production hardening)
                    try:
                        if message.type == MessageType.CHAT:
                            await rate_limiter.check_rate_limit("chat_message", username)
                        elif message.type == MessageType.HAND_RAISE:
                            await rate_limiter.check_rate_limit("hand_raise", username)
                        elif message.type == MessageType.REACTION:
                            await rate_limiter.check_rate_limit("reaction", username)
                        elif message.type == MessageType.FILE_SHARE:
                            await rate_limiter.check_rate_limit("file_share", username)
                        else:
                            # Generic WebSocket message rate limit
                            await rate_limiter.check_rate_limit("websocket_message", username)
                    except RateLimitExceeded as rle:
                        error_msg = WebRtcMessage.create_error(
                            code="RATE_LIMIT_EXCEEDED",
                            message=f"Rate limit exceeded for {message.type}. Retry after {rle.retry_after}s"
                        )
                        await websocket.send_json(error_msg.model_dump())
                        continue  # Skip this message
                    
                    # Content security validation (production hardening)
                    try:
                        if message.type == MessageType.CHAT and message.payload:
                            chat_text = message.payload.get("text", "")
                            if chat_text:
                                # Sanitize the message (removes XSS/malicious content)
                                sanitized_text = sanitize_html(chat_text)
                                if not sanitized_text and chat_text:  # Content was entirely malicious
                                    error_msg = WebRtcMessage.create_error(
                                        code="MALICIOUS_CONTENT",
                                        message="Message contains potentially malicious content"
                                    )
                                    await websocket.send_json(error_msg.model_dump())
                                    continue
                                
                                # Update payload with sanitized text
                                message.payload["text"] = sanitized_text
                        
                        elif message.type == MessageType.FILE_SHARE and message.payload:
                            file_info = message.payload.get("file", {})
                            filename = file_info.get("name", "")
                            file_size = file_info.get("size", 0)
                            
                            if filename and file_size:
                                # Validate file type and size
                                is_valid, validation_error = validate_file_upload(filename, file_size)
                                if not is_valid:
                                    error_msg = WebRtcMessage.create_error(
                                        code="FILE_VALIDATION_FAILED",
                                        message=validation_error or "File validation failed"
                                    )
                                    await websocket.send_json(error_msg.model_dump())
                                    continue
                    
                    except Exception as security_error:
                        logger.warning(f"Content security validation failed: {security_error}")
                        error_msg = WebRtcMessage.create_error(
                            code="CONTENT_SECURITY_ERROR",
                            message=str(security_error)
                        )
                        await websocket.send_json(error_msg.model_dump())
                        continue
                    
                    # Persist chat messages to MongoDB (production persistence)
                    if message.type == MessageType.CHAT:
                        try:
                            await webrtc_persistence.save_chat_message(
                                room_id=room_id,
                                sender=username,
                                message=message.payload.get("text", ""),
                                metadata={
                                    "message_id": message.payload.get("id"),
                                    "timestamp": message.timestamp or datetime.now(timezone.utc).isoformat()
                                }
                            )
                        except Exception as persist_error:
                            logger.error(f"Failed to persist chat message: {persist_error}", exc_info=True)
                    
                    # Track analytics events (production monitoring)
                    if message.type in [MessageType.OFFER, MessageType.ANSWER, MessageType.ICE_CANDIDATE]:
                        try:
                            await webrtc_persistence.save_analytics_event(
                                room_id=room_id,
                                event_type=f"webrtc_{message.type.value}",
                                user=username,
                                metadata={"message_type": message.type.value}
                            )
                        except Exception as analytics_error:
                            logger.error(f"Failed to save analytics: {analytics_error}", exc_info=True)
                    
                    logger.debug(
                        f"Received {message.type} from user {username} in room {room_id}",
                        extra={
                            "room_id": room_id,
                            "username": username,
                            "message_type": message.type
                        }
                    )
                    
                    # Buffer message for reconnection replay (production feature)
                    try:
                        await reconnection_manager.buffer_message(room_id, message)
                    except Exception as buffer_error:
                        logger.warning(f"Failed to buffer message: {buffer_error}")
                        # Continue anyway
                    
                    # Publish to Redis (will be received by all subscribed instances)
                    await webrtc_manager.publish_to_room(room_id, message)
                    
                    # Update user presence (heartbeat)
                    await webrtc_manager.update_presence(room_id, username)
                    
            except WebSocketDisconnect:
                logger.info(f"Client {username} disconnected from room {room_id}")
            except Exception as e:
                logger.error(
                    f"Error receiving from client {username}: {e}",
                    extra={"room_id": room_id, "username": username, "error": str(e)},
                    exc_info=True
                )
        
        async def receive_from_redis():
            """Subscribe to Redis and forward messages to client."""
            try:
                async for message in webrtc_manager.subscribe_to_room(room_id):
                    # Don't send messages back to the sender
                    if message.sender_id != username:
                        await websocket.send_json(message.model_dump())
                        
                        logger.debug(
                            f"Forwarded {message.type} to user {username} in room {room_id}",
                            extra={
                                "room_id": room_id,
                                "username": username,
                                "message_type": message.type,
                                "sender_id": message.sender_id
                            }
                        )
                        
            except Exception as e:
                logger.error(
                    f"Error receiving from Redis for user {username}: {e}",
                    extra={"room_id": room_id, "username": username, "error": str(e)},
                    exc_info=True
                )
        
        # Run both tasks concurrently
        receive_task = asyncio.create_task(receive_from_client())
        subscription_task = asyncio.create_task(receive_from_redis())
        
        # Wait for either task to complete (typically on disconnect)
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
            f"WebSocket disconnected: user {username} left room {room_id}",
            extra={"room_id": room_id, "username": username}
        )
        
    except Exception as e:
        logger.error(
            f"WebSocket error for user {username} in room {room_id}: {e}",
            extra={"room_id": room_id, "username": username, "error": str(e)},
            exc_info=True
        )
        
        # Send error message to client
        try:
            error_message = WebRtcMessage.create_error(
                code="INTERNAL_ERROR",
                message=str(e)
            )
            await websocket.send_json(error_message.model_dump())
        except:
            pass
        
    finally:
        # Track disconnection for reconnection support (production feature)
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
            
            # Update room session in MongoDB (production persistence)
            try:
                if remaining == 0:
                    # Last participant leaving - end the session
                    await webrtc_persistence.end_room_session(
                        room_id=room_id,
                        metadata={"last_participant": username}
                    )
                    
                    # Cleanup reconnection state for empty room (production feature)
                    try:
                        await reconnection_manager.cleanup_room(room_id)
                    except Exception as cleanup_error:
                        logger.warning(f"Failed to cleanup reconnection state: {cleanup_error}")
                    
                    logger.debug(f"Room session ended: {room_id}", extra={"room_id": room_id})
            except Exception as persist_error:
                logger.error(f"Failed to end room session: {persist_error}", exc_info=True)
            
            # Send updated room state to remaining participants
            remaining_participants = await webrtc_manager.get_participants(room_id)
            updated_room_state_message = WebRtcMessage(
                type=MessageType.ROOM_STATE,
                payload={
                    "room_id": room_id,
                    "participants": remaining_participants,
                    "participant_count": len(remaining_participants)
                },
                room_id=room_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await webrtc_manager.publish_to_room(room_id, updated_room_state_message)
            
            # Also notify with user-left message for event tracking
            leave_message = WebRtcMessage.create_user_left(
                user_id=username,
                username=username,
                room_id=room_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await webrtc_manager.publish_to_room(room_id, leave_message)
            
            logger.info(
                f"User {username} left room {room_id}, {remaining} participants remaining",
                extra={
                    "room_id": room_id,
                    "username": username,
                    "remaining_participants": remaining
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error during WebSocket cleanup: {e}",
                extra={"room_id": room_id, "username": username, "error": str(e)}
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


@router.get("/config", response_model=WebRtcConfig)
async def get_webrtc_config(
    current_user: dict = Depends(get_current_user)
):
    """
    Get WebRTC configuration including STUN/TURN servers.
    
    This endpoint provides the ICE server configuration needed for WebRTC
    connections. Clients should call this endpoint before establishing
    WebRTC connections.
    
    **Authentication**: Requires valid JWT token.
    
    **Returns**:
    - ICE servers (STUN/TURN)
    - Transport policies
    - Other WebRTC configuration
    """
    try:
        # Build ICE servers list
        ice_servers = []
        
        # Add STUN servers
        if settings.WEBRTC_STUN_URLS:
            stun_urls = [url.strip() for url in settings.WEBRTC_STUN_URLS.split(",")]
            ice_servers.append(IceServerConfig(urls=stun_urls))
        
        # Add TURN servers (if configured)
        if settings.WEBRTC_TURN_URLS:
            turn_urls = [url.strip() for url in settings.WEBRTC_TURN_URLS.split(",")]
            turn_server = IceServerConfig(
                urls=turn_urls,
                username=settings.WEBRTC_TURN_USERNAME,
                credential=settings.WEBRTC_TURN_CREDENTIAL
            )
            ice_servers.append(turn_server)
        
        # Fallback to public STUN servers if nothing configured
        if not ice_servers:
            ice_servers.append(IceServerConfig(
                urls=["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"]
            ))
        
        config = WebRtcConfig(
            ice_servers=ice_servers,
            ice_transport_policy=settings.WEBRTC_ICE_TRANSPORT_POLICY,
            bundle_policy=settings.WEBRTC_BUNDLE_POLICY,
            rtcp_mux_policy=settings.WEBRTC_RTCP_MUX_POLICY
        )
        
        username = current_user.get("username") or current_user.get("email")
        logger.info(
            f"Provided WebRTC config to user {username}",
            extra={"username": username, "ice_server_count": len(ice_servers)}
        )
        
        return config
        
    except Exception as e:
        logger.error(
            f"Failed to get WebRTC config: {e}",
            extra={"error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve WebRTC configuration"
        )


@router.get("/rooms/{room_id}/participants")
async def get_room_participants(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get list of participants currently in a room.
    
    **Authentication**: Requires valid JWT token.
    
    **Returns**:
    - List of participants with user IDs and usernames
    - Participant count
    """
    try:
        room_id = validate_room_id(room_id)
        participants = await webrtc_manager.get_participants(room_id)
        
        return {
            "room_id": room_id,
            "participants": participants,
            "participant_count": len(participants)
        }
        
    except Exception as e:
        logger.error(
            f"Failed to get participants for room {room_id}: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve room participants"
        )


# ============================================================================
# Phase 1: Room Permissions & Roles
# ============================================================================

@router.post("/rooms/{room_id}/roles/{user_id}")
async def set_user_role(
    room_id: str,
    user_id: str,
    role: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Set a user's role in a room.
    
    **Authentication**: Requires valid JWT token with management permissions.
    
    **Roles**: host, moderator, participant, observer
    """
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check if current user has permission to manage roles
        current_role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if current_role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to manage roles"
            )
        
        # Set the role
        await webrtc_manager.set_user_role(room_id, user_id, role)
        
        # Notify room about role change
        from second_brain_database.webrtc.schemas import RoomRole
        role_enum = RoomRole(role)
        role_message = WebRtcMessage.create_role_update(
            user_id=user_id,
            role=role_enum,
            updated_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, role_message)
        
        return {"success": True, "user_id": user_id, "role": role}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to set role: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set user role"
        )


@router.get("/rooms/{room_id}/roles/{user_id}")
async def get_user_role(
    room_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a user's role in a room."""
    try:
        room_id = validate_room_id(room_id)
        role = await webrtc_manager.get_user_role(room_id, user_id)
        
        return {"user_id": user_id, "role": role}
        
    except Exception as e:
        logger.error(
            f"Failed to get role: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user role"
        )


@router.post("/rooms/{room_id}/permissions/{user_id}")
async def set_user_permissions(
    room_id: str,
    user_id: str,
    permissions: dict,
    current_user: dict = Depends(get_current_user)
):
    """Set a user's permissions in a room."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check if current user has permission to manage permissions
        current_role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if current_role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to manage permissions"
            )
        
        # Set permissions
        await webrtc_manager.set_user_permissions(room_id, user_id, permissions)
        
        # Notify room about permission change
        from second_brain_database.webrtc.schemas import RoomPermissions
        perm_obj = RoomPermissions(**permissions)
        perm_message = WebRtcMessage.create_permission_update(
            user_id=user_id,
            permissions=perm_obj,
            updated_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, perm_message)
        
        return {"success": True, "user_id": user_id, "permissions": permissions}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to set permissions: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set permissions"
        )


@router.get("/rooms/{room_id}/permissions/{user_id}")
async def get_user_permissions(
    room_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get a user's permissions in a room."""
    try:
        room_id = validate_room_id(room_id)
        permissions = await webrtc_manager.get_user_permissions(room_id, user_id)
        
        return {"user_id": user_id, "permissions": permissions}
        
    except Exception as e:
        logger.error(
            f"Failed to get permissions: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get permissions"
        )


# ============================================================================
# Phase 2: Analytics Dashboard
# ============================================================================

@router.get("/rooms/{room_id}/analytics")
async def get_room_analytics(
    room_id: str,
    limit: int = 100,
    current_user: dict = Depends(get_current_user)
):
    """
    Get analytics events for a room.
    
    **Authentication**: Requires valid JWT token.
    
    **Parameters**:
    - limit: Maximum number of events to return (default 100)
    """
    try:
        room_id = validate_room_id(room_id)
        events = await webrtc_manager.get_room_analytics(room_id, limit)
        
        return {
            "room_id": room_id,
            "events": events,
            "count": len(events)
        }
        
    except Exception as e:
        logger.error(
            f"Failed to get analytics: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics"
        )


@router.get("/rooms/{room_id}/analytics/summary")
async def get_room_analytics_summary(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get analytics summary for a room."""
    try:
        room_id = validate_room_id(room_id)
        events = await webrtc_manager.get_room_analytics(room_id, limit=1000)
        
        # Calculate summary statistics
        summary = {
            "total_events": len(events),
            "event_types": {},
            "unique_users": set(),
            "peak_participants": 0
        }
        
        for event in events:
            event_type = event.get("event_type", "unknown")
            summary["event_types"][event_type] = summary["event_types"].get(event_type, 0) + 1
            
            if "username" in event:
                summary["unique_users"].add(event["username"])
        
        summary["unique_users"] = len(summary["unique_users"])
        
        # Get current participants
        participants = await webrtc_manager.get_participants(room_id)
        summary["current_participants"] = len(participants)
        
        return summary
        
    except Exception as e:
        logger.error(
            f"Failed to get analytics summary: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve analytics summary"
        )


# ============================================================================
# Phase 2: Recording Management
# ============================================================================

@router.post("/rooms/{room_id}/recordings/start")
async def start_recording(
    room_id: str,
    recording_id: str,
    metadata: Optional[dict] = None,
    current_user: dict = Depends(get_current_user)
):
    """Start a recording session."""
    try:
        room_id = validate_room_id(room_id)
        user_id = current_user.get("username") or current_user.get("email")
        
        # Check if user has recording permission
        permissions = await webrtc_manager.get_user_permissions(room_id, user_id)
        if not permissions.get("can_record", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to start recording"
            )
        
        # Start recording
        recording_metadata = metadata or {}
        recording_metadata["user_id"] = user_id
        await webrtc_manager.start_recording(room_id, recording_id, recording_metadata)
        
        # Notify room
        recording_message = WebRtcMessage.create_recording_control(
            action="start",
            recording_id=recording_id,
            user_id=user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, recording_message)
        
        return {"success": True, "recording_id": recording_id, "status": "recording"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to start recording: {e}",
            extra={"room_id": room_id, "recording_id": recording_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start recording"
        )


@router.post("/rooms/{room_id}/recordings/{recording_id}/stop")
async def stop_recording(
    room_id: str,
    recording_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Stop a recording session."""
    try:
        room_id = validate_room_id(room_id)
        user_id = current_user.get("username") or current_user.get("email")
        
        # Stop recording
        await webrtc_manager.stop_recording(room_id, recording_id)
        
        # Notify room
        recording_message = WebRtcMessage.create_recording_control(
            action="stop",
            recording_id=recording_id,
            user_id=user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, recording_message)
        
        return {"success": True, "recording_id": recording_id, "status": "stopped"}
        
    except Exception as e:
        logger.error(
            f"Failed to stop recording: {e}",
            extra={"room_id": room_id, "recording_id": recording_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop recording"
        )


@router.get("/rooms/{room_id}/recordings")
async def get_active_recordings(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get list of active recordings in a room."""
    try:
        room_id = validate_room_id(room_id)
        recordings = await webrtc_manager.get_active_recordings(room_id)
        
        return {
            "room_id": room_id,
            "active_recordings": recordings,
            "count": len(recordings)
        }
        
    except Exception as e:
        logger.error(
            f"Failed to get recordings: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve recordings"
        )


# ============================================================================
# Immediate Features: Participant List Enhancements
# ============================================================================

@router.get("/rooms/{room_id}/participants/enhanced")
async def get_enhanced_participants(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get enhanced participant information including media states.
    
    **Authentication**: Requires valid JWT token.
    """
    try:
        room_id = validate_room_id(room_id)
        participants = await webrtc_manager.get_participants(room_id)
        
        # Enhance with additional info
        enhanced_participants = []
        for participant in participants:
            username = participant.get("username")
            if username:
                info = await webrtc_manager.get_participant_info(room_id, username)
                enhanced_participants.append({**participant, **info})
            else:
                enhanced_participants.append(participant)
        
        return {
            "room_id": room_id,
            "participants": enhanced_participants,
            "participant_count": len(enhanced_participants)
        }
        
    except Exception as e:
        logger.error(
            f"Failed to get enhanced participants: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve enhanced participants"
        )


@router.post("/rooms/{room_id}/participants/{user_id}/info")
async def update_participant_info(
    room_id: str,
    user_id: str,
    info: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update participant information."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Only user can update their own info
        if current_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Can only update own participant info"
            )
        
        await webrtc_manager.update_participant_info(room_id, user_id, info)
        
        # Notify room
        from second_brain_database.webrtc.schemas import ParticipantInfo
        participant = ParticipantInfo(**info)
        participant_message = WebRtcMessage.create_participant_update(
            participant=participant,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, participant_message)
        
        return {"success": True, "user_id": user_id, "info": info}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update participant info: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update participant info"
        )


# ============================================================================
# Immediate Features: Room Settings
# ============================================================================

@router.get("/rooms/{room_id}/settings")
async def get_room_settings(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get room settings."""
    try:
        room_id = validate_room_id(room_id)
        settings = await webrtc_manager.get_room_settings(room_id)
        
        return {"room_id": room_id, "settings": settings}
        
    except Exception as e:
        logger.error(
            f"Failed to get room settings: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve room settings"
        )


@router.post("/rooms/{room_id}/settings")
async def update_room_settings(
    room_id: str,
    settings: dict,
    current_user: dict = Depends(get_current_user)
):
    """Update room settings."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to update room settings"
            )
        
        await webrtc_manager.set_room_settings(room_id, settings)
        
        # Notify room
        from second_brain_database.webrtc.schemas import RoomSettings
        settings_obj = RoomSettings(**settings)
        settings_message = WebRtcMessage.create_room_settings_update(
            settings=settings_obj,
            updated_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, settings_message)
        
        return {"success": True, "room_id": room_id, "settings": settings}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to update room settings: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update room settings"
        )


# ============================================================================
# Immediate Features: Hand Raise Queue
# ============================================================================

@router.post("/rooms/{room_id}/hand-raise")
async def raise_hand(
    room_id: str,
    raised: bool = True,
    current_user: dict = Depends(get_current_user)
):
    """Raise or lower hand."""
    try:
        room_id = validate_room_id(room_id)
        username = current_user.get("username") or current_user.get("email")
        timestamp = datetime.now(timezone.utc).isoformat()
        
        if raised:
            position = await webrtc_manager.add_to_hand_raise_queue(room_id, username, timestamp)
        else:
            await webrtc_manager.remove_from_hand_raise_queue(room_id, username)
            position = None
        
        # Notify room
        hand_raise_message = WebRtcMessage.create_hand_raise(
            user_id=username,
            username=username,
            raised=raised,
            room_id=room_id,
            timestamp=timestamp
        )
        await webrtc_manager.publish_to_room(room_id, hand_raise_message)
        
        # Send updated queue
        queue = await webrtc_manager.get_hand_raise_queue(room_id)
        from second_brain_database.webrtc.schemas import HandRaiseQueueEntry
        queue_entries = [HandRaiseQueueEntry(**entry) for entry in queue]
        queue_message = WebRtcMessage.create_hand_raise_queue(
            queue=queue_entries,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, queue_message)
        
        return {"success": True, "raised": raised, "position": position}
        
    except Exception as e:
        logger.error(
            f"Failed to raise/lower hand: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to raise/lower hand"
        )


@router.get("/rooms/{room_id}/hand-raise/queue")
async def get_hand_raise_queue_endpoint(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get hand raise queue."""
    try:
        room_id = validate_room_id(room_id)
        queue = await webrtc_manager.get_hand_raise_queue(room_id)
        
        return {"room_id": room_id, "queue": queue, "count": len(queue)}
        
    except Exception as e:
        logger.error(
            f"Failed to get hand raise queue: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hand raise queue"
        )


# ============================================================================
# Short Term: Waiting Room
# ============================================================================

@router.get("/rooms/{room_id}/waiting-room")
async def get_waiting_room(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get waiting room participants."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view waiting room"
            )
        
        participants = await webrtc_manager.get_waiting_room_participants(room_id)
        
        return {
            "room_id": room_id,
            "participants": participants,
            "count": len(participants)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get waiting room: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve waiting room"
        )


@router.post("/rooms/{room_id}/waiting-room/{user_id}/admit")
async def admit_from_waiting_room(
    room_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Admit user from waiting room."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to admit from waiting room"
            )
        
        await webrtc_manager.remove_from_waiting_room(room_id, user_id)
        
        # Notify room
        admit_message = WebRtcMessage.create_waiting_room_admit(
            user_id=user_id,
            actioned_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, admit_message)
        
        return {"success": True, "user_id": user_id, "action": "admitted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to admit from waiting room: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to admit from waiting room"
        )


@router.post("/rooms/{room_id}/waiting-room/{user_id}/reject")
async def reject_from_waiting_room(
    room_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Reject user from waiting room."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to reject from waiting room"
            )
        
        await webrtc_manager.remove_from_waiting_room(room_id, user_id)
        
        # Notify room
        reject_message = WebRtcMessage.create_waiting_room_reject(
            user_id=user_id,
            actioned_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, reject_message)
        
        return {"success": True, "user_id": user_id, "action": "rejected"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to reject from waiting room: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject from waiting room"
        )


# ============================================================================
# Medium Term: Breakout Rooms
# ============================================================================

@router.post("/rooms/{room_id}/breakout-rooms")
async def create_breakout_room(
    room_id: str,
    config: dict,
    current_user: dict = Depends(get_current_user)
):
    """Create a breakout room."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to create breakout rooms"
            )
        
        breakout_room_id = config.get("breakout_room_id")
        await webrtc_manager.create_breakout_room(room_id, breakout_room_id, config)
        
        # Notify room
        from second_brain_database.webrtc.schemas import BreakoutRoomConfig
        breakout_config = BreakoutRoomConfig(**config)
        breakout_message = WebRtcMessage.create_breakout_room_create(
            config=breakout_config,
            created_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, breakout_message)
        
        return {"success": True, "breakout_room_id": breakout_room_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to create breakout room: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create breakout room"
        )


@router.post("/rooms/{room_id}/breakout-rooms/{breakout_room_id}/assign/{user_id}")
async def assign_to_breakout_room(
    room_id: str,
    breakout_room_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Assign user to breakout room."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to assign to breakout rooms"
            )
        
        await webrtc_manager.assign_to_breakout_room(room_id, user_id, breakout_room_id)
        
        # Notify room
        assign_message = WebRtcMessage.create_breakout_room_assign(
            user_id=user_id,
            breakout_room_id=breakout_room_id,
            assigned_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, assign_message)
        
        return {"success": True, "user_id": user_id, "breakout_room_id": breakout_room_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to assign to breakout room: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign to breakout room"
        )


@router.delete("/rooms/{room_id}/breakout-rooms/{breakout_room_id}")
async def close_breakout_room_endpoint(
    room_id: str,
    breakout_room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Close a breakout room."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to close breakout rooms"
            )
        
        await webrtc_manager.close_breakout_room(room_id, breakout_room_id)
        
        # Notify room
        close_message = WebRtcMessage.create_breakout_room_close(
            breakout_room_id=breakout_room_id,
            closed_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, close_message)
        
        return {"success": True, "breakout_room_id": breakout_room_id, "status": "closed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to close breakout room: {e}",
            extra={"room_id": room_id, "breakout_room_id": breakout_room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to close breakout room"
        )


# ============================================================================
# Medium Term: Live Streaming
# ============================================================================

@router.post("/rooms/{room_id}/live-streams/start")
async def start_live_stream_endpoint(
    room_id: str,
    config: dict,
    current_user: dict = Depends(get_current_user)
):
    """Start a live stream."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to start live stream"
            )
        
        stream_id = config.get("stream_id")
        await webrtc_manager.start_live_stream(room_id, stream_id, config)
        
        # Notify room
        from second_brain_database.webrtc.schemas import LiveStreamConfig
        stream_config = LiveStreamConfig(**config)
        stream_message = WebRtcMessage.create_live_stream_start(
            config=stream_config,
            started_by=current_user_id,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, stream_message)
        
        return {"success": True, "stream_id": stream_id, "status": "streaming"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to start live stream: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start live stream"
        )


@router.post("/rooms/{room_id}/live-streams/{stream_id}/stop")
async def stop_live_stream_endpoint(
    room_id: str,
    stream_id: str,
    duration_seconds: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """Stop a live stream."""
    try:
        room_id = validate_room_id(room_id)
        current_user_id = current_user.get("username") or current_user.get("email")
        
        # Check permissions
        role = await webrtc_manager.get_user_role(room_id, current_user_id)
        if role not in ["host", "moderator"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to stop live stream"
            )
        
        await webrtc_manager.stop_live_stream(room_id, stream_id)
        
        # Notify room
        stop_message = WebRtcMessage.create_live_stream_stop(
            stream_id=stream_id,
            stopped_by=current_user_id,
            duration_seconds=duration_seconds,
            room_id=room_id,
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        await webrtc_manager.publish_to_room(room_id, stop_message)
        
        return {"success": True, "stream_id": stream_id, "status": "stopped"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to stop live stream: {e}",
            extra={"room_id": room_id, "stream_id": stream_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stop live stream"
        )


@router.get("/rooms/{room_id}/live-streams")
async def get_active_live_streams_endpoint(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get active live streams."""
    try:
        room_id = validate_room_id(room_id)
        streams = await webrtc_manager.get_active_live_streams(room_id)
        
        return {
            "room_id": room_id,
            "active_streams": streams,
            "count": len(streams)
        }
        
    except Exception as e:
        logger.error(
            f"Failed to get live streams: {e}",
            extra={"room_id": room_id, "error": str(e)},
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve live streams"
        )


# ============================================================================
# HEALTH & MONITORING ENDPOINTS (Production Hardening)
# ============================================================================

@router.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns status of all WebRTC dependencies:
    - Redis (state storage, pub/sub)
    - MongoDB (persistence)
    - Overall service health
    """
    health = await webrtc_monitoring.check_health()
    
    # Return appropriate status code based on health
    status_code_map = {
        "healthy": status.HTTP_200_OK,
        "degraded": status.HTTP_200_OK,  # Still operational
        "unhealthy": status.HTTP_503_SERVICE_UNAVAILABLE
    }
    
    return JSONResponse(
        status_code=status_code_map.get(health.status, status.HTTP_500_INTERNAL_SERVER_ERROR),
        content=health.model_dump()
    )


@router.get("/webrtc-metrics")
async def get_webrtc_metrics():
    """
    Get real-time WebRTC-specific metrics.
    
    Note: Global Prometheus metrics are available at /metrics (main app endpoint)
    
    Includes:
    - Active connections and rooms
    - Participant statistics
    - Message throughput
    - Error rates
    - Resource utilization
    """
    metrics = await webrtc_monitoring.get_metrics()
    return metrics


@router.get("/stats")
async def get_stats():
    """
    Get detailed WebRTC statistics.
    
    Provides:
    - Room size distribution
    - Feature usage analytics
    - Top active rooms
    - Recording statistics
    """
    stats = await webrtc_monitoring.get_stats()
    return stats


@router.get("/rate-limits/{limit_type}/status")
async def get_rate_limit_status(
    limit_type: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get current rate limit status for the authenticated user.
    
    Args:
        limit_type: Type of rate limit to check (e.g., "websocket_message", "chat_message")
    """
    username = current_user.get("username") or current_user.get("email")
    status_info = await rate_limiter.get_rate_limit_status(limit_type, username)
    
    return status_info


# ====================
# Connection Quality & Reconnection Endpoints (Production Feature)
# ====================

@router.post("/rooms/{room_id}/connection-quality", tags=["WebRTC"])
async def report_connection_quality(
    room_id: str,
    metrics: Dict = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Report connection quality metrics for reconnection management.
    
    This endpoint allows clients to report their connection quality metrics,
    which helps the reconnection manager detect poor connections and optimize
    the reconnection experience.
    
    Metrics should include:
    - latency_ms: Round-trip time in milliseconds
    - packet_loss_percent: Packet loss percentage (0-100)
    - jitter_ms: Jitter in milliseconds
    - bandwidth_kbps: Available bandwidth in Kbps (optional)
    
    Returns:
        Dict with quality assessment and recommendations
    """
    try:
        username = current_user.get("username")
        
        # Detect connection quality
        quality = await reconnection_manager.detect_connection_quality(
            room_id=room_id,
            user_id=username,
            metrics=metrics
        )
        
        # Generate recommendations based on quality
        recommendations = []
        if quality == "poor":
            recommendations = [
                "Consider reducing video quality",
                "Close other bandwidth-intensive applications",
                "Check your network connection",
                "Try reconnecting if issues persist"
            ]
        elif quality == "fair":
            recommendations = [
                "Connection is stable but could be better",
                "Consider reducing video quality if experiencing lag"
            ]
        
        return {
            "quality": quality,
            "metrics": metrics,
            "recommendations": recommendations,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Connection quality report failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process connection quality: {str(e)}"
        )


@router.get("/rooms/{room_id}/reconnection-state", tags=["WebRTC"])
async def get_reconnection_state(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get reconnection state for current user in room.
    
    Useful for debugging and monitoring reconnection behavior.
    
    Returns:
        Dict with user's reconnection state including sequence number,
        connection status, and last seen timestamp
    """
    try:
        username = current_user.get("username")
        
        state = await reconnection_manager.get_user_state(room_id, username)
        
        if not state:
            return {
                "room_id": room_id,
                "user_id": username,
                "state": None,
                "message": "No reconnection state found"
            }
        
        return {
            "room_id": room_id,
            "user_id": username,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Failed to get reconnection state: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve reconnection state: {str(e)}"
        )


# ====================
# File Transfer Endpoints (Production Feature)
# ====================

@router.post("/rooms/{room_id}/file-transfer/offer", tags=["WebRTC File Transfer"])
async def create_file_transfer_offer(
    room_id: str,
    receiver_id: str = Body(...),
    filename: str = Body(...),
    file_size: int = Body(...),
    mime_type: Optional[str] = Body(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new file transfer offer.
    
    Initiates a chunked file transfer from sender to receiver in a room.
    
    Args:
        room_id: Room ID where transfer occurs
        receiver_id: User ID of intended receiver
        filename: Name of file being transferred
        file_size: Size of file in bytes
        mime_type: MIME type of file (optional)
        
    Returns:
        Transfer details including transfer_id and chunk info
    """
    try:
        sender_id = current_user.get("username")
        
        # Create transfer offer
        transfer_state = await file_transfer_manager.create_offer(
            room_id=room_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type
        )
        
        # Broadcast offer to room
        offer_message = WebRtcMessage(
            type=MessageType.FILE_SHARE_OFFER,
            payload={
                "transfer_id": transfer_state["transfer_id"],
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "filename": filename,
                "file_size": file_size,
                "mime_type": mime_type,
                "total_chunks": transfer_state["total_chunks"],
                "chunk_size": transfer_state["chunk_size"]
            },
            room_id=room_id,
            sender_id=sender_id
        )
        
        await webrtc_manager.publish_to_room(room_id, offer_message)
        
        return transfer_state
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create file transfer offer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/file-transfer/{transfer_id}/accept", tags=["WebRTC File Transfer"])
async def accept_file_transfer(
    room_id: str,
    transfer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Accept a pending file transfer.
    
    Args:
        room_id: Room ID
        transfer_id: Transfer ID to accept
        
    Returns:
        Updated transfer state
    """
    try:
        receiver_id = current_user.get("username")
        
        transfer_state = await file_transfer_manager.accept_transfer(
            transfer_id=transfer_id,
            receiver_id=receiver_id
        )
        
        # Broadcast acceptance to room
        accept_message = WebRtcMessage(
            type=MessageType.FILE_SHARE_ACCEPT,
            payload={
                "transfer_id": transfer_id,
                "receiver_id": receiver_id
            },
            room_id=room_id,
            sender_id=receiver_id
        )
        
        await webrtc_manager.publish_to_room(room_id, accept_message)
        
        return transfer_state
        
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to accept file transfer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/file-transfer/{transfer_id}/reject", tags=["WebRTC File Transfer"])
async def reject_file_transfer(
    room_id: str,
    transfer_id: str,
    reason: Optional[str] = Body(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Reject a pending file transfer.
    
    Args:
        room_id: Room ID
        transfer_id: Transfer ID to reject
        reason: Optional rejection reason
        
    Returns:
        Updated transfer state
    """
    try:
        receiver_id = current_user.get("username")
        
        transfer_state = await file_transfer_manager.reject_transfer(
            transfer_id=transfer_id,
            receiver_id=receiver_id,
            reason=reason
        )
        
        # Broadcast rejection to room
        reject_message = WebRtcMessage(
            type=MessageType.FILE_SHARE_REJECT,
            payload={
                "transfer_id": transfer_id,
                "receiver_id": receiver_id,
                "reason": reason
            },
            room_id=room_id,
            sender_id=receiver_id
        )
        
        await webrtc_manager.publish_to_room(room_id, reject_message)
        
        return transfer_state
        
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to reject file transfer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/file-transfer/{transfer_id}/pause", tags=["WebRTC File Transfer"])
async def pause_file_transfer(
    room_id: str,
    transfer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Pause an active file transfer.
    
    Args:
        room_id: Room ID
        transfer_id: Transfer ID to pause
        
    Returns:
        Updated transfer state
    """
    try:
        user_id = current_user.get("username")
        
        transfer_state = await file_transfer_manager.pause_transfer(
            transfer_id=transfer_id,
            user_id=user_id
        )
        
        return transfer_state
        
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to pause file transfer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/file-transfer/{transfer_id}/resume", tags=["WebRTC File Transfer"])
async def resume_file_transfer(
    room_id: str,
    transfer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Resume a paused file transfer.
    
    Args:
        room_id: Room ID
        transfer_id: Transfer ID to resume
        
    Returns:
        Updated transfer state
    """
    try:
        user_id = current_user.get("username")
        
        transfer_state = await file_transfer_manager.resume_transfer(
            transfer_id=transfer_id,
            user_id=user_id
        )
        
        return transfer_state
        
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to resume file transfer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/file-transfer/{transfer_id}/progress", tags=["WebRTC File Transfer"])
async def get_file_transfer_progress(
    room_id: str,
    transfer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get real-time file transfer progress.
    
    Args:
        room_id: Room ID
        transfer_id: Transfer ID
        
    Returns:
        Transfer state with progress information
    """
    try:
        transfer_state = await file_transfer_manager.get_transfer_progress(transfer_id)
        
        return transfer_state
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get transfer progress: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rooms/{room_id}/file-transfer/{transfer_id}", tags=["WebRTC File Transfer"])
async def cancel_file_transfer(
    room_id: str,
    transfer_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a file transfer and cleanup.
    
    Args:
        room_id: Room ID
        transfer_id: Transfer ID to cancel
        
    Returns:
        Updated transfer state
    """
    try:
        user_id = current_user.get("username")
        
        transfer_state = await file_transfer_manager.cancel_transfer(
            transfer_id=transfer_id,
            user_id=user_id
        )
        
        return transfer_state
        
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel file transfer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/file-transfers", tags=["WebRTC File Transfer"])
async def get_user_file_transfers(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all file transfers for the current user.
    
    Args:
        status: Optional status filter (pending, active, paused, completed, failed, cancelled)
        
    Returns:
        List of transfer states
    """
    try:
        user_id = current_user.get("username")
        
        transfers = await file_transfer_manager.get_user_transfers(
            user_id=user_id,
            status=status
        )
        
        return {"transfers": transfers, "count": len(transfers)}
        
    except Exception as e:
        logger.error(f"Failed to get user transfers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RECORDING ENDPOINTS
# ============================================================================

@router.post("/rooms/{room_id}/recording/start", tags=["WebRTC Recording"])
async def start_room_recording(
    room_id: str,
    recording_format: Optional[RecordingFormat] = Query(None, description="Recording format"),
    quality: Optional[RecordingQuality] = Query(None, description="Quality preset"),
    current_user: dict = Depends(get_current_user)
):
    """
    Start recording a room session.
    
    Args:
        room_id: Room ID to record
        recording_format: Format (webm, mp4, mkv)
        quality: Quality preset (low, medium, high, ultra)
        
    Returns:
        Recording state
    """
    try:
        user_id = current_user.get("username")
        
        recording_state = await recording_manager.start_recording(
            room_id=room_id,
            user_id=user_id,
            recording_format=recording_format,
            quality=quality
        )
        
        # Broadcast recording started event
        await broadcast_webrtc_message(
            room_id=room_id,
            message_type="recording_started",
            data={
                "recording_id": recording_state["recording_id"],
                "user_id": user_id,
                "format": recording_state["format"],
                "quality": recording_state["quality"]
            },
            sender_id=user_id
        )
        
        return recording_state
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start recording: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/recording/{recording_id}/stop", tags=["WebRTC Recording"])
async def stop_room_recording(
    room_id: str,
    recording_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Stop an active recording.
    
    Args:
        room_id: Room ID
        recording_id: Recording ID to stop
        
    Returns:
        Updated recording state
    """
    try:
        user_id = current_user.get("username")
        
        recording_state = await recording_manager.stop_recording(
            recording_id=recording_id,
            user_id=user_id
        )
        
        # Broadcast recording stopped event
        await broadcast_webrtc_message(
            room_id=room_id,
            message_type="recording_stopped",
            data={
                "recording_id": recording_id,
                "duration": recording_state["duration_seconds"]
            },
            sender_id=user_id
        )
        
        return recording_state
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to stop recording: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/recording/{recording_id}/pause", tags=["WebRTC Recording"])
async def pause_room_recording(
    room_id: str,
    recording_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Pause an active recording.
    
    Args:
        room_id: Room ID
        recording_id: Recording ID to pause
        
    Returns:
        Updated recording state
    """
    try:
        user_id = current_user.get("username")
        
        recording_state = await recording_manager.pause_recording(
            recording_id=recording_id,
            user_id=user_id
        )
        
        # Broadcast recording paused event
        await broadcast_webrtc_message(
            room_id=room_id,
            message_type="recording_paused",
            data={"recording_id": recording_id},
            sender_id=user_id
        )
        
        return recording_state
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to pause recording: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/recording/{recording_id}/resume", tags=["WebRTC Recording"])
async def resume_room_recording(
    room_id: str,
    recording_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Resume a paused recording.
    
    Args:
        room_id: Room ID
        recording_id: Recording ID to resume
        
    Returns:
        Updated recording state
    """
    try:
        user_id = current_user.get("username")
        
        recording_state = await recording_manager.resume_recording(
            recording_id=recording_id,
            user_id=user_id
        )
        
        # Broadcast recording resumed event
        await broadcast_webrtc_message(
            room_id=room_id,
            message_type="recording_resumed",
            data={"recording_id": recording_id},
            sender_id=user_id
        )
        
        return recording_state
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to resume recording: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rooms/{room_id}/recording/{recording_id}", tags=["WebRTC Recording"])
async def cancel_room_recording(
    room_id: str,
    recording_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Cancel a recording and cleanup.
    
    Args:
        room_id: Room ID
        recording_id: Recording ID to cancel
        
    Returns:
        Updated recording state
    """
    try:
        user_id = current_user.get("username")
        
        recording_state = await recording_manager.cancel_recording(
            recording_id=recording_id,
            user_id=user_id
        )
        
        # Broadcast recording cancelled event
        await broadcast_webrtc_message(
            room_id=room_id,
            message_type="recording_cancelled",
            data={"recording_id": recording_id},
            sender_id=user_id
        )
        
        return recording_state
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel recording: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/recording/{recording_id}/status", tags=["WebRTC Recording"])
async def get_recording_status(
    room_id: str,
    recording_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get recording status.
    
    Args:
        room_id: Room ID
        recording_id: Recording ID
        
    Returns:
        Recording state
    """
    try:
        recording_state = await recording_manager.get_recording_status(recording_id)
        
        return recording_state
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get recording status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/recordings", tags=["WebRTC Recording"])
async def get_room_recordings(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all recordings for a room.
    
    Args:
        room_id: Room ID
        
    Returns:
        List of recording states
    """
    try:
        recordings = await recording_manager.get_room_recordings(room_id)
        
        return {"recordings": recordings, "count": len(recordings)}
        
    except Exception as e:
        logger.error(f"Failed to get room recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recordings", tags=["WebRTC Recording"])
async def get_user_recordings(
    status: Optional[str] = Query(None, description="Filter by status"),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all recordings for the current user.
    
    Args:
        status: Optional status filter
        
    Returns:
        List of recording states
    """
    try:
        user_id = current_user.get("username")
        
        recordings = await recording_manager.get_user_recordings(
            user_id=user_id,
            status=status
        )
        
        return {"recordings": recordings, "count": len(recordings)}
        
    except Exception as e:
        logger.error(f"Failed to get user recordings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# E2EE (END-TO-END ENCRYPTION) ENDPOINTS
# ============================================================================

@router.post("/rooms/{room_id}/e2ee/keys/generate", tags=["WebRTC E2EE"])
async def generate_e2ee_keys(
    room_id: str,
    key_type: Optional[KeyType] = Query(KeyType.EPHEMERAL, description="Key type"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate E2EE key pair for the current user in a room.
    
    Args:
        room_id: Room ID
        key_type: Type of key (ephemeral or identity)
        
    Returns:
        Public key information
    """
    try:
        user_id = current_user.get("username")
        
        key_pair = await e2ee_manager.generate_key_pair(
            user_id=user_id,
            room_id=room_id,
            key_type=key_type
        )
        
        # Broadcast key exchange message
        await broadcast_webrtc_message(
            room_id=room_id,
            message_type="e2ee_key_exchange",
            data={
                "user_id": user_id,
                "key_id": key_pair["key_id"],
                "public_key": key_pair["public_key"],
                "signature_public_key": key_pair.get("signature_public_key"),
                "key_type": key_pair["key_type"]
            },
            sender_id=user_id
        )
        
        return key_pair
        
    except Exception as e:
        logger.error(f"Failed to generate E2EE keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/e2ee/keys/exchange", tags=["WebRTC E2EE"])
async def exchange_e2ee_keys(
    room_id: str,
    peer_user_id: str = Body(..., description="Peer user ID"),
    current_user: dict = Depends(get_current_user)
):
    """
    Perform key exchange with another user.
    
    Args:
        room_id: Room ID
        peer_user_id: Peer user ID to exchange keys with
        
    Returns:
        Success status
    """
    try:
        user_id = current_user.get("username")
        
        success = await e2ee_manager.exchange_keys(
            user_a_id=user_id,
            user_b_id=peer_user_id,
            room_id=room_id
        )
        
        return {"success": success, "peer_user_id": peer_user_id}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to exchange E2EE keys: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rooms/{room_id}/e2ee/keys/{user_id}", tags=["WebRTC E2EE"])
async def get_user_public_key(
    room_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a user's public key.
    
    Args:
        room_id: Room ID
        user_id: User ID whose key to retrieve
        
    Returns:
        Public key information
    """
    try:
        public_key = await e2ee_manager.get_public_key(
            user_id=user_id,
            room_id=room_id
        )
        
        if not public_key:
            raise HTTPException(status_code=404, detail="Public key not found")
        
        return public_key
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get public key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/e2ee/keys/rotate", tags=["WebRTC E2EE"])
async def rotate_e2ee_key(
    room_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Rotate the current user's ephemeral key.
    
    Args:
        room_id: Room ID
        
    Returns:
        New key information
    """
    try:
        user_id = current_user.get("username")
        
        new_key = await e2ee_manager.rotate_key(
            user_id=user_id,
            room_id=room_id
        )
        
        # Broadcast key rotation
        await broadcast_webrtc_message(
            room_id=room_id,
            message_type="e2ee_key_rotation",
            data={
                "user_id": user_id,
                "new_key_id": new_key["key_id"],
                "public_key": new_key["public_key"]
            },
            sender_id=user_id
        )
        
        return new_key
        
    except Exception as e:
        logger.error(f"Failed to rotate E2EE key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/rooms/{room_id}/e2ee/keys/{key_id}", tags=["WebRTC E2EE"])
async def revoke_e2ee_key(
    room_id: str,
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Revoke a specific key.
    
    Args:
        room_id: Room ID
        key_id: Key ID to revoke
        
    Returns:
        Success status
    """
    try:
        user_id = current_user.get("username")
        
        success = await e2ee_manager.revoke_key(
            user_id=user_id,
            room_id=room_id,
            key_id=key_id
        )
        
        # Broadcast key revocation
        await broadcast_webrtc_message(
            room_id=room_id,
            message_type="e2ee_key_revoke",
            data={
                "user_id": user_id,
                "key_id": key_id
            },
            sender_id=user_id
        )
        
        return {"success": success, "key_id": key_id}
        
    except Exception as e:
        logger.error(f"Failed to revoke E2EE key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/e2ee/encrypt", tags=["WebRTC E2EE"])
async def encrypt_message_endpoint(
    room_id: str,
    recipient_id: str = Body(..., description="Recipient user ID"),
    message: dict = Body(..., description="Message to encrypt"),
    current_user: dict = Depends(get_current_user)
):
    """
    Encrypt a message for a specific recipient.
    
    Args:
        room_id: Room ID
        recipient_id: Recipient user ID
        message: Plaintext message
        
    Returns:
        Encrypted message envelope
    """
    try:
        user_id = current_user.get("username")
        
        encrypted = await e2ee_manager.encrypt_message(
            message=message,
            sender_id=user_id,
            recipient_id=recipient_id,
            room_id=room_id
        )
        
        return encrypted
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to encrypt message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rooms/{room_id}/e2ee/decrypt", tags=["WebRTC E2EE"])
async def decrypt_message_endpoint(
    room_id: str,
    encrypted_message: dict = Body(..., description="Encrypted message"),
    current_user: dict = Depends(get_current_user)
):
    """
    Decrypt an encrypted message.
    
    Args:
        room_id: Room ID
        encrypted_message: Encrypted message envelope
        
    Returns:
        Decrypted message
    """
    try:
        user_id = current_user.get("username")
        
        decrypted = await e2ee_manager.decrypt_message(
            encrypted=encrypted_message,
            recipient_id=user_id
        )
        
        return decrypted
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to decrypt message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ERROR HANDLERS
# ============================================================================
# Note: Exception handlers must be registered at app level in main.py,
# not at router level. FastAPI routers don't support exception_handler decorator.
# WebRTC errors are caught and handled within endpoint try/except blocks.
# ============================================================================


