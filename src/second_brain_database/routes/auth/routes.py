"""
Authentication routes module.

Provides user registration, login, token management, and password change
functionality with comprehensive security features.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from second_brain_database.routes.auth.models import (
    UserIn, UserOut, Token, PasswordChangeRequest
)
from second_brain_database.security_manager import security_manager
from second_brain_database.routes.auth.service import (
    register_user, verify_user_email, login_user, change_user_password, create_access_token, get_current_user, send_verification_email, send_password_reset_email
)

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])

def get_current_user_dep(token: str = Depends(oauth2_scheme)):
    return get_current_user(token)

@router.post("/register", response_model=UserOut)
async def register(user: UserIn, request: Request):
    await security_manager.check_rate_limit(request, "register")
    try:
        user_doc, verification_token = await register_user(user)
        await send_verification_email(user.email, verification_token)
        return UserOut(username=user.username, email=user.email)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Registration failed for user %s: %s", user.username, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        ) from e

@router.get("/verify-email")
async def verify_email(token: str):
    await verify_user_email(token)
    return {"message": "Email verified successfully."}

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), request: Request = None):
    await security_manager.check_rate_limit(request, "login")
    try:
        user = await login_user(form_data.username, form_data.password)
        access_token = create_access_token({"sub": user["username"]})
        return Token(access_token=access_token, token_type="bearer")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Login failed for user %s: %s", form_data.username, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        ) from e

# @router.get("/me", response_model=UserOut)
# async def read_users_me(current_user: dict = Depends(get_current_user_dep)):
#     """Get current authenticated user"""
#     return UserOut(
#         username=current_user["username"],
#         email=current_user["email"],
#         created_at=current_user.get("created_at"),
#         last_login=current_user.get("last_login"),
#         is_active=current_user.get("is_active", True)
#     )

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: dict = Depends(get_current_user_dep)):
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
async def logout(current_user: dict = Depends(get_current_user_dep)):
    """Logout user (invalidate token on client side)"""
    logger.info("User logged out: %s", current_user["username"])
    return {"message": "Successfully logged out"}

@router.put("/change-password")
async def change_password(
    password_request: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    try:
        await change_user_password(current_user, password_request)
        return {"message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Password change failed for user %s: %s", current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        ) from e

@router.post("/forgot-password")
async def forgot_password(request: Request, email: str):
    """Initiate password reset process by sending a reset link to the user's email."""
    await security_manager.check_rate_limit(request, "forgot-password")
    try:
        await send_password_reset_email(email)
        return {"message": "If the email exists, a password reset link has been sent."}
    except Exception as e:
        logger.error("Forgot password failed for email %s: %s", email, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate password reset"
        ) from e
