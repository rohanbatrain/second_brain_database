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
    
    # Immediate Features (This Week)
    PARTICIPANT_UPDATE = "participant-update"  # Enhanced participant info
    ROOM_SETTINGS_UPDATE = "room-settings-update"  # Room settings changes
    HAND_RAISE = "hand-raise"  # Raise/lower hand
    HAND_RAISE_QUEUE = "hand-raise-queue"  # Hand raise queue update
    
    # Short Term (This Month)
    WAITING_ROOM_JOIN = "waiting-room-join"  # User joins waiting room
    WAITING_ROOM_ADMIT = "waiting-room-admit"  # Admit from waiting room
    WAITING_ROOM_REJECT = "waiting-room-reject"  # Reject from waiting room
    REACTION = "reaction"  # User reaction/emoji
    
    # Medium Term (Next Quarter)
    BREAKOUT_ROOM_CREATE = "breakout-room-create"  # Create breakout room
    BREAKOUT_ROOM_ASSIGN = "breakout-room-assign"  # Assign user to breakout
    BREAKOUT_ROOM_CLOSE = "breakout-room-close"  # Close breakout room
    VIRTUAL_BACKGROUND_UPDATE = "virtual-background-update"  # Background change
    LIVE_STREAM_START = "live-stream-start"  # Start live stream
    LIVE_STREAM_STOP = "live-stream-stop"  # Stop live stream
    
    # Long Term (6+ Months)
    E2EE_KEY_EXCHANGE = "e2ee-key-exchange"  # End-to-end encryption keys
    E2EE_RATCHET_UPDATE = "e2ee-ratchet-update"  # E2EE ratchet update


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


# ============================================================================
# Immediate Features (This Week): Participant List Enhancements
# ============================================================================

class ParticipantInfo(BaseModel):
    """Enhanced participant information."""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    role: RoomRole = Field(default=RoomRole.PARTICIPANT, description="User role")
    audio_enabled: bool = Field(default=True, description="Audio enabled")
    video_enabled: bool = Field(default=True, description="Video enabled")
    screen_sharing: bool = Field(default=False, description="Screen sharing active")
    hand_raised: bool = Field(default=False, description="Hand raised")
    hand_raised_at: Optional[str] = Field(None, description="When hand was raised")
    joined_at: str = Field(..., description="Join timestamp")
    connection_quality: str = Field(default="good", description="Connection quality")
    is_speaking: bool = Field(default=False, description="Currently speaking")


class ParticipantUpdatePayload(BaseModel):
    """Participant state update payload."""
    participant: ParticipantInfo = Field(..., description="Updated participant info")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Immediate Features (This Week): Room Settings
# ============================================================================

class RoomSettings(BaseModel):
    """Room configuration settings."""
    lock_room: bool = Field(default=False, description="Room is locked (no new joins)")
    enable_waiting_room: bool = Field(default=False, description="Enable waiting room")
    mute_on_entry: bool = Field(default=False, description="Mute participants on entry")
    disable_video_on_entry: bool = Field(default=False, description="Disable video on entry")
    enable_chat: bool = Field(default=True, description="Enable chat")
    enable_screen_share: bool = Field(default=True, description="Enable screen sharing")
    enable_reactions: bool = Field(default=True, description="Enable reactions")
    enable_file_sharing: bool = Field(default=True, description="Enable file sharing")
    enable_recording: bool = Field(default=True, description="Enable recording")
    max_participants: Optional[int] = Field(None, description="Maximum participants allowed")
    require_host_to_start: bool = Field(default=False, description="Require host to start meeting")
    allow_participants_rename: bool = Field(default=True, description="Allow participants to rename themselves")
    allow_participants_unmute: bool = Field(default=True, description="Allow participants to unmute themselves")


class RoomSettingsUpdatePayload(BaseModel):
    """Room settings update payload."""
    settings: RoomSettings = Field(..., description="Updated room settings")
    updated_by: str = Field(..., description="User who updated settings")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Immediate Features (This Week): Hand Raise Queue
# ============================================================================

class HandRaisePayload(BaseModel):
    """Hand raise/lower payload."""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    raised: bool = Field(..., description="True if raising, False if lowering")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class HandRaiseQueueEntry(BaseModel):
    """Entry in hand raise queue."""
    username: str = Field(..., description="Username (primary identifier)")
    raised_at: str = Field(..., description="When hand was raised")
    position: int = Field(..., description="Position in queue")
    user_id: Optional[str] = Field(None, description="User ID (deprecated, for backward compatibility)")


