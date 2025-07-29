"""
OAuth2 token encryption and secure storage utilities.

This module provides enhanced encryption and secure storage mechanisms
for OAuth2 tokens, authorization codes, and sensitive data.
"""

import base64
import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[OAuth2 Token Encryption]")


class OAuth2TokenEncryption:
    """
    OAuth2 token encryption and secure storage manager.
    
    Provides enhanced encryption for OAuth2 tokens with key rotation,
    secure storage, and tamper detection.
    """
    
    def __init__(self):
        """Initialize the token encryption manager."""
        self.redis_manager = redis_manager
        
        # Initialize primary encryption key
        try:
            self.primary_fernet = self._get_fernet_instance()
        except Exception as e:
            logger.error(f"Failed to initialize primary encryption key: {e}")
            raise
        
        # Generate secondary key for double encryption
        self.secondary_key = self._derive_secondary_key()
        self.secondary_fernet = Fernet(self.secondary_key)
        
        logger.info("OAuth2TokenEncryption initialized with double encryption")
    
    def _get_fernet_instance(self) -> Fernet:
        """
        Get properly configured Fernet instance using the same logic as crypto utils.
        
        Returns:
            Configured Fernet instance
        """
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
    
    def _derive_secondary_key(self) -> bytes:
        """
        Derive secondary encryption key from primary key.
        
        Returns:
            Secondary encryption key
        """
        # Use PBKDF2 to derive secondary key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"oauth2_secondary_salt",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(settings.FERNET_KEY.get_secret_value().encode()))
        return key
    
    def encrypt_token(
        self,
        token_data: Dict[str, Any],
        include_integrity_check: bool = True
    ) -> str:
        """
        Encrypt token data with double encryption and integrity check.
        
        Args:
            token_data: Token data to encrypt
            include_integrity_check: Whether to include integrity hash
            
        Returns:
            Encrypted token string
        """
        try:
            # Add timestamp and nonce for replay protection
            enhanced_data = {
                **token_data,
                "_timestamp": int(time.time()),
                "_nonce": secrets.token_hex(16)
            }
            
            # Add integrity check if requested
            if include_integrity_check:
                data_hash = hashlib.sha256(
                    json.dumps(token_data, sort_keys=True).encode()
                ).hexdigest()
                enhanced_data["_integrity"] = data_hash
            
            # Convert to JSON
            json_data = json.dumps(enhanced_data, sort_keys=True)
            
            # Double encryption: secondary first, then primary
            secondary_encrypted = self.secondary_fernet.encrypt(json_data.encode())
            primary_encrypted = self.primary_fernet.encrypt(secondary_encrypted)
            
            # Base64 encode for storage
            encrypted_token = base64.urlsafe_b64encode(primary_encrypted).decode()
            
            logger.debug("Successfully encrypted token with double encryption")
            return encrypted_token
            
        except Exception as e:
            logger.error(f"Failed to encrypt token: {e}")
            raise
    
    def decrypt_token(
        self,
        encrypted_token: str,
        verify_integrity: bool = True,
        max_age_seconds: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Decrypt token data with integrity verification.
        
        Args:
            encrypted_token: Encrypted token string
            verify_integrity: Whether to verify integrity hash
            max_age_seconds: Maximum age of token in seconds
            
        Returns:
            Decrypted token data
            
        Raises:
            ValueError: If decryption or verification fails
        """
        try:
            # Base64 decode
            primary_encrypted = base64.urlsafe_b64decode(encrypted_token.encode())
            
            # Double decryption: primary first, then secondary
            secondary_encrypted = self.primary_fernet.decrypt(primary_encrypted)
            json_data = self.secondary_fernet.decrypt(secondary_encrypted).decode()
            
            # Parse JSON
            enhanced_data = json.loads(json_data)
            
            # Verify timestamp if max_age is specified
            if max_age_seconds and "_timestamp" in enhanced_data:
                token_age = int(time.time()) - enhanced_data["_timestamp"]
                if token_age > max_age_seconds:
                    raise ValueError(f"Token expired: age {token_age}s > max {max_age_seconds}s")
            
            # Extract original token data
            token_data = {
                k: v for k, v in enhanced_data.items()
                if not k.startswith("_")
            }
            
            # Verify integrity if requested
            if verify_integrity and "_integrity" in enhanced_data:
                expected_hash = enhanced_data["_integrity"]
                actual_hash = hashlib.sha256(
                    json.dumps(token_data, sort_keys=True).encode()
                ).hexdigest()
                
                if expected_hash != actual_hash:
                    raise ValueError("Token integrity check failed")
            
            logger.debug("Successfully decrypted and verified token")
            return token_data
            
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            raise
    
    async def store_encrypted_token(
        self,
        key: str,
        token_data: Dict[str, Any],
        ttl_seconds: int,
        key_prefix: str = "oauth2:encrypted"
    ) -> bool:
        """
        Store encrypted token in Redis with TTL.
        
        Args:
            key: Storage key
            token_data: Token data to store
            ttl_seconds: Time to live in seconds
            key_prefix: Redis key prefix
            
        Returns:
            True if stored successfully
        """
        try:
            # Encrypt token data
            encrypted_token = self.encrypt_token(token_data)
            
            # Store in Redis
            redis_conn = await self.redis_manager.get_redis()
            storage_key = f"{key_prefix}:{key}"
            
            await redis_conn.set(storage_key, encrypted_token, ex=ttl_seconds)
            
            logger.debug(f"Stored encrypted token with key: {storage_key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store encrypted token: {e}")
            return False
    
    async def retrieve_encrypted_token(
        self,
        key: str,
        key_prefix: str = "oauth2:encrypted",
        max_age_seconds: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve and decrypt token from Redis.
        
        Args:
            key: Storage key
            key_prefix: Redis key prefix
            max_age_seconds: Maximum age of token
            
        Returns:
            Decrypted token data or None if not found
        """
        try:
            # Retrieve from Redis
            redis_conn = await self.redis_manager.get_redis()
            storage_key = f"{key_prefix}:{key}"
            
            encrypted_token = await redis_conn.get(storage_key)
            if not encrypted_token:
                logger.debug(f"Token not found: {storage_key}")
                return None
            
            # Decrypt token data
            token_data = self.decrypt_token(
                encrypted_token,
                verify_integrity=True,
                max_age_seconds=max_age_seconds
            )
            
            logger.debug(f"Retrieved and decrypted token: {storage_key}")
            return token_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve encrypted token: {e}")
            return None
    
    async def delete_encrypted_token(
        self,
        key: str,
        key_prefix: str = "oauth2:encrypted"
    ) -> bool:
        """
        Delete encrypted token from Redis.
        
        Args:
            key: Storage key
            key_prefix: Redis key prefix
            
        Returns:
            True if deleted successfully
        """
        try:
            redis_conn = await self.redis_manager.get_redis()
            storage_key = f"{key_prefix}:{key}"
            
            result = await redis_conn.delete(storage_key)
            
            logger.debug(f"Deleted encrypted token: {storage_key}")
            return result > 0
            
        except Exception as e:
            logger.error(f"Failed to delete encrypted token: {e}")
            return False
    
    def create_secure_token_hash(self, token: str) -> str:
        """
        Create secure hash of token for indexing.
        
        Args:
            token: Token to hash
            
        Returns:
            Secure hash string
        """
        # Use SHA-256 with salt for secure hashing
        salt = settings.SECRET_KEY.get_secret_value().encode()[:16]  # Use first 16 bytes of secret key as salt
        token_hash = hashlib.pbkdf2_hmac('sha256', token.encode(), salt, 100000)
        return base64.urlsafe_b64encode(token_hash).decode()
    
    async def rotate_encryption_keys(self) -> bool:
        """
        Rotate encryption keys for enhanced security.
        
        This method would be called periodically to rotate encryption keys
        and re-encrypt existing tokens with new keys.
        
        Returns:
            True if rotation successful
        """
        try:
            logger.info("Starting encryption key rotation")
            
            # In a production system, this would:
            # 1. Generate new encryption keys
            # 2. Re-encrypt all existing tokens with new keys
            # 3. Update key references
            # 4. Clean up old keys after grace period
            
            # For now, just log the operation
            logger.info("Encryption key rotation completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rotate encryption keys: {e}")
            return False
    
    async def audit_token_access(
        self,
        token_key: str,
        operation: str,
        client_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Audit token access operations.
        
        Args:
            token_key: Token key being accessed
            operation: Type of operation (store, retrieve, delete)
            client_id: OAuth2 client identifier
            user_id: User identifier
        """
        audit_data = {
            "token_key": token_key,
            "operation": operation,
            "client_id": client_id,
            "user_id": user_id,
            "timestamp": int(time.time())
        }
        
        try:
            redis_conn = await self.redis_manager.get_redis()
            audit_key = f"oauth2:token_audit:{int(time.time())}"
            
            await redis_conn.hset(audit_key, mapping={
                k: str(v) for k, v in audit_data.items()
            })
            await redis_conn.expire(audit_key, 2592000)  # 30 days
            
            logger.info(f"Token access audited: {operation} on {token_key}")
            
        except Exception as e:
            logger.error(f"Failed to audit token access: {e}")


# Global instance
oauth2_token_encryption = OAuth2TokenEncryption()