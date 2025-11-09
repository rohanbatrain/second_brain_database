"""
WebRTC Signaling Message Schemas

Pydantic models for all WebRTC signaling messages to ensure type safety
and validation across the signaling protocol.
"""

from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """WebRTC signaling message types."""
    # Core signaling
    OFFER = "offer"
    ANSWER = "answer"
    ICE_CANDIDATE = "ice-candidate"
    USER_JOINED = "user-joined"
    USER_LEFT = "user-left"
    ERROR = "error"
    ROOM_STATE = "room-state"
    
    # Phase 1: Media Controls
    MEDIA_CONTROL = "media-control"
    SCREEN_SHARE_CONTROL = "screen-share-control"
    
    # Phase 1: Chat
    CHAT_MESSAGE = "chat-message"
    
    # Phase 1: Room Permissions
    ROLE_UPDATED = "role-updated"
    PERMISSION_UPDATED = "permission-updated"
    
    # Phase 2: Recording
    RECORDING_CONTROL = "recording-control"
    RECORDING_STATUS = "recording-status"
    
    # Phase 2: File Sharing
    FILE_SHARE_OFFER = "file-share-offer"
    FILE_SHARE_ACCEPT = "file-share-accept"
    FILE_SHARE_REJECT = "file-share-reject"
    FILE_SHARE_PROGRESS = "file-share-progress"
    FILE_SHARE_COMPLETE = "file-share-complete"
    
    # Phase 2: Network Optimization
    NETWORK_STATS = "network-stats"
    QUALITY_UPDATE = "quality-update"
    
    # Phase 2: Analytics
    ANALYTICS_EVENT = "analytics-event"


class SdpPayload(BaseModel):
    """Session Description Protocol payload for offers and answers."""
    sdp: str = Field(..., description="SDP string containing session information")
    type: str = Field(..., description="SDP type: 'offer' or 'answer'")
    target_user_id: Optional[str] = Field(None, description="Target user ID for this SDP (optional for broadcast)")


class IceCandidatePayload(BaseModel):
    """ICE candidate payload for network negotiation."""
    candidate: str = Field(..., description="ICE candidate string")
    sdp_mid: Optional[str] = Field(None, alias="sdpMid", description="Media stream ID")
    sdp_m_line_index: Optional[int] = Field(None, alias="sdpMLineIndex", description="Media line index")
    target_user_id: Optional[str] = Field(None, description="Target user ID for this candidate")

    class Config:
        populate_by_name = True


class UserEventPayload(BaseModel):
    """Payload for user join/leave events."""
    user_id: str = Field(..., description="ID of the user who joined/left")
    username: Optional[str] = Field(None, description="Username of the user")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the event")


class RoomStatePayload(BaseModel):
    """Current state of the room."""
    room_id: str = Field(..., description="Room identifier")
    participants: list[Dict[str, Any]] = Field(default_factory=list, description="List of current participants")
    participant_count: int = Field(..., description="Number of participants")


class ErrorPayload(BaseModel):
    """Error message payload."""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


# ============================================================================
# Phase 1: Media Controls
# ============================================================================

class MediaType(str, Enum):
    """Media stream types."""
    AUDIO = "audio"
    VIDEO = "video"
    SCREEN_SHARE = "screen-share"


class MediaControlPayload(BaseModel):
    """Media control action payload."""
    action: str = Field(..., description="Action: mute, unmute, video_on, video_off")
    media_type: MediaType = Field(..., description="Type of media being controlled")
    user_id: str = Field(..., description="User ID whose media is being controlled")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class ScreenShareControlPayload(BaseModel):
    """Screen share control payload."""
    action: str = Field(..., description="Action: start, stop")
    user_id: str = Field(..., description="User ID sharing screen")
    screen_id: Optional[str] = Field(None, description="Screen/window identifier")
    quality: str = Field(default="medium", description="Quality: low, medium, high")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Phase 1: Room Permissions
# ============================================================================

class RoomRole(str, Enum):
    """User roles in a room."""
    HOST = "host"
    MODERATOR = "moderator"
    PARTICIPANT = "participant"
    OBSERVER = "observer"


