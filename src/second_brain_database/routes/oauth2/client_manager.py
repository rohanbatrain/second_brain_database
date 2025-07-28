"""
OAuth2 client management system.

This module provides comprehensive OAuth2 client management functionality including:
- Client registration and validation
- Client authentication with secure secret hashing
- Client database operations
- Redirect URI validation
- Scope management

The ClientManager integrates with existing crypto utilities and follows the same
security patterns used throughout the Second Brain Database application.
"""

import hashlib
import secrets
import string
from datetime import datetime
from typing import Dict, List, Optional

import bcrypt

from second_brain_database.managers.logging_manager import get_logger

from .database import oauth2_db
from .models import (
    ClientType,
    OAuthClient,
    OAuthClientRegistration,
    OAuthClientResponse,
    generate_client_id,
    generate_client_secret,
    validate_scopes,
)

logger = get_logger(prefix="[OAuth2 ClientManager]")


class ClientManager:
    """
    OAuth2 client application management.
    
    Provides comprehensive client management functionality including registration,
    validation, authentication, and database operations for OAuth2 client applications.
    """
    
    def __init__(self):
        """Initialize the ClientManager."""
        self.db = oauth2_db
        logger.info("OAuth2 ClientManager initialized")
    
    async def register_client(
        self,
        registration: OAuthClientRegistration,
        owner_user_id: Optional[str] = None
    ) -> OAuthClientResponse:
        """
        Register a new OAuth2 client application.
        
        Args:
            registration: Client registration data
            owner_user_id: Optional user ID who owns this client
            
        Returns:
            OAuthClientResponse: Client registration response with credentials
            
        Raises:
            ValueError: If registration data is invalid
            RuntimeError: If client creation fails
        """
        logger.info(f"Registering new OAuth2 client: {registration.name}")
        
        # Validate scopes
        try:
            validated_scopes = validate_scopes(registration.scopes)
        except ValueError as e:
            logger.error(f"Invalid scopes in client registration: {e}")
            raise ValueError(f"Invalid scopes: {e}")
        
        # Generate client credentials
        client_id = generate_client_id()
        client_secret = None
        client_secret_hash = None
        
        # Only confidential clients get a secret
        if registration.client_type == ClientType.CONFIDENTIAL:
            client_secret = generate_client_secret()
            client_secret_hash = self._hash_client_secret(client_secret)
        
        # Create client document
        client = OAuthClient(
            client_id=client_id,
            client_secret_hash=client_secret_hash,
            name=registration.name,
            description=registration.description,
            client_type=registration.client_type,
            redirect_uris=registration.redirect_uris,
            scopes=validated_scopes,
            website_url=registration.website_url,
            owner_user_id=owner_user_id,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        # Store in database
        success = await self.db.create_client(client)
        if not success:
            logger.error(f"Failed to create OAuth2 client in database: {client_id}")
            raise RuntimeError("Failed to create client in database")
        
        logger.info(f"Successfully registered OAuth2 client: {client_id}")
        
        # Return response (client_secret only shown once)
        return OAuthClientResponse(
            client_id=client_id,
            client_secret=client_secret,  # Only returned on registration
            name=registration.name,
            client_type=registration.client_type,
            redirect_uris=registration.redirect_uris,
            scopes=validated_scopes,
            created_at=client.created_at,
            is_active=True
        )
    
    async def validate_client(
        self,
        client_id: str,
        client_secret: Optional[str] = None
    ) -> Optional[OAuthClient]:
        """
        Validate OAuth2 client credentials.
        
        Args:
            client_id: Client identifier
            client_secret: Client secret (required for confidential clients)
            
        Returns:
            OAuthClient if valid, None otherwise
        """
        logger.debug(f"Validating OAuth2 client: {client_id}")
        
        # Get client from database
        client = await self.db.get_client(client_id)
        if not client:
            logger.warning(f"OAuth2 client not found: {client_id}")
            return None
        
        # Check if client is active
        if not client.is_active:
            logger.warning(f"OAuth2 client is inactive: {client_id}")
            return None
        
        # Validate client secret for confidential clients
        if client.client_type == ClientType.CONFIDENTIAL:
            if not client_secret:
                logger.warning(f"Client secret required for confidential client: {client_id}")
                return None
            
            if not self._verify_client_secret(client_secret, client.client_secret_hash):
                logger.warning(f"Invalid client secret for client: {client_id}")
                return None
        
        logger.debug(f"OAuth2 client validation successful: {client_id}")
        return client
    
    async def authenticate_client(
        self,
        client_id: str,
        client_secret: Optional[str] = None
    ) -> bool:
        """
        Authenticate OAuth2 client credentials.
        
        Args:
            client_id: Client identifier
            client_secret: Client secret (required for confidential clients)
            
        Returns:
            bool: True if authentication successful
        """
        client = await self.validate_client(client_id, client_secret)
        return client is not None
    
    async def validate_redirect_uri(
        self,
        client_id: str,
        redirect_uri: str
    ) -> bool:
        """
        Validate redirect URI against registered client URIs.
        
        Args:
            client_id: Client identifier
            redirect_uri: Redirect URI to validate
            
        Returns:
            bool: True if redirect URI is valid
        """
        logger.debug(f"Validating redirect URI for client {client_id}: {redirect_uri}")
        
        client = await self.db.get_client(client_id)
        if not client:
            logger.warning(f"Client not found for redirect URI validation: {client_id}")
            return False
        
        # Check if redirect URI is in the registered list
        is_valid = redirect_uri in client.redirect_uris
        
        if not is_valid:
            logger.warning(f"Invalid redirect URI for client {client_id}: {redirect_uri}")
            logger.debug(f"Registered URIs for client {client_id}: {client.redirect_uris}")
        
        return is_valid
    
    async def get_client_scopes(
        self,
        client_id: str
    ) -> List[str]:
        """
        Get allowed scopes for a client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            List of allowed scopes
        """
        client = await self.db.get_client(client_id)
        if not client:
            logger.warning(f"Client not found for scope retrieval: {client_id}")
            return []
        
        return client.scopes
    
    async def get_client(
        self,
        client_id: str
    ) -> Optional[OAuthClient]:
        """
        Get OAuth2 client by ID.
        
        Args:
            client_id: Client identifier
            
        Returns:
            OAuthClient if found, None otherwise
        """
        return await self.db.get_client(client_id)
    
    async def update_client(
        self,
        client_id: str,
        updates: Dict
    ) -> bool:
        """
        Update OAuth2 client.
        
        Args:
            client_id: Client identifier
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if updated successfully
        """
        logger.info(f"Updating OAuth2 client: {client_id}")
        
        # Validate scopes if being updated
        if "scopes" in updates:
            try:
                updates["scopes"] = validate_scopes(updates["scopes"])
            except ValueError as e:
                logger.error(f"Invalid scopes in client update: {e}")
                raise ValueError(f"Invalid scopes: {e}")
        
        # Hash new client secret if provided
        if "client_secret" in updates:
            client_secret = updates.pop("client_secret")
            updates["client_secret_hash"] = self._hash_client_secret(client_secret)
        
        success = await self.db.update_client(client_id, updates)
        if success:
            logger.info(f"Successfully updated OAuth2 client: {client_id}")
        else:
            logger.error(f"Failed to update OAuth2 client: {client_id}")
        
        return success
    
    async def delete_client(
        self,
        client_id: str
    ) -> bool:
        """
        Delete OAuth2 client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            bool: True if deleted successfully
        """
        logger.info(f"Deleting OAuth2 client: {client_id}")
        
        success = await self.db.delete_client(client_id)
        if success:
            logger.info(f"Successfully deleted OAuth2 client: {client_id}")
        else:
            logger.error(f"Failed to delete OAuth2 client: {client_id}")
        
        return success
    
    async def list_clients(
        self,
        owner_user_id: Optional[str] = None
    ) -> List[OAuthClient]:
        """
        List OAuth2 clients.
        
        Args:
            owner_user_id: Optional filter by owner user ID
            
        Returns:
            List of OAuth2 clients
        """
        return await self.db.list_clients(owner_user_id)
    
    async def deactivate_client(
        self,
        client_id: str
    ) -> bool:
        """
        Deactivate OAuth2 client (soft delete).
        
        Args:
            client_id: Client identifier
            
        Returns:
            bool: True if deactivated successfully
        """
        logger.info(f"Deactivating OAuth2 client: {client_id}")
        
        success = await self.update_client(client_id, {"is_active": False})
        if success:
            logger.info(f"Successfully deactivated OAuth2 client: {client_id}")
        
        return success
    
    async def reactivate_client(
        self,
        client_id: str
    ) -> bool:
        """
        Reactivate OAuth2 client.
        
        Args:
            client_id: Client identifier
            
        Returns:
            bool: True if reactivated successfully
        """
        logger.info(f"Reactivating OAuth2 client: {client_id}")
        
        success = await self.update_client(client_id, {"is_active": True})
        if success:
            logger.info(f"Successfully reactivated OAuth2 client: {client_id}")
        
        return success
    
    async def regenerate_client_secret(
        self,
        client_id: str
    ) -> Optional[str]:
        """
        Regenerate client secret for confidential clients.
        
        Args:
            client_id: Client identifier
            
        Returns:
            New client secret if successful, None otherwise
        """
        logger.info(f"Regenerating client secret for: {client_id}")
        
        # Get client to verify it's confidential
        client = await self.db.get_client(client_id)
        if not client:
            logger.error(f"Client not found for secret regeneration: {client_id}")
            return None
        
        if client.client_type != ClientType.CONFIDENTIAL:
            logger.error(f"Cannot regenerate secret for public client: {client_id}")
            return None
        
        # Generate new secret
        new_secret = generate_client_secret()
        new_secret_hash = self._hash_client_secret(new_secret)
        
        # Update in database
        success = await self.update_client(client_id, {"client_secret_hash": new_secret_hash})
        if not success:
            logger.error(f"Failed to update client secret in database: {client_id}")
            return None
        
        logger.info(f"Successfully regenerated client secret for: {client_id}")
        return new_secret
    
    def _hash_client_secret(self, client_secret: str) -> str:
        """
        Hash client secret using bcrypt.
        
        Args:
            client_secret: Plain text client secret
            
        Returns:
            Hashed client secret
        """
        return bcrypt.hashpw(client_secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    
    def _verify_client_secret(self, client_secret: str, client_secret_hash: str) -> bool:
        """
        Verify client secret against hash.
        
        Args:
            client_secret: Plain text client secret
            client_secret_hash: Hashed client secret
            
        Returns:
            bool: True if secret matches hash
        """
        try:
            return bcrypt.checkpw(client_secret.encode("utf-8"), client_secret_hash.encode("utf-8"))
        except Exception as e:
            logger.error(f"Error verifying client secret: {e}")
            return False


# Global instance
client_manager = ClientManager()