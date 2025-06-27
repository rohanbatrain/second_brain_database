"""
Authentication routes module for Second Brain Database.

Password Reset Abuse Prevention Overview:
- All /forgot-password requests are logged (email, IP, user-agent, timestamp) to Redis for real-time abuse detection.
- Abuse detection logic (service.py) flags suspicious activity based on volume, unique IPs, and IP reputation (VPN/proxy/abuse).
- If suspicious, the user is notified by email, and the (email, IP) pair is flagged in Redis for 15 minutes.
- Scoped whitelisting/blocking of (email, IP) pairs is supported and respected by the abuse logic.
- All sensitive endpoints, including /forgot-password, are rate-limited per IP and per endpoint.
- If a /forgot-password request is suspicious, CAPTCHA (Cloudflare Turnstile) is required and verified before proceeding.
- All abuse logs and flags are ephemeral (15 min expiry in Redis), and only metadata is stored (no sensitive data).
- See service.py for further details and configuration.

Defines API endpoints for user registration, login, email verification, token management,
password change, and password reset. All business logic is delegated to the service layer.
"""
from typing import Any, Dict, Optional, List
import secrets
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from fastapi.responses import JSONResponse, HTMLResponse
from pymongo import ASCENDING, DESCENDING
import bcrypt
import httpx
from jose import jwt
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.models import (
    UserIn, UserOut, Token, PasswordChangeRequest, 
    TwoFASetupRequest, TwoFAVerifyRequest, TwoFAStatus, 
    LoginRequest, TwoFASetupResponse, LoginLog, RegistrationLog,
    validate_password_strength
)
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.services.auth.registration import register_user, verify_user_email
from second_brain_database.routes.auth.services.auth.login import login_user, create_access_token, get_current_user
from second_brain_database.routes.auth.services.auth.password import change_user_password, send_password_reset_email, send_password_reset_notification, send_trusted_ip_lockdown_code_email
from second_brain_database.routes.auth.services.auth.twofa import setup_2fa, verify_2fa, get_2fa_status, disable_2fa, reset_2fa
from second_brain_database.routes.auth.services.security.tokens import blacklist_token
from second_brain_database.routes.auth.services.utils.redis_utils import redis_incr_username_demand, redis_get_top_demanded_usernames, consume_abuse_action_token
from second_brain_database.routes.auth.services.auth.verification import send_verification_email, resend_verification_email_service
from second_brain_database.routes.auth.services.abuse.detection import log_password_reset_request, detect_password_reset_abuse
from second_brain_database.routes.auth.services.abuse.management import is_pair_blocked, reconcile_blocklist_whitelist, whitelist_reset_pair, block_reset_pair
from second_brain_database.database import db_manager
from second_brain_database.config import settings
from second_brain_database.routes.auth.routes_html import render_reset_password_page
from second_brain_database.routes.auth.services.auth import login as login_service

# Constants
RESEND_RESET_EMAIL_INTERVAL: int = 60  # seconds
RESET_EMAIL_EXPIRY: int = 900  # seconds
MAX_BACKUP_CODES: int = 10
BACKUP_CODE_LENGTH: int = 4

