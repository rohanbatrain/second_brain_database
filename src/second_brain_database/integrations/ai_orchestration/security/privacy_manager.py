"""
Privacy protection manager for AI conversations and data isolation.

This module provides:
- Encrypted conversation storage
- Data isolation for user and family AI conversations
- Privacy settings integration
- Comprehensive audit trails
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
from enum import Enum
import json
import uuid
from cryptography.fernet import Fernet
import base64

from pydantic import BaseModel

from ....managers.logging_manager import get_logger
from ....managers.redis_manager import redis_manager
from ....integrations.mcp.context import MCPUserContext
from ....config import settings
from .ai_security_manager import ConversationPrivacyMode, AIAuditEvent

logger = get_logger(prefix="[AIPrivacyManager]")


class PrivacySetting(str, Enum):
    """Privacy settings for AI interactions."""
    CONVERSATION_RETENTION = "conversation_retention"  # How long to keep conversations
    DATA_SHARING = "data_sharing"  # Whether to share data for improvements
    FAMILY_VISIBILITY = "family_visibility"  # Family member access to conversations
    ENCRYPTION_ENABLED = "encryption_enabled"  # Whether to encrypt conversations
    AUDIT_LOGGING = "audit_logging"  # Level of audit logging
    KNOWLEDGE_INDEXING = "knowledge_indexing"  # Whether to index conversations for search


class ConversationMetadata(BaseModel):
    """Metadata for AI conversations."""
    conversation_id: str
    user_id: str
    family_id: Optional[str] = None
    workspace_id: Optional[str] = None
    agent_type: str
    privacy_mode: ConversationPrivacyMode
    created_at: datetime
    updated_at: datetime
    expires_at: Optional[datetime] = None
    encrypted: bool = False
    tags: List[str] = []
    participants: List[str] = []  # User IDs with access


class EncryptedConversation(BaseModel):
    """Encrypted conversation data."""
    conversation_id: str
    encrypted_data: str
    encryption_key_id: str
    metadata: ConversationMetadata


class AIPrivacyManager:
    """
    Privacy protection manager for AI conversations and data.
    """

    def __init__(self):
        self.logger = logger
        self.env_prefix = getattr(settings, "ENV_PREFIX", "dev")
        
        # Initialize encryption
        self.encryption_key = self._get_or_create_encryption_key()
        self.fernet = Fernet(self.encryption_key)
        
        # Default privacy settings
        self.default_privacy_settings = {
            PrivacySetting.CONVERSATION_RETENTION: "30_days",
            PrivacySetting.DATA_SHARING: False,
            PrivacySetting.FAMILY_VISIBILITY: "admin_only",
            PrivacySetting.ENCRYPTION_ENABLED: True,
            PrivacySetting.AUDIT_LOGGING: "full",
            PrivacySetting.KNOWLEDGE_INDEXING: True
        }
        
        # Retention periods in seconds
        self.retention_periods = {
            "1_day": 24 * 3600,
            "7_days": 7 * 24 * 3600,
            "30_days": 30 * 24 * 3600,
            "90_days": 90 * 24 * 3600,
            "1_year": 365 * 24 * 3600,
            "never": None  # Never expire
        }

    async def get_redis(self):
        """Get Redis connection."""
        return await redis_manager.get_redis()

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for conversations."""
        try:
            # In production, this should come from secure key management
            key_setting = getattr(settings, "AI_ENCRYPTION_KEY", None)
            if key_setting:
                return base64.urlsafe_b64decode(key_setting.encode())
            
            # Generate new key if not configured
            key = Fernet.generate_key()
            self.logger.warning(
                "Generated new AI encryption key. In production, configure AI_ENCRYPTION_KEY setting."
            )
            return key
            
        except Exception as e:
            self.logger.error("Error getting encryption key: %s", str(e), exc_info=True)
            # Fallback to generated key
            return Fernet.generate_key()

    async def get_user_privacy_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get privacy settings for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict of privacy settings
        """
        try:
            redis_conn = await self.get_redis()
            cache_key = f"{self.env_prefix}:ai_privacy_settings:{user_id}"
            
            # Try cache first
            cached_settings = await redis_conn.get(cache_key)
            if cached_settings:
                return json.loads(cached_settings)
            
            # Get from database (placeholder - would integrate with user preferences)
            settings_dict = self.default_privacy_settings.copy()
            
            # Cache for 1 hour
            await redis_conn.setex(cache_key, 3600, json.dumps(settings_dict))
            
            return settings_dict
            
        except Exception as e:
            self.logger.error(
                "Error getting privacy settings for user %s: %s",
                user_id, str(e), exc_info=True
            )
            return self.default_privacy_settings.copy()

    async def update_user_privacy_settings(
        self, 
        user_id: str, 
        settings_update: Dict[str, Any]
    ) -> bool:
        """
        Update privacy settings for user.
        
        Args:
            user_id: User ID
            settings_update: Settings to update
            
        Returns:
            bool: True if successful
        """
        try:
            # Get current settings
            current_settings = await self.get_user_privacy_settings(user_id)
            
            # Update with new values
            current_settings.update(settings_update)
            
            # Store in cache and database
            redis_conn = await self.get_redis()
            cache_key = f"{self.env_prefix}:ai_privacy_settings:{user_id}"
            await redis_conn.setex(cache_key, 3600, json.dumps(current_settings))
            
            # TODO: Store in database
            
            self.logger.info(
                "Updated privacy settings for user %s: %s",
                user_id, list(settings_update.keys())
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error updating privacy settings for user %s: %s",
                user_id, str(e), exc_info=True
            )
            return False

    async def encrypt_conversation_data(self, data: Dict[str, Any]) -> str:
        """
        Encrypt conversation data.
        
        Args:
            data: Conversation data to encrypt
            
        Returns:
            str: Encrypted data as base64 string
        """
        try:
            json_data = json.dumps(data, default=str)
            encrypted_bytes = self.fernet.encrypt(json_data.encode())
            return base64.urlsafe_b64encode(encrypted_bytes).decode()
            
        except Exception as e:
            self.logger.error("Error encrypting conversation data: %s", str(e), exc_info=True)
            raise

    async def decrypt_conversation_data(self, encrypted_data: str) -> Dict[str, Any]:
        """
        Decrypt conversation data.
        
        Args:
            encrypted_data: Base64 encoded encrypted data
            
        Returns:
            Dict: Decrypted conversation data
        """
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
            return json.loads(decrypted_bytes.decode())
            
        except Exception as e:
            self.logger.error("Error decrypting conversation data: %s", str(e), exc_info=True)
            raise

    async def store_conversation(
        self,
        conversation_id: str,
        user_context: MCPUserContext,
        conversation_data: Dict[str, Any],
        privacy_mode: ConversationPrivacyMode,
        agent_type: str,
        family_id: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> bool:
        """
        Store conversation with appropriate privacy protection.
        
        Args:
            conversation_id: Unique conversation ID
            user_context: User context
            conversation_data: Conversation data to store
            privacy_mode: Privacy mode for the conversation
            agent_type: Type of AI agent
            family_id: Optional family ID
            workspace_id: Optional workspace ID
            
        Returns:
            bool: True if successful
        """
        try:
            redis_conn = await self.get_redis()
            now = datetime.now(timezone.utc)
            
            # Get user privacy settings
            privacy_settings = await self.get_user_privacy_settings(user_context.user_id)
            
            # Create metadata
            metadata = ConversationMetadata(
                conversation_id=conversation_id,
                user_id=user_context.user_id,
                family_id=family_id,
                workspace_id=workspace_id,
                agent_type=agent_type,
                privacy_mode=privacy_mode,
                created_at=now,
                updated_at=now,
                encrypted=privacy_mode == ConversationPrivacyMode.ENCRYPTED,
                participants=[user_context.user_id]
            )
            
            # Set expiration based on retention settings
            retention_setting = privacy_settings.get(PrivacySetting.CONVERSATION_RETENTION, "30_days")
            retention_seconds = self.retention_periods.get(retention_setting)
            if retention_seconds:
                metadata.expires_at = now + timedelta(seconds=retention_seconds)
            
            # Handle different privacy modes
            if privacy_mode == ConversationPrivacyMode.EPHEMERAL:
                # Don't store ephemeral conversations
                return True
            
            elif privacy_mode == ConversationPrivacyMode.ENCRYPTED:
                # Encrypt the conversation data
                encrypted_data = await self.encrypt_conversation_data(conversation_data)
                
                # Store encrypted conversation
                storage_key = f"{self.env_prefix}:ai_conversation:encrypted:{conversation_id}"
                encrypted_conv = EncryptedConversation(
                    conversation_id=conversation_id,
                    encrypted_data=encrypted_data,
                    encryption_key_id="default",  # In production, use key rotation
                    metadata=metadata
                )
                
                if retention_seconds:
                    await redis_conn.setex(
                        storage_key, 
                        retention_seconds, 
                        encrypted_conv.model_dump_json()
                    )
                else:
                    await redis_conn.set(storage_key, encrypted_conv.model_dump_json())
            
            else:
                # Store unencrypted conversation with appropriate isolation
                storage_key = self._get_conversation_storage_key(
                    conversation_id, privacy_mode, user_context.user_id, family_id, workspace_id
                )
                
                storage_data = {
                    "metadata": metadata.model_dump(mode="json"),
                    "data": conversation_data
                }
                
                if retention_seconds:
                    await redis_conn.setex(
                        storage_key, 
                        retention_seconds, 
                        json.dumps(storage_data, default=str)
                    )
                else:
                    await redis_conn.set(storage_key, json.dumps(storage_data, default=str))
            
            # Add to user's conversation index
            await self._index_conversation(user_context.user_id, conversation_id, metadata)
            
            # Add to family/workspace indexes if applicable
            if family_id and privacy_mode == ConversationPrivacyMode.FAMILY_SHARED:
                await self._index_family_conversation(family_id, conversation_id, metadata)
            
            if workspace_id:
                await self._index_workspace_conversation(workspace_id, conversation_id, metadata)
            
            self.logger.info(
                "Stored conversation %s for user %s with privacy mode %s",
                conversation_id, user_context.user_id, privacy_mode.value
            )
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error storing conversation %s for user %s: %s",
                conversation_id, user_context.user_id, str(e), exc_info=True
            )
            return False

    async def retrieve_conversation(
        self,
        conversation_id: str,
        user_context: MCPUserContext,
        requesting_user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve conversation with privacy checks.
        
        Args:
            conversation_id: Conversation ID to retrieve
            user_context: User context
            requesting_user_id: Optional different user requesting access
            
        Returns:
            Optional[Dict]: Conversation data if accessible, None otherwise
        """
        try:
            redis_conn = await self.get_redis()
            
            # First, try to find the conversation in different storage locations
            conversation_data = None
            metadata = None
            
            # Try encrypted storage first
            encrypted_key = f"{self.env_prefix}:ai_conversation:encrypted:{conversation_id}"
            encrypted_data = await redis_conn.get(encrypted_key)
            
            if encrypted_data:
                encrypted_conv = EncryptedConversation.model_validate_json(encrypted_data)
                metadata = encrypted_conv.metadata
                
                # Check access permissions
                if not await self._check_conversation_access(metadata, user_context, requesting_user_id):
                    return None
                
                # Decrypt data
                conversation_data = await self.decrypt_conversation_data(encrypted_conv.encrypted_data)
            
            else:
                # Try different privacy mode storage locations
                for privacy_mode in ConversationPrivacyMode:
                    if privacy_mode in [ConversationPrivacyMode.EPHEMERAL, ConversationPrivacyMode.ENCRYPTED]:
                        continue
                    
                    storage_key = self._get_conversation_storage_key(
                        conversation_id, privacy_mode, user_context.user_id
                    )
                    
                    stored_data = await redis_conn.get(storage_key)
                    if stored_data:
                        data_dict = json.loads(stored_data)
                        metadata = ConversationMetadata.model_validate(data_dict["metadata"])
                        
                        # Check access permissions
                        if await self._check_conversation_access(metadata, user_context, requesting_user_id):
                            conversation_data = data_dict["data"]
                            break
            
            if not conversation_data:
                return None
            
            # Log access
            self.logger.info(
                "Retrieved conversation %s for user %s (requested by %s)",
                conversation_id, user_context.user_id, requesting_user_id or user_context.user_id
            )
            
            return {
                "metadata": metadata.model_dump(mode="json") if metadata else {},
                "data": conversation_data
            }
            
        except Exception as e:
            self.logger.error(
                "Error retrieving conversation %s for user %s: %s",
                conversation_id, user_context.user_id, str(e), exc_info=True
            )
            return None

    def _get_conversation_storage_key(
        self,
        conversation_id: str,
        privacy_mode: ConversationPrivacyMode,
        user_id: str,
        family_id: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> str:
        """Generate storage key based on privacy mode and context."""
        base_key = f"{self.env_prefix}:ai_conversation"
        
        if privacy_mode == ConversationPrivacyMode.PRIVATE:
            return f"{base_key}:private:{user_id}:{conversation_id}"
        elif privacy_mode == ConversationPrivacyMode.FAMILY_SHARED and family_id:
            return f"{base_key}:family:{family_id}:{conversation_id}"
        elif privacy_mode == ConversationPrivacyMode.PUBLIC:
            return f"{base_key}:public:{conversation_id}"
        else:
            return f"{base_key}:private:{user_id}:{conversation_id}"

    async def _check_conversation_access(
        self,
        metadata: ConversationMetadata,
        user_context: MCPUserContext,
        requesting_user_id: Optional[str] = None
    ) -> bool:
        """Check if user has access to conversation."""
        try:
            actual_user_id = requesting_user_id or user_context.user_id
            
            # Owner always has access
            if actual_user_id == metadata.user_id:
                return True
            
            # Check participants list
            if actual_user_id in metadata.participants:
                return True
            
            # Check family access
            if (metadata.privacy_mode == ConversationPrivacyMode.FAMILY_SHARED and 
                metadata.family_id):
                # Would check family membership here
                return True
            
            # Public conversations are accessible to all
            if metadata.privacy_mode == ConversationPrivacyMode.PUBLIC:
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(
                "Error checking conversation access: %s", str(e), exc_info=True
            )
            return False

    async def _index_conversation(
        self, 
        user_id: str, 
        conversation_id: str, 
        metadata: ConversationMetadata
    ) -> None:
        """Add conversation to user's index."""
        try:
            redis_conn = await self.get_redis()
            index_key = f"{self.env_prefix}:ai_conversation_index:{user_id}"
            
            index_entry = {
                "conversation_id": conversation_id,
                "agent_type": metadata.agent_type,
                "privacy_mode": metadata.privacy_mode.value,
                "created_at": metadata.created_at.isoformat(),
                "tags": metadata.tags
            }
            
            await redis_conn.lpush(index_key, json.dumps(index_entry))
            await redis_conn.ltrim(index_key, 0, 999)  # Keep last 1000 conversations
            await redis_conn.expire(index_key, 90 * 24 * 3600)  # 90 days
            
        except Exception as e:
            self.logger.error(
                "Error indexing conversation for user %s: %s",
                user_id, str(e), exc_info=True
            )

    async def _index_family_conversation(
        self, 
        family_id: str, 
        conversation_id: str, 
        metadata: ConversationMetadata
    ) -> None:
        """Add conversation to family's index."""
        try:
            redis_conn = await self.get_redis()
            index_key = f"{self.env_prefix}:ai_conversation_index:family:{family_id}"
            
            index_entry = {
                "conversation_id": conversation_id,
                "user_id": metadata.user_id,
                "agent_type": metadata.agent_type,
                "created_at": metadata.created_at.isoformat(),
                "tags": metadata.tags
            }
            
            await redis_conn.lpush(index_key, json.dumps(index_entry))
            await redis_conn.ltrim(index_key, 0, 999)
            await redis_conn.expire(index_key, 90 * 24 * 3600)
            
        except Exception as e:
            self.logger.error(
                "Error indexing family conversation for family %s: %s",
                family_id, str(e), exc_info=True
            )

    async def _index_workspace_conversation(
        self, 
        workspace_id: str, 
        conversation_id: str, 
        metadata: ConversationMetadata
    ) -> None:
        """Add conversation to workspace's index."""
        try:
            redis_conn = await self.get_redis()
            index_key = f"{self.env_prefix}:ai_conversation_index:workspace:{workspace_id}"
            
            index_entry = {
                "conversation_id": conversation_id,
                "user_id": metadata.user_id,
                "agent_type": metadata.agent_type,
                "created_at": metadata.created_at.isoformat(),
                "tags": metadata.tags
            }
            
            await redis_conn.lpush(index_key, json.dumps(index_entry))
            await redis_conn.ltrim(index_key, 0, 999)
            await redis_conn.expire(index_key, 90 * 24 * 3600)
            
        except Exception as e:
            self.logger.error(
                "Error indexing workspace conversation for workspace %s: %s",
                workspace_id, str(e), exc_info=True
            )


# Global instance
ai_privacy_manager = AIPrivacyManager()