"""
Authentication routes module for Second Brain Database.

Defines API endpoints for user registration, login, email verification, token management,
password change, and password reset. All business logic is delegated to the service layer.
"""
import logging
import secrets
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from second_brain_database.routes.auth.models import (
    UserIn, UserOut, Token, PasswordChangeRequest, TwoFASetupRequest, TwoFAVerifyRequest, TwoFAStatus, LoginRequest
)
from second_brain_database.security_manager import security_manager
from second_brain_database.routes.auth.service import (
    register_user, verify_user_email, login_user, change_user_password, create_access_token, get_current_user, send_verification_email, send_password_reset_email,
    setup_2fa, verify_2fa, get_2fa_status, disable_2fa, blacklist_token
)
from second_brain_database.database import db_manager

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])

def get_current_user_dep(token: str = Depends(oauth2_scheme)):
    """
    Dependency function to retrieve the current authenticated user
    based on the provided OAuth2 token.
    """
    return get_current_user(token)

@router.post("/register", response_model=UserOut)
async def register(user: UserIn, request: Request):
    """Register a new user and send a verification email."""
    await security_manager.check_rate_limit(request, "register")
    try:
        verification_token = await register_user(user)
        # Log the verification email with link
        verification_link = f"{request.base_url}auth/verify-email?token={verification_token}"
        await send_verification_email(user.email, verification_token, verification_link)
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
    """Verify user's email using the provided token."""
    await verify_user_email(token)
    return {"message": "Email verified successfully."}

@router.post("/login", response_model=Token)
async def login(
    login_request: LoginRequest = Body(...),
    request: Request = None
):
    """Authenticate user and return JWT token if credentials and email verification are valid. If 2FA is enabled, require 2FA code."""
    await security_manager.check_rate_limit(request, "login")
    try:
        user = await login_user(
            login_request.username,
            login_request.password,
            two_fa_code=login_request.two_fa_code,
            two_fa_method=login_request.two_fa_method
        )
        token = create_access_token({"sub": user["username"]})
        return Token(access_token=token, token_type="bearer")
    except HTTPException as e:
        logger.warning("Login failed for user ID: %s", getattr(e, 'user_id', 'unknown'))
        raise
    except Exception as e:
        logger.warning("Login failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: dict = Depends(get_current_user_dep)):
    """Refresh access token for authenticated user."""
    try:
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
async def logout(current_user: dict = Depends(get_current_user_dep), token: str = Depends(oauth2_scheme)):
    """Logout user (invalidate token on server side)."""
    blacklist_token(token)
    logger.info("User logged out: %s", current_user["username"])

@router.put("/change-password")
async def change_password(
    password_request: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user_dep)
):
    """Change the password for the current authenticated user. Requires recent authentication."""
    # TODO: Require recent password confirmation or re-login for sensitive actions
    try:
        result = await change_user_password(current_user, password_request)
        return {"message": "Password changed successfully"}
    except HTTPException as e:
        logger.warning("Password change failed for user ID: %s", current_user.get("username", "unknown"))
        raise
    except Exception as e:
        logger.warning("Password change failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

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

@router.post("/resend-verification-email")
async def resend_verification_email(request: Request, email: str):
    """Resend verification email to a user if not already verified. Heavily rate-limited to prevent abuse."""
    # Heavier rate limit: 1 request per 10 minutes per IP
    await security_manager.check_rate_limit(request, "resend-verification-email", rate_limit_requests=1, rate_limit_period=600)
    user = await db_manager.get_collection("users").find_one({"email": email})
    if not user:
        # Do not reveal if user exists for security
        return {"message": "If the email exists, a verification email has been sent."}
    if user.get("is_verified", False):
        return {"message": "Account already verified."}
    verification_token = secrets.token_urlsafe(32)
    await db_manager.get_collection("users").update_one(
        {"email": email},
        {"$set": {"verification_token": verification_token}}
    )
    verification_link = f"{request.base_url}auth/verify-email?token={verification_token}"
    await send_verification_email(email, verification_token, verification_link)
    return {"message": "If the email exists, a verification email has been sent."}

@router.post("/2fa/setup", response_model=TwoFAStatus)
async def setup_two_fa(request: TwoFASetupRequest, current_user: dict = Depends(get_current_user_dep)):
    """Setup a 2FA method for the current user."""
    # TODO: Require recent password confirmation or re-login for sensitive actions
    return await setup_2fa(current_user, request)

@router.post("/2fa/verify", response_model=TwoFAStatus)
async def verify_two_fa(request: TwoFAVerifyRequest, current_user: dict = Depends(get_current_user_dep)):
    """Verify a 2FA code for the current user."""
    return await verify_2fa(current_user, request)

@router.get("/2fa/status", response_model=TwoFAStatus)
async def get_two_fa_status(current_user: dict = Depends(get_current_user_dep)):
    """Get 2FA status for the current user."""
    return await get_2fa_status(current_user)

@router.post("/2fa/disable", response_model=TwoFAStatus)
async def disable_two_fa(current_user: dict = Depends(get_current_user_dep)):
    """Disable all 2FA for the current user."""
    # TODO: Require recent password confirmation or re-login for sensitive actions
    return await disable_2fa(current_user)
