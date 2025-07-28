"""
OAuth2 authorization code management service.

This module provides secure authorization code generation, storage, retrieval,
and lifecycle management for the OAuth2 authorization code flow.
"""

import hashlib
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

from ..models import AuthorizationCode, PKCEMethod

logger = get_logger(prefix="[OAuth2 AuthCode]")

# Redis key prefix for authorization codes
OAUTH2_AUTH_CODE_PREFIX = "oauth2:auth_code:"
OAUTH2_AUTH_CODE_USAGE_PREFIX = "oauth2:auth_code_usage:"

# Default authorization code expiration (10 minutes as per RFC 6749)
DEFAULT_AUTH_CODE_TTL = 600


class AuthorizationCodeManager:
    """
    Manages OAuth2 authorization codes with secure generation, storage, and lifecycle management.
    
    Features:
    - Secure random authorization code generation
    - Redis-based storage with automatic expiration
    - Usage tracking to prevent replay attacks
    - Cleanup mechanisms for expired codes
    """
    
    def __init__(self):
        self.logger = logger
    
    def generate_authorization_code(self) -> str:
        """
        Generate a cryptographically secure authorization code.
        
        Uses secrets module for secure random generation with sufficient entropy.
        Format: auth_code_<32_random_chars>
        
        Returns:
            str: Secure authorization code
        """
        # Generate 32 characters of random data for high entropy
        random_part = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
        code = f"auth_code_{random_part}"
        
        self.logger.debug("Generated new authorization code")
        return code
    
    async def store_authorization_code(
        self,
        code: str,
        client_id: str,
        user_id: str,
        redirect_uri: str,
        scopes: list[str],
        code_challenge: str,
        code_challenge_method: PKCEMethod,
        ttl_seconds: int = DEFAULT_AUTH_CODE_TTL
    ) -> bool:
        """
        Store authorization code in Redis with expiration and metadata.
        
        Args:
            code: Authorization code string
            client_id: OAuth2 client identifier
            user_id: User who authorized the code
            redirect_uri: Redirect URI used in authorization
            scopes: List of granted scopes
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE challenge method
            ttl_seconds: Time to live in seconds (default 10 minutes)
            
        Returns:
            bool: True if stored successfully, False otherwise
        """
        try:
            # Create authorization code data
            auth_code_data = AuthorizationCode(
                code=code,
                client_id=client_id,
                user_id=user_id,
                redirect_uri=redirect_uri,
                scopes=scopes,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds),
                used=False,
                created_at=datetime.utcnow()
            )
            
            # Store in Redis with expiration
            key = f"{OAUTH2_AUTH_CODE_PREFIX}{code}"
            data = auth_code_data.model_dump_json()
            
            success = await redis_manager.setex(key, ttl_seconds, data)
            
            if success:
                self.logger.info(f"Stored authorization code for client {client_id}, user {user_id}")
                # Also initialize usage tracking
                usage_key = f"{OAUTH2_AUTH_CODE_USAGE_PREFIX}{code}"
                await redis_manager.setex(usage_key, ttl_seconds, "0")
            else:
                self.logger.error(f"Failed to store authorization code for client {client_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error storing authorization code: {e}")
            return False
    
    async def get_authorization_code(self, code: str) -> Optional[AuthorizationCode]:
        """
        Retrieve authorization code data from Redis.
        
        Args:
            code: Authorization code string
            
        Returns:
            AuthorizationCode if found and valid, None otherwise
        """
        try:
            key = f"{OAUTH2_AUTH_CODE_PREFIX}{code}"
            data = await redis_manager.get(key)
            
            if not data:
                self.logger.debug(f"Authorization code not found: {code}")
                return None
            
            auth_code = AuthorizationCode.model_validate_json(data)
            
            # Check if code has expired
            if datetime.utcnow() > auth_code.expires_at:
                self.logger.warning(f"Authorization code expired: {code}")
                # Clean up expired code
                await self._cleanup_authorization_code(code)
                return None
            
            # Check if code has been used
            if auth_code.used:
                self.logger.warning(f"Authorization code already used: {code}")
                return None
            
            self.logger.debug(f"Retrieved valid authorization code for client {auth_code.client_id}")
            return auth_code
            
        except Exception as e:
            self.logger.error(f"Error retrieving authorization code: {e}")
            return None
    
    async def use_authorization_code(self, code: str) -> Optional[AuthorizationCode]:
        """
        Mark authorization code as used and prevent replay attacks.
        
        This method implements single-use semantics for authorization codes
        as required by RFC 6749. Once used, the code cannot be used again.
        
        Args:
            code: Authorization code string
            
        Returns:
            AuthorizationCode if successfully used, None if invalid or already used
        """
        try:
            # First, get the authorization code
            auth_code = await self.get_authorization_code(code)
            if not auth_code:
                return None
            
            # Check usage tracking to prevent replay attacks
            usage_key = f"{OAUTH2_AUTH_CODE_USAGE_PREFIX}{code}"
            usage_count = await redis_manager.get(usage_key)
            
            if usage_count and int(usage_count) > 0:
                self.logger.error(f"Replay attack detected for authorization code: {code}")
                # Immediately revoke the code
                await self._cleanup_authorization_code(code)
                return None
            
            # Increment usage count atomically
            redis_conn = await redis_manager.get_redis()
            new_usage_count = await redis_conn.incr(usage_key)
            
            if new_usage_count > 1:
                self.logger.error(f"Concurrent usage detected for authorization code: {code}")
                # Revoke the code immediately
                await self._cleanup_authorization_code(code)
                return None
            
            # Mark as used and delete from Redis (single use)
            auth_code.used = True
            await self._cleanup_authorization_code(code)
            
            self.logger.info(f"Authorization code used successfully for client {auth_code.client_id}")
            return auth_code
            
        except Exception as e:
            self.logger.error(f"Error using authorization code: {e}")
            return None
    
    async def revoke_authorization_code(self, code: str) -> bool:
        """
        Revoke an authorization code before it expires.
        
        Args:
            code: Authorization code string
            
        Returns:
            bool: True if revoked successfully, False otherwise
        """
        try:
            success = await self._cleanup_authorization_code(code)
            if success:
                self.logger.info(f"Authorization code revoked: {code}")
            return success
            
        except Exception as e:
            self.logger.error(f"Error revoking authorization code: {e}")
            return False
    
    async def _cleanup_authorization_code(self, code: str) -> bool:
        """
        Clean up authorization code and its usage tracking from Redis.
        
        Args:
            code: Authorization code string
            
        Returns:
            bool: True if cleaned up successfully
        """
        try:
            key = f"{OAUTH2_AUTH_CODE_PREFIX}{code}"
            usage_key = f"{OAUTH2_AUTH_CODE_USAGE_PREFIX}{code}"
            
            # Delete both the code and usage tracking
            deleted_count = 0
            deleted_count += await redis_manager.delete(key)
            deleted_count += await redis_manager.delete(usage_key)
            
            return deleted_count > 0
            
        except Exception as e:
            self.logger.error(f"Error cleaning up authorization code: {e}")
            return False
    
    async def cleanup_expired_codes(self) -> int:
        """
        Clean up expired authorization codes from Redis.
        
        This method scans for authorization code keys and removes expired ones.
        Should be called periodically for maintenance.
        
        Returns:
            int: Number of expired codes cleaned up
        """
        try:
            # Get all authorization code keys
            pattern = f"{OAUTH2_AUTH_CODE_PREFIX}*"
            keys = await redis_manager.keys(pattern)
            
            cleaned_count = 0
            current_time = datetime.utcnow()
            
            for key in keys:
                try:
                    data = await redis_manager.get(key)
                    if data:
                        auth_code = AuthorizationCode.model_validate_json(data)
                        if current_time > auth_code.expires_at:
                            # Extract code from key
                            code = key.replace(OAUTH2_AUTH_CODE_PREFIX, "")
                            await self._cleanup_authorization_code(code)
                            cleaned_count += 1
                except Exception:
                    # If we can't parse the data, clean it up anyway
                    await redis_manager.delete(key)
                    cleaned_count += 1
            
            if cleaned_count > 0:
                self.logger.info(f"Cleaned up {cleaned_count} expired authorization codes")
            
            return cleaned_count
            
        except Exception as e:
            self.logger.error(f"Error during authorization code cleanup: {e}")
            return 0
    
    async def get_code_statistics(self) -> dict:
        """
        Get statistics about authorization codes in Redis.
        
        Returns:
            dict: Statistics including total codes, expired codes, etc.
        """
        try:
            pattern = f"{OAUTH2_AUTH_CODE_PREFIX}*"
            keys = await redis_manager.keys(pattern)
            
            total_codes = len(keys)
            expired_codes = 0
            used_codes = 0
            current_time = datetime.utcnow()
            
            for key in keys:
                try:
                    data = await redis_manager.get(key)
                    if data:
                        auth_code = AuthorizationCode.model_validate_json(data)
                        if current_time > auth_code.expires_at:
                            expired_codes += 1
                        if auth_code.used:
                            used_codes += 1
                except Exception:
                    continue
            
            return {
                "total_codes": total_codes,
                "expired_codes": expired_codes,
                "used_codes": used_codes,
                "active_codes": total_codes - expired_codes - used_codes
            }
            
        except Exception as e:
            self.logger.error(f"Error getting code statistics: {e}")
            return {
                "total_codes": 0,
                "expired_codes": 0,
                "used_codes": 0,
                "active_codes": 0
            }


# Global instance
auth_code_manager = AuthorizationCodeManager()