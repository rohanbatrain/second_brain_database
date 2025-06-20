"""
Authentication routes module for Second Brain Database.

Defines API endpoints for user registration, login, email verification, token management,
password change, and password reset. All business logic is delegated to the service layer.
"""
import logging
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from second_brain_database.routes.auth.models import (
    UserIn, UserOut, Token, PasswordChangeRequest, TwoFASetupRequest, TwoFAVerifyRequest, TwoFAStatus, LoginRequest, TwoFASetupResponse, LoginLog, RegistrationLog
)
from second_brain_database.security_manager import security_manager
from second_brain_database.routes.auth.service import (
    register_user, verify_user_email, login_user, change_user_password, create_access_token, get_current_user, send_verification_email, send_password_reset_email,
    setup_2fa, verify_2fa, get_2fa_status, disable_2fa, blacklist_token, redis_check_username, redis_incr_username_demand, redis_get_top_demanded_usernames
)
from second_brain_database.database import db_manager
from second_brain_database.config import settings
from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])

async def get_current_user_dep(token: str = Depends(oauth2_scheme)):
    """
    Dependency function to retrieve the current authenticated user
    based on the provided OAuth2 token.
    """
    return await get_current_user(token)

@router.on_event("startup")
async def create_log_indexes():
    """Create indexes for the logs collection on startup."""
    logs = db_manager.get_collection("logs")
    await logs.create_index([("username", ASCENDING)])
    await logs.create_index([("timestamp", DESCENDING)])
    await logs.create_index([("outcome", ASCENDING)])

@router.post("/register", response_model=UserOut)
async def register(user: UserIn, request: Request):
    """Register a new user and return a login-like response payload."""
    await security_manager.check_rate_limit(request, "register")
    reg_log = RegistrationLog(
        timestamp=datetime.utcnow().replace(microsecond=0),
        ip_address=security_manager.get_client_ip(request) if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        username=user.username,
        email=user.email,
        outcome="pending",
        reason=None,
        plan=getattr(user, "plan", None),
        role=getattr(user, "role", None)
    )
    try:
        user_doc, verification_token = await register_user(user)
        # Optionally send verification email (but do not return link)
        verification_link = f"{request.base_url}auth/verify-email?token={verification_token}"
        await send_verification_email(user.email, verification_token, verification_link, username=user.username)
        # Build login-like response
        issued_at = int(datetime.utcnow().timestamp())
        expires_at = issued_at + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        token = create_access_token({"sub": user_doc["username"]})
        is_verified = user_doc.get("is_verified", False)
        reg_log.outcome = "success"
        reg_log.reason = None
        await db_manager.get_collection("logs").insert_one(reg_log.model_dump())
        return JSONResponse({
            "access_token": token,
            "token_type": "bearer",
            "client_side_encryption": user_doc.get("client_side_encryption", False),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "is_verified": is_verified
        })
    except HTTPException as e:
        reg_log.outcome = f"failure:{str(e.detail).replace(' ', '_').lower()}"
        reg_log.reason = str(e.detail)
        await db_manager.get_collection("logs").insert_one(reg_log.model_dump())
        raise
    except Exception as e:
        reg_log.outcome = "failure:internal_error"
        reg_log.reason = str(e)
        await db_manager.get_collection("logs").insert_one(reg_log.model_dump())
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