class RoomPermissions(BaseModel):
    """Room permissions for a user."""
    can_speak: bool = Field(default=True, description="Can unmute and speak")
    can_share_video: bool = Field(default=True, description="Can share video")
    can_share_screen: bool = Field(default=True, description="Can share screen")
    can_send_chat: bool = Field(default=True, description="Can send chat messages")
    can_share_files: bool = Field(default=True, description="Can share files")
    can_manage_participants: bool = Field(default=False, description="Can manage other participants")
    can_record: bool = Field(default=False, description="Can start/stop recording")


class RoleUpdatePayload(BaseModel):
    """Role update payload."""
    user_id: str = Field(..., description="User whose role is being updated")
    role: RoomRole = Field(..., description="New role")
    updated_by: str = Field(..., description="User who updated the role")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class PermissionUpdatePayload(BaseModel):
    """Permission update payload."""
    user_id: str = Field(..., description="User whose permissions are being updated")
    permissions: RoomPermissions = Field(..., description="Updated permissions")
    updated_by: str = Field(..., description="User who updated permissions")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Phase 1: Chat Integration
# ============================================================================

class ChatMessagePayload(BaseModel):
    """Chat message payload."""
    message_id: str = Field(..., description="Unique message ID")
    user_id: str = Field(..., description="Sender user ID")
    username: str = Field(..., description="Sender username")
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    message_type: str = Field(default="text", description="Message type: text, emoji, system")
    reply_to: Optional[str] = Field(None, description="Message ID being replied to")


# ============================================================================
# Phase 2: Recording System
# ============================================================================

class RecordingControlPayload(BaseModel):
    """Recording control payload."""
    action: str = Field(..., description="Action: start, stop, pause, resume")
    recording_id: str = Field(..., description="Unique recording ID")
    user_id: str = Field(..., description="User controlling recording")
    format: str = Field(default="mp4", description="Recording format: mp4, webm")
    quality: str = Field(default="medium", description="Recording quality: low, medium, high")
    include_audio: bool = Field(default=True, description="Include audio in recording")
    include_video: bool = Field(default=True, description="Include video in recording")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class RecordingStatusPayload(BaseModel):
    """Recording status payload."""
    recording_id: str = Field(..., description="Recording ID")
    status: str = Field(..., description="Status: recording, paused, stopped, processing")
    duration: int = Field(default=0, description="Duration in seconds")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Phase 2: File Sharing
# ============================================================================

