"""
Utilities for Redis operations related to authentication and security.
"""

import json
import secrets
from typing import Any, Dict, List, Optional, Tuple, TypedDict

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

logger = get_logger(prefix="[Auth Service Utils Redis]")
security_logger = SecurityLogger(prefix="[REDIS-UTILS-SECURITY]")
db_logger = DatabaseLogger(prefix="[REDIS-UTILS-DB]")

BACKUP_CODES_REDIS_PREFIX: str = "2fa:backup_codes:"
BACKUP_CODES_PENDING_TIME: int = getattr(settings, "BACKUP_CODES_PENDING_TIME", 600)
ABUSE_ACTION_TOKEN_EXPIRY: int = getattr(settings, "ABUSE_ACTION_TOKEN_EXPIRY", 1800)
USERNAME_EXISTS_PREFIX: str = "username:exists:"
USERNAME_DEMAND_PREFIX: str = "username:demand:"
USERNAME_DEMAND_EXPIRY: int = 86400  # 1 day in seconds
USERNAME_EXISTS_EXPIRY: int = 3600  # 1 hour in seconds
ABUSE_ACTION_TOKEN_PREFIX: str = "abuse:reset:action:"
TOP_DEMAND_DEFAULT: int = 10


class AbuseActionTokenData(TypedDict):
    email: str
    ip: str
    action: str


def _get_username_exists_key(username: str) -> str:
    return f"{USERNAME_EXISTS_PREFIX}{username.lower()}"


def _get_username_demand_key(username: str) -> str:
    return f"{USERNAME_DEMAND_PREFIX}{username.lower()}"


def _get_backup_codes_key(username: str) -> str:
    return f"{BACKUP_CODES_REDIS_PREFIX}{username}"


def _get_abuse_action_token_key(token: str) -> str:
    return f"{ABUSE_ACTION_TOKEN_PREFIX}{token}"


@log_performance("redis_check_username")
async def redis_check_username(username: str) -> bool:
    """
    Check if a username exists, using Redis cache and falling back to DB.
    Args:
        username: The username to check.
    Returns:
        True if exists, False otherwise.
    Side-effects:
        Updates Redis cache.
    """
    logger.debug("Checking username existence: %s", username)

    redis_conn = await redis_manager.get_redis()
    key = _get_username_exists_key(username)

    try:
        # Try cache first
        cached = await redis_conn.get(key)
        if cached is not None:
            exists = cached == "1"
            logger.debug("Username '%s' existence found in cache: %s", username, exists)

            log_security_event(
                event_type="username_check_cache_hit",
                user_id=username,
                success=True,
                details={"exists": exists, "source": "redis_cache"},
            )

            return exists

        # Cache miss - check database
        logger.debug("Cache miss for username '%s', checking database", username)
        user = await db_manager.get_collection("users").find_one({"username": username.lower()})
        exists = user is not None

        log_database_operation(
            operation="check_username_exists",
            collection="users",
            query={"username": username.lower()},
            result={"exists": exists},
        )

        # Update cache
        await redis_conn.set(key, "1" if exists else "0", ex=USERNAME_EXISTS_EXPIRY)

        logger.info("Username '%s' checked in DB, exists: %s", username, exists)

        log_security_event(
            event_type="username_check_database",
            user_id=username,
            success=True,
            details={"exists": exists, "source": "database", "cached": True},
        )

        return exists

    except (AttributeError, TypeError, ValueError) as e:
        logger.error("Error checking username '%s' existence: %s", username, e, exc_info=True)
        log_error_with_context(e, context={"username": username}, operation="redis_check_username")
        return False


async def redis_incr_username_demand(username: str) -> None:
    """
    Increment the demand counter for a username in Redis.
    Args:
        username: The username to increment demand for.
    Side-effects:
        Updates Redis counter and expiry.
    """
    redis_conn = await redis_manager.get_redis()
    key = _get_username_demand_key(username)
    try:
        await redis_conn.incr(key)
        await redis_conn.expire(key, USERNAME_DEMAND_EXPIRY)
        logger.debug("Incremented demand for username '%s'", username)
    except (AttributeError, TypeError, ValueError) as e:
        logger.error("Error incrementing demand for username '%s': %s", username, e, exc_info=True)


