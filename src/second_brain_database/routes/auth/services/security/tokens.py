"""
Token blacklisting utilities for authentication security.

This module provides async functions to blacklist tokens and check if a token or user is blacklisted.
It uses Redis for persistence and is instrumented with production-grade logging and error handling.
"""
from typing import Optional
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Service Security Tokens]")

BLACKLIST_USER_EXPIRY: int = 60 * 60 * 24 * 7  # 7 days
BLACKLIST_TOKEN_EXPIRY: int = 60 * 60 * 24     # 1 day

async def blacklist_token(user_id: Optional[str] = None, token: Optional[str] = None) -> None:
    """
    Blacklist all tokens for a user (by user_id) or a specific token.
    Uses Redis for production-ready persistence and multi-instance support.

    Args:
        user_id (Optional[str]): The user's ID to blacklist.
        token (Optional[str]): The specific token to blacklist.

    Side Effects:
        Writes to Redis. Logs actions and errors.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        if user_id is not None:
            await redis_conn.set(f"blacklist:user:{user_id}", "1", ex=BLACKLIST_USER_EXPIRY)
            logger.info("Blacklisted all tokens for user_id=%s", user_id)
        if token is not None:
            await redis_conn.set(f"blacklist:token:{token}", "1", ex=BLACKLIST_TOKEN_EXPIRY)
            logger.info("Blacklisted token: %s", token)
    except (TypeError, ValueError, RuntimeError, KeyError) as exc:
        logger.error("Failed to blacklist token or user: %s", exc, exc_info=True)

async def is_token_blacklisted(token: str, user_id: Optional[str] = None) -> bool:
    """
    Check if a token or user is blacklisted.

    Args:
        token (str): The token to check.
        user_id (Optional[str]): The user ID to check.

    Returns:
        bool: True if blacklisted, False otherwise.

    Side Effects:
        Reads from Redis. Logs errors.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        if user_id:
            if await redis_conn.get(f"blacklist:user:{user_id}"):
                logger.debug("User %s is blacklisted", user_id)
                return True
        if await redis_conn.get(f"blacklist:token:{token}"):
            logger.debug("Token is blacklisted: %s", token)
            return True
        return False
    except (TypeError, ValueError, RuntimeError, KeyError) as exc:
        logger.error("Failed to check token blacklist: %s", exc, exc_info=True)
        return False
