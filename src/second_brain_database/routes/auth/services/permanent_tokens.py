"""
Permanent token authentication service.

Handles validation and management of permanent API tokens for long-lived
authentication and integrations.
"""

import hashlib
from typing import Any, Dict, Optional

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.models import PermanentTokenDocument

logger = get_logger(prefix="[Permanent Tokens]")


def is_permanent_token(token: str) -> bool:
    """
    Check if a token is a permanent token.

    Permanent tokens are identified by their format or by checking
    if they exist in the permanent tokens collection.

    Args:
        token: The token to check

    Returns:
        True if the token is a permanent token, False otherwise
    """
    if not token or not isinstance(token, str):
        return False

    # Check if token starts with permanent token prefix
    if token.startswith("sbd_permanent_"):
        return True

    # For JWT tokens, check the token_type claim
    try:
        import jwt

        from second_brain_database.config import settings

        secret_key = getattr(settings, "SECRET_KEY", None)
        if hasattr(secret_key, "get_secret_value"):
            secret_key = secret_key.get_secret_value()

        if secret_key:
            # Try to decode without verification first to check token_type
            try:
                payload = jwt.decode(token, options={"verify_signature": False})
                token_type = payload.get("token_type")
                if token_type == "permanent":
                    return True
            except:
                pass
    except Exception:
        pass

    return False