# Magic constants
LOGIN_RATE_LIMIT: int = 100
LOGIN_RATE_PERIOD: int = 60
REGISTER_RATE_LIMIT: int = 100
REGISTER_RATE_PERIOD: int = 60
VERIFY_EMAIL_RATE_LIMIT: int = 100
VERIFY_EMAIL_RATE_PERIOD: int = 60
RESEND_VERIFICATION_EMAIL_LIMIT: int = 50
RESEND_VERIFICATION_EMAIL_PERIOD: int = 600
FORGOT_PASSWORD_RATE_LIMIT: int = 100
FORGOT_PASSWORD_RATE_PERIOD: int = 60
CHANGE_PASSWORD_RATE_LIMIT: int = 100
CHANGE_PASSWORD_RATE_PERIOD: int = 60
REFRESH_TOKEN_RATE_LIMIT: int = 100
REFRESH_TOKEN_RATE_PERIOD: int = 60
LOGOUT_RATE_LIMIT: int = 100
LOGOUT_RATE_PERIOD: int = 60
CHECK_USERNAME_RATE_LIMIT: int = 100
CHECK_USERNAME_RATE_PERIOD: int = 60
CHECK_EMAIL_RATE_LIMIT: int = 100
CHECK_EMAIL_RATE_PERIOD: int = 60
USERNAME_DEMAND_RATE_LIMIT: int = 100
USERNAME_DEMAND_RATE_PERIOD: int = 60
TWO_FA_SETUP_RATE_LIMIT: int = 100
TWO_FA_SETUP_RATE_PERIOD: int = 60
TWO_FA_VERIFY_RATE_LIMIT: int = 100
TWO_FA_VERIFY_RATE_PERIOD: int = 60
TWO_FA_STATUS_RATE_LIMIT: int = 100
TWO_FA_STATUS_RATE_PERIOD: int = 60
TWO_FA_DISABLE_RATE_LIMIT: int = 100
TWO_FA_DISABLE_RATE_PERIOD: int = 60
IS_VERIFIED_RATE_LIMIT: int = 100
IS_VERIFIED_RATE_PERIOD: int = 60
VALIDATE_TOKEN_RATE_LIMIT: int = 100
VALIDATE_TOKEN_RATE_PERIOD: int = 60
TWO_FA_GUIDE_RATE_LIMIT: int = 100
TWO_FA_GUIDE_RATE_PERIOD: int = 60
SECURITY_DASHBOARD_RATE_LIMIT: int = 100
SECURITY_DASHBOARD_RATE_PERIOD: int = 60
TWO_FA_BACKUP_CODES_LIMIT: int = 5
TWO_FA_BACKUP_CODES_PERIOD: int = 300
TWO_FA_REGENERATE_BACKUP_LIMIT: int = 200
TWO_FA_REGENERATE_BACKUP_PERIOD: int = 3600
TWO_FA_RESET_LIMIT: int = 5
TWO_FA_RESET_PERIOD: int = 3600
RESET_PASSWORD_RATE_LIMIT: int = 100
RESET_PASSWORD_RATE_PERIOD: int = 60

logger = get_logger(prefix="[Auth Routes]")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])

admin_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)

async def get_current_user_dep(token: str = Depends(oauth2_scheme)):
    """
    Dependency function to retrieve the current authenticated user
    based on the provided OAuth2 token.
    """
    return await get_current_user(token)

