"""
OAuth2 error handling and logging utilities.

This module provides centralized error handling for OAuth2 operations,
following RFC 6749 error response standards and integrating with the
existing logging system for comprehensive audit trails.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import JSONResponse, RedirectResponse
from urllib.parse import urlencode

from second_brain_database.managers.logging_manager import get_logger
from .models import OAuth2Error

logger = get_logger(prefix="[OAuth2 Error Handler]")


class OAuth2ErrorCode(str, Enum):
    """
    Standard OAuth2 error codes as defined in RFC 6749.
    
    These error codes are used in both authorization and token endpoint responses.
    """
    
    # Authorization endpoint errors (RFC 6749 Section 4.1.2.1)
    INVALID_REQUEST = "invalid_request"
    UNAUTHORIZED_CLIENT = "unauthorized_client"
    ACCESS_DENIED = "access_denied"
    UNSUPPORTED_RESPONSE_TYPE = "unsupported_response_type"
    INVALID_SCOPE = "invalid_scope"
    SERVER_ERROR = "server_error"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    
    # Token endpoint errors (RFC 6749 Section 5.2)
    INVALID_CLIENT = "invalid_client"
    INVALID_GRANT = "invalid_grant"
    UNSUPPORTED_GRANT_TYPE = "unsupported_grant_type"
    
    # Additional security-related errors
    INVALID_REDIRECT_URI = "invalid_redirect_uri"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PKCE_VALIDATION_FAILED = "invalid_grant"  # Maps to invalid_grant per RFC 7636


class OAuth2ErrorSeverity(str, Enum):
    """Error severity levels for logging and monitoring."""
    
    LOW = "low"          # User errors, validation failures
    MEDIUM = "medium"    # Client configuration issues
    HIGH = "high"        # Security violations, abuse attempts
    CRITICAL = "critical"  # System failures, security breaches


class OAuth2ErrorHandler:
    """
    Centralized OAuth2 error handling and logging.
    
    This class provides standardized error responses and comprehensive logging
    for all OAuth2 operations, ensuring consistent error handling across
    authorization and token endpoints.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[OAuth2 Error Handler]")
    
    def authorization_error(
        self,
        error_code: OAuth2ErrorCode,
        error_description: str,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        severity: OAuth2ErrorSeverity = OAuth2ErrorSeverity.LOW,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> RedirectResponse:
        """
        Create OAuth2 authorization error response with redirect.
        
        For authorization endpoint errors, the error is typically returned
        to the client via redirect to the redirect_uri with error parameters.
        
        Args:
            error_code: Standard OAuth2 error code
            error_description: Human-readable error description
            redirect_uri: Client redirect URI for error delivery
            state: Client state parameter (if provided in request)
            client_id: OAuth2 client identifier (for logging)
            user_id: User identifier (for logging)
            request: FastAPI request object (for logging)
            severity: Error severity level
            additional_context: Additional context for logging
            
        Returns:
            RedirectResponse with OAuth2 error parameters
        """
        # Log the error with full context
        self._log_oauth2_error(
            error_type="authorization_error",
            error_code=error_code,
            error_description=error_description,
            client_id=client_id,
            user_id=user_id,
            request=request,
            severity=severity,
            additional_context={
                "redirect_uri": redirect_uri,
                "state": state,
                **(additional_context or {})
            }
        )
        
        # If no redirect URI, return JSON error (shouldn't happen in normal flow)
        if not redirect_uri:
            self.logger.warning(f"Authorization error without redirect_uri: {error_code}")
            return self.token_error(
                error_code=error_code,
                error_description=error_description,
                client_id=client_id,
                user_id=user_id,
                request=request,
                severity=severity,
                additional_context=additional_context
            )
        
        # Build error parameters
        error_params = {
            "error": error_code.value,
            "error_description": error_description
        }
        
        if state:
            error_params["state"] = state
        
        # Build redirect URL with error parameters
        separator = "&" if "?" in redirect_uri else "?"
        redirect_url = f"{redirect_uri}{separator}{urlencode(error_params)}"
        
        self.logger.debug(f"Redirecting to client with error: {error_code.value}")
        return RedirectResponse(url=redirect_url, status_code=302)
    
    def token_error(
        self,
        error_code: OAuth2ErrorCode,
        error_description: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        severity: OAuth2ErrorSeverity = OAuth2ErrorSeverity.LOW,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """
        Create OAuth2 token error response.
        
        For token endpoint errors, the error is returned as JSON response
        with appropriate HTTP status code.
        
        Args:
            error_code: Standard OAuth2 error code
            error_description: Human-readable error description
            client_id: OAuth2 client identifier (for logging)
            user_id: User identifier (for logging)
            request: FastAPI request object (for logging)
            severity: Error severity level
            additional_context: Additional context for logging
            
        Returns:
            JSONResponse with OAuth2 error format
        """
        # Log the error with full context
        self._log_oauth2_error(
            error_type="token_error",
            error_code=error_code,
            error_description=error_description,
            client_id=client_id,
            user_id=user_id,
            request=request,
            severity=severity,
            additional_context=additional_context
        )
        
        # Create OAuth2 error response
        error_response = OAuth2Error(
            error=error_code.value,
            error_description=error_description
        )
        
        # Determine HTTP status code based on error type
        status_code = self._get_http_status_code(error_code)
        
        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump()
        )
    
    def security_error(
        self,
        error_code: OAuth2ErrorCode,
        error_description: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        security_event_type: str = "security_violation",
        additional_context: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """
        Handle security-related OAuth2 errors with enhanced logging.
        
        Security errors require special handling with detailed logging
        for monitoring and alerting purposes.
        
        Args:
            error_code: Standard OAuth2 error code
            error_description: Human-readable error description
            client_id: OAuth2 client identifier
            user_id: User identifier
            request: FastAPI request object
            security_event_type: Type of security event
            additional_context: Additional security context
            
        Returns:
            JSONResponse with OAuth2 error format
        """
        # Enhanced logging for security events
        security_context = {
            "security_event": True,
            "event_type": security_event_type,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        if request:
            security_context.update({
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "request_method": request.method,
                "request_url": str(request.url)
            })
        
        return self.token_error(
            error_code=error_code,
            error_description=error_description,
            client_id=client_id,
            user_id=user_id,
            request=request,
            severity=OAuth2ErrorSeverity.HIGH,
            additional_context=security_context
        )
    
    def _log_oauth2_error(
        self,
        error_type: str,
        error_code: OAuth2ErrorCode,
        error_description: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        severity: OAuth2ErrorSeverity = OAuth2ErrorSeverity.LOW,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 error with comprehensive context.
        
        This method provides structured logging for all OAuth2 errors,
        including security context, client information, and request details.
        
        Args:
            error_type: Type of error (authorization_error, token_error, etc.)
            error_code: Standard OAuth2 error code
            error_description: Human-readable error description
            client_id: OAuth2 client identifier
            user_id: User identifier
            request: FastAPI request object
            severity: Error severity level
            additional_context: Additional context for logging
        """
        # Build comprehensive log context
        log_context = {
            "error_type": error_type,
            "error_code": error_code.value,
            "error_description": error_description,
            "severity": severity.value,
            "timestamp": datetime.utcnow().isoformat(),
            "client_id": client_id,
            "user_id": user_id,
            **(additional_context or {})
        }
        
        # Add request context if available
        if request:
            log_context.update({
                "request_method": request.method,
                "request_url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "request_headers": dict(request.headers) if severity == OAuth2ErrorSeverity.CRITICAL else None
            })
        
        # Log with appropriate level based on severity
        log_message = f"OAuth2 {error_type}: {error_code.value} - {error_description}"
        
        if severity == OAuth2ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, extra={"oauth2_context": log_context})
        elif severity == OAuth2ErrorSeverity.HIGH:
            self.logger.error(log_message, extra={"oauth2_context": log_context})
        elif severity == OAuth2ErrorSeverity.MEDIUM:
            self.logger.warning(log_message, extra={"oauth2_context": log_context})
        else:
            self.logger.info(log_message, extra={"oauth2_context": log_context})
    
    def _get_http_status_code(self, error_code: OAuth2ErrorCode) -> int:
        """
        Get appropriate HTTP status code for OAuth2 error.
        
        Args:
            error_code: OAuth2 error code
            
        Returns:
            HTTP status code
        """
        status_code_mapping = {
            OAuth2ErrorCode.INVALID_REQUEST: 400,
            OAuth2ErrorCode.INVALID_CLIENT: 400,  # Changed from 401 to 400 for OAuth2 spec compliance
            OAuth2ErrorCode.UNAUTHORIZED_CLIENT: 400,  # Changed from 401 to 400 for OAuth2 spec compliance
            OAuth2ErrorCode.ACCESS_DENIED: 403,
            OAuth2ErrorCode.INVALID_GRANT: 400,
            OAuth2ErrorCode.UNSUPPORTED_GRANT_TYPE: 400,
            OAuth2ErrorCode.UNSUPPORTED_RESPONSE_TYPE: 400,
            OAuth2ErrorCode.INVALID_SCOPE: 400,
            OAuth2ErrorCode.INVALID_REDIRECT_URI: 400,
            OAuth2ErrorCode.RATE_LIMIT_EXCEEDED: 429,
            OAuth2ErrorCode.SERVER_ERROR: 500,
            OAuth2ErrorCode.TEMPORARILY_UNAVAILABLE: 503,
        }
        
        return status_code_mapping.get(error_code, 400)


# Global error handler instance
oauth2_error_handler = OAuth2ErrorHandler()


# Convenience functions for common error scenarios
def invalid_request_error(
    description: str,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    **kwargs
):
    """Create invalid_request error response."""
    if redirect_uri:
        return oauth2_error_handler.authorization_error(
            error_code=OAuth2ErrorCode.INVALID_REQUEST,
            error_description=description,
            redirect_uri=redirect_uri,
            state=state,
            **kwargs
        )
    else:
        return oauth2_error_handler.token_error(
            error_code=OAuth2ErrorCode.INVALID_REQUEST,
            error_description=description,
            **kwargs
        )


def invalid_client_error(description: str = "Client authentication failed", **kwargs):
    """Create invalid_client error response."""
    return oauth2_error_handler.token_error(
        error_code=OAuth2ErrorCode.INVALID_CLIENT,
        error_description=description,
        severity=OAuth2ErrorSeverity.MEDIUM,
        **kwargs
    )


def invalid_grant_error(description: str, **kwargs):
    """Create invalid_grant error response."""
    return oauth2_error_handler.token_error(
        error_code=OAuth2ErrorCode.INVALID_GRANT,
        error_description=description,
        **kwargs
    )


def access_denied_error(
    redirect_uri: str,
    state: Optional[str] = None,
    description: str = "User denied authorization",
    **kwargs
):
    """Create access_denied error response."""
    return oauth2_error_handler.authorization_error(
        error_code=OAuth2ErrorCode.ACCESS_DENIED,
        error_description=description,
        redirect_uri=redirect_uri,
        state=state,
        **kwargs
    )


def server_error(
    description: str = "Internal server error",
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    **kwargs
):
    """Create server_error response."""
    if redirect_uri:
        return oauth2_error_handler.authorization_error(
            error_code=OAuth2ErrorCode.SERVER_ERROR,
            error_description=description,
            redirect_uri=redirect_uri,
            state=state,
            severity=OAuth2ErrorSeverity.CRITICAL,
            **kwargs
        )
    else:
        return oauth2_error_handler.token_error(
            error_code=OAuth2ErrorCode.SERVER_ERROR,
            error_description=description,
            severity=OAuth2ErrorSeverity.CRITICAL,
            **kwargs
        )


def security_violation_error(
    description: str,
    security_event_type: str = "security_violation",
    **kwargs
):
    """Create security violation error response."""
    return oauth2_error_handler.security_error(
        error_code=OAuth2ErrorCode.INVALID_REQUEST,
        error_description=description,
        security_event_type=security_event_type,
        **kwargs
    )


def rate_limit_error(description: str = "Rate limit exceeded", **kwargs):
    """Create rate limit error response."""
    return oauth2_error_handler.token_error(
        error_code=OAuth2ErrorCode.RATE_LIMIT_EXCEEDED,
        error_description=description,
        severity=OAuth2ErrorSeverity.HIGH,
        **kwargs
    )