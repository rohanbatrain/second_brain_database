"""Cryptographic utilities for secure data storage.
Provides encryption/decryption for sensitive data like TOTP secrets.
"""

import base64
import hashlib
import time

from cryptography.fernet import Fernet

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.utils.logging_utils import SecurityLogger, log_error_with_context, log_security_event

logger = get_logger(prefix="[Crypto Utils]")
security_logger = SecurityLogger(prefix="[CRYPTO-SECURITY]")


def _get_encryption_key() -> bytes:
    """Use the FERNET_KEY from settings for Fernet encryption.
    If the key is not already base64-encoded, encode it.
    """
    start_time = time.time()
    logger.debug("Retrieving encryption key for cryptographic operations")

    try:
        # Log security event for key access
        log_security_event(
            event_type="encryption_key_access",
            success=True,
            details={"operation": "key_retrieval", "key_source": "settings"},
        )

        key_raw = (
            settings.FERNET_KEY.get_secret_value()
            if hasattr(settings.FERNET_KEY, "get_secret_value")
            else settings.FERNET_KEY
        )
        key_material = key_raw.encode("utf-8")

        # Fernet requires a 32-byte base64-encoded key
        try:
            # Try to decode as base64; if it fails, hash and encode
            decoded = base64.urlsafe_b64decode(key_material)
            if len(decoded) == 32:
                duration = time.time() - start_time
                logger.debug("Encryption key retrieved successfully in %.3fs (pre-encoded)", duration)
                return key_material
        except base64.binascii.Error as decode_error:
            logger.debug("Key not pre-encoded, will hash and encode: %s", decode_error)

        # If not valid, hash and encode
        logger.debug("Hashing and encoding encryption key material")
        hashed_key = hashlib.sha256(key_material).digest()
        encoded_key = base64.urlsafe_b64encode(hashed_key)

        duration = time.time() - start_time
        logger.debug("Encryption key processed successfully in %.3fs (hashed and encoded)", duration)

        return encoded_key

    except Exception as e:
        duration = time.time() - start_time
        error_context = {"operation": "encryption_key_retrieval", "duration": duration, "error_type": type(e).__name__}

        log_error_with_context(e, context=error_context, operation="get_encryption_key")
        log_security_event(
            event_type="encryption_key_access", success=False, details={"operation": "key_retrieval", "error": str(e)}
        )

        logger.error("Failed to retrieve encryption key after %.3fs: %s", duration, e)
        raise RuntimeError("Encryption key retrieval failed") from e


def encrypt_totp_secret(secret: str) -> str:
    """
    Encrypt a TOTP secret for secure database storage.

    Args:
        secret: The plaintext TOTP secret (base32 string)

    Returns:
        Encrypted secret as a base64-encoded string
    """
    start_time = time.time()
    operation_context = {
        "operation": "totp_secret_encryption",
        "secret_length": len(secret) if secret else 0,
        "secret_type": "base32_totp",
    }

    logger.info("Starting TOTP secret encryption - length: %d characters", len(secret) if secret else 0)

    # Log security event for encryption operation
    log_security_event(
        event_type="totp_encryption",
        success=True,
        details={
            "operation": "encrypt_totp_secret",
            "secret_length": len(secret) if secret else 0,
            "encryption_algorithm": "fernet",
        },
    )

    try:
        # Validate input
        if not secret:
            raise ValueError("Secret cannot be empty")

        if not isinstance(secret, str):
            raise TypeError("Secret must be a string")

        logger.debug("Input validation passed for TOTP secret encryption")

        # Get encryption key and perform encryption
        key = _get_encryption_key()
        f = Fernet(key)

        logger.debug("Performing Fernet encryption on TOTP secret")
        encrypted_secret = f.encrypt(secret.encode("utf-8"))

        # Encode result
        result = base64.urlsafe_b64encode(encrypted_secret).decode("utf-8")

        duration = time.time() - start_time
        logger.info("TOTP secret encryption completed successfully in %.3fs - output length: %d", duration, len(result))

        # Log performance metrics
        if duration > 0.1:  # Log if encryption takes more than 100ms
            logger.warning("SLOW ENCRYPTION: TOTP secret encryption took %.3fs", duration)

        # Log successful security event
        log_security_event(
            event_type="totp_encryption",
            success=True,
            details={"operation": "encrypt_totp_secret_completed", "duration": duration, "output_length": len(result)},
        )

        return result

    except Exception as e:
        duration = time.time() - start_time
        operation_context.update({"duration": duration, "error_type": type(e).__name__, "error_message": str(e)})

        log_error_with_context(e, context=operation_context, operation="encrypt_totp_secret")

        # Log security failure event
        log_security_event(
            event_type="totp_encryption",
            success=False,
            details={"operation": "encrypt_totp_secret_failed", "error": str(e), "duration": duration},
        )

        logger.error("Failed to encrypt TOTP secret after %.3fs: %s", duration, e)
        raise RuntimeError("Encryption failed") from e


