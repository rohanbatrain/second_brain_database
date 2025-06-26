"""
Cryptographic utilities for secure data storage.
Provides encryption/decryption for sensitive data like TOTP secrets.
"""
import base64
import hashlib
from cryptography.fernet import Fernet
from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

def _get_encryption_key() -> bytes:
    """
    Use the FERNET_KEY from settings for Fernet encryption.
    If the key is not already base64-encoded, encode it.
    """
    key_raw = settings.FERNET_KEY.get_secret_value() if hasattr(settings.FERNET_KEY, "get_secret_value") else settings.FERNET_KEY
    key_material = key_raw.encode('utf-8')
    # Fernet requires a 32-byte base64-encoded key
    try:
        # Try to decode as base64; if it fails, hash and encode
        decoded = base64.urlsafe_b64decode(key_material)
        if len(decoded) == 32:
            return key_material
    except (base64.binascii.Error, ValueError):
        pass
    # If not valid, hash and encode
    hashed_key = hashlib.sha256(key_material).digest()
    return base64.urlsafe_b64encode(hashed_key)

def encrypt_totp_secret(secret: str) -> str:
    """
    Encrypt a TOTP secret for secure database storage.
    
    Args:
        secret: The plaintext TOTP secret (base32 string)
        
    Returns:
        Encrypted secret as a base64-encoded string
    """
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted_secret = f.encrypt(secret.encode('utf-8'))
        return base64.urlsafe_b64encode(encrypted_secret).decode('utf-8')
    except Exception as e:
        logger.error("Failed to encrypt TOTP secret: %s", e)
        raise RuntimeError("Encryption failed") from e

def decrypt_totp_secret(encrypted_secret: str) -> str:
    """
    Decrypt a TOTP secret from database storage.
    
    Args:
        encrypted_secret: The encrypted secret as a base64-encoded string
        
    Returns:
        Decrypted TOTP secret (base32 string)
    """
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        encrypted_data = base64.urlsafe_b64decode(encrypted_secret.encode('utf-8'))
        decrypted_secret = f.decrypt(encrypted_data)
        return decrypted_secret.decode('utf-8')
    except Exception as e:
        logger.error("Failed to decrypt TOTP secret: %s", e)
        raise RuntimeError("Decryption failed") from e

def is_encrypted_totp_secret(secret: str) -> bool:
    """
    Check if a TOTP secret is encrypted (for migration purposes).
    
    Args:
        secret: The secret to check
        
    Returns:
        True if the secret appears to be encrypted, False if plaintext
    """
    try:
        # Try to decode as base64 and decrypt
        # If it succeeds without errors, it's likely encrypted
        decrypt_totp_secret(secret)
        return True
    except (RuntimeError, ValueError) as e:
        logger.debug("is_encrypted_totp_secret: decryption failed, treating as plaintext. Error: %s", e)
        return False

def migrate_plaintext_secret(plaintext_secret: str) -> str:
    """
    Migrate a plaintext TOTP secret to encrypted format.
    This is used during the migration process.
    
    Args:
        plaintext_secret: The plaintext TOTP secret
        
    Returns:
        Encrypted secret
    """
    if is_encrypted_totp_secret(plaintext_secret):
        logger.warning("Secret is already encrypted, skipping migration")
        return plaintext_secret
    
    logger.info("Migrating plaintext TOTP secret to encrypted format")
    return encrypt_totp_secret(plaintext_secret)
