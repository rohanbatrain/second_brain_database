"""
Verification email utilities for authentication workflows.

This module provides async functions for sending and resending verification emails,
with rate limiting and production-grade logging.
"""
import secrets
from typing import Optional, Dict
from fastapi import HTTPException
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Service Verification]")

RATE_LIMIT_SECONDS: int = 60
MAX_VERIFICATION_EMAILS: int = 2
MAX_COMBINED_EMAILS: int = 3

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
    await email_manager.send_verification_email(email, verification_link, username=username)

async def resend_verification_email_service(
    email: Optional[str] = None,
    username: Optional[str] = None,
    base_url: Optional[str] = None
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
    if not email and not username:
        logger.warning("Resend verification called without email or username.")
        raise HTTPException(status_code=400, detail="Email or username required.")
    user = None
    identifier = email or username
    try:
        redis_conn = await redis_manager.get_redis()
        rv_key = f"resend_verification:{identifier}"
        combined_key = f"combined_reset_verify:{identifier}"
        rv_count = await redis_conn.incr(rv_key)
        if rv_count == 1:
            await redis_conn.expire(rv_key, RATE_LIMIT_SECONDS)
        combined_count = await redis_conn.incr(combined_key)
        if combined_count == 1:
            await redis_conn.expire(combined_key, RATE_LIMIT_SECONDS)
        if rv_count > MAX_VERIFICATION_EMAILS or combined_count > MAX_COMBINED_EMAILS:
            logger.warning("Verification email rate limited for %s", identifier)
            return {"message": "Verification email did not sent"}
        if email:
            user = await db_manager.get_collection("users").find_one({"email": email})
        elif username:
            user = await db_manager.get_collection("users").find_one({"username": username})
        if not user:
            logger.info("Verification email requested for non-existent user: %s", identifier)
            return {"message": "Verification email sent"}
        if user.get("is_verified", False):
            logger.info("Account already verified for user: %s", identifier)
            return {"message": "Account already verified"}
        verification_token = secrets.token_urlsafe(32)
        await db_manager.get_collection("users").update_one(
            {"_id": user["_id"]},
            {"$set": {"verification_token": verification_token}}
        )
        verification_link = f"{base_url}auth/verify-email?token={verification_token}"
        logger.info("Verification link (resend): %s", verification_link)
        await send_verification_email(user["email"],
                                      verification_link, username=user.get("username"))
        return {"message": "Verification email sent"}
    except (TypeError, ValueError, RuntimeError, KeyError) as exc:
        logger.error("Failed to resend verification email for %s: %s",
                     identifier, exc, exc_info=True)
        return {"message": "Verification email did not sent"}