def decrypt_totp_secret(encrypted_secret: str) -> str:
    """
    Decrypt a TOTP secret from database storage.

    Args:
        encrypted_secret: The encrypted secret as a base64-encoded string

    Returns:
        Decrypted TOTP secret (base32 string)
    """
    start_time = time.time()
    operation_context = {
        "operation": "totp_secret_decryption",
        "encrypted_length": len(encrypted_secret) if encrypted_secret else 0,
        "secret_type": "base32_totp",
    }

    logger.info(
        "Starting TOTP secret decryption - input length: %d characters",
        len(encrypted_secret) if encrypted_secret else 0,
    )

    # Log security event for decryption operation
    log_security_event(
        event_type="totp_decryption",
        success=True,
        details={
            "operation": "decrypt_totp_secret",
            "encrypted_length": len(encrypted_secret) if encrypted_secret else 0,
            "decryption_algorithm": "fernet",
        },
    )

    try:
        # Validate input
        if not encrypted_secret:
            raise ValueError("Encrypted secret cannot be empty")

        if not isinstance(encrypted_secret, str):
            raise TypeError("Encrypted secret must be a string")

        logger.debug("Input validation passed for TOTP secret decryption")

        # Get encryption key
        key = _get_encryption_key()
        f = Fernet(key)

        # Decode base64 data
        logger.debug("Decoding base64 encrypted data")
        try:
            encrypted_data = base64.urlsafe_b64decode(encrypted_secret.encode("utf-8"))
        except Exception as decode_error:
            logger.error("Failed to decode base64 encrypted data: %s", decode_error)
            raise ValueError("Invalid base64 encrypted data") from decode_error

        # Perform decryption
        logger.debug("Performing Fernet decryption on TOTP secret")
        decrypted_secret = f.decrypt(encrypted_data)
        result = decrypted_secret.decode("utf-8")

        duration = time.time() - start_time
        logger.info("TOTP secret decryption completed successfully in %.3fs - output length: %d", duration, len(result))

        # Log performance metrics
        if duration > 0.1:  # Log if decryption takes more than 100ms
            logger.warning("SLOW DECRYPTION: TOTP secret decryption took %.3fs", duration)

        # Log successful security event
        log_security_event(
            event_type="totp_decryption",
            success=True,
            details={"operation": "decrypt_totp_secret_completed", "duration": duration, "output_length": len(result)},
        )

        return result

    except Exception as e:
        duration = time.time() - start_time
        operation_context.update({"duration": duration, "error_type": type(e).__name__, "error_message": str(e)})

        log_error_with_context(e, context=operation_context, operation="decrypt_totp_secret")

        # Log security failure event
        log_security_event(
            event_type="totp_decryption",
            success=False,
            details={"operation": "decrypt_totp_secret_failed", "error": str(e), "duration": duration},
        )

        logger.error("Failed to decrypt TOTP secret after %.3fs: %s", duration, e)
        raise RuntimeError("Decryption failed") from e