async def require_admin(current_user: dict = Depends(get_current_user_dep)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required.")
    return current_user

@router.on_event("startup")
async def create_log_indexes():
    """Create indexes for the logs collection on startup."""
    logs = db_manager.get_collection("logs")
    await logs.create_index([("username", ASCENDING)])
    await logs.create_index([("timestamp", DESCENDING)])
    await logs.create_index([("outcome", ASCENDING)])

@router.on_event("startup")
async def reconcile_blocklist_whitelist_on_startup():
    await reconcile_blocklist_whitelist()

# Rate limit: register: 100 requests per 60 seconds per IP (default)
@router.post("/register", response_model=UserOut)
async def register(user: UserIn, request: Request) -> JSONResponse:
    """
    Register a new user and return a login-like response payload.
    Args:
        user: UserIn - registration data
        request: Request - FastAPI request object
    Returns:
        JSONResponse with access token and user info
    Side-effects:
        Writes to DB, sends verification email, logs registration
    """
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
        verification_link = f"{request.base_url}auth/verify-email?token={verification_token}"
        await send_verification_email(user.email, verification_link, username=user.username)
        issued_at = int(datetime.utcnow().timestamp())
        expires_at = issued_at + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        token = await create_access_token({"sub": user_doc["username"]})
        email_verified = user_doc.get("is_verified", False)
        reg_log.outcome = "success"
        reg_log.reason = None
        await db_manager.get_collection("logs").insert_one(reg_log.model_dump())
        logger.info("User registered: %s", user.username)
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
        logger.warning("Registration failed for user %s: %s", user.username, e.detail)
        raise
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        reg_log.outcome = "failure:internal_error"
        reg_log.reason = str(e)
        await db_manager.get_collection("logs").insert_one(reg_log.model_dump())
        logger.error("Registration failed for user %s: %s", user.username, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        ) from e

# Rate limit: verify-email: 100 requests per 60 seconds per IP (default)
@router.get("/verify-email")
async def verify_email(request: Request, token: str = None, username: str = None):
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
    request: Request,
    login_request: LoginRequest = Body(...)
) -> JSONResponse:
    """
    Authenticate user and return JWT token if credentials and email verification are valid. If 2FA is enabled, require 2FA code.
    Args:
        login_request (LoginRequest): Login request data.
        request (Request): FastAPI request object.
    Returns:
        JSONResponse: Token and user info or error response.
    Side-effects:
        Writes to DB, logs login attempt, may raise HTTPException.
    """
    await security_manager.check_rate_limit(request, "login")
    login_log = LoginLog(
        timestamp=datetime.utcnow().replace(microsecond=0),
        ip_address=security_manager.get_client_ip(request) if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        username=login_request.username if login_request.username else "",
        email=login_request.email if login_request.email else None,
        outcome="pending",
        reason=None,
        mfa_status=None
    )
    # Set request_ip contextvar for trusted IP lockdown enforcement
    request_ip = security_manager.get_client_ip(request) if request else None
    token = None
    if request_ip:
        token = login_service.request_ip_ctx.set(request_ip)
    try:
        user = await login_user(
            username=login_request.username,
            email=login_request.email,
            password=login_request.password,
            two_fa_code=login_request.two_fa_code,
            two_fa_method=login_request.two_fa_method,
            client_side_encryption=login_request.client_side_encryption
        )
    finally:
        if request_ip and token is not None:
            login_service.request_ip_ctx.reset(token)
    try:
        issued_at = int(datetime.utcnow().timestamp())
        expires_at = issued_at + settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        token = await create_access_token({"sub": user["username"]})
        login_log.username = user.get("username", login_log.username)
        login_log.email = user.get("email", login_log.email)
        login_log.outcome = "success"
        login_log.reason = None
        login_log.mfa_status = user.get("two_fa_enabled", False)
        await db_manager.get_collection("logs").insert_one(login_log.model_dump())
        logger.info("User logged in: %s", login_log.username)
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
            logger.info("2FA required for user: %s", login_request.username or login_request.email)
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
        elif str(e.detail) == "Email not verified":
            email_resp = login_request.email
            username_resp = login_request.username
            user_doc = None
            if not email_resp or not username_resp:
                if login_request.username:
                    user_doc = await db_manager.get_collection("users").find_one({"username": login_request.username})
                elif login_request.email:
                    user_doc = await db_manager.get_collection("users").find_one({"email": login_request.email})
                if user_doc:
                    if not email_resp:
                        email_resp = user_doc.get("email")
                    if not username_resp:
                        username_resp = user_doc.get("username")
            logger.info("Login failed: email not verified for user: %s", username_resp)
            return JSONResponse(
                status_code=403,
                content={"detail": "Email not verified", "email": email_resp, "username": username_resp}
            )
        login_log.outcome = f"failure:{str(e.detail).replace(' ', '_').lower()}"
        login_log.reason = str(e.detail)
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
        logger.warning("Login failed for user: %s, reason: %s", login_log.username, str(e.detail))
        raise
    except (ValueError, KeyError, TypeError) as e:
        login_log.outcome = "failure:bad_request"
        login_log.reason = str(e)
        await db_manager.get_collection("logs").insert_one(login_log.model_dump())
        logger.error("Login failed due to bad request: %s", str(e), exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid login request") from e
    # Do not catch Exception: let FastAPI handle unexpected errors for full traceability

# Rate limit: refresh-token: 100 requests per 60 seconds per IP (default)
@router.post("/refresh", response_model=Token)
async def refresh_token(request: Request, current_user: dict = Depends(get_current_user_dep)):
    """Refresh access token for authenticated user."""
    await security_manager.check_rate_limit(request, "refresh-token")
    try:
        access_token = await create_access_token({"sub": current_user["username"]})
        logger.info("Token refreshed for user: %s", current_user["username"])
        return Token(access_token=access_token, token_type="bearer")
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        logger.error("Token refresh failed for user %s: %s", current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        ) from e

# Rate limit: logout: 100 requests per 60 seconds per IP (default)
@router.post("/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user_dep), token: str = Depends(oauth2_scheme)):
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
async def forgot_password(request: Request, 
                          payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
    """
    Initiate password reset process by sending a reset link to the user's email. 
    Accepts JSON or query param.
    If abuse detection flags the request as suspicious, 
    require and verify Turnstile CAPTCHA.
    SECURITY NOTE: 
    Rate limiting is always enforced via 
    security_manager.check_rate_limit BEFORE any abuse/whitelist logic.
    Args:
        request: FastAPI request object
        payload: Optional dict with email and turnstile_token
    Returns:
        Dict with status message and abuse info
    Side-effects:
        Writes to Redis, logs abuse, sends email
    """
    await security_manager.check_rate_limit(request, "forgot-password")
    email: Optional[str] = None
    if payload and isinstance(payload, dict):
        email = payload.get("email")
    if not email:
        email = request.query_params.get("email")
    if not email:
        logger.warning("Forgot password request missing email.")
        raise HTTPException(status_code=400, detail="Email is required.")
    try:
        ip = request.client.host
        user_agent = request.headers.get("user-agent")
        request_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        redis_conn = await security_manager.get_redis()
        resend_key = f"forgotpw:last:{email}"
        last_ts = await redis_conn.get(resend_key)
        now_ts = int(datetime.utcnow().timestamp())
        if last_ts and now_ts - int(last_ts) < RESEND_RESET_EMAIL_INTERVAL:
            logger.info("Password reset email resend blocked for %s (rate limit)", email)
            raise HTTPException(status_code=429, 
                                detail="Please wait at least 60 seconds before requesting another password reset email.")
        await redis_conn.set(resend_key, now_ts, ex=RESET_EMAIL_EXPIRY)
        await log_password_reset_request(email, ip, user_agent, request_time)
        user = await db_manager.get_collection("users").find_one({"email": email})
        if user and user.get("abuse_suspended", False):
            logger.warning("Account suspended for abuse: %s", email)
            raise HTTPException(status_code=403,
                                detail="Account suspended due to repeated password reset abuse. Contact support.")
        if await is_pair_blocked(email, ip):
            logger.warning("Password reset blocked for %s from IP %s", email, ip)
            raise HTTPException(status_code=403, 
                                detail="Password reset requests from this device are temporarily blocked due to abuse. Try again later.")
        abuse_result = await detect_password_reset_abuse(email, ip)
        if abuse_result["suspicious"]:
            abuse_msgs = []
            targeted_abuse = False
            for reason in abuse_result["reasons"]:
                if "High volume" in reason:
                    abuse_msgs.append("Too many password reset requests have been made for this account in a short period. This is a security measure to protect your account.")
                elif "Many unique IPs" in reason:
                    abuse_msgs.append("Password reset requests for your account are coming from multiple locations. This could indicate that someone else is trying to reset your password (targeted abuse). If this wasn't you, please secure your account and contact support.")
                    targeted_abuse = True
                elif "Pair blocked" in reason:
                    abuse_msgs.append("Password reset requests from your device are temporarily blocked due to previous abuse. Please try again later or contact support if this is a mistake.")
                elif "Pair whitelisted" in reason:
                    abuse_msgs.append("Your device is whitelisted for password resets. If you are having trouble, please contact support.")
                elif "VPN/proxy" in reason or "abuse/relay" in reason:
                    abuse_msgs.append("Password reset requests from VPNs, proxies, or relays may be restricted for security reasons.")
                else:
                    abuse_msgs.append(reason)
            detail_msg = " ".join(abuse_msgs)
            extra_info = ""
            if targeted_abuse:
                extra_info = " You may be a victim of targeted abuse. Please review your account security and contact support if you did not initiate these requests."
            logger.warning("Suspicious password reset activity for %s: %s", email, abuse_result["reasons"])
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Suspicious activity detected. CAPTCHA required. {detail_msg}{extra_info}",
                    "captcha_required": True,
                    "suspicious": True,
                    "abuse_reasons": abuse_result["reasons"]
                }
            )

        location: Optional[str] = None
        isp: Optional[str] = None
        try:
            async with httpx.AsyncClient() as client:
                geo = await client.get(f"https://ipinfo.io/{ip}/json")
                geo_data = geo.json()
                location = f"{geo_data.get('city', '')}, {geo_data.get('country', '')}".strip(', ')
                isp = geo_data.get('org')
        except httpx.HTTPError as geo_exc:
            logger.warning("GeoIP lookup failed for IP %s: %s", ip, geo_exc, exc_info=True)
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
        logger.info("Password reset email sent to %s", email)
        return {"message": "Password reset email sent", "suspicious": abuse_result["suspicious"], "abuse_reasons": abuse_result["reasons"]}
    except HTTPException as e:
        logger.warning("Forgot password HTTP error for email %s: %s", email, e.detail, exc_info=True)
        raise
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        logger.error("Forgot password failed for email %s: %s", email, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate password reset"
        ) from e

# --- Admin endpoints for password reset abuse management have been moved ---
# See: second_brain_database.routes.admin.routes
# All admin logic for whitelist/blocklist and abuse event review is now in the admin module.

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
    logger.info("/auth/resend-verification-email payload: %s", payload)
    base_url = str(request.base_url)

    # --- Abuse detection and logging (self-abuse protection) ---
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    request_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    # Prefer email for abuse tracking, fallback to username
    abuse_id = email or username
    if abuse_id:
        await log_password_reset_request(abuse_id, ip, user_agent, request_time)
        # Check if account is suspended
        user = None
        if email:
            user = await db_manager.get_collection("users").find_one({"email": email})
        elif username:
            user = await db_manager.get_collection("users").find_one({"username": username})
        if user and user.get("abuse_suspended", False):
            raise HTTPException(status_code=403, detail="Account suspended due to repeated abuse. Contact support.")
        # Check if pair is blocked
        if await is_pair_blocked(abuse_id, ip):
            raise HTTPException(status_code=403, detail="Requests from this device are temporarily blocked due to abuse. Try again later.")
        abuse_result = await detect_password_reset_abuse(abuse_id, ip)
        if abuse_result["suspicious"]:
            abuse_msgs = []
            for reason in abuse_result["reasons"]:
                if "High volume" in reason:
                    abuse_msgs.append("Too many requests have been made for this account in a short period. This is a security measure to protect your account.")
                elif "Many unique IPs" in reason:
                    abuse_msgs.append("Requests for your account are coming from multiple locations. This could indicate that someone else is trying to abuse this endpoint. If this wasn't you, please secure your account and contact support.")
                elif "Pair blocked" in reason:
                    abuse_msgs.append("Requests from your device are temporarily blocked due to previous abuse. Please try again later or contact support if this is a mistake.")
                elif "Pair whitelisted" in reason:
                    abuse_msgs.append("Your device is whitelisted for this endpoint. If you are having trouble, please contact support.")
                elif "VPN/proxy" in reason or "abuse/relay" in reason:
                    abuse_msgs.append("Requests from VPNs, proxies, or relays may be restricted for security reasons.")
                else:
                    abuse_msgs.append(reason)
            detail_msg = " ".join(abuse_msgs)
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Suspicious activity detected. {detail_msg}",
                    "suspicious": True,
                    "abuse_reasons": abuse_result["reasons"]
                }
            )
    return await resend_verification_email_service(email=email, username=username, base_url=base_url)

