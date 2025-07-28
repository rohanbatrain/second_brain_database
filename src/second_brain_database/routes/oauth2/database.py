"""
OAuth2 database operations.

This module provides database operations for OAuth2 provider functionality,
including client management, authorization codes, user consents, and token storage.
"""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

from .models import (
    AuthorizationCode,
    OAuthClient,
    RefreshTokenData,
    UserConsent,
)

logger = get_logger(prefix="[OAuth2 Database]")

# Collection names
OAUTH2_CLIENTS_COLLECTION = "oauth2_clients"
OAUTH2_USER_CONSENTS_COLLECTION = "oauth2_user_consents"

# Redis key prefixes
OAUTH2_AUTH_CODE_PREFIX = "oauth2:auth_code:"
OAUTH2_REFRESH_TOKEN_PREFIX = "oauth2:refresh_token:"
OAUTH2_STATE_PREFIX = "oauth2:state:"


class OAuth2DatabaseManager:
    """Database operations manager for OAuth2 provider."""
    
    def __init__(self):
        self._clients_collection = None
        self._consents_collection = None
    
    @property
    def clients_collection(self):
        """Lazy initialization of clients collection."""
        if self._clients_collection is None:
            self._clients_collection = db_manager.get_collection(OAUTH2_CLIENTS_COLLECTION)
        return self._clients_collection
    
    @property
    def consents_collection(self):
        """Lazy initialization of consents collection."""
        if self._consents_collection is None:
            self._consents_collection = db_manager.get_collection(OAUTH2_USER_CONSENTS_COLLECTION)
        return self._consents_collection
    
    # Client Management
    
    async def create_client(self, client: OAuthClient) -> bool:
        """
        Create a new OAuth2 client in the database.
        
        Args:
            client: OAuth2 client document to create
            
        Returns:
            bool: True if created successfully
        """
        try:
            result = await self.clients_collection.insert_one(client.model_dump())
            logger.info(f"Created OAuth2 client: {client.client_id}")
            return result.inserted_id is not None
        except Exception as e:
            logger.error(f"Failed to create OAuth2 client {client.client_id}: {e}")
            return False
    
    async def get_client(self, client_id: str) -> Optional[OAuthClient]:
        """
        Get OAuth2 client by client ID.
        
        Args:
            client_id: Client identifier
            
        Returns:
            OAuthClient if found, None otherwise
        """
        try:
            doc = await self.clients_collection.find_one({"client_id": client_id})
            if doc:
                # Remove MongoDB _id field
                doc.pop("_id", None)
                return OAuthClient(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to get OAuth2 client {client_id}: {e}")
            return None
    
    async def update_client(self, client_id: str, updates: Dict) -> bool:
        """
        Update OAuth2 client.
        
        Args:
            client_id: Client identifier
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if updated successfully
        """
        try:
            updates["updated_at"] = datetime.utcnow()
            result = await self.clients_collection.update_one(
                {"client_id": client_id},
                {"$set": updates}
            )
            logger.info(f"Updated OAuth2 client: {client_id}")
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update OAuth2 client {client_id}: {e}")
            return False
    
    async def delete_client(self, client_id: str) -> bool:
        """
        Delete OAuth2 client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            result = await self.clients_collection.delete_one({"client_id": client_id})
            if result.deleted_count > 0:
                logger.info(f"Deleted OAuth2 client: {client_id}")
                # Also clean up related consents
                await self.revoke_all_client_consents(client_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete OAuth2 client {client_id}: {e}")
            return False
    
    async def list_clients(self, owner_user_id: Optional[str] = None) -> List[OAuthClient]:
        """
        List OAuth2 clients.
        
        Args:
            owner_user_id: Optional filter by owner user ID
            
        Returns:
            List of OAuth2 clients
        """
        try:
            query = {}
            if owner_user_id:
                query["owner_user_id"] = owner_user_id
            
            cursor = self.clients_collection.find(query).sort("created_at", -1)
            clients = []
            async for doc in cursor:
                doc.pop("_id", None)
                clients.append(OAuthClient(**doc))
            
            return clients
        except Exception as e:
            logger.error(f"Failed to list OAuth2 clients: {e}")
            return []
    
    # Authorization Code Management
    
    async def store_authorization_code(self, auth_code: AuthorizationCode, ttl_seconds: int = 600) -> bool:
        """
        Store authorization code in Redis with expiration.
        
        Args:
            auth_code: Authorization code data
            ttl_seconds: Time to live in seconds (default 10 minutes)
            
        Returns:
            bool: True if stored successfully
        """
        try:
            key = f"{OAUTH2_AUTH_CODE_PREFIX}{auth_code.code}"
            data = auth_code.model_dump_json()
            
            success = await redis_manager.setex(key, ttl_seconds, data)
            if success:
                logger.info(f"Stored authorization code for client {auth_code.client_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to store authorization code: {e}")
            return False
    
    async def get_authorization_code(self, code: str) -> Optional[AuthorizationCode]:
        """
        Get authorization code from Redis.
        
        Args:
            code: Authorization code string
            
        Returns:
            AuthorizationCode if found and valid, None otherwise
        """
        try:
            key = f"{OAUTH2_AUTH_CODE_PREFIX}{code}"
            data = await redis_manager.get(key)
            
            if data:
                return AuthorizationCode.model_validate_json(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get authorization code: {e}")
            return None
    
    async def use_authorization_code(self, code: str) -> bool:
        """
        Mark authorization code as used and delete from Redis.
        
        Args:
            code: Authorization code string
            
        Returns:
            bool: True if marked as used successfully
        """
        try:
            key = f"{OAUTH2_AUTH_CODE_PREFIX}{code}"
            
            # Get the code first to mark as used
            auth_code = await self.get_authorization_code(code)
            if not auth_code:
                return False
            
            # Delete from Redis (single use)
            deleted = await redis_manager.delete(key)
            if deleted:
                logger.info(f"Used authorization code for client {auth_code.client_id}")
            return deleted > 0
        except Exception as e:
            logger.error(f"Failed to use authorization code: {e}")
            return False
    
    # User Consent Management
    
    async def store_user_consent(self, consent: UserConsent) -> bool:
        """
        Store user consent in database.
        
        Args:
            consent: User consent data
            
        Returns:
            bool: True if stored successfully
        """
        try:
            # Check if consent already exists
            existing = await self.consents_collection.find_one({
                "user_id": consent.user_id,
                "client_id": consent.client_id
            })
            
            if existing:
                # Update existing consent
                result = await self.consents_collection.update_one(
                    {"user_id": consent.user_id, "client_id": consent.client_id},
                    {"$set": {
                        "scopes": consent.scopes,
                        "granted_at": consent.granted_at,
                        "is_active": consent.is_active
                    }}
                )
                success = result.modified_count > 0
            else:
                # Create new consent
                result = await self.consents_collection.insert_one(consent.model_dump())
                success = result.inserted_id is not None
            
            if success:
                logger.info(f"Stored user consent for client {consent.client_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to store user consent: {e}")
            return False
    
    async def get_user_consent(self, user_id: str, client_id: str) -> Optional[UserConsent]:
        """
        Get user consent for a specific client.
        
        Args:
            user_id: User identifier
            client_id: Client identifier
            
        Returns:
            UserConsent if found, None otherwise
        """
        try:
            doc = await self.consents_collection.find_one({
                "user_id": user_id,
                "client_id": client_id,
                "is_active": True
            })
            
            if doc:
                doc.pop("_id", None)
                return UserConsent(**doc)
            return None
        except Exception as e:
            logger.error(f"Failed to get user consent: {e}")
            return None
    
    async def list_user_consents(self, user_id: str) -> List[UserConsent]:
        """
        List all consents for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of user consents
        """
        try:
            cursor = self.consents_collection.find({
                "user_id": user_id,
                "is_active": True
            }).sort("granted_at", -1)
            
            consents = []
            async for doc in cursor:
                doc.pop("_id", None)
                consents.append(UserConsent(**doc))
            
            return consents
        except Exception as e:
            logger.error(f"Failed to list user consents: {e}")
            return []
    
    async def revoke_user_consent(self, user_id: str, client_id: str) -> bool:
        """
        Revoke user consent for a specific client.
        
        Args:
            user_id: User identifier
            client_id: Client identifier
            
        Returns:
            bool: True if revoked successfully
        """
        try:
            result = await self.consents_collection.update_one(
                {"user_id": user_id, "client_id": client_id},
                {"$set": {"is_active": False}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Revoked user consent for client {client_id}")
                # Also invalidate any refresh tokens for this client/user
                await self.revoke_refresh_tokens(user_id, client_id)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to revoke user consent: {e}")
            return False
    
    async def revoke_all_client_consents(self, client_id: str) -> bool:
        """
        Revoke all user consents for a specific client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            bool: True if revoked successfully
        """
        try:
            result = await self.consents_collection.update_many(
                {"client_id": client_id},
                {"$set": {"is_active": False}}
            )
            
            logger.info(f"Revoked all consents for client {client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke all client consents: {e}")
            return False
    
    # Refresh Token Management
    
    async def store_refresh_token(self, token_hash: str, token_data: RefreshTokenData, ttl_seconds: int) -> bool:
        """
        Store refresh token in Redis.
        
        Args:
            token_hash: SHA-256 hash of the refresh token
            token_data: Refresh token metadata
            ttl_seconds: Time to live in seconds
            
        Returns:
            bool: True if stored successfully
        """
        try:
            key = f"{OAUTH2_REFRESH_TOKEN_PREFIX}{token_hash}"
            data = token_data.model_dump_json()
            
            success = await redis_manager.setex(key, ttl_seconds, data)
            if success:
                logger.info(f"Stored refresh token for client {token_data.client_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to store refresh token: {e}")
            return False
    
    async def get_refresh_token(self, token_hash: str) -> Optional[RefreshTokenData]:
        """
        Get refresh token data from Redis.
        
        Args:
            token_hash: SHA-256 hash of the refresh token
            
        Returns:
            RefreshTokenData if found and valid, None otherwise
        """
        try:
            key = f"{OAUTH2_REFRESH_TOKEN_PREFIX}{token_hash}"
            data = await redis_manager.get(key)
            
            if data:
                return RefreshTokenData.model_validate_json(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get refresh token: {e}")
            return None
    
    async def revoke_refresh_token(self, token_hash: str) -> bool:
        """
        Revoke a specific refresh token.
        
        Args:
            token_hash: SHA-256 hash of the refresh token
            
        Returns:
            bool: True if revoked successfully
        """
        try:
            key = f"{OAUTH2_REFRESH_TOKEN_PREFIX}{token_hash}"
            deleted = await redis_manager.delete(key)
            
            if deleted > 0:
                logger.info("Revoked refresh token")
            return deleted > 0
        except Exception as e:
            logger.error(f"Failed to revoke refresh token: {e}")
            return False
    
    async def revoke_refresh_tokens(self, user_id: str, client_id: str) -> bool:
        """
        Revoke all refresh tokens for a user/client combination.
        
        Args:
            user_id: User identifier
            client_id: Client identifier
            
        Returns:
            bool: True if revoked successfully
        """
        try:
            # Get all refresh token keys
            pattern = f"{OAUTH2_REFRESH_TOKEN_PREFIX}*"
            keys = await redis_manager.keys(pattern)
            
            revoked_count = 0
            for key in keys:
                data = await redis_manager.get(key)
                if data:
                    try:
                        token_data = RefreshTokenData.model_validate_json(data)
                        if token_data.user_id == user_id and token_data.client_id == client_id:
                            await redis_manager.delete(key)
                            revoked_count += 1
                    except Exception:
                        continue
            
            logger.info(f"Revoked {revoked_count} refresh tokens for user {user_id}, client {client_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to revoke refresh tokens: {e}")
            return False
    
    # State Management (CSRF Protection)
    
    async def store_state(self, state: str, data: Dict, ttl_seconds: int = 600) -> bool:
        """
        Store OAuth2 state parameter for CSRF protection.
        
        Args:
            state: State parameter string
            data: State data to store
            ttl_seconds: Time to live in seconds (default 10 minutes)
            
        Returns:
            bool: True if stored successfully
        """
        try:
            key = f"{OAUTH2_STATE_PREFIX}{state}"
            success = await redis_manager.setex(key, ttl_seconds, str(data))
            return success
        except Exception as e:
            logger.error(f"Failed to store OAuth2 state: {e}")
            return False
    
    async def validate_and_consume_state(self, state: str) -> Optional[Dict]:
        """
        Validate state parameter and consume it (single use).
        
        Args:
            state: State parameter string
            
        Returns:
            State data if valid, None otherwise
        """
        try:
            key = f"{OAUTH2_STATE_PREFIX}{state}"
            data = await redis_manager.get(key)
            
            if data:
                # Delete state (single use)
                await redis_manager.delete(key)
                return eval(data)  # Convert string back to dict
            return None
        except Exception as e:
            logger.error(f"Failed to validate OAuth2 state: {e}")
            return None


# Global instance
oauth2_db = OAuth2DatabaseManager()