import secrets
from datetime import datetime
import bcrypt
from fastapi import HTTPException, status, Depends
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.models import UserIn, PasswordChangeRequest, validate_password_strength

async def register_user(user: UserIn):
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
        if existing_user["username"] == user.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
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
        "role": user.role
    }
    result = await db_manager.get_collection("users").insert_one(user_doc)
    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )
    return user_doc, verification_token

async def verify_user_email(token: str):
    user = await db_manager.get_collection("users").find_one({"verification_token": token})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token.")
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True}, "$unset": {"verification_token": ""}}
    )
    return user

async def login_user(email: str, password: str):
    user = await db_manager.get_collection("users").find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    if user.get("failed_login_attempts", 0) >= 5:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account locked due to too many failed login attempts"
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    if not bcrypt.checkpw(password.encode('utf-8'), user["hashed_password"].encode('utf-8')):
        await db_manager.get_collection("users").update_one(
            {"email": email},
            {"$inc": {"failed_login_attempts": 1}}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    await db_manager.get_collection("users").update_one(
        {"email": email},
        {"$set": {"last_login": datetime.utcnow()}, "$unset": {"failed_login_attempts": ""}}
    )
    return user

async def change_user_password(current_user: dict, password_request: PasswordChangeRequest):
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
    return True

async def send_verification_email(email: str, token: str):
    """Placeholder for sending verification email."""
    import logging
    logger = logging.getLogger(__name__)
    # Implement your email sending logic here
    logger.info(f"Send verification email to {email} with token: {token}")

async def send_password_reset_email(email: str):
    """Placeholder for sending password reset email."""
    import logging
    logger = logging.getLogger(__name__)
    # Implement your password reset email logic here
    logger.info(f"Send password reset email to {email}")

def create_access_token(data: dict) -> str:
    """Create JWT access token with expiration."""
    from second_brain_database.config import settings
    import jwt
    from datetime import datetime, timedelta
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(token: str) -> dict:
    """Get current authenticated user from token"""
    from fastapi import HTTPException, status
    from second_brain_database.config import settings
    import jwt
    from second_brain_database.database import db_manager
    import logging
    logger = logging.getLogger(__name__)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            logger.warning("Token missing username claim")
            raise credentials_exception
        user = await db_manager.get_collection("users").find_one({"username": username})
        if user is None:
            logger.warning("User %s not found in database", username)
            raise credentials_exception
        return user
    except jwt.ExpiredSignatureError as exc:
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid token: %s", e)
        raise credentials_exception from e
    except Exception as e:
        logger.error("Unexpected error validating token: %s", e)
        raise credentials_exception from e
