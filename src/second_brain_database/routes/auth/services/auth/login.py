"""
Authentication login logic for user sign-in, lockout, and 2FA enforcement.

This module provides async functions for user authentication, including password
and 2FA checks, account lockout, and JWT access token creation and validation.
All functions are comprehensively logged for production monitoring and security auditing.
"""

import contextvars
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import bcrypt
from fastapi import HTTPException, status
from jose import jwt
import pyotp

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.services.security.tokens import is_token_blacklisted
from second_brain_database.utils.crypto import decrypt_totp_secret, is_encrypted_totp_secret
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

MAX_FAILED_LOGIN_ATTEMPTS: int = 5

logger = get_logger(prefix="[Auth Service Login]")
security_logger = SecurityLogger(prefix="[AUTH-LOGIN-SECURITY]")
db_logger = DatabaseLogger(prefix="[AUTH-LOGIN-DB]")

request_ip_ctx = contextvars.ContextVar("request_ip", default=None)


@log_performance("get_user_auth_methods")
async def get_user_auth_methods(user_id: str) -> Dict[str, Any]:
    """
    Get available authentication methods for a user.

    Checks what authentication methods are available and returns user preferences.

    Args:
        user_id (str): User ID to check authentication methods for

    Returns:
        Dict[str, Any]: Available authentication methods and preferences
    """
    try:
        # Get user document
        user = await db_manager.get_collection("users").find_one({"_id": user_id})
        if not user:
            return {
                "available_methods": [],
                "preferred_method": None,
                "has_password": False,
                "has_webauthn": False,
                "webauthn_credential_count": 0,
            }

        # Check for password authentication
        has_password = bool(user.get("hashed_password") or user.get("password_hash"))

        # Remove WebAuthn/passkey support
        has_webauthn = False
        available_methods = []
        if has_password:
            available_methods.append("password")
        preferred_method = user.get("preferred_auth_method")
        if preferred_method != "password":
            preferred_method = "password" if has_password else None
        return {
            "available_methods": available_methods,
            "preferred_method": preferred_method,
            "has_password": has_password,
            "has_webauthn": False,
            "webauthn_credential_count": 0,
            "recent_auth_methods": user.get("recent_auth_methods", []),
            "last_auth_method": user.get("last_auth_method"),
        }

    except Exception as e:
        logger.error("Failed to get user auth methods: %s", e, exc_info=True)
        log_error_with_context(
            e,
            context={"user_id": user_id},
            operation="get_user_auth_methods",
        )
        return {
            "available_methods": [],
            "preferred_method": None,
            "has_password": False,
            "has_webauthn": False,
            "webauthn_credential_count": 0,
        }


@log_performance("set_user_auth_preference")
async def set_user_auth_preference(user_id: str, preferred_method: str) -> bool:
    """
    Set user's preferred authentication method.

    Validates that the method is available for the user before setting preference.

    Args:
        user_id (str): User ID to set preference for
        preferred_method (str): Preferred authentication method ("password")

    Returns:
        bool: True if preference was set successfully, False otherwise
    """
    try:
        # Validate the preferred method is available
        auth_methods = await get_user_auth_methods(user_id)
        if preferred_method not in auth_methods["available_methods"]:
            logger.warning(
                "Cannot set unavailable auth method as preference: %s for user %s", preferred_method, user_id
            )
            return False

        # Update user preference
        result = await db_manager.get_collection("users").update_one(
            {"_id": user_id}, {"$set": {"preferred_auth_method": preferred_method}}
        )

        if result.modified_count > 0:
            logger.info("Updated auth preference for user %s: %s", user_id, preferred_method)
            log_security_event(
                event_type="auth_preference_updated",
                user_id=user_id,
                success=True,
                details={"preferred_method": preferred_method},
            )
            return True
        else:
            logger.warning("Failed to update auth preference for user %s", user_id)
            return False

    except Exception as e:
        logger.error("Failed to set user auth preference: %s", e, exc_info=True)
        log_error_with_context(
            e,
            context={"user_id": user_id, "preferred_method": preferred_method},
            operation="set_user_auth_preference",
        )
        return False


