"""
OAuth2 error handling and logging utilities.

This module provides centralized error handling for OAuth2 operations,
following RFC 6749 error response standards and integrating with the
existing logging system for comprehensive audit trails.

Enhanced for Task 8: Comprehensive Error Handling
- Browser-friendly error responses for OAuth2 errors
- Error page templates for common OAuth2 error scenarios
- Error logging for browser-based OAuth2 flows
- User guidance in error messages
- Proper error codes and descriptions
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
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
    
    Enhanced for comprehensive error handling:
    - Browser-friendly HTML error responses
    - Detailed error logging for browser flows
    - User-friendly error messages with guidance
    - Proper error categorization and severity
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[OAuth2 Error Handler]")
    
    def browser_error(
        self,
        error_code: OAuth2ErrorCode,
        error_description: str,
        user_friendly_message: Optional[str] = None,
        client_id: Optional[str] = None,
        client_name: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        severity: OAuth2ErrorSeverity = OAuth2ErrorSeverity.LOW,
        additional_context: Optional[Dict[str, Any]] = None,
        show_login_button: bool = True,
        show_back_button: bool = True
    ) -> HTMLResponse:
        """
        Create browser-friendly OAuth2 error response with HTML template.
        
        This method provides user-friendly error pages for browser-based OAuth2 flows,
        with appropriate guidance and actions for users to resolve issues.
        
        Args:
            error_code: Standard OAuth2 error code
            error_description: Technical error description for logging
            user_friendly_message: User-friendly error message (auto-generated if None)
            client_id: OAuth2 client identifier
            client_name: Human-readable client name
            user_id: User identifier (for logging)
            request: FastAPI request object (for logging)
            severity: Error severity level
            additional_context: Additional context for logging
            show_login_button: Whether to show login button
            show_back_button: Whether to show back button
            
        Returns:
            HTMLResponse with user-friendly error page
        """
        # Import templates here to avoid circular imports
        from .templates import render_oauth2_authorization_error, render_generic_oauth2_error
        
        # Generate user-friendly message if not provided
        if not user_friendly_message:
            user_friendly_message = self._get_user_friendly_message(error_code, client_name)
        
        # Log the error with comprehensive context
        self._log_oauth2_error(
            error_type="browser_error",
            error_code=error_code,
            error_description=error_description,
            client_id=client_id,
            user_id=user_id,
            request=request,
            severity=severity,
            additional_context={
                "user_friendly_message": user_friendly_message,
                "client_name": client_name,
                "show_login_button": show_login_button,
                "show_back_button": show_back_button,
                **(additional_context or {})
            }
        )
        
        # Determine appropriate template and content
        if error_code in [OAuth2ErrorCode.INVALID_CLIENT, OAuth2ErrorCode.UNAUTHORIZED_CLIENT]:
            # Use specific authorization error template for client-related errors
            error_html = render_oauth2_authorization_error(
                error_message=user_friendly_message,
                error_details=self._get_error_details(error_code),
                client_name=client_name or client_id
            )
        else:
            # Use generic error template for other errors
            error_html = render_generic_oauth2_error(
                title=self._get_error_title(error_code),
                message=user_friendly_message,
                icon=self._get_error_icon(error_code),
                show_login_button=show_login_button,
                show_back_button=show_back_button,
                additional_info=self._get_troubleshooting_info(error_code)
            )
        
        # Determine HTTP status code
        status_code = self._get_http_status_code(error_code)
        
        return HTMLResponse(content=error_html, status_code=status_code)

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
        additional_context: Optional[Dict[str, Any]] = None,
        is_browser_request: bool = False,
        client_name: Optional[str] = None
    ) -> RedirectResponse:
        """
        Create OAuth2 authorization error response with redirect or browser-friendly page.
        
        For authorization endpoint errors, the error is typically returned
        to the client via redirect to the redirect_uri with error parameters.
        For browser requests without valid redirect_uri, returns HTML error page.
        
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
            is_browser_request: Whether this is a browser request
            client_name: Human-readable client name for browser errors
            
        Returns:
            RedirectResponse with OAuth2 error parameters or HTMLResponse for browser errors
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
        
        # If no redirect URI and this is a browser request, return HTML error page
        if not redirect_uri:
            self.logger.warning(f"Authorization error without redirect_uri: {error_code}")
            if is_browser_request:
                return self.browser_error(
                    error_code=error_code,
                    error_description=error_description,
                    client_id=client_id,
                    client_name=client_name,
                    user_id=user_id,
                    request=request,
                    severity=severity,
                    additional_context=additional_context
                )
            else:
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
    
    def _get_user_friendly_message(self, error_code: OAuth2ErrorCode, client_name: Optional[str] = None) -> str:
        """
        Get user-friendly error message for browser display.
        
        Args:
            error_code: OAuth2 error code
            client_name: Optional client name for context
            
        Returns:
            User-friendly error message
        """
        client_context = f" for {client_name}" if client_name else ""
        
        user_friendly_messages = {
            OAuth2ErrorCode.INVALID_REQUEST: f"There was a problem with the authorization request{client_context}. Please check the application link and try again.",
            OAuth2ErrorCode.INVALID_CLIENT: f"The application{client_context} is not properly configured or has been disabled. Please contact the application developer.",
            OAuth2ErrorCode.UNAUTHORIZED_CLIENT: f"The application{client_context} is not authorized to request access. Please contact the application developer.",
            OAuth2ErrorCode.ACCESS_DENIED: f"You have denied access to the application{client_context}. You can close this window or try again if this was a mistake.",
            OAuth2ErrorCode.UNSUPPORTED_RESPONSE_TYPE: f"The application{client_context} is using an unsupported authorization method. Please contact the application developer.",
            OAuth2ErrorCode.INVALID_SCOPE: f"The application{client_context} is requesting permissions it's not allowed to access. Please contact the application developer.",
            OAuth2ErrorCode.INVALID_REDIRECT_URI: f"The application{client_context} has an invalid redirect configuration. Please contact the application developer.",
            OAuth2ErrorCode.RATE_LIMIT_EXCEEDED: "Too many authorization attempts. Please wait a few minutes before trying again.",
            OAuth2ErrorCode.SERVER_ERROR: "A temporary server error occurred. Please try again in a few moments.",
            OAuth2ErrorCode.TEMPORARILY_UNAVAILABLE: "The authorization service is temporarily unavailable. Please try again later.",
            OAuth2ErrorCode.INVALID_GRANT: f"The authorization request{client_context} has expired or is invalid. Please start the authorization process again.",
            OAuth2ErrorCode.UNSUPPORTED_GRANT_TYPE: f"The application{client_context} is using an unsupported authorization method. Please contact the application developer."
        }
        
        return user_friendly_messages.get(error_code, f"An authorization error occurred{client_context}. Please try again or contact support if the problem persists.")
    
    def _get_error_title(self, error_code: OAuth2ErrorCode) -> str:
        """
        Get appropriate error title for browser display.
        
        Args:
            error_code: OAuth2 error code
            
        Returns:
            Error title
        """
        error_titles = {
            OAuth2ErrorCode.INVALID_REQUEST: "Invalid Authorization Request",
            OAuth2ErrorCode.INVALID_CLIENT: "Application Not Found",
            OAuth2ErrorCode.UNAUTHORIZED_CLIENT: "Application Not Authorized",
            OAuth2ErrorCode.ACCESS_DENIED: "Access Denied",
            OAuth2ErrorCode.UNSUPPORTED_RESPONSE_TYPE: "Unsupported Authorization Method",
            OAuth2ErrorCode.INVALID_SCOPE: "Invalid Permissions Request",
            OAuth2ErrorCode.INVALID_REDIRECT_URI: "Invalid Application Configuration",
            OAuth2ErrorCode.RATE_LIMIT_EXCEEDED: "Too Many Requests",
            OAuth2ErrorCode.SERVER_ERROR: "Server Error",
            OAuth2ErrorCode.TEMPORARILY_UNAVAILABLE: "Service Unavailable",
            OAuth2ErrorCode.INVALID_GRANT: "Authorization Expired",
            OAuth2ErrorCode.UNSUPPORTED_GRANT_TYPE: "Unsupported Grant Type"
        }
        
        return error_titles.get(error_code, "Authorization Error")
    
    def _get_error_icon(self, error_code: OAuth2ErrorCode) -> str:
        """
        Get appropriate emoji icon for error display.
        
        Args:
            error_code: OAuth2 error code
            
        Returns:
            Emoji icon
        """
        error_icons = {
            OAuth2ErrorCode.INVALID_REQUEST: "❌",
            OAuth2ErrorCode.INVALID_CLIENT: "🚫",
            OAuth2ErrorCode.UNAUTHORIZED_CLIENT: "🔒",
            OAuth2ErrorCode.ACCESS_DENIED: "⛔",
            OAuth2ErrorCode.UNSUPPORTED_RESPONSE_TYPE: "⚠️",
            OAuth2ErrorCode.INVALID_SCOPE: "🔐",
            OAuth2ErrorCode.INVALID_REDIRECT_URI: "🔗",
            OAuth2ErrorCode.RATE_LIMIT_EXCEEDED: "⏱️",
            OAuth2ErrorCode.SERVER_ERROR: "🔧",
            OAuth2ErrorCode.TEMPORARILY_UNAVAILABLE: "🚧",
            OAuth2ErrorCode.INVALID_GRANT: "⏰",
            OAuth2ErrorCode.UNSUPPORTED_GRANT_TYPE: "⚠️"
        }
        
        return error_icons.get(error_code, "⚠️")
    
    def _get_error_details(self, error_code: OAuth2ErrorCode) -> str:
        """
        Get technical error details for display.
        
        Args:
            error_code: OAuth2 error code
            
        Returns:
            Technical error details
        """
        error_details = {
            OAuth2ErrorCode.INVALID_REQUEST: "The request is missing required parameters, includes invalid parameter values, or is otherwise malformed.",
            OAuth2ErrorCode.INVALID_CLIENT: "Client authentication failed or the client is not registered.",
            OAuth2ErrorCode.UNAUTHORIZED_CLIENT: "The client is not authorized to request an authorization code using this method.",
            OAuth2ErrorCode.ACCESS_DENIED: "The resource owner or authorization server denied the request.",
            OAuth2ErrorCode.UNSUPPORTED_RESPONSE_TYPE: "The authorization server does not support obtaining an authorization code using this method.",
            OAuth2ErrorCode.INVALID_SCOPE: "The requested scope is invalid, unknown, or malformed.",
            OAuth2ErrorCode.INVALID_REDIRECT_URI: "The redirect URI provided does not match the registered redirect URIs.",
            OAuth2ErrorCode.RATE_LIMIT_EXCEEDED: "The client has exceeded the allowed number of requests in the given time period.",
            OAuth2ErrorCode.SERVER_ERROR: "The authorization server encountered an unexpected condition that prevented it from fulfilling the request.",
            OAuth2ErrorCode.TEMPORARILY_UNAVAILABLE: "The authorization server is currently unable to handle the request due to temporary overloading or maintenance.",
            OAuth2ErrorCode.INVALID_GRANT: "The provided authorization grant is invalid, expired, revoked, or does not match the redirect URI.",
            OAuth2ErrorCode.UNSUPPORTED_GRANT_TYPE: "The authorization grant type is not supported by the authorization server."
        }
        
        return error_details.get(error_code, "An OAuth2 protocol error occurred.")
    
    def _get_troubleshooting_info(self, error_code: OAuth2ErrorCode) -> str:
        """
        Get troubleshooting information for users.
        
        Args:
            error_code: OAuth2 error code
            
        Returns:
            HTML troubleshooting information
        """
        troubleshooting_info = {
            OAuth2ErrorCode.INVALID_REQUEST: """
                <strong>Troubleshooting:</strong><br>
                • Make sure you're using the correct authorization link<br>
                • Check that the link hasn't been modified or corrupted<br>
                • Try copying and pasting the link again<br>
                • Contact the application developer if the problem persists
            """,
            OAuth2ErrorCode.INVALID_CLIENT: """
                <strong>Troubleshooting:</strong><br>
                • Verify the application is still active and available<br>
                • Check that you're using the correct application link<br>
                • The application may have been removed or disabled<br>
                • Contact the application developer for assistance
            """,
            OAuth2ErrorCode.UNAUTHORIZED_CLIENT: """
                <strong>Troubleshooting:</strong><br>
                • The application may not be properly configured<br>
                • Contact the application developer to report this issue<br>
                • Try again later in case this is a temporary configuration issue
            """,
            OAuth2ErrorCode.ACCESS_DENIED: """
                <strong>What happened:</strong><br>
                • You chose to deny access to the application<br>
                • This is normal if you don't want to grant permissions<br>
                • You can close this window or start over if you changed your mind
            """,
            OAuth2ErrorCode.RATE_LIMIT_EXCEEDED: """
                <strong>Troubleshooting:</strong><br>
                • Wait 5-10 minutes before trying again<br>
                • Avoid repeatedly clicking authorization links<br>
                • Clear your browser cache and cookies<br>
                • Contact support if you continue to see this error
            """,
            OAuth2ErrorCode.SERVER_ERROR: """
                <strong>Troubleshooting:</strong><br>
                • This is usually a temporary issue<br>
                • Try again in a few minutes<br>
                • Check your internet connection<br>
                • Contact support if the problem persists
            """,
            OAuth2ErrorCode.TEMPORARILY_UNAVAILABLE: """
                <strong>Troubleshooting:</strong><br>
                • The service may be undergoing maintenance<br>
                • Try again in 10-15 minutes<br>
                • Check the application's status page if available<br>
                • Contact support if the issue continues
            """,
            OAuth2ErrorCode.INVALID_GRANT: """
                <strong>Troubleshooting:</strong><br>
                • Your authorization session may have expired<br>
                • Start the authorization process from the beginning<br>
                • Make sure you complete the process within the time limit<br>
                • Clear your browser cache and cookies if the problem persists
            """
        }
        
        return troubleshooting_info.get(error_code, """
            <strong>Troubleshooting:</strong><br>
            • Try refreshing the page<br>
            • Clear your browser cache and cookies<br>
            • Make sure JavaScript is enabled<br>
            • Contact support if the problem continues
        """)