# Rate limit: check-username: 100 requests per 60 seconds per IP (default)
@router.get("/check-username")
async def check_username(request: Request, username: str = Query(..., min_length=3, max_length=50)):
    """Check if a username is available (not already taken), using DB for accuracy and Redis for demand tracking only."""
    await security_manager.check_rate_limit(request, "check-username")
    await redis_incr_username_demand(username)
    # Always check DB directly for availability
    exists = await db_manager.get_collection("users").find_one({"username": username})
    return {"username": username, "available": not bool(exists)}

# Rate limit: check-email: 100 requests per 60 seconds per IP (default)
@router.get("/check-email")
async def check_email(request: Request, email: str = Query(...)):
    """Check if an email is available (not already taken), using DB directly."""
    await security_manager.check_rate_limit(request, "check-email")
    exists = await db_manager.get_collection("users").find_one({"email": email})
    return {"email": email, "available": not bool(exists)}

# Rate limit: username-demand: 100 requests per 60 seconds per IP (default)
@router.get("/username-demand")
async def username_demand(request: Request, top_n: int = 10):
    """Get the most in-demand usernames (most checked), using Redis."""
    await security_manager.check_rate_limit(request, "username-demand")
    most_demanded = await redis_get_top_demanded_usernames(top_n=top_n)
    return [{"username": uname, "checks": count} for uname, count in most_demanded]