@log_performance("check_auth_fallback_available")
async def check_auth_fallback_available(user_id: str, failed_method: str) -> Dict[str, Any]:
    """
    Check if authentication fallback is available when one method fails.

    Determines what alternative authentication methods are available if the primary method fails.

    Args:
        user_id (str): User ID to check fallback for
        failed_method (str): Authentication method that failed

    Returns:
        Dict[str, Any]: Fallback options and recommendations
    """
    try:
        auth_methods = await get_user_auth_methods(user_id)
        available_methods = auth_methods["available_methods"]

        # Remove the failed method from available options
        fallback_methods = [method for method in available_methods if method != failed_method]

        # Determine recommended fallback
        recommended_fallback = None
        if fallback_methods:
            # Prefer the user's preferred method if it's available and different from failed method
            preferred = auth_methods["preferred_method"]
            if preferred and preferred in fallback_methods:
                recommended_fallback = preferred
            else:
                # Otherwise, recommend the first available fallback
                recommended_fallback = fallback_methods[0]

        fallback_info = {
            "has_fallback": len(fallback_methods) > 0,
            "fallback_methods": fallback_methods,
            "recommended_fallback": recommended_fallback,
            "failed_method": failed_method,
            "total_methods_available": len(available_methods),
        }

        logger.info("Auth fallback check for user %s: %s", user_id, fallback_info)

        return fallback_info

    except Exception as e:
        logger.error("Failed to check auth fallback: %s", e, exc_info=True)
        log_error_with_context(
            e,
            context={"user_id": user_id, "failed_method": failed_method},
            operation="check_auth_fallback_available",
        )
        return {
            "has_fallback": False,
            "fallback_methods": [],
            "recommended_fallback": None,
            "failed_method": failed_method,
            "total_methods_available": 0,
        }


@log_performance("send_blocked_login_notification")
async def send_blocked_login_notification(email: str, attempted_ip: str, trusted_ips: list[str]):
    """
    Send an email notification about a blocked login attempt due to Trusted IP Lockdown.
    Uses the same enhanced template as general IP lockdown notifications with action buttons.
    """
    from second_brain_database.routes.auth.routes_html import render_blocked_ip_notification_email
    from second_brain_database.routes.auth.services.temporary_access import generate_temporary_ip_access_token

    logger.info("Sending blocked login notification to %s for IP %s", email, attempted_ip)

    # Generate temporary access tokens for action buttons
    allow_once_token = None
    add_to_trusted_token = None
    endpoint = "POST /auth/login"

    try:
        allow_once_token = await generate_temporary_ip_access_token(
            user_email=email, ip_address=attempted_ip, action="allow_once", endpoint=endpoint
        )
        logger.debug("Generated allow once token for login notification to %s", email)
    except Exception as e:
        logger.error("Failed to generate allow once token for login notification to %s: %s", email, e, exc_info=True)

    try:
        add_to_trusted_token = await generate_temporary_ip_access_token(
            user_email=email, ip_address=attempted_ip, action="add_to_trusted", endpoint=endpoint
        )
        logger.debug("Generated add to trusted token for login notification to %s", email)
    except Exception as e:
        logger.error(
            "Failed to generate add to trusted token for login notification to %s: %s", email, e, exc_info=True
        )

    # Log security event for blocked login attempt
    log_security_event(
        event_type="trusted_ip_lockdown_block",
        user_id=email,
        ip_address=attempted_ip,
        success=False,
        details={
            "attempted_ip": attempted_ip,
            "trusted_ips": trusted_ips,
            "endpoint": endpoint,
            "action": "notification_sent",
            "tokens_generated": {
                "allow_once": allow_once_token is not None,
                "add_to_trusted": add_to_trusted_token is not None,
            },
        },
    )

    subject = "Blocked Login Attempt: IP Lockdown Active"
    timestamp = datetime.utcnow().isoformat()
    html_content = render_blocked_ip_notification_email(
        attempted_ip=attempted_ip,
        trusted_ips=trusted_ips,
        endpoint=endpoint,
        timestamp=timestamp,
        allow_once_token=allow_once_token,
        add_to_trusted_token=add_to_trusted_token,
    )

    try:
        await email_manager._send_via_console(email, subject, html_content)
        logger.info("Successfully sent blocked login notification to %s", email)
    except RuntimeError as e:
        logger.error("Failed to send blocked login notification to %s: %s", email, e, exc_info=True)
        log_error_with_context(
            e, context={"email": email, "attempted_ip": attempted_ip}, operation="send_blocked_login_notification"
        )


