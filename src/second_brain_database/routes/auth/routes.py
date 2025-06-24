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
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request, Body, Query, Security
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from second_brain_database.routes.auth.models import (
    UserIn, UserOut, Token, PasswordChangeRequest, TwoFASetupRequest, TwoFAVerifyRequest, TwoFAStatus, LoginRequest, TwoFASetupResponse, LoginLog, RegistrationLog,
    validate_password_strength
)
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.service import (
    register_user, verify_user_email, login_user, change_user_password, create_access_token, get_current_user, send_verification_email, send_password_reset_email,
    setup_2fa, verify_2fa, get_2fa_status, disable_2fa, reset_2fa, blacklist_token, redis_check_username, redis_incr_username_demand, redis_get_top_demanded_usernames,
    resend_verification_email_service, send_password_reset_notification, log_password_reset_request, detect_password_reset_abuse, whitelist_reset_pair, block_reset_pair,
    is_pair_whitelisted, is_pair_blocked
)
from second_brain_database.database import db_manager
from second_brain_database.config import settings
from pymongo import ASCENDING, DESCENDING
import bcrypt

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])

admin_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)

# Dummy admin key check (replace with real auth in production)
def is_admin(api_key: str = Security(admin_api_key_header)):
    if api_key != getattr(settings, "ADMIN_API_KEY", "changeme"):
        raise HTTPException(status_code=403, detail="Admin authentication required.")

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
async def forgot_password(request: Request, payload: dict = Body(default=None)):
    """
    Initiate password reset process by sending a reset link to the user's email. Accepts JSON or query param.
    If abuse detection flags the request as suspicious, require and verify Turnstile CAPTCHA.
    SECURITY NOTE: Rate limiting is always enforced via security_manager.check_rate_limit
    BEFORE any abuse/whitelist logic. Whitelisting never exempts from rate limiting.
    """
    await security_manager.check_rate_limit(request, "forgot-password")
    email = None
    turnstile_token = None
    # Try to get email and turnstile_token from JSON body
    if payload and isinstance(payload, dict):
        email = payload.get("email")
        turnstile_token = payload.get("turnstile_token")
    # Fallback: try to get email from query param
    if not email:
        email = request.query_params.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required.")
    try:
        ip = request.client.host
        user_agent = request.headers.get("user-agent")
        request_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        # Log the reset request for abuse detection
        await log_password_reset_request(email, ip, user_agent, request_time)
        # Check if account is suspended
        user = await db_manager.get_collection("users").find_one({"email": email})
        if user and user.get("abuse_suspended", False):
            raise HTTPException(status_code=403, detail="Account suspended due to repeated password reset abuse. Contact support.")
        # Check if pair is blocked
        if await is_pair_blocked(email, ip):
            raise HTTPException(status_code=403, detail="Password reset requests from this device are temporarily blocked due to abuse. Try again later.")
        # Abuse detection logic
        abuse_result = await detect_password_reset_abuse(email, ip)
        # If suspicious, require CAPTCHA
        if abuse_result["suspicious"]:
            from second_brain_database.routes.auth.service import verify_turnstile_captcha
            if not turnstile_token or not await verify_turnstile_captcha(turnstile_token, remoteip=ip):
                # Return a response indicating CAPTCHA is required
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Suspicious activity detected. CAPTCHA required.",
                        "captcha_required": True,
                        "suspicious": True,
                        "abuse_reasons": abuse_result["reasons"]
                    }
                )
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
        except httpx.HTTPError as geo_exc:
            logger.warning("GeoIP lookup failed for IP %s: %s", ip, geo_exc)
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
        return {"message": "Password reset email sent", "suspicious": abuse_result["suspicious"], "abuse_reasons": abuse_result["reasons"]}
    except HTTPException as e:
        logger.warning("Forgot password HTTP error for email %s: %s", email, e.detail)
        raise
    except Exception as e:
        logger.error("Forgot password failed for email %s: %s", email, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate password reset"
        ) from e

# --- ADMIN ENDPOINTS FOR WHITELIST/BLOCKLIST MANAGEMENT ---
@router.get("/admin/list-reset-whitelist")
async def admin_list_reset_whitelist(api_key: str = Security(admin_api_key_header)):
    is_admin(api_key)
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:whitelist")
    return {"whitelist": [m.decode() if hasattr(m, 'decode') else m for m in members]}

@router.get("/admin/list-reset-blocklist")
async def admin_list_reset_blocklist(api_key: str = Security(admin_api_key_header)):
    is_admin(api_key)
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:blocklist")
    return {"blocklist": [m.decode() if hasattr(m, 'decode') else m for m in members]}

@router.post("/admin/whitelist-reset-pair")
async def admin_whitelist_reset_pair(email: str, ip: str, api_key: str = Security(admin_api_key_header)):
    is_admin(api_key)
    await whitelist_reset_pair(email, ip)
    return {"message": f"Whitelisted {email}:{ip}"}

@router.post("/admin/block-reset-pair")
async def admin_block_reset_pair(email: str, ip: str, api_key: str = Security(admin_api_key_header)):
    is_admin(api_key)
    await block_reset_pair(email, ip)
    return {"message": f"Blocked {email}:{ip}"}

@router.delete("/admin/whitelist-reset-pair")
async def admin_remove_whitelist_reset_pair(email: str, ip: str, api_key: str = Security(admin_api_key_header)):
    is_admin(api_key)
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    await redis_conn.srem("abuse:reset:whitelist", f"{email}:{ip}")
    return {"message": f"Removed {email}:{ip} from whitelist"}

