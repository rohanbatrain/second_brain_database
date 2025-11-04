"""
Permanent token revocation service.

This module provides functionality to revoke permanent tokens,
including cache invalidation and database updates.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from bson import ObjectId

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.models import PermanentTokenInfo, TokenRevocationResponse
from second_brain_database.routes.auth.services.permanent_tokens.generator import hash_token
from second_brain_database.routes.auth.services.permanent_tokens.validator import get_cache_key, invalidate_token_cache

logger = get_logger(prefix="[Permanent Token Revocation]")


async def revoke_token_by_id(user_id: str, token_id: str) -> Optional[TokenRevocationResponse]:
    """
    Revoke a permanent token by its ID.

    Args:
        user_id (str): MongoDB ObjectId of the token owner
        token_id (str): Unique token identifier

    Returns:
        Optional[TokenRevocationResponse]: Revocation confirmation if successful, None otherwise

    Raises:
        ValueError: If token doesn't belong to user or doesn't exist
    """
    try:
        collection = db_manager.get_collection("permanent_tokens")

        # Find the token and verify ownership
        token_doc = await collection.find_one({"user_id": user_id, "token_id": token_id, "is_revoked": False})

        if not token_doc:
            raise ValueError("Token not found or already revoked")

        # Mark token as revoked in database
        revoked_at = datetime.utcnow()
        result = await collection.update_one(
            {"_id": token_doc["_id"]}, {"$set": {"is_revoked": True, "revoked_at": revoked_at}}
        )

        if result.modified_count == 0:
            raise RuntimeError("Failed to revoke token in database")

        # Invalidate Redis cache
        token_hash = token_doc["token_hash"]
        await invalidate_token_cache(token_hash)

        logger.info("Permanent token revoked: token_id=%s, user_id=%s", token_id, user_id)

        return TokenRevocationResponse(message="Token revoked successfully", token_id=token_id, revoked_at=revoked_at)

    except ValueError:
        raise
    except Exception as e:
        logger.error("Error revoking token %s for user %s: %s", token_id, user_id, e)
        raise RuntimeError(f"Failed to revoke token: {str(e)}") from e


async def revoke_token_by_hash(token_hash: str) -> bool:
    """
    Revoke a permanent token by its hash.

    Args:
        token_hash (str): SHA-256 hash of the token

    Returns:
        bool: True if revocation was successful, False otherwise
    """
    try:
        collection = db_manager.get_collection("permanent_tokens")

        # Mark token as revoked
        revoked_at = datetime.utcnow()
        result = await collection.update_one(
            {"token_hash": token_hash, "is_revoked": False}, {"$set": {"is_revoked": True, "revoked_at": revoked_at}}
        )

        if result.modified_count > 0:
            # Invalidate Redis cache
            await invalidate_token_cache(token_hash)
            logger.info("Permanent token revoked by hash: %s", token_hash[:16] + "...")
            return True

        return False

    except Exception as e:
        logger.error("Error revoking token by hash: %s", e)
        return False


async def revoke_all_user_tokens(user_id: str) -> int:
    """
    Revoke all permanent tokens for a user.

    Args:
        user_id (str): MongoDB ObjectId of the user

    Returns:
        int: Number of tokens revoked
    """
    try:
        collection = db_manager.get_collection("permanent_tokens")

        # Get all active tokens for user
        active_tokens = await collection.find({"user_id": user_id, "is_revoked": False}).to_list(length=None)

        if not active_tokens:
            return 0

        # Mark all tokens as revoked
        revoked_at = datetime.utcnow()
        result = await collection.update_many(
            {"user_id": user_id, "is_revoked": False}, {"$set": {"is_revoked": True, "revoked_at": revoked_at}}
        )

        # Invalidate all caches
        for token_doc in active_tokens:
            await invalidate_token_cache(token_doc["token_hash"])

        revoked_count = result.modified_count
        logger.info("Revoked %d permanent tokens for user %s", revoked_count, user_id)

        return revoked_count

    except Exception as e:
        logger.error("Error revoking all tokens for user %s: %s", user_id, e)
        return 0


async def get_user_tokens(user_id: str, include_revoked: bool = False) -> List[PermanentTokenInfo]:
    """
    Get all permanent tokens for a user.

    Args:
        user_id (str): MongoDB ObjectId of the user
        include_revoked (bool): Whether to include revoked tokens

    Returns:
        List[PermanentTokenInfo]: List of token metadata
    """
    try:
        collection = db_manager.get_collection("permanent_tokens")

        # Build query
        query = {"user_id": user_id}
        if not include_revoked:
            query["is_revoked"] = False

        # Get tokens
        tokens = await collection.find(query).sort("created_at", -1).to_list(length=None)

        # Convert to response models
        token_infos = []
        for token_doc in tokens:
            token_info = PermanentTokenInfo(
                token_id=token_doc.get("token_id", ""),
                description=token_doc.get("description"),
                created_at=token_doc["created_at"],
                last_used_at=token_doc.get("last_used_at"),
                is_revoked=token_doc.get("is_revoked", False),
                revoked_at=token_doc.get("revoked_at"),
            )
            token_infos.append(token_info)

        return token_infos

    except Exception as e:
        logger.error("Error getting tokens for user %s: %s", user_id, e)
        return []


async def cleanup_revoked_tokens(days_old: int = 30) -> int:
    """
    Clean up revoked tokens older than specified days.

    Args:
        days_old (int): Number of days after which to delete revoked tokens

    Returns:
        int: Number of tokens deleted
    """
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        collection = db_manager.get_collection("permanent_tokens")

        # Delete old revoked tokens
        result = await collection.delete_many({"is_revoked": True, "revoked_at": {"$lt": cutoff_date}})

        deleted_count = result.deleted_count
        if deleted_count > 0:
            logger.info("Cleaned up %d old revoked permanent tokens", deleted_count)

        return deleted_count

    except Exception as e:
        logger.error("Error cleaning up revoked tokens: %s", e)
        return 0