@log_performance("login_user", log_args=False)
async def login_user(
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    two_fa_code: Optional[str] = None,
    two_fa_method: Optional[str] = None,
    client_side_encryption: bool = False,
    authentication_method: str = "password",
) -> Dict[str, Any]:
    """
    Authenticate a user using password authentication methods.

    Supports dual authentication with fallback mechanisms and user preference storage.
    Handles lockout, failed attempts, and 2FA enforcement for authentication methods.
    Enforces account suspension for repeated password reset abuse.

    Args:
        username (Optional[str]): Username for login.
        email (Optional[str]): Email for login.
        password (Optional[str]): Password for login (required for password auth).
        two_fa_code (Optional[str]): 2FA code if required.
        two_fa_method (Optional[str]): 2FA method if required.
        client_side_encryption (bool): Whether client-side encryption is enabled.
        authentication_method (str): Authentication method used ("password").

    Returns:
        Dict[str, Any]: The user document with authentication metadata if authentication succeeds.

    Raises:
        HTTPException: On authentication failure or account lockout.
    """
    # Log login attempt initiation
    identifier = username or email or "unknown"
    logger.info("Login attempt initiated for identifier: %s", identifier)

    # Log security event for login attempt
    log_security_event(
        event_type="login_attempt",
        user_id=identifier,
        ip_address=request_ip_ctx.get(),
        success=False,  # Will be updated to True on success
        details={
            "has_username": bool(username),
            "has_email": bool(email),
            "has_2fa_code": bool(two_fa_code),
            "two_fa_method": two_fa_method,
            "client_side_encryption": client_side_encryption,
        },
    )

    # Validate input parameters
    if username:
        logger.debug("Looking up user by username: %s", username)
        user = await db_manager.get_collection("users").find_one({"username": username})
    elif email:
        logger.debug("Looking up user by email: %s", email)
        user = await db_manager.get_collection("users").find_one({"email": email})
    else:
        logger.warning("Login attempt missing username/email")
        log_security_event(
            event_type="login_invalid_input",
            user_id="unknown",
            ip_address=request_ip_ctx.get(),
            success=False,
            details={"error": "missing_username_email"},
        )
        raise HTTPException(status_code=400, detail="Username or email required")

    if not user:
        logger.warning("Login failed: user not found for username=%s, email=%s", username, email)
        log_security_event(
            event_type="login_user_not_found",
            user_id=identifier,
            ip_address=request_ip_ctx.get(),
            success=False,
            details={"username": username, "email": email},
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Check account status and security restrictions
    user_id = user.get("username", user.get("email", "unknown"))

    if user.get("abuse_suspended", False):
        logger.warning("Login blocked: abuse_suspended for user %s", user_id)
        log_security_event(
            event_type="login_abuse_suspended",
            user_id=user_id,
            ip_address=request_ip_ctx.get(),
            success=False,
            details={"reason": "abuse_suspended", "suspended_at": user.get("abuse_suspended_at")},
        )
        raise HTTPException(
            status_code=403,
            detail="Account suspended due to repeated abuse of the password reset system. Please contact support.",
        )

    if user.get("failed_login_attempts", 0) >= MAX_FAILED_LOGIN_ATTEMPTS:
        logger.warning(
            "Login blocked: too many failed attempts for user %s (attempts: %d)",
            user_id,
            user.get("failed_login_attempts", 0),
        )
        log_security_event(
            event_type="login_account_locked",
            user_id=user_id,
            ip_address=request_ip_ctx.get(),
            success=False,
            details={
                "failed_attempts": user.get("failed_login_attempts", 0),
                "max_attempts": MAX_FAILED_LOGIN_ATTEMPTS,
            },
        )
        raise HTTPException(status_code=403, detail="Account locked due to too many failed attempts")

    if not user.get("is_active", True):
        logger.warning("Login blocked: inactive account for user %s", user_id)
        log_security_event(
            event_type="login_inactive_account",
            user_id=user_id,
            ip_address=request_ip_ctx.get(),
            success=False,
            details={"is_active": user.get("is_active", True)},
        )
        raise HTTPException(
            status_code=403, detail="User account is inactive, please contact support to reactivate account."
        )
    # Check IP lockdown for login (special case since login is not an authenticated endpoint)
    # We need to check IP lockdown after user authentication but before proceeding
    try:
        # Create a mock request object with the IP context
        class MockRequest:
            def __init__(self, ip_address):
                self.client = type("obj", (object,), {"host": ip_address})
                self.headers = {}
                self.url = type("obj", (object,), {"path": "/auth/login"})
                self.method = "POST"

        mock_request = MockRequest(request_ip_ctx.get())
        await security_manager.check_ip_lockdown(mock_request, user)

    except HTTPException as ip_lockdown_error:
        # IP lockdown blocked the login attempt
        logger.warning("Login blocked by IP lockdown for user %s from IP %s", user_id, request_ip_ctx.get())

        # Send blocked login notification
        try:
            user_email = user.get("email")
            trusted_ips = user.get("trusted_ips", [])
            if user_email:
                await send_blocked_login_notification(
                    email=user_email, attempted_ip=request_ip_ctx.get() or "unknown", trusted_ips=trusted_ips
                )
                logger.info("Sent blocked login notification to %s", user_email)
        except Exception as email_error:
            logger.error("Failed to send blocked login notification: %s", email_error, exc_info=True)

        # Re-raise the IP lockdown exception
        raise ip_lockdown_error

    # Validate authentication method and credentials
    if authentication_method == "password":
        # Password authentication validation
        password_hash = user.get("hashed_password") or user.get("password_hash")
        if not password or not password_hash or not bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
            logger.info("Login failed: invalid password for user %s", user_id)

            # Log failed login attempt and increment counter
            log_security_event(
                event_type="login_invalid_password",
                user_id=user_id,
                ip_address=request_ip_ctx.get(),
                success=False,
                details={
                    "current_failed_attempts": user.get("failed_login_attempts", 0),
                    "max_attempts": MAX_FAILED_LOGIN_ATTEMPTS,
                    "authentication_method": authentication_method,
                },
            )

            # Update failed login attempts in database
            await db_manager.get_collection("users").update_one(
                {"_id": user["_id"]}, {"$inc": {"failed_login_attempts": 1}}
            )
            logger.debug("Incremented failed login attempts for user %s", user_id)

            raise HTTPException(status_code=401, detail="Invalid credentials")

        logger.info("Password authentication successful for user %s", user_id)

    else:
        logger.warning("Invalid authentication method for user %s: %s", user_id, authentication_method)
        log_security_event(
            event_type="login_invalid_auth_method",
            user_id=user_id,
            ip_address=request_ip_ctx.get(),
            success=False,
            details={"authentication_method": authentication_method},
        )
        raise HTTPException(status_code=400, detail="Invalid authentication method")

    # Check email verification
    if not user.get("is_verified", False):
        logger.warning("Login blocked: email not verified for user %s", user_id)
        log_security_event(
            event_type="login_email_not_verified",
            user_id=user_id,
            ip_address=request_ip_ctx.get(),
            success=False,
            details={"is_verified": user.get("is_verified", False)},
        )
        raise HTTPException(status_code=403, detail="Email not verified")
    # 2FA check
    if user.get("two_fa_enabled"):
        if not two_fa_code or not two_fa_method:
            logger.info("2FA required for user %s", user.get("username", user.get("email")))
            raise HTTPException(
                status_code=422, detail="2FA authentication required", headers={"X-2FA-Required": "true"}
            )
        methods = user.get("two_fa_methods", [])
        if two_fa_method not in methods and two_fa_method != "backup":
            logger.info("Invalid 2FA method for user %s: %s", user.get("username", user.get("email")), two_fa_method)
            raise HTTPException(status_code=422, detail="Invalid 2FA method")
        if two_fa_method == "totp":
            secret = user.get("totp_secret")
            if not secret:
                logger.warning("TOTP not set up for user %s", user.get("username", user.get("email")))
                raise HTTPException(status_code=401, detail="TOTP not set up")
            if is_encrypted_totp_secret(secret):
                secret = decrypt_totp_secret(secret)
            totp = pyotp.TOTP(secret)
            if not totp.verify(two_fa_code, valid_window=1):
                logger.info("Invalid TOTP code for user %s", user.get("username", user.get("email")))
                raise HTTPException(status_code=401, detail="Invalid TOTP code")
        elif two_fa_method == "backup":
            backup_codes = user.get("backup_codes", [])
            backup_codes_used = user.get("backup_codes_used", [])
            code_valid = False
            for i, hashed_code in enumerate(backup_codes):
                if i not in backup_codes_used and bcrypt.checkpw(
                    two_fa_code.encode("utf-8"), hashed_code.encode("utf-8")
                ):
                    code_valid = True
                    await db_manager.get_collection("users").update_one(
                        {"_id": user["_id"]}, {"$push": {"backup_codes_used": i}}
                    )
                    logger.info("Backup code used for user %s", user["username"])
                    break
            if not code_valid:
                logger.info("Invalid or used backup code for user %s", user.get("username", user.get("email")))
                raise HTTPException(status_code=401, detail="Invalid or already used backup code")
        else:
            logger.warning(
                "2FA method not implemented for user %s: %s", user.get("username", user.get("email")), two_fa_method
            )
            raise HTTPException(status_code=401, detail="2FA method not implemented")
    # Update user document with login information and authentication preferences
    update_data = {
        "last_login": datetime.utcnow(),
        "last_auth_method": authentication_method,
    }

    # Update preferred authentication method based on usage patterns
    current_preferred = user.get("preferred_auth_method")
    if not current_preferred:
        # First time setting preference - use current method
        update_data["preferred_auth_method"] = authentication_method
        logger.info("Setting initial preferred auth method for user %s: %s", user_id, authentication_method)
    elif current_preferred != authentication_method:
        # User is using a different method - update preference if they've used it recently
        recent_auth_methods = user.get("recent_auth_methods", [])
        if len([m for m in recent_auth_methods if m == authentication_method]) >= 2:
            update_data["preferred_auth_method"] = authentication_method
            logger.info(
                "Updating preferred auth method for user %s: %s -> %s",
                user_id,
                current_preferred,
                authentication_method,
            )

    # Track recent authentication methods (last 5)
    recent_methods = user.get("recent_auth_methods", [])
    recent_methods.append(authentication_method)
    if len(recent_methods) > 5:
        recent_methods = recent_methods[-5:]
    update_data["recent_auth_methods"] = recent_methods

    # Clear failed login attempts and update user document
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]}, {"$set": update_data, "$unset": {"failed_login_attempts": ""}}
    )

    # Log successful authentication with method details
    log_security_event(
        event_type="login_successful",
        user_id=user_id,
        ip_address=request_ip_ctx.get(),
        success=True,
        details={
            "authentication_method": authentication_method,
            "client_side_encryption": client_side_encryption,
            "preferred_auth_method": update_data.get("preferred_auth_method"),
        },
    )

    if client_side_encryption:
        logger.info("User %s logged in with client-side encryption enabled", user["username"])

    logger.info("User %s logged in successfully using %s authentication", user["username"], authentication_method)

    # Add authentication metadata to user document for return
    user["authentication_method"] = authentication_method

    return user


