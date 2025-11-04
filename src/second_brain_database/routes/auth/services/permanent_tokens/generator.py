"""
Permanent token generation service.

This module provides functionality to generate permanent JWT tokens without expiration
for API access. Tokens are hashed using SHA-256 for secure storage and include
proper metadata tracking.
"""

from datetime import datetime, timezone
import hashlib
import secrets
from typing import Any, Dict, Optional

from bson import ObjectId
from jose import jwt

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.models import PermanentTokenDocument, PermanentTokenResponse
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Permanent Token Generator]")
security_logger = SecurityLogger(prefix="[PERM-TOKEN-GENERATOR-SECURITY]")
db_logger = DatabaseLogger(prefix="[PERM-TOKEN-GENERATOR-DB]")


def generate_secure_token_id() -> str:
    """
    Generate a cryptographically secure token ID.

    Returns:
        str: A secure random token ID (32 characters)
    """
    return secrets.token_urlsafe(24)  # 32 chars when base64 encoded


def hash_token(token: str) -> str:
    """
    Create SHA-256 hash of a token for secure storage.

    Args:
        token (str): The JWT token to hash

    Returns:
        str: SHA-256 hash of the token (hex encoded)
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@log_performance("create_permanent_token", log_args=False)
async def create_permanent_token(
    user_id: str,
    username: str,
    email: str,
    role: str = "user",
    is_verified: bool = False,
    description: Optional[str] = None,
) -> PermanentTokenResponse:
    """
    Generate a new permanent JWT token for a user.

    Creates a JWT token without expiration claim and stores metadata
    in the database with SHA-256 hash for security.

    Args:
        user_id (str): MongoDB ObjectId of the user
        username (str): Username of the token owner
        email (str): Email of the token owner
        role (str): User role (default: "user")
        is_verified (bool): Email verification status
        description (Optional[str]): Optional token description

    Returns:
        PermanentTokenResponse: Response containing the token and metadata

    Raises:
        RuntimeError: If token generation fails
        ValueError: If required parameters are missing
    """
    logger.info("Creating permanent token for user %s (role: %s)", username, role)

    if not user_id or not username or not email:
        logger.error(
            "Missing required parameters for token creation: user_id=%s, username=%s, email=%s",
            bool(user_id),
            bool(username),
            bool(email),
        )
        raise ValueError("user_id, username, and email are required")

    try:
        # Generate unique token ID
        token_id = generate_secure_token_id()
        logger.debug("Generated secure token ID: %s", token_id)

        # Create JWT payload without expiration
        payload = {
            "sub": username,
            "username": username,
            "email": email,
            "role": role,
            "is_verified": is_verified,
            "token_type": "permanent",
            "token_id": token_id,
            "iat": datetime.now(timezone.utc),
        }

        # Log security event for token creation attempt
        log_security_event(
            event_type="permanent_token_creation_attempt",
            user_id=username,
            success=False,  # Will be updated to True on success
            details={
                "user_id": user_id,
                "role": role,
                "is_verified": is_verified,
                "description": description,
                "token_id": token_id,
            },
        )

        # Get secret key
        secret_key = getattr(settings, "SECRET_KEY", None)
        if hasattr(secret_key, "get_secret_value"):
            secret_key = secret_key.get_secret_value()

        if not isinstance(secret_key, (str, bytes)) or not secret_key:
            logger.error("JWT secret key is missing or invalid for user %s", username)
            log_security_event(
                event_type="permanent_token_creation_failed",
                user_id=username,
                success=False,
                details={"error": "invalid_secret_key", "token_id": token_id},
            )
            raise RuntimeError("JWT secret key is missing or invalid")

        # Generate JWT token without expiration
        token = jwt.encode(payload, secret_key, algorithm=settings.ALGORITHM)
        logger.debug("JWT token generated successfully for user %s", username)

        # Hash token for storage
        token_hash = hash_token(token)
        logger.debug("Token hash generated for secure storage: %s", token_hash[:16] + "...")

        # Create database document
        created_at = datetime.now(timezone.utc)
        token_doc = PermanentTokenDocument(
            user_id=user_id,
            token_id=token_id,
            token_hash=token_hash,
            description=description,
            created_at=created_at,
            last_used_at=None,
            is_revoked=False,
            revoked_at=None,
        )

        # Store in database
        collection = db_manager.get_collection("permanent_tokens")
        result = await collection.insert_one(token_doc.model_dump())

        # Corrected logging call to match function signature
        log_database_operation("permanent_tokens", "insert")

        if not result.inserted_id:
            logger.error("Failed to store token in database for user %s", username)
            log_security_event(
                event_type="permanent_token_creation_failed",
                user_id=username,
                success=False,
                details={"error": "database_insert_failed", "token_id": token_id},
            )
            raise RuntimeError("Failed to store token in database")

        logger.info(
            "Permanent token created successfully for user %s (ID: %s, token_id: %s)", username, user_id, token_id
        )

        # Log successful token creation
        log_security_event(
            event_type="permanent_token_created",
            user_id=username,
            success=True,
            details={
                "user_id": user_id,
                "token_id": token_id,
                "role": role,
                "description": description,
                "database_id": str(result.inserted_id),
            },
        )

        # Return response with actual token (only returned once)
        return PermanentTokenResponse(token=token, token_id=token_id, created_at=created_at, description=description)

    except Exception as e:
        logger.error("Failed to create permanent token for user %s: %s", username, e, exc_info=True)
        log_error_with_context(
            e,
            context={
                "user_id": user_id,
                "username": username,
                "email": email,
                "role": role,
                "description": description,
            },
            operation="create_permanent_token",
        )
        raise RuntimeError(f"Token generation failed: {str(e)}") from e


@log_performance("validate_token_ownership")
async def validate_token_ownership(user_id: str, token_id: str) -> bool:
    """
    Validate that a token belongs to a specific user.

    Args:
        user_id (str): MongoDB ObjectId of the user
        token_id (str): Token ID to validate

    Returns:
        bool: True if token belongs to user, False otherwise
    """
    logger.debug("Validating token ownership for user %s, token %s", user_id, token_id)

    try:
        collection = db_manager.get_collection("permanent_tokens")
        token_doc = await collection.find_one({"user_id": user_id, "token_id": token_id, "is_revoked": False})

        is_valid = token_doc is not None

        log_database_operation(
            operation="validate_token_ownership",
            collection="permanent_tokens",
            query={"user_id": user_id, "token_id": token_id, "is_revoked": False},
            result={"valid": is_valid},
        )

        if is_valid:
            logger.info("Token ownership validated successfully for user %s", user_id)
        else:
            logger.warning("Token ownership validation failed for user %s, token %s", user_id, token_id)
            log_security_event(
                event_type="token_ownership_validation_failed",
                user_id=user_id,
                success=False,
                details={"token_id": token_id},
            )

        return is_valid
    except Exception as e:
        logger.error("Error validating token ownership for user %s: %s", user_id, e, exc_info=True)
        log_error_with_context(
            e, context={"user_id": user_id, "token_id": token_id}, operation="validate_token_ownership"
        )
        return False


@log_performance("get_token_metadata")
async def get_token_metadata(token_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve token metadata by hash.

    Args:
        token_hash (str): SHA-256 hash of the token

    Returns:
        Optional[Dict[str, Any]]: Token metadata if found, None otherwise
    """
    logger.debug("Retrieving token metadata for hash: %s", token_hash[:16] + "...")

    try:
        collection = db_manager.get_collection("permanent_tokens")
        token_doc = await collection.find_one({"token_hash": token_hash})

        log_database_operation(
            operation="get_token_metadata",
            collection="permanent_tokens",
            query={"token_hash": token_hash[:8] + "..."},
            result={"found": token_doc is not None},
        )

        if token_doc:
            logger.info("Token metadata retrieved successfully for hash: %s", token_hash[:16] + "...")
        else:
            logger.warning("Token metadata not found for hash: %s", token_hash[:16] + "...")

        return token_doc
    except Exception as e:
        logger.error("Error retrieving token metadata: %s", e, exc_info=True)
        log_error_with_context(e, context={"token_hash_prefix": token_hash[:8]}, operation="get_token_metadata")
        return None