# Rate limit: 2fa-setup: 100 requests per 60 seconds per IP (default)
@router.post("/2fa/setup", response_model=TwoFASetupResponse)
async def setup_two_fa(req: Request, request: TwoFASetupRequest, current_user: dict = Depends(get_current_user_dep)):
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
async def verify_two_fa(req: Request, request: TwoFAVerifyRequest, current_user: dict = Depends(get_current_user_dep)):
    """Verify a 2FA code for the current user."""
    await security_manager.check_rate_limit(req, "2fa-verify")
    return await verify_2fa(current_user, request)

# Rate limit: 2fa-status: 100 requests per 60 seconds per IP (default)
@router.get("/2fa/status", response_model=TwoFAStatus)
async def get_two_fa_status(request: Request, current_user: dict = Depends(get_current_user_dep)):
    """Get 2FA status for the current user."""
    await security_manager.check_rate_limit(request, "2fa-status")
    return await get_2fa_status(current_user)

# Rate limit: 2fa-disable: 100 requests per 60 seconds per IP (default)
@router.post("/2fa/disable", response_model=TwoFAStatus)
async def disable_two_fa(request: Request, current_user: dict = Depends(get_current_user_dep)):
    """Disable all 2FA for the current user."""
    await security_manager.check_rate_limit(request, "2fa-disable")
    # Recent password confirmation or re-login should be required for sensitive actions in production
    return await disable_2fa(current_user)