@log_performance("create_access_token")
async def create_access_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT access token with short expiry and required claims.
    Includes token_version for stateless invalidation and tenant information for multi-tenancy.

    Args:
        data (Dict[str, Any]): Claims to encode in the JWT. Can include:
            - sub: Username (required)
            - user_id: User ID (optional, will be fetched if not provided)

    Returns:
        str: Encoded JWT access token.

    Raises:
        RuntimeError: If the secret key is missing or invalid.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "sub": data.get("sub"), "type": "access"})

    # Add user-specific claims including token_version and tenant information
    if "username" in data or "sub" in data:
        username = data.get("username") or data.get("sub")
        user = None
        if username:
            user = await db_manager.get_collection("users").find_one({"username": username})
        if user:
            token_version = user.get("token_version", 0)
            to_encode["token_version"] = token_version
            to_encode["user_id"] = str(user.get("_id"))
            
            # Add tenant information for multi-tenancy
            to_encode["primary_tenant_id"] = user.get("primary_tenant_id", settings.DEFAULT_TENANT_ID)
            
            # Include tenant memberships (limited to tenant_id and role for JWT size)
            tenant_memberships = user.get("tenant_memberships", [])
            to_encode["tenant_memberships"] = [
                {
                    "tenant_id": membership.get("tenant_id"),
                    "role": membership.get("role")
                }
                for membership in tenant_memberships
            ]

    secret_key = getattr(settings, "SECRET_KEY", None)
    if hasattr(secret_key, "get_secret_value"):
        secret_key = secret_key.get_secret_value()
    if not isinstance(secret_key, (str, bytes)) or not secret_key:
        logger.error("JWT secret key is missing or invalid. Check your settings.SECRET_KEY.")
        raise RuntimeError("JWT secret key is missing or invalid. Check your settings.SECRET_KEY.")

    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.ALGORITHM)

    auth_method = "password"
    logger.debug(
        "JWT access token created for user: %s (auth method: %s, tenant: %s)", 
        data.get("username") or data.get("sub"), 
        auth_method,
        to_encode.get("primary_tenant_id")
    )

    return encoded_jwt