@router.post("/login")
async def login(
    login_request: LoginRequest = Body(...),
    request: Request = None
):
    """Authenticate user and return JWT token if credentials and email verification are valid. If 2FA is enabled, require 2FA code."""
    await security_manager.check_rate_limit(request, "login")
    login_log = LoginLog(
        timestamp=datetime.utcnow().replace(microsecond=0),  # ISO 8601 UTC, no microseconds
        ip_address=security_manager.get_client_ip(request) if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        username=login_request.username if login_request.username else "",
        email=login_request.email if login_request.email else None,
        outcome="pending",
        reason=None,
        mfa_status=None
    )
    try:
        user = await login_user(
            username=login_request.username,
            email=login_request.email,
            password=login_request.password,
            two_fa_code=login_request.two_fa_code,
            two_fa_method=login_request.two_fa_method,
            client_side_encryption=login_request.client_side_encryption
        )
        # Token creation
        issued_at = int(datetime.utcnow().timestamp())
        expires_at = issued_at + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        token = create_access_token({"sub": user["username"]})
        login_log.username = user.get("username", login_log.username)
        login_log.email = user.get("email", login_log.email)
        login_log.outcome = "success"
        login_log.reason = None
        login_log.mfa_status = user.get("two_fa_enabled", False)
        await db_manager.get_collection("logs").insert_one(login_log.model_dump())
        return JSONResponse({
            "access_token": token,
            "token_type": "bearer",
            "client_side_encryption": user.get("client_side_encryption", False),
            "issued_at": issued_at,
            "expires_at": expires_at
        })
    except HTTPException as e:
        login_log.outcome = f"failure:{str(e.detail).replace(' ', '_').lower()}"
        login_log.reason = str(e.detail)
        # Try to get email if possible
        user_doc = None
        if login_request.username:
            user_doc = await db_manager.get_collection("users").find_one({"username": login_request.username})
        elif login_request.email:
            user_doc = await db_manager.get_collection("users").find_one({"email": login_request.email})
        if user_doc:
            login_log.username = user_doc.get("username", login_log.username)
            login_log.email = user_doc.get("email", login_log.email)
            login_log.mfa_status = user_doc.get("two_fa_enabled", False)
        await db_manager.get_collection("logs").insert_one(login_log.model_dump())
        logger.warning("Login failed for user ID: %s", getattr(e, 'user_id', 'unknown'))
        raise
    except Exception as e:
        login_log.outcome = "failure:internal_error"
        login_log.reason = str(e)
        user_doc = None
        if login_request.username:
            user_doc = await db_manager.get_collection("users").find_one({"username": login_request.username})
        elif login_request.email:
            user_doc = await db_manager.get_collection("users").find_one({"email": login_request.email})
        if user_doc:
            login_log.username = user_doc.get("username", login_log.username)
            login_log.email = user_doc.get("email", login_log.email)
            login_log.mfa_status = user_doc.get("two_fa_enabled", False)
        await db_manager.get_collection("logs").insert_one(login_log.model_dump())
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
        await change_user_password(current_user, password_request)
        return {"message": "Password changed successfully"}
    except HTTPException as e:
        logger.warning("Password change failed for user ID: %s", current_user.get("username", "unknown"))
        raise
    except Exception as e:
        logger.warning("Password change failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Internal server error") from e

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

@router.get("/check-username")
async def check_username(username: str = Query(..., min_length=3, max_length=50)):
    """Check if a username is available (not already taken), using DB for accuracy and Redis for demand tracking only."""
    await redis_incr_username_demand(username)
    # Always check DB directly for availability
    exists = await db_manager.get_collection("users").find_one({"username": username})
    return {"username": username, "available": not bool(exists)}

@router.get("/check-email")
async def check_email(email: str = Query(...)):
    """Check if an email is available (not already taken), using DB directly."""
    exists = await db_manager.get_collection("users").find_one({"email": email})
    return {"email": email, "available": not bool(exists)}

@router.get("/username-demand")
async def username_demand(top_n: int = 10):
    """Get the most in-demand usernames (most checked), using Redis."""
    most_demanded = await redis_get_top_demanded_usernames(top_n=top_n)
    return [{"username": uname, "checks": count} for uname, count in most_demanded]

@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_two_fa(request: TwoFASetupRequest, current_user: dict = Depends(get_current_user_dep)):
    """Setup a 2FA method for the current user and return TOTP secret and provisioning URI."""
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

@router.get("/is-verified")
async def is_verified(current_user: dict = Depends(get_current_user_dep)):
    """Check if the current user's email is verified."""
    return {"is_verified": current_user.get("is_verified", False)}
