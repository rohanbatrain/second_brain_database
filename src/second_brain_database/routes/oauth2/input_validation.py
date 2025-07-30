"""
Comprehensive input validation and sanitization for OAuth2 browser inputs.

This module provides enterprise-grade input validation and sanitization for all
browser-based OAuth2 authentication flows, protecting against various injection
attacks and ensuring data integrity.

Features:
- Comprehensive input validation for all OAuth2 parameters
- Advanced sanitization to prevent XSS and injection attacks
- URL validation and normalization
- Client ID and secret validation
- State parameter validation and entropy checking
- PKCE parameter validation
- Scope validation and normalization
- Redirect URI validation with security checks
- Rate limiting for validation attempts
- Comprehensive logging and monitoring
"""

import html
import re
import secrets
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from fastapi import HTTPException, Request, status
from pydantic import BaseModel, Field, validator

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager

logger = get_logger(prefix="[OAuth2 Input Validation]")

# Validation configuration constants
MAX_CLIENT_ID_LENGTH = 255
MAX_CLIENT_SECRET_LENGTH = 512
MAX_REDIRECT_URI_LENGTH = 2048
MAX_SCOPE_LENGTH = 1024
MAX_STATE_LENGTH = 512
MAX_CODE_CHALLENGE_LENGTH = 128
MAX_AUTHORIZATION_CODE_LENGTH = 512
MAX_ACCESS_TOKEN_LENGTH = 2048
MAX_REFRESH_TOKEN_LENGTH = 2048

# Minimum entropy requirements
MIN_STATE_ENTROPY_BITS = 128
MIN_CODE_CHALLENGE_ENTROPY_BITS = 256
MIN_CLIENT_SECRET_ENTROPY_BITS = 256

# Allowed characters patterns
CLIENT_ID_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')
STATE_PATTERN = re.compile(r'^[a-zA-Z0-9._~-]+$')
CODE_CHALLENGE_PATTERN = re.compile(r'^[a-zA-Z0-9._~-]+$')
AUTHORIZATION_CODE_PATTERN = re.compile(r'^[a-zA-Z0-9._~-]+$')

# OAuth2 parameter validation
VALID_RESPONSE_TYPES = {"code", "token", "id_token"}
VALID_GRANT_TYPES = {"authorization_code", "refresh_token", "client_credentials"}
VALID_CODE_CHALLENGE_METHODS = {"S256", "plain"}
VALID_TOKEN_TYPES = {"Bearer"}

# Rate limiting for validation
VALIDATION_RATE_LIMIT = 1000  # 1000 validations per period
VALIDATION_RATE_PERIOD = 300  # 5 minutes


class ValidationError(Exception):
    """Custom exception for validation errors."""
    
    def __init__(self, message: str, field: str, value: Any = None, severity: str = "medium"):
        self.message = message
        self.field = field
        self.value = value
        self.severity = severity
        super().__init__(message)


