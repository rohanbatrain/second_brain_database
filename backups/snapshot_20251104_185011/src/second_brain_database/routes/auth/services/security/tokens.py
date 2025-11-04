"""
Token blacklisting utilities for authentication security.

This module provides async functions to blacklist tokens and check if a token or user is blacklisted.
It uses Redis for persistence and is instrumented with production-grade logging and error handling.
"""

from typing import Optional

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import (
    SecurityLogger,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Auth Service Security Tokens]")
security_logger = SecurityLogger(prefix="[TOKEN-BLACKLIST-SECURITY]")

BLACKLIST_USER_EXPIRY: int = 60 * 60 * 24 * 7  # 7 days
BLACKLIST_TOKEN_EXPIRY: int = 60 * 60 * 24  # 1 day


@log_performance("blacklist_token")
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
    if not user_id and not token:
        logger.warning("Blacklist token called without user_id or token")
        return

    logger.info("Blacklisting tokens - user_id: %s, token: %s", user_id or "None", "provided" if token else "None")

    try:
        redis_conn = await redis_manager.get_redis()

        if user_id is not None:
            key = f"blacklist:user:{user_id}"
            await redis_conn.set(key, "1", ex=BLACKLIST_USER_EXPIRY)

            logger.info(
                "Successfully blacklisted all tokens for user_id=%s (expires in %d seconds)",
                user_id,
                BLACKLIST_USER_EXPIRY,
            )

            log_security_event(
                event_type="user_tokens_blacklisted",
                user_id=user_id,
                success=True,
                details={
                    "blacklist_type": "user_all_tokens",
                    "expiry_seconds": BLACKLIST_USER_EXPIRY,
                    "redis_key": key,
                },
            )

        if token is not None:
            # Only log partial token for security
            token_preview = token[:8] + "..." if len(token) > 8 else token
            key = f"blacklist:token:{token}"
            await redis_conn.set(key, "1", ex=BLACKLIST_TOKEN_EXPIRY)

            logger.info(
                "Successfully blacklisted specific token: %s (expires in %d seconds)",
                token_preview,
                BLACKLIST_TOKEN_EXPIRY,
            )

            log_security_event(
                event_type="specific_token_blacklisted",
                user_id=user_id or "unknown",
                success=True,
                details={
                    "blacklist_type": "specific_token",
                    "token_preview": token_preview,
                    "expiry_seconds": BLACKLIST_TOKEN_EXPIRY,
                    "redis_key": key[:20] + "...",  # Partial key for security
                },
            )

    except (TypeError, ValueError, RuntimeError, KeyError) as exc:
        logger.error(
            "Failed to blacklist token or user (user_id=%s, token=%s): %s",
            user_id,
            "provided" if token else "None",
            exc,
            exc_info=True,
        )

        log_error_with_context(
            exc,
            context={
                "user_id": user_id,
                "has_token": bool(token),
                "token_length": len(token) if token else 0,
                "operation_type": "blacklist",
            },
            operation="blacklist_token",
        )

        log_security_event(
            event_type="token_blacklist_error",
            user_id=user_id or "unknown",
            success=False,
            details={
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "has_user_id": bool(user_id),
                "has_token": bool(token),
            },
        )


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
