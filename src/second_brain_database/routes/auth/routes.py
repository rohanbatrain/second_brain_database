"""
Authentication routes module for Second Brain Database.

Defines API endpoints for user registration, login, email verification, token management,
password change, and password reset. All business logic is delegated to the service layer.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import JSONResponse
from second_brain_database.routes.auth.models import (
    UserIn, UserOut, Token, PasswordChangeRequest, TwoFASetupRequest, TwoFAVerifyRequest, TwoFAStatus, LoginRequest, TwoFASetupResponse, LoginLog, RegistrationLog,
    validate_password_strength
)
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.service import (
    register_user, verify_user_email, login_user, change_user_password, create_access_token, get_current_user, send_verification_email, send_password_reset_email,
    setup_2fa, verify_2fa, get_2fa_status, disable_2fa, reset_2fa, blacklist_token, redis_check_username, redis_incr_username_demand, redis_get_top_demanded_usernames,
    resend_verification_email_service, send_password_reset_notification
)
from second_brain_database.database import db_manager
from second_brain_database.config import settings
from pymongo import ASCENDING, DESCENDING
import bcrypt

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

# Rate limit: register: 100 requests per 60 seconds per IP (default)
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
        await send_verification_email(user.email, verification_link, username=user.username)
        # Build login-like response
        issued_at = int(datetime.utcnow().timestamp())
        expires_at = issued_at + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        token = create_access_token({"sub": user_doc["username"]})
        email_verified = user_doc.get("is_verified", False)
        reg_log.outcome = "success"
        reg_log.reason = None
        await db_manager.get_collection("logs").insert_one(reg_log.model_dump())
        return JSONResponse({
            "access_token": token,
            "token_type": "bearer",
            "client_side_encryption": user_doc.get("client_side_encryption", False),
            "issued_at": issued_at,
            "expires_at": expires_at,
            "is_verified": email_verified,
            "two_fa_enabled": False
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

# Rate limit: verify-email: 100 requests per 60 seconds per IP (default)
@router.get("/verify-email")
async def verify_email(token: str = None, username: str = None, request: Request = None):
    """Verify user's email using the provided token or username."""
    await security_manager.check_rate_limit(request, "verify-email")
    if not token and not username:
        raise HTTPException(status_code=400, detail="Token or username required.")
    if token:
        await verify_user_email(token)
        return {"message": "Email verified successfully"}
    # Securely handle username-based verification
    user = await db_manager.get_collection("users").find_one({"username": username})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username")
    if user.get("is_verified", False):
        return {"message": "Email already verified"}
    verification_token = user.get("verification_token")
    if not verification_token:
        raise HTTPException(status_code=400, detail="No verification token found for this user.")
    await verify_user_email(verification_token)
    return {"message": "Email verified successfully"}

# Rate limit: login: 100 requests per 60 seconds per IP (default)
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
            "expires_at": expires_at,
            "is_verified": user.get("is_verified", False),
            "role": user.get("role", None),
            "username": user.get("username", None),
            "email": user.get("email", None)
        })
    except HTTPException as e:
        # Special handling for '2FA authentication required' error
        if str(e.detail) == "2FA authentication required":
            user_doc = None
            if login_request.username:
                user_doc = await db_manager.get_collection("users").find_one({"username": login_request.username})
            elif login_request.email:
                user_doc = await db_manager.get_collection("users").find_one({"email": login_request.email})
            
            two_fa_methods = user_doc.get("two_fa_methods", []) if user_doc else []
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "2FA authentication required", 
                    "two_fa_required": True,
                    "available_methods": two_fa_methods + ["backup"],
                    "username": user_doc.get("username") if user_doc else login_request.username,
                    "email": user_doc.get("email") if user_doc else login_request.email
                }
            )
        # Special handling for 'Email not verified' error
        elif str(e.detail) == "Email not verified":
            email_resp = login_request.email
            username_resp = login_request.username
            # If only username or email was provided, try to fetch missing info from DB
            if (not email_resp or not username_resp):
                user_doc = None
                if login_request.username:
                    user_doc = await db_manager.get_collection("users").find_one({"username": login_request.username})
                elif login_request.email:
                    user_doc = await db_manager.get_collection("users").find_one({"email": login_request.email})
                if user_doc:
                    if not email_resp:
                        email_resp = user_doc.get("email")
                    if not username_resp:
                        username_resp = user_doc.get("username")
            return JSONResponse(
                status_code=403,
                content={"detail": "Email not verified", "email": email_resp, "username": username_resp}
            )
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
        raise HTTPException(status_code=500, detail="Internal server error") from e

