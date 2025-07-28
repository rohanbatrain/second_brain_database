"""
OAuth2 user consent management service.

This module provides comprehensive user consent management for OAuth2 authorization,
including consent granting, revocation, persistence, and retrieval operations.
"""

from datetime import datetime
from typing import Dict, List, Optional

from second_brain_database.managers.logging_manager import get_logger

from ..database import oauth2_db
from ..models import ConsentInfo, ConsentRequest, UserConsent, get_scope_descriptions

logger = get_logger(prefix="[OAuth2 Consent Manager]")


class ConsentManager:
    """
    OAuth2 user consent management service.
    
    Handles all aspects of user consent for OAuth2 authorization including:
    - Consent information retrieval for display
    - Consent granting and persistence
    - Consent revocation and cleanup
    - Consent validation and checking
    """
    
    async def get_consent_info(self, client_id: str, user_id: str, requested_scopes: List[str]) -> Optional[ConsentInfo]:
        """
        Get consent information for display to user.
        
        Args:
            client_id: OAuth2 client identifier
            user_id: User identifier
            requested_scopes: List of scopes being requested
            
        Returns:
            ConsentInfo with client details and scope descriptions, None if client not found
        """
        try:
            # Get client information
            client = await oauth2_db.get_client(client_id)
            if not client:
                logger.error(f"Client not found for consent info: {client_id}")
                return None
            
            # Check for existing consent
            existing_consent = await oauth2_db.get_user_consent(user_id, client_id)
            has_existing_consent = existing_consent is not None and existing_consent.is_active
            
            # Get scope descriptions for display
            scope_descriptions = get_scope_descriptions(requested_scopes)
            
            consent_info = ConsentInfo(
                client_name=client.name,
                client_description=client.description,
                website_url=client.website_url,
                requested_scopes=scope_descriptions,
                existing_consent=has_existing_consent
            )
            
            logger.info(f"Retrieved consent info for client {client_id}, user {user_id}")
            return consent_info
            
        except Exception as e:
            logger.error(f"Failed to get consent info for client {client_id}: {e}")
            return None
    
    async def grant_consent(self, user_id: str, consent_request: ConsentRequest) -> bool:
        """
        Grant user consent for OAuth2 client access.
        
        Args:
            user_id: User identifier
            consent_request: Consent request with client_id, scopes, and approval status
            
        Returns:
            bool: True if consent granted successfully
        """
        try:
            if not consent_request.approved:
                logger.info(f"User {user_id} denied consent for client {consent_request.client_id}")
                return False
            
            # Validate client exists
            client = await oauth2_db.get_client(consent_request.client_id)
            if not client:
                logger.error(f"Cannot grant consent for non-existent client: {consent_request.client_id}")
                return False
            
            # Validate client is active
            if not client.is_active:
                logger.error(f"Cannot grant consent for inactive client: {consent_request.client_id}")
                return False
            
            # Validate requested scopes are allowed for this client
            client_scopes = set(client.scopes)
            requested_scopes_set = set(consent_request.scopes)
            if not requested_scopes_set.issubset(client_scopes):
                invalid_scopes = requested_scopes_set - client_scopes
                logger.error(f"Client {consent_request.client_id} requested unauthorized scopes: {invalid_scopes}")
                return False
            
            # Create consent record
            consent = UserConsent(
                user_id=user_id,
                client_id=consent_request.client_id,
                scopes=consent_request.scopes,
                granted_at=datetime.utcnow(),
                is_active=True
            )
            
            # Store consent in database
            success = await oauth2_db.store_user_consent(consent)
            if success:
                logger.info(f"Granted consent for client {consent_request.client_id}, user {user_id}, scopes: {consent_request.scopes}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to grant consent for client {consent_request.client_id}: {e}")
            return False
    
    async def check_existing_consent(self, user_id: str, client_id: str, requested_scopes: List[str]) -> Optional[UserConsent]:
        """
        Check if user has existing valid consent for the requested scopes.
        
        Args:
            user_id: User identifier
            client_id: Client identifier
            requested_scopes: List of scopes being requested
            
        Returns:
            UserConsent if valid consent exists, None otherwise
        """
        try:
            existing_consent = await oauth2_db.get_user_consent(user_id, client_id)
            
            if not existing_consent or not existing_consent.is_active:
                return None
            
            # Check if existing consent covers all requested scopes
            existing_scopes = set(existing_consent.scopes)
            requested_scopes_set = set(requested_scopes)
            
            if requested_scopes_set.issubset(existing_scopes):
                # Update last used timestamp
                await self.update_consent_last_used(user_id, client_id)
                logger.info(f"Found valid existing consent for client {client_id}, user {user_id}")
                return existing_consent
            
            logger.info(f"Existing consent for client {client_id}, user {user_id} does not cover all requested scopes")
            return None
            
        except Exception as e:
            logger.error(f"Failed to check existing consent for client {client_id}: {e}")
            return None
    
    async def update_consent_last_used(self, user_id: str, client_id: str) -> bool:
        """
        Update the last used timestamp for a consent record.
        
        Args:
            user_id: User identifier
            client_id: Client identifier
            
        Returns:
            bool: True if updated successfully
        """
        try:
            # Update last_used_at timestamp in database
            updates = {"last_used_at": datetime.utcnow()}
            
            # Use the consents collection directly for update
            result = await oauth2_db.consents_collection.update_one(
                {"user_id": user_id, "client_id": client_id, "is_active": True},
                {"$set": updates}
            )
            
            success = result.modified_count > 0
            if success:
                logger.debug(f"Updated last used timestamp for consent: client {client_id}, user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to update consent last used timestamp: {e}")
            return False
    
    async def list_user_consents(self, user_id: str) -> List[Dict]:
        """
        List all active consents for a user with client information.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of consent records with client information
        """
        try:
            consents = await oauth2_db.list_user_consents(user_id)
            consent_list = []
            
            for consent in consents:
                # Get client information for each consent
                client = await oauth2_db.get_client(consent.client_id)
                if client:
                    consent_info = {
                        "client_id": consent.client_id,
                        "client_name": client.name,
                        "client_description": client.description,
                        "website_url": client.website_url,
                        "scopes": consent.scopes,
                        "scope_descriptions": get_scope_descriptions(consent.scopes),
                        "granted_at": consent.granted_at,
                        "last_used_at": consent.last_used_at,
                        "is_active": consent.is_active
                    }
                    consent_list.append(consent_info)
            
            logger.info(f"Retrieved {len(consent_list)} consents for user {user_id}")
            return consent_list
            
        except Exception as e:
            logger.error(f"Failed to list user consents for user {user_id}: {e}")
            return []
    
    async def revoke_consent(self, user_id: str, client_id: str) -> bool:
        """
        Revoke user consent for a specific client.
        
        This also revokes all associated refresh tokens for the user-client pair.
        
        Args:
            user_id: User identifier
            client_id: Client identifier
            
        Returns:
            bool: True if revoked successfully
        """
        try:
            # Revoke consent in database
            success = await oauth2_db.revoke_user_consent(user_id, client_id)
            
            if success:
                # Also revoke all refresh tokens for this user-client pair
                try:
                    from .token_manager import token_manager
                    revoked_tokens = await token_manager.revoke_all_user_tokens(user_id, client_id)
                    logger.info(f"Revoked consent and {revoked_tokens} tokens for client {client_id}, user {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to revoke tokens after consent revocation: {e}")
                    # Don't fail the consent revocation if token revocation fails
                
                logger.info(f"Revoked consent for client {client_id}, user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to revoke consent for client {client_id}: {e}")
            return False
    
    async def revoke_all_user_consents(self, user_id: str) -> bool:
        """
        Revoke all consents for a user.
        
        This also revokes all associated refresh tokens for the user.
        
        Args:
            user_id: User identifier
            
        Returns:
            bool: True if revoked successfully
        """
        try:
            # Get all user consents first
            consents = await oauth2_db.list_user_consents(user_id)
            
            revoked_count = 0
            for consent in consents:
                if await oauth2_db.revoke_user_consent(user_id, consent.client_id):
                    revoked_count += 1
            
            # Also revoke all refresh tokens for this user
            if revoked_count > 0:
                try:
                    from .token_manager import token_manager
                    revoked_tokens = await token_manager.revoke_all_user_tokens(user_id)
                    logger.info(f"Revoked {revoked_count} consents and {revoked_tokens} tokens for user {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to revoke tokens after consent revocation: {e}")
                    # Don't fail the consent revocation if token revocation fails
            
            logger.info(f"Revoked {revoked_count} consents for user {user_id}")
            return revoked_count > 0
            
        except Exception as e:
            logger.error(f"Failed to revoke all consents for user {user_id}: {e}")
            return False
    
    async def validate_consent_for_authorization(self, user_id: str, client_id: str, requested_scopes: List[str]) -> bool:
        """
        Validate that user has valid consent for authorization request.
        
        Args:
            user_id: User identifier
            client_id: Client identifier
            requested_scopes: List of scopes being requested
            
        Returns:
            bool: True if user has valid consent for all requested scopes
        """
        try:
            consent = await self.check_existing_consent(user_id, client_id, requested_scopes)
            return consent is not None
            
        except Exception as e:
            logger.error(f"Failed to validate consent for authorization: {e}")
            return False


# Global instance
consent_manager = ConsentManager()