"""
WebRTC WebSocket Authentication Dependencies

Provides authentication for WebSocket connections using JWT tokens
passed as query parameters.
"""

from typing import Optional
from fastapi import WebSocket, status
from fastapi.exceptions import WebSocketException

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[WebRTC-Auth]")


async def get_current_user_ws(websocket: WebSocket) -> dict:
    """
    Authenticate WebSocket connection using JWT token from query parameters.
    
    Uses the same authentication logic as the REST API by leveraging the
    existing get_current_user function from the auth module.
    
    Args:
        websocket: The WebSocket connection
        
    Returns:
        User dict with user information
        
    Raises:
        WebSocketException: If authentication fails
    """
    try:
        # Import here to avoid circular imports
        from second_brain_database.routes.auth.services.auth.login import get_current_user
        
        # Extract token from query parameters
        token = websocket.query_params.get("token")
        
        if not token:
            logger.warning(
                "WebSocket connection attempt without token",
                extra={"client": websocket.client}
            )
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Authentication token required in query parameters"
            )
        
        # Use the existing get_current_user function for validation
        # This ensures consistency with REST API authentication
        try:
            user = await get_current_user(token)
            
            if not user:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Invalid token: user not found"
                )
            
            if not user.get("is_active", False):
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="User account is not active"
                )
            
            username = user.get("username") or user.get("email")
            logger.info(
                f"WebSocket authenticated for user {username}",
                extra={"user_id": str(user["_id"]), "client": websocket.client}
            )
            
            return user
            
        except Exception as e:
            # Convert HTTPException or other auth errors to WebSocketException
            error_msg = str(e)
            if hasattr(e, 'detail'):
                error_msg = e.detail
            
            logger.warning(
                f"WebSocket authentication failed: {error_msg}",
                extra={"error": error_msg}
            )
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=f"Authentication failed: {error_msg}"
            )
            
    except WebSocketException:
        raise
    except Exception as e:
        logger.error(
            f"WebSocket authentication error: {e}",
            extra={"error": str(e)},
            exc_info=True
        )
        raise WebSocketException(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Authentication failed due to internal error"
        )


def validate_room_id(room_id: str) -> str:
    """
    Validate and sanitize room ID.
    
    Args:
        room_id: The room identifier
        
    Returns:
        Sanitized room ID
        
    Raises:
        WebSocketException: If room ID is invalid
    """
    if not room_id or not room_id.strip():
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid room ID"
        )
    
    # Sanitize room ID (alphanumeric, dashes, underscores only)
    sanitized = "".join(c for c in room_id if c.isalnum() or c in "-_")
    
    if not sanitized or len(sanitized) > 100:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Room ID must be alphanumeric (with dashes/underscores) and max 100 characters"
        )
    
    return sanitized