class HandRaiseQueuePayload(BaseModel):
    """Hand raise queue state payload."""
    queue: list[HandRaiseQueueEntry] = Field(..., description="Ordered queue of raised hands")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Short Term (This Month): Waiting Room
# ============================================================================

class WaitingRoomParticipant(BaseModel):
    """Participant in waiting room."""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    joined_at: str = Field(..., description="Join timestamp")


class WaitingRoomJoinPayload(BaseModel):
    """User joins waiting room payload."""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class WaitingRoomResponsePayload(BaseModel):
    """Admit/reject from waiting room payload."""
    user_id: str = Field(..., description="User ID being admitted/rejected")
    actioned_by: str = Field(..., description="User who admitted/rejected")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Short Term (This Month): Reactions
# ============================================================================

class ReactionType(str, Enum):
    """Reaction types."""
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    CLAP = "clap"
    HEART = "heart"
    LAUGH = "laugh"
    SURPRISED = "surprised"
    THINKING = "thinking"
    CELEBRATE = "celebrate"


class ReactionPayload(BaseModel):
    """User reaction payload."""
    user_id: str = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    reaction_type: ReactionType = Field(..., description="Type of reaction")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Medium Term (Next Quarter): Breakout Rooms
# ============================================================================

class BreakoutRoomConfig(BaseModel):
    """Breakout room configuration."""
    breakout_room_id: str = Field(..., description="Breakout room ID")
    name: str = Field(..., description="Breakout room name")
    max_participants: Optional[int] = Field(None, description="Max participants")
    auto_move_back: bool = Field(default=True, description="Auto move back to main room when closed")
    duration_minutes: Optional[int] = Field(None, description="Auto-close after duration")


class BreakoutRoomCreatePayload(BaseModel):
    """Create breakout room payload."""
    config: BreakoutRoomConfig = Field(..., description="Breakout room config")
    created_by: str = Field(..., description="User who created the breakout room")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class BreakoutRoomAssignPayload(BaseModel):
    """Assign user to breakout room payload."""
    user_id: str = Field(..., description="User being assigned")
    breakout_room_id: str = Field(..., description="Breakout room ID")
    assigned_by: str = Field(..., description="User who assigned")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class BreakoutRoomClosePayload(BaseModel):
    """Close breakout room payload."""
    breakout_room_id: str = Field(..., description="Breakout room ID")
    closed_by: str = Field(..., description="User who closed the room")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Medium Term (Next Quarter): Virtual Backgrounds & Live Streaming
# ============================================================================

class VirtualBackgroundType(str, Enum):
    """Virtual background types."""
    NONE = "none"
    BLUR = "blur"
    IMAGE = "image"
    VIDEO = "video"


class VirtualBackgroundUpdatePayload(BaseModel):
    """Virtual background update payload."""
    user_id: str = Field(..., description="User ID")
    background_type: VirtualBackgroundType = Field(..., description="Background type")
    background_url: Optional[str] = Field(None, description="URL for image/video background")
    blur_intensity: Optional[int] = Field(None, description="Blur intensity 0-100")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class LiveStreamPlatform(str, Enum):
    """Live streaming platforms."""
    YOUTUBE = "youtube"
    FACEBOOK = "facebook"
    TWITCH = "twitch"
    CUSTOM_RTMP = "custom_rtmp"


class LiveStreamConfig(BaseModel):
    """Live stream configuration."""
    stream_id: str = Field(..., description="Stream ID")
    platform: LiveStreamPlatform = Field(..., description="Streaming platform")
    stream_url: str = Field(..., description="RTMP URL")
    stream_key: str = Field(..., description="Stream key")
    title: str = Field(..., description="Stream title")
    description: Optional[str] = Field(None, description="Stream description")


class LiveStreamStartPayload(BaseModel):
    """Start live stream payload."""
    config: LiveStreamConfig = Field(..., description="Stream configuration")
    started_by: str = Field(..., description="User who started stream")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class LiveStreamStopPayload(BaseModel):
    """Stop live stream payload."""
    stream_id: str = Field(..., description="Stream ID")
    stopped_by: str = Field(..., description="User who stopped stream")
    duration_seconds: int = Field(..., description="Stream duration")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ============================================================================
# Long Term (6+ Months): End-to-End Encryption
# ============================================================================