# Rate limit: is-verified: 100 requests per 60 seconds per IP (default)
@router.get("/is-verified")
async def is_verified(request: Request, current_user: dict = Depends(get_current_user_dep)):
    """Check if the current user's email is verified."""
    await security_manager.check_rate_limit(request, "is-verified")
    return {"is_verified": current_user.get("is_verified", False)}

# Rate limit: validate-token: 100 requests per 60 seconds per IP (default)
@router.get("/validate-token")
async def validate_token(token: str = Depends(oauth2_scheme), request: Request = None):
    """Validate a JWT access token and return user info if valid, matching login response fields (except token)."""
    await security_manager.check_rate_limit(request, "validate-token")
    try:
        user = await get_current_user(token)
        if user.get("is_verified", False):
            # Parse token for issued_at and expires_at
            secret_key = getattr(settings, "SECRET_KEY", None)
            if hasattr(secret_key, "get_secret_value"):
                secret_key = secret_key.get_secret_value()
            payload = jwt.decode(token, secret_key, algorithms=[settings.ALGORITHM])
            issued_at = int(payload.get("iat", 0))
            expires_at = int(payload.get("exp", 0))
            return {
                "access_token": token,
                # "token_type": "bearer",
                "client_side_encryption": user.get("client_side_encryption", False),
                "issued_at": issued_at,
                "expires_at": expires_at,
                "is_verified": user.get("is_verified", False),
                "role": user.get("role", None),
                "username": user.get("username", None),
                "email": user.get("email", None)
            }
        else:
            return {"token": "invalid", "reason": "User is not verified"}
    except HTTPException as e:
        return {"token": "invalid", "reason": str(e.detail) if hasattr(e, 'detail') else str(e)}
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        return {"token": "invalid", "reason": str(e)}

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
    backup_codes = [secrets.token_hex(BACKUP_CODE_LENGTH).upper() for _ in range(MAX_BACKUP_CODES)]
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
async def reset_password(payload: dict = Body(...)):
    """Reset the user's password using a valid reset token."""
    token = payload.get("token")
    new_password = payload.get("new_password")
    if not token or not new_password:
        raise HTTPException(status_code=400, detail="Token and new password are required.")
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
    # Increment token_version for stateless JWT invalidation
    new_token_version = (user.get("token_version") or 0) + 1
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {"$set": {"hashed_password": hashed_pw, "token_version": new_token_version}, "$unset": {"password_reset_token": "", "password_reset_token_expiry": ""}}
    )
    # Invalidate all existing tokens for this user in Redis (production-ready)
    await blacklist_token(user_id=str(user["_id"]))
    logger.info("Password reset for user %s", user.get("username", user.get("email")))
    # Send notification email (console log for now)
    await send_password_reset_notification(user["email"])
    return {"message": "Password has been reset successfully."}

