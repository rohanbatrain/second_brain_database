"""
User registration and verification utilities for authentication workflows.

This module provides async functions for registering users, sending welcome and suspension emails,
and verifying user emails. All email sending is logged and instrumented for production.
"""
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
import secrets
from fastapi import HTTPException, status
import bcrypt
from second_brain_database.routes.auth.models import UserIn, validate_password_strength
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Auth Service Registration]")

async def register_user(user: UserIn) -> Tuple[Dict[str, Any], str]:
    """
    Register a new user, validate password, and return user doc and verification token.

    Args:
        user (UserIn): User registration input model.

    Returns:
        Tuple[Dict[str, Any], str]: The user document and verification token.

    Raises:
        HTTPException: If validation fails or user already exists.
    """
    if not validate_password_strength(user.password):
        logger.info("Password strength validation failed for username=%s", user.username)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain "
                   "uppercase, lowercase, digit, and special character"
        )
    existing_user = await db_manager.get_collection("users").find_one({
        "$or": [
            {"username": user.username},
            {"email": user.email}
        ]
    })
    if existing_user:
        logger.info("Registration failed: username or email already exists (%s, %s)", user.username, user.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )
    hashed_pw = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    verification_token = secrets.token_urlsafe(32)
    user_doc = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_pw,
        "created_at": datetime.utcnow(),
        "is_active": True,
        "failed_login_attempts": 0,
        "last_login": None,
        "is_verified": False,
        "verification_token": verification_token,
        "plan": user.plan,
        "team": user.team,
        "role": user.role,
        "client_side_encryption": user.client_side_encryption
    }
    result = await db_manager.get_collection("users").insert_one(user_doc)
    if not result.inserted_id:
        logger.error("Failed to create user: %s", user.username)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    logger.info("User registered: %s", user.username)
    return user_doc, verification_token

async def send_welcome_email(email: str, username: Optional[str] = None) -> None:
    """
    Send a personalized welcome email after user verifies their email.

    Args:
        email (str): The user's email address.
        username (Optional[str]): The user's username.

    Side Effects:
        Sends an email to the user.
    """
    subject = "Welcome to Second Brain Database!"
    display_name = username or "there"
    html_content = f"""
    <html><body>
    <h2>Hey {display_name}, welcome and thank you for verifying your email!</h2>
    <p>We’re excited to have you join the Second Brain Database community. Your account is now fully active, and you can start exploring all the features we offer to help you organize, secure, and supercharge your knowledge.</p>
    <p>If you have any questions or need assistance, our team is here to help. Wishing you a productive and inspiring journey with us!</p>
    <br>
    <p>Best regards,<br>The Second Brain Database Team</p>
    </body></html>
    """
    logger.info("[WELCOME EMAIL] To: %s | Subject: %s", email, subject)
    await email_manager._send_via_console(email, subject, html_content)

async def verify_user_email(token: str) -> Dict[str, Any]:
    """
    Verify a user's email using the provided token and send a welcome email.

    Args:
        token (str): The verification token.

    Returns:
        Dict[str, Any]: The user document after verification.

    Raises:
        HTTPException: If the token is invalid or expired.
    """
    user = await db_manager.get_collection("users").find_one({"verification_token": token})
    if not user:
        logger.warning("Invalid or expired verification token: %s", token)
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True}, "$unset": {"verification_token": ""}}
    )
    await send_welcome_email(user["email"], user.get("username"))
    logger.info("User email verified: %s", user.get("username"))
    return user

async def send_account_suspension_email(email: str, username: Optional[str] = None) -> None:
    """
    Optionally notify the user by email when their account is suspended for abuse.

    Args:
        email (str): The user's email address.
        username (Optional[str]): The user's username.

    Side Effects:
        Sends an email to the user.
    """
    subject = "Account Suspended Due to Abuse"
    display_name = username or "user"
    html_content = f"""
    <html><body>
    <h2>Account Suspended</h2>
    <p>Dear {display_name},</p>
    <p>Your account has been suspended due to repeated abuse of the password reset system. If you believe this is a mistake, please contact support for review and possible reactivation.</p>
    <p>Thank you,<br>The Second Brain Database Team</p>
    </body></html>
    """
    logger.info("[SUSPEND EMAIL] To: %s | Subject: %s", email, subject)
    await email_manager._send_via_console(email, subject, html_content)

