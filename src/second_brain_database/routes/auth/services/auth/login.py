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

logger = get_logger()

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