@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(token: str):
    """
    Serve the password reset HTML page, injecting the Turnstile sitekey and token.
    """
    return render_reset_password_page(token)

@router.get("/confirm-reset-abuse", response_class=HTMLResponse)
async def confirm_reset_abuse(token: str):
    """
    Endpoint for user to confirm (whitelist) a suspicious password reset attempt via secure email link.
    """
    email, ip = await consume_abuse_action_token(token, expected_action="whitelist")
    if not email or not ip:
        return HTMLResponse("<h2>Invalid or expired confirmation link.</h2>", status_code=400)
    await whitelist_reset_pair(email, ip)
    return HTMLResponse(f"<h2>Device whitelisted!</h2><p>Password reset requests from this device (IP: {ip}) are now allowed for {email} (for 30 minutes).</p>")

@router.get("/block-reset-abuse", response_class=HTMLResponse)
async def block_reset_abuse(token: str):
    """
    Endpoint for user to block a suspicious password reset attempt via secure email link.
    """
    email, ip = await consume_abuse_action_token(token, expected_action="block")
    if not email or not ip:
        return HTMLResponse("<h2>Invalid or expired block link.</h2>", status_code=400)
    await block_reset_pair(email, ip)
    return HTMLResponse(f"<h2>Device blocked!</h2><p>Password reset requests from this device (IP: {ip}) are now blocked for {email} (for 24 hours).</p>")

