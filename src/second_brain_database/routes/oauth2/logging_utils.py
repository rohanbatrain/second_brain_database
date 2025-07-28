"""
OAuth2 logging utilities for comprehensive audit trails.

This module provides specialized logging functions for OAuth2 operations,
integrating with the existing logging system to provide detailed audit trails
for security monitoring and debugging purposes.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from fastapi import Request

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[OAuth2 Logging]")


class OAuth2EventType(str, Enum):
    """OAuth2 event types for structured logging."""
    
    # Authorization flow events
    AUTHORIZATION_REQUEST = "authorization_request"
    AUTHORIZATION_GRANTED = "authorization_granted"
    AUTHORIZATION_DENIED = "authorization_denied"
    CONSENT_SHOWN = "consent_shown"
    CONSENT_GRANTED = "consent_granted"
    CONSENT_DENIED = "consent_denied"
    CONSENT_REVOKED = "consent_revoked"
    
    # Token flow events
    TOKEN_REQUEST = "token_request"
    TOKEN_ISSUED = "token_issued"
    TOKEN_REFRESH = "token_refresh"
    TOKEN_REVOKED = "token_revoked"
    
    # Client management events
    CLIENT_REGISTERED = "client_registered"
    CLIENT_AUTHENTICATED = "client_authenticated"
    CLIENT_AUTHENTICATION_FAILED = "client_authentication_failed"
    
    # Security events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PKCE_VALIDATION_FAILED = "pkce_validation_failed"
    INVALID_REDIRECT_URI = "invalid_redirect_uri"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    
    # Error events
    AUTHORIZATION_ERROR = "authorization_error"
    TOKEN_ERROR = "token_error"
    VALIDATION_ERROR = "validation_error"
    SYSTEM_ERROR = "system_error"


class OAuth2Logger:
    """
    Specialized logger for OAuth2 operations.
    
    Provides structured logging with consistent format and comprehensive
    context for all OAuth2 events, enabling effective monitoring and debugging.
    """
    
    def __init__(self):
        self.logger = get_logger(prefix="[OAuth2 Operations]")
    
    def log_authorization_request(
        self,
        client_id: str,
        user_id: Optional[str],
        scopes: List[str],
        redirect_uri: str,
        state: str,
        code_challenge_method: str,
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 authorization request.
        
        Args:
            client_id: OAuth2 client identifier
            user_id: User identifier (if authenticated)
            scopes: Requested scopes
            redirect_uri: Client redirect URI
            state: Client state parameter
            code_challenge_method: PKCE challenge method
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": OAuth2EventType.AUTHORIZATION_REQUEST.value,
            "client_id": client_id,
            "user_id": user_id,
            "scopes": scopes,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge_method": code_challenge_method,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        self.logger.info(
            f"OAuth2 authorization request from client {client_id}",
            extra={"oauth2_context": context}
        )
    
    def log_authorization_granted(
        self,
        client_id: str,
        user_id: str,
        scopes: List[str],
        authorization_code: str,
        expires_in: int,
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log successful OAuth2 authorization.
        
        Args:
            client_id: OAuth2 client identifier
            user_id: User identifier
            scopes: Granted scopes
            authorization_code: Generated authorization code (masked for security)
            expires_in: Code expiration time in seconds
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": OAuth2EventType.AUTHORIZATION_GRANTED.value,
            "client_id": client_id,
            "user_id": user_id,
            "scopes": scopes,
            "authorization_code": self._mask_token(authorization_code),
            "expires_in": expires_in,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        self.logger.info(
            f"OAuth2 authorization granted to client {client_id} for user {user_id}",
            extra={"oauth2_context": context}
        )
    
    def log_token_request(
        self,
        client_id: str,
        grant_type: str,
        scopes: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 token request.
        
        Args:
            client_id: OAuth2 client identifier
            grant_type: OAuth2 grant type
            scopes: Requested scopes (if applicable)
            user_id: User identifier (if applicable)
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": OAuth2EventType.TOKEN_REQUEST.value,
            "client_id": client_id,
            "grant_type": grant_type,
            "scopes": scopes,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        self.logger.info(
            f"OAuth2 token request from client {client_id}, grant_type: {grant_type}",
            extra={"oauth2_context": context}
        )
    
    def log_token_issued(
        self,
        client_id: str,
        user_id: str,
        scopes: List[str],
        access_token_expires_in: int,
        has_refresh_token: bool,
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log successful OAuth2 token issuance.
        
        Args:
            client_id: OAuth2 client identifier
            user_id: User identifier
            scopes: Granted scopes
            access_token_expires_in: Access token expiration time in seconds
            has_refresh_token: Whether refresh token was issued
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": OAuth2EventType.TOKEN_ISSUED.value,
            "client_id": client_id,
            "user_id": user_id,
            "scopes": scopes,
            "access_token_expires_in": access_token_expires_in,
            "has_refresh_token": has_refresh_token,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        self.logger.info(
            f"OAuth2 tokens issued to client {client_id} for user {user_id}",
            extra={"oauth2_context": context}
        )
    
    def log_consent_event(
        self,
        event_type: OAuth2EventType,
        client_id: str,
        user_id: str,
        scopes: List[str],
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 consent events.
        
        Args:
            event_type: Type of consent event
            client_id: OAuth2 client identifier
            user_id: User identifier
            scopes: Scopes involved in consent
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": event_type.value,
            "client_id": client_id,
            "user_id": user_id,
            "scopes": scopes,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        self.logger.info(
            f"OAuth2 consent event: {event_type.value} for client {client_id}, user {user_id}",
            extra={"oauth2_context": context}
        )
    
    def log_security_event(
        self,
        event_type: OAuth2EventType,
        client_id: Optional[str],
        user_id: Optional[str],
        severity: str,
        description: str,
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 security events.
        
        Args:
            event_type: Type of security event
            client_id: OAuth2 client identifier (if applicable)
            user_id: User identifier (if applicable)
            severity: Event severity level
            description: Event description
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": event_type.value,
            "client_id": client_id,
            "user_id": user_id,
            "severity": severity,
            "description": description,
            "timestamp": datetime.utcnow().isoformat(),
            "security_event": True,
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        # Log with appropriate level based on severity
        if severity == "critical":
            self.logger.critical(
                f"OAuth2 security event: {event_type.value} - {description}",
                extra={"oauth2_context": context}
            )
        elif severity == "high":
            self.logger.error(
                f"OAuth2 security event: {event_type.value} - {description}",
                extra={"oauth2_context": context}
            )
        elif severity == "medium":
            self.logger.warning(
                f"OAuth2 security event: {event_type.value} - {description}",
                extra={"oauth2_context": context}
            )
        else:
            self.logger.info(
                f"OAuth2 security event: {event_type.value} - {description}",
                extra={"oauth2_context": context}
            )
    
    def log_error_event(
        self,
        event_type: OAuth2EventType,
        error_code: str,
        error_description: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 error events.
        
        Args:
            event_type: Type of error event
            error_code: OAuth2 error code
            error_description: Error description
            client_id: OAuth2 client identifier (if applicable)
            user_id: User identifier (if applicable)
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": event_type.value,
            "error_code": error_code,
            "error_description": error_description,
            "client_id": client_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        self.logger.error(
            f"OAuth2 error: {error_code} - {error_description}",
            extra={"oauth2_context": context}
        )
    
    def log_client_event(
        self,
        event_type: OAuth2EventType,
        client_id: str,
        client_name: Optional[str] = None,
        owner_user_id: Optional[str] = None,
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 client management events.
        
        Args:
            event_type: Type of client event
            client_id: OAuth2 client identifier
            client_name: Client application name
            owner_user_id: User who owns/registered the client
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": event_type.value,
            "client_id": client_id,
            "client_name": client_name,
            "owner_user_id": owner_user_id,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        self.logger.info(
            f"OAuth2 client event: {event_type.value} for client {client_id}",
            extra={"oauth2_context": context}
        )
    
    def log_client_registered(
        self,
        client_id: str,
        client_name: str,
        owner_user_id: str,
        client_type: str,
        scopes: List[str],
        request: Optional[Request] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log OAuth2 client registration events.
        
        Args:
            client_id: OAuth2 client identifier
            client_name: Client application name
            owner_user_id: User who registered the client
            client_type: Type of client (confidential/public)
            scopes: List of allowed scopes
            request: FastAPI request object
            additional_context: Additional context information
        """
        context = {
            "event_type": OAuth2EventType.CLIENT_REGISTERED.value,
            "client_id": client_id,
            "client_name": client_name,
            "owner_user_id": owner_user_id,
            "client_type": client_type,
            "scopes": scopes,
            "timestamp": datetime.utcnow().isoformat(),
            **(additional_context or {})
        }
        
        self._add_request_context(context, request)
        
        self.logger.info(
            f"OAuth2 client registered: {client_name} ({client_id}) by user {owner_user_id}",
            extra={"oauth2_context": context}
        )
    
    def _add_request_context(
        self,
        context: Dict[str, Any],
        request: Optional[Request]
    ) -> None:
        """
        Add request context to logging context.
        
        Args:
            context: Logging context dictionary to update
            request: FastAPI request object
        """
        if request:
            context.update({
                "request_method": request.method,
                "request_url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "request_id": request.headers.get("x-request-id"),
            })
    
    def _mask_token(self, token: str, visible_chars: int = 8) -> str:
        """
        Mask sensitive token for logging.
        
        Args:
            token: Token to mask
            visible_chars: Number of characters to show at the beginning
            
        Returns:
            Masked token string
        """
        if not token or len(token) <= visible_chars:
            return "***"
        
        return f"{token[:visible_chars]}***"


