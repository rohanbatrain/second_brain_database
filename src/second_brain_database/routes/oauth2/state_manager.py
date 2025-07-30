"""
OAuth2 state management system for preserving authorization parameters.

This module provides comprehensive OAuth2 state management including:
- Secure state storage in Redis with encryption
- State creation when redirecting to login
- State retrieval when returning from login
- State expiration and cleanup
- State validation to prevent tampering
- Enterprise-grade security features

The state management system ensures OAuth2 authorization parameters are
preserved securely during authentication redirects while maintaining
enterprise security standards.
"""

import hashlib
import json
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
from urllib.parse import urlencode

from fastapi import HTTPException, Request, status
from cryptography.fernet import Fernet

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[OAuth2 StateManager]")


class OAuth2StateManager:
    """
    OAuth2 state management system for secure parameter preservation.
    
    Provides enterprise-grade state management for OAuth2 authorization flows
    including secure storage, validation, and cleanup of authorization parameters
    during authentication redirects.
    """
    
    def __init__(self):
        """Initialize the OAuth2StateManager with encryption and Redis connection."""
        self.redis_manager = redis_manager
        self._fernet = self._initialize_encryption()
        
        # State configuration
        self.default_ttl = 1800  # 30 minutes
        self.max_ttl = 3600      # 1 hour
        self.cleanup_interval = 300  # 5 minutes
        
        logger.info("OAuth2StateManager initialized with enterprise security")
    
    def _initialize_encryption(self) -> Fernet:
        """
        Initialize Fernet encryption for state data protection.
        
        Returns:
            Configured Fernet instance for encryption/decryption
        """
        try:
            import base64
            
            key_raw = settings.FERNET_KEY.get_secret_value()
            key_material = key_raw.encode("utf-8")
            
            # Try to decode as base64; if it fails, hash and encode
            try:
                decoded = base64.urlsafe_b64decode(key_material)
                if len(decoded) == 32:
                    return Fernet(key_material)
            except Exception:
                pass
            
            # If not valid base64, hash and encode
            hashed_key = hashlib.sha256(key_material).digest()
            encoded_key = base64.urlsafe_b64encode(hashed_key)
            return Fernet(encoded_key)
            
        except Exception as e:
            logger.error(f"Failed to initialize OAuth2 state encryption: {e}")
            raise RuntimeError("OAuth2 state encryption initialization failed")
    
    def generate_state_key(self, client_id: str, original_state: str) -> str:
        """
        Generate a cryptographically secure state key for OAuth2 parameter storage.
        
        Args:
            client_id: OAuth2 client identifier
            original_state: Original OAuth2 state parameter
            
        Returns:
            Cryptographically secure state key
        """
        # Generate multiple entropy sources
        timestamp = str(int(time.time() * 1000))
        random_primary = secrets.token_urlsafe(24)
        random_secondary = secrets.token_urlsafe(16)
        
        # Create state components with multiple entropy sources
        state_components = [
            client_id,
            original_state,
            timestamp,
            random_primary,
            random_secondary,
            secrets.token_hex(8)
        ]
        
        # Combine and hash
        state_data = ":".join(state_components)
        state_hash = hashlib.sha256(state_data.encode('utf-8')).hexdigest()
        
        # Create final key with security layers
        key_components = [
            "oauth2_state",
            state_hash[:20],
            timestamp,
            random_primary[:12]
        ]
        
        return ":".join(key_components)
    
    async def store_authorization_state(
        self,
        request: Request,
        client_id: str,
        redirect_uri: str,
        scope: str,
        state: str,
        code_challenge: str,
        code_challenge_method: str,
        response_type: str,
        ttl_seconds: Optional[int] = None
    ) -> str:
        """
        Store OAuth2 authorization parameters securely during authentication redirect.
        
        Args:
            request: FastAPI request object
            client_id: OAuth2 client identifier
            redirect_uri: Client redirect URI
            scope: Requested scopes
            state: OAuth2 state parameter
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE challenge method
            response_type: OAuth2 response type
            ttl_seconds: Custom TTL in seconds (optional)
            
        Returns:
            Secure state key for retrieving stored parameters
            
        Raises:
            HTTPException: If state storage fails
        """
        try:
            # Generate secure state key
            state_key = self.generate_state_key(client_id, state)
            
            # Prepare comprehensive state data
            auth_state = {
                # Core OAuth2 parameters
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                "response_type": response_type,
                
                # Security and audit context
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "client_ip": request.client.host if request.client else "unknown",
                "user_agent": request.headers.get("user-agent", ""),
                "request_id": getattr(request.state, "request_id", None),
                
                # Security fingerprinting
                "security_fingerprint": {
                    "accept_language": request.headers.get("accept-language", ""),
                    "accept_encoding": request.headers.get("accept-encoding", ""),
                    "connection": request.headers.get("connection", ""),
                    "request_method": request.method,
                    "request_path": request.url.path,
                    "query_params_hash": hash(str(sorted(request.query_params.items())))
                },
                
                # Metadata
                "storage_version": "1.0",
                "ttl_seconds": ttl_seconds or self.default_ttl
            }
            
            # Encrypt state data
            encrypted_data = await self._encrypt_state_data(auth_state)
            
            # Store in Redis with TTL
            redis_conn = await self.redis_manager.get_redis()
            redis_key = f"oauth2:state:{state_key}"
            ttl = min(ttl_seconds or self.default_ttl, self.max_ttl)
            
            await redis_conn.setex(redis_key, ttl, encrypted_data)
            
            # Log successful storage
            logger.info(
                "OAuth2 authorization state stored securely",
                extra={
                    "state_key": state_key,
                    "client_id": client_id,
                    "original_state": state,
                    "client_ip": request.client.host if request.client else "unknown",
                    "ttl_seconds": ttl,
                    "event_type": "oauth2_state_stored"
                }
            )
            
            return state_key
            
        except Exception as e:
            logger.error(
                f"Failed to store OAuth2 authorization state: {e}",
                exc_info=True,
                extra={
                    "client_id": client_id,
                    "state": state,
                    "client_ip": request.client.host if request.client else "unknown"
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to preserve authorization state for security reasons"
            )
    
    async def retrieve_authorization_state(self, state_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve and consume stored OAuth2 authorization parameters.
        
        Args:
            state_key: Secure state key from state storage
            
        Returns:
            Authorization state data if found and valid, None otherwise
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            redis_key = f"oauth2:state:{state_key}"
            
            # Retrieve encrypted data
            encrypted_data = await redis_conn.get(redis_key)
            if not encrypted_data:
                logger.warning(
                    "OAuth2 authorization state not found or expired",
                    extra={
                        "state_key": state_key,
                        "event_type": "oauth2_state_not_found"
                    }
                )
                return None
            
            # Decrypt state data
            auth_state = await self._decrypt_state_data(encrypted_data)
            
            # Validate state integrity
            if not self._validate_state_integrity(auth_state):
                logger.warning(
                    "OAuth2 authorization state failed integrity validation",
                    extra={
                        "state_key": state_key,
                        "client_id": auth_state.get("client_id"),
                        "event_type": "oauth2_state_validation_failed"
                    }
                )
                return None
            
            # Delete state after successful retrieval (single use)
            await redis_conn.delete(redis_key)
            
            # Log successful retrieval
            logger.info(
                "OAuth2 authorization state retrieved successfully",
                extra={
                    "state_key": state_key,
                    "client_id": auth_state.get("client_id"),
                    "original_state": auth_state.get("state"),
                    "age_seconds": self._calculate_state_age(auth_state),
                    "event_type": "oauth2_state_retrieved"
                }
            )
            
            return auth_state
            
        except Exception as e:
            logger.error(
                f"Error retrieving OAuth2 authorization state: {e}",
                exc_info=True,
                extra={
                    "state_key": state_key,
                    "event_type": "oauth2_state_retrieval_error"
                }
            )
            return None
    
    async def validate_state_parameters(
        self,
        state_key: str,
        expected_client_id: Optional[str] = None,
        expected_state: Optional[str] = None
    ) -> bool:
        """
        Validate state parameters without consuming the state.
        
        Args:
            state_key: State key to validate
            expected_client_id: Expected client ID (optional)
            expected_state: Expected original state (optional)
            
        Returns:
            True if state is valid and matches expectations
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            redis_key = f"oauth2:state:{state_key}"
            
            # Check if state exists
            encrypted_data = await redis_conn.get(redis_key)
            if not encrypted_data:
                return False
            
            # Decrypt and validate
            auth_state = await self._decrypt_state_data(encrypted_data)
            if not self._validate_state_integrity(auth_state):
                return False
            
            # Check expected values
            if expected_client_id and auth_state.get("client_id") != expected_client_id:
                return False
            
            if expected_state and auth_state.get("state") != expected_state:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating state parameters: {e}")
            return False
    
    async def cleanup_expired_states(self) -> int:
        """
        Clean up expired OAuth2 states from Redis.
        
        Returns:
            Number of expired states cleaned up
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            pattern = "oauth2:state:*"
            
            # Get all state keys
            state_keys = await redis_conn.keys(pattern)
            cleaned_count = 0
            
            for key in state_keys:
                # Check TTL
                ttl = await redis_conn.ttl(key)
                if ttl == -2:  # Key doesn't exist
                    cleaned_count += 1
                elif ttl == -1:  # Key exists but no TTL set (shouldn't happen)
                    # Set a default TTL
                    await redis_conn.expire(key, self.default_ttl)
            
            if cleaned_count > 0:
                logger.info(
                    f"Cleaned up {cleaned_count} expired OAuth2 states",
                    extra={
                        "cleaned_count": cleaned_count,
                        "total_checked": len(state_keys),
                        "event_type": "oauth2_state_cleanup"
                    }
                )
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error during OAuth2 state cleanup: {e}")
            return 0
    
    async def get_state_statistics(self) -> Dict[str, int]:
        """
        Get statistics about stored OAuth2 states.
        
        Returns:
            Dictionary with state statistics
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            pattern = "oauth2:state:*"
            
            state_keys = await redis_conn.keys(pattern)
            total_states = len(state_keys)
            
            # Count states by TTL ranges
            expiring_soon = 0  # < 5 minutes
            normal_ttl = 0     # 5-30 minutes
            long_ttl = 0       # > 30 minutes
            
            for key in state_keys:
                ttl = await redis_conn.ttl(key)
                if ttl > 0:
                    if ttl < 300:  # 5 minutes
                        expiring_soon += 1
                    elif ttl <= 1800:  # 30 minutes
                        normal_ttl += 1
                    else:
                        long_ttl += 1
            
            return {
                "total_states": total_states,
                "expiring_soon": expiring_soon,
                "normal_ttl": normal_ttl,
                "long_ttl": long_ttl
            }
            
        except Exception as e:
            logger.error(f"Error getting state statistics: {e}")
            return {
                "total_states": 0,
                "expiring_soon": 0,
                "normal_ttl": 0,
                "long_ttl": 0
            }
    
    async def _encrypt_state_data(self, state_data: Dict[str, Any]) -> str:
        """
        Encrypt state data for secure storage.
        
        Args:
            state_data: State data to encrypt
            
        Returns:
            Encrypted state data as string
        """
        try:
            json_data = json.dumps(state_data, sort_keys=True, default=str)
            encrypted_data = self._fernet.encrypt(json_data.encode())
            return encrypted_data.decode()
        except Exception as e:
            logger.error(f"Failed to encrypt state data: {e}")
            raise
    
    async def _decrypt_state_data(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt state data from secure storage.
        
        Args:
            encrypted_data: Encrypted state data string
            
        Returns:
            Decrypted state data dictionary
        """
        try:
            decrypted_data = self._fernet.decrypt(encrypted_data.encode())
            return json.loads(decrypted_data.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt state data: {e}")
            raise
    
    def _validate_state_integrity(self, auth_state: Dict[str, Any]) -> bool:
        """
        Validate the integrity and security of retrieved OAuth2 state.
        
        Args:
            auth_state: Retrieved authorization state data
            
        Returns:
            True if state is valid and secure
        """
        try:
            # Check required fields
            required_fields = [
                "client_id", "redirect_uri", "scope", "state",
                "code_challenge", "code_challenge_method", "response_type", "timestamp"
            ]
            
            for field in required_fields:
                if field not in auth_state:
                    logger.warning(f"Missing required field in OAuth2 state: {field}")
                    return False
            
            # Validate timestamp (not too old)
            timestamp_str = auth_state.get("timestamp")
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timestamp.tzinfo is None:
                        timestamp = timestamp.replace(tzinfo=timezone.utc)
                    
                    current_time = datetime.now(timezone.utc)
                    age = current_time - timestamp
                    
                    # State should not be older than max TTL
                    if age.total_seconds() > self.max_ttl:
                        logger.warning(f"OAuth2 state too old: {age.total_seconds()} seconds")
                        return False
                        
                except ValueError as e:
                    logger.warning(f"Invalid timestamp in OAuth2 state: {e}")
                    return False
            
            # Validate OAuth2 parameters
            if auth_state.get("response_type") != "code":
                logger.warning(f"Invalid response_type in OAuth2 state: {auth_state.get('response_type')}")
                return False
            
            if auth_state.get("code_challenge_method") not in ["S256", "plain"]:
                logger.warning(f"Invalid code_challenge_method in OAuth2 state: {auth_state.get('code_challenge_method')}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating OAuth2 state: {e}")
            return False
    
    def _calculate_state_age(self, auth_state: Dict[str, Any]) -> Optional[float]:
        """
        Calculate the age of a state in seconds.
        
        Args:
            auth_state: Authorization state data
            
        Returns:
            Age in seconds, or None if timestamp is invalid
        """
        try:
            timestamp_str = auth_state.get("timestamp")
            if not timestamp_str:
                return None
            
            timestamp = datetime.fromisoformat(timestamp_str)
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            
            current_time = datetime.now(timezone.utc)
            age = current_time - timestamp
            return age.total_seconds()
            
        except Exception:
            return None


# Global instance
oauth2_state_manager = OAuth2StateManager()