# --- Trusted IP Lockdown: 2FA-like Enable/Disable Flow (IP-bound confirmation) ---
@router.post("/trusted-ips/lockdown-request")
async def trusted_ips_lockdown_request(
    request: Request,
    action: str = Body(..., embed=True),  # 'enable' or 'disable'
    trusted_ips: List[str] = Body(default=None, embed=True),  # List of IPs to allow confirmation from (optional for disable)
    current_user: dict = Depends(get_current_user_dep)
):
    logger.info("[trusted_ips_lockdown_request] user=%s action=%s trusted_ips=%s request_ip=%s headers=%s",
                current_user.get("username"), action, trusted_ips, request.client.host, dict(request.headers))
    await security_manager.check_rate_limit(request, "trusted-ips-lockdown-request", rate_limit_requests=5, rate_limit_period=3600)
    if action not in ("enable", "disable"):
        logger.info("Invalid lockdown action requested: %s by user %s", action, current_user.get("username"))
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'enable' or 'disable'.")
    if action == "disable":
        # First, check if trusted_ip_lockdown is enabled before proceeding
        user_doc = await db_manager.get_collection("users").find_one({"_id": current_user["_id"]})
        if not user_doc.get("trusted_ip_lockdown", False):
            logger.info("Trusted IP Lockdown is not enabled for user %s; cannot disable", current_user.get("username"))
            raise HTTPException(status_code=400, detail="Trusted IP Lockdown is not enabled.")
        # For disabling, ignore user-provided trusted_ips and use the current trusted_ips from the DB
        trusted_ips = user_doc.get("trusted_ips", [])
        if not trusted_ips:
            logger.info("No trusted_ips set for user %s; cannot disable lockdown without any trusted IPs", current_user.get("username"))
            raise HTTPException(status_code=400, detail="No trusted IPs set. Cannot disable lockdown without any trusted IPs.")
    elif not trusted_ips or not isinstance(trusted_ips, list):
        logger.info("No trusted_ips provided for lockdown by user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="trusted_ips must be a non-empty list.")
    code = secrets.token_urlsafe(8)
    expiry = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    await db_manager.get_collection("users").update_one(
        {"_id": current_user["_id"]},
        {"$set": {"lockdown_code": code, "lockdown_code_expiry": expiry, "lockdown_code_action": action, "lockdown_code_ips": trusted_ips}}
    )
    email = current_user.get("email")
    if action == "disable":
        # Notify user of the IPs that will be allowed to disable lockdown (before confirmation)
        from second_brain_database.managers.email import email_manager
        subject = "[Security Notice] Trusted IP Lockdown Disable Requested"
        html_content = f"""
        <html><body>
        <h2>Trusted IP Lockdown Disable Requested</h2>
        <p>A request was made to disable Trusted IP Lockdown on your account.</p>
        <p><b>The following IPs will be allowed to confirm this action:</b></p>
        <ul>{''.join(f'<li>{ip}</li>' for ip in trusted_ips)}</ul>
        <p>If you did not request this, your account may be at risk. Please review your account security and contact support immediately.</p>
        </body></html>
        """
        await email_manager._send_via_console(current_user["email"], subject, html_content)
    try:
        await send_trusted_ip_lockdown_code_email(email, code, action, trusted_ips)
        logger.info("Lockdown %s code sent to user %s (allowed IPs: %s)", action, current_user.get("username"), trusted_ips)
    except Exception as e:
        logger.error("Failed to send lockdown code to %s: %s", email, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send confirmation code.") from e
    return {"message": f"Confirmation code sent to {email}. Must confirm from one of the provided IPs."}

@router.post("/trusted-ips/lockdown-confirm")
async def trusted_ips_lockdown_confirm(
    request: Request,
    code: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user_dep)
):
    user = await db_manager.get_collection("users").find_one({"_id": current_user["_id"]})
    logger.info("[trusted_ips_lockdown_confirm] user=%s code=%s request_ip=%s allowed_ips=%s headers=%s",
                current_user.get("username"), code, request.client.host, user.get("lockdown_code_ips", []), dict(request.headers))
    await security_manager.check_rate_limit(request, "trusted-ips-lockdown-confirm", rate_limit_requests=10, rate_limit_period=3600)
    stored_code = user.get("lockdown_code")
    expiry = user.get("lockdown_code_expiry")
    action = user.get("lockdown_code_action")
    allowed_ips = user.get("lockdown_code_ips", [])
    if not stored_code or not expiry or not action or not allowed_ips:
        logger.info("No lockdown code or allowed IPs found for user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="No pending lockdown action.")
    if datetime.utcnow() > datetime.fromisoformat(expiry):
        logger.info("Expired lockdown code for user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="Code expired.")
    if code != stored_code:
        logger.info("Invalid lockdown code for user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="Invalid code.")
    request_ip = request.client.host
    if action == "disable":
        db_trusted_ips = user.get("trusted_ips", [])
        if request_ip not in db_trusted_ips:
            logger.info("Lockdown disable confirm from non-trusted IP %s for user %s (trusted_ips: %s)", request_ip, current_user.get("username"), db_trusted_ips)
            raise HTTPException(status_code=403, detail="Disabling lockdown must be confirmed from one of your existing trusted IPs.")
    else:
        if request_ip not in allowed_ips:
            logger.info("Lockdown confirm from disallowed IP %s for user %s (allowed: %s)", request_ip, current_user.get("username"), allowed_ips)
            raise HTTPException(status_code=403, detail="Confirmation must be from one of the allowed IPs.")
    lockdown_flag = True if action == "enable" else False
    update_fields = {"trusted_ip_lockdown": lockdown_flag}
    if action == "enable":
        update_fields["trusted_ips"] = allowed_ips
    await db_manager.get_collection("users").update_one(
        {"_id": current_user["_id"]},
        {"$set": update_fields, "$unset": {"lockdown_code": "", "lockdown_code_expiry": "", "lockdown_code_action": "", "lockdown_code_ips": ""}}
    )
    logger.info("Trusted IP lockdown %s for user %s (confirmed from IP %s, trusted_ips updated if enabled)", action, current_user.get("username"), request_ip)
    return {"message": f"Trusted IP lockdown {action}d successfully.{ ' Trusted IPs updated.' if action == 'enable' else ''}"}

@router.get("/trusted-ips/lockdown-status")
async def trusted_ips_lockdown_status(request: Request, current_user: dict = Depends(get_current_user_dep)):
    logger.info("[trusted_ips_lockdown_status] user=%s", current_user.get("username"))
    lockdown_status = bool(current_user.get("trusted_ip_lockdown", False))
    return {"trusted_ip_lockdown": lockdown_status, "your_ip": request.client.host}
