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
                # Log consent denial for audit trail
                await self._log_consent_audit_event(
                    event_type="consent_denied",
                    user_id=user_id,
                    client_id=consent_request.client_id,
                    scopes=consent_request.scopes,
                    additional_context={
                        "denial_reason": "user_denied",
                        "state": consent_request.state
                    }
                )
                return False
            
            # Validate client exists
            client = await oauth2_db.get_client(consent_request.client_id)
            if not client:
                logger.error(f"Cannot grant consent for non-existent client: {consent_request.client_id}")
                await self._log_consent_audit_event(
                    event_type="consent_grant_failed",
                    user_id=user_id,
                    client_id=consent_request.client_id,
                    scopes=consent_request.scopes,
                    additional_context={
                        "failure_reason": "client_not_found",
                        "state": consent_request.state
                    }
                )
                return False
            
            # Validate client is active
            if not client.is_active:
                logger.error(f"Cannot grant consent for inactive client: {consent_request.client_id}")
                await self._log_consent_audit_event(
                    event_type="consent_grant_failed",
                    user_id=user_id,
                    client_id=consent_request.client_id,
                    scopes=consent_request.scopes,
                    additional_context={
                        "failure_reason": "client_inactive",
                        "client_name": client.name,
                        "state": consent_request.state
                    }
                )
                return False
            
            # Validate requested scopes are allowed for this client
            client_scopes = set(client.scopes)
            requested_scopes_set = set(consent_request.scopes)
            if not requested_scopes_set.issubset(client_scopes):
                invalid_scopes = requested_scopes_set - client_scopes
                logger.error(f"Client {consent_request.client_id} requested unauthorized scopes: {invalid_scopes}")
                await self._log_consent_audit_event(
                    event_type="consent_grant_failed",
                    user_id=user_id,
                    client_id=consent_request.client_id,
                    scopes=consent_request.scopes,
                    additional_context={
                        "failure_reason": "unauthorized_scopes",
                        "invalid_scopes": list(invalid_scopes),
                        "client_scopes": list(client_scopes),
                        "client_name": client.name,
                        "state": consent_request.state
                    }
                )
                return False
            
            # Check if this is updating existing consent
            existing_consent = await oauth2_db.get_user_consent(user_id, consent_request.client_id)
            is_update = existing_consent is not None and existing_consent.is_active
            
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
                
                # Log successful consent grant for audit trail
                await self._log_consent_audit_event(
                    event_type="consent_granted" if not is_update else "consent_updated",
                    user_id=user_id,
                    client_id=consent_request.client_id,
                    scopes=consent_request.scopes,
                    additional_context={
                        "client_name": client.name,
                        "client_type": client.client_type.value,
                        "is_update": is_update,
                        "previous_scopes": existing_consent.scopes if existing_consent else [],
                        "state": consent_request.state,
                        "granted_at": consent.granted_at.isoformat()
                    }
                )
            else:
                await self._log_consent_audit_event(
                    event_type="consent_grant_failed",
                    user_id=user_id,
                    client_id=consent_request.client_id,
                    scopes=consent_request.scopes,
                    additional_context={
                        "failure_reason": "database_error",
                        "client_name": client.name,
                        "state": consent_request.state
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to grant consent for client {consent_request.client_id}: {e}")
            await self._log_consent_audit_event(
                event_type="consent_grant_error",
                user_id=user_id,
                client_id=consent_request.client_id,
                scopes=consent_request.scopes,
                additional_context={
                    "error": str(e),
                    "exception_type": type(e).__name__
                }
            )
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
            # Get existing consent for audit logging
            existing_consent = await oauth2_db.get_user_consent(user_id, client_id)
            if not existing_consent or not existing_consent.is_active:
                logger.warning(f"Attempted to revoke non-existent or inactive consent: client {client_id}, user {user_id}")
                await self._log_consent_audit_event(
                    event_type="consent_revocation_failed",
                    user_id=user_id,
                    client_id=client_id,
                    scopes=[],
                    additional_context={
                        "failure_reason": "consent_not_found_or_inactive"
                    }
                )
                return False
            
            # Get client info for audit logging
            client = await oauth2_db.get_client(client_id)
            client_name = client.name if client else "Unknown Client"
            
            # Revoke consent in database
            success = await oauth2_db.revoke_user_consent(user_id, client_id)
            
            if success:
                # Also revoke all refresh tokens for this user-client pair
                revoked_tokens = 0
                try:
                    from .token_manager import token_manager
                    revoked_tokens = await token_manager.revoke_all_user_tokens(user_id, client_id)
                    logger.info(f"Revoked consent and {revoked_tokens} tokens for client {client_id}, user {user_id}")
                except Exception as e:
                    logger.warning(f"Failed to revoke tokens after consent revocation: {e}")
                    # Don't fail the consent revocation if token revocation fails
                
                logger.info(f"Revoked consent for client {client_id}, user {user_id}")
                
                # Log successful consent revocation for audit trail
                await self._log_consent_audit_event(
                    event_type="consent_revoked",
                    user_id=user_id,
                    client_id=client_id,
                    scopes=existing_consent.scopes,
                    additional_context={
                        "client_name": client_name,
                        "revoked_tokens_count": revoked_tokens,
                        "original_grant_date": existing_consent.granted_at.isoformat(),
                        "last_used_at": existing_consent.last_used_at.isoformat() if existing_consent.last_used_at else None,
                        "revocation_timestamp": datetime.utcnow().isoformat()
                    }
                )
            else:
                await self._log_consent_audit_event(
                    event_type="consent_revocation_failed",
                    user_id=user_id,
                    client_id=client_id,
                    scopes=existing_consent.scopes,
                    additional_context={
                        "failure_reason": "database_error",
                        "client_name": client_name
                    }
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to revoke consent for client {client_id}: {e}")
            await self._log_consent_audit_event(
                event_type="consent_revocation_error",
                user_id=user_id,
                client_id=client_id,
                scopes=[],
                additional_context={
                    "error": str(e),
                    "exception_type": type(e).__name__
                }
            )
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
    
    async def _log_consent_audit_event(
        self,
        event_type: str,
        user_id: str,
        client_id: str,
        scopes: List[str],
        additional_context: Optional[Dict] = None
    ) -> None:
        """
        Log consent audit events for comprehensive tracking.
        
        Args:
            event_type: Type of consent event
            user_id: User identifier
            client_id: Client identifier
            scopes: Scopes involved in the event
            additional_context: Additional context information
        """
        try:
            # Import here to avoid circular imports
            from ..logging_utils import oauth2_logger, OAuth2EventType
            
            # Map event types to OAuth2EventType enum
            event_type_mapping = {
                "consent_granted": OAuth2EventType.CONSENT_GRANTED,
                "consent_updated": OAuth2EventType.CONSENT_GRANTED,  # Use same type for updates
                "consent_denied": OAuth2EventType.CONSENT_DENIED,
                "consent_revoked": OAuth2EventType.CONSENT_REVOKED,
                "consent_grant_failed": OAuth2EventType.VALIDATION_ERROR,
                "consent_grant_error": OAuth2EventType.SYSTEM_ERROR,
                "consent_revocation_failed": OAuth2EventType.VALIDATION_ERROR,
                "consent_revocation_error": OAuth2EventType.SYSTEM_ERROR
            }
            
            oauth2_event_type = event_type_mapping.get(event_type, OAuth2EventType.SYSTEM_ERROR)
            
            # Log the consent event
            oauth2_logger.log_consent_event(
                event_type=oauth2_event_type,
                client_id=client_id,
                user_id=user_id,
                scopes=scopes,
                additional_context={
                    "consent_event_subtype": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    **(additional_context or {})
                }
            )
            
            # Also log to the general audit trail for critical events
            if event_type in ["consent_granted", "consent_revoked", "consent_updated"]:
                logger.info(
                    f"AUDIT: Consent {event_type} - User: {user_id}, Client: {client_id}, Scopes: {scopes}",
                    extra={
                        "audit_event": True,
                        "event_type": event_type,
                        "user_id": user_id,
                        "client_id": client_id,
                        "scopes": scopes,
                        "additional_context": additional_context
                    }
                )
            
        except Exception as e:
            logger.error(f"Failed to log consent audit event: {e}")
            # Don't raise exception to avoid breaking the main flow


# Global instance
consent_manager = ConsentManager()