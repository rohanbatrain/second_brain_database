"""
WebRTC Error Handling

Comprehensive error codes and structured error responses for all WebRTC operations.
Provides clear, actionable error messages with recovery strategies.
"""

from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class WebRtcErrorCode(str, Enum):
    """Standard error codes for WebRTC operations."""
    
    # Authentication & Authorization (401, 403)
    UNAUTHORIZED = "unauthorized"
    INVALID_TOKEN = "invalid_token"
    TOKEN_EXPIRED = "token_expired"
    PERMISSION_DENIED = "permission_denied"
    INSUFFICIENT_ROLE = "insufficient_role"
    
    # Rate Limiting (429)
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TOO_MANY_MESSAGES = "too_many_messages"
    TOO_MANY_REQUESTS = "too_many_requests"
    
    # Capacity & Resource Limits (403, 507)
    ROOM_FULL = "room_full"
    MAX_ROOMS_REACHED = "max_rooms_reached"
    MAX_PARTICIPANTS_REACHED = "max_participants_reached"
    STORAGE_QUOTA_EXCEEDED = "storage_quota_exceeded"
    
    # Room State (400, 404, 409)
    ROOM_NOT_FOUND = "room_not_found"
    ROOM_LOCKED = "room_locked"
    ROOM_CLOSED = "room_closed"
    ROOM_ALREADY_EXISTS = "room_already_exists"
    WAITING_ROOM_REQUIRED = "waiting_room_required"
    
    # Participant State (404, 409)
    USER_NOT_FOUND = "user_not_found"
    USER_NOT_IN_ROOM = "user_not_in_room"
    USER_ALREADY_IN_ROOM = "user_already_in_room"
    USER_BANNED = "user_banned"
    
    # Media & Signaling (400, 422)
    INVALID_SDP = "invalid_sdp"
    INVALID_ICE_CANDIDATE = "invalid_ice_candidate"
    INVALID_MESSAGE_TYPE = "invalid_message_type"
    INVALID_PAYLOAD = "invalid_payload"
    MEDIA_NOT_SUPPORTED = "media_not_supported"
    
    # Recording (400, 403, 409)
    RECORDING_NOT_ALLOWED = "recording_not_allowed"
    RECORDING_ALREADY_ACTIVE = "recording_already_active"
    RECORDING_NOT_FOUND = "recording_not_found"
    RECORDING_FAILED = "recording_failed"
    
    # File Sharing (400, 403, 413)
    FILE_TOO_LARGE = "file_too_large"
    FILE_TYPE_NOT_ALLOWED = "file_type_not_allowed"
    FILE_TRANSFER_FAILED = "file_transfer_failed"
    MALICIOUS_FILE_DETECTED = "malicious_file_detected"
    
    # Network & Connection (503, 504)
    REDIS_UNAVAILABLE = "redis_unavailable"
    MONGODB_UNAVAILABLE = "mongodb_unavailable"
    WEBSOCKET_ERROR = "websocket_error"
    CONNECTION_TIMEOUT = "connection_timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"
    
    # Validation (400, 422)
    VALIDATION_ERROR = "validation_error"
    INVALID_ROOM_ID = "invalid_room_id"
    INVALID_USER_ID = "invalid_user_id"
    INVALID_SETTINGS = "invalid_settings"
    INVALID_PARAMETER = "invalid_parameter"
    
    # General (500)
    INTERNAL_ERROR = "internal_error"
    OPERATION_FAILED = "operation_failed"
    UNKNOWN_ERROR = "unknown_error"


class WebRtcErrorResponse(BaseModel):
    """Structured error response for WebRTC operations."""
    
    error_code: WebRtcErrorCode = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retrying (for rate limits)")
    recovery_suggestion: Optional[str] = Field(None, description="Suggested action to resolve the error")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "rate_limit_exceeded",
                "message": "Too many messages sent. Please slow down.",
                "details": {
                    "limit": 100,
                    "used": 100,
                    "window_seconds": 60
                },
                "retry_after": 45,
                "recovery_suggestion": "Wait 45 seconds before sending more messages"
            }
        }


