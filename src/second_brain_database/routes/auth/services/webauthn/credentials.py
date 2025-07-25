"""
WebAuthn credential storage and retrieval service.

This module provides functionality to store, retrieve, and manage WebAuthn credentials
following existing database operation patterns from permanent_tokens. Includes Redis
caching for optimal performance and comprehensive logging.
"""

from datetime import datetime, timedelta
import json
from typing import Any, Dict, List, Optional

from bson import ObjectId

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[WebAuthn Credentials]")
security_logger = SecurityLogger(prefix="[WEBAUTHN-CREDENTIALS-SECURITY]")
db_logger = DatabaseLogger(prefix="[WEBAUTHN-CREDENTIALS-DB]")

# Cache configuration following permanent_tokens patterns
CACHE_TTL_SECONDS = 60 * 60  # 1 hour cache TTL
REDIS_CREDENTIAL_PREFIX = "webauthn_creds:"
REDIS_SINGLE_CREDENTIAL_PREFIX = "webauthn_cred:"


def get_user_credentials_cache_key(user_id: str) -> str:
    """
    Generate Redis cache key for user's WebAuthn credentials.

    Args:
        user_id (str): MongoDB ObjectId of the user

    Returns:
        str: Redis cache key
    """
    return f"{REDIS_CREDENTIAL_PREFIX}{user_id}"


def get_single_credential_cache_key(credential_id: str) -> str:
    """
    Generate Redis cache key for a single WebAuthn credential.

    Args:
        credential_id (str): Credential ID

    Returns:
        str: Redis cache key
    """
    return f"{REDIS_SINGLE_CREDENTIAL_PREFIX}{credential_id}"


