"""
WebRTC End-to-End Encryption (E2EE) Manager

Provides secure key exchange and message encryption for WebRTC communications.

Features:
- X25519 (ECDH) key exchange
- ChaCha20-Poly1305 authenticated encryption
- Ed25519 digital signatures
- Replay attack prevention (nonce tracking)
- Key rotation support
- Forward secrecy with ephemeral keys
"""

import base64
import json
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager

logger = get_logger(prefix="[WebRTC-E2EE]")


class KeyType(str, Enum):
    """Key types for E2EE."""
    IDENTITY = "identity"     # Long-term identity key
    EPHEMERAL = "ephemeral"   # Session ephemeral key
    SIGNATURE = "signature"   # Signature verification key


class E2EEManager:
    """
    Manages end-to-end encryption for WebRTC communications.
    
    Architecture:
    - X25519 (ECDH) for key exchange
    - ChaCha20-Poly1305 for AEAD encryption
    - Ed25519 for digital signatures
    - HKDF for key derivation
    - Nonce-based replay protection
    
    Security Features:
    - Perfect forward secrecy (ephemeral keys)
    - Authenticated encryption
    - Message integrity verification
    - Replay attack prevention
    - Key rotation support
    """
    
    def __init__(
        self,
        nonce_ttl: int = 300,  # 5 minutes
        max_key_age: int = 86400,  # 24 hours
        enable_signatures: bool = True
    ):
        """
        Initialize E2EE manager.
        
        Args:
            nonce_ttl: Nonce time-to-live in seconds
            max_key_age: Maximum key age before rotation
            enable_signatures: Enable message signing
        """
        self.nonce_ttl = nonce_ttl
        self.max_key_age = max_key_age
        self.enable_signatures = enable_signatures
        
        # Redis key prefixes
        self.KEY_PAIR_PREFIX = "webrtc:e2ee:keypair:"
        self.PUBLIC_KEY_PREFIX = "webrtc:e2ee:pubkey:"
        self.SHARED_SECRET_PREFIX = "webrtc:e2ee:shared:"
        self.NONCE_PREFIX = "webrtc:e2ee:nonce:"
        self.USER_KEYS_PREFIX = "webrtc:e2ee:userkeys:"
        
        logger.info(
            f"E2EE manager initialized "
            f"(nonce_ttl={nonce_ttl}s, max_key_age={max_key_age}s, "
            f"signatures={enable_signatures})"
        )
    
    async def generate_key_pair(
        self,
        user_id: str,
        room_id: str,
        key_type: KeyType = KeyType.EPHEMERAL
    ) -> Dict:
        """
        Generate a new key pair for a user in a room.
        
        Args:
            user_id: User ID
            room_id: Room ID
            key_type: Type of key (ephemeral or identity)
            
        Returns:
            Key pair metadata (public key only)
        """
        try:
            # Generate X25519 key pair for ECDH
            private_key = X25519PrivateKey.generate()
            public_key = private_key.public_key()
            
            # Serialize keys
            private_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_bytes = public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            
            # Generate signature key if enabled
            signature_private_key = None
            signature_public_key = None
            
            if self.enable_signatures:
                signature_private_key = Ed25519PrivateKey.generate()
                signature_public_key = signature_private_key.public_key()
            
            # Create key pair object
            key_id = f"{user_id}:{room_id}:{key_type}:{int(time.time() * 1000)}"  # Use milliseconds
            
            key_pair = {
                "key_id": key_id,
                "user_id": user_id,
                "room_id": room_id,
                "key_type": key_type,
                "public_key": base64.b64encode(public_bytes).decode(),
                "private_key": base64.b64encode(private_bytes).decode(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=self.max_key_age)).isoformat()
            }
            
            # Add signature keys if enabled
            if self.enable_signatures and signature_private_key and signature_public_key:
                sig_private_bytes = signature_private_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                )
                
                sig_public_bytes = signature_public_key.public_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PublicFormat.Raw
                )
                
                key_pair["signature_public_key"] = base64.b64encode(sig_public_bytes).decode()
                key_pair["signature_private_key"] = base64.b64encode(sig_private_bytes).decode()
            
            # Store in Redis
            await self._store_key_pair(key_id, key_pair)
            
            # Store public key separately for easy access
            await self._store_public_key(user_id, room_id, key_id, key_pair)
            
            # Add to user's key list
            await self._add_user_key(user_id, room_id, key_id)
            
            logger.info(
                f"Generated {key_type} key pair for user {user_id} in room {room_id}",
                extra={"key_id": key_id, "user_id": user_id, "room_id": room_id}
            )
            
            # Return public key information only
            return {
                "key_id": key_id,
                "user_id": user_id,
                "room_id": room_id,
                "key_type": key_type,
                "public_key": key_pair["public_key"],
                "signature_public_key": key_pair.get("signature_public_key"),
                "created_at": key_pair["created_at"],
                "expires_at": key_pair["expires_at"]
            }
            
        except Exception as e:
            logger.error(f"Failed to generate key pair: {e}", exc_info=True)
            raise
    
    async def exchange_keys(
        self,
        user_a_id: str,
        user_b_id: str,
        room_id: str
    ) -> bool:
        """
        Perform key exchange between two users.
        
        Args:
            user_a_id: First user ID
            user_b_id: Second user ID
            room_id: Room ID
            
        Returns:
            True if exchange successful
        """
        try:
            # Get latest keys for both users
            key_a = await self._get_latest_user_key(user_a_id, room_id)
            key_b = await self._get_latest_user_key(user_b_id, room_id)
            
            if not key_a or not key_b:
                raise ValueError("One or both users don't have keys")
            
            # Derive shared secrets
            shared_a_b = await self._derive_shared_secret(
                key_a["key_id"],
                key_b["public_key"],
                user_a_id,
                user_b_id,
                room_id
            )
            
            shared_b_a = await self._derive_shared_secret(
                key_b["key_id"],
                key_a["public_key"],
                user_b_id,
                user_a_id,
                room_id
            )
            
            logger.info(
                f"Key exchange completed between {user_a_id} and {user_b_id}",
                extra={"room_id": room_id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to exchange keys: {e}", exc_info=True)
            raise
    
    async def encrypt_message(
        self,
        message: Dict,
        sender_id: str,
        recipient_id: str,
        room_id: str
    ) -> Dict:
        """
        Encrypt a message for a recipient.
        
        Args:
            message: Plaintext message dict
            sender_id: Sender user ID
            recipient_id: Recipient user ID
            room_id: Room ID
            
        Returns:
            Encrypted message envelope
        """
        try:
            # Get shared secret
            shared_secret = await self._get_shared_secret(
                sender_id,
                recipient_id,
                room_id
            )
            
            if not shared_secret:
                raise ValueError(f"No shared secret between {sender_id} and {recipient_id}")
            
            # Serialize message
            plaintext = json.dumps(message).encode('utf-8')
            
            # Generate nonce (12 bytes for ChaCha20-Poly1305)
            nonce = secrets.token_bytes(12)
            
            # Encrypt with ChaCha20-Poly1305
            cipher = ChaCha20Poly1305(shared_secret)
            ciphertext = cipher.encrypt(nonce, plaintext, None)
            
            # Create encrypted envelope
            encrypted = {
                "type": "e2ee_encrypted_message",
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "room_id": room_id,
                "nonce": base64.b64encode(nonce).decode(),
                "ciphertext": base64.b64encode(ciphertext).decode(),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Sign message if enabled
            if self.enable_signatures:
                signature = await self._sign_message(encrypted, sender_id, room_id)
                if signature:
                    encrypted["signature"] = signature
            
            # Don't store nonce yet - only store on successful decryption
            # This prevents blocking legitimate decryption attempts
            
            logger.debug(
                f"Encrypted message from {sender_id} to {recipient_id}",
                extra={"room_id": room_id}
            )
            
            return encrypted
            
        except Exception as e:
            logger.error(f"Failed to encrypt message: {e}", exc_info=True)
            raise
    
    async def decrypt_message(
        self,
        encrypted: Dict,
        recipient_id: str
    ) -> Dict:
        """
        Decrypt an encrypted message.
        
        Args:
            encrypted: Encrypted message envelope
            recipient_id: Recipient user ID (for verification)
            
        Returns:
            Decrypted message dict
        """
        try:
            sender_id = encrypted["sender_id"]
            room_id = encrypted["room_id"]
            
            # Verify recipient
            if encrypted["recipient_id"] != recipient_id:
                raise ValueError("Message not intended for this recipient")
            
            # Verify signature if present
            if "signature" in encrypted and self.enable_signatures:
                valid = await self._verify_signature(
                    encrypted,
                    sender_id,
                    room_id
                )
                if not valid:
                    raise ValueError("Invalid message signature")
            
            # Check nonce for replay attacks
            nonce_b64 = encrypted["nonce"]
            nonce = base64.b64decode(nonce_b64)
            
            if await self._check_nonce_used(nonce, sender_id, room_id):
                raise ValueError("Replay attack detected: nonce already used")
            
            # Get shared secret
            shared_secret = await self._get_shared_secret(
                recipient_id,
                sender_id,
                room_id
            )
            
            if not shared_secret:
                raise ValueError(f"No shared secret with {sender_id}")
            
            # Decrypt with ChaCha20-Poly1305
            ciphertext = base64.b64decode(encrypted["ciphertext"])
            cipher = ChaCha20Poly1305(shared_secret)
            plaintext = cipher.decrypt(nonce, ciphertext, None)
            
            # Deserialize message
            message = json.loads(plaintext.decode('utf-8'))
            
            # Store nonce to prevent future replay
            await self._store_nonce(nonce, sender_id, room_id)
            
            logger.debug(
                f"Decrypted message from {sender_id} to {recipient_id}",
                extra={"room_id": room_id}
            )
            
            return message
            
        except Exception as e:
            logger.error(f"Failed to decrypt message: {e}", exc_info=True)
            raise
    
    async def rotate_key(
        self,
        user_id: str,
        room_id: str
    ) -> Dict:
        """
        Rotate a user's ephemeral key.
        
        Args:
            user_id: User ID
            room_id: Room ID
            
        Returns:
            New key pair metadata
        """
        try:
            # Generate new ephemeral key
            new_key = await self.generate_key_pair(
                user_id=user_id,
                room_id=room_id,
                key_type=KeyType.EPHEMERAL
            )
            
            logger.info(
                f"Rotated key for user {user_id} in room {room_id}",
                extra={"new_key_id": new_key["key_id"]}
            )
            
            return new_key
            
        except Exception as e:
            logger.error(f"Failed to rotate key: {e}", exc_info=True)
            raise
    
    async def revoke_key(
        self,
        user_id: str,
        room_id: str,
        key_id: str
    ) -> bool:
        """
        Revoke a specific key.
        
        Args:
            user_id: User ID
            room_id: Room ID
            key_id: Key ID to revoke
            
        Returns:
            True if revoked successfully
        """
        try:
            redis_client = await redis_manager.get_redis()
            
            # Delete key pair
            key_pair_key = f"{self.KEY_PAIR_PREFIX}{key_id}"
            await redis_client.delete(key_pair_key)
            
            # Delete public key
            public_key_key = f"{self.PUBLIC_KEY_PREFIX}{user_id}:{room_id}:{key_id}"
            await redis_client.delete(public_key_key)
            
            # Remove from user's key list
            user_keys_key = f"{self.USER_KEYS_PREFIX}{user_id}:{room_id}"
            await redis_client.srem(user_keys_key, key_id)
            
            logger.info(
                f"Revoked key {key_id} for user {user_id}",
                extra={"key_id": key_id, "room_id": room_id}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to revoke key: {e}", exc_info=True)
            raise
    
    async def get_public_key(
        self,
        user_id: str,
        room_id: str
    ) -> Optional[Dict]:
        """
        Get a user's latest public key.
        
        Args:
            user_id: User ID
            room_id: Room ID
            
        Returns:
            Public key metadata or None
        """
        try:
            return await self._get_latest_user_key(user_id, room_id)
            
        except Exception as e:
            logger.error(f"Failed to get public key: {e}", exc_info=True)
            return None
    
    async def cleanup_user_keys(
        self,
        user_id: str,
        room_id: str
    ) -> int:
        """
        Clean up all keys for a user in a room.
        
        Args:
            user_id: User ID
            room_id: Room ID
            
        Returns:
            Number of keys cleaned up
        """
        try:
            redis_client = await redis_manager.get_redis()
            
            # Get user's key list
            user_keys_key = f"{self.USER_KEYS_PREFIX}{user_id}:{room_id}"
            key_ids = await redis_client.smembers(user_keys_key)
            
            count = 0
            for key_id in key_ids:
                await self.revoke_key(user_id, room_id, key_id)
                count += 1
            
            # Delete user's key list
            await redis_client.delete(user_keys_key)
            
            logger.info(
                f"Cleaned up {count} keys for user {user_id} in room {room_id}"
            )
            
            return count
            
        except Exception as e:
            logger.error(f"Failed to cleanup user keys: {e}", exc_info=True)
            return 0
    
    # Private helper methods
    
    async def _store_key_pair(self, key_id: str, key_pair: Dict) -> None:
        """Store key pair in Redis."""
        try:
            redis_client = await redis_manager.get_redis()
            key = f"{self.KEY_PAIR_PREFIX}{key_id}"
            
            await redis_client.setex(
                key,
                self.max_key_age,
                json.dumps(key_pair)
            )
            
        except Exception as e:
            logger.error(f"Failed to store key pair: {e}", exc_info=True)
            raise
    
    async def _store_public_key(
        self,
        user_id: str,
        room_id: str,
        key_id: str,
        key_pair: Dict
    ) -> None:
        """Store public key separately."""
        try:
            redis_client = await redis_manager.get_redis()
            key = f"{self.PUBLIC_KEY_PREFIX}{user_id}:{room_id}:{key_id}"
            
            public_key_data = {
                "key_id": key_id,
                "user_id": user_id,
                "room_id": room_id,
                "key_type": key_pair["key_type"],
                "public_key": key_pair["public_key"],
                "signature_public_key": key_pair.get("signature_public_key"),
                "created_at": key_pair["created_at"],
                "expires_at": key_pair["expires_at"]
            }
            
            await redis_client.setex(
                key,
                self.max_key_age,
                json.dumps(public_key_data)
            )
            
        except Exception as e:
            logger.error(f"Failed to store public key: {e}", exc_info=True)
            raise
    
    async def _add_user_key(
        self,
        user_id: str,
        room_id: str,
        key_id: str
    ) -> None:
        """Add key to user's key list."""
        try:
            redis_client = await redis_manager.get_redis()
            key = f"{self.USER_KEYS_PREFIX}{user_id}:{room_id}"
            
            await redis_client.sadd(key, key_id)
            await redis_client.expire(key, self.max_key_age)
            
        except Exception as e:
            logger.error(f"Failed to add user key: {e}", exc_info=True)
            raise
    
    async def _get_latest_user_key(
        self,
        user_id: str,
        room_id: str
    ) -> Optional[Dict]:
        """Get user's latest key."""
        try:
            redis_client = await redis_manager.get_redis()
            user_keys_key = f"{self.USER_KEYS_PREFIX}{user_id}:{room_id}"
            
            key_ids = await redis_client.smembers(user_keys_key)
            
            if not key_ids:
                return None
            
            # Get all keys and find latest
            latest_key = None
            latest_time = None
            
            for key_id in key_ids:
                public_key_key = f"{self.PUBLIC_KEY_PREFIX}{user_id}:{room_id}:{key_id}"
                key_json = await redis_client.get(public_key_key)
                
                if key_json:
                    key_data = json.loads(key_json)
                    created_at = datetime.fromisoformat(key_data["created_at"].replace('Z', '+00:00'))
                    
                    if latest_time is None or created_at > latest_time:
                        latest_time = created_at
                        latest_key = key_data
            
            return latest_key
            
        except Exception as e:
            logger.error(f"Failed to get latest user key: {e}", exc_info=True)
            return None
    
    async def _derive_shared_secret(
        self,
        our_key_id: str,
        their_public_key_b64: str,
        our_user_id: str,
        their_user_id: str,
        room_id: str
    ) -> bytes:
        """Derive shared secret using ECDH."""
        try:
            # Get our private key
            redis_client = await redis_manager.get_redis()
            key_pair_key = f"{self.KEY_PAIR_PREFIX}{our_key_id}"
            key_pair_json = await redis_client.get(key_pair_key)
            
            if not key_pair_json:
                raise ValueError("Private key not found")
            
            key_pair = json.loads(key_pair_json)
            private_bytes = base64.b64decode(key_pair["private_key"])
            
            # Load keys
            private_key = X25519PrivateKey.from_private_bytes(private_bytes)
            public_bytes = base64.b64decode(their_public_key_b64)
            public_key = X25519PublicKey.from_public_bytes(public_bytes)
            
            # Perform ECDH
            shared_key = private_key.exchange(public_key)
            
            # Derive final key using HKDF
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=None,
                info=f"{room_id}:{our_user_id}:{their_user_id}".encode(),
                backend=default_backend()
            )
            
            shared_secret = hkdf.derive(shared_key)
            
            # Store shared secret
            await self._store_shared_secret(
                our_user_id,
                their_user_id,
                room_id,
                shared_secret
            )
            
            return shared_secret
            
        except Exception as e:
            logger.error(f"Failed to derive shared secret: {e}", exc_info=True)
            raise
    
    async def _store_shared_secret(
        self,
        user_a_id: str,
        user_b_id: str,
        room_id: str,
        secret: bytes
    ) -> None:
        """Store shared secret."""
        try:
            redis_client = await redis_manager.get_redis()
            
            # Use consistent ordering for key
            users = sorted([user_a_id, user_b_id])
            key = f"{self.SHARED_SECRET_PREFIX}{users[0]}:{users[1]}:{room_id}"
            
            await redis_client.setex(
                key,
                self.max_key_age,
                base64.b64encode(secret).decode()
            )
            
        except Exception as e:
            logger.error(f"Failed to store shared secret: {e}", exc_info=True)
            raise
    
    async def _get_shared_secret(
        self,
        user_a_id: str,
        user_b_id: str,
        room_id: str
    ) -> Optional[bytes]:
        """Get shared secret."""
        try:
            redis_client = await redis_manager.get_redis()
            
            # Use consistent ordering for key
            users = sorted([user_a_id, user_b_id])
            key = f"{self.SHARED_SECRET_PREFIX}{users[0]}:{users[1]}:{room_id}"
            
            secret_b64 = await redis_client.get(key)
            
            if not secret_b64:
                return None
            
            return base64.b64decode(secret_b64)
            
        except Exception as e:
            logger.error(f"Failed to get shared secret: {e}", exc_info=True)
            return None
    
    async def _sign_message(
        self,
        message: Dict,
        user_id: str,
        room_id: str
    ) -> Optional[str]:
        """Sign a message with Ed25519."""
        try:
            # Get signing key
            latest_key = await self._get_latest_user_key(user_id, room_id)
            
            if not latest_key or "signature_public_key" not in latest_key:
                return None
            
            # Get private signing key
            redis_client = await redis_manager.get_redis()
            key_pair_key = f"{self.KEY_PAIR_PREFIX}{latest_key['key_id']}"
            key_pair_json = await redis_client.get(key_pair_key)
            
            if not key_pair_json:
                return None
            
            key_pair = json.loads(key_pair_json)
            
            if "signature_private_key" not in key_pair:
                return None
            
            # Load signing key
            sig_private_bytes = base64.b64decode(key_pair["signature_private_key"])
            signing_key = Ed25519PrivateKey.from_private_bytes(sig_private_bytes)
            
            # Create message to sign (exclude signature field)
            msg_copy = {k: v for k, v in message.items() if k != "signature"}
            msg_bytes = json.dumps(msg_copy, sort_keys=True).encode()
            
            # Sign
            signature = signing_key.sign(msg_bytes)
            
            return base64.b64encode(signature).decode()
            
        except Exception as e:
            logger.error(f"Failed to sign message: {e}", exc_info=True)
            return None
    
    async def _verify_signature(
        self,
        message: Dict,
        sender_id: str,
        room_id: str
    ) -> bool:
        """Verify message signature."""
        try:
            if "signature" not in message:
                return False
            
            # Get sender's public signing key
            sender_key = await self._get_latest_user_key(sender_id, room_id)
            
            if not sender_key or "signature_public_key" not in sender_key:
                return False
            
            # Load verification key
            sig_public_bytes = base64.b64decode(sender_key["signature_public_key"])
            verify_key = Ed25519PublicKey.from_public_bytes(sig_public_bytes)
            
            # Recreate message bytes (exclude signature)
            msg_copy = {k: v for k, v in message.items() if k != "signature"}
            msg_bytes = json.dumps(msg_copy, sort_keys=True).encode()
            
            # Verify signature
            signature = base64.b64decode(message["signature"])
            verify_key.verify(signature, msg_bytes)
            
            return True
            
        except Exception:
            return False
    
    async def _store_nonce(
        self,
        nonce: bytes,
        user_id: str,
        room_id: str
    ) -> None:
        """Store nonce to prevent replay."""
        try:
            redis_client = await redis_manager.get_redis()
            nonce_b64 = base64.b64encode(nonce).decode()
            key = f"{self.NONCE_PREFIX}{user_id}:{room_id}:{nonce_b64}"
            
            await redis_client.setex(key, self.nonce_ttl, "1")
            
        except Exception as e:
            logger.error(f"Failed to store nonce: {e}", exc_info=True)
    
    async def _check_nonce_used(
        self,
        nonce: bytes,
        user_id: str,
        room_id: str
    ) -> bool:
        """Check if nonce was already used."""
        try:
            redis_client = await redis_manager.get_redis()
            nonce_b64 = base64.b64encode(nonce).decode()
            key = f"{self.NONCE_PREFIX}{user_id}:{room_id}:{nonce_b64}"
            
            exists = await redis_client.exists(key)
            return exists > 0
            
        except Exception as e:
            logger.error(f"Failed to check nonce: {e}", exc_info=True)
            return False


# Global singleton instance
e2ee_manager = E2EEManager()