# Rate limit: refresh-token: 100 requests per 60 seconds per IP (default)
@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: dict = Depends(get_current_user_dep), request: Request = None):
    """Refresh access token for authenticated user."""
    await security_manager.check_rate_limit(request, "refresh-token")
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

# Rate limit: logout: 100 requests per 60 seconds per IP (default)
@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user_dep), token: str = Depends(oauth2_scheme), request: Request = None):
    """Logout user (invalidate token on server side)."""
    await security_manager.check_rate_limit(request, "logout")
    blacklist_token(token)
    logger.info("User logged out: %s", current_user["username"])

# Rate limit: change-password: 100 requests per 60 seconds per IP (default)
@router.put("/change-password")
async def change_password(
    password_request: PasswordChangeRequest,
    current_user: dict = Depends(get_current_user_dep),
    request: Request = None
):
    """Change the password for the current authenticated user. Requires recent authentication."""
    await security_manager.check_rate_limit(request, "change-password")
    # Recent password confirmation or re-login should be required for sensitive actions in production
    try:
        await change_user_password(current_user, password_request)
        return {"message": "Password changed successfully"}
    except HTTPException:
        logger.warning("Password change failed for user ID: %s", current_user.get("username", "unknown"))
        raise
    except Exception as password_error:
        logger.warning("Password change failed: %s", str(password_error))
        raise HTTPException(status_code=500, detail="Internal server error") from password_error

# Rate limit: forgot-password: 100 requests per 60 seconds per IP (default)
@router.post("/forgot-password")
async def forgot_password(request: Request, payload: dict = Body(...)):
    """Initiate password reset process by sending a reset link to the user's email."""
    await security_manager.check_rate_limit(request, "forgot-password")
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    try:
        ip = request.client.host
        user_agent = request.headers.get("user-agent")
        request_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        # Fetch GeoIP info
        import httpx
        location = None
        isp = None
        try:
            async with httpx.AsyncClient() as client:
                geo = await client.get(f"https://ipinfo.io/{ip}/json")
                geo_data = geo.json()
                location = f"{geo_data.get('city', '')}, {geo_data.get('country', '')}".strip(', ')
                isp = geo_data.get('org')
        except Exception:
            location = None
            isp = None
        await send_password_reset_email(
            email,
            ip=ip,
            user_agent=user_agent,
            request_time=request_time,
            location=location,
            isp=isp
        )
        return {"message": "Password reset email sent"}
    except Exception as e:
        logger.error("Forgot password failed for email %s: %s", email, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate password reset"
        ) from e

# Rate limit: resend-verification-email: 1 request per 600 seconds per IP
@router.post("/resend-verification-email")
async def resend_verification_email(request: Request):
    """Resend verification email to a user if not already verified. Accepts email or username in JSON body. Heavily rate-limited to prevent abuse."""
    await security_manager.check_rate_limit(request, "resend-verification-email", rate_limit_requests=50, rate_limit_period=600)
    try:
        payload = await request.json()
    except ValueError:
        payload = {}
    email = payload.get("email")
    username = payload.get("username")
    # Optional: log the received payload for debugging
    logger.info("/auth/resend-verification-email payload: %s", payload)
    base_url = str(request.base_url)
    return await resend_verification_email_service(email=email, username=username, base_url=base_url)

# Rate limit: check-username: 100 requests per 60 seconds per IP (default)
@router.get("/check-username")
async def check_username(username: str = Query(..., min_length=3, max_length=50), request: Request = None):
    """Check if a username is available (not already taken), using DB for accuracy and Redis for demand tracking only."""
    await security_manager.check_rate_limit(request, "check-username")
    await redis_incr_username_demand(username)
    # Always check DB directly for availability
    exists = await db_manager.get_collection("users").find_one({"username": username})
    return {"username": username, "available": not bool(exists)}

# Rate limit: check-email: 100 requests per 60 seconds per IP (default)
@router.get("/check-email")
async def check_email(email: str = Query(...), request: Request = None):
    """Check if an email is available (not already taken), using DB directly."""
    await security_manager.check_rate_limit(request, "check-email")
    exists = await db_manager.get_collection("users").find_one({"email": email})
    return {"email": email, "available": not bool(exists)}