class FileShareOfferPayload(BaseModel):
    """File share offer payload."""
    transfer_id: str = Field(..., description="Unique transfer ID")
    sender_id: str = Field(..., description="Sender user ID")
    file_name: str = Field(..., description="File name")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type")
    chunk_size: int = Field(default=16384, description="Chunk size in bytes")
    total_chunks: int = Field(..., description="Total number of chunks")
    target_user_id: Optional[str] = Field(None, description="Target user (None for broadcast)")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class FileShareResponsePayload(BaseModel):
    """File share accept/reject payload."""
    transfer_id: str = Field(..., description="Transfer ID")
    user_id: str = Field(..., description="Responding user ID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class FileShareProgressPayload(BaseModel):
    """File share progress payload."""
    transfer_id: str = Field(..., description="Transfer ID")
    chunks_received: int = Field(..., description="Number of chunks received")
    total_chunks: int = Field(..., description="Total chunks")
    percentage: float = Field(..., description="Progress percentage")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class FileShareCompletePayload(BaseModel):
    """File share complete payload."""
    transfer_id: str = Field(..., description="Transfer ID")
    success: bool = Field(..., description="Whether transfer completed successfully")
    error: Optional[str] = Field(None, description="Error message if failed")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Phase 2: Network Optimization
# ============================================================================

class NetworkStatsPayload(BaseModel):
    """Network statistics payload."""
    user_id: str = Field(..., description="User ID")
    bandwidth_up: int = Field(..., description="Upload bandwidth in kbps")
    bandwidth_down: int = Field(..., description="Download bandwidth in kbps")
    latency: int = Field(..., description="Latency in ms")
    packet_loss: float = Field(..., description="Packet loss percentage")
    jitter: int = Field(..., description="Jitter in ms")
    connection_quality: str = Field(..., description="Quality: excellent, good, fair, poor")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class QualityUpdatePayload(BaseModel):
    """Adaptive quality update payload."""
    user_id: str = Field(..., description="User ID")
    video_resolution: str = Field(..., description="Resolution: 1080p, 720p, 480p, 360p")
    video_bitrate: int = Field(..., description="Video bitrate in kbps")
    audio_bitrate: int = Field(..., description="Audio bitrate in kbps")
    frame_rate: int = Field(..., description="Frame rate")
    reason: str = Field(..., description="Reason for quality change")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Phase 2: Analytics
# ============================================================================

class AnalyticsEventPayload(BaseModel):
    """Analytics event payload."""
    event_type: str = Field(..., description="Event type: connection, media_change, error, etc.")
    user_id: str = Field(..., description="User ID")
    data: Dict[str, Any] = Field(..., description="Event-specific data")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class WebRtcMessage(BaseModel):
    """Base WebRTC signaling message."""
    type: MessageType = Field(..., description="Type of the message")
    payload: Dict[str, Any] = Field(..., description="Message payload")
    sender_id: Optional[str] = Field(None, description="ID of the message sender")
    room_id: Optional[str] = Field(None, description="Room identifier")
    timestamp: Optional[str] = Field(None, description="Message timestamp")

    @classmethod
    def create_offer(cls, sdp: str, sender_id: str, room_id: str, target_user_id: Optional[str] = None) -> "WebRtcMessage":
        """Create an offer message."""
        return cls(
            type=MessageType.OFFER,
            payload=SdpPayload(sdp=sdp, type="offer", target_user_id=target_user_id).model_dump(),
            sender_id=sender_id,
            room_id=room_id
        )

    @classmethod
    def create_answer(cls, sdp: str, sender_id: str, room_id: str, target_user_id: Optional[str] = None) -> "WebRtcMessage":
        """Create an answer message."""
        return cls(
            type=MessageType.ANSWER,
            payload=SdpPayload(sdp=sdp, type="answer", target_user_id=target_user_id).model_dump(),
            sender_id=sender_id,
            room_id=room_id
        )

    @classmethod
    def create_ice_candidate(
        cls,
        candidate: str,
        sender_id: str,
        room_id: str,
        sdp_mid: Optional[str] = None,
        sdp_m_line_index: Optional[int] = None,
        target_user_id: Optional[str] = None
    ) -> "WebRtcMessage":
        """Create an ICE candidate message."""
        return cls(
            type=MessageType.ICE_CANDIDATE,
            payload=IceCandidatePayload(
                candidate=candidate,
                sdp_mid=sdp_mid,
                sdp_m_line_index=sdp_m_line_index,
                target_user_id=target_user_id
            ).model_dump(by_alias=True),
            sender_id=sender_id,
            room_id=room_id
        )

    @classmethod
    def create_user_joined(cls, user_id: str, username: Optional[str], room_id: str, timestamp: str) -> "WebRtcMessage":
        """Create a user joined event."""
        return cls(
            type=MessageType.USER_JOINED,
            payload=UserEventPayload(user_id=user_id, username=username, timestamp=timestamp).model_dump(),
            room_id=room_id
        )

    @classmethod
    def create_user_left(cls, user_id: str, username: Optional[str], room_id: str, timestamp: str) -> "WebRtcMessage":
        """Create a user left event."""
        return cls(
            type=MessageType.USER_LEFT,
            payload=UserEventPayload(user_id=user_id, username=username, timestamp=timestamp).model_dump(),
            room_id=room_id
        )

    @classmethod
    def create_error(cls, code: str, message: str, details: Optional[Dict[str, Any]] = None) -> "WebRtcMessage":
        """Create an error message."""
        return cls(
            type=MessageType.ERROR,
            payload=ErrorPayload(code=code, message=message, details=details).model_dump()
        )
    
    # ========================================================================
    # Phase 1: Media Controls
    # ========================================================================
    
    @classmethod
    def create_media_control(
        cls,
        action: str,
        media_type: MediaType,
        user_id: str,
        room_id: str,
        sender_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a media control message."""
        return cls(
            type=MessageType.MEDIA_CONTROL,
            payload=MediaControlPayload(
                action=action,
                media_type=media_type,
                user_id=user_id,
                timestamp=timestamp
            ).model_dump(),
            sender_id=sender_id,
            room_id=room_id
        )
    
    @classmethod
    def create_screen_share_control(
        cls,
        action: str,
        user_id: str,
        room_id: str,
        sender_id: str,
        timestamp: str,
        screen_id: Optional[str] = None,
        quality: str = "medium"
    ) -> "WebRtcMessage":
        """Create a screen share control message."""
        return cls(
            type=MessageType.SCREEN_SHARE_CONTROL,
            payload=ScreenShareControlPayload(
                action=action,
                user_id=user_id,
                screen_id=screen_id,
                quality=quality,
                timestamp=timestamp
            ).model_dump(),
            sender_id=sender_id,
            room_id=room_id
        )
    
    # ========================================================================
    # Phase 1: Chat Integration
    # ========================================================================
    
    @classmethod
    def create_chat_message(
        cls,
        message_id: str,
        user_id: str,
        username: str,
        content: str,
        room_id: str,
        timestamp: str,
        message_type: str = "text",
        reply_to: Optional[str] = None
    ) -> "WebRtcMessage":
        """Create a chat message."""
        return cls(
            type=MessageType.CHAT_MESSAGE,
            payload=ChatMessagePayload(
                message_id=message_id,
                user_id=user_id,
                username=username,
                content=content,
                timestamp=timestamp,
                message_type=message_type,
                reply_to=reply_to
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    # ========================================================================
    # Phase 1: Room Permissions
    # ========================================================================
    
    @classmethod
    def create_role_update(
        cls,
        user_id: str,
        role: RoomRole,
        updated_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a role update message."""
        return cls(
            type=MessageType.ROLE_UPDATED,
            payload=RoleUpdatePayload(
                user_id=user_id,
                role=role,
                updated_by=updated_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=updated_by,
            room_id=room_id
        )
    
    @classmethod
    def create_permission_update(
        cls,
        user_id: str,
        permissions: RoomPermissions,
        updated_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a permission update message."""
        return cls(
            type=MessageType.PERMISSION_UPDATED,
            payload=PermissionUpdatePayload(
                user_id=user_id,
                permissions=permissions,
                updated_by=updated_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=updated_by,
            room_id=room_id
        )
    
    # ========================================================================
    # Phase 2: Recording System
    # ========================================================================
    
    @classmethod
    def create_recording_control(
        cls,
        action: str,
        recording_id: str,
        user_id: str,
        room_id: str,
        timestamp: str,
        format: str = "mp4",
        quality: str = "medium",
        include_audio: bool = True,
        include_video: bool = True
    ) -> "WebRtcMessage":
        """Create a recording control message."""
        return cls(
            type=MessageType.RECORDING_CONTROL,
            payload=RecordingControlPayload(
                action=action,
                recording_id=recording_id,
                user_id=user_id,
                format=format,
                quality=quality,
                include_audio=include_audio,
                include_video=include_video,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    @classmethod
    def create_recording_status(
        cls,
        recording_id: str,
        status: str,
        room_id: str,
        timestamp: str,
        duration: int = 0,
        file_size: Optional[int] = None
    ) -> "WebRtcMessage":
        """Create a recording status message."""
        return cls(
            type=MessageType.RECORDING_STATUS,
            payload=RecordingStatusPayload(
                recording_id=recording_id,
                status=status,
                duration=duration,
                file_size=file_size,
                timestamp=timestamp
            ).model_dump(),
            room_id=room_id
        )
    
    # ========================================================================
    # Phase 2: File Sharing
    # ========================================================================
    
    @classmethod
    def create_file_share_offer(
        cls,
        transfer_id: str,
        sender_id: str,
        file_name: str,
        file_size: int,
        file_type: str,
        total_chunks: int,
        room_id: str,
        timestamp: str,
        target_user_id: Optional[str] = None,
        chunk_size: int = 16384
    ) -> "WebRtcMessage":
        """Create a file share offer message."""
        return cls(
            type=MessageType.FILE_SHARE_OFFER,
            payload=FileShareOfferPayload(
                transfer_id=transfer_id,
                sender_id=sender_id,
                file_name=file_name,
                file_size=file_size,
                file_type=file_type,
                chunk_size=chunk_size,
                total_chunks=total_chunks,
                target_user_id=target_user_id,
                timestamp=timestamp
            ).model_dump(),
            sender_id=sender_id,
            room_id=room_id
        )
    
    @classmethod
    def create_file_share_response(
        cls,
        transfer_id: str,
        user_id: str,
        room_id: str,
        timestamp: str,
        accepted: bool
    ) -> "WebRtcMessage":
        """Create a file share accept/reject message."""
        return cls(
            type=MessageType.FILE_SHARE_ACCEPT if accepted else MessageType.FILE_SHARE_REJECT,
            payload=FileShareResponsePayload(
                transfer_id=transfer_id,
                user_id=user_id,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    @classmethod
    def create_file_share_progress(
        cls,
        transfer_id: str,
        chunks_received: int,
        total_chunks: int,
        room_id: str,
        timestamp: str,
        sender_id: str
    ) -> "WebRtcMessage":
        """Create a file share progress message."""
        percentage = (chunks_received / total_chunks * 100) if total_chunks > 0 else 0
        return cls(
            type=MessageType.FILE_SHARE_PROGRESS,
            payload=FileShareProgressPayload(
                transfer_id=transfer_id,
                chunks_received=chunks_received,
                total_chunks=total_chunks,
                percentage=percentage,
                timestamp=timestamp
            ).model_dump(),
            sender_id=sender_id,
            room_id=room_id
        )
    
    @classmethod
    def create_file_share_complete(
        cls,
        transfer_id: str,
        success: bool,
        room_id: str,
        timestamp: str,
        sender_id: str,
        error: Optional[str] = None
    ) -> "WebRtcMessage":
        """Create a file share complete message."""
        return cls(
            type=MessageType.FILE_SHARE_COMPLETE,
            payload=FileShareCompletePayload(
                transfer_id=transfer_id,
                success=success,
                error=error,
                timestamp=timestamp
            ).model_dump(),
            sender_id=sender_id,
            room_id=room_id
        )
    
    # ========================================================================
    # Phase 2: Network Optimization
    # ========================================================================
    
    @classmethod
    def create_network_stats(
        cls,
        user_id: str,
        bandwidth_up: int,
        bandwidth_down: int,
        latency: int,
        packet_loss: float,
        jitter: int,
        connection_quality: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a network stats message."""
        return cls(
            type=MessageType.NETWORK_STATS,
            payload=NetworkStatsPayload(
                user_id=user_id,
                bandwidth_up=bandwidth_up,
                bandwidth_down=bandwidth_down,
                latency=latency,
                packet_loss=packet_loss,
                jitter=jitter,
                connection_quality=connection_quality,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    @classmethod
    def create_quality_update(
        cls,
        user_id: str,
        video_resolution: str,
        video_bitrate: int,
        audio_bitrate: int,
        frame_rate: int,
        reason: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a quality update message."""
        return cls(
            type=MessageType.QUALITY_UPDATE,
            payload=QualityUpdatePayload(
                user_id=user_id,
                video_resolution=video_resolution,
                video_bitrate=video_bitrate,
                audio_bitrate=audio_bitrate,
                frame_rate=frame_rate,
                reason=reason,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    # ========================================================================
    # Phase 2: Analytics
    # ========================================================================
    
    @classmethod
    def create_analytics_event(
        cls,
        event_type: str,
        user_id: str,
        data: Dict[str, Any],
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create an analytics event message."""
        return cls(
            type=MessageType.ANALYTICS_EVENT,
            payload=AnalyticsEventPayload(
                event_type=event_type,
                user_id=user_id,
                data=data,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )


class IceServerConfig(BaseModel):
    """ICE server configuration for STUN/TURN."""
    urls: list[str] = Field(..., description="List of server URLs")
    username: Optional[str] = Field(None, description="Username for TURN authentication")
    credential: Optional[str] = Field(None, description="Credential for TURN authentication")


class WebRtcConfig(BaseModel):
    """WebRTC configuration response."""
    ice_servers: list[IceServerConfig] = Field(..., description="List of ICE servers (STUN/TURN)")
    ice_transport_policy: str = Field(default="all", description="ICE transport policy: 'all' or 'relay'")
    bundle_policy: str = Field(default="balanced", description="Bundle policy: 'balanced', 'max-compat', or 'max-bundle'")
    rtcp_mux_policy: str = Field(default="require", description="RTCP mux policy")