class OAuth2InputValidator:
    """
    Comprehensive input validator for OAuth2 browser flows.
    
    Provides enterprise-grade validation and sanitization for all OAuth2
    parameters and inputs to prevent security vulnerabilities.
    """
    
    def __init__(self):
        """Initialize the input validator."""
        self.logger = logger
        
        # Validation statistics
        self.stats = {
            "validations_performed": 0,
            "validation_failures": 0,
            "sanitizations_applied": 0,
            "security_violations_detected": 0,
            "rate_limit_violations": 0
        }
        
        # Allowed redirect URI schemes
        self.allowed_redirect_schemes = {"https", "http"}
        if settings.DEBUG:
            self.allowed_redirect_schemes.add("http")
        
        # Blocked redirect URI patterns (security)
        self.blocked_redirect_patterns = [
            r'javascript:',
            r'data:',
            r'vbscript:',
            r'file:',
            r'ftp:',
            r'about:',
            r'chrome:',
            r'chrome-extension:',
            r'moz-extension:',
            r'ms-browser-extension:'
        ]
    
    async def validate_authorization_request(
        self,
        request: Request,
        client_id: str,
        response_type: str,
        redirect_uri: str,
        scope: Optional[str] = None,
        state: Optional[str] = None,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate OAuth2 authorization request parameters.
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            response_type: OAuth2 response type
            redirect_uri: Redirect URI
            scope: Optional scope parameter
            state: Optional state parameter
            code_challenge: Optional PKCE code challenge
            code_challenge_method: Optional PKCE code challenge method
            
        Returns:
            Dict with validated and sanitized parameters
            
        Raises:
            ValidationError: If validation fails
            HTTPException: If rate limit exceeded
        """
        start_time = time.time()
        
        try:
            # Apply rate limiting
            await security_manager.check_rate_limit(
                request,
                "oauth2-validation",
                rate_limit_requests=VALIDATION_RATE_LIMIT,
                rate_limit_period=VALIDATION_RATE_PERIOD
            )
            
            validated_params = {}
            
            # Validate client_id
            validated_params["client_id"] = await self._validate_client_id(client_id)
            
            # Validate response_type
            validated_params["response_type"] = self._validate_response_type(response_type)
            
            # Validate redirect_uri
            validated_params["redirect_uri"] = await self._validate_redirect_uri(
                redirect_uri, client_id
            )
            
            # Validate optional parameters
            if scope:
                validated_params["scope"] = self._validate_scope(scope)
            
            if state:
                validated_params["state"] = self._validate_state(state)
            
            if code_challenge:
                validated_params["code_challenge"] = self._validate_code_challenge(
                    code_challenge, code_challenge_method
                )
                validated_params["code_challenge_method"] = code_challenge_method or "S256"
            
            # Update statistics
            self.stats["validations_performed"] += 1
            
            # Log successful validation
            self.logger.info(
                "Authorization request validation successful",
                extra={
                    "client_id": client_id,
                    "response_type": response_type,
                    "has_state": bool(state),
                    "has_pkce": bool(code_challenge),
                    "validation_duration_ms": (time.time() - start_time) * 1000,
                    "event_type": "oauth2_authorization_validation_success"
                }
            )
            
            return validated_params
            
        except ValidationError as e:
            self.stats["validation_failures"] += 1
            self._log_validation_error(e, "authorization_request", start_time)
            raise
        except HTTPException:
            self.stats["rate_limit_violations"] += 1
            raise
        except Exception as e:
            self.stats["validation_failures"] += 1
            self.logger.error(
                "Unexpected error in authorization request validation: %s",
                e,
                exc_info=True,
                extra={
                    "client_id": client_id,
                    "validation_duration_ms": (time.time() - start_time) * 1000
                }
            )
            raise ValidationError("Internal validation error", "general")
    
    async def validate_token_request(
        self,
        request: Request,
        grant_type: str,
        client_id: str,
        client_secret: Optional[str] = None,
        code: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        code_verifier: Optional[str] = None,
        refresh_token: Optional[str] = None,
        scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate OAuth2 token request parameters.
        
        Args:
            request: FastAPI request object
            grant_type: OAuth2 grant type
            client_id: OAuth2 client identifier
            client_secret: Optional client secret
            code: Optional authorization code
            redirect_uri: Optional redirect URI
            code_verifier: Optional PKCE code verifier
            refresh_token: Optional refresh token
            scope: Optional scope parameter
            
        Returns:
            Dict with validated and sanitized parameters
            
        Raises:
            ValidationError: If validation fails
        """
        start_time = time.time()
        
        try:
            # Apply rate limiting
            await security_manager.check_rate_limit(
                request,
                "oauth2-token-validation",
                rate_limit_requests=VALIDATION_RATE_LIMIT,
                rate_limit_period=VALIDATION_RATE_PERIOD
            )
            
            validated_params = {}
            
            # Validate grant_type
            validated_params["grant_type"] = self._validate_grant_type(grant_type)
            
            # Validate client_id
            validated_params["client_id"] = await self._validate_client_id(client_id)
            
            # Validate client_secret if provided
            if client_secret:
                validated_params["client_secret"] = self._validate_client_secret(client_secret)
            
            # Validate parameters based on grant type
            if grant_type == "authorization_code":
                if not code:
                    raise ValidationError("Authorization code is required", "code")
                validated_params["code"] = self._validate_authorization_code(code)
                
                if redirect_uri:
                    validated_params["redirect_uri"] = await self._validate_redirect_uri(
                        redirect_uri, client_id
                    )
                
                if code_verifier:
                    validated_params["code_verifier"] = self._validate_code_verifier(code_verifier)
            
            elif grant_type == "refresh_token":
                if not refresh_token:
                    raise ValidationError("Refresh token is required", "refresh_token")
                validated_params["refresh_token"] = self._validate_refresh_token(refresh_token)
            
            # Validate scope if provided
            if scope:
                validated_params["scope"] = self._validate_scope(scope)
            
            # Update statistics
            self.stats["validations_performed"] += 1
            
            # Log successful validation
            self.logger.info(
                "Token request validation successful",
                extra={
                    "client_id": client_id,
                    "grant_type": grant_type,
                    "has_client_secret": bool(client_secret),
                    "has_code_verifier": bool(code_verifier),
                    "validation_duration_ms": (time.time() - start_time) * 1000,
                    "event_type": "oauth2_token_validation_success"
                }
            )
            
            return validated_params
            
        except ValidationError as e:
            self.stats["validation_failures"] += 1
            self._log_validation_error(e, "token_request", start_time)
            raise
        except HTTPException:
            self.stats["rate_limit_violations"] += 1
            raise
        except Exception as e:
            self.stats["validation_failures"] += 1
            self.logger.error(
                "Unexpected error in token request validation: %s",
                e,
                exc_info=True,
                extra={
                    "client_id": client_id,
                    "grant_type": grant_type,
                    "validation_duration_ms": (time.time() - start_time) * 1000
                }
            )
            raise ValidationError("Internal validation error", "general")
    
    def sanitize_html_input(self, input_value: str) -> str:
        """
        Sanitize HTML input to prevent XSS attacks.
        
        Args:
            input_value: Input string to sanitize
            
        Returns:
            Sanitized string
        """
        if not input_value:
            return ""
        
        # HTML escape
        sanitized = html.escape(input_value, quote=True)
        
        # Remove potentially dangerous patterns
        dangerous_patterns = [
            r'javascript:',
            r'vbscript:',
            r'data:',
            r'<script',
            r'</script>',
            r'<iframe',
            r'</iframe>',
            r'<object',
            r'</object>',
            r'<embed',
            r'</embed>',
            r'<link',
            r'<meta',
            r'onload=',
            r'onerror=',
            r'onclick=',
            r'onmouseover='
        ]
        
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Update statistics
        if sanitized != input_value:
            self.stats["sanitizations_applied"] += 1
        
        return sanitized
    
    def sanitize_url_input(self, url: str) -> str:
        """
        Sanitize URL input to prevent various URL-based attacks.
        
        Args:
            url: URL string to sanitize
            
        Returns:
            Sanitized URL string
        """
        if not url:
            return ""
        
        try:
            # Parse URL
            parsed = urlparse(url)
            
            # Validate scheme
            if parsed.scheme.lower() not in self.allowed_redirect_schemes:
                raise ValidationError(f"Invalid URL scheme: {parsed.scheme}", "url")
            
            # Check for blocked patterns
            for pattern in self.blocked_redirect_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    raise ValidationError(f"Blocked URL pattern detected", "url")
            
            # Normalize URL
            normalized_url = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path,
                parsed.params,
                parsed.query,
                parsed.fragment
            ))
            
            return normalized_url
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Invalid URL format: {str(e)}", "url")
    
    # Private validation methods
    
    async def _validate_client_id(self, client_id: str) -> str:
        """Validate OAuth2 client ID."""
        if not client_id:
            raise ValidationError("Client ID is required", "client_id")
        
        if len(client_id) > MAX_CLIENT_ID_LENGTH:
            raise ValidationError(
                f"Client ID too long (max {MAX_CLIENT_ID_LENGTH} characters)",
                "client_id"
            )
        
        if not CLIENT_ID_PATTERN.match(client_id):
            raise ValidationError("Client ID contains invalid characters", "client_id")
        
        # Additional security check - ensure client exists
        # This would typically check against a database
        # For now, we'll just validate the format
        
        return client_id
    
    def _validate_response_type(self, response_type: str) -> str:
        """Validate OAuth2 response type."""
        if not response_type:
            raise ValidationError("Response type is required", "response_type")
        
        if response_type not in VALID_RESPONSE_TYPES:
            raise ValidationError(
                f"Invalid response type: {response_type}",
                "response_type"
            )
        
        return response_type
    
    async def _validate_redirect_uri(self, redirect_uri: str, client_id: str) -> str:
        """Validate OAuth2 redirect URI."""
        if not redirect_uri:
            raise ValidationError("Redirect URI is required", "redirect_uri")
        
        if len(redirect_uri) > MAX_REDIRECT_URI_LENGTH:
            raise ValidationError(
                f"Redirect URI too long (max {MAX_REDIRECT_URI_LENGTH} characters)",
                "redirect_uri"
            )
        
        # Sanitize and validate URL
        sanitized_uri = self.sanitize_url_input(redirect_uri)
        
        # Parse URI for additional validation
        try:
            parsed = urlparse(sanitized_uri)
            
            # Ensure absolute URI
            if not parsed.scheme or not parsed.netloc:
                raise ValidationError("Redirect URI must be absolute", "redirect_uri")
            
            # Security checks
            if parsed.scheme.lower() not in self.allowed_redirect_schemes:
                raise ValidationError(
                    f"Invalid redirect URI scheme: {parsed.scheme}",
                    "redirect_uri"
                )
            
            # Check for localhost in production
            if not settings.DEBUG and parsed.netloc.lower() in ["localhost", "127.0.0.1"]:
                raise ValidationError(
                    "Localhost redirect URIs not allowed in production",
                    "redirect_uri"
                )
            
            # Validate against registered redirect URIs for client
            # This would typically check against a database
            # For now, we'll perform basic validation
            
            return sanitized_uri
            
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Invalid redirect URI format: {str(e)}", "redirect_uri")
    
    def _validate_scope(self, scope: str) -> str:
        """Validate OAuth2 scope parameter."""
        if len(scope) > MAX_SCOPE_LENGTH:
            raise ValidationError(
                f"Scope too long (max {MAX_SCOPE_LENGTH} characters)",
                "scope"
            )
        
        # Sanitize scope
        sanitized_scope = self.sanitize_html_input(scope)
        
        # Validate scope format (space-separated values)
        scope_values = sanitized_scope.split()
        
        # Validate individual scope values
        valid_scope_pattern = re.compile(r'^[a-zA-Z0-9._:-]+$')
        for scope_value in scope_values:
            if not valid_scope_pattern.match(scope_value):
                raise ValidationError(
                    f"Invalid scope value: {scope_value}",
                    "scope"
                )
        
        # Remove duplicates and sort for consistency
        unique_scopes = sorted(set(scope_values))
        
        return " ".join(unique_scopes)
    
    def _validate_state(self, state: str) -> str:
        """Validate OAuth2 state parameter."""
        if len(state) > MAX_STATE_LENGTH:
            raise ValidationError(
                f"State parameter too long (max {MAX_STATE_LENGTH} characters)",
                "state"
            )
        
        if not STATE_PATTERN.match(state):
            raise ValidationError("State parameter contains invalid characters", "state")
        
        # Check entropy (security requirement)
        entropy_bits = self._calculate_entropy(state)
        if entropy_bits < MIN_STATE_ENTROPY_BITS:
            self.logger.warning(
                "State parameter has low entropy: %d bits (recommended: %d+)",
                entropy_bits,
                MIN_STATE_ENTROPY_BITS,
                extra={"state_length": len(state), "entropy_bits": entropy_bits}
            )
        
        return state
    
    def _validate_code_challenge(
        self,
        code_challenge: str,
        code_challenge_method: Optional[str] = None
    ) -> str:
        """Validate PKCE code challenge."""
        if len(code_challenge) > MAX_CODE_CHALLENGE_LENGTH:
            raise ValidationError(
                f"Code challenge too long (max {MAX_CODE_CHALLENGE_LENGTH} characters)",
                "code_challenge"
            )
        
        if not CODE_CHALLENGE_PATTERN.match(code_challenge):
            raise ValidationError(
                "Code challenge contains invalid characters",
                "code_challenge"
            )
        
        # Validate code challenge method
        method = code_challenge_method or "S256"
        if method not in VALID_CODE_CHALLENGE_METHODS:
            raise ValidationError(
                f"Invalid code challenge method: {method}",
                "code_challenge_method"
            )
        
        # For S256, validate base64url format and length
        if method == "S256":
            if len(code_challenge) < 43 or len(code_challenge) > 128:
                raise ValidationError(
                    "S256 code challenge must be 43-128 characters",
                    "code_challenge"
                )
        
        # Check entropy
        entropy_bits = self._calculate_entropy(code_challenge)
        if entropy_bits < MIN_CODE_CHALLENGE_ENTROPY_BITS:
            raise ValidationError(
                f"Code challenge has insufficient entropy: {entropy_bits} bits",
                "code_challenge",
                severity="high"
            )
        
        return code_challenge
    
    def _validate_grant_type(self, grant_type: str) -> str:
        """Validate OAuth2 grant type."""
        if not grant_type:
            raise ValidationError("Grant type is required", "grant_type")
        
        if grant_type not in VALID_GRANT_TYPES:
            raise ValidationError(f"Invalid grant type: {grant_type}", "grant_type")
        
        return grant_type
    
    def _validate_client_secret(self, client_secret: str) -> str:
        """Validate OAuth2 client secret."""
        if len(client_secret) > MAX_CLIENT_SECRET_LENGTH:
            raise ValidationError(
                f"Client secret too long (max {MAX_CLIENT_SECRET_LENGTH} characters)",
                "client_secret"
            )
        
        # Check entropy for security
        entropy_bits = self._calculate_entropy(client_secret)
        if entropy_bits < MIN_CLIENT_SECRET_ENTROPY_BITS:
            self.logger.warning(
                "Client secret has low entropy: %d bits (recommended: %d+)",
                entropy_bits,
                MIN_CLIENT_SECRET_ENTROPY_BITS,
                extra={"secret_length": len(client_secret), "entropy_bits": entropy_bits}
            )
        
        return client_secret
    
    def _validate_authorization_code(self, code: str) -> str:
        """Validate OAuth2 authorization code."""
        if not code:
            raise ValidationError("Authorization code is required", "code")
        
        if len(code) > MAX_AUTHORIZATION_CODE_LENGTH:
            raise ValidationError(
                f"Authorization code too long (max {MAX_AUTHORIZATION_CODE_LENGTH} characters)",
                "code"
            )
        
        if not AUTHORIZATION_CODE_PATTERN.match(code):
            raise ValidationError(
                "Authorization code contains invalid characters",
                "code"
            )
        
        return code
    
    def _validate_code_verifier(self, code_verifier: str) -> str:
        """Validate PKCE code verifier."""
        if len(code_verifier) < 43 or len(code_verifier) > 128:
            raise ValidationError(
                "Code verifier must be 43-128 characters",
                "code_verifier"
            )
        
        # Validate base64url format
        if not re.match(r'^[a-zA-Z0-9._~-]+$', code_verifier):
            raise ValidationError(
                "Code verifier contains invalid characters",
                "code_verifier"
            )
        
        return code_verifier
    
    def _validate_refresh_token(self, refresh_token: str) -> str:
        """Validate OAuth2 refresh token."""
        if not refresh_token:
            raise ValidationError("Refresh token is required", "refresh_token")
        
        if len(refresh_token) > MAX_REFRESH_TOKEN_LENGTH:
            raise ValidationError(
                f"Refresh token too long (max {MAX_REFRESH_TOKEN_LENGTH} characters)",
                "refresh_token"
            )
        
        return refresh_token
    
    def _calculate_entropy(self, value: str) -> float:
        """Calculate Shannon entropy of a string in bits."""
        if not value:
            return 0.0
        
        # Count character frequencies
        char_counts = {}
        for char in value:
            char_counts[char] = char_counts.get(char, 0) + 1
        
        # Calculate entropy
        entropy = 0.0
        length = len(value)
        
        for count in char_counts.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)
        
        return entropy * length
    
    def _log_validation_error(
        self,
        error: ValidationError,
        validation_type: str,
        start_time: float
    ) -> None:
        """Log validation error with context."""
        self.logger.warning(
            "OAuth2 input validation failed: %s",
            error.message,
            extra={
                "validation_type": validation_type,
                "field": error.field,
                "error_message": error.message,
                "severity": error.severity,
                "validation_duration_ms": (time.time() - start_time) * 1000,
                "event_type": "oauth2_validation_error"
            }
        )
        
        # Track security violations
        if error.severity in ["high", "critical"]:
            self.stats["security_violations_detected"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get input validation statistics."""
        return {
            **self.stats,
            "validation_success_rate": (
                (self.stats["validations_performed"] - self.stats["validation_failures"]) /
                max(1, self.stats["validations_performed"])
            ),
            "security_violation_rate": (
                self.stats["security_violations_detected"] /
                max(1, self.stats["validations_performed"])
            )
        }


# Global input validator instance
input_validator = OAuth2InputValidator()