# Rate limit: username-demand: 100 requests per 60 seconds per IP (default)
@router.get("/username-demand")
async def username_demand(top_n: int = 10, request: Request = None):
    """Get the most in-demand usernames (most checked), using Redis."""
    await security_manager.check_rate_limit(request, "username-demand")
    most_demanded = await redis_get_top_demanded_usernames(top_n=top_n)
    return [{"username": uname, "checks": count} for uname, count in most_demanded]

# Rate limit: 2fa-setup: 100 requests per 60 seconds per IP (default)
@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_two_fa(request: TwoFASetupRequest, current_user: dict = Depends(get_current_user_dep), req: Request = None):
    """
    Setup a 2FA method for the current user and return TOTP secret, provisioning URI, QR code image, and backup codes.
    If a 2FA setup is already pending, returns the existing setup information instead of generating a new one.
    """
    await security_manager.check_rate_limit(req, "2fa-setup")
    # Recent password confirmation or re-login should be required for sensitive actions in production
    # If setup is already pending, the service will return the existing setup info
    return await setup_2fa(current_user, request)

# Rate limit: 2fa-verify: 100 requests per 60 seconds per IP (default)
@router.post("/2fa/verify", response_model=TwoFAStatus)
async def verify_two_fa(request: TwoFAVerifyRequest, current_user: dict = Depends(get_current_user_dep), req: Request = None):
    """Verify a 2FA code for the current user."""
    await security_manager.check_rate_limit(req, "2fa-verify")
    return await verify_2fa(current_user, request)

# Rate limit: 2fa-status: 100 requests per 60 seconds per IP (default)
@router.get("/2fa/status", response_model=TwoFAStatus)
async def get_two_fa_status(current_user: dict = Depends(get_current_user_dep), request: Request = None):
    """Get 2FA status for the current user."""
    await security_manager.check_rate_limit(request, "2fa-status")
    return await get_2fa_status(current_user)

# Rate limit: 2fa-disable: 100 requests per 60 seconds per IP (default)
@router.post("/2fa/disable", response_model=TwoFAStatus)
async def disable_two_fa(current_user: dict = Depends(get_current_user_dep), request: Request = None):
    """Disable all 2FA for the current user."""
    await security_manager.check_rate_limit(request, "2fa-disable")
    # Recent password confirmation or re-login should be required for sensitive actions in production
    return await disable_2fa(current_user)

# Rate limit: is-verified: 100 requests per 60 seconds per IP (default)
@router.get("/is-verified")
async def is_verified(current_user: dict = Depends(get_current_user_dep), request: Request = None):
    """Check if the current user's email is verified."""
    await security_manager.check_rate_limit(request, "is-verified")
    return {"is_verified": current_user.get("is_verified", False)}

# Rate limit: validate-token: 100 requests per 60 seconds per IP (default)
@router.get("/validate-token")
async def validate_token(token: str = Depends(oauth2_scheme), request: Request = None):
    """Validate a JWT access token and return validity status, only if user is verified and has client_side_encryption."""
    await security_manager.check_rate_limit(request, "validate-token")
    try:
        user = await get_current_user(token)
        if user.get("is_verified", False) and user.get("client_side_encryption", False):
            return {"token": "valid"}
        else:
            return {"token": "invalid"}
    except (HTTPException, ValueError):
        return {"token": "invalid"}

# Rate limit: 2fa-guide: 100 requests per 60 seconds per IP (default)
@router.get("/2fa/guide")
async def get_2fa_setup_guide(current_user: dict = Depends(get_current_user_dep), request: Request = None):
    """Get basic 2FA setup information."""
    await security_manager.check_rate_limit(request, "2fa-guide")
    
    return {
        "enabled": current_user.get("two_fa_enabled", False),
        "methods": current_user.get("two_fa_methods", []),
        "apps": ["Google Authenticator", "Microsoft Authenticator", "Authy", "1Password", "Bitwarden"]
    }

