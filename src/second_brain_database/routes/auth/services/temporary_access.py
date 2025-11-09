"""
Temporary access token management for IP and User Agent lockdown "allow once" functionality.

This module provides functions to generate, validate, and manage temporary access tokens
that allow users to bypass IP and User Agent lockdown restrictions for a limited time
or add IPs/User Agents to their trusted list via email action buttons.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
from typing import Any, Dict, Optional

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import log_performance, log_security_event

logger = get_logger(prefix="[Temporary Access]")

# Token expiration times
ALLOW_ONCE_DURATION_MINUTES = 15  # Allow once tokens expire in 15 minutes
ADD_TO_TRUSTED_DURATION_MINUTES = 60  # Add to trusted tokens expire in 1 hour

# Redis key prefixes
REDIS_IP_TOKEN_PREFIX = "temp_ip_token"
REDIS_USER_AGENT_TOKEN_PREFIX = "temp_ua_token"


@log_performance("store_token_in_redis")
async def store_token_in_redis(
    token_hash: str, token_data: Dict[str, Any], expiration_minutes: int, prefix: str
) -> None:
    """
    Store a temporary access token in Redis with automatic expiration.

    Args:
        token_hash (str): The hashed token to use as key
        token_data (Dict[str, Any]): Token data to store
        expiration_minutes (int): Minutes until token expires
        prefix (str): Redis key prefix
    """
    redis_conn = await redis_manager.get_redis()
    key = f"{prefix}:{token_hash}"
    value = json.dumps(token_data)
    expiration_seconds = expiration_minutes * 60

    await redis_conn.set(key, value, ex=expiration_seconds)
    logger.debug("Stored token in Redis with key %s, expires in %d minutes", key[:20] + "...", expiration_minutes)


@log_performance("get_token_from_redis")
async def get_token_from_redis(token_hash: str, prefix: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve and delete a temporary access token from Redis.

    Args:
        token_hash (str): The hashed token to retrieve
        prefix (str): Redis key prefix

    Returns:
        Optional[Dict[str, Any]]: Token data if found, None otherwise
    """
    redis_conn = await redis_manager.get_redis()
    key = f"{prefix}:{token_hash}"

    # Get and delete the token in one operation (single use)
    value = await redis_conn.getdel(key)

    if not value:
        logger.debug("Token not found or expired in Redis: %s", key[:20] + "...")
        return None

    try:
        token_data = json.loads(value)
        logger.debug("Retrieved and deleted token from Redis: %s", key[:20] + "...")
        return token_data
    except json.JSONDecodeError:
        logger.error("Failed to decode token data from Redis: %s", key[:20] + "...")
        return None


@log_performance("generate_temporary_ip_access_token")
async def generate_temporary_ip_access_token(user_email: str, ip_address: str, action: str, endpoint: str) -> str:
    """
    Generate a temporary access token for IP-based actions.

    Args:
        user_email (str): User's email address
        ip_address (str): IP address for the token
        action (str): Action type ("allow_once" or "add_to_trusted")
        endpoint (str): The endpoint that was blocked

    Returns:
        str: The generated token
    """
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Set expiration based on action type
    if action == "allow_once":
        expiration_minutes = ALLOW_ONCE_DURATION_MINUTES
    elif action == "add_to_trusted":
        expiration_minutes = ADD_TO_TRUSTED_DURATION_MINUTES
    else:
        raise ValueError(f"Invalid action type: {action}")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)

    # Create token data
    token_data = {
        "user_email": user_email,
        "ip_address": ip_address,
        "action": action,
        "endpoint": endpoint,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    # Store token in Redis with automatic expiration
    await store_token_in_redis(token_hash, token_data, expiration_minutes, REDIS_IP_TOKEN_PREFIX)

    # Log token generation
    log_security_event(
        event_type="temporary_ip_token_generated",
        user_id=user_email,
        ip_address=ip_address,
        success=True,
        details={
            "action": action,
            "endpoint": endpoint,
            "expires_at": expires_at.isoformat(),
            "token_hash": token_hash[:8] + "...",  # Log only first 8 chars for security
        },
    )

    logger.info("Generated temporary IP access token for user %s, IP %s, action %s", user_email, ip_address, action)

    return token


@log_performance("validate_and_use_temporary_ip_token")
async def validate_and_use_temporary_ip_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate and use a temporary IP access token (single use).

    Args:
        token (str): The token to validate

    Returns:
        Optional[Dict[str, Any]]: Token data if valid, None if invalid/expired/used
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Get token from Redis (this also deletes it for single use)
    token_data = await get_token_from_redis(token_hash, REDIS_IP_TOKEN_PREFIX)

    if not token_data:
        logger.warning("Invalid or expired temporary IP access token: %s", token_hash[:8] + "...")
        return None

    # Log token usage
    log_security_event(
        event_type="temporary_ip_token_used",
        user_id=token_data.get("user_email"),
        ip_address=token_data.get("ip_address"),
        success=True,
        details={
            "action": token_data.get("action"),
            "endpoint": token_data.get("endpoint"),
            "token_hash": token_hash[:8] + "...",
        },
    )

    logger.info(
        "Used temporary IP access token for user %s, action %s", token_data.get("user_email"), token_data.get("action")
    )

    return token_data


@log_performance("execute_allow_once_ip_access")
async def execute_allow_once_ip_access(token_data: Dict[str, Any]) -> bool:
    """
    Execute the "allow once" action for an IP address.

    This creates a temporary bypass that allows the IP to access the account
    for a limited time without adding it to the permanent trusted list.

    Args:
        token_data (Dict[str, Any]): Validated token data

    Returns:
        bool: True if successful, False otherwise
    """
    user_email = token_data.get("user_email")
    ip_address = token_data.get("ip_address")

    if not user_email or not ip_address:
        logger.error("Invalid token data for allow once action: %s", token_data)
        return False

    # Create a temporary bypass entry (this could be implemented as a Redis entry
    # or a special field in the user document that the lockdown check respects)
    # For now, we'll add it as a temporary entry that the security manager can check

    bypass_entry = {
        "ip_address": ip_address,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=ALLOW_ONCE_DURATION_MINUTES)).isoformat(),
        "reason": "allow_once_token",
    }

    users_collection = db_manager.get_collection("users")
    result = await users_collection.update_one(
        {"email": user_email}, {"$push": {"temporary_ip_bypasses": bypass_entry}}
    )

    if result.modified_count == 0:
        logger.error("Failed to create temporary IP bypass for user %s", user_email)
        return False

    # Log the action
    log_security_event(
        event_type="ip_allow_once_executed",
        user_id=user_email,
        ip_address=ip_address,
        success=True,
        details={"expires_at": bypass_entry["expires_at"], "endpoint": token_data.get("endpoint")},
    )

    logger.info("Created temporary IP bypass for user %s, IP %s", user_email, ip_address)
    return True