@log_performance("create_refresh_token")
async def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token with long expiry for token refresh flow.
    
    Refresh tokens use a separate secret key and have longer expiration.
    They are used to obtain new access tokens without re-authentication.

    Args:
        data (Dict[str, Any]): Claims to encode in the JWT. Can include:
            - sub: Username (required)

    Returns:
        str: Encoded JWT refresh token.

    Raises:
        RuntimeError: If the refresh token secret key is missing or invalid.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "sub": data.get("sub"), "type": "refresh"})

    # Get refresh token secret key
    refresh_secret_key = getattr(settings, "REFRESH_TOKEN_SECRET_KEY", None)
    if hasattr(refresh_secret_key, "get_secret_value"):
        refresh_secret_key = refresh_secret_key.get_secret_value()
    
    # Fallback to regular SECRET_KEY if REFRESH_TOKEN_SECRET_KEY not set (backward compatibility)
    if not refresh_secret_key or not isinstance(refresh_secret_key, (str, bytes)):
        logger.warning("REFRESH_TOKEN_SECRET_KEY not set, falling back to SECRET_KEY")
        refresh_secret_key = getattr(settings, "SECRET_KEY", None)
        if hasattr(refresh_secret_key, "get_secret_value"):
            refresh_secret_key = refresh_secret_key.get_secret_value()
    
    if not isinstance(refresh_secret_key, (str, bytes)) or not refresh_secret_key:
        logger.error("Refresh token secret key is missing or invalid.")
        raise RuntimeError("Refresh token secret key is missing or invalid.")

    encoded_jwt = jwt.encode(to_encode, refresh_secret_key, algorithm=settings.ALGORITHM)

    logger.debug("JWT refresh token created for user: %s", data.get("username") or data.get("sub"))

    return encoded_jwt


