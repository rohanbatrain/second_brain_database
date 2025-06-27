"""
Authentication login logic for user sign-in, lockout, and 2FA enforcement.

This module provides async functions for user authentication, including password
and 2FA checks, account lockout, and JWT access token creation and validation.
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
from jose import jwt
import bcrypt
import pyotp
from datetime import datetime, timedelta
from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.security.tokens import is_token_blacklisted
from second_brain_database.utils.crypto import decrypt_totp_secret, is_encrypted_totp_secret
import contextvars
from second_brain_database.managers.email import email_manager

MAX_FAILED_LOGIN_ATTEMPTS: int = 5

logger = get_logger(prefix="[Auth Service Login]")

request_ip_ctx = contextvars.ContextVar("request_ip", default=None)

async def send_blocked_login_notification(email: str, attempted_ip: str, trusted_ips: list[str]):
    """
    Send an email notification about a blocked login attempt due to Trusted IP Lockdown.
    """
    
    subject = "Blocked Login Attempt: Trusted IP Lockdown Active"
    html_content = f"""
    <html><body>
    <h2>Blocked Login Attempt</h2>
    <p>A login attempt to your account was blocked because it came from an IP address not on your trusted list.</p>
    <ul>
        <li><b>Attempted IP:</b> {attempted_ip}</li>
        <li><b>Allowed IPs:</b> {', '.join(trusted_ips) or 'None'}</li>
        <li><b>Time (UTC):</b> {datetime.utcnow().isoformat()}</li>
    </ul>
    <p>If this was you, please check your trusted IP settings. If you did not attempt to log in, no action is needed.</p>
    </body></html>
    """
    try:
        await email_manager._send_via_console(email, subject, html_content)
    except RuntimeError as e:
        logger.error("Failed to send blocked login notification: %s", e, exc_info=True)

async def login_user(
    username: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    two_fa_code: Optional[str] = None,
    two_fa_method: Optional[str] = None,
    client_side_encryption: bool = False
) -> Dict[str, Any]:
    """
    Authenticate a user by username or email and password, handle lockout and failed attempts, and check 2FA if enabled.
    Enforces account suspension for repeated password reset abuse.

    Args:
        username (Optional[str]): Username for login.
        email (Optional[str]): Email for login.
        password (Optional[str]): Password for login.
        two_fa_code (Optional[str]): 2FA code if required.
        two_fa_method (Optional[str]): 2FA method if required.
        client_side_encryption (bool): Whether client-side encryption is enabled.

    Returns:
        Dict[str, Any]: The user document if authentication succeeds.

    Raises:
        HTTPException: On authentication failure or account lockout.
    """
    if username:
        user = await db_manager.get_collection("users").find_one({"username": username})
    elif email:
        user = await db_manager.get_collection("users").find_one({"email": email})
    else:
        logger.warning("Login attempt missing username/email")
        raise HTTPException(status_code=400, detail="Username or email required")
    if not user:
        logger.warning("Login failed: user not found for username=%s, email=%s", username, email)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("abuse_suspended", False):
        logger.warning("Login blocked: abuse_suspended for user %s", user.get("username", user.get("email")))
        raise HTTPException(
            status_code=403,
            detail="Account suspended due to repeated abuse of the password reset system. Please contact support."
        )
    if user.get("failed_login_attempts", 0) >= MAX_FAILED_LOGIN_ATTEMPTS:
        logger.warning("Login blocked: too many failed attempts for user %s", user.get("username", user.get("email")))
        raise HTTPException(status_code=403, detail="Account locked due to too many failed attempts")
    if not user.get("is_active", True):
        logger.warning("Login blocked: inactive account for user %s", user.get("username", user.get("email")))
        raise HTTPException(status_code=403, detail="User account is inactive, please contact support to reactivate account.")
    if user.get("trusted_ip_lockdown", False):
        # Enforce trusted IP lockdown: only allow login from trusted IPs
        request_ip = request_ip_ctx.get()
        if not request_ip:
            # Fallback: try to get from user doc (should not happen)
            logger.warning("Trusted IP lockdown: could not determine request IP for user %s", user.get("username", user.get("email")))
            raise HTTPException(status_code=403, detail="Trusted IP lockdown: unable to determine request IP.")
        trusted_ips = user.get("trusted_ips", [])
        if request_ip not in trusted_ips:
            logger.warning("Trusted IP lockdown: login attempt from disallowed IP %s for user %s (trusted: %s)", request_ip, user.get("username", user.get("email")), trusted_ips)
            await send_blocked_login_notification(user["email"], request_ip, trusted_ips)
            raise HTTPException(status_code=403, detail="Login not allowed from this IP (Trusted IP Lockdown is enabled).")
    if not password or not bcrypt.checkpw(password.encode('utf-8'), user["hashed_password"].encode('utf-8')):
        await db_manager.get_collection("users").update_one(
            {"_id": user["_id"]},
            {"$inc": {"failed_login_attempts": 1}}
        )
        logger.info("Login failed: invalid password for user %s", user.get("username", user.get("email")))
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.get("is_verified", False):
        logger.warning("Login blocked: email not verified for user %s", user.get("username", user.get("email")))
        raise HTTPException(status_code=403, detail="Email not verified")
    # 2FA check
    if user.get("two_fa_enabled"):
        if not two_fa_code or not two_fa_method:
            logger.info("2FA required for user %s", user.get("username", user.get("email")))
            raise HTTPException(
                status_code=422,
                detail="2FA authentication required",
                headers={"X-2FA-Required": "true"}
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
                if i not in backup_codes_used and bcrypt.checkpw(two_fa_code.encode('utf-8'), hashed_code.encode('utf-8')):
                    code_valid = True
                    await db_manager.get_collection("users").update_one(
                        {"_id": user["_id"]},
                        {"$push": {"backup_codes_used": i}}
                    )
                    logger.info("Backup code used for user %s", user["username"])
                    break
            if not code_valid:
                logger.info("Invalid or used backup code for user %s", user.get("username", user.get("email")))
                raise HTTPException(status_code=401, detail="Invalid or already used backup code")
        else:
            logger.warning("2FA method not implemented for user %s: %s", user.get("username", user.get("email")), two_fa_method)
            raise HTTPException(status_code=401, detail="2FA method not implemented")
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}, "$unset": {"failed_login_attempts": ""}}
    )
    if client_side_encryption:
        logger.info("User %s logged in with client-side encryption enabled", user["username"])
    logger.info("User %s logged in successfully", user["username"])
    return user

async def create_access_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT access token with short expiry and required claims.
    Includes token_version for stateless invalidation.

    Args:
        data (Dict[str, Any]): Claims to encode in the JWT.

    Returns:
        str: Encoded JWT access token.

    Raises:
        RuntimeError: If the secret key is missing or invalid.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "sub": data.get("sub")})
    if "username" in data or "sub" in data:
        username = data.get("username") or data.get("sub")
        user = None
        if username:
            user = await db_manager.get_collection("users").find_one({"username": username})
        if user:
            token_version = user.get("token_version", 0)
            to_encode["token_version"] = token_version
    secret_key = getattr(settings, "SECRET_KEY", None)
    if hasattr(secret_key, "get_secret_value"):
        secret_key = secret_key.get_secret_value()
    if not isinstance(secret_key, (str, bytes)) or not secret_key:
        logger.error("JWT secret key is missing or invalid. Check your settings.SECRET_KEY.")
        raise RuntimeError("JWT secret key is missing or invalid. Check your settings.SECRET_KEY.")
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.ALGORITHM)
    logger.debug("JWT access token created for user: %s", data.get("username") or data.get("sub"))
    return encoded_jwt

async def get_current_user(token: str) -> Dict[str, Any]:
    """
    Get the current authenticated user from a JWT token.

    Args:
        token (str): JWT access token.

    Returns:
        Dict[str, Any]: The user document if token is valid.

    Raises:
        HTTPException: If the token is invalid, expired, or user not found.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if await is_token_blacklisted(token):
            logger.warning("Token is blacklisted")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is blacklisted",
                headers={"WWW-Authenticate": "Bearer"},
            )
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
        if token_version_claim is not None:
            user_token_version = user.get("token_version", 0)
            if token_version_claim != user_token_version:
                logger.warning("JWT token_version mismatch for user %s", username)
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is no longer valid (password changed or reset)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        logger.debug("JWT validated for user: %s", username)
        return user
    except jwt.ExpiredSignatureError as exc:
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