@log_performance("execute_add_to_trusted_ip_list")
async def execute_add_to_trusted_ip_list(token_data: Dict[str, Any]) -> bool:
    """
    Execute the "add to trusted list" action for an IP address.

    Args:
        token_data (Dict[str, Any]): Validated token data

    Returns:
        bool: True if successful, False otherwise
    """
    user_email = token_data.get("user_email")
    ip_address = token_data.get("ip_address")

    if not user_email or not ip_address:
        logger.error("Invalid token data for add to trusted action: %s", token_data)
        return False

    # Add IP to trusted list
    users_collection = db_manager.get_collection("users")

    # First check if IP is already in trusted list
    user = await users_collection.find_one({"email": user_email})
    if not user:
        logger.error("User not found for add to trusted action: %s", user_email)
        return False

    trusted_ips = user.get("trusted_ips", [])
    if ip_address in trusted_ips:
        logger.info("IP %s already in trusted list for user %s", ip_address, user_email)
        return True

    # Add IP to trusted list
    result = await users_collection.update_one({"email": user_email}, {"$addToSet": {"trusted_ips": ip_address}})

    if result.modified_count == 0:
        logger.error("Failed to add IP to trusted list for user %s", user_email)
        return False

    # Log the action
    log_security_event(
        event_type="ip_added_to_trusted_via_token",
        user_id=user_email,
        ip_address=ip_address,
        success=True,
        details={
            "endpoint": token_data.get("endpoint"),
            "previous_trusted_count": len(trusted_ips),
            "new_trusted_count": len(trusted_ips) + 1,
        },
    )

    logger.info("Added IP %s to trusted list for user %s via token", ip_address, user_email)
    return True


# User Agent temporary access functions


