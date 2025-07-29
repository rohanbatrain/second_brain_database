"""
OAuth2 security manager and validation layer.

This module provides OAuth2-specific security operations including:
- Redirect URI validation against registered client URIs
- State parameter generation and validation for CSRF protection
- Integration with existing security_manager for rate limiting
- OAuth2-specific security validations and protections
- Security headers and input sanitization
- Token encryption and secure storage
- Abuse prevention and monitoring

The OAuth2SecurityManager integrates with the existing security infrastructure
while providing OAuth2-specific security features and validations.
"""

import hashlib
import html
import re
import secrets
import string
import time
from typing import Dict, List, Optional, Pattern
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response, status
from cryptography.fernet import Fernet

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager
# Crypto utilities will be handled by Fernet directly

from .client_manager import client_manager

logger = get_logger(prefix="[OAuth2 SecurityManager]")


class OAuth2SecurityHardening:
    """
    OAuth2 security hardening utilities and constants.
    
    Contains security patterns, validation rules, and hardening configurations
    for OAuth2 implementation security.
    """
    
    # Input validation patterns
    CLIENT_ID_PATTERN: Pattern[str] = re.compile(r'^[a-zA-Z0-9_-]{8,64}$')
    STATE_PATTERN: Pattern[str] = re.compile(r'^[a-zA-Z0-9_.-]{8,128}$')
    CODE_PATTERN: Pattern[str] = re.compile(r'^[a-zA-Z0-9_-]{32,128}$')
    SCOPE_PATTERN: Pattern[str] = re.compile(r'^[a-zA-Z0-9_:.-]+$')
    
    # Dangerous patterns to detect in input
    XSS_PATTERNS: List[Pattern[str]] = [
        re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
        re.compile(r'javascript:', re.IGNORECASE),
        re.compile(r'data:', re.IGNORECASE),
        re.compile(r'vbscript:', re.IGNORECASE),
        re.compile(r'on\w+\s*=', re.IGNORECASE),
        re.compile(r'<iframe[^>]*>', re.IGNORECASE),
        re.compile(r'<object[^>]*>', re.IGNORECASE),
        re.compile(r'<embed[^>]*>', re.IGNORECASE),
    ]
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS: List[Pattern[str]] = [
        re.compile(r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)', re.IGNORECASE),
        re.compile(r'(\b(OR|AND)\s+\d+\s*=\s*\d+)', re.IGNORECASE),
        re.compile(r'[\'";]', re.IGNORECASE),
    ]
    
    # Security headers for OAuth2 endpoints
    SECURITY_HEADERS: Dict[str, str] = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "object-src 'none'; "
            "media-src 'none'; "
            "frame-src 'none'; "
            "base-uri 'self'"
        ),
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Cache-Control": "no-store, no-cache, must-revalidate, private",
        "Pragma": "no-cache",
        "Expires": "0"
    }
    
    # Rate limiting thresholds for abuse detection
    ABUSE_DETECTION_THRESHOLDS = {
        "failed_auth_attempts": 10,  # Failed authentication attempts per hour
        "invalid_client_requests": 20,  # Invalid client requests per hour
        "malformed_requests": 50,  # Malformed requests per hour
        "suspicious_redirects": 5,  # Suspicious redirect attempts per hour
    }
    
    @staticmethod
    def sanitize_input(value: str, max_length: int = 1000) -> str:
        """
        Sanitize input string to prevent XSS and injection attacks.
        
        Args:
            value: Input string to sanitize
            max_length: Maximum allowed length
            
        Returns:
            Sanitized string
        """
        if not value or not isinstance(value, str):
            return ""
        
        # Truncate to max length
        value = value[:max_length]
        
        # HTML escape
        value = html.escape(value, quote=True)
        
        # Remove null bytes and control characters
        value = ''.join(char for char in value if ord(char) >= 32 or char in '\t\n\r')
        
        return value.strip()
    
    @staticmethod
    def detect_malicious_patterns(value: str) -> List[str]:
        """
        Detect malicious patterns in input.
        
        Args:
            value: Input string to check
            
        Returns:
            List of detected pattern types
        """
        detected_patterns = []
        
        # Check for XSS patterns
        for pattern in OAuth2SecurityHardening.XSS_PATTERNS:
            if pattern.search(value):
                detected_patterns.append("xss")
                break
        
        # Check for SQL injection patterns
        for pattern in OAuth2SecurityHardening.SQL_INJECTION_PATTERNS:
            if pattern.search(value):
                detected_patterns.append("sql_injection")
                break
        
        return detected_patterns


