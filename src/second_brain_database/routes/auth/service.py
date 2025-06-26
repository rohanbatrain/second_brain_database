"""
Service layer for authentication and user management.

Password Reset Abuse Prevention Implementation:
- All /forgot-password requests are logged to Redis (email, IP, user-agent, timestamp) for real-time abuse detection.
- Abuse detection logic flags suspicious activity based on request volume, unique IPs, and IP reputation (VPN/proxy/abuse/relay via IPinfo).
- If suspicious, the user is notified by email, and the (email, IP) pair is flagged in Redis for 15 minutes.
- Scoped whitelisting/blocking of (email, IP) pairs is supported and respected by the abuse logic.
- All sensitive endpoints, including /forgot-password, are rate-limited per IP and per endpoint.
- If a /forgot-password request is suspicious, CAPTCHA (Cloudflare Turnstile) is required and verified before proceeding.
- All abuse logs and flags are ephemeral (15 min expiry in Redis), and only metadata is stored (no sensitive data).
- See function docstrings for details on thresholds, expiry, and privacy/security considerations.
"""

import json
import secrets
import hashlib
import base64
import bcrypt
import pyotp
import qrcode
import httpx
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from jose import jwt
from second_brain_database.routes.auth.models import TwoFASetupResponse, TwoFAStatus, UserIn, PasswordChangeRequest, validate_password_strength, TwoFASetupRequest, TwoFAVerifyRequest
from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.utils.crypto import encrypt_totp_secret, decrypt_totp_secret, is_encrypted_totp_secret, migrate_plaintext_secret
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

STRICTER_WHITELIST_LIMIT = getattr(settings, "STRICTER_WHITELIST_LIMIT", 3)
STRICTER_WHITELIST_PERIOD = getattr(settings, "STRICTER_WHITELIST_PERIOD", 86400)  # 24h
ABUSE_ACTION_TOKEN_EXPIRY = getattr(settings, "ABUSE_ACTION_TOKEN_EXPIRY", 1800)  # 30 min
ABUSE_ACTION_BLOCK_EXPIRY = getattr(settings, "ABUSE_ACTION_BLOCK_EXPIRY", 86400)  # 24h
MAX_RESET_REQUESTS = getattr(settings, "MAX_RESET_REQUESTS", 8)
MAX_RESET_UNIQUE_IPS = getattr(settings, "MAX_RESET_UNIQUE_IPS", 4)

async def blacklist_token(user_id=None, token: str = None):
    """
    Blacklist all tokens for a user (by user_id) or a specific token.
    Uses Redis for production-ready persistence and multi-instance support.
    """
    redis_conn = await redis_manager.get_redis()
    if user_id is not None:
        # Blacklist user by user_id for 7 days (adjust as needed)
        await redis_conn.set(f"blacklist:user:{user_id}", "1", ex=60*60*24*7)
    if token is not None:
        # Blacklist specific token for 1 day (adjust as needed)
        await redis_conn.set(f"blacklist:token:{token}", "1", ex=60*60*24)

async def is_token_blacklisted(token: str, user_id: str = None) -> bool:
    redis_conn = await redis_manager.get_redis()
    if user_id:
        if await redis_conn.get(f"blacklist:user:{user_id}"):
            return True
    if await redis_conn.get(f"blacklist:token:{token}"):
        return True
    return False

def get_decrypted_totp_secret(user: dict) -> str:
    """
    Safely get and decrypt a user's TOTP secret.
    Handles both encrypted and legacy plaintext secrets for migration.
    
    Args:
        user: User document from database
        
    Returns:
        Decrypted TOTP secret
        
    Raises:
        ValueError: If no TOTP secret exists or decryption fails
    """
    encrypted_secret = user.get("totp_secret")
    if not encrypted_secret:
        raise ValueError("No TOTP secret found")
    
    try:
        # Check if it's already encrypted
        if is_encrypted_totp_secret(encrypted_secret):
            return decrypt_totp_secret(encrypted_secret)
        else:
            # Legacy plaintext secret - log and migrate
            logger.warning("Found plaintext TOTP secret for user %s, migrating to encrypted format", user.get("username", "unknown"))
            # Migrate in-place for future use
            migrated_secret = migrate_plaintext_secret(encrypted_secret)
            # Update the database with encrypted version
            users = db_manager.get_collection("users")
            users.update_one(
                {"_id": user["_id"]},
                {"$set": {"totp_secret": migrated_secret}}
            )
            logger.info("Successfully migrated TOTP secret to encrypted format for user %s", user.get("username", "unknown"))
            return encrypted_secret  # Return original plaintext for immediate use
    except Exception as e:
        logger.error("Failed to decrypt TOTP secret for user %s: %s", user.get("username", "unknown"), e)
        raise ValueError("Failed to decrypt TOTP secret") from e

# Username business logic for username availability and demand tracking using Redis
async def redis_check_username(username: str) -> bool:
    redis_conn = await redis_manager.get_redis()
    key = f"username:exists:{username.lower()}"
    cached = await redis_conn.get(key)
    if cached is not None:
        return cached == "1"
    # Fallback to DB
    user = await db_manager.get_collection("users").find_one({"username": username.lower()})
    exists = user is not None
    await redis_conn.set(key, "1" if exists else "0", ex=3600)
    return exists

async def redis_incr_username_demand(username: str):
    redis_conn = await redis_manager.get_redis()
    key = f"username:demand:{username.lower()}"
    await redis_conn.incr(key)
    await redis_conn.expire(key, 86400)  # 1 day expiry

async def redis_get_top_demanded_usernames(top_n=10):
    redis_conn = await redis_manager.get_redis()
    pattern = "username:demand:*"
    keys = await redis_conn.keys(pattern)
    result = []
    for key in keys:
        count = await redis_conn.get(key)
        uname = key.split(":", 2)[-1]
        result.append((uname, int(count)))
    result.sort(key=lambda x: x[1], reverse=True)
    return result[:top_n]

# --- Redis helpers for 2FA backup codes ---
BACKUP_CODES_REDIS_PREFIX = "2fa:backup_codes:"
BACKUP_CODES_PENDING_TIME = settings.BACKUP_CODES_PENDING_TIME

async def store_backup_codes_temp(username: str, codes: list):
    redis_conn = await redis_manager.get_redis()
    key = f"{BACKUP_CODES_REDIS_PREFIX}{username}"
    await redis_conn.set(key, json.dumps(codes), ex=BACKUP_CODES_PENDING_TIME)

