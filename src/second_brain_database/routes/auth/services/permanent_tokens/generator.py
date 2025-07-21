"""
Permanent token generation service.

This module provides functionality to generate permanent JWT tokens without expiration
for API access. Tokens are hashed using SHA-256 for secure storage and include
proper metadata tracking.
"""
import hashlib
import secrets
from datetime import datetime
from typing import Optional, Dict, Any
from jose import jwt
from bson import ObjectId

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.models import (
    PermanentTokenResponse,
    PermanentTokenDocument
)

logger = get_logger(prefix="[Permanent Token Generator]")


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
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


async def create_permanent_token(
    user_id: str,
    username: str,
    email: str,
    role: str = "user",
    is_verified: bool = False,
    description: Optional[str] = None
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
    if not user_id or not username or not email:
        raise ValueError("user_id, username, and email are required")
    
    try:
        # Generate unique token ID
        token_id = generate_secure_token_id()
        
        # Create JWT payload without expiration
        payload = {
            "sub": username,
            "username": username,
            "email": email,
            "role": role,
            "is_verified": is_verified,
            "token_type": "permanent",
            "token_id": token_id,
            "iat": datetime.utcnow()
        }
        
        # Get secret key
        secret_key = getattr(settings, "SECRET_KEY", None)
        if hasattr(secret_key, "get_secret_value"):
            secret_key = secret_key.get_secret_value()
        
        if not isinstance(secret_key, (str, bytes)) or not secret_key:
            logger.error("JWT secret key is missing or invalid")
            raise RuntimeError("JWT secret key is missing or invalid")
        
        # Generate JWT token without expiration
        token = jwt.encode(payload, secret_key, algorithm=settings.ALGORITHM)
        
        # Hash token for storage
        token_hash = hash_token(token)
        
        # Create database document
        created_at = datetime.utcnow()
        token_doc = PermanentTokenDocument(
            user_id=user_id,
            token_id=token_id,
            token_hash=token_hash,
            description=description,
            created_at=created_at,
            last_used_at=None,
            is_revoked=False,
            revoked_at=None
        )
        
        # Store in database
        collection = db_manager.get_collection("permanent_tokens")
        result = await collection.insert_one(token_doc.model_dump())
        
        if not result.inserted_id:
            raise RuntimeError("Failed to store token in database")
        
        logger.info(
            "Permanent token created for user %s (ID: %s, token_id: %s)",
            username, user_id, token_id
        )
        
        # Return response with actual token (only returned once)
        return PermanentTokenResponse(
            token=token,
            token_id=token_id,
            created_at=created_at,
            description=description
        )
        
    except Exception as e:
        logger.error("Failed to create permanent token for user %s: %s", username, e)
        raise RuntimeError(f"Token generation failed: {str(e)}") from e


async def validate_token_ownership(user_id: str, token_id: str) -> bool:
    """
    Validate that a token belongs to a specific user.
    
    Args:
        user_id (str): MongoDB ObjectId of the user
        token_id (str): Token ID to validate
        
    Returns:
        bool: True if token belongs to user, False otherwise
    """
    try:
        collection = db_manager.get_collection("permanent_tokens")
        token_doc = await collection.find_one({
            "user_id": user_id,
            "token_id": token_id,
            "is_revoked": False
        })
        return token_doc is not None
    except Exception as e:
        logger.error("Error validating token ownership: %s", e)
        return False


async def get_token_metadata(token_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve token metadata by hash.
    
    Args:
        token_hash (str): SHA-256 hash of the token
        
    Returns:
        Optional[Dict[str, Any]]: Token metadata if found, None otherwise
    """
    try:
        collection = db_manager.get_collection("permanent_tokens")
        token_doc = await collection.find_one({"token_hash": token_hash})
        return token_doc
    except Exception as e:
        logger.error("Error retrieving token metadata: %s", e)
        return None


async def update_last_used(token_hash: str) -> bool:
    """
    Update the last_used_at timestamp for a token.
    
    Args:
        token_hash (str): SHA-256 hash of the token
        
    Returns:
        bool: True if update was successful, False otherwise
    """
    try:
        collection = db_manager.get_collection("permanent_tokens")
        result = await collection.update_one(
            {"token_hash": token_hash, "is_revoked": False},
            {"$set": {"last_used_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
    except Exception as e:
        logger.error("Error updating last_used timestamp: %s", e)
        return False