"""
Verification email utilities for authentication workflows.

This module provides async functions for sending and resending verification emails,
with rate limiting and production-grade logging.
"""

import secrets
from typing import Dict, Optional

from fastapi import HTTPException

from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Auth Service Verification]")
security_logger = SecurityLogger(prefix="[VERIFICATION-SECURITY]")
db_logger = DatabaseLogger(prefix="[VERIFICATION-DB]")

RATE_LIMIT_SECONDS: int = 60
MAX_VERIFICATION_EMAILS: int = 2
MAX_COMBINED_EMAILS: int = 3


@log_performance("send_verification_email")
async def send_verification_email(email: str, verification_link: str, username: Optional[str] = None) -> None:
    """
    Send the verification email using the EmailManager (HTML, multi-provider).

    Args:
        email (str): The user's email address.
        verification_link (str): The verification link to include.
        username (Optional[str]): The user's username.

    Side Effects:
        Sends an email to the user.
    """
    logger.info("Sending verification email to %s for user %s", email, username or "unknown")

    # Log security event for verification email sending
    log_security_event(
        event_type="verification_email_sent",
        user_id=username or email,
        success=True,
        details={"email": email, "username": username, "link_provided": bool(verification_link)},
    )

    try:
        await email_manager.send_verification_email(email, verification_link, username=username)
        logger.info("Successfully sent verification email to %s", email)
    except Exception as e:
        logger.error("Failed to send verification email to %s: %s", email, e, exc_info=True)
        log_error_with_context(e, context={"email": email, "username": username}, operation="send_verification_email")
        raise


@log_performance("resend_verification_email_service")
async def resend_verification_email_service(
    email: Optional[str] = None, username: Optional[str] = None, base_url: Optional[str] = None
) -> Dict[str, str]:
    """
    Resend verification email to a user if not already verified. Accepts email or username.
    Enforces rate limits and does not reveal user existence.

    Args:
        email (Optional[str]): The user's email address.
        username (Optional[str]): The user's username.
        base_url (Optional[str]): The base URL for verification link.

    Returns:
        Dict[str, str]: Message about the result of the operation.

    Raises:
        HTTPException: If neither email nor username is provided.
    """
    identifier = email or username
    logger.info("Resend verification email requested for identifier: %s", identifier)

    if not email and not username:
        logger.warning("Resend verification called without email or username")
        log_security_event(
            event_type="resend_verification_invalid_input",
            user_id="unknown",
            success=False,
            details={"error": "missing_email_username"},
        )
        raise HTTPException(status_code=400, detail="Email or username required.")

    # Log security event for resend verification attempt
    log_security_event(
        event_type="resend_verification_attempt",
        user_id=identifier,
        success=False,  # Will be updated based on outcome
        details={"has_email": bool(email), "has_username": bool(username), "has_base_url": bool(base_url)},
    )

    user = None
    try:
        # Check rate limits
        redis_conn = await redis_manager.get_redis()
        rv_key = f"resend_verification:{identifier}"
        combined_key = f"combined_reset_verify:{identifier}"

        rv_count = await redis_conn.incr(rv_key)
        if rv_count == 1:
            await redis_conn.expire(rv_key, RATE_LIMIT_SECONDS)

        combined_count = await redis_conn.incr(combined_key)
        if combined_count == 1:
            await redis_conn.expire(combined_key, RATE_LIMIT_SECONDS)

        logger.debug("Rate limit check for %s: rv_count=%d, combined_count=%d", identifier, rv_count, combined_count)

        if rv_count > MAX_VERIFICATION_EMAILS or combined_count > MAX_COMBINED_EMAILS:
            logger.warning(
                "Verification email rate limited for %s (rv: %d, combined: %d)", identifier, rv_count, combined_count
            )

            log_security_event(
                event_type="resend_verification_rate_limited",
                user_id=identifier,
                success=False,
                details={
                    "rv_count": rv_count,
                    "combined_count": combined_count,
                    "max_verification": MAX_VERIFICATION_EMAILS,
                    "max_combined": MAX_COMBINED_EMAILS,
                },
            )

            return {"message": "Verification email did not sent"}

        # Find user in database
        if email:
            logger.debug("Looking up user by email: %s", email)
            user = await db_manager.get_collection("users").find_one({"email": email})
        elif username:
            logger.debug("Looking up user by username: %s", username)
            user = await db_manager.get_collection("users").find_one({"username": username})

        logger.info(
            "Database lookup for verification resend - Collection: users, Query: %s, Found: %s",
            {"email" if email else "username": identifier},
            user is not None,
        )

        if not user:
            logger.info("Verification email requested for non-existent user: %s", identifier)
            log_security_event(
                event_type="resend_verification_user_not_found",
                user_id=identifier,
                success=True,  # Success from security perspective (no info leak)
                details={"identifier_type": "email" if email else "username"},
            )
            return {"message": "Verification email sent"}

        # Check if already verified
        if user.get("is_verified", False):
            logger.info("Account already verified for user: %s", identifier)
            log_security_event(
                event_type="resend_verification_already_verified",
                user_id=user.get("username", identifier),
                success=True,
                details={"is_verified": True},
            )
            return {"message": "Account already verified"}

        # Generate new verification token
        verification_token = secrets.token_urlsafe(32)
        logger.debug("Generated new verification token for user: %s", user.get("username", identifier))

        # Update user with new token
        update_result = await db_manager.get_collection("users").update_one(
            {"_id": user["_id"]}, {"$set": {"verification_token": verification_token}}
        )

        logger.info(
            "Database update for verification token - Collection: users, User ID: %s, Modified: %d",
            str(user["_id"]),
            update_result.modified_count,
        )

        if update_result.modified_count == 0:
            logger.error("Failed to update verification token for user: %s", user.get("username", identifier))
            log_error_with_context(
                RuntimeError("Database update failed"),
                context={"user_id": str(user["_id"]), "username": user.get("username")},
                operation="update_verification_token",
            )
            return {"message": "Verification email did not sent"}

        # Create verification link and send email
        verification_link = f"{base_url}auth/verify-email?token={verification_token}"
        logger.info("Generated verification link for user %s: %s", user.get("username", identifier), verification_link)

        await send_verification_email(user["email"], verification_link, username=user.get("username"))

        logger.info("Successfully resent verification email to %s", user["email"])

        log_security_event(
            event_type="resend_verification_success",
            user_id=user.get("username", identifier),
            success=True,
            details={"email": user["email"], "username": user.get("username"), "token_generated": True},
        )

        return {"message": "Verification email sent"}

    except (TypeError, ValueError, RuntimeError, KeyError) as exc:
        logger.error("Failed to resend verification email for %s: %s", identifier, exc, exc_info=True)

        log_error_with_context(
            exc,
            context={"identifier": identifier, "email": email, "username": username, "user_found": user is not None},
            operation="resend_verification_email_service",
        )

        log_security_event(
            event_type="resend_verification_error",
            user_id=identifier,
            success=False,
            details={"error_type": type(exc).__name__, "error_message": str(exc)},
        )

        return {"message": "Verification email did not sent"}