# Global error handler instance
oauth2_error_handler = OAuth2ErrorHandler()


# Convenience functions for common error scenarios
def invalid_request_error(
    description: str,
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    is_browser_request: bool = False,
    **kwargs
):
    """Create invalid_request error response with browser support."""
    if redirect_uri or is_browser_request:
        return oauth2_error_handler.authorization_error(
            error_code=OAuth2ErrorCode.INVALID_REQUEST,
            error_description=description,
            redirect_uri=redirect_uri,
            state=state,
            is_browser_request=is_browser_request,
            **kwargs
        )
    else:
        return oauth2_error_handler.token_error(
            error_code=OAuth2ErrorCode.INVALID_REQUEST,
            error_description=description,
            **kwargs
        )


def invalid_client_error(
    description: str = "Client authentication failed", 
    is_browser_request: bool = False,
    **kwargs
):
    """Create invalid_client error response with browser support."""
    if is_browser_request:
        return oauth2_error_handler.browser_error(
            error_code=OAuth2ErrorCode.INVALID_CLIENT,
            error_description=description,
            severity=OAuth2ErrorSeverity.MEDIUM,
            **kwargs
        )
    else:
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
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    description: str = "User denied authorization",
    is_browser_request: bool = False,
    **kwargs
):
    """Create access_denied error response with browser support."""
    return oauth2_error_handler.authorization_error(
        error_code=OAuth2ErrorCode.ACCESS_DENIED,
        error_description=description,
        redirect_uri=redirect_uri,
        state=state,
        is_browser_request=is_browser_request,
        **kwargs
    )


def server_error(
    description: str = "Internal server error",
    redirect_uri: Optional[str] = None,
    state: Optional[str] = None,
    is_browser_request: bool = False,
    **kwargs
):
    """Create server_error response with browser support."""
    if redirect_uri or is_browser_request:
        return oauth2_error_handler.authorization_error(
            error_code=OAuth2ErrorCode.SERVER_ERROR,
            error_description=description,
            redirect_uri=redirect_uri,
            state=state,
            is_browser_request=is_browser_request,
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


def rate_limit_error(
    description: str = "Rate limit exceeded", 
    is_browser_request: bool = False,
    **kwargs
):
    """Create rate limit error response with browser support."""
    if is_browser_request:
        return oauth2_error_handler.browser_error(
            error_code=OAuth2ErrorCode.RATE_LIMIT_EXCEEDED,
            error_description=description,
            severity=OAuth2ErrorSeverity.HIGH,
            **kwargs
        )
    else:
        return oauth2_error_handler.token_error(
            error_code=OAuth2ErrorCode.RATE_LIMIT_EXCEEDED,
            error_description=description,
            severity=OAuth2ErrorSeverity.HIGH,
            **kwargs
        )