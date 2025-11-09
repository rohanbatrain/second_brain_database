"""
WebRTC Router

FastAPI router providing WebSocket signaling endpoint and REST API
for WebRTC configuration.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.webrtc.schemas import WebRtcMessage, WebRtcConfig, IceServerConfig, MessageType
from second_brain_database.webrtc.dependencies import get_current_user_ws, validate_room_id
from second_brain_database.webrtc.connection_manager import webrtc_manager
from second_brain_database.routes.auth.dependencies import get_current_user_dep as get_current_user

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
    user_id = str(user["_id"])
    username = user.get("username") or user.get("email")
    
    # Accept the WebSocket connection
    await websocket.accept()
    
    logger.info(
        f"WebSocket connected: user {user_id} joined room {room_id}",
        extra={"room_id": room_id, "user_id": user_id}
    )
    
    # Subscribe to room's Redis channel
    subscription_task = None
    receive_task = None
    
    try:
        # Add user to room participants
        participant_count = await webrtc_manager.add_participant(room_id, user_id, username)
        
        # Get current participants
        participants = await webrtc_manager.get_participants(room_id)
        
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
            user_id=user_id,
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
                    message.sender_id = user_id
                    message.room_id = room_id
                    
                    logger.debug(
                        f"Received {message.type} from user {user_id} in room {room_id}",
                        extra={
                            "room_id": room_id,
                            "user_id": user_id,
                            "message_type": message.type
                        }
                    )
                    
                    # Publish to Redis (will be received by all subscribed instances)
                    await webrtc_manager.publish_to_room(room_id, message)
                    
                    # Update user presence (heartbeat)
                    await webrtc_manager.update_presence(room_id, user_id)
                    
            except WebSocketDisconnect:
                logger.info(f"Client {user_id} disconnected from room {room_id}")
            except Exception as e:
                logger.error(
                    f"Error receiving from client {user_id}: {e}",
                    extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
                    exc_info=True
                )
        
        async def receive_from_redis():
            """Subscribe to Redis and forward messages to client."""
            try:
                async for message in webrtc_manager.subscribe_to_room(room_id):
                    # Don't send messages back to the sender
                    if message.sender_id != user_id:
                        await websocket.send_json(message.model_dump())
                        
                        logger.debug(
                            f"Forwarded {message.type} to user {user_id} in room {room_id}",
                            extra={
                                "room_id": room_id,
                                "user_id": user_id,
                                "message_type": message.type,
                                "sender_id": message.sender_id
                            }
                        )
                        
            except Exception as e:
                logger.error(
                    f"Error receiving from Redis for user {user_id}: {e}",
                    extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
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
            f"WebSocket disconnected: user {user_id} left room {room_id}",
            extra={"room_id": room_id, "user_id": user_id}
        )
        
    except Exception as e:
        logger.error(
            f"WebSocket error for user {user_id} in room {room_id}: {e}",
            extra={"room_id": room_id, "user_id": user_id, "error": str(e)},
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
        # Cleanup: remove user from room
        try:
            remaining = await webrtc_manager.remove_participant(room_id, user_id)
            
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
                user_id=user_id,
                username=username,
                room_id=room_id,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            await webrtc_manager.publish_to_room(room_id, leave_message)
            
            logger.info(
                f"User {user_id} left room {room_id}, {remaining} participants remaining",
                extra={
                    "room_id": room_id,
                    "user_id": user_id,
                    "remaining_participants": remaining
                }
            )
            
        except Exception as e:
            logger.error(
                f"Error during WebSocket cleanup: {e}",
                extra={"room_id": room_id, "user_id": user_id, "error": str(e)}
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
        
        logger.info(
            f"Provided WebRTC config to user {current_user['_id']}",
            extra={"user_id": current_user["_id"], "ice_server_count": len(ice_servers)}
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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
            
            if "user_id" in event:
                summary["unique_users"].add(event["user_id"])
        
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
        user_id = str(current_user["_id"])
        
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
        user_id = str(current_user["_id"])
        
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
            user_id = participant.get("user_id")
            if user_id:
                info = await webrtc_manager.get_participant_info(room_id, user_id)
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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
        user_id = str(current_user["_id"])
        username = current_user.get("username") or current_user.get("email")
        timestamp = datetime.now(timezone.utc).isoformat()
        
        if raised:
            position = await webrtc_manager.add_to_hand_raise_queue(room_id, user_id, username, timestamp)
        else:
            await webrtc_manager.remove_from_hand_raise_queue(room_id, user_id)
            position = None
        
        # Notify room
        hand_raise_message = WebRtcMessage.create_hand_raise(
            user_id=user_id,
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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
        current_user_id = str(current_user["_id"])
        
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

