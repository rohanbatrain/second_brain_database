"""
OAuth2 Token Management Service.

This module provides comprehensive token management functionality including:
- Refresh token validation and rotation
- Token revocation and cleanup
- Token expiration handling
- Integration with existing token systems

The implementation follows RFC 7009 (OAuth 2.0 Token Revocation) and integrates
with the existing JWT token system and Redis cache.
"""

import hashlib
import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth.services.auth.login import create_access_token

from ..models import RefreshTokenData, TokenResponse, TokenType

logger = get_logger(prefix="[OAuth2 Token Manager]")


class TokenManager:
    """
    OAuth2 token management service.
    
    Handles refresh token lifecycle, validation, rotation, and revocation.
    Integrates with existing JWT system and Redis cache for token storage.
    """
    
    def __init__(self):
        """Initialize token manager."""
        self.refresh_token_ttl = 30 * 24 * 60 * 60  # 30 days in seconds
        self.access_token_ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
        
    async def generate_refresh_token(
        self, 
        client_id: str, 
        user_id: str, 
        scopes: List[str]
    ) -> Optional[str]:
        """
        Generate and store a new refresh token.
        
        Args:
            client_id: OAuth2 client identifier
            user_id: User identifier
            scopes: List of granted scopes
            
        Returns:
            Refresh token string if successful, None otherwise
        """
        try:
            # Generate secure refresh token
            token_data = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))
            refresh_token = f"rt_{token_data}"
            
            # Create token hash for storage
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            
            # Create refresh token data
            refresh_data = RefreshTokenData(
                token_hash=token_hash,
                client_id=client_id,
                user_id=user_id,
                scopes=scopes,
                expires_at=datetime.now(timezone.utc) + timedelta(seconds=self.refresh_token_ttl),
                created_at=datetime.now(timezone.utc),
                is_active=True
            )
            
            # Store in Redis with expiration
            key = f"oauth2:refresh_token:{token_hash}"
            success = await redis_manager.setex(
                key, 
                self.refresh_token_ttl, 
                refresh_data.model_dump_json()
            )
            
            if success:
                logger.debug(f"Generated refresh token for client {client_id}, user {user_id}")
                return refresh_token
            else:
                logger.error(f"Failed to store refresh token for client {client_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating refresh token: {e}", exc_info=True)
            return None
    
    async def validate_refresh_token(
        self, 
        refresh_token: str, 
        client_id: str
    ) -> Optional[RefreshTokenData]:
        """
        Validate refresh token and return associated data.
        
        Args:
            refresh_token: Refresh token string
            client_id: Expected client identifier
            
        Returns:
            RefreshTokenData if valid, None otherwise
        """
        try:
            # Create token hash
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            key = f"oauth2:refresh_token:{token_hash}"
            
            # Get token data from Redis
            data = await redis_manager.get(key)
            if not data:
                logger.debug("Refresh token not found in Redis")
                return None
            
            refresh_data = RefreshTokenData.model_validate_json(data)
            
            # Validate client matches
            if refresh_data.client_id != client_id:
                logger.warning(f"Client mismatch for refresh token: expected {client_id}, got {refresh_data.client_id}")
                return None
            
            # Check if token is active
            if not refresh_data.is_active:
                logger.warning("Refresh token is inactive")
                return None
            
            # Check if token is expired
            if refresh_data.expires_at < datetime.now(timezone.utc):
                logger.warning("Refresh token is expired")
                await self._cleanup_expired_token(token_hash)
                return None
            
            logger.debug(f"Refresh token validated for client {client_id}")
            return refresh_data
            
        except Exception as e:
            logger.error(f"Error validating refresh token: {e}", exc_info=True)
            return None
    
    async def rotate_refresh_token(
        self,
        old_refresh_token: str,
        client_id: str,
        user_id: str,
        scopes: List[str]
    ) -> Optional[str]:
        """
        Rotate refresh token (invalidate old, create new).
        
        This implements refresh token rotation as a security best practice.
        The old token is immediately invalidated and a new one is generated.
        
        Args:
            old_refresh_token: Current refresh token
            client_id: OAuth2 client identifier
            user_id: User identifier
            scopes: List of granted scopes
            
        Returns:
            New refresh token if successful, None otherwise
        """
        try:
            # Validate old token first
            old_token_data = await self.validate_refresh_token(old_refresh_token, client_id)
            if not old_token_data:
                logger.error(f"Cannot rotate invalid refresh token for client {client_id}")
                return None
            
            # Invalidate old refresh token
            success = await self.revoke_refresh_token(old_refresh_token)
            if not success:
                logger.warning(f"Failed to revoke old refresh token for client {client_id}")
                # Continue anyway, as the new token generation is more important
            
            # Generate new refresh token
            new_refresh_token = await self.generate_refresh_token(client_id, user_id, scopes)
            
            if new_refresh_token:
                logger.info(f"Refresh token rotated for client {client_id}, user {user_id}")
            else:
                logger.error(f"Failed to generate new refresh token for client {client_id}")
            
            return new_refresh_token
            
        except Exception as e:
            logger.error(f"Error rotating refresh token: {e}", exc_info=True)
            return None
    
    async def revoke_refresh_token(self, refresh_token: str) -> bool:
        """
        Revoke a refresh token.
        
        Args:
            refresh_token: Refresh token to revoke
            
        Returns:
            True if revoked successfully, False otherwise
        """
        try:
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            key = f"oauth2:refresh_token:{token_hash}"
            
            deleted = await redis_manager.delete(key)
            
            if deleted:
                logger.debug("Refresh token revoked successfully")
            else:
                logger.debug("Refresh token not found for revocation")
            
            return deleted > 0
            
        except Exception as e:
            logger.error(f"Error revoking refresh token: {e}", exc_info=True)
            return False
    
    async def revoke_all_user_tokens(self, user_id: str, client_id: Optional[str] = None) -> int:
        """
        Revoke all refresh tokens for a user, optionally filtered by client.
        
        Args:
            user_id: User identifier
            client_id: Optional client identifier to filter by
            
        Returns:
            Number of tokens revoked
        """
        try:
            revoked_count = 0
            
            # Get all refresh token keys
            pattern = "oauth2:refresh_token:*"
            keys = await redis_manager.keys(pattern)
            
            for key in keys:
                try:
                    data = await redis_manager.get(key)
                    if not data:
                        continue
                    
                    refresh_data = RefreshTokenData.model_validate_json(data)
                    
                    # Check if this token belongs to the user
                    if refresh_data.user_id != user_id:
                        continue
                    
                    # Check client filter if provided
                    if client_id and refresh_data.client_id != client_id:
                        continue
                    
                    # Revoke the token
                    deleted = await redis_manager.delete(key)
                    if deleted:
                        revoked_count += 1
                        logger.debug(f"Revoked refresh token for user {user_id}, client {refresh_data.client_id}")
                    
                except Exception as e:
                    logger.warning(f"Error processing token key {key}: {e}")
                    continue
            
            logger.info(f"Revoked {revoked_count} refresh tokens for user {user_id}")
            return revoked_count
            
        except Exception as e:
            logger.error(f"Error revoking user tokens: {e}", exc_info=True)
            return 0
    
    async def revoke_all_client_tokens(self, client_id: str) -> int:
        """
        Revoke all refresh tokens for a client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            Number of tokens revoked
        """
        try:
            revoked_count = 0
            
            # Get all refresh token keys
            pattern = "oauth2:refresh_token:*"
            keys = await redis_manager.keys(pattern)
            
            for key in keys:
                try:
                    data = await redis_manager.get(key)
                    if not data:
                        continue
                    
                    refresh_data = RefreshTokenData.model_validate_json(data)
                    
                    # Check if this token belongs to the client
                    if refresh_data.client_id != client_id:
                        continue
                    
                    # Revoke the token
                    deleted = await redis_manager.delete(key)
                    if deleted:
                        revoked_count += 1
                        logger.debug(f"Revoked refresh token for client {client_id}, user {refresh_data.user_id}")
                    
                except Exception as e:
                    logger.warning(f"Error processing token key {key}: {e}")
                    continue
            
            logger.info(f"Revoked {revoked_count} refresh tokens for client {client_id}")
            return revoked_count
            
        except Exception as e:
            logger.error(f"Error revoking client tokens: {e}", exc_info=True)
            return 0
    
    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired refresh tokens from Redis.
        
        Returns:
            Number of expired tokens cleaned up
        """
        try:
            cleaned_count = 0
            current_time = datetime.now(timezone.utc)
            
            # Get all refresh token keys
            pattern = "oauth2:refresh_token:*"
            keys = await redis_manager.keys(pattern)
            
            for key in keys:
                try:
                    data = await redis_manager.get(key)
                    if not data:
                        continue
                    
                    refresh_data = RefreshTokenData.model_validate_json(data)
                    
                    # Check if token is expired
                    if refresh_data.expires_at < current_time:
                        deleted = await redis_manager.delete(key)
                        if deleted:
                            cleaned_count += 1
                            logger.debug(f"Cleaned up expired refresh token for client {refresh_data.client_id}")
                    
                except Exception as e:
                    logger.warning(f"Error processing token key {key}: {e}")
                    continue
            
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired refresh tokens")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}", exc_info=True)
            return 0
    
    async def _cleanup_expired_token(self, token_hash: str) -> None:
        """
        Clean up a specific expired token.
        
        Args:
            token_hash: Hash of the token to clean up
        """
        try:
            key = f"oauth2:refresh_token:{token_hash}"
            await redis_manager.delete(key)
            logger.debug(f"Cleaned up expired token: {token_hash}")
        except Exception as e:
            logger.warning(f"Error cleaning up expired token {token_hash}: {e}")
    
    async def get_token_info(self, refresh_token: str) -> Optional[Dict]:
        """
        Get information about a refresh token without validating client.
        
        Args:
            refresh_token: Refresh token string
            
        Returns:
            Token information dictionary if found, None otherwise
        """
        try:
            token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            key = f"oauth2:refresh_token:{token_hash}"
            
            data = await redis_manager.get(key)
            if not data:
                return None
            
            refresh_data = RefreshTokenData.model_validate_json(data)
            
            return {
                "client_id": refresh_data.client_id,
                "user_id": refresh_data.user_id,
                "scopes": refresh_data.scopes,
                "expires_at": refresh_data.expires_at.isoformat(),
                "created_at": refresh_data.created_at.isoformat(),
                "is_active": refresh_data.is_active
            }
            
        except Exception as e:
            logger.error(f"Error getting token info: {e}", exc_info=True)
            return None
    
    async def refresh_access_token(
        self,
        refresh_token: str,
        client_id: str
    ) -> Optional[TokenResponse]:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token string
            client_id: Client identifier
            
        Returns:
            TokenResponse with new access token and rotated refresh token
        """
        try:
            # Validate refresh token
            refresh_data = await self.validate_refresh_token(refresh_token, client_id)
            if not refresh_data:
                logger.error(f"Invalid refresh token for client {client_id}")
                return None
            
            # Generate new access token
            access_token = await create_access_token({
                "sub": refresh_data.user_id,
                "aud": client_id,
                "scope": " ".join(refresh_data.scopes)
            })
            
            # Rotate refresh token
            new_refresh_token = await self.rotate_refresh_token(
                old_refresh_token=refresh_token,
                client_id=client_id,
                user_id=refresh_data.user_id,
                scopes=refresh_data.scopes
            )
            
            if not new_refresh_token:
                logger.error(f"Failed to rotate refresh token for client {client_id}")
                # Use old refresh token if rotation failed
                new_refresh_token = refresh_token
            
            logger.info(f"Access token refreshed for client {client_id}, user {refresh_data.user_id}")
            
            return TokenResponse(
                access_token=access_token,
                token_type=TokenType.BEARER,
                expires_in=self.access_token_ttl,
                refresh_token=new_refresh_token,
                scope=" ".join(refresh_data.scopes)
            )
            
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}", exc_info=True)
            return None
    
    async def get_token_statistics(self) -> Dict:
        """
        Get statistics about refresh tokens.
        
        Returns:
            Dictionary with token statistics
        """
        try:
            stats = {
                "total_tokens": 0,
                "active_tokens": 0,
                "expired_tokens": 0,
                "clients": set(),
                "users": set()
            }
            
            current_time = datetime.now(timezone.utc)
            pattern = "oauth2:refresh_token:*"
            keys = await redis_manager.keys(pattern)
            
            for key in keys:
                try:
                    data = await redis_manager.get(key)
                    if not data:
                        continue
                    
                    refresh_data = RefreshTokenData.model_validate_json(data)
                    stats["total_tokens"] += 1
                    stats["clients"].add(refresh_data.client_id)
                    stats["users"].add(refresh_data.user_id)
                    
                    if refresh_data.expires_at < current_time:
                        stats["expired_tokens"] += 1
                    else:
                        stats["active_tokens"] += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing token key {key}: {e}")
                    continue
            
            # Convert sets to counts
            stats["unique_clients"] = len(stats["clients"])
            stats["unique_users"] = len(stats["users"])
            del stats["clients"]
            del stats["users"]
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting token statistics: {e}", exc_info=True)
            return {
                "total_tokens": 0,
                "active_tokens": 0,
                "expired_tokens": 0,
                "unique_clients": 0,
                "unique_users": 0,
                "error": str(e)
            }


# Global token manager instance
token_manager = TokenManager()