async def get_backup_codes_temp(username: str):
    redis_conn = await redis_manager.get_redis()
    key = f"{BACKUP_CODES_REDIS_PREFIX}{username}"
    val = await redis_conn.get(key)
    if val:
        return json.loads(val)
    return None

async def delete_backup_codes_temp(username: str):
    redis_conn = await redis_manager.get_redis()
    key = f"{BACKUP_CODES_REDIS_PREFIX}{username}"
    await redis_conn.delete(key)

async def clear_2fa_pending_if_expired(user: dict):
    """
    If 2FA is pending for more than BACKUP_CODES_PENDING_TIME, clear all 2FA pending state from user.
    Logs cleanup actions and errors for auditability.
    """
    if user.get("two_fa_pending", False):
        pending_since = user.get("two_fa_pending_since")
        now = datetime.utcnow()
        if not pending_since:
            pending_since = user.get("updatedAt") or user.get("created_at") or now
        else:
            pending_since = pending_since if isinstance(pending_since, datetime) else datetime.fromisoformat(pending_since)
        if (now - pending_since).total_seconds() > BACKUP_CODES_PENDING_TIME:
            users = db_manager.get_collection("users")
            await users.update_one(
                {"_id": user["_id"]},
                {"$unset": {
                    "two_fa_pending": "", 
                    "totp_secret": "", 
                    "backup_codes": "", 
                    "backup_codes_used": "", 
                    "two_fa_pending_since": "",
                    "two_fa_methods": ""
                }}
            )
            try:
                await delete_backup_codes_temp(user["username"])
            except Exception as e:
                logger.error(f"Failed to delete backup codes from Redis for user {user['username']}: {e}")
            logger.info(f"Cleared expired 2FA pending state for user {user['username']}")
            return True
    return False

async def register_user(user: UserIn):
    """Register a new user, validate password, and return user doc and verification token."""
    if not validate_password_strength(user.password):
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
        # Generic error to prevent user enumeration
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    return user_doc, verification_token


async def send_welcome_email(email: str, username: str = None):
    """Send a personalized welcome email after user verifies their email."""
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
    logger.info(f"[WELCOME EMAIL] To: {email}\nSubject: {subject}\nHTML:\n{html_content}")
    await email_manager._send_via_console(email, subject, html_content)


async def verify_user_email(token: str):
    """Verify a user's email using the provided token and send a welcome email."""
    user = await db_manager.get_collection("users").find_one({"verification_token": token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True}, "$unset": {"verification_token": ""}}
    )
    # Send welcome email after successful verification
    await send_welcome_email(user["email"], user.get("username"))
    return user


async def login_user(username: str = None, email: str = None, password: str = None, two_fa_code: str = None, two_fa_method: str = None, client_side_encryption: bool = False):
    """
    Authenticate a user by username or email and password, handle lockout and failed attempts, and check 2FA if enabled.
    Enforces account suspension for repeated password reset abuse:
      - If abuse_suspended is True, login is blocked and a clear error is returned.
      - Suspended users are told the reason and to contact support.
      - Admins can unsuspend by setting is_active: True, abuse_suspended: False, and clearing abuse_suspended_at.
      - Optionally, a notification email is sent to the user on suspension (see send_account_suspension_email).
    """
    if username:
        user = await db_manager.get_collection("users").find_one({"username": username})
    elif email:
        user = await db_manager.get_collection("users").find_one({"email": email})
    else:
        raise HTTPException(status_code=400, detail="Username or email required")
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # --- Account suspension enforcement ---
    if user.get("abuse_suspended", False):
        raise HTTPException(
            status_code=403,
            detail="Account suspended due to repeated abuse of the password reset system. Please contact support.",
        )
    if user.get("failed_login_attempts", 0) >= 5:
        raise HTTPException(status_code=403, detail="Account locked due to too many failed attempts")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="User account is inactive, please contact support to reactivate account.")
    # Password check first
    if not bcrypt.checkpw(password.encode('utf-8'), user["hashed_password"].encode('utf-8')):
        await db_manager.get_collection("users").update_one(
            {"_id": user["_id"]},
            {"$inc": {"failed_login_attempts": 1}}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Only after password is correct, check email verification
    if not user.get("is_verified", False):
        raise HTTPException(status_code=403, detail="Email not verified")
    # 2FA check
    if user.get("two_fa_enabled"):
        if not two_fa_code or not two_fa_method:
            raise HTTPException(
                status_code=422, 
                detail="2FA authentication required",
                headers={"X-2FA-Required": "true"}
            )
        methods = user.get("two_fa_methods", [])
        if two_fa_method not in methods and two_fa_method != "backup":
            raise HTTPException(status_code=422, detail="Invalid 2FA method")
        
        if two_fa_method == "totp":
            secret = user.get("totp_secret")
            if not secret:
                raise HTTPException(status_code=401, detail="TOTP not set up")
            # Decrypt if needed
            if is_encrypted_totp_secret(secret):
                secret = decrypt_totp_secret(secret)
            totp = pyotp.TOTP(secret)
            if not totp.verify(two_fa_code, valid_window=1):
                raise HTTPException(status_code=401, detail="Invalid TOTP code")
                
        elif two_fa_method == "backup":
            # Check backup code
            backup_codes = user.get("backup_codes", [])
            backup_codes_used = user.get("backup_codes_used", [])
            
            code_valid = False
            for i, hashed_code in enumerate(backup_codes):
                if i not in backup_codes_used and bcrypt.checkpw(two_fa_code.encode('utf-8'), hashed_code.encode('utf-8')):
                    code_valid = True
                    # Mark this backup code as used
                    await db_manager.get_collection("users").update_one(
                        {"_id": user["_id"]},
                        {"$push": {"backup_codes_used": i}}
                    )
                    logger.info("Backup code used for user %s", user["username"])
                    break
            
            if not code_valid:
                raise HTTPException(status_code=401, detail="Invalid or already used backup code")
        else:
            raise HTTPException(status_code=401, detail="2FA method not implemented")
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.utcnow()}, "$unset": {"failed_login_attempts": ""}}
    )
    # Optionally log client_side_encryption setting
    if client_side_encryption:
        logger.info("User %s logged in with client-side encryption enabled", user["username"])
    return user