class OAuth2SecurityManager:
    """
    OAuth2-specific security operations and validations.
    
    Provides comprehensive security features for OAuth2 flows including:
    - Redirect URI validation against registered client URIs
    - State parameter generation and validation for CSRF protection
    - Rate limiting integration for OAuth2 endpoints
    - OAuth2-specific security validations
    - Input sanitization and malicious pattern detection
    - Security headers for OAuth2 endpoints
    - Token encryption and secure storage
    - Abuse detection and prevention
    """
    
    def __init__(self):
        """Initialize the OAuth2SecurityManager."""
        self.redis_manager = redis_manager
        self.security_manager = security_manager
        self.client_manager = client_manager
        self.hardening = OAuth2SecurityHardening()
        
        # Initialize encryption for token storage
        try:
            self.fernet = self._get_fernet_instance()
        except Exception as e:
            logger.error(f"Failed to initialize token encryption: {e}")
            raise
        
        logger.info("OAuth2SecurityManager initialized with security hardening")
    
    def _get_fernet_instance(self) -> Fernet:
        """
        Get properly configured Fernet instance using the same logic as crypto utils.
        
        Returns:
            Configured Fernet instance
        """
        import base64
        import hashlib
        
        key_raw = settings.FERNET_KEY.get_secret_value()
        key_material = key_raw.encode("utf-8")
        
        # Try to decode as base64; if it fails, hash and encode
        try:
            decoded = base64.urlsafe_b64decode(key_material)
            if len(decoded) == 32:
                return Fernet(key_material)
        except base64.binascii.Error:
            pass
        
        # If not valid, hash and encode
        hashed_key = hashlib.sha256(key_material).digest()
        encoded_key = base64.urlsafe_b64encode(hashed_key)
        return Fernet(encoded_key)
    
    async def validate_redirect_uri(
        self,
        client_id: str,
        redirect_uri: str
    ) -> bool:
        """
        Validate redirect URI against registered client URIs.
        
        Performs comprehensive validation including:
        - Exact match against registered URIs
        - Security checks for malicious URIs
        - Protocol validation (HTTPS required except localhost)
        
        Args:
            client_id: OAuth2 client identifier
            redirect_uri: Redirect URI to validate
            
        Returns:
            bool: True if redirect URI is valid and secure
        """
        logger.debug(f"Validating redirect URI for client {client_id}: {redirect_uri}")
        
        # Basic URI format validation
        if not self._is_valid_uri_format(redirect_uri):
            logger.warning(f"Invalid URI format: {redirect_uri}")
            return False
        
        # Security validation
        if not self._is_secure_redirect_uri(redirect_uri):
            logger.warning(f"Insecure redirect URI: {redirect_uri}")
            return False
        
        # Validate against registered client URIs
        is_registered = await self.client_manager.validate_redirect_uri(client_id, redirect_uri)
        if not is_registered:
            logger.warning(f"Redirect URI not registered for client {client_id}: {redirect_uri}")
            return False
        
        logger.debug(f"Redirect URI validation successful for client {client_id}: {redirect_uri}")
        return True
    
    def generate_secure_state(self, length: int = 32) -> str:
        """
        Generate a cryptographically secure state parameter for CSRF protection.
        
        Args:
            length: Length of the state parameter (default: 32)
            
        Returns:
            str: Secure random state parameter
        """
        state = ''.join(secrets.choice(string.ascii_letters + string.digits + '-_') for _ in range(length))
        logger.debug("Generated secure state parameter")
        return state
    
    async def store_state(
        self,
        state: str,
        client_id: str,
        user_id: str,
        expiration_seconds: int = 600  # 10 minutes
    ) -> bool:
        """
        Store state parameter in Redis for validation.
        
        Args:
            state: State parameter to store
            client_id: OAuth2 client identifier
            user_id: User identifier
            expiration_seconds: State expiration time in seconds
            
        Returns:
            bool: True if stored successfully
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            state_key = f"oauth2:state:{state}"
            state_data = {
                "client_id": client_id,
                "user_id": user_id,
                "created_at": str(int(secrets.randbits(32)))  # Simple timestamp
            }
            
            # Store state with expiration
            await redis_conn.hset(state_key, mapping=state_data)
            await redis_conn.expire(state_key, expiration_seconds)
            
            logger.debug(f"Stored state parameter for client {client_id}, user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store state parameter: {e}", exc_info=True)
            return False
    
    async def validate_state(
        self,
        state: str,
        expected_client_id: str,
        expected_user_id: str
    ) -> bool:
        """
        Validate state parameter against stored value for CSRF protection.
        
        Args:
            state: State parameter to validate
            expected_client_id: Expected OAuth2 client identifier
            expected_user_id: Expected user identifier
            
        Returns:
            bool: True if state is valid and matches expected values
        """
        logger.debug(f"Validating state parameter for client {expected_client_id}, user {expected_user_id}")
        
        try:
            redis_conn = await self.redis_manager.get_redis()
            state_key = f"oauth2:state:{state}"
            
            # Get stored state data
            state_data = await redis_conn.hgetall(state_key)
            if not state_data:
                logger.warning("State parameter not found or expired")
                return False
            
            # Validate client_id and user_id
            stored_client_id = state_data.get("client_id")
            stored_user_id = state_data.get("user_id")
            
            if stored_client_id != expected_client_id:
                logger.warning(f"State validation failed: client_id mismatch. Expected: {expected_client_id}, Got: {stored_client_id}")
                return False
            
            if stored_user_id != expected_user_id:
                logger.warning(f"State validation failed: user_id mismatch. Expected: {expected_user_id}, Got: {stored_user_id}")
                return False
            
            # Delete state after successful validation (one-time use)
            await redis_conn.delete(state_key)
            
            logger.debug("State parameter validation successful")
            return True
            
        except Exception as e:
            logger.error(f"Error validating state parameter: {e}", exc_info=True)
            return False
    
    async def rate_limit_client(
        self,
        request: Request,
        client_id: str,
        endpoint: str,
        rate_limit_requests: Optional[int] = None,
        rate_limit_period: Optional[int] = None
    ) -> None:
        """
        Apply rate limiting to OAuth2 client requests.
        
        Integrates with existing security_manager to provide rate limiting
        for OAuth2 endpoints with client-specific tracking.
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            endpoint: OAuth2 endpoint name (e.g., 'authorize', 'token')
            rate_limit_requests: Custom request limit (optional)
            rate_limit_period: Custom period in seconds (optional)
            
        Raises:
            HTTPException: If rate limit is exceeded with 429 status code
        """
        # Import here to avoid circular imports
        from second_brain_database.config import settings
        
        # Only skip rate limiting if explicitly disabled via environment variable
        # This allows tests to still verify rate limiting functionality
        import os
        if os.environ.get('DISABLE_OAUTH2_RATE_LIMITING') == 'true':
            logger.debug(f"OAuth2 rate limiting disabled via environment variable for client {client_id}")
            return
        
        # Create client-specific action for rate limiting
        action = f"oauth2_{endpoint}_{client_id}"
        
        logger.debug(f"Applying rate limit for client {client_id} on endpoint {endpoint}")
        
        try:
            # Use existing security manager for rate limiting
            await self.security_manager.check_rate_limit(
                request=request,
                action=action,
                rate_limit_requests=rate_limit_requests,
                rate_limit_period=rate_limit_period
            )
            
        except HTTPException as e:
            # Ensure rate limiting always returns 429 status code
            if e.status_code != 429:
                logger.warning(f"Rate limiting returned non-429 status code: {e.status_code}, correcting to 429")
                e.status_code = 429
                
            # Log OAuth2-specific rate limit events
            logger.warning(f"Rate limit exceeded for OAuth2 client {client_id} on endpoint {endpoint}")
            raise e
    
    async def validate_client_request_security(
        self,
        request: Request,
        client_id: str,
        redirect_uri: Optional[str] = None,
        state: Optional[str] = None
    ) -> None:
        """
        Comprehensive security validation for OAuth2 client requests.
        
        Performs multiple security checks including:
        - Client existence and status validation
        - Redirect URI validation (if provided)
        - Request origin validation
        - Security headers validation
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            redirect_uri: Redirect URI to validate (optional)
            state: State parameter (optional)
            
        Raises:
            HTTPException: If any security validation fails
        """
        logger.debug(f"Performing security validation for OAuth2 client: {client_id}")
        
        # Validate client exists and is active
        client = await self.client_manager.get_client(client_id)
        if not client:
            logger.warning(f"OAuth2 request with invalid client_id: {client_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid client_id"
            )
        
        if not client.is_active:
            logger.warning(f"OAuth2 request with inactive client: {client_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client is inactive"
            )
        
        # Validate redirect URI if provided
        if redirect_uri:
            if not await self.validate_redirect_uri(client_id, redirect_uri):
                logger.warning(f"Invalid redirect URI for client {client_id}: {redirect_uri}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid redirect_uri"
                )
        
        # Validate state parameter format if provided
        if state and not self._is_valid_state_format(state):
            logger.warning(f"Invalid state parameter format for client {client_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter format"
            )
        
        logger.debug(f"Security validation successful for OAuth2 client: {client_id}")
    
    def _is_valid_uri_format(self, uri: str) -> bool:
        """
        Validate URI format.
        
        Args:
            uri: URI to validate
            
        Returns:
            bool: True if URI format is valid
        """
        try:
            parsed = urlparse(uri)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    def _is_secure_redirect_uri(self, redirect_uri: str) -> bool:
        """
        Validate redirect URI security requirements.
        
        Args:
            redirect_uri: Redirect URI to validate
            
        Returns:
            bool: True if redirect URI meets security requirements
        """
        try:
            parsed = urlparse(redirect_uri)
            
            # Check for dangerous schemes
            if parsed.scheme.lower() in ['javascript', 'data', 'vbscript']:
                return False
            
            # Require HTTPS except for localhost/127.0.0.1
            if parsed.scheme.lower() != 'https':
                if parsed.hostname not in ['localhost', '127.0.0.1', '::1']:
                    return False
            
            # Check for suspicious patterns
            if any(pattern in redirect_uri.lower() for pattern in ['<script', 'javascript:', 'data:']):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _is_valid_state_format(self, state: str) -> bool:
        """
        Validate state parameter format.
        
        Args:
            state: State parameter to validate
            
        Returns:
            bool: True if state format is valid
        """
        # State should be reasonable length and contain safe characters
        if not state or len(state) < 8 or len(state) > 128:
            return False
        
        # Allow alphanumeric, hyphens, underscores, and dots
        allowed_chars = set(string.ascii_letters + string.digits + '-_.')
        return all(c in allowed_chars for c in state)
    
    async def log_oauth2_security_event(
        self,
        event_type: str,
        client_id: str,
        user_id: Optional[str] = None,
        details: Optional[dict] = None
    ) -> None:
        """
        Log OAuth2 security events for audit and monitoring.
        
        Args:
            event_type: Type of security event
            client_id: OAuth2 client identifier
            user_id: User identifier (optional)
            details: Additional event details (optional)
        """
        log_data = {
            "event_type": event_type,
            "client_id": client_id,
            "user_id": user_id,
            "details": details or {}
        }
        
        logger.info(f"OAuth2 security event: {event_type}", extra=log_data)
    
    async def validate_pkce_security(
        self,
        code_challenge: str,
        code_challenge_method: str
    ) -> bool:
        """
        Validate PKCE parameters for security compliance.
        
        Args:
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE challenge method
            
        Returns:
            bool: True if PKCE parameters are secure
        """
        # Validate challenge method
        if code_challenge_method not in ['S256', 'plain']:
            logger.warning(f"Invalid PKCE challenge method: {code_challenge_method}")
            return False
        
        # Validate challenge format
        if not code_challenge or len(code_challenge) < 43 or len(code_challenge) > 128:
            logger.warning("Invalid PKCE code challenge length")
            return False
        
        # For S256, validate base64url format
        if code_challenge_method == 'S256':
            allowed_chars = set(string.ascii_letters + string.digits + '-_')
            if not all(c in allowed_chars for c in code_challenge):
                logger.warning("Invalid PKCE code challenge format for S256")
                return False
        
        return True
    
    async def store_authorization_state(
        self,
        state_key: str,
        auth_params: dict,
        expiration_seconds: int = 600  # 10 minutes
    ) -> bool:
        """
        Store authorization request parameters for consent flow.
        
        Args:
            state_key: State key for storing parameters
            auth_params: Authorization parameters to store
            expiration_seconds: Expiration time in seconds
            
        Returns:
            bool: True if stored successfully
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            auth_key = f"oauth2:auth_state:{state_key}"
            
            # Store authorization parameters with expiration
            await redis_conn.hset(auth_key, mapping={
                k: str(v) if not isinstance(v, list) else ','.join(v)
                for k, v in auth_params.items()
            })
            await redis_conn.expire(auth_key, expiration_seconds)
            
            logger.debug(f"Stored authorization state: {state_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store authorization state: {e}", exc_info=True)
            return False
    
    async def get_authorization_state(self, state_key: str) -> Optional[dict]:
        """
        Retrieve and consume authorization request parameters.
        
        Args:
            state_key: State key for retrieving parameters
            
        Returns:
            dict: Authorization parameters if found, None otherwise
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            auth_key = f"oauth2:auth_state:{state_key}"
            
            # Get stored authorization parameters
            auth_data = await redis_conn.hgetall(auth_key)
            if not auth_data:
                logger.warning(f"Authorization state not found: {state_key}")
                return None
            
            # Delete state after retrieval (single use)
            await redis_conn.delete(auth_key)
            
            # Convert back to proper format
            auth_params = {}
            for k, v in auth_data.items():
                if k == 'scopes':
                    auth_params[k] = v.split(',') if v else []
                else:
                    auth_params[k] = v
            
            logger.debug(f"Retrieved authorization state: {state_key}")
            return auth_params
            
        except Exception as e:
            logger.error(f"Failed to get authorization state: {e}", exc_info=True)
            return None
    
    def apply_security_headers(self, response: Response) -> Response:
        """
        Apply OAuth2-specific security headers to response.
        
        Args:
            response: FastAPI response object
            
        Returns:
            Response with security headers applied
        """
        for header_name, header_value in OAuth2SecurityHardening.SECURITY_HEADERS.items():
            response.headers[header_name] = header_value
        
        logger.debug("Applied OAuth2 security headers to response")
        return response
    
    async def validate_and_sanitize_input(
        self,
        input_data: Dict[str, str],
        client_id: Optional[str] = None,
        request: Optional[Request] = None
    ) -> Dict[str, str]:
        """
        Validate and sanitize OAuth2 input parameters.
        
        Args:
            input_data: Dictionary of input parameters to validate
            client_id: OAuth2 client identifier (for logging)
            request: FastAPI request object (for logging)
            
        Returns:
            Dictionary of sanitized input parameters
            
        Raises:
            HTTPException: If input validation fails or malicious patterns detected
        """
        sanitized_data = {}
        validation_errors = []
        
        for key, value in input_data.items():
            if not isinstance(value, str):
                validation_errors.append(f"Parameter {key} must be a string")
                continue
            
            # Check for malicious patterns
            malicious_patterns = OAuth2SecurityHardening.detect_malicious_patterns(value)
            if malicious_patterns:
                await self._log_security_violation(
                    event_type="malicious_input_detected",
                    client_id=client_id,
                    request=request,
                    details={
                        "parameter": key,
                        "patterns": malicious_patterns,
                        "value_length": len(value)
                    }
                )
                validation_errors.append(f"Invalid characters in parameter {key}")
                continue
            
            # Sanitize the input
            sanitized_value = OAuth2SecurityHardening.sanitize_input(value)
            
            # Validate specific parameter formats
            if key == "client_id" and not OAuth2SecurityHardening.CLIENT_ID_PATTERN.match(sanitized_value):
                validation_errors.append("Invalid client_id format")
            elif key == "state" and not OAuth2SecurityHardening.STATE_PATTERN.match(sanitized_value):
                validation_errors.append("Invalid state parameter format")
            elif key == "code" and not OAuth2SecurityHardening.CODE_PATTERN.match(sanitized_value):
                validation_errors.append("Invalid authorization code format")
            elif key == "scope":
                # Validate individual scopes
                scopes = sanitized_value.split()
                for scope in scopes:
                    if not OAuth2SecurityHardening.SCOPE_PATTERN.match(scope):
                        validation_errors.append(f"Invalid scope format: {scope}")
            
            sanitized_data[key] = sanitized_value
        
        if validation_errors:
            await self._log_security_violation(
                event_type="input_validation_failed",
                client_id=client_id,
                request=request,
                details={
                    "validation_errors": validation_errors,
                    "parameter_count": len(input_data)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input validation failed: {'; '.join(validation_errors)}"
            )
        
        logger.debug(f"Successfully validated and sanitized {len(sanitized_data)} parameters")
        return sanitized_data
    
    async def encrypt_token_data(self, token_data: Dict[str, str]) -> str:
        """
        Encrypt token data for secure storage.
        
        Args:
            token_data: Token data to encrypt
            
        Returns:
            Encrypted token data as string
        """
        try:
            # Convert dict to JSON string and encrypt
            import json
            json_data = json.dumps(token_data, sort_keys=True)
            encrypted_data = self.fernet.encrypt(json_data.encode())
            
            logger.debug("Successfully encrypted token data")
            return encrypted_data.decode()
            
        except Exception as e:
            logger.error(f"Failed to encrypt token data: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token encryption failed"
            )
    
    async def decrypt_token_data(self, encrypted_data: str) -> Dict[str, str]:
        """
        Decrypt token data from secure storage.
        
        Args:
            encrypted_data: Encrypted token data string
            
        Returns:
            Decrypted token data dictionary
        """
        try:
            # Decrypt and parse JSON
            import json
            decrypted_bytes = self.fernet.decrypt(encrypted_data.encode())
            token_data = json.loads(decrypted_bytes.decode())
            
            logger.debug("Successfully decrypted token data")
            return token_data
            
        except Exception as e:
            logger.error(f"Failed to decrypt token data: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token decryption failed"
            )
    
    async def detect_abuse_patterns(
        self,
        client_id: str,
        request: Request,
        event_type: str
    ) -> bool:
        """
        Detect abuse patterns and rate limit violations.
        
        Args:
            client_id: OAuth2 client identifier
            request: FastAPI request object
            event_type: Type of event to track
            
        Returns:
            True if abuse detected, False otherwise
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            client_ip = request.client.host if request.client else "unknown"
            
            # Create tracking keys
            hour_key = f"oauth2:abuse:{event_type}:{client_id}:{int(time.time() // 3600)}"
            ip_hour_key = f"oauth2:abuse:{event_type}:ip:{client_ip}:{int(time.time() // 3600)}"
            
            # Increment counters
            current_count = await redis_conn.incr(hour_key)
            ip_count = await redis_conn.incr(ip_hour_key)
            
            # Set expiration (1 hour + buffer)
            await redis_conn.expire(hour_key, 3900)
            await redis_conn.expire(ip_hour_key, 3900)
            
            # Check thresholds
            threshold = OAuth2SecurityHardening.ABUSE_DETECTION_THRESHOLDS.get(event_type, 100)
            
            if current_count > threshold or ip_count > threshold * 2:
                await self._log_security_violation(
                    event_type="abuse_pattern_detected",
                    client_id=client_id,
                    request=request,
                    details={
                        "abuse_type": event_type,
                        "client_count": current_count,
                        "ip_count": ip_count,
                        "threshold": threshold
                    }
                )
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in abuse detection: {e}")
            return False
    
    async def enhanced_rate_limiting(
        self,
        request: Request,
        client_id: str,
        endpoint: str,
        custom_limits: Optional[Dict[str, int]] = None
    ) -> None:
        """
        Enhanced rate limiting with abuse detection.
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            endpoint: OAuth2 endpoint name
            custom_limits: Custom rate limits (optional)
            
        Raises:
            HTTPException: If rate limit exceeded or abuse detected
        """
        # Check for abuse patterns first
        abuse_detected = await self.detect_abuse_patterns(
            client_id=client_id,
            request=request,
            event_type=f"{endpoint}_requests"
        )
        
        if abuse_detected:
            await self._log_security_violation(
                event_type="rate_limit_abuse",
                client_id=client_id,
                request=request,
                details={"endpoint": endpoint}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded due to abuse detection"
            )
        
        # Apply standard rate limiting
        await self.rate_limit_client(
            request=request,
            client_id=client_id,
            endpoint=endpoint,
            rate_limit_requests=custom_limits.get("requests") if custom_limits else None,
            rate_limit_period=custom_limits.get("period") if custom_limits else None
        )
    
    async def validate_redirect_uri_security(
        self,
        redirect_uri: str,
        client_id: str,
        request: Optional[Request] = None
    ) -> bool:
        """
        Enhanced redirect URI security validation.
        
        Args:
            redirect_uri: Redirect URI to validate
            client_id: OAuth2 client identifier
            request: FastAPI request object (for logging)
            
        Returns:
            True if redirect URI is secure, False otherwise
        """
        # Basic validation first
        if not await self.validate_redirect_uri(client_id, redirect_uri):
            return False
        
        # Additional security checks
        parsed_uri = urlparse(redirect_uri)
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "javascript:",
            "data:",
            "vbscript:",
            "file:",
            "ftp:",
        ]
        
        if any(pattern in redirect_uri.lower() for pattern in suspicious_patterns):
            await self._log_security_violation(
                event_type="suspicious_redirect_uri",
                client_id=client_id,
                request=request,
                details={
                    "redirect_uri": redirect_uri,
                    "reason": "suspicious_scheme"
                }
            )
            return False
        
        # Check for open redirects
        if parsed_uri.hostname and parsed_uri.hostname.lower() in [
            "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly"
        ]:
            await self._log_security_violation(
                event_type="suspicious_redirect_uri",
                client_id=client_id,
                request=request,
                details={
                    "redirect_uri": redirect_uri,
                    "reason": "url_shortener"
                }
            )
            return False
        
        return True
    
    async def _log_security_violation(
        self,
        event_type: str,
        client_id: Optional[str] = None,
        request: Optional[Request] = None,
        details: Optional[Dict] = None
    ) -> None:
        """
        Log security violations with comprehensive context.
        
        Args:
            event_type: Type of security violation
            client_id: OAuth2 client identifier
            request: FastAPI request object
            details: Additional violation details
        """
        violation_context = {
            "event_type": event_type,
            "client_id": client_id,
            "timestamp": time.time(),
            "details": details or {}
        }
        
        if request:
            violation_context.update({
                "client_ip": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
                "request_method": request.method,
                "request_url": str(request.url),
                "request_headers": dict(request.headers)
            })
        
        logger.error(
            f"OAuth2 security violation: {event_type}",
            extra={"security_violation": violation_context}
        )
        
        # Store in Redis for monitoring
        try:
            redis_conn = await self.redis_manager.get_redis()
            violation_key = f"oauth2:security_violations:{int(time.time())}"
            await redis_conn.hset(violation_key, mapping={
                k: str(v) for k, v in violation_context.items()
            })
            await redis_conn.expire(violation_key, 86400)  # 24 hours
        except Exception as e:
            logger.error(f"Failed to store security violation: {e}")


# Global instance
oauth2_security_manager = OAuth2SecurityManager()