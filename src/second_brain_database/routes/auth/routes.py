"""
Authentication routes module.

Provides user registration, login, token management, and password change
functionality with comprehensive security features.
"""
import logging
import re
from datetime import datetime, timedelta

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.models import (
    UserIn, UserOut, Token, PasswordChangeRequest
)

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])

def validate_password_strength(password: str) -> bool:
    """
    Validate password strength requirements.

    Password must contain:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character

    Args:
        password: The password to validate

    Returns:
        bool: True if password meets all requirements, False otherwise
    """
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"\d", password):
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False
    return True

def create_access_token(data: dict) -> str:
    """Create JWT access token with expiration."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current authenticated user from token"""
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

        # Verify user still exists in database
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

@router.post("/register", response_model=UserOut)
async def register(user: UserIn):
    """Register a new user"""
    try:
        # Validate password strength
        if not validate_password_strength(user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long and contain "
                       "uppercase, lowercase, digit, and special character"
            )

        # Check if user already exists
        existing_user = await db_manager.get_collection("users").find_one({
            "$or": [
                {"username": user.username},
                {"email": user.email}
            ]
        })
        if existing_user:
            if existing_user["username"] == user.username:
                logger.warning("Registration attempt with existing username: %s", user.username)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
            logger.warning("Registration attempt with existing email: %s", user.email)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )

        # Hash password and create user
        hashed_pw = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        user_doc = {
            "username": user.username,
            "email": user.email,
            "hashed_password": hashed_pw,
            "created_at": datetime.utcnow(),
            "is_active": True,
            "failed_login_attempts": 0,
            "last_login": None
        }

        result = await db_manager.get_collection("users").insert_one(user_doc)
        if not result.inserted_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )

        logger.info("User registered successfully: %s", user.username)
        return UserOut(username=user.username, email=user.email)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration failed for user %s: %s", user.username, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        ) from e

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate user with email and password and return JWT token"""
    try:
        # Find user by email (form_data.username contains the email)
        user = await db_manager.get_collection("users").find_one({"email": form_data.username})
        if not user:
            logger.warning("Login attempt with non-existent email: %s", form_data.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Check if account is locked due to failed attempts
        if user.get("failed_login_attempts", 0) >= 5:
            logger.warning("Login attempt on locked account: %s", user["username"])
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked due to too many failed login attempts"
            )

        # Check if account is active
        if not user.get("is_active", True):
            logger.warning("Login attempt on inactive account: %s", user["username"])
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive"
            )

        # Verify password
        if not bcrypt.checkpw(form_data.password.encode('utf-8'),
                              user["hashed_password"].encode('utf-8')):
            # Increment failed login attempts
            await db_manager.get_collection("users").update_one(
                {"email": form_data.username},
                {"$inc": {"failed_login_attempts": 1}}
            )
            logger.warning("Failed login attempt for user: %s", user["username"])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Reset failed login attempts and update last login
        await db_manager.get_collection("users").update_one(
            {"email": form_data.username},
            {
                "$set": {"last_login": datetime.utcnow()},
                "$unset": {"failed_login_attempts": ""}
            }
        )

        # Create access token
        access_token = create_access_token({"sub": user["username"]})
        logger.info("Successful login for user: %s", user["username"])

        return Token(access_token=access_token, token_type="bearer")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login failed for user %s: %s", form_data.username, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        ) from e

@router.get("/me", response_model=UserOut)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user"""
    return UserOut(
        username=current_user["username"],
        email=current_user["email"],
        created_at=current_user.get("created_at"),
        last_login=current_user.get("last_login"),
        is_active=current_user.get("is_active", True)
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh access token for authenticated user"""
    try:
        # Create new access token
        access_token = create_access_token({"sub": current_user["username"]})
        logger.info("Token refreshed for user: %s", current_user["username"])

        return Token(access_token=access_token, token_type="bearer")

    except Exception as e:
        logger.error("Token refresh failed for user %s: %s", current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        ) from e

@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout user (invalidate token on client side)"""
    logger.info("User logged out: %s", current_user["username"])
    return {"message": "Successfully logged out"}

@router.put("/change-password")
async def change_password(
    password_request: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    try:
        # Validate new password strength
        if not validate_password_strength(password_request.new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long and contain "
                       "uppercase, lowercase, digit, and special character"
            )

        # Verify old password
        if not bcrypt.checkpw(password_request.old_password.encode('utf-8'),
                              current_user["hashed_password"].encode('utf-8')):
            logger.warning(
                "Password change attempt with wrong old password for user: %s",
                current_user["username"]
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid old password"
            )

        # Hash new password and update
        new_hashed_pw = bcrypt.hashpw(password_request.new_password.encode('utf-8'),
                                      bcrypt.gensalt()).decode('utf-8')
        result = await db_manager.get_collection("users").update_one(
            {"username": current_user["username"]},
            {"$set": {"hashed_password": new_hashed_pw}}
        )

        if not result.modified_count:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )

        logger.info("Password changed successfully for user: %s",
                   current_user["username"])
        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Password change failed for user %s: %s",
                    current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        ) from e