@log_performance("generate_temporary_user_agent_access_token")
async def generate_temporary_user_agent_access_token(
    user_email: str, user_agent: str, action: str, endpoint: str
) -> str:
    """
    Generate a temporary access token for User Agent-based actions.

    Args:
        user_email (str): User's email address
        user_agent (str): User Agent string for the token
        action (str): Action type ("allow_once" or "add_to_trusted")
        endpoint (str): The endpoint that was blocked

    Returns:
        str: The generated token
    """
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Set expiration based on action type
    if action == "allow_once":
        expiration_minutes = ALLOW_ONCE_DURATION_MINUTES
    elif action == "add_to_trusted":
        expiration_minutes = ADD_TO_TRUSTED_DURATION_MINUTES
    else:
        raise ValueError(f"Invalid action type: {action}")

    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)

    # Create token data
    token_data = {
        "user_email": user_email,
        "user_agent": user_agent,
        "action": action,
        "endpoint": endpoint,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    # Store token in Redis with automatic expiration
    await store_token_in_redis(token_hash, token_data, expiration_minutes, REDIS_USER_AGENT_TOKEN_PREFIX)

    # Log token generation
    log_security_event(
        event_type="temporary_user_agent_token_generated",
        user_id=user_email,
        success=True,
        details={
            "user_agent": user_agent,
            "action": action,
            "endpoint": endpoint,
            "expires_at": expires_at.isoformat(),
            "token_hash": token_hash[:8] + "...",  # Log only first 8 chars for security
        },
    )

    logger.info(
        "Generated temporary User Agent access token for user %s, User Agent %s, action %s",
        user_email,
        user_agent[:50] + "..." if len(user_agent) > 50 else user_agent,
        action,
    )

    return token


@log_performance("validate_and_use_temporary_user_agent_token")
async def validate_and_use_temporary_user_agent_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Validate and use a temporary User Agent access token (single use).

    Args:
        token (str): The token to validate

    Returns:
        Optional[Dict[str, Any]]: Token data if valid, None if invalid/expired/used
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Get token from Redis (this also deletes it for single use)
    token_data = await get_token_from_redis(token_hash, REDIS_USER_AGENT_TOKEN_PREFIX)

    if not token_data:
        logger.warning("Invalid or expired temporary User Agent access token: %s", token_hash[:8] + "...")
        return None

    # Log token usage
    log_security_event(
        event_type="temporary_user_agent_token_used",
        user_id=token_data.get("user_email"),
        success=True,
        details={
            "user_agent": token_data.get("user_agent"),
            "action": token_data.get("action"),
            "endpoint": token_data.get("endpoint"),
            "token_hash": token_hash[:8] + "...",
        },
    )

    logger.info(
        "Used temporary User Agent access token for user %s, action %s",
        token_data.get("user_email"),
        token_data.get("action"),
    )

    return token_data


@log_performance("execute_allow_once_user_agent_access")
async def execute_allow_once_user_agent_access(token_data: Dict[str, Any]) -> bool:
    """
    Execute the "allow once" action for a User Agent.

    This creates a temporary bypass that allows the User Agent to access the account
    for a limited time without adding it to the permanent trusted list.

    Args:
        token_data (Dict[str, Any]): Validated token data

    Returns:
        bool: True if successful, False otherwise
    """
    user_email = token_data.get("user_email")
    user_agent = token_data.get("user_agent")

    if not user_email or not user_agent:
        logger.error("Invalid token data for allow once action: %s", token_data)
        return False

    # Create a temporary bypass entry
    bypass_entry = {
        "user_agent": user_agent,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=ALLOW_ONCE_DURATION_MINUTES)).isoformat(),
        "reason": "allow_once_token",
    }

    users_collection = db_manager.get_collection("users")
    result = await users_collection.update_one(
        {"email": user_email}, {"$push": {"temporary_user_agent_bypasses": bypass_entry}}
    )

    if result.modified_count == 0:
        logger.error("Failed to create temporary User Agent bypass for user %s", user_email)
        return False

    # Log the action
    log_security_event(
        event_type="user_agent_allow_once_executed",
        user_id=user_email,
        success=True,
        details={
            "user_agent": user_agent,
            "expires_at": bypass_entry["expires_at"],
            "endpoint": token_data.get("endpoint"),
        },
    )

    logger.info(
        "Created temporary User Agent bypass for user %s, User Agent %s",
        user_email,
        user_agent[:50] + "..." if len(user_agent) > 50 else user_agent,
    )
    return True


@log_performance("execute_add_to_trusted_user_agent_list")
async def execute_add_to_trusted_user_agent_list(token_data: Dict[str, Any]) -> bool:
    """
    Execute the "add to trusted list" action for a User Agent.

    Args:
        token_data (Dict[str, Any]): Validated token data

    Returns:
        bool: True if successful, False otherwise
    """
    user_email = token_data.get("user_email")
    user_agent = token_data.get("user_agent")

    if not user_email or not user_agent:
        logger.error("Invalid token data for add to trusted action: %s", token_data)
        return False

    # Add User Agent to trusted list
    users_collection = db_manager.get_collection("users")

    # First check if User Agent is already in trusted list
    user = await users_collection.find_one({"email": user_email})
    if not user:
        logger.error("User not found for add to trusted action: %s", user_email)
        return False

    trusted_user_agents = user.get("trusted_user_agents", [])
    if user_agent in trusted_user_agents:
        logger.info("User Agent already in trusted list for user %s", user_email)
        return True

    # Add User Agent to trusted list
    result = await users_collection.update_one(
        {"email": user_email}, {"$addToSet": {"trusted_user_agents": user_agent}}
    )

    if result.modified_count == 0:
        logger.error("Failed to add User Agent to trusted list for user %s", user_email)
        return False

    # Log the action
    log_security_event(
        event_type="user_agent_added_to_trusted_via_token",
        user_id=user_email,
        success=True,
        details={
            "user_agent": user_agent,
            "endpoint": token_data.get("endpoint"),
            "previous_trusted_count": len(trusted_user_agents),
            "new_trusted_count": len(trusted_user_agents) + 1,
        },
    )

    logger.info("Added User Agent to trusted list for user %s via token", user_email)
    return True
