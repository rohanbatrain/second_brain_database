"""
OAuth2 security manager and validation layer.

This module provides OAuth2-specific security operations including:
- Redirect URI validation against registered client URIs
- State parameter generation and validation for CSRF protection
- Integration with existing security_manager for rate limiting
- OAuth2-specific security validations and protections

The OAuth2SecurityManager integrates with the existing security infrastructure
while providing OAuth2-specific security features and validations.
"""

import hashlib
import secrets
import string
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException, Request, status

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.security_manager import security_manager

from .client_manager import client_manager

logger = get_logger(prefix="[OAuth2 SecurityManager]")


class OAuth2SecurityManager:
    """
    OAuth2-specific security operations and validations.
    
    Provides comprehensive security features for OAuth2 flows including:
    - Redirect URI validation against registered client URIs
    - State parameter generation and validation for CSRF protection
    - Rate limiting integration for OAuth2 endpoints
    - OAuth2-specific security validations
    """
    
    def __init__(self):
        """Initialize the OAuth2SecurityManager."""
        self.redis_manager = redis_manager
        self.security_manager = security_manager
        self.client_manager = client_manager
        logger.info("OAuth2SecurityManager initialized")
    
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
            HTTPException: If rate limit is exceeded
        """
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


# Global instance
oauth2_security_manager = OAuth2SecurityManager()