class E2EEKeyType(str, Enum):
    """E2EE key types."""
    IDENTITY_KEY = "identity_key"
    SIGNED_PRE_KEY = "signed_pre_key"
    ONE_TIME_PRE_KEY = "one_time_pre_key"
    RATCHET_KEY = "ratchet_key"


class E2EEKeyExchangePayload(BaseModel):
    """E2EE key exchange payload."""
    sender_user_id: str = Field(..., description="Sender user ID")
    recipient_user_id: str = Field(..., description="Recipient user ID")
    key_type: E2EEKeyType = Field(..., description="Type of key")
    public_key: str = Field(..., description="Base64 encoded public key")
    key_id: str = Field(..., description="Unique key ID")
    signature: Optional[str] = Field(None, description="Key signature")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class E2EERatchetUpdatePayload(BaseModel):
    """E2EE ratchet update payload."""
    sender_user_id: str = Field(..., description="Sender user ID")
    recipient_user_id: str = Field(..., description="Recipient user ID")
    chain_key: str = Field(..., description="Base64 encoded chain key")
    message_number: int = Field(..., description="Message number in chain")
    previous_chain_length: int = Field(..., description="Previous chain length")
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
    
    # ========================================================================
    # Immediate Features: Participant List Enhancements
    # ========================================================================
    
    @classmethod
    def create_participant_update(
        cls,
        participant: ParticipantInfo,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a participant update message."""
        return cls(
            type=MessageType.PARTICIPANT_UPDATE,
            payload=ParticipantUpdatePayload(
                participant=participant,
                timestamp=timestamp
            ).model_dump(),
            sender_id=participant.user_id,
            room_id=room_id
        )
    
    # ========================================================================
    # Immediate Features: Room Settings
    # ========================================================================
    
    @classmethod
    def create_room_settings_update(
        cls,
        settings: RoomSettings,
        updated_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a room settings update message."""
        return cls(
            type=MessageType.ROOM_SETTINGS_UPDATE,
            payload=RoomSettingsUpdatePayload(
                settings=settings,
                updated_by=updated_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=updated_by,
            room_id=room_id
        )
    
    # ========================================================================
    # Immediate Features: Hand Raise Queue
    # ========================================================================
    
    @classmethod
    def create_hand_raise(
        cls,
        user_id: str,
        username: str,
        raised: bool,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a hand raise/lower message."""
        return cls(
            type=MessageType.HAND_RAISE,
            payload=HandRaisePayload(
                user_id=user_id,
                username=username,
                raised=raised,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    @classmethod
    def create_hand_raise_queue(
        cls,
        queue: list[HandRaiseQueueEntry],
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a hand raise queue update message."""
        return cls(
            type=MessageType.HAND_RAISE_QUEUE,
            payload=HandRaiseQueuePayload(
                queue=queue,
                timestamp=timestamp
            ).model_dump(),
            room_id=room_id
        )
    
    # ========================================================================
    # Short Term: Waiting Room
    # ========================================================================
    
    @classmethod
    def create_waiting_room_join(
        cls,
        user_id: str,
        username: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a waiting room join message."""
        return cls(
            type=MessageType.WAITING_ROOM_JOIN,
            payload=WaitingRoomJoinPayload(
                user_id=user_id,
                username=username,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    @classmethod
    def create_waiting_room_admit(
        cls,
        user_id: str,
        actioned_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a waiting room admit message."""
        return cls(
            type=MessageType.WAITING_ROOM_ADMIT,
            payload=WaitingRoomResponsePayload(
                user_id=user_id,
                actioned_by=actioned_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=actioned_by,
            room_id=room_id
        )
    
    @classmethod
    def create_waiting_room_reject(
        cls,
        user_id: str,
        actioned_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a waiting room reject message."""
        return cls(
            type=MessageType.WAITING_ROOM_REJECT,
            payload=WaitingRoomResponsePayload(
                user_id=user_id,
                actioned_by=actioned_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=actioned_by,
            room_id=room_id
        )
    
    # ========================================================================
    # Short Term: Reactions
    # ========================================================================
    
    @classmethod
    def create_reaction(
        cls,
        user_id: str,
        username: str,
        reaction_type: ReactionType,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a reaction message."""
        return cls(
            type=MessageType.REACTION,
            payload=ReactionPayload(
                user_id=user_id,
                username=username,
                reaction_type=reaction_type,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    # ========================================================================
    # Medium Term: Breakout Rooms
    # ========================================================================
    
    @classmethod
    def create_breakout_room_create(
        cls,
        config: BreakoutRoomConfig,
        created_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a breakout room creation message."""
        return cls(
            type=MessageType.BREAKOUT_ROOM_CREATE,
            payload=BreakoutRoomCreatePayload(
                config=config,
                created_by=created_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=created_by,
            room_id=room_id
        )
    
    @classmethod
    def create_breakout_room_assign(
        cls,
        user_id: str,
        breakout_room_id: str,
        assigned_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a breakout room assignment message."""
        return cls(
            type=MessageType.BREAKOUT_ROOM_ASSIGN,
            payload=BreakoutRoomAssignPayload(
                user_id=user_id,
                breakout_room_id=breakout_room_id,
                assigned_by=assigned_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=assigned_by,
            room_id=room_id
        )
    
    @classmethod
    def create_breakout_room_close(
        cls,
        breakout_room_id: str,
        closed_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a breakout room close message."""
        return cls(
            type=MessageType.BREAKOUT_ROOM_CLOSE,
            payload=BreakoutRoomClosePayload(
                breakout_room_id=breakout_room_id,
                closed_by=closed_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=closed_by,
            room_id=room_id
        )
    
    # ========================================================================
    # Medium Term: Virtual Backgrounds & Live Streaming
    # ========================================================================
    
    @classmethod
    def create_virtual_background_update(
        cls,
        user_id: str,
        background_type: VirtualBackgroundType,
        room_id: str,
        timestamp: str,
        background_url: Optional[str] = None,
        blur_intensity: Optional[int] = None
    ) -> "WebRtcMessage":
        """Create a virtual background update message."""
        return cls(
            type=MessageType.VIRTUAL_BACKGROUND_UPDATE,
            payload=VirtualBackgroundUpdatePayload(
                user_id=user_id,
                background_type=background_type,
                background_url=background_url,
                blur_intensity=blur_intensity,
                timestamp=timestamp
            ).model_dump(),
            sender_id=user_id,
            room_id=room_id
        )
    
    @classmethod
    def create_live_stream_start(
        cls,
        config: LiveStreamConfig,
        started_by: str,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a live stream start message."""
        return cls(
            type=MessageType.LIVE_STREAM_START,
            payload=LiveStreamStartPayload(
                config=config,
                started_by=started_by,
                timestamp=timestamp
            ).model_dump(),
            sender_id=started_by,
            room_id=room_id
        )
    
    @classmethod
    def create_live_stream_stop(
        cls,
        stream_id: str,
        stopped_by: str,
        duration_seconds: int,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create a live stream stop message."""
        return cls(
            type=MessageType.LIVE_STREAM_STOP,
            payload=LiveStreamStopPayload(
                stream_id=stream_id,
                stopped_by=stopped_by,
                duration_seconds=duration_seconds,
                timestamp=timestamp
            ).model_dump(),
            sender_id=stopped_by,
            room_id=room_id
        )
    
    # ========================================================================
    # Long Term: End-to-End Encryption
    # ========================================================================
    
    @classmethod
    def create_e2ee_key_exchange(
        cls,
        sender_user_id: str,
        recipient_user_id: str,
        key_type: E2EEKeyType,
        public_key: str,
        key_id: str,
        room_id: str,
        timestamp: str,
        signature: Optional[str] = None
    ) -> "WebRtcMessage":
        """Create an E2EE key exchange message."""
        return cls(
            type=MessageType.E2EE_KEY_EXCHANGE,
            payload=E2EEKeyExchangePayload(
                sender_user_id=sender_user_id,
                recipient_user_id=recipient_user_id,
                key_type=key_type,
                public_key=public_key,
                key_id=key_id,
                signature=signature,
                timestamp=timestamp
            ).model_dump(),
            sender_id=sender_user_id,
            room_id=room_id
        )
    
    @classmethod
    def create_e2ee_ratchet_update(
        cls,
        sender_user_id: str,
        recipient_user_id: str,
        chain_key: str,
        message_number: int,
        previous_chain_length: int,
        room_id: str,
        timestamp: str
    ) -> "WebRtcMessage":
        """Create an E2EE ratchet update message."""
        return cls(
            type=MessageType.E2EE_RATCHET_UPDATE,
            payload=E2EERatchetUpdatePayload(
                sender_user_id=sender_user_id,
                recipient_user_id=recipient_user_id,
                chain_key=chain_key,
                message_number=message_number,
                previous_chain_length=previous_chain_length,
                timestamp=timestamp
            ).model_dump(),
            sender_id=sender_user_id,
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