async def send_account_suspension_email(email: str, username: str = None):
    """
    Optionally notify the user by email when their account is suspended for abuse.
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
    logger.info(f"[SUSPEND EMAIL] To: {email}\nSubject: {subject}\nHTML:\n{html_content}")
    await email_manager._send_via_console(email, subject, html_content)


async def change_user_password(current_user: dict, password_request: PasswordChangeRequest):
    """Change the password for the current user after validating the old password. Should require recent authentication."""
    # Recent password confirmation or re-login should be enforced for sensitive actions in production
    if not validate_password_strength(password_request.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long and contain "
                   "uppercase, lowercase, digit, and special character"
        )
    if not bcrypt.checkpw(password_request.old_password.encode('utf-8'),
                          current_user["hashed_password"].encode('utf-8')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid old password"
        )
    new_hashed_pw = bcrypt.hashpw(password_request.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    result = await db_manager.get_collection("users").update_one(
        {"username": current_user["username"]},
        {"$set": {"hashed_password": new_hashed_pw}}
    )
    if not result.modified_count:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )
    # Blacklist all tokens for this user (in prod, use Redis or DB)
    # Optionally, you could store a token version in the user doc and increment it here
    # For demo, just log
    logger.info("Password changed for user %s; tokens should be invalidated.", current_user["username"])
    return True


async def send_verification_email(email: str, verification_link: str, username: str = None):
    """Send the verification email using the EmailManager (HTML, multi-provider)."""
    await email_manager.send_verification_email(email, verification_link, username=username)


async def send_password_reset_email(email: str, ip=None, user_agent=None, request_time=None, location=None, isp=None):
    """Send a password reset email with metadata and a real token (hashed in DB)."""
    redis_conn = await redis_manager.get_redis()
    # Individual and combined rate limit keys
    fp_key = f"forgot_password:{email}"
    rv_key = f"resend_verification:{email}"
    combined_key = f"combined_reset_verify:{email}"
    # Increment all relevant counters
    fp_count = await redis_conn.incr(fp_key)
    if fp_count == 1:
        await redis_conn.expire(fp_key, 60)
    combined_count = await redis_conn.incr(combined_key)
    if combined_count == 1:
        await redis_conn.expire(combined_key, 60)
    # Check limits: individual and combined
    if fp_count > 2 or combined_count > 3:
        return {"message": "Password reset email did not sent"}
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    user = await db_manager.get_collection("users").find_one({"email": email})
    if not user:
        logger.info("Password reset requested for non-existent email: %s", email)
        return  # Do not reveal user existence
    # Generate a secure token and expiry
    reset_token = secrets.token_urlsafe(32)
    # Hash the token before storing in DB
    token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
    expiry = datetime.utcnow() + timedelta(minutes=30)  # 30 min expiry
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"password_reset_token": token_hash, "password_reset_token_expiry": expiry.isoformat()}}
    )
    reset_link = f"{base_url}/auth/reset-password?token={reset_token}"
    # Compose metadata section
    meta = f"""
    <ul>
        <li><b>IP Address:</b> {ip or 'Unknown'}</li>
        <li><b>Location:</b> {location or 'Unknown'}</li>
        <li><b>Time:</b> {request_time or 'Unknown'}</li>
        <li><b>Device:</b> {user_agent or 'Unknown'}</li>
        <li><b>ISP:</b> {isp or 'Unknown'}</li>
    </ul>
    """
    # --- Stricter rate limit for whitelisted pairs ---
    redis_conn = await redis_manager.get_redis()
    stricter_limit = STRICTER_WHITELIST_LIMIT
    stricter_period = STRICTER_WHITELIST_PERIOD
    warning_message = ""
    abuse_message = ""
    if ip and await is_pair_whitelisted(email, ip):
        key = f"abuse:reset:whitelist_limit:{email}:{ip}"
        count = await redis_conn.incr(key)
        if count == 1:
            await redis_conn.expire(key, stricter_period)
        if count > stricter_limit:
            # Block further resets for 24h
            await block_reset_pair(email, ip)
            warning_message = "<b>Warning:</b> You have exceeded the allowed number of password reset requests from this device in 24 hours. Further requests are blocked for 24 hours."
            # Track abuse for this pair
            abuse_key = f"abuse:reset:whitelist_abuse:{email}:{ip}"
            abuse_count = await redis_conn.incr(abuse_key)
            if abuse_count == 1:
                await redis_conn.expire(abuse_key, 604800)  # 1 week
            # Log self_abuse event in abuse_events
            await log_reset_abuse_event(
                email=email,
                ip=ip,
                user_agent=user_agent,
                event_type="self_abuse",
                details="Exceeded whitelist limit for password resets",
                whitelisted=True,
                action_taken="blocked",
            )
            # Escalate to ban if repeated self_abuse (3+ times in a week)
            if abuse_count >= STRICTER_WHITELIST_LIMIT:
                await db_manager.get_collection("users").update_one(
                    {"email": email},
                    {"$set": {"is_active": False, "abuse_suspended": True, "abuse_suspended_at": datetime.utcnow()}}
                )
                abuse_message = "<b>Notice:</b> Your account has been suspended due to repeated abuse of the password reset system. Please contact support."
                await redis_conn.sadd("abuse:reset:abuse_ips", ip)
                # Log ban event
                await log_reset_abuse_event(
                    email=email,
                    ip=ip,
                    user_agent=user_agent,
                    event_type="self_abuse",
                    details="Account suspended due to repeated whitelist abuse",
                    whitelisted=True,
                    action_taken="banned",
                )
        elif count == stricter_limit:
            warning_message = "<b>Warning:</b> You are about to reach the maximum allowed password reset requests from this device in 24 hours. Further requests will be blocked."
    html_content = f"""
    <html>
    <body>
        <h2>Password Reset Requested</h2>
        <p>We received a request to reset your password.</p>
        {warning_message}
        {abuse_message}
        <b>Request details:</b>
        {meta}
        <p>If this was <b>you</b>, click the button below to reset your password:</p>
        <a href='{reset_link}' style='padding:10px 20px;background:#007bff;color:#fff;text-decoration:none;border-radius:5px;'>Reset Password</a>
        <p>If this wasn't you, we recommend securing your account.</p>
    </body>
    </html>
    """
    logger.info("Send password reset email to %s", email)
    logger.info("Password reset link: %s", reset_link)
    logger.info("Password reset metadata: IP=%s, UA=%s, Time=%s, Location=%s, ISP=%s", ip, user_agent, request_time, location, isp)
    await email_manager._send_via_console(email, "Password Reset Requested", html_content)

async def send_password_reset_notification(email: str):
    """Send a notification email after successful password reset (console log for now)."""
    subject = "Your password was reset"
    html_content = f"""
    <html><body>
    <h2>Password Changed</h2>
    <p>Your password was successfully reset. If this wasn't you, please contact support immediately.</p>
    </body></html>
    """
    logger.info(f"[NOTIFY EMAIL] To: {email}\nSubject: {subject}\nHTML:\n{html_content}")
    await email_manager._send_via_console(email, subject, html_content)


async def resend_verification_email_service(email: str = None, username: str = None, base_url: str = None):
    """Resend verification email to a user if not already verified. Accepts email or username."""
    if not email and not username:
        raise HTTPException(status_code=400, detail="Email or username required.")
    user = None
    identifier = email or username
    redis_conn = await redis_manager.get_redis()
    # Individual and combined rate limit keys
    rv_key = f"resend_verification:{identifier}"
    fp_key = f"forgot_password:{identifier}"
    combined_key = f"combined_reset_verify:{identifier}"
    rv_count = await redis_conn.incr(rv_key)
    if rv_count == 1:
        await redis_conn.expire(rv_key, 60)
    combined_count = await redis_conn.incr(combined_key)
    if combined_count == 1:
        await redis_conn.expire(combined_key, 60)
    # Check limits: individual and combined
    if rv_count > 2 or combined_count > 3:
        return {"message": "Verification email did not sent"}
    if email:
        user = await db_manager.get_collection("users").find_one({"email": email})
    elif username:
        user = await db_manager.get_collection("users").find_one({"username": username})
    if not user:
        # Do not reveal if user exists for security
        return {"message": "Verification email sent"}
    if user.get("is_verified", False):
        return {"message": "Account already verified"}
    verification_token = secrets.token_urlsafe(32)
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"verification_token": verification_token}}
    )
    verification_link = f"{base_url}auth/verify-email?token={verification_token}"
    logger.info("Verification link (resend): %s", verification_link)
    await send_verification_email(user["email"], verification_link, username=user.get("username"))
    return {"message": "Verification email sent"}


async def create_access_token(data: dict) -> str:
    """
    Create a JWT access token with short expiry and required claims.
    Includes token_version for stateless invalidation.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "sub": data.get("sub")})
    # Add token_version if user is present
    if "username" in data or "sub" in data:
        username = data.get("username") or data.get("sub")
        user = None
        if username:
            user = await db_manager.get_collection("users").find_one({"username": username})
        if user:
            token_version = user.get("token_version", 0)
            to_encode["token_version"] = token_version
    secret_key = getattr(settings, "SECRET_KEY", None)
    # If it's a SecretStr, extract the value
    if hasattr(secret_key, "get_secret_value"):
        secret_key = secret_key.get_secret_value()
    if not isinstance(secret_key, (str, bytes)) or not secret_key:
        logger.error("JWT secret key is missing or invalid. Check your settings.SECRET_KEY.")
        raise RuntimeError("JWT secret key is missing or invalid. Check your settings.SECRET_KEY.")
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str) -> dict:
    """Get the current authenticated user from a JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if await is_token_blacklisted(token):
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
        username: str = payload.get("sub")
        token_version_claim = payload.get("token_version")
        if username is None:
            raise credentials_exception
        user = await db_manager.get_collection("users").find_one({"username": username})
        if user is None:
            raise credentials_exception
        # Check stateless token_version for JWT invalidation
        if token_version_claim is not None:
            user_token_version = user.get("token_version", 0)
            if token_version_claim != user_token_version:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token is no longer valid (password changed or reset)",
                    headers={"WWW-Authenticate": "Bearer"},
                )
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
        logger.error("Unexpected error validating token: %s", e)
        raise credentials_exception from e


async def setup_2fa(current_user: dict, request: TwoFASetupRequest):
    users = db_manager.get_collection("users")
    method = request.method

    # Check if 2FA is already enabled
    if current_user.get("two_fa_enabled", False):
        raise HTTPException(
            status_code=400, 
            detail="2FA is already enabled. Disable 2FA first before setting up again."
        )

    # Check for expired pending state and clean up if needed
    user = await users.find_one({"username": current_user["username"]})
    cleared = await clear_2fa_pending_if_expired(user)
    if cleared:
        user = await users.find_one({"username": current_user["username"]})

    # If setup is already pending, return existing setup info (but never backup codes)
    if user.get("two_fa_pending", False):
        try:
            secret = get_decrypted_totp_secret(user)
        except Exception:
            secret = None
        issuer = "Second Brain Database"
        account_name = f"{user['username']}@app.sbd.rohanbatra.in"
        provisioning_uri = None
        if secret:
            provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)
        qr_code_data = None
        try:
            from io import BytesIO
            import base64
            import qrcode
            if provisioning_uri:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(provisioning_uri)
                qr.make(fit=True)
                img = qr.make_image(fill_color="black", back_color="white")
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                qr_code_data = base64.b64encode(buffered.getvalue()).decode()
        except ImportError:
            qr_code_data = None
            logger.warning("QR code generation failed - qrcode library not available")
        except (OSError, ValueError) as qr_exc:
            qr_code_data = None
            logger.warning("QR code generation failed: %s", qr_exc)
        # Do NOT return backup codes here anymore
        return TwoFASetupResponse(
            enabled=False,
            methods=[],
            totp_secret=secret,
            provisioning_uri=provisioning_uri,
            qr_code_data=qr_code_data
        )

    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")

    secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp_secret(secret)

    # Generate backup codes (10 codes)
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    hashed_backup_codes = [bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') for code in backup_codes]

    # Store backup codes in Redis for 10 min
    try:
        await store_backup_codes_temp(current_user["username"], backup_codes)
    except Exception as e:
        logger.error(f"Failed to store backup codes in Redis for user {current_user['username']}: {e}")

    await users.update_one(
        {"username": current_user["username"]},
        {
            "$set": {
                "two_fa_enabled": False,  # Don't enable until verified!
                "two_fa_pending": True,   # Mark as pending verification
                "two_fa_pending_since": datetime.utcnow().isoformat(),
                "totp_secret": encrypted_secret, 
                "two_fa_methods": ["totp"],
                "backup_codes": hashed_backup_codes,
                "backup_codes_used": []
            }, 
            "$unset": {"email_otp_obj": "", "passkeys": ""}
        }
    )
    user = await users.find_one({"username": current_user["username"]})

    issuer = "Second Brain Database"
    account_name = f"{current_user['username']}@app.sbd.rohanbatra.in"
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)

    try:
        import qrcode
        from io import BytesIO
        import base64
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_data = base64.b64encode(buffered.getvalue()).decode()
    except ImportError:
        qr_code_data = None
        logger.warning("QR code generation failed - qrcode library not available")
    except (OSError, ValueError) as qr_exc:
        qr_code_data = None
        logger.warning("QR code generation failed: %s", qr_exc)

    # Only return backup_codes on first setup call (they are in Redis)
    return TwoFASetupResponse(
        enabled=False,  # Not enabled until verified
        methods=[],     # No methods until verified
        totp_secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_data=qr_code_data
    )


async def reset_2fa(current_user: dict, request: TwoFASetupRequest):
    """
    Reset 2FA for a user who already has it enabled. This generates new secret and backup codes.
    This should require additional verification in production (like password confirmation).
    """
    users = db_manager.get_collection("users")
    method = request.method
    
    # Check if 2FA is enabled (required for reset)
    if not current_user.get("two_fa_enabled", False):
        raise HTTPException(
            status_code=400, 
            detail="2FA is not enabled. Use setup endpoint instead."
        )
    
    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    
    # Recent password confirmation or re-login should be enforced for sensitive actions in production
    
    secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp_secret(secret)
    
    # Generate new backup codes (10 codes)
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    # Hash backup codes for storage
    hashed_backup_codes = [bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') for code in backup_codes]
    
    await users.update_one(
        {"username": current_user["username"]},
        {
            "$set": {
                "two_fa_enabled": True, 
                "totp_secret": encrypted_secret, 
                "two_fa_methods": ["totp"],
                "backup_codes": hashed_backup_codes,
                "backup_codes_used": []  # Reset used backup codes
            }
        }
    )
    user = await users.find_one({"username": current_user["username"]})
    
    # Build provisioning URI for QR code
    username = user.get("username", "user")
    account_name = f"{username}@app.sbd.rohanbatra.in"
    
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=account_name,
        issuer_name="Second Brain Database"
    )
    
    # Generate QR code
    qr_code_data = None
    try:
        import qrcode
        from io import BytesIO
        import base64
        
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_data = base64.b64encode(buffered.getvalue()).decode()
        
    except ImportError:
        qr_code_data = None
        logger.warning("QR code generation failed - qrcode library not available")
    except (OSError, ValueError) as qr_exc:
        qr_code_data = None
        logger.warning("QR code generation failed: %s", qr_exc)
    
    return TwoFASetupResponse(
        enabled=user.get("two_fa_enabled", False),
        methods=user.get("two_fa_methods", []),
        totp_secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_data=qr_code_data
    )


async def verify_2fa(current_user: dict, request: TwoFAVerifyRequest):
    # Check for expired pending state and clean up if needed
    users = db_manager.get_collection("users")
    user = await users.find_one({"username": current_user["username"]})
    cleared = await clear_2fa_pending_if_expired(user)
    if cleared:
        raise HTTPException(status_code=400, detail="2FA setup expired. Please set up 2FA again.")

    method = request.method
    code = request.code
    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    secret = current_user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="TOTP not set up. Please complete 2FA setup before verifying.")
    # Decrypt if needed
    if is_encrypted_totp_secret(secret):
        secret = decrypt_totp_secret(secret)
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid TOTP code. Please check your authenticator app and try again.")
    # If verification successful and 2FA is pending, enable it now
    if current_user.get("two_fa_pending", False):
        await users.update_one(
            {"username": current_user["username"]},
            {
                "$set": {
                    "two_fa_enabled": True,
                    "two_fa_methods": ["totp"]
                },
                "$unset": {"two_fa_pending": "", "two_fa_pending_since": ""}
            }
        )
        backup_codes = await get_backup_codes_temp(current_user["username"])
        await delete_backup_codes_temp(current_user["username"])
        logger.info("2FA enabled for user %s after successful verification", current_user["username"])
        return TwoFAStatus(enabled=True, methods=["totp"], pending=False, backup_codes=backup_codes)
    return TwoFAStatus(
        enabled=current_user.get("two_fa_enabled", False), 
        methods=current_user.get("two_fa_methods", []),
        pending=current_user.get("two_fa_pending", False)
    )


async def get_2fa_status(current_user: dict):
    return TwoFAStatus(
        enabled=current_user.get("two_fa_enabled", False), 
        methods=current_user.get("two_fa_methods", []),
        pending=current_user.get("two_fa_pending", False)
    )


async def disable_2fa(current_user: dict):
    users = db_manager.get_collection("users")
    await users.update_one(
        {"username": current_user["username"]}, 
        {
            "$set": {"two_fa_enabled": False, "two_fa_methods": []}, 
            "$unset": {
                "totp_secret": "", 
                "email_otp_obj": "", 
                "passkeys": "",
                "two_fa_pending": "",  # Clear pending state too
                "backup_codes": "",
                "backup_codes_used": ""
            }
        }
    )
    user = await users.find_one({"username": current_user["username"]})
    return TwoFAStatus(enabled=user.get("two_fa_enabled", False), methods=user.get("two_fa_methods", []), pending=False)


async def log_password_reset_request(email: str, ip: str, user_agent: str, timestamp: str):
    """
    Log a password reset request to Redis for real-time abuse detection.
    Stores a rolling window of requests per email and per (email, ip) pair.
    Privacy/Security: These logs are kept only in Redis, expire after 15 minutes, and are used solely for abuse detection.
    No sensitive data (passwords, tokens) is stored. Only email, IP, user-agent, and timestamp are logged.
    """
    redis_conn = await redis_manager.get_redis()
    # Store per-email list (for abuse detection)
    email_key = f"abuse:reset:email:{email}"
    await redis_conn.lpush(email_key, json.dumps({"ip": ip, "user_agent": user_agent, "timestamp": timestamp}))
    await redis_conn.ltrim(email_key, 0, 49)  # Keep last 50
    await redis_conn.expire(email_key, 900)   # 15 min TTL
    # Store per (email, ip) pair for whitelisting/blocking
    pair_key = f"abuse:reset:pair:{email}:{ip}"
    await redis_conn.lpush(pair_key, json.dumps({"user_agent": user_agent, "timestamp": timestamp}))
    await redis_conn.ltrim(pair_key, 0, 19)  # Keep last 20
    await redis_conn.expire(pair_key, 900)   # 15 min TTL


async def generate_abuse_action_token(email: str, ip: str, action: str, expiry_seconds: int = ABUSE_ACTION_TOKEN_EXPIRY) -> str:
    """
    Generate a secure, single-use, time-limited token for whitelist/block actions.
    Store in Redis with expiry.
    """
    redis_conn = await redis_manager.get_redis()
    token = secrets.token_urlsafe(32)
    key = f"abuse:reset:action:{token}"
    await redis_conn.set(key, json.dumps({"email": email, "ip": ip, "action": action}), ex=expiry_seconds)
    return token

async def consume_abuse_action_token(token: str, expected_action: str) -> tuple:
    """
    Validate and consume a single-use abuse action token. Returns (email, ip) if valid, else (None, None).
    """
    redis_conn = await redis_manager.get_redis()
    key = f"abuse:reset:action:{token}"
    val = await redis_conn.get(key)
    if not val:
        return None, None
    try:
        data = json.loads(val)
        if data.get("action") != expected_action:
            return None, None
        email = data.get("email")
        ip = data.get("ip")
        await redis_conn.delete(key)
        return email, ip
    except Exception:
        return None, None

async def notify_user_of_suspicious_reset(email: str, reasons: list, ip: str = None, user_agent: str = None, request_time: str = None, location: str = None, isp: str = None):
    """
    Notify the user by email if a suspicious password reset attempt is detected for their account.
    Includes secure links to whitelist or block the (email, IP) pair.
    Includes full request metadata for user context and security.
    """
    user = await db_manager.get_collection("users").find_one({"email": email})
    if not user:
        return
    subject = "Suspicious Password Reset Attempt Detected"
    reason_list = "<ul>" + "".join(f"<li>{r}</li>" for r in reasons) + "</ul>"
    # Generate secure tokens for whitelist/block actions
    whitelist_token = await generate_abuse_action_token(email, ip, "whitelist", expiry_seconds=ABUSE_ACTION_TOKEN_EXPIRY)  # 30 min
    block_token = await generate_abuse_action_token(email, ip, "block", expiry_seconds=ABUSE_ACTION_BLOCK_EXPIRY)  # 24h
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    whitelist_link = f"{base_url}auth/confirm-reset-abuse?token={whitelist_token}"
    block_link = f"{base_url}auth/block-reset-abuse?token={block_token}"
    # Compose metadata section (same as password reset email)
    meta = f"""
    <ul>
        <li><b>IP Address:</b> {ip or 'Unknown'}</li>
        <li><b>Location:</b> {location or 'Unknown'}</li>
        <li><b>Time:</b> {request_time or 'Unknown'}</li>
        <li><b>Device:</b> {user_agent or 'Unknown'}</li>
        <li><b>ISP:</b> {isp or 'Unknown'}</li>
    </ul>
    """
    # Add warnings for stricter rate limit and possible suspension
    redis_conn = await redis_manager.get_redis()
    warning_message = ""
    abuse_message = ""
    if ip and await is_pair_whitelisted(email, ip):
        key = f"abuse:reset:whitelist_limit:{email}:{ip}"
        count = await redis_conn.get(key)
        if count is not None:
            count = int(count)
            stricter_limit = STRICTER_WHITELIST_LIMIT
            if count >= stricter_limit:
                warning_message = "<b>Warning:</b> You have exceeded the allowed number of password reset requests from this device in 24 hours. Further requests are blocked for 24 hours."
                abuse_key = f"abuse:reset:whitelist_abuse:{email}:{ip}"
                abuse_count = await redis_conn.get(abuse_key)
                if abuse_count is not None and int(abuse_count) >= STRICTER_WHITELIST_LIMIT:
                    abuse_message = "<b>Notice:</b> Your account has been suspended due to repeated abuse of the password reset system. Please contact support."
                elif count == stricter_limit - 1:
                    warning_message = "<b>Warning:</b> You are about to reach the maximum allowed password reset requests from this device in 24 hours. Further requests will be blocked."
    html_content = f"""
    <html><body>
    <h2>Suspicious Password Reset Attempt</h2>
    <p>We detected a suspicious password reset attempt for your account.</p>
    {warning_message}
    {abuse_message}
    <b>Details:</b>
    {reason_list}
    <b>Request metadata:</b>
    {meta}
    <p>If this was <b>you</b>, you can <a href='{whitelist_link}'>confirm and allow password resets from this device</a> (valid for 30 minutes).</p>
    <p>If this was <b>not you</b>, you can <a href='{block_link}'>block password resets from this device for 24 hours</a>.</p>
    <p><i>These links are single-use and expire automatically for your security.</i></p>
    </body></html>
    """
    logger.info("[SECURITY NOTIFY] To: %s | Subject: %s | Reasons: %s | IP: %s | UA: %s | Time: %s | Location: %s | ISP: %s", email, subject, reasons, ip, user_agent, request_time, location, isp)
    await email_manager._send_via_console(email, subject, html_content)


WHITELIST_KEY = "abuse:reset:whitelist"
BLOCKLIST_KEY = "abuse:reset:blocklist"

async def whitelist_reset_pair(email: str, ip: str):
    redis_conn = await redis_manager.get_redis()
    await redis_conn.sadd(WHITELIST_KEY, f"{email}:{ip}")

async def block_reset_pair(email: str, ip: str):
    redis_conn = await redis_manager.get_redis()
    await redis_conn.sadd(BLOCKLIST_KEY, f"{email}:{ip}")

async def is_pair_whitelisted(email: str, ip: str) -> bool:
    # WARNING: Whitelisting only exempts from abuse/CAPTCHA escalation, NOT from rate limiting.
    # Rate limiting is always enforced regardless of whitelist status to prevent DDoS.
    redis_conn = await redis_manager.get_redis()
    return await redis_conn.sismember(WHITELIST_KEY, f"{email}:{ip}")

async def is_pair_blocked(email: str, ip: str) -> bool:
    redis_conn = await redis_manager.get_redis()
    return await redis_conn.sismember(BLOCKLIST_KEY, f"{email}:{ip}")

async def detect_password_reset_abuse(email: str, ip: str) -> dict:
    """
    Detect abuse for password reset requests:
    - Mass/coordinated attempts (many requests for same email, or from many unique IPs)
    - IP reputation check (VPN/proxy/abuse via IPinfo)
    - Store and flag suspicious activity in Redis
    Privacy/Security: Abuse flags are stored in Redis for 15 minutes only (ephemeral, not persisted).
    No sensitive data is stored. Only metadata for abuse detection and notification.
    Returns a dict: { 'suspicious': bool, 'reasons': [str], 'ip_reputation': str, ... }

    SECURITY NOTE: Whitelisting (email, IP) pairs only exempts from abuse/CAPTCHA escalation.
    Whitelisted pairs are NEVER exempt from rate limiting, which is always enforced
    by security_manager.check_rate_limit in the route handler. This prevents DDoS attacks
    via whitelisted pairs. Do not change this behavior.
    """
    redis_conn = await redis_manager.get_redis()
    suspicious = False
    reasons = []
    ip_reputation = None

    # Check whitelist/blocklist first (see SECURITY NOTE above)
    if await is_pair_whitelisted(email, ip):
        return {"suspicious": False, "reasons": ["Pair whitelisted"], "ip_reputation": None}
    if await is_pair_blocked(email, ip):
        return {"suspicious": True, "reasons": ["Pair blocked"], "ip_reputation": None}

    abuse_key = f"abuse:reset:email:{email}"
    # 1. Check number of requests for this email in last 15 min
    recent_requests = await redis_conn.lrange(abuse_key, 0, 49)
    if recent_requests is None:
        recent_requests = []
    # 2. Count unique IPs for this email
    unique_ips = set()
    for entry in recent_requests:
        try:
            data = json.loads(entry)
            unique_ips.add(data.get("ip"))
        except Exception:
            continue
    # 3. Thresholds (tune as needed)
    max_requests = MAX_RESET_REQUESTS  # e.g. 8+ resets in 15 min
    max_unique_ips = MAX_RESET_UNIQUE_IPS  # e.g. 4+ unique IPs in 15 min
    if len(recent_requests) >= max_requests:
        suspicious = True
        reasons.append(f"High volume: {len(recent_requests)} reset requests in 15 min")
        # Log self_abuse event in abuse_events (MongoDB)
        await log_reset_abuse_event(
            email=email,
            ip=ip,
            user_agent=None,
            event_type="self_abuse",
            details=f"{len(recent_requests)} reset requests in 15 min",
            whitelisted=False,
            action_taken="notified" if suspicious else "none",
        )
    if len(unique_ips) >= max_unique_ips:
        suspicious = True
        reasons.append(f"Many unique IPs: {len(unique_ips)} for this email in 15 min")
        # Log targeted_abuse event in abuse_events
        await log_reset_abuse_event(
            email=email,
            ip=ip,
            user_agent=None,
            event_type="targeted_abuse",
            details=f"{len(unique_ips)} unique IPs in 15 min for this email",
            whitelisted=False,
            action_taken="notified" if suspicious else "none",
        )
    # 4. IP reputation check (IPinfo, fallback to None)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"https://ipinfo.io/{ip}/json")
            data = resp.json()
            if data.get("privacy", {}).get("vpn") or data.get("privacy", {}).get("proxy"):
                suspicious = True
                ip_reputation = "vpn/proxy"
                reasons.append("IP is VPN/proxy (IPinfo)")
            elif data.get("abuse") or data.get("privacy", {}).get("relay"):
                suspicious = True
                ip_reputation = "abuse/relay"
                reasons.append("IP flagged as abuse/relay (IPinfo)")
            else:
                ip_reputation = data.get("org")
    except Exception:
        ip_reputation = None
    # 5. Store flag in Redis for this (email, ip) pair
    if suspicious:
        flag_key = f"abuse:reset:flagged:{email}:{ip}"
        await redis_conn.set(flag_key, json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "reasons": reasons,
            "ip_reputation": ip_reputation
        }), ex=900)  # 15 min expiry
        # Notify user of suspicious activity
        await notify_user_of_suspicious_reset(email, reasons, ip)
    return {"suspicious": suspicious, "reasons": reasons, "ip_reputation": ip_reputation}

async def verify_turnstile_captcha(token: str, remoteip: str = None) -> bool:
    """
    Verify a Cloudflare Turnstile CAPTCHA token. Returns True if valid, False otherwise.
    """
    import httpx
    secret_key = getattr(settings, "TURNSTILE_SECRET_KEY", None)
    if not secret_key:
        logger.error("Turnstile secret key not configured.")
        return False
    data = {
        "secret": secret_key,
        "response": token,
    }
    if remoteip:
        data["remoteip"] = remoteip
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", data=data)
            result = resp.json()
            return result.get("success", False)
    except Exception as e:
        logger.error(f"Turnstile CAPTCHA verification failed: {e}")
        return False

async def is_repeated_violator(user: dict, window_minutes: int = None, min_unique_ips: int = None) -> bool:
    """
    Returns True if the user has abuse events from >= min_unique_ips different IPs
    within the last `window_minutes`, and those events are near-simultaneous (within the window).
    This is stricter than just unique IPs: it requires overlap in time, reducing false positives from mobile/dynamic IPs.
    Uses config values if not provided.
    """
    from second_brain_database.config import settings
    if window_minutes is None:
        window_minutes = getattr(settings, "REPEATED_VIOLATOR_WINDOW_MINUTES", 10)
    if min_unique_ips is None:
        min_unique_ips = getattr(settings, "REPEATED_VIOLATOR_MIN_UNIQUE_IPS", 3)

    # Query abuse_events for self_abuse events for this user in the window
    collection = db_manager.get_collection("abuse_events")
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=window_minutes)
    # Only consider self_abuse events
    query = {
        "email": user.get("email"),
        "event_type": "self_abuse",
        "timestamp": {"$gte": window_start.isoformat()}
    }
    cursor = collection.find(query)
    events = []
    async for doc in cursor:
        events.append(doc)
    # Group by IP
    ip_to_times = {}
    for e in events:
        ts = e["timestamp"]
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                continue
        ip = e["ip"]
        ip_to_times.setdefault(ip, []).append(ts)
    if len(ip_to_times) < min_unique_ips:
        return False
    # Check for overlap: find a time where >=min_unique_ips IPs had an event within window
    all_times = sorted([ts for times in ip_to_times.values() for ts in times])
    for t in all_times:
        count = sum(any(abs((t - ts).total_seconds()) < window_minutes*60 for ts in times) for times in ip_to_times.values())
        if count >= min_unique_ips:
            return True
    return False

# --- Abuse Event Logging ---
async def log_reset_abuse_event(
    email: str,
    ip: str,
    user_agent: str = None,
    event_type: str = None,  # 'self_abuse' or 'targeted_abuse'
    details: str = None,
    whitelisted: bool = False,
    action_taken: str = None,  # e.g., 'blocked', 'notified', 'banned', 'none'
    resolved_by_admin: bool = False,
    notes: str = None,
    timestamp: datetime = None,
):
    """
    Log an abuse event to the abuse_events collection.
    This collection is used for admin/backend review and escalation, and to distinguish between self-abuse and targeted abuse.
    Fields:
      - email: The user's email (indexed)
      - ip: The IP address involved
      - user_agent: The user agent string (optional)
      - event_type: 'self_abuse' (user abusing their own whitelist) or 'targeted_abuse' (user being targeted by others)
      - details: Freeform string for reason/context
      - whitelisted: Was this (email, ip) pair whitelisted at the time?
      - action_taken: What action was taken ('blocked', 'notified', 'banned', etc)
      - resolved_by_admin: Has an admin reviewed/resolved this event?
      - notes: Admin notes
      - timestamp: When the event occurred (defaults to now)
    """
    collection = db_manager.get_collection("abuse_events")
    doc = {
        "email": email,
        "ip": ip,
        "user_agent": user_agent,
        "event_type": event_type,
        "details": details,
        "whitelisted": whitelisted,
        "action_taken": action_taken,
        "resolved_by_admin": resolved_by_admin,
        "notes": notes,
        "timestamp": (timestamp or datetime.utcnow()).isoformat(),
    }
    await collection.insert_one(doc)

# --- Admin Management Endpoints for Abuse ---
# These functions are intended to be called from admin-only API endpoints (see routes.py).
# They provide CRUD operations for the password reset whitelist/blocklist (Redis, fast path)
# and abuse event review (MongoDB, persistent history).

# --- Whitelist/Blocklist Management (Redis, Fast Path) ---
async def admin_add_whitelist_pair(email: str, ip: str) -> bool:
    """
    Add an (email, ip) pair to the password reset whitelist (Redis, fast path).
    Returns True if added, False if already present.
    """
    redis_conn = await redis_manager.get_redis()
    result = await redis_conn.sadd(WHITELIST_KEY, f"{email}:{ip}")
    return bool(result)

async def admin_remove_whitelist_pair(email: str, ip: str) -> bool:
    """
    Remove an (email, ip) pair from the password reset whitelist (Redis).
    Returns True if removed, False if not present.
    """
    redis_conn = await redis_manager.get_redis()
    result = await redis_conn.srem(WHITELIST_KEY, f"{email}:{ip}")
    return bool(result)

async def admin_list_whitelist_pairs() -> list:
    """
    List all (email, ip) pairs currently in the password reset whitelist (Redis).
    Returns a list of dicts: [{"email": ..., "ip": ...}, ...]
    """
    redis_conn = await redis_manager.get_redis()
    pairs = await redis_conn.smembers(WHITELIST_KEY)
    result = []
    for pair in pairs:
        try:
            email, ip = pair.split(":", 1)
            result.append({"email": email, "ip": ip})
        except Exception:
            continue
    return result

async def admin_add_blocklist_pair(email: str, ip: str) -> bool:
    """
    Add an (email, ip) pair to the password reset blocklist (Redis, fast path).
    Returns True if added, False if already present.
    """
    redis_conn = await redis_manager.get_redis()
    result = await redis_conn.sadd(BLOCKLIST_KEY, f"{email}:{ip}")
    return bool(result)

async def admin_remove_blocklist_pair(email: str, ip: str) -> bool:
    """
    Remove an (email, ip) pair from the password reset blocklist (Redis).
    Returns True if removed, False if not present.
    """
    redis_conn = await redis_manager.get_redis()
    result = await redis_conn.srem(BLOCKLIST_KEY, f"{email}:{ip}")
    return bool(result)

async def admin_list_blocklist_pairs() -> list:
    """
    List all (email, ip) pairs currently in the password reset blocklist (Redis).
    Returns a list of dicts: [{"email": ..., "ip": ...}, ...]
    """
    redis_conn = await redis_manager.get_redis()
    pairs = await redis_conn.smembers(BLOCKLIST_KEY)
    result = []
    for pair in pairs:
        try:
            email, ip = pair.split(":", 1)
            result.append({"email": email, "ip": ip})
        except Exception:
            continue
    return result

# --- Abuse Event Review (MongoDB, Persistent) ---
async def admin_list_abuse_events(
    email: str = None,
    event_type: str = None,
    resolved: bool = None,
    limit: int = 100,
) -> list:
    """
    List abuse events for admin review (MongoDB, persistent).
    Supports filtering by email, event_type ('self_abuse' or 'targeted_abuse'), and resolved status.
    Returns a list of events sorted by timestamp (most recent first).
    """
    collection = db_manager.get_collection("abuse_events")
    query = {}
    if email:
        query["email"] = email
    if event_type:
        query["event_type"] = event_type
    if resolved is not None:
        query["resolved_by_admin"] = resolved
    cursor = collection.find(query).sort("timestamp", -1).limit(limit)
    events = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId for JSON
        events.append(doc)
    return events

async def admin_resolve_abuse_event(event_id: str, notes: str = None) -> bool:
    """
    Mark an abuse event as resolved by admin, with optional notes (MongoDB).
    Returns True if updated, False if not found.
    """
    from bson import ObjectId
    collection = db_manager.get_collection("abuse_events")
    result = await collection.update_one(
        {"_id": ObjectId(event_id)},
        {"$set": {"resolved_by_admin": True, "notes": notes or ""}}
    )
    return result.modified_count > 0

async def reconcile_blocklist_whitelist() -> None:
    """
    Make MongoDB the source of truth for blocklist/whitelist reconciliation.
    - Redis will be updated to exactly match MongoDB.
    - Any (email, ip) pair not present in MongoDB will be removed from Redis.
    - Deleting from MongoDB will always remove from Redis on the next sync.
    """
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    users = db_manager.get_collection("users")
    changes = {"mongo_to_redis": 0, "redis_removed": 0}
    for list_type in ["blocklist", "whitelist"]:
        redis_key = f"abuse:reset:{list_type}"
        # 1. Build set of all (email, ip) pairs in MongoDB for this list_type
        mongo_pairs = set()
        async for user in users.find({f"reset_{list_type}": {"$exists": True, "$ne": []}}):
            email = user.get("email")
            for ip in user.get(f"reset_{list_type}", []):
                mongo_pairs.add(f"{email}:{ip}")
        # 2. Get all pairs in Redis
        redis_members = await redis_conn.smembers(redis_key)
        redis_pairs = set(m.decode() if hasattr(m, 'decode') else m for m in redis_members)
        # 3. Remove from Redis any pair not in MongoDB
        for pair in redis_pairs - mongo_pairs:
            await redis_conn.srem(redis_key, pair)
            changes["redis_removed"] += 1
        # 4. Add to Redis any pair in MongoDB not in Redis
        for pair in mongo_pairs - redis_pairs:
            await redis_conn.sadd(redis_key, pair)
            changes["mongo_to_redis"] += 1
    logger.info(json.dumps({"event": "blocklist_whitelist_reconcile", "changes": changes, "ts": datetime.utcnow().isoformat()}))
    logger.info("Blocklist/whitelist reconciliation (MongoDB → Redis) complete.")