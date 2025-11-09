"""
WebRTC Module

Production-ready WebRTC signaling server with Redis Pub/Sub for horizontal scaling.
"""

from second_brain_database.webrtc.router import router
from second_brain_database.webrtc.schemas import (
    WebRtcMessage,
    WebRtcConfig,
    IceServerConfig,
    MessageType
)
from second_brain_database.webrtc.connection_manager import webrtc_manager

__all__ = [
    "router",
    "WebRtcMessage",
    "WebRtcConfig",
    "IceServerConfig",
    "MessageType",
    "webrtc_manager"
]