@log_performance("store_webauthn_credential", log_args=False)
@log_database_operation("webauthn_credentials", "insert")
async def store_credential(
    user_id: str,
    credential_id: str,
    public_key: str,
    device_name: Optional[str] = None,
    authenticator_type: str = "platform",
    transport: Optional[List[str]] = None,
    aaguid: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Store a new WebAuthn credential in the database.

    Follows existing database operation patterns from permanent_tokens with
    comprehensive logging and error handling.

    Args:
        user_id (str): MongoDB ObjectId of the user
        credential_id (str): Unique credential identifier
        public_key (str): CBOR encoded public key
        device_name (Optional[str]): User-friendly device name
        authenticator_type (str): Type of authenticator (platform/cross-platform)
        transport (Optional[List[str]]): Transport methods supported
        aaguid (Optional[str]): Authenticator AAGUID

    Returns:
        Dict[str, Any]: Stored credential metadata

    Raises:
        ValueError: If required parameters are missing
        RuntimeError: If credential storage fails
    """
    logger.info("Storing WebAuthn credential for user %s, device: %s", user_id, device_name or "Unknown")

    if not user_id or not credential_id or not public_key:
        logger.error(
            "Missing required parameters: user_id=%s, credential_id=%s, public_key=%s",
            bool(user_id),
            bool(credential_id),
            bool(public_key),
        )
        raise ValueError("user_id, credential_id, and public_key are required")

    try:
        # Log security event for credential storage attempt
        log_security_event(
            event_type="webauthn_credential_storage_attempt",
            user_id=user_id,
            success=False,  # Will be updated to True on success
            details={
                "credential_id": credential_id,
                "device_name": device_name,
                "authenticator_type": authenticator_type,
                "transport": transport,
            },
        )

        # Create credential document
        created_at = datetime.utcnow()
        credential_doc = {
            "user_id": ObjectId(user_id),
            "credential_id": credential_id,
            "public_key": public_key,
            "sign_count": 0,
            "device_name": device_name or "WebAuthn Device",
            "authenticator_type": authenticator_type,
            "transport": transport or [],
            "aaguid": aaguid,
            "created_at": created_at,
            "last_used_at": None,
            "is_active": True,
        }

        # Store in database
        collection = db_manager.get_collection("webauthn_credentials")
        
        # Check if credential already exists and update if so
        existing_credential = await collection.find_one({"credential_id": credential_id})
        
        if existing_credential:
            # Update existing credential
            result = await collection.update_one(
                {"credential_id": credential_id},
                {
                    "$set": {
                        "public_key": public_key,
                        "device_name": device_name or existing_credential.get("device_name", "WebAuthn Device"),
                        "authenticator_type": authenticator_type,
                        "transport": transport or existing_credential.get("transport", []),
                        "aaguid": aaguid,
                        "is_active": True,
                        "updated_at": created_at,
                    }
                }
            )
            
            if result.modified_count == 0:
                logger.error("Failed to update existing credential in database")
                raise RuntimeError("Failed to update existing credential in database")
                
            logger.info("Updated existing WebAuthn credential: %s", credential_id)
            credential_doc["_id"] = existing_credential["_id"]
            operation_type = "update"
        else:
            # Insert new credential
            result = await collection.insert_one(credential_doc)
            
            if not result.inserted_id:
                logger.error("Failed to store credential in database")
                raise RuntimeError("Failed to store credential in database")
                
            credential_doc["_id"] = result.inserted_id
            operation_type = "insert"

        # Invalidate user's credential cache
        await invalidate_user_credentials_cache(user_id)

        logger.info(
            "WebAuthn credential %s successfully for user %s (ID: %s, credential_id: %s)",
            operation_type + "ed",
            user_id,
            str(credential_doc["_id"]),
            credential_id,
        )

        # Log successful credential storage
        log_security_event(
            event_type="webauthn_credential_stored",
            user_id=user_id,
            success=True,
            details={
                "credential_id": credential_id,
                "device_name": device_name,
                "authenticator_type": authenticator_type,
                "database_id": str(credential_doc["_id"]),
                "operation": operation_type,
            },
        )

        # Return credential metadata (without sensitive data)
        return {
            "credential_id": credential_id,
            "device_name": credential_doc["device_name"],
            "authenticator_type": authenticator_type,
            "transport": transport or [],
            "created_at": created_at,
            "is_active": True,
        }

    except Exception as e:
        logger.error("Failed to store WebAuthn credential: %s", e, exc_info=True)
        log_error_with_context(
            e,
            context={
                "user_id": user_id,
                "credential_id": credential_id,
                "device_name": device_name,
                "authenticator_type": authenticator_type,
            },
            operation="store_webauthn_credential",
        )
        raise RuntimeError(f"Credential storage failed: {str(e)}") from e


@log_performance("get_user_credentials")
async def get_user_credentials(user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
    """
    Retrieve all WebAuthn credentials for a user with Redis caching.

    Follows existing caching patterns from permanent_tokens with cache-first
    approach and database fallback.

    Args:
        user_id (str): MongoDB ObjectId of the user
        active_only (bool): Whether to return only active credentials

    Returns:
        List[Dict[str, Any]]: List of user's credentials
    """
    logger.debug("Retrieving WebAuthn credentials for user: %s (active_only: %s)", user_id, active_only)

    try:
        # Try Redis cache first
        cached_credentials = await get_cached_user_credentials(user_id)
        if cached_credentials is not None:
            logger.info("Cache hit for user credentials: %s", user_id)
            
            # Filter active credentials if requested
            if active_only:
                cached_credentials = [cred for cred in cached_credentials if cred.get("is_active", True)]
            
            return cached_credentials

        # Cache miss - fetch from database
        logger.debug("Cache miss, fetching credentials from database for user: %s", user_id)

        collection = db_manager.get_collection("webauthn_credentials")
        query = {"user_id": ObjectId(user_id)}
        
        if active_only:
            query["is_active"] = True

        cursor = collection.find(query).sort("created_at", -1)  # Most recent first
        credentials = await cursor.to_list(length=None)

        # Convert to serializable format
        credential_list = []
        for cred in credentials:
            credential_data = {
                "credential_id": cred["credential_id"],
                "device_name": cred["device_name"],
                "authenticator_type": cred["authenticator_type"],
                "transport": cred.get("transport", []),
                "created_at": cred["created_at"],
                "last_used_at": cred.get("last_used_at"),
                "is_active": cred.get("is_active", True),
                "public_key": cred["public_key"],  # Include for authentication
                "sign_count": cred.get("sign_count", 0),
            }
            credential_list.append(credential_data)

        # Cache the results
        await cache_user_credentials(user_id, credential_list)

        logger.info("Retrieved %d WebAuthn credentials for user %s from database", len(credential_list), user_id)

        return credential_list

    except Exception as e:
        logger.error("Error retrieving user credentials: %s", e, exc_info=True)
        log_error_with_context(e, context={"user_id": user_id, "active_only": active_only}, operation="get_user_credentials")
        return []


@log_performance("get_credential_by_id")
async def get_credential_by_id(credential_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a specific WebAuthn credential by ID with caching.

    Args:
        credential_id (str): Credential ID to retrieve

    Returns:
        Optional[Dict[str, Any]]: Credential data if found, None otherwise
    """
    logger.debug("Retrieving WebAuthn credential by ID: %s", credential_id)

    try:
        # Try Redis cache first
        cached_credential = await get_cached_single_credential(credential_id)
        if cached_credential is not None:
            logger.debug("Cache hit for credential: %s", credential_id)
            return cached_credential

        # Cache miss - fetch from database
        collection = db_manager.get_collection("webauthn_credentials")
        credential = await collection.find_one({"credential_id": credential_id, "is_active": True})

        if not credential:
            logger.info("Credential not found: %s", credential_id)
            return None

        # Convert to serializable format
        credential_data = {
            "credential_id": credential["credential_id"],
            "user_id": str(credential["user_id"]),
            "device_name": credential["device_name"],
            "authenticator_type": credential["authenticator_type"],
            "transport": credential.get("transport", []),
            "created_at": credential["created_at"],
            "last_used_at": credential.get("last_used_at"),
            "is_active": credential.get("is_active", True),
            "public_key": credential["public_key"],
            "sign_count": credential.get("sign_count", 0),
        }

        # Cache the result
        await cache_single_credential(credential_id, credential_data)

        logger.debug("Retrieved credential from database: %s", credential_id)
        return credential_data

    except Exception as e:
        logger.error("Error retrieving credential by ID: %s", e, exc_info=True)
        log_error_with_context(e, context={"credential_id": credential_id}, operation="get_credential_by_id")
        return None


@log_performance("update_credential_usage")
@log_database_operation("webauthn_credentials", "update_usage")
async def update_credential_usage(credential_id: str, sign_count: int) -> bool:
    """
    Update credential's last used timestamp and signature counter.

    Args:
        credential_id (str): Credential ID to update
        sign_count (int): New signature counter value

    Returns:
        bool: True if update was successful, False otherwise
    """
    logger.debug("Updating credential usage: %s (sign_count: %d)", credential_id, sign_count)

    try:
        collection = db_manager.get_collection("webauthn_credentials")
        now = datetime.utcnow()
        
        result = await collection.update_one(
            {"credential_id": credential_id, "is_active": True},
            {
                "$set": {
                    "last_used_at": now,
                    "sign_count": sign_count,
                }
            }
        )

        success = result.modified_count > 0

        if success:
            logger.debug("Successfully updated credential usage: %s", credential_id)
            
            # Invalidate caches
            await invalidate_single_credential_cache(credential_id)
            
            # Get user_id to invalidate user cache
            credential = await collection.find_one({"credential_id": credential_id}, {"user_id": 1})
            if credential:
                await invalidate_user_credentials_cache(str(credential["user_id"]))
        else:
            logger.warning("Failed to update credential usage - credential not found or inactive: %s", credential_id)

        return success

    except Exception as e:
        logger.error("Error updating credential usage: %s", e, exc_info=True)
        log_error_with_context(e, context={"credential_id": credential_id, "sign_count": sign_count}, operation="update_credential_usage")
        return False


@log_performance("cache_user_credentials")
async def cache_user_credentials(user_id: str, credentials: List[Dict[str, Any]]) -> bool:
    """
    Cache user's WebAuthn credentials in Redis.

    Args:
        user_id (str): MongoDB ObjectId of the user
        credentials (List[Dict[str, Any]]): Credentials to cache

    Returns:
        bool: True if caching was successful, False otherwise
    """
    logger.debug("Caching %d WebAuthn credentials for user: %s", len(credentials), user_id)

    try:
        cache_key = get_user_credentials_cache_key(user_id)
        
        # Prepare cache data with timestamp
        cache_data = {
            "credentials": credentials,
            "cached_at": datetime.utcnow().isoformat(),
        }

        redis_conn = await redis_manager.get_redis()
        await redis_conn.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(cache_data, default=str))

        logger.debug("Successfully cached credentials for user: %s", user_id)
        return True

    except Exception as e:
        logger.error("Failed to cache user credentials: %s", e, exc_info=True)
        log_error_with_context(e, context={"user_id": user_id, "credential_count": len(credentials)}, operation="cache_user_credentials")
        return False