async def validate_permanent_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate a permanent token against the database.

    Checks if the token exists in the permanent tokens collection,
    is not revoked, and retrieves the associated user.

    Args:
        token: The permanent token to validate

    Returns:
        User document if token is valid, None otherwise
    """
    try:
        if not token:
            logger.warning("Empty token provided for permanent token validation")
            return None

        # Handle JWT permanent tokens
        if token.startswith("eyJ"):  # JWT token
            try:
                import jwt

                from second_brain_database.config import settings

                secret_key = getattr(settings, "SECRET_KEY", None)
                if hasattr(secret_key, "get_secret_value"):
                    secret_key = secret_key.get_secret_value()

                if not secret_key:
                    logger.error("JWT secret key not configured")
                    return None

                # Decode the JWT token
                payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
                token_id = payload.get("token_id")

                if not token_id:
                    logger.warning("JWT permanent token missing token_id claim")
                    return None

                # Find the permanent token document
                token_doc = await db_manager.get_collection("permanent_tokens").find_one({
                    "token_id": token_id,
                    "is_revoked": False
                })

                if not token_doc:
                    logger.warning("Permanent token not found or revoked: %s", token_id)
                    return None

                # Get the user
                user = await db_manager.get_collection("users").find_one({
                    "_id": token_doc["user_id"]
                })

                if not user:
                    logger.warning("User not found for permanent token: %s", token_doc["user_id"])
                    return None

                # Update last used timestamp
                await db_manager.get_collection("permanent_tokens").update_one(
                    {"_id": token_doc["_id"]},
                    {"$set": {"last_used_at": jwt.decode(token, options={"verify_signature": False}).get("iat")}}
                )

                logger.debug("Permanent JWT token validated for user: %s", user.get("username"))
                return user

            except jwt.ExpiredSignatureError:
                logger.warning("Permanent JWT token has expired")
                return None
            except Exception as e:
                logger.error("Error validating permanent JWT token: %s", e)
                return None

        # Handle raw permanent tokens (prefixed format)
        elif token.startswith("sbd_permanent_"):
            # Extract token hash for database lookup
            token_hash = hashlib.sha256(token.encode()).hexdigest()

            # Find the permanent token document
            token_doc = await db_manager.get_collection("permanent_tokens").find_one({
                "token_hash": token_hash,
                "is_revoked": False
            })

            if not token_doc:
                logger.warning("Permanent token not found or revoked")
                return None

            # Get the user
            user = await db_manager.get_collection("users").find_one({
                "_id": token_doc["user_id"]
            })

            if not user:
                logger.warning("User not found for permanent token: %s", token_doc["user_id"])
                return None

            # Update usage statistics
            await db_manager.get_collection("permanent_tokens").update_one(
                {"_id": token_doc["_id"]},
                {
                    "$inc": {"usage_count": 1},
                    "$set": {"last_used_at": jwt.decode(token, options={"verify_signature": False}).get("iat") if token.startswith("eyJ") else None}
                }
            )

            logger.debug("Permanent token validated for user: %s", user.get("username"))
            return user

        else:
            logger.warning("Invalid permanent token format")
            return None

    except Exception as e:
        logger.error("Unexpected error validating permanent token: %s", e, exc_info=True)
        return None


async def create_permanent_token(
    user_id: str,
    username: str,
    email: str,
    role: str = "user",
    is_verified: bool = False,
    description: Optional[str] = None,
    expires_at: Optional[float] = None
) -> PermanentTokenResponse:
    """
    Create a new permanent token for a user.

    Args:
        user_id: The user ID to create the token for
        username: The username of the user
        email: The email of the user
        role: The role of the user
        is_verified: Whether the user is verified
        description: Optional description for the token
        expires_at: Optional expiration timestamp

    Returns:
        PermanentTokenResponse with token details

    Raises:
        ValueError: If user doesn't exist or token creation fails
    """
    try:
        # Verify user exists
        user = await db_manager.get_collection("users").find_one({"_id": user_id})
        if not user:
            raise ValueError(f"User not found: {user_id}")

        # Generate token
        from datetime import datetime, timezone
        import secrets

        import jwt

        from second_brain_database.routes.auth.models import PermanentTokenResponse

        token_id = secrets.token_hex(16)

        # Create JWT permanent token
        payload = {
            "sub": username,
            "username": username,
            "email": email,
            "role": role,
            "is_verified": is_verified,
            "token_type": "permanent",
            "token_id": token_id,
            "iat": datetime.now(timezone.utc).timestamp(),
        }

        if expires_at:
            payload["exp"] = expires_at

        secret_key = getattr(settings, "SECRET_KEY", None)
        if hasattr(secret_key, "get_secret_value"):
            secret_key = secret_key.get_secret_value()

        if not secret_key:
            raise ValueError("JWT secret key not configured")

        token = jwt.encode(payload, secret_key, algorithm=settings.ALGORITHM)

        # Store token hash in database
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        token_doc = PermanentTokenDocument(
            user_id=user_id,
            token_id=token_id,
            token_hash=token_hash,
            description=description,
        )

        await db_manager.get_collection("permanent_tokens").insert_one(token_doc.model_dump())

        logger.info("Created permanent token for user: %s", username)

        # Return response model
        return PermanentTokenResponse(
            token=token,
            token_id=token_id,
            created_at=datetime.now(timezone.utc),
            description=description,
            expires_at=datetime.fromtimestamp(expires_at, tz=timezone.utc) if expires_at else None,
            ip_restrictions=None,  
            last_used_at=None,
            usage_count=0,
            is_revoked=False,
        )

    except Exception as e:
        logger.error("Failed to create permanent token: %s", e)
        raise


async def revoke_permanent_token(token_id: str, user_id: str) -> bool:
    """
    Revoke a permanent token.

    Args:
        token_id: The token ID to revoke
        user_id: The user ID (for authorization)

    Returns:
        True if token was revoked, False otherwise
    """
    try:
        from datetime import datetime, timezone

        result = await db_manager.get_collection("permanent_tokens").update_one(
            {"token_id": token_id, "user_id": user_id},
            {
                "$set": {
                    "is_revoked": True,
                    "revoked_at": datetime.now(timezone.utc)
                }
            }
        )

        if result.modified_count > 0:
            logger.info("Revoked permanent token: %s", token_id)
            return True
        else:
            logger.warning("Failed to revoke permanent token: %s", token_id)
            return False

    except Exception as e:
        logger.error("Error revoking permanent token: %s", e)
        return False