@log_performance("update_last_used")
async def update_last_used(token_hash: str) -> bool:
    """
    Update the last_used_at timestamp for a token.

    Args:
        token_hash (str): SHA-256 hash of the token

    Returns:
        bool: True if update was successful, False otherwise
    """
    logger.debug("Updating last_used timestamp for token: %s", token_hash[:16] + "...")

    try:
        collection = db_manager.get_collection("permanent_tokens")
        now = datetime.now(timezone.utc)
        result = await collection.update_one(
            {"token_hash": token_hash, "is_revoked": False}, {"$set": {"last_used_at": now}}
        )

        success = result.modified_count > 0

        log_database_operation(
            operation="update_token_last_used",
            collection="permanent_tokens",
            query={"token_hash": token_hash[:8] + "...", "is_revoked": False},
            result={"modified_count": result.modified_count, "timestamp": now.isoformat()},
        )

        if success:
            logger.debug("Successfully updated last_used timestamp for token: %s", token_hash[:16] + "...")
        else:
            logger.warning(
                "Failed to update last_used timestamp - token not found or revoked: %s", token_hash[:16] + "..."
            )

        return success
    except Exception as e:
        logger.error("Error updating last_used timestamp: %s", e, exc_info=True)
        log_error_with_context(e, context={"token_hash_prefix": token_hash[:8]}, operation="update_last_used")
        return False