def is_encrypted_totp_secret(secret: str) -> bool:
    """
    Check if a TOTP secret is encrypted (for migration purposes).

    Args:
        secret: The secret to check

    Returns:
        True if the secret appears to be encrypted, False if plaintext
    """
    start_time = time.time()
    operation_context = {
        "operation": "totp_secret_validation",
        "secret_length": len(secret) if secret else 0,
        "validation_type": "encryption_check",
    }

    logger.debug("Checking if TOTP secret is encrypted - length: %d characters", len(secret) if secret else 0)

    # Log security event for validation operation
    log_security_event(
        event_type="totp_validation",
        success=True,
        details={
            "operation": "is_encrypted_totp_secret",
            "secret_length": len(secret) if secret else 0,
            "validation_purpose": "migration_check",
        },
    )

    try:
        # Validate input
        if not secret:
            logger.debug("Empty secret provided, treating as plaintext")
            return False

        if not isinstance(secret, str):
            logger.debug("Non-string secret provided, treating as plaintext")
            return False

        # Try to decode as base64 and decrypt
        # If it succeeds without errors, it's likely encrypted
        logger.debug("Attempting decryption to validate encryption status")
        decrypt_totp_secret(secret)

        duration = time.time() - start_time
        logger.debug("Secret validation completed in %.3fs - determined to be encrypted", duration)

        # Log successful validation
        log_security_event(
            event_type="totp_validation",
            success=True,
            details={"operation": "is_encrypted_totp_secret_completed", "result": "encrypted", "duration": duration},
        )

        return True

    except (RuntimeError, ValueError) as e:
        duration = time.time() - start_time
        logger.debug(
            "is_encrypted_totp_secret: decryption failed in %.3fs, treating as plaintext. Error: %s", duration, e
        )

        # Log validation result (this is expected behavior, not an error)
        log_security_event(
            event_type="totp_validation",
            success=True,
            details={
                "operation": "is_encrypted_totp_secret_completed",
                "result": "plaintext",
                "duration": duration,
                "validation_method": "decryption_attempt",
            },
        )

        return False

    except Exception as e:
        duration = time.time() - start_time
        operation_context.update({"duration": duration, "error_type": type(e).__name__, "error_message": str(e)})

        log_error_with_context(e, context=operation_context, operation="is_encrypted_totp_secret")

        # Log unexpected error
        log_security_event(
            event_type="totp_validation",
            success=False,
            details={"operation": "is_encrypted_totp_secret_failed", "error": str(e), "duration": duration},
        )

        logger.error("Unexpected error during TOTP secret validation after %.3fs: %s", duration, e)
        # Default to plaintext on unexpected errors for safety
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
    start_time = time.time()
    operation_context = {
        "operation": "totp_secret_migration",
        "secret_length": len(plaintext_secret) if plaintext_secret else 0,
        "migration_type": "plaintext_to_encrypted",
    }

    logger.info(
        "Starting TOTP secret migration - length: %d characters", len(plaintext_secret) if plaintext_secret else 0
    )

    # Log security event for migration operation
    log_security_event(
        event_type="totp_migration",
        success=True,
        details={
            "operation": "migrate_plaintext_secret",
            "secret_length": len(plaintext_secret) if plaintext_secret else 0,
            "migration_purpose": "encryption_upgrade",
        },
    )

    try:
        # Validate input
        if not plaintext_secret:
            raise ValueError("Plaintext secret cannot be empty")

        if not isinstance(plaintext_secret, str):
            raise TypeError("Plaintext secret must be a string")

        logger.debug("Input validation passed for TOTP secret migration")

        # Check if secret is already encrypted
        logger.debug("Checking if secret is already encrypted before migration")
        if is_encrypted_totp_secret(plaintext_secret):
            duration = time.time() - start_time
            logger.warning("Secret is already encrypted, skipping migration - completed in %.3fs", duration)

            # Log security event for skipped migration
            log_security_event(
                event_type="totp_migration",
                success=True,
                details={
                    "operation": "migrate_plaintext_secret_skipped",
                    "reason": "already_encrypted",
                    "duration": duration,
                },
            )

            return plaintext_secret

        # Perform migration by encrypting the plaintext secret
        logger.info("Migrating plaintext TOTP secret to encrypted format")
        result = encrypt_totp_secret(plaintext_secret)

        duration = time.time() - start_time
        logger.info("TOTP secret migration completed successfully in %.3fs - output length: %d", duration, len(result))

        # Log performance metrics
        if duration > 0.2:  # Log if migration takes more than 200ms
            logger.warning("SLOW MIGRATION: TOTP secret migration took %.3fs", duration)

        # Log successful migration event
        log_security_event(
            event_type="totp_migration",
            success=True,
            details={
                "operation": "migrate_plaintext_secret_completed",
                "duration": duration,
                "output_length": len(result),
                "migration_status": "successful",
            },
        )

        return result

    except Exception as e:
        duration = time.time() - start_time
        operation_context.update({"duration": duration, "error_type": type(e).__name__, "error_message": str(e)})

        log_error_with_context(e, context=operation_context, operation="migrate_plaintext_secret")

        # Log security failure event
        log_security_event(
            event_type="totp_migration",
            success=False,
            details={"operation": "migrate_plaintext_secret_failed", "error": str(e), "duration": duration},
        )

        logger.error("Failed to migrate TOTP secret after %.3fs: %s", duration, e)
        raise RuntimeError("Migration failed") from e