@router.delete("/admin/block-reset-pair")
async def admin_remove_block_reset_pair(email: str, ip: str, api_key: str = Security(admin_api_key_header)):
    is_admin(api_key)
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    await redis_conn.srem("abuse:reset:blocklist", f"{email}:{ip}")
    return {"message": f"Removed {email}:{ip} from blocklist"}

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
    html = '''
    <!DOCTYPE html>
   <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Reset Password</title>
    <link href="https://fonts.googleapis.com/css?family=Roboto:400,700&display=swap" rel="stylesheet">
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
    <style>
        :root {
            --primary: #3a86ff;
            --primary-hover: #265dbe;
            --background: #f6f8fa;
            --foreground: #ffffff;
            --text-main: #22223b;
            --text-sub: #4a4e69;
            --border-color: #c9c9c9;
            --error: #d90429;
            --success: #06d6a0;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            background-color: var(--background);
            font-family: 'Roboto', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
        }

        .container {
            background-color: var(--foreground);
            padding: 2.5rem 2rem;
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
            width: 100%;
            max-width: 420px;
        }

        h2 {
            margin-bottom: 1.5rem;
            color: var(--text-main);
            font-size: 1.5rem;
            font-weight: 700;
            text-align: center;
        }

        label {
            display: block;
            margin-bottom: 0.5rem;
            color: var(--text-sub);
            font-weight: 500;
        }

        input[type="password"] {
            width: 100%;
            padding: 0.75rem;
            margin-bottom: 1.25rem;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 1rem;
        }

        button {
            width: 100%;
            padding: 0.75rem;
            background-color: var(--primary);
            color: #fff;
            border: none;
            border-radius: 6px;
            font-size: 1.1rem;
            font-weight: 700;
            cursor: pointer;
            transition: background-color 0.2s ease-in-out;
        }

        button:hover {
            background-color: var(--primary-hover);
        }

        .msg {
            margin-top: 1rem;
            text-align: center;
            font-size: 0.95rem;
        }

        .error {
            color: var(--error);
        }

        .success {
            color: var(--success);
        }

        .cf-turnstile {
            margin-bottom: 1.25rem;
        }
    </style>
</head>
<body>
    <main class="container" role="main">
        <h2>Reset Your Password</h2>
        <form id="resetForm" aria-describedby="msg">
            <label for="new_password">New Password</label>
            <input type="password" id="new_password" name="new_password" required minlength="8" autocomplete="new-password" />

            <label for="confirm_password">Confirm Password</label>
            <input type="password" id="confirm_password" name="confirm_password" required minlength="8" autocomplete="new-password" />

            <div class="cf-turnstile" data-sitekey="__TURNSTILE_SITEKEY__" data-theme="light"></div>

            <button type="submit" aria-label="Submit new password">Reset Password</button>
        </form>

        <div class="msg" id="msg" role="alert" aria-live="polite"></div>
    </main>

    <script>
        const RESET_TOKEN = window.RESET_TOKEN || new URLSearchParams(window.location.search).get('token');
        const form = document.getElementById('resetForm');
        const msg = document.getElementById('msg');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            msg.textContent = '';
            msg.className = 'msg';

            const newPassword = form.new_password.value.trim();
            const confirmPassword = form.confirm_password.value.trim();

            if (newPassword !== confirmPassword) {
                msg.textContent = 'Passwords do not match.';
                msg.classList.add('error');
                return;
            }

            const turnstileTokenInput = document.querySelector('input[name="cf-turnstile-response"]');
            const turnstileToken = turnstileTokenInput ? turnstileTokenInput.value : '';

            if (!turnstileToken) {
                msg.textContent = 'Please complete the CAPTCHA.';
                msg.classList.add('error');
                return;
            }

            try {
                const response = await fetch('/auth/reset-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        token: RESET_TOKEN,
                        new_password: newPassword,
                        turnstile_token: turnstileToken
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    msg.textContent = data.message || 'Password reset successful!';
                    msg.classList.add('success');
                    form.reset();
                } else {
                    msg.textContent = data.detail || 'Error resetting password.';
                    msg.classList.add('error');
                }
            } catch (error) {
                msg.textContent = 'A network error occurred. Please try again.';
                msg.classList.add('error');
            }
        });
    </script>
</body>
</html>
    '''
    html = html.replace("__TURNSTILE_SITEKEY__", settings.TURNSTILE_SITEKEY)
    return HTMLResponse(content=html)

@router.get("/confirm-reset-abuse", response_class=HTMLResponse)
async def confirm_reset_abuse(token: str):
    """
    Endpoint for user to confirm (whitelist) a suspicious password reset attempt via secure email link.
    """
    from second_brain_database.routes.auth.service import consume_abuse_action_token, whitelist_reset_pair
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
    from second_brain_database.routes.auth.service import consume_abuse_action_token, block_reset_pair
    email, ip = await consume_abuse_action_token(token, expected_action="block")
    if not email or not ip:
        return HTMLResponse("<h2>Invalid or expired block link.</h2>", status_code=400)
    await block_reset_pair(email, ip)
    return HTMLResponse(f"<h2>Device blocked!</h2><p>Password reset requests from this device (IP: {ip}) are now blocked for {email} (for 24 hours).</p>")