async def redis_get_top_demanded_usernames(top_n: int = TOP_DEMAND_DEFAULT) -> List[Tuple[str, int]]:
    """
    Get the top N most demanded usernames from Redis.
    Args:
        top_n: Number of top usernames to return.
    Returns:
        List of (username, demand count) tuples.
    """
    redis_conn = await redis_manager.get_redis()
    pattern = f"{USERNAME_DEMAND_PREFIX}*"
    result: List[Tuple[str, int]] = []
    try:
        keys = await redis_conn.keys(pattern)
        for key in keys:
            try:
                count = await redis_conn.get(key)
                uname = key.split(":", 2)[-1]
                result.append((uname, int(count)))
            except (ValueError, TypeError) as e:
                logger.warning("Malformed demand count for key '%s': %s", key, e)
        result.sort(key=lambda x: x[1], reverse=True)
        logger.debug("Top demanded usernames: %s", result[:top_n])
        return result[:top_n]
    except (AttributeError, TypeError, ValueError) as e:
        logger.error("Error retrieving top demanded usernames: %s", e, exc_info=True)
        return []


async def store_backup_codes_temp(username: str, codes: List[str]) -> None:
    """
    Store backup codes for a user temporarily in Redis.
    Args:
        username: The username.
        codes: List of backup codes.
    Side-effects:
        Stores codes in Redis with expiry.
    """
    redis_conn = await redis_manager.get_redis()
    key = _get_backup_codes_key(username)
    try:
        await redis_conn.set(key, json.dumps(codes), ex=BACKUP_CODES_PENDING_TIME)
        logger.debug("Stored backup codes for '%s' in Redis", username)
    except (TypeError, ValueError) as e:
        logger.error("Error storing backup codes for '%s': %s", username, e, exc_info=True)


async def get_backup_codes_temp(username: str) -> Optional[List[str]]:
    """
    Retrieve temporary backup codes for a user from Redis.
    Args:
        username: The username.
    Returns:
        List of codes if found, else None.
    """
    redis_conn = await redis_manager.get_redis()
    key = _get_backup_codes_key(username)
    try:
        val = await redis_conn.get(key)
        if val:
            codes = json.loads(val)
            logger.debug("Retrieved backup codes for '%s' from Redis", username)
            return codes
        return None
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Malformed backup codes for '%s': %s", username, e)
        return None


async def delete_backup_codes_temp(username: str) -> None:
    """
    Delete temporary backup codes for a user from Redis.
    Args:
        username: The username.
    Side-effects:
        Removes codes from Redis.
    """
    redis_conn = await redis_manager.get_redis()
    key = _get_backup_codes_key(username)
    try:
        await redis_conn.delete(key)
        logger.debug("Deleted backup codes for '%s' from Redis", username)
    except (AttributeError, TypeError) as e:
        logger.error("Error deleting backup codes for '%s': %s", username, e, exc_info=True)


async def generate_abuse_action_token(
    email: str, ip: str, action: str, expiry_seconds: int = ABUSE_ACTION_TOKEN_EXPIRY
) -> str:
    """
    Generate a secure, single-use, time-limited token for abuse actions.
    Args:
        email: User's email.
        ip: User's IP address.
        action: Action type (e.g., 'whitelist', 'block').
        expiry_seconds: Token expiry in seconds.
    Returns:
        The generated token string.
    Side-effects:
        Stores token data in Redis with expiry.
    """
    redis_conn = await redis_manager.get_redis()
    token = secrets.token_urlsafe(32)
    key = _get_abuse_action_token_key(token)
    data: AbuseActionTokenData = {"email": email, "ip": ip, "action": action}
    try:
        await redis_conn.set(key, json.dumps(data), ex=expiry_seconds)
        logger.debug("Generated abuse action token for '%s' action '%s'", email, action)
        return token
    except (TypeError, ValueError) as e:
        logger.error("Error generating abuse action token for '%s': %s", email, e, exc_info=True)
        raise


async def consume_abuse_action_token(token: str, expected_action: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate and consume a single-use abuse action token.
    Args:
        token: The token string.
        expected_action: The expected action type.
    Returns:
        (email, ip) if valid, else (None, None).
    Side-effects:
        Deletes token from Redis if valid.
    """
    redis_conn = await redis_manager.get_redis()
    key = _get_abuse_action_token_key(token)
    try:
        val = await redis_conn.get(key)
        if not val:
            logger.info("Abuse action token '%s' not found or expired", token)
            return None, None
        try:
            data: Dict[str, Any] = json.loads(val)
        except json.JSONDecodeError as e:
            logger.warning("Malformed abuse action token data for '%s': %s", token, e)
            return None, None
        if data.get("action") != expected_action:
            logger.info("Abuse action token '%s' action mismatch", token)
            return None, None
        email = data.get("email")
        ip = data.get("ip")
        await redis_conn.delete(key)
        logger.debug("Consumed abuse action token for '%s' action '%s'", email, expected_action)
        return email, ip
    except (TypeError, ValueError) as e:
        logger.error("Error consuming abuse action token '%s': %s", token, e, exc_info=True)
        return None, None
