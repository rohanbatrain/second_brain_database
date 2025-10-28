"""Helpers for lightweight LiveKit integration.

This module provides a small helper to generate LiveKit access tokens from the
server-side. The LiveKit token format may evolve; this helper creates a simple
JWT signed with the provided API secret. The generated token should be
validated against your LiveKit deployment. For production usage prefer the
official LiveKit SDK or verify the exact token shape required by your server
version.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from jose import jwt


def create_access_token(api_key: str, api_secret: str, identity: str, room: Optional[str] = None, ttl_seconds: int = 3600, can_publish: bool = True, can_subscribe: bool = True) -> str:
    """Create a simple LiveKit-style access token (JWT).

    Note: LiveKit's official token structure includes specific 'scope' and
    'grants'. This helper produces a basic HS256-signed JWT with common claims.

    Args:
        api_key: LiveKit API key (iss)
        api_secret: LiveKit API secret (signing key)
        identity: The identity/subject for the token (sub)
        room: Optional room name to restrict the token
        ttl_seconds: Token lifetime in seconds
        can_publish: Allow publishing tracks
        can_subscribe: Allow subscribing to tracks

    Returns:
        Signed JWT string.
    """
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())

    payload = {
        "jti": jti,
        "iss": api_key,
        "sub": identity,
        "nbf": int(now.timestamp()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
        # LiveKit-specific grants
        "video": {
            "room": room,
            "roomJoin": True,
            "canPublish": can_publish,
            "canSubscribe": can_subscribe,
        },
        "type": "access",
    }

    token = jwt.encode(payload, api_secret, algorithm="HS256")
    return token


__all__ = ["create_access_token"]