class WebRtcError(Exception):
    """Base exception for WebRTC errors."""
    
    def __init__(
        self,
        error_code: WebRtcErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        recovery_suggestion: Optional[str] = None,
        status_code: int = 400
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.retry_after = retry_after
        self.recovery_suggestion = recovery_suggestion
        self.status_code = status_code
        super().__init__(message)
    
    def to_response(self) -> WebRtcErrorResponse:
        """Convert exception to error response model."""
        return WebRtcErrorResponse(
            error_code=self.error_code,
            message=self.message,
            details=self.details,
            retry_after=self.retry_after,
            recovery_suggestion=self.recovery_suggestion
        )
    
    def to_dict(self) -> dict:
        """Convert exception to dictionary."""
        return self.to_response().model_dump(exclude_none=True)


# Specific error classes for common scenarios

class RateLimitError(WebRtcError):
    """Rate limit exceeded error."""
    
    def __init__(
        self,
        limit_type: str,
        current: int,
        max_allowed: int,
        retry_after: int
    ):
        super().__init__(
            error_code=WebRtcErrorCode.RATE_LIMIT_EXCEEDED,
            message=f"Rate limit exceeded for {limit_type}",
            details={
                "limit_type": limit_type,
                "current": current,
                "max_allowed": max_allowed,
                "retry_after": retry_after
            },
            retry_after=retry_after,
            recovery_suggestion=f"Wait {retry_after} seconds before retrying",
            status_code=429
        )


class RoomFullError(WebRtcError):
    """Room capacity exceeded error."""
    
    def __init__(self, room_id: str, max_participants: int, current_count: int):
        super().__init__(
            error_code=WebRtcErrorCode.ROOM_FULL,
            message=f"Room {room_id} is full",
            details={
                "room_id": room_id,
                "max_participants": max_participants,
                "current_participants": current_count
            },
            recovery_suggestion="Try joining a different room or wait for someone to leave",
            status_code=403
        )


class RoomLockedError(WebRtcError):
    """Room locked error."""
    
    def __init__(self, room_id: str):
        super().__init__(
            error_code=WebRtcErrorCode.ROOM_LOCKED,
            message=f"Room {room_id} is locked",
            details={"room_id": room_id},
            recovery_suggestion="Request host to unlock the room",
            status_code=403
        )


class PermissionDeniedError(WebRtcError):
    """Permission denied error."""
    
    def __init__(self, action: str, required_permission: Optional[str] = None):
        details = {"action": action}
        if required_permission:
            details["required_permission"] = required_permission
        
        super().__init__(
            error_code=WebRtcErrorCode.PERMISSION_DENIED,
            message=f"Permission denied: {action}",
            details=details,
            recovery_suggestion="Request appropriate permissions from room host",
            status_code=403
        )


class UserNotFoundError(WebRtcError):
    """User not found error."""
    
    def __init__(self, identifier: str):
        super().__init__(
            error_code=WebRtcErrorCode.USER_NOT_FOUND,
            message=f"User not found: {identifier}",
            details={"identifier": identifier},
            recovery_suggestion="Verify the user identifier is correct",
            status_code=404
        )


class RoomNotFoundError(WebRtcError):
    """Room not found error."""
    
    def __init__(self, room_id: str):
        super().__init__(
            error_code=WebRtcErrorCode.ROOM_NOT_FOUND,
            message=f"Room not found: {room_id}",
            details={"room_id": room_id},
            recovery_suggestion="Verify the room ID is correct or create a new room",
            status_code=404
        )


class ValidationError(WebRtcError):
    """Validation error."""
    
    def __init__(self, field: str, message: str, value: Any = None):
        details = {"field": field, "validation_message": message}
        if value is not None:
            details["invalid_value"] = str(value)
        
        super().__init__(
            error_code=WebRtcErrorCode.VALIDATION_ERROR,
            message=f"Validation failed: {message}",
            details=details,
            recovery_suggestion=f"Check the {field} field and correct the value",
            status_code=422
        )


class ServiceUnavailableError(WebRtcError):
    """Service unavailable error."""
    
    def __init__(self, service: str, reason: str):
        super().__init__(
            error_code=WebRtcErrorCode.SERVICE_UNAVAILABLE,
            message=f"{service} is currently unavailable",
            details={"service": service, "reason": reason},
            retry_after=30,
            recovery_suggestion="Try again in a few moments. If the problem persists, contact support.",
            status_code=503
        )


# HTTP status code mapping
ERROR_STATUS_CODES = {
    WebRtcErrorCode.UNAUTHORIZED: 401,
    WebRtcErrorCode.INVALID_TOKEN: 401,
    WebRtcErrorCode.TOKEN_EXPIRED: 401,
    WebRtcErrorCode.PERMISSION_DENIED: 403,
    WebRtcErrorCode.INSUFFICIENT_ROLE: 403,
    WebRtcErrorCode.RATE_LIMIT_EXCEEDED: 429,
    WebRtcErrorCode.TOO_MANY_MESSAGES: 429,
    WebRtcErrorCode.TOO_MANY_REQUESTS: 429,
    WebRtcErrorCode.ROOM_FULL: 403,
    WebRtcErrorCode.MAX_ROOMS_REACHED: 403,
    WebRtcErrorCode.MAX_PARTICIPANTS_REACHED: 403,
    WebRtcErrorCode.STORAGE_QUOTA_EXCEEDED: 507,
    WebRtcErrorCode.ROOM_NOT_FOUND: 404,
    WebRtcErrorCode.ROOM_LOCKED: 403,
    WebRtcErrorCode.ROOM_CLOSED: 410,
    WebRtcErrorCode.ROOM_ALREADY_EXISTS: 409,
    WebRtcErrorCode.WAITING_ROOM_REQUIRED: 403,
    WebRtcErrorCode.USER_NOT_FOUND: 404,
    WebRtcErrorCode.USER_NOT_IN_ROOM: 404,
    WebRtcErrorCode.USER_ALREADY_IN_ROOM: 409,
    WebRtcErrorCode.USER_BANNED: 403,
    WebRtcErrorCode.INVALID_SDP: 400,
    WebRtcErrorCode.INVALID_ICE_CANDIDATE: 400,
    WebRtcErrorCode.INVALID_MESSAGE_TYPE: 400,
    WebRtcErrorCode.INVALID_PAYLOAD: 400,
    WebRtcErrorCode.MEDIA_NOT_SUPPORTED: 415,
    WebRtcErrorCode.RECORDING_NOT_ALLOWED: 403,
    WebRtcErrorCode.RECORDING_ALREADY_ACTIVE: 409,
    WebRtcErrorCode.RECORDING_NOT_FOUND: 404,
    WebRtcErrorCode.RECORDING_FAILED: 500,
    WebRtcErrorCode.FILE_TOO_LARGE: 413,
    WebRtcErrorCode.FILE_TYPE_NOT_ALLOWED: 415,
    WebRtcErrorCode.FILE_TRANSFER_FAILED: 500,
    WebRtcErrorCode.MALICIOUS_FILE_DETECTED: 403,
    WebRtcErrorCode.REDIS_UNAVAILABLE: 503,
    WebRtcErrorCode.MONGODB_UNAVAILABLE: 503,
    WebRtcErrorCode.WEBSOCKET_ERROR: 500,
    WebRtcErrorCode.CONNECTION_TIMEOUT: 504,
    WebRtcErrorCode.SERVICE_UNAVAILABLE: 503,
    WebRtcErrorCode.VALIDATION_ERROR: 422,
    WebRtcErrorCode.INVALID_ROOM_ID: 400,
    WebRtcErrorCode.INVALID_USER_ID: 400,
    WebRtcErrorCode.INVALID_SETTINGS: 400,
    WebRtcErrorCode.INVALID_PARAMETER: 400,
    WebRtcErrorCode.INTERNAL_ERROR: 500,
    WebRtcErrorCode.OPERATION_FAILED: 500,
    WebRtcErrorCode.UNKNOWN_ERROR: 500,
}


def get_error_status_code(error_code: WebRtcErrorCode) -> int:
    """Get HTTP status code for an error code."""
    return ERROR_STATUS_CODES.get(error_code, 500)
