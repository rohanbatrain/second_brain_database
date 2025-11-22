"""
User registration and verification utilities for authentication workflows.

This module provides async functions for registering users, sending welcome and suspension emails,
and verifying user emails. All email sending is logged and instrumented for production.
"""

from datetime import datetime
import secrets
from typing import Any, Dict, Optional, Tuple

import bcrypt
from fastapi import HTTPException, status

from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.models import UserIn, validate_password_strength
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

logger = get_logger(prefix="[Auth Service Registration]")
security_logger = SecurityLogger(prefix="[AUTH-REG-SECURITY]")
db_logger = DatabaseLogger(prefix="[AUTH-REG-DB]")


@log_performance("register_user", log_args=False)
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
    logger.info("Registration attempt for username: %s, email: %s", user.username, user.email)

    # Log security event for registration attempt
    log_security_event(
        event_type="registration_attempt",
        user_id=user.username,
        success=False,  # Will be updated to True on success
        details={
            "username": user.username,
            "email": user.email,
            "plan": user.plan,
            "team": user.team,
            "role": user.role,
            "client_side_encryption": user.client_side_encryption,
        },
    )

    # Additional security logging for plan validation bypass attempts
    if user.plan and user.plan.lower() != "free":
        logger.warning("Plan validation bypass attempt detected: user=%s requested plan=%s", user.username, user.plan)
        log_security_event(
            event_type="registration_plan_bypass_attempt",
            user_id=user.username,
            success=False,
            details={
                "username": user.username,
                "email": user.email,
                "attempted_plan": user.plan,
                "allowed_plan": "free",
            },
        )

    # Validate username format and reserved prefixes using comprehensive validation
    from second_brain_database.managers.family_manager import family_manager

    is_valid, error_message = await family_manager.validate_username_against_reserved_prefixes(user.username)
    if not is_valid:
        logger.info("Username validation failed: %s for username=%s", error_message, user.username)
        log_security_event(
            event_type="registration_reserved_username",
            user_id=user.username,
            success=False,
            details={"username": user.username, "email": user.email, "reason": error_message},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_message,
        )

    # Validate password strength
    if not validate_password_strength(user.password):
        logger.info("Password strength validation failed for username=%s", user.username)
        log_security_event(
            event_type="registration_weak_password",
            user_id=user.username,
            success=False,
            details={"username": user.username, "email": user.email},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain "
            "uppercase, lowercase, digit, and special character",
        )

    # Check for existing user
    logger.debug("Checking for existing user with username: %s or email: %s", user.username, user.email)
    existing_user = await db_manager.get_collection("users").find_one(
        {"$or": [{"username": user.username}, {"email": user.email}]}
    )
    if existing_user:
        logger.info("Registration failed: username or email already exists (%s, %s)", user.username, user.email)
        log_security_event(
            event_type="registration_duplicate_user",
            user_id=user.username,
            success=False,
            details={
                "username": user.username,
                "email": user.email,
                "existing_username": existing_user.get("username"),
                "existing_email": existing_user.get("email"),
            },
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or email already exists")
    # Create user document
    logger.debug("Creating user document for username: %s", user.username)
    hashed_pw = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    verification_token = secrets.token_urlsafe(32)
    
    # Import settings for default tenant
    from second_brain_database.config import settings
    
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
        "client_side_encryption": user.client_side_encryption,
        # Multi-tenancy fields
        "primary_tenant_id": settings.DEFAULT_TENANT_ID,
        "tenant_memberships": [
            {
                "tenant_id": settings.DEFAULT_TENANT_ID,
                "role": "member",
                "joined_at": datetime.utcnow(),
            }
        ],
        # User Agent lockdown fields (default disabled)
        "trusted_user_agent_lockdown": False,
        "trusted_user_agents": [],
        "trusted_user_agent_lockdown_codes": [],
        # Temporary access tracking fields for "allow once" functionality
        "temporary_ip_access_tokens": [],
        "temporary_user_agent_access_tokens": [],
        "temporary_ip_bypasses": [],
        # SBD Token fields
        "sbd_tokens": 0,
        "sbd_tokens_transactions": [],
    }

    # Insert user into database
    logger.debug("Inserting user into database: %s", user.username)
    result = await db_manager.get_collection("users").insert_one(user_doc)
    if not result.inserted_id:
        logger.error("Failed to create user: %s", user.username)
        log_error_with_context(
            RuntimeError("Database insert failed"),
            context={"username": user.username, "email": user.email},
            operation="register_user",
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create user")

    # Log successful registration
    logger.info("User registered successfully: %s", user.username)
    log_security_event(
        event_type="registration_success",
        user_id=user.username,
        success=True,
        details={"username": user.username, "email": user.email, "plan": user.plan, "user_id": str(result.inserted_id)},
    )

    return user_doc, verification_token


@log_performance("send_welcome_email")
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


@log_performance("verify_user_email")
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
        {"_id": user["_id"]}, {"$set": {"is_verified": True}, "$unset": {"verification_token": ""}}
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