@log_performance("get_cached_user_credentials")
async def get_cached_user_credentials(user_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve cached user credentials from Redis.

    Args:
        user_id (str): MongoDB ObjectId of the user

    Returns:
        Optional[List[Dict[str, Any]]]: Cached credentials if found, None otherwise
    """
    try:
        cache_key = get_user_credentials_cache_key(user_id)
        redis_conn = await redis_manager.get_redis()
        cached_data = await redis_conn.get(cache_key)

        if cached_data:
            data_dict = json.loads(cached_data)
            logger.debug("Cache hit for user credentials: %s", user_id)
            return data_dict.get("credentials", [])

        logger.debug("Cache miss for user credentials: %s", user_id)
        return None

    except Exception as e:
        logger.error("Failed to retrieve cached user credentials: %s", e, exc_info=True)
        return None


@log_performance("cache_single_credential")
async def cache_single_credential(credential_id: str, credential_data: Dict[str, Any]) -> bool:
    """
    Cache a single WebAuthn credential in Redis.

    Args:
        credential_id (str): Credential ID
        credential_data (Dict[str, Any]): Credential data to cache

    Returns:
        bool: True if caching was successful, False otherwise
    """
    try:
        cache_key = get_single_credential_cache_key(credential_id)
        
        # Add cache timestamp
        cache_data = {
            **credential_data,
            "cached_at": datetime.utcnow().isoformat(),
        }

        redis_conn = await redis_manager.get_redis()
        await redis_conn.setex(cache_key, CACHE_TTL_SECONDS, json.dumps(cache_data, default=str))

        logger.debug("Successfully cached single credential: %s", credential_id)
        return True

    except Exception as e:
        logger.error("Failed to cache single credential: %s", e, exc_info=True)
        return False


@log_performance("get_cached_single_credential")
async def get_cached_single_credential(credential_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a cached single credential from Redis.

    Args:
        credential_id (str): Credential ID

    Returns:
        Optional[Dict[str, Any]]: Cached credential if found, None otherwise
    """
    try:
        cache_key = get_single_credential_cache_key(credential_id)
        redis_conn = await redis_manager.get_redis()
        cached_data = await redis_conn.get(cache_key)

        if cached_data:
            credential_data = json.loads(cached_data)
            # Remove cache metadata before returning
            credential_data.pop("cached_at", None)
            logger.debug("Cache hit for single credential: %s", credential_id)
            return credential_data

        logger.debug("Cache miss for single credential: %s", credential_id)
        return None

    except Exception as e:
        logger.error("Failed to retrieve cached single credential: %s", e, exc_info=True)
        return None


async def invalidate_user_credentials_cache(user_id: str) -> bool:
    """
    Invalidate cached user credentials in Redis.

    Args:
        user_id (str): MongoDB ObjectId of the user

    Returns:
        bool: True if invalidation was successful, False otherwise
    """
    try:
        cache_key = get_user_credentials_cache_key(user_id)
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.delete(cache_key)
        
        if result > 0:
            logger.debug("Invalidated credentials cache for user: %s", user_id)
        
        return result > 0

    except Exception as e:
        logger.error("Failed to invalidate user credentials cache: %s", e)
        return False


async def invalidate_single_credential_cache(credential_id: str) -> bool:
    """
    Invalidate cached single credential in Redis.

    Args:
        credential_id (str): Credential ID

    Returns:
        bool: True if invalidation was successful, False otherwise
    """
    try:
        cache_key = get_single_credential_cache_key(credential_id)
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.delete(cache_key)
        
        if result > 0:
            logger.debug("Invalidated cache for single credential: %s", credential_id)
        
        return result > 0

    except Exception as e:
        logger.error("Failed to invalidate single credential cache: %s", e)
        return False


@log_performance("deactivate_credential")
@log_database_operation("webauthn_credentials", "deactivate")
async def deactivate_credential(credential_id: str, user_id: str) -> bool:
    """
    Deactivate a WebAuthn credential (soft delete).

    Args:
        credential_id (str): Credential ID to deactivate
        user_id (str): User ID for ownership validation

    Returns:
        bool: True if deactivation was successful, False otherwise
    """
    logger.info("Deactivating WebAuthn credential: %s for user: %s", credential_id, user_id)

    try:
        collection = db_manager.get_collection("webauthn_credentials")
        
        # Verify ownership and deactivate
        result = await collection.update_one(
            {"credential_id": credential_id, "user_id": ObjectId(user_id), "is_active": True},
            {
                "$set": {
                    "is_active": False,
                    "deactivated_at": datetime.utcnow(),
                }
            }
        )

        success = result.modified_count > 0

        if success:
            logger.info("Successfully deactivated credential: %s", credential_id)
            
            # Invalidate caches
            await invalidate_single_credential_cache(credential_id)
            await invalidate_user_credentials_cache(user_id)
            
            # Log security event
            log_security_event(
                event_type="webauthn_credential_deactivated",
                user_id=user_id,
                success=True,
                details={"credential_id": credential_id},
            )
        else:
            logger.warning("Failed to deactivate credential - not found or not owned by user: %s", credential_id)
            
            log_security_event(
                event_type="webauthn_credential_deactivation_failed",
                user_id=user_id,
                success=False,
                details={"credential_id": credential_id, "reason": "not_found_or_not_owned"},
            )

        return success

    except Exception as e:
        logger.error("Error deactivating credential: %s", e, exc_info=True)
        log_error_with_context(
            e, 
            context={"credential_id": credential_id, "user_id": user_id}, 
            operation="deactivate_credential"
        )
        return False


@log_performance("validate_credential_ownership")
async def validate_credential_ownership(credential_id: str, user_id: str) -> bool:
    """
    Validate that a credential belongs to a specific user.

    Args:
        credential_id (str): Credential ID to validate
        user_id (str): User ID to check ownership against

    Returns:
        bool: True if credential belongs to user, False otherwise
    """
    logger.debug("Validating credential ownership: %s for user: %s", credential_id, user_id)

    try:
        collection = db_manager.get_collection("webauthn_credentials")
        credential = await collection.find_one({
            "credential_id": credential_id,
            "user_id": ObjectId(user_id),
            "is_active": True
        })

        is_valid = credential is not None

        if is_valid:
            logger.debug("Credential ownership validated successfully")
        else:
            logger.warning("Credential ownership validation failed")
            log_security_event(
                event_type="webauthn_credential_ownership_validation_failed",
                user_id=user_id,
                success=False,
                details={"credential_id": credential_id},
            )

        return is_valid

    except Exception as e:
        logger.error("Error validating credential ownership: %s", e, exc_info=True)
        log_error_with_context(
            e, 
            context={"credential_id": credential_id, "user_id": user_id}, 
            operation="validate_credential_ownership"
        )
        return False


# Credential Management Operations following permanent_tokens patterns


@log_performance("get_user_credential_list")
async def get_user_credential_list(user_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get all WebAuthn credentials for a user for management operations.
    
    Follows existing patterns from permanent_tokens.get_user_tokens with
    comprehensive logging and error handling.

    Args:
        user_id (str): MongoDB ObjectId of the user
        include_inactive (bool): Whether to include inactive credentials

    Returns:
        List[Dict[str, Any]]: List of credential metadata (safe for API responses)
    """
    logger.info("Retrieving credential list for user: %s (include_inactive: %s)", user_id, include_inactive)

    try:
        collection = db_manager.get_collection("webauthn_credentials")

        # Build query following permanent_tokens pattern
        query = {"user_id": ObjectId(user_id)}
        if not include_inactive:
            query["is_active"] = True

        # Get credentials sorted by creation date (most recent first)
        cursor = collection.find(query).sort("created_at", -1)
        credentials = await cursor.to_list(length=None)

        # Convert to safe response format (exclude sensitive data)
        credential_list = []
        for cred in credentials:
            credential_info = {
                "credential_id": cred["credential_id"],
                "device_name": cred["device_name"],
                "authenticator_type": cred["authenticator_type"],
                "transport": cred.get("transport", []),
                "created_at": cred["created_at"],
                "last_used_at": cred.get("last_used_at"),
                "is_active": cred.get("is_active", True),
                # Exclude sensitive data: public_key, sign_count
            }
            credential_list.append(credential_info)

        log_database_operation(
            operation="get_user_credential_list",
            collection="webauthn_credentials",
            query={"user_id": user_id, "is_active": not include_inactive},
            result={"credential_count": len(credential_list)},
        )

        logger.info("Retrieved %d WebAuthn credentials for user %s", len(credential_list), user_id)
        return credential_list

    except Exception as e:
        logger.error("Error getting credential list for user %s: %s", user_id, e, exc_info=True)
        log_error_with_context(
            e, 
            context={"user_id": user_id, "include_inactive": include_inactive}, 
            operation="get_user_credential_list"
        )
        return []


@log_performance("delete_credential_by_id")
@log_database_operation("webauthn_credentials", "delete")
async def delete_credential_by_id(user_id: str, credential_id: str) -> Optional[Dict[str, Any]]:
    """
    Delete a WebAuthn credential by its ID with ownership validation.
    
    Follows existing patterns from permanent_tokens.revoke_token_by_id with
    comprehensive security logging and ownership validation.

    Args:
        user_id (str): MongoDB ObjectId of the credential owner
        credential_id (str): Unique credential identifier

    Returns:
        Optional[Dict[str, Any]]: Deletion confirmation if successful, None otherwise

    Raises:
        ValueError: If credential doesn't belong to user or doesn't exist
        RuntimeError: If deletion fails
    """
    logger.info("Deleting WebAuthn credential: %s for user: %s", credential_id, user_id)

    try:
        # Log security event for credential deletion attempt
        log_security_event(
            event_type="webauthn_credential_deletion_attempt",
            user_id=user_id,
            success=False,  # Will be updated to True on success
            details={"credential_id": credential_id},
        )

        collection = db_manager.get_collection("webauthn_credentials")

        # Find the credential and verify ownership (following permanent_tokens pattern)
        credential_doc = await collection.find_one({
            "user_id": ObjectId(user_id),
            "credential_id": credential_id,
            "is_active": True
        })

        if not credential_doc:
            logger.warning("Credential not found or not owned by user: %s", credential_id)
            log_security_event(
                event_type="webauthn_credential_deletion_failed",
                user_id=user_id,
                success=False,
                details={"credential_id": credential_id, "reason": "not_found_or_not_owned"},
            )
            raise ValueError("Credential not found or already deleted")

        # Mark credential as inactive (soft delete following existing pattern)
        deleted_at = datetime.utcnow()
        result = await collection.update_one(
            {"_id": credential_doc["_id"]},
            {
                "$set": {
                    "is_active": False,
                    "deleted_at": deleted_at,
                }
            }
        )

        if result.modified_count == 0:
            logger.error("Failed to delete credential in database")
            log_security_event(
                event_type="webauthn_credential_deletion_failed",
                user_id=user_id,
                success=False,
                details={"credential_id": credential_id, "reason": "database_update_failed"},
            )
            raise RuntimeError("Failed to delete credential in database")

        # Invalidate caches (following existing patterns)
        await invalidate_single_credential_cache(credential_id)
        await invalidate_user_credentials_cache(user_id)

        logger.info("WebAuthn credential deleted successfully: credential_id=%s, user_id=%s", credential_id, user_id)

        # Log successful credential deletion
        log_security_event(
            event_type="webauthn_credential_deleted",
            user_id=user_id,
            success=True,
            details={
                "credential_id": credential_id,
                "device_name": credential_doc["device_name"],
                "authenticator_type": credential_doc["authenticator_type"],
                "database_id": str(credential_doc["_id"]),
            },
        )

        # Return deletion confirmation (following TokenRevocationResponse pattern)
        return {
            "message": "Credential deleted successfully",
            "credential_id": credential_id,
            "device_name": credential_doc["device_name"],
            "deleted_at": deleted_at,
        }

    except ValueError:
        # Re-raise ValueError for proper HTTP status code handling
        raise
    except Exception as e:
        logger.error("Error deleting credential %s for user %s: %s", credential_id, user_id, e, exc_info=True)
        log_error_with_context(
            e,
            context={"credential_id": credential_id, "user_id": user_id},
            operation="delete_credential_by_id"
        )
        raise RuntimeError(f"Failed to delete credential: {str(e)}") from e