# Global OAuth2 logger instance
oauth2_logger = OAuth2Logger()


# Convenience functions for common logging scenarios
def log_authorization_flow(
    event_type: OAuth2EventType,
    client_id: str,
    user_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    **kwargs
) -> None:
    """Log authorization flow events."""
    if event_type == OAuth2EventType.AUTHORIZATION_REQUEST:
        oauth2_logger.log_authorization_request(
            client_id=client_id,
            user_id=user_id,
            scopes=scopes or [],
            **kwargs
        )
    elif event_type in [OAuth2EventType.CONSENT_GRANTED, OAuth2EventType.CONSENT_DENIED]:
        oauth2_logger.log_consent_event(
            event_type=event_type,
            client_id=client_id,
            user_id=user_id or "",
            scopes=scopes or [],
            **kwargs
        )


def log_token_flow(
    event_type: OAuth2EventType,
    client_id: str,
    user_id: Optional[str] = None,
    **kwargs
) -> None:
    """Log token flow events."""
    if event_type == OAuth2EventType.TOKEN_REQUEST:
        oauth2_logger.log_token_request(
            client_id=client_id,
            user_id=user_id,
            **kwargs
        )
    elif event_type == OAuth2EventType.TOKEN_ISSUED:
        oauth2_logger.log_token_issued(
            client_id=client_id,
            user_id=user_id or "",
            **kwargs
        )


def log_security_violation(
    violation_type: str,
    description: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    severity: str = "high",
    **kwargs
) -> None:
    """Log security violations."""
    oauth2_logger.log_security_event(
        event_type=OAuth2EventType.SUSPICIOUS_ACTIVITY,
        client_id=client_id,
        user_id=user_id,
        severity=severity,
        description=f"{violation_type}: {description}",
        additional_context={"violation_type": violation_type},
        **kwargs
    )


def log_oauth2_error(
    error_code: str,
    error_description: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    endpoint: str = "unknown",
    **kwargs
) -> None:
    """Log OAuth2 errors."""
    event_type = (
        OAuth2EventType.AUTHORIZATION_ERROR
        if endpoint == "authorize"
        else OAuth2EventType.TOKEN_ERROR
    )
    
    oauth2_logger.log_error_event(
        event_type=event_type,
        error_code=error_code,
        error_description=error_description,
        client_id=client_id,
        user_id=user_id,
        additional_context={"endpoint": endpoint},
        **kwargs
    )