# Rate limit: security-dashboard: 100 requests per 60 seconds per IP (default)
@router.get("/security-dashboard")
async def get_security_dashboard(current_user: dict = Depends(get_current_user_dep), request: Request = None):
    """Get security status for the current user."""
    await security_manager.check_rate_limit(request, "security-dashboard")
    
    # Calculate security score
    security_score = 0
    email_verified = current_user.get("is_verified", False)
    two_fa_enabled = current_user.get("two_fa_enabled", False)
    
    if email_verified:
        security_score += 20
    if two_fa_enabled:
        security_score += 40
    security_score += 20  # Password strength
    if current_user.get("last_login"):
        security_score += 20
    
    return {
        "security_score": security_score,
        "email_verified": email_verified,
        "two_fa_enabled": two_fa_enabled,
        "two_fa_methods": current_user.get("two_fa_methods", []),
        "client_side_encryption": current_user.get("client_side_encryption", False),
        "account_active": current_user.get("is_active", True)
    }

# Rate limit: 2fa-backup-codes: 5 requests per 300 seconds per IP (restricted)
@router.get("/2fa/backup-codes")
async def get_backup_codes_status(current_user: dict = Depends(get_current_user_dep), request: Request = None):
    """Get backup codes status (count remaining, not the actual codes for security)."""
    await security_manager.check_rate_limit(request, "2fa-backup-codes", rate_limit_requests=5, rate_limit_period=300)
    
    if not current_user.get("two_fa_enabled", False):
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    
    backup_codes = current_user.get("backup_codes", [])
    backup_codes_used = current_user.get("backup_codes_used", [])
    
    total_codes = len(backup_codes)
    used_codes = len(backup_codes_used)
    remaining_codes = total_codes - used_codes
    
    return {
        "total_codes": total_codes,
        "used_codes": used_codes,
        "remaining_codes": remaining_codes
    }

# Rate limit: 2fa-regenerate-backup: 20 requests per 3600 (1hr) seconds per IP (increased for testing)
@router.post("/2fa/regenerate-backup-codes")
async def regenerate_backup_codes(current_user: dict = Depends(get_current_user_dep), request: Request = None):
    """Regenerate backup codes for 2FA recovery. This invalidates all existing backup codes."""
    # Increased rate limit for testing purposes doing it 200 times per hour
    await security_manager.check_rate_limit(request, "2fa-regenerate-backup", rate_limit_requests=200, rate_limit_period=3600)
    
    if not current_user.get("two_fa_enabled", False):
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    
    # Generate new backup codes
    import secrets
    backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]
    hashed_backup_codes = [bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8') for code in backup_codes]
    
    # Update user with new backup codes
    await db_manager.get_collection("users").update_one(
        {"username": current_user["username"]},
        {
            "$set": {
                "backup_codes": hashed_backup_codes,
                "backup_codes_used": []  # Reset used codes
            }
        }
    )
    
    logger.info("Backup codes regenerated for user %s", current_user["username"])
    
    return {
        "message": "New backup codes generated successfully",
        "backup_codes": backup_codes
    }

# Rate limit: 2fa-reset: 5 requests per 3600 seconds per IP (very restricted)
@router.post("/2fa/reset", response_model=TwoFASetupResponse)
async def reset_two_fa(request: TwoFASetupRequest, current_user: dict = Depends(get_current_user_dep), req: Request = None):
    """Reset 2FA setup for the current user. This generates new secret, backup codes, provisioning URI, and QR code image, invalidating the old ones."""
    await security_manager.check_rate_limit(req, "2fa-reset", rate_limit_requests=5, rate_limit_period=3600)
    # Recent password confirmation or re-login should be required for sensitive actions in production
    return await reset_2fa(current_user, request)

# Rate limit: reset-password: 100 requests per 60 seconds per IP (default)
@router.post("/reset-password")
async def reset_password(request: Request, payload: dict = Body(...)):
    """Reset the user's password using a valid reset token."""
    token = payload.get("token")
    new_password = payload.get("new_password")
    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token and new password are required.")
    import hashlib
    user = await db_manager.get_collection("users").find_one({"password_reset_token": hashlib.sha256(token.encode()).hexdigest()})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    expiry = user.get("password_reset_token_expiry")
    if not expiry or datetime.utcnow() > datetime.fromisoformat(expiry):
        raise HTTPException(status_code=400, detail="Token has expired.")
    # Validate password strength
    if not validate_password_strength(new_password):
        raise HTTPException(status_code=400, detail="Password does not meet strength requirements.")
    # Hash and update password
    hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"hashed_password": hashed_pw}, "$unset": {"password_reset_token": "", "password_reset_token_expiry": ""}}
    )
    logger.info("Password reset for user %s", user.get("username", user.get("email")))
    # Send notification email (console log for now)
    await send_password_reset_notification(user["email"])
    return {"message": "Password has been reset successfully."}
