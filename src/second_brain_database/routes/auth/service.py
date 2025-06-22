"""
Service layer for authentication and user management.
Handles registration, login, password change, token creation, email logging, and 2FA management.
"""
import logging
import secrets
import pyotp
import bcrypt
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from jose import jwt
from second_brain_database.routes.auth.models import TwoFASetupResponse
from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.models import UserIn, PasswordChangeRequest, validate_password_strength, TwoFASetupRequest, TwoFAVerifyRequest, TwoFAStatus
from second_brain_database.redis_manager import redis_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.utils.crypto import encrypt_totp_secret, decrypt_totp_secret, is_encrypted_totp_secret, migrate_plaintext_secret

logger = logging.getLogger(__name__)

# Token blacklist (in-memory for demo; use Redis or DB in prod)
TOKEN_BLACKLIST = set()

def blacklist_token(token: str):
    TOKEN_BLACKLIST.add(token)

def is_token_blacklisted(token: str) -> bool:
    return token in TOKEN_BLACKLIST

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


async def login_user(username: str = None, email: str = None, password: str = None, two_fa_code: str = None, two_fa_method: str = None, client_side_encryption: bool = False):
    """Authenticate a user by username or email and password, handle lockout and failed attempts, and check 2FA if enabled."""
    if username:
        user = await db_manager.get_collection("users").find_one({"username": username})
    elif email:
        user = await db_manager.get_collection("users").find_one({"email": email})
    else:
        raise HTTPException(status_code=400, detail="Username or email required")
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
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


async def send_password_reset_email(email: str):
    """Log the password reset email and link to the console (no real email sent)."""
    base_url = getattr(settings, "BASE_URL", "http://localhost:8000")
    reset_link = f"{base_url}/auth/reset-password?email={email}&token=FAKE_TOKEN"
    logger.info("Send password reset email to %s", email)
    logger.info("Password reset link: %s", reset_link)


async def resend_verification_email_service(email: str = None, username: str = None, base_url: str = None):
    """Resend verification email to a user if not already verified. Accepts email or username."""
    if not email and not username:
        raise HTTPException(status_code=400, detail="Email or username required.")
    user = None
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
    
    # Check if 2FA is already enabled or pending
    if current_user.get("two_fa_enabled", False):
        raise HTTPException(
            status_code=400, 
            detail="2FA is already enabled. Disable 2FA first before setting up again."
        )
    
    if current_user.get("two_fa_pending", False):
        raise HTTPException(
            status_code=400, 
            detail="2FA setup is already pending. Complete verification or disable to start over."
        )
    
    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    
    secret = pyotp.random_base32()
    encrypted_secret = encrypt_totp_secret(secret)
    
    # Generate backup codes (10 codes)
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    # Hash backup codes for storage
    hashed_backup_codes = [bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') for code in backup_codes]
    
    await users.update_one(
        {"username": current_user["username"]},
        {
            "$set": {
                "two_fa_enabled": False,  # Don't enable until verified!
                "two_fa_pending": True,   # Mark as pending verification
                "totp_secret": encrypted_secret, 
                "two_fa_methods": ["totp"],
                "backup_codes": hashed_backup_codes,
                "backup_codes_used": []
            }, 
            "$unset": {"email_otp_obj": "", "passkeys": ""}
        }
    )
    user = await users.find_one({"username": current_user["username"]})
    
    # Build provisioning URI for QR code
    issuer = "Second Brain Database"
    account_name = f"{current_user['username']}@app.sbd.rohanbatra.in"
    provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(name=account_name, issuer_name=issuer)
    
    # Generate QR code data URL
    try:
        import qrcode
        import qrcode.image.svg
        from io import BytesIO
        import base64
        
        # Create QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64 for data URL
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        qr_code_data = base64.b64encode(buffered.getvalue()).decode()
        qr_code_url = f"data:image/png;base64,{qr_code_data}"
        
    except ImportError:
        qr_code_url = None
        logger.warning("QR code generation failed - qrcode library not available")
    except (OSError, ValueError) as qr_exc:
        qr_code_url = None
        logger.warning("QR code generation failed: %s", qr_exc)
    
    return TwoFASetupResponse(
        enabled=False,  # Not enabled until verified
        methods=[],     # No methods until verified
        totp_secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_url=qr_code_url,
        backup_codes=backup_codes,
        setup_instructions=None
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
    qr_code_url = None
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
        qr_code_url = f"data:image/png;base64,{qr_code_data}"
        
    except ImportError:
        qr_code_url = None
        logger.warning("QR code generation failed - qrcode library not available")
    except (OSError, ValueError) as qr_exc:
        qr_code_url = None
        logger.warning("QR code generation failed: %s", qr_exc)
    
    return TwoFASetupResponse(
        enabled=user.get("two_fa_enabled", False),
        methods=user.get("two_fa_methods", []),
        totp_secret=secret,
        provisioning_uri=provisioning_uri,
        qr_code_url=qr_code_url,
        backup_codes=backup_codes
    )


async def verify_2fa(current_user: dict, request: TwoFAVerifyRequest):
    method = request.method
    code = request.code
    if method != "totp":
        raise HTTPException(status_code=400, detail="Only TOTP 2FA is supported in this demo.")
    
    secret = current_user.get("totp_secret")
    if not secret:
        raise HTTPException(status_code=400, detail="TOTP not set up")
    # Decrypt if needed
    if is_encrypted_totp_secret(secret):
        secret = decrypt_totp_secret(secret)
    
    totp = pyotp.TOTP(secret)
    if not totp.verify(code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")
    
    # If verification successful and 2FA is pending, enable it now
    if current_user.get("two_fa_pending", False):
        users = db_manager.get_collection("users")
        await users.update_one(
            {"username": current_user["username"]},
            {
                "$set": {
                    "two_fa_enabled": True,
                    "two_fa_methods": ["totp"]
                },
                "$unset": {"two_fa_pending": ""}
            }
        )
        logger.info("2FA enabled for user %s after successful verification", current_user["username"])
        return TwoFAStatus(enabled=True, methods=["totp"], pending=False)
    
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
