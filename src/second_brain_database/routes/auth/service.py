"""
Service layer for authentication and user management.
Handles registration, login, password change, token creation, email logging, and 2FA management.
"""
import logging
import secrets
import pyotp
import bcrypt
import re
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from jose import jwt
from second_brain_database.routes.auth.models import TwoFASetupResponse
from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.models import UserIn, PasswordChangeRequest, validate_password_strength, TwoFASetupRequest, TwoFAVerifyRequest, TwoFAStatus
from second_brain_database.redis_manager import redis_manager
from second_brain_database.managers.email import email_manager

logger = logging.getLogger(__name__)

# Token blacklist (in-memory for demo; use Redis or DB in prod)
TOKEN_BLACKLIST = set()

def blacklist_token(token: str):
    TOKEN_BLACKLIST.add(token)

def is_token_blacklisted(token: str) -> bool:
    return token in TOKEN_BLACKLIST

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
        "client_side_encryption": user.client_side_encryption,
        "registration_app_id": user.registration_app_id
    }
    result = await db_manager.get_collection("users").insert_one(user_doc)
    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    return user_doc, verification_token


async def verify_user_email(token: str):
    """Verify a user's email using the provided token."""
    user = await db_manager.get_collection("users").find_one({"verification_token": token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True}, "$unset": {"verification_token": ""}}
    )
    return user


async def login_user(username: str, password: str, two_fa_code: str = None, two_fa_method: str = None, client_side_encryption: bool = False):
    """Authenticate a user by username and password, handle lockout and failed attempts, and check 2FA if enabled."""
    user = await db_manager.get_collection("users").find_one({"username": username})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("failed_login_attempts", 0) >= 5:
        raise HTTPException(status_code=403, detail="Account locked due to too many failed attempts")
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="User account is inactive, please contact support to reactivate account.")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=403, detail="Email not verified")
    if not bcrypt.checkpw(password.encode('utf-8'), user["hashed_password"].encode('utf-8')):
        await db_manager.get_collection("users").update_one(
            {"username": username},
            {"$inc": {"failed_login_attempts": 1}}
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # 2FA check
    if user.get("two_fa_enabled"):
        if not two_fa_code or not two_fa_method:
            raise HTTPException(status_code=401, detail="2FA code and method required")
        methods = user.get("two_fa_methods", [])
        if two_fa_method not in methods:
            raise HTTPException(status_code=401, detail="Invalid 2FA method")
        if two_fa_method == "totp":
            secret = user.get("totp_secret")
            if not secret:
                raise HTTPException(status_code=401, detail="TOTP not set up")
            totp = pyotp.TOTP(secret)
            if not totp.verify(two_fa_code, valid_window=1):
                raise HTTPException(status_code=401, detail="Invalid TOTP code")
        else:
            raise HTTPException(status_code=401, detail="2FA method not implemented")
    await db_manager.get_collection("users").update_one(
        {"username": username},
        {"$set": {"last_login": datetime.utcnow()}, "$unset": {"failed_login_attempts": ""}}
    )
    # Optionally log or use client_side_encryption here
    return user


async def change_user_password(current_user: dict, password_request: PasswordChangeRequest):
    """Change the password for the current user after validating the old password. Should require recent authentication."""
    # TODO: Enforce recent password confirmation or re-login for sensitive actions
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


async def send_verification_email(email: str, token: str, verification_link: str, username: str = None):
    """Send the verification email using the EmailManager (HTML, multi-provider)."""
    await email_manager.send_verification_email(email, verification_link, username=username)


async def send_password_reset_email(email: str):
    """Log the password reset email and link to the console (no real email sent)."""
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    reset_link = f"{base_url}/auth/reset-password?email={email}&token=FAKE_TOKEN"
    logger.info("Send password reset email to %s", email)
    logger.info("Password reset link: %s", reset_link)


def create_access_token(data: dict) -> str:
    """
    Create a JWT access token with short expiry and required claims.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "sub": data.get("sub")})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str) -> dict:
    """Get the current authenticated user from a JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token is blacklisted",
                headers={"WWW-Authenticate": "Bearer"},
            )
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = await db_manager.get_collection("users").find_one({"username": username})
        if user is None:
            raise credentials_exception
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
    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    secret = pyotp.random_base32()
    await users.update_one(
        {"username": current_user["username"]},
        {"$set": {"two_fa_enabled": True, "totp_secret": secret, "two_fa_methods": ["totp"]}, "$unset": {"email_otp_obj": "", "passkeys": ""}}
    )
    user = await users.find_one({"username": current_user["username"]})
    # Build provisioning URI for QR code
    issuer = getattr(settings, "BASE_URL", "SecondBrain")
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=current_user["username"], issuer_name=issuer)
    return TwoFASetupResponse(
        enabled=user.get("two_fa_enabled", False),
        methods=user.get("two_fa_methods", []),
        totp_secret=secret,
        provisioning_uri=provisioning_uri
    )


async def verify_2fa(current_user: dict, request: TwoFAVerifyRequest):
    method = request.method
    code = request.code
    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    secret = current_user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="TOTP not set up")
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")
    return TwoFAStatus(enabled=current_user.get("two_fa_enabled", False), methods=current_user.get("two_fa_methods", []))


async def get_2fa_status(current_user: dict):
    return TwoFAStatus(enabled=current_user.get("two_fa_enabled", False), methods=current_user.get("two_fa_methods", []))


async def disable_2fa(current_user: dict):
    users = db_manager.get_collection("users")
    await users.update_one({"username": current_user["username"]}, {"$set": {"two_fa_enabled": False, "two_fa_methods": []}, "$unset": {"totp_secret": "", "email_otp_obj": "", "passkeys": ""}})
    user = await users.find_one({"username": current_user["username"]})
    return TwoFAStatus(enabled=user.get("two_fa_enabled", False), methods=user.get("two_fa_methods", []))