async def get_current_user(token: str) -> Dict[str, Any]:
    """
    Get the current authenticated user from a JWT token.

    Supports both regular JWT tokens (with expiration) and permanent tokens (without expiration).
    Permanent tokens are validated using Redis cache-first approach with database fallback.

    Args:
        token (str): JWT access token (regular or permanent).

    Returns:
        Dict[str, Any]: The user document if token is valid.

    Raises:
        HTTPException: If the token is invalid, expired, or user not found.
    """
    from second_brain_database.routes.auth.services.permanent_tokens import is_permanent_token, validate_permanent_token

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Check if token is blacklisted first (applies to both token types)
        if await is_token_blacklisted(token):
            logger.warning("Token is blacklisted")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is blacklisted",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Check if this is a permanent token
        if is_permanent_token(token):
            logger.debug("Detected permanent token, using permanent token validation")
            user = await validate_permanent_token(token)
            if user is None:
                logger.warning("Permanent token validation failed")
                raise credentials_exception
            return user

        # Regular JWT token validation (existing logic)
        secret_key = getattr(settings, "SECRET_KEY", None)
        if hasattr(secret_key, "get_secret_value"):
            secret_key = secret_key.get_secret_value()
        if not isinstance(secret_key, (str, bytes)) or not secret_key:
            logger.error("JWT secret key is missing or invalid. Check your settings.SECRET_KEY.")
            raise credentials_exception

        payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
        username: Optional[str] = payload.get("sub")
        token_version_claim = payload.get("token_version")

        if username is None:
            logger.warning("JWT payload missing 'sub' claim")
            raise credentials_exception

        user = await db_manager.get_collection("users").find_one({"username": username})
        if user is None:
            logger.warning("User not found for JWT 'sub' claim: %s", username)
            raise credentials_exception

        # Check token version for regular tokens (permanent tokens don't use this)
        if token_version_claim is not None:
            user_token_version = user.get("token_version", 0)
            if token_version_claim != user_token_version:
                logger.warning("JWT token_version mismatch for user %s", username)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is no longer valid (password changed or reset)",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        logger.debug("Regular JWT validated for user: %s", username)
        return user

    except jwt.ExpiredSignatureError as exc:
        # Regular token expired - check if it might be a permanent token
        try:
            if is_permanent_token(token):
                logger.debug("Expired signature but permanent token detected, validating as permanent")
                user = await validate_permanent_token(token)
                if user is not None:
                    return user
        except Exception:
            pass  # Fall through to expired token error

        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except Exception as e:
        from jose.exceptions import JWTError

        if isinstance(e, JWTError):
            logger.warning("Invalid token: %s", e)
            raise credentials_exception from e
        logger.error("Unexpected error validating token: %s", e, exc_info=True)
        raise credentials_exception from e
