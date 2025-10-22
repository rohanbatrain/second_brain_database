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

from datetime import datetime, timedelta
import hashlib
import secrets
from typing import Any, Dict, List, Optional

import bcrypt
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
import httpx
from jose import jwt
from pymongo import ASCENDING, DESCENDING

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.docs.models import (
    StandardErrorResponse,
    StandardSuccessResponse,
    ValidationErrorResponse,
    create_error_responses,
    create_standard_responses,
)
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.logging_utils import (
    auth_logger,
    extract_request_info,
    set_auth_context as set_auth_logging_context,
)
from second_brain_database.routes.auth.models import (
    AuthFallbackResponse,
    AuthMethodsResponse,
    AuthPreferenceResponse,
    LoginLog,
    LoginRequest,
    PasswordChangeRequest,
    PermanentTokenListResponse,
    PermanentTokenRequest,
    PermanentTokenResponse,
    RegistrationLog,
    Token,
    TokenRevocationResponse,
    TwoFASetupRequest,
    TwoFASetupResponse,
    TwoFAStatus,
    TwoFAVerifyRequest,
    UserIn,
    UserOut,
    validate_password_strength,
    WebAuthnAuthenticationBeginRequest,
    WebAuthnAuthenticationBeginResponse,
    WebAuthnAuthenticationCompleteRequest,
    WebAuthnAuthenticationCompleteResponse,
    WebAuthnCredentialDeletionResponse,
    WebAuthnCredentialListResponse,
    WebAuthnRegistrationBeginRequest,
    WebAuthnRegistrationBeginResponse,
    WebAuthnRegistrationCompleteRequest,
    WebAuthnRegistrationCompleteResponse,
)
from second_brain_database.routes.auth.routes_html import render_reset_password_page
from second_brain_database.routes.auth.services.abuse.detection import (
    detect_password_reset_abuse,
    log_password_reset_request,
)
from second_brain_database.routes.auth.services.abuse.management import (
    block_reset_pair,
    is_pair_blocked,
    reconcile_blocklist_whitelist,
    whitelist_reset_pair,
)
from second_brain_database.routes.auth.services.auth import login as login_service
from second_brain_database.routes.auth.services.auth.login import (
    create_access_token, 
    get_current_user, 
    login_user,
    # get_user_auth_methods,
    set_user_auth_preference,
    check_auth_fallback_available,
)
from second_brain_database.routes.auth.services.auth.password import (
    change_user_password,
    send_password_reset_email,
    send_password_reset_notification,
    send_trusted_ip_lockdown_code_email,
    send_user_agent_lockdown_code_email,
    send_blocked_user_agent_notification,
)
from second_brain_database.routes.auth.services.auth.registration import register_user, verify_user_email
from second_brain_database.routes.auth.services.auth.twofa import (
    disable_2fa,
    get_2fa_status,
    reset_2fa,
    setup_2fa,
    verify_2fa,
)
from second_brain_database.routes.auth.services.auth.verification import (
    resend_verification_email_service,
    send_verification_email,
)
from second_brain_database.routes.auth.services.webauthn.authentication import (
    begin_authentication,
    complete_authentication,
)
from second_brain_database.routes.auth.services.webauthn.registration import (
    begin_registration,
)
from second_brain_database.utils.logging_utils import (
    log_auth_failure,
    log_auth_success,
    log_security_event,
)
from second_brain_database.routes.auth.services.security.tokens import blacklist_token
from second_brain_database.routes.auth.services.utils.redis_utils import (
    consume_abuse_action_token,
    redis_get_top_demanded_usernames,
    redis_incr_username_demand,
)
from second_brain_database.utils.logging_utils import (
    ip_address_context,
    log_database_operation,
    log_performance,
    request_id_context,
    user_id_context,
)
from second_brain_database.routes.auth.dependencies import enforce_all_lockdowns, get_current_user_dep

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
WEBAUTHN_CREDENTIALS_LIST_RATE_LIMIT: int = 100
WEBAUTHN_CREDENTIALS_LIST_RATE_PERIOD: int = 60
WEBAUTHN_CREDENTIALS_DELETE_RATE_LIMIT: int = 50
WEBAUTHN_CREDENTIALS_DELETE_RATE_PERIOD: int = 60
WEBAUTHN_REGISTER_BEGIN_RATE_LIMIT: int = 50
WEBAUTHN_REGISTER_BEGIN_RATE_PERIOD: int = 60
WEBAUTHN_REGISTER_COMPLETE_RATE_LIMIT: int = 50
WEBAUTHN_REGISTER_COMPLETE_RATE_PERIOD: int = 60
WEBAUTHN_AUTH_BEGIN_RATE_LIMIT: int = 50
WEBAUTHN_AUTH_BEGIN_RATE_PERIOD: int = 60
WEBAUTHN_AUTH_COMPLETE_RATE_LIMIT: int = 50
WEBAUTHN_AUTH_COMPLETE_RATE_PERIOD: int = 60

logger = get_logger(prefix="[Auth Routes]")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["auth"])

admin_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)


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
@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    summary="Register a new user account",
    description="""
    Register a new user account with email verification.
    
    **Process:**
    1. Validates user input (username, email, password strength)
    2. Creates user account in database
    3. Sends email verification link
    4. Returns JWT token for immediate API access
    
    **Security Features:**
    - Password strength validation (8+ chars, mixed case, numbers, symbols)
    - Username format validation (alphanumeric, dashes, underscores only)
    - Email format validation and normalization
    - Rate limiting (100 requests per 60 seconds per IP)
    - Comprehensive audit logging
    
    **Email Verification:**
    - Account is created but marked as unverified
    - Verification email sent automatically
    - Some features may be restricted until email is verified
    
    **Response:**
    Returns JWT token and user information for immediate API access.
    """,
    responses={
        201: {
            "description": "User registered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "token_type": "bearer",
                        "client_side_encryption": False,
                        "issued_at": 1640993400,
                        "expires_at": 1640995200,
                        "is_verified": False,
                        "two_fa_enabled": False,
                    }
                }
            },
        },
        400: {
            "description": "Invalid input data",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "validation_error",
                        "message": "Invalid registration data",
                        "details": {"field": "password", "issue": "too_weak"},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        409: {
            "description": "Username or email already exists",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "resource_conflict",
                        "message": "Username or email already exists",
                        "details": {"field": "username", "issue": "already_exists"},
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        422: {"description": "Validation failed", "model": ValidationErrorResponse},
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
    tags=["Authentication"],
)
async def register(user: UserIn, request: Request) -> JSONResponse:
    """
    Register a new user account with comprehensive validation and security features.

    This endpoint creates a new user account, sends an email verification link,
    and returns a JWT token for immediate API access.
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
        role=getattr(user, "role", None),
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
        return JSONResponse(
            {
                "access_token": token,
                "token_type": "bearer",
                "client_side_encryption": user_doc.get("client_side_encryption", False),
                "issued_at": issued_at,
                "expires_at": expires_at,
                "is_verified": email_verified,
                "two_fa_enabled": False,
            }
        )
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
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Registration failed") from e


# Rate limit: verify-email: 100 requests per 60 seconds per IP (default)
@router.get("/verify-email")
@log_performance("email_verification")
async def verify_email(request: Request, token: str = None, username: str = None):
    """Verify user's email using the provided token or username."""
    # Extract request info and set context
    request_info = extract_request_info(request)
    set_auth_logging_context(ip_address=request_info["ip_address"])

    await security_manager.check_rate_limit(request, "verify-email")
    
    # Check if request is from a web browser (render HTML) or API client (return JSON)
    user_agent = request.headers.get("user-agent", "").lower()
    accept_header = request.headers.get("accept", "").lower()
    is_browser = "mozilla" in user_agent or "chrome" in user_agent or "safari" in user_agent or "text/html" in accept_header
    is_mobile_app = any(app in user_agent for app in ["emotion_tracker", "dart", "flutter"])

    if not token and not username:
        auth_logger.log_email_verification(
            user_id=username or "unknown",
            email="unknown",
            ip_address=request_info["ip_address"],
            success=False,
            reason="Token or username required",
        )
        if is_browser and not is_mobile_app:
            from second_brain_database.routes.auth.main import render_email_verification_page
            return render_email_verification_page(request, success=False, message="Verification Failed: No Token Provided")
        raise HTTPException(status_code=400, detail="Token or username required.")

    try:
        if token:
            await verify_user_email(token)
            # Log successful verification (token-based)
            auth_logger.log_email_verification(
                user_id="token_based", email="unknown", ip_address=request_info["ip_address"], success=True
            )
            if is_browser and not is_mobile_app:
                from second_brain_database.routes.auth.main import render_email_verification_page
                return render_email_verification_page(request, success=True)
            return {"message": "Email verified successfully"}

        # Securely handle username-based verification
        user = await db_manager.get_collection("users").find_one({"username": username})
        if not user:
            auth_logger.log_email_verification(
                user_id=username,
                email="unknown",
                ip_address=request_info["ip_address"],
                success=False,
                reason="Invalid username",
            )
            if is_browser and not is_mobile_app:
                from second_brain_database.routes.auth.main import render_email_verification_page
                return render_email_verification_page(request, success=False, message="Verification Failed: Invalid Username")
            raise HTTPException(status_code=400, detail="Invalid username")

        if user.get("is_verified", False):
            auth_logger.log_email_verification(
                user_id=username,
                email=user.get("email", "unknown"),
                ip_address=request_info["ip_address"],
                success=True,
                reason="Already verified",
            )
            if is_browser and not is_mobile_app:
                from second_brain_database.routes.auth.main import render_email_verification_page
                return render_email_verification_page(request, success=True, message="Email Already Verified")
            return {"message": "Email already verified"}

        verification_token = user.get("verification_token")
        if not verification_token:
            auth_logger.log_email_verification(
                user_id=username,
                email=user.get("email", "unknown"),
                ip_address=request_info["ip_address"],
                success=False,
                reason="No verification token found",
            )
            if is_browser and not is_mobile_app:
                from second_brain_database.routes.auth.main import render_email_verification_page
                return render_email_verification_page(request, success=False, message="Verification Failed: No Token Found")
            raise HTTPException(status_code=400, detail="No verification token found for this user.")

        await verify_user_email(verification_token)

        # Log successful verification
        auth_logger.log_email_verification(
            user_id=username, email=user.get("email", "unknown"), ip_address=request_info["ip_address"], success=True
        )
        
        if is_browser and not is_mobile_app:
            from second_brain_database.routes.auth.main import render_email_verification_page
            return render_email_verification_page(request, success=True)
        return {"message": "Email verified successfully"}

    except HTTPException as e:
        if is_browser and not is_mobile_app:
            from second_brain_database.routes.auth.main import render_email_verification_page
            error_msg = str(e.detail) if hasattr(e, 'detail') else "Verification Failed"
            return render_email_verification_page(request, success=False, message=f"Verification Failed: {error_msg}")
        raise
    except Exception as e:
        auth_logger.log_email_verification(
            user_id=username or "unknown",
            email="unknown",
            ip_address=request_info["ip_address"],
            success=False,
            reason=f"Internal error: {str(e)}",
        )
        logger.error("Email verification failed: %s", str(e), exc_info=True)
        if is_browser and not is_mobile_app:
            from second_brain_database.routes.auth.main import render_email_verification_page
            return render_email_verification_page(request, success=False, message="Verification Failed: Internal Error")
        raise HTTPException(status_code=500, detail="Email verification failed")


# Rate limit: login: 100 requests per 60 seconds per IP (default)
@router.post(
    "/login",
    summary="Authenticate user and obtain JWT token",
    description="""
    Authenticate user credentials and return JWT token for API access.
    
    **Authentication Methods:**
    - Username + Password
    - Email + Password
    - Username/Email + Password + 2FA Code (if 2FA enabled)
    
    **Input Formats:**
    - JSON: Use LoginRequest model with flexible authentication options
    - Form Data: OAuth2 compatible form data (username/password)
    
    **2FA Flow:**
    1. First attempt: Send username/email + password
    2. If 2FA required: Response includes available 2FA methods
    3. Second attempt: Include two_fa_code and two_fa_method
    
    **Security Features:**
    - Rate limiting (100 requests per 60 seconds per IP)
    - Email verification requirement
    - 2FA support (TOTP, backup codes)
    - Comprehensive audit logging
    - IP-based trusted device tracking
    
    **Response:**
    Returns JWT token with user information and session details.
    """,
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "token_type": "bearer",
                        "client_side_encryption": False,
                        "issued_at": 1640993400,
                        "expires_at": 1640995200,
                        "is_verified": True,
                        "role": "user",
                        "username": "john_doe",
                        "email": "john.doe@example.com",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request format or credentials",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "invalid_request",
                        "message": "Invalid login request format",
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        401: {
            "description": "Invalid credentials",
            "model": StandardErrorResponse,
            "content": {
                "application/json": {
                    "example": {
                        "error": "authentication_failed",
                        "message": "Invalid username or password",
                        "timestamp": "2024-01-01T12:00:00Z",
                    }
                }
            },
        },
        403: {
            "description": "Email not verified",
            "content": {
                "application/json": {
                    "example": {"detail": "Email not verified", "email": "john.doe@example.com", "username": "john_doe"}
                }
            },
        },
        422: {
            "description": "2FA authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "2FA authentication required",
                        "two_fa_required": True,
                        "available_methods": ["totp", "backup"],
                        "username": "john_doe",
                        "email": "john.doe@example.com",
                    }
                }
            },
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
        500: {"description": "Internal server error", "model": StandardErrorResponse},
    },
    tags=["Authentication"],
)
async def login(request: Request, login_request: Optional[LoginRequest] = Body(None)) -> JSONResponse:
    """
    Authenticate user credentials and return JWT token.

    Supports multiple authentication flows including standard login and 2FA.
    Compatible with both JSON requests and OAuth2 form data.
    """
    await security_manager.check_rate_limit(request, "login")
    
    # Log request details for debugging (especially for mobile apps)
    user_agent = request.headers.get("user-agent", "")
    content_type = request.headers.get("content-type", "")
    is_mobile_app = any(app in user_agent.lower() for app in ["emotion_tracker", "dart", "flutter"])
    
    if is_mobile_app:
        logger.info(
            "POST /auth/login from mobile app - User-Agent: %s, Content-Type: %s, Method: %s, URL: %s",
            user_agent[:100], content_type, request.method, str(request.url)
        )
    
    # Default values
    username = email = password = two_fa_code = two_fa_method = None
    client_side_encryption = False
    # Prefer JSON body if present
    if "application/json" in content_type and login_request:
        # Use Pydantic validation
        username = login_request.username
        email = login_request.email
        password = login_request.password
        two_fa_code = login_request.two_fa_code
        two_fa_method = login_request.two_fa_method
        client_side_encryption = login_request.client_side_encryption
    elif "application/x-www-form-urlencoded" in content_type:
        # Manually parse form data
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
        # Optionally, allow email in username field if you want
        if "@" in username:
            email = username
            username = None
        # Validate using LoginRequest model
        try:
            login_request_obj = LoginRequest(
                username=username, email=email, password=password, client_side_encryption=False
            )
            username = login_request_obj.username
            email = login_request_obj.email
            password = login_request_obj.password
            two_fa_code = login_request_obj.two_fa_code
            two_fa_method = login_request_obj.two_fa_method
            client_side_encryption = login_request_obj.client_side_encryption
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid login form data: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="Unsupported login format")
    login_log = LoginLog(
        timestamp=datetime.utcnow().replace(microsecond=0),
        ip_address=security_manager.get_client_ip(request) if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        username=username or "",
        email=email,
        outcome="pending",
        reason=None,
        mfa_status=None,
    )
    # Set request_ip contextvar for trusted IP lockdown enforcement
    request_ip = security_manager.get_client_ip(request) if request else None
    token_ctx = None
    if request_ip:
        token_ctx = login_service.request_ip_ctx.set(request_ip)
    try:
        user = await login_user(
            username=username,
            email=email,
            password=password,
            two_fa_code=two_fa_code,
            two_fa_method=two_fa_method,
            client_side_encryption=client_side_encryption,
        )
    finally:
        if request_ip and token_ctx is not None:
            login_service.request_ip_ctx.reset(token_ctx)
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
        return JSONResponse(
            {
                "access_token": token,
                "token_type": "bearer",
                "client_side_encryption": user.get("client_side_encryption", False),
                "issued_at": issued_at,
                "expires_at": expires_at,
                "is_verified": user.get("is_verified", False),
                "role": user.get("role", None),
                "username": user.get("username", None),
                "email": user.get("email", None),
            }
        )
    except HTTPException as e:
        # Special handling for '2FA authentication required' error
        if str(e.detail) == "2FA authentication required":
            user_doc = None
            if username:
                user_doc = await db_manager.get_collection("users").find_one({"username": username})
            elif email:
                user_doc = await db_manager.get_collection("users").find_one({"email": email})
            two_fa_methods = user_doc.get("two_fa_methods", []) if user_doc else []
            logger.info("2FA required for user: %s", username or email)
            return JSONResponse(
                status_code=422,
                content={
                    "detail": "2FA authentication required",
                    "two_fa_required": True,
                    "available_methods": two_fa_methods + ["backup"],
                    "username": user_doc.get("username") if user_doc else username,
                    "email": user_doc.get("email") if user_doc else email,
                },
            )
        elif str(e.detail) == "Email not verified":
            email_resp = email
            username_resp = username
            user_doc = None
            if not email_resp or not username_resp:
                if username:
                    user_doc = await db_manager.get_collection("users").find_one({"username": username})
                elif email:
                    user_doc = await db_manager.get_collection("users").find_one({"email": email})
                if user_doc:
                    if not email_resp:
                        email_resp = user_doc.get("email")
                    if not username_resp:
                        username_resp = user_doc.get("username")
            logger.info("Login failed: email not verified for user: %s", username_resp)
            return JSONResponse(
                status_code=403,
                content={"detail": "Email not verified", "email": email_resp, "username": username_resp},
            )
        login_log.outcome = f"failure:{str(e.detail).replace(' ', '_').lower()}"
        login_log.reason = str(e.detail)
        user_doc = None
        if username:
            user_doc = await db_manager.get_collection("users").find_one({"username": username})
        elif email:
            user_doc = await db_manager.get_collection("users").find_one({"email": email})
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
@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh JWT access token",
    description="""
    Refresh an expired or soon-to-expire JWT access token.
    
    **Usage:**
    - Use this endpoint when your JWT token is about to expire
    - Requires a valid (non-expired) JWT token in Authorization header
    - Returns a new JWT token with extended expiration time
    
    **Security:**
    - Rate limited to prevent abuse
    - Requires valid authentication
    - Old token remains valid until natural expiration
    
    **Best Practice:**
    Implement automatic token refresh in your client applications
    to maintain seamless user experience.
    """,
    responses={
        200: {
            "description": "Token refreshed successfully",
            "content": {
                "application/json": {
                    "example": {"access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...", "token_type": "bearer"}
                }
            },
        },
        401: {"description": "Invalid or expired token", "model": StandardErrorResponse},
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
        500: {"description": "Token refresh failed", "model": StandardErrorResponse},
    },
    tags=["Authentication"],
)
@log_performance("token_refresh")
async def refresh_token(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Refresh JWT access token for authenticated user.

    Generates a new JWT token with extended expiration time while
    maintaining the same user session and permissions.
    """
    # Extract request info and set context
    request_info = extract_request_info(request)
    set_auth_logging_context(user_id=current_user["username"], ip_address=request_info["ip_address"])

    await security_manager.check_rate_limit(request, "refresh-token")

    try:
        access_token = await create_access_token({"sub": current_user["username"]})

        # Log successful token refresh
        auth_logger.log_token_operation(
            user_id=current_user["username"],
            operation="refresh",
            token_type="access",
            ip_address=request_info["ip_address"],
            success=True,
        )

        logger.info("Token refreshed for user: %s", current_user["username"])
        return Token(access_token=access_token, token_type="bearer")
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        # Log failed token refresh
        auth_logger.log_token_operation(
            user_id=current_user["username"],
            operation="refresh",
            token_type="access",
            ip_address=request_info["ip_address"],
            success=False,
            reason=str(e),
        )

        logger.error("Token refresh failed for user %s: %s", current_user["username"], e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Token refresh failed") from e


# Rate limit: logout: 100 requests per 60 seconds per IP (default)
@router.post("/logout")
@log_performance("user_logout")
async def logout(
    request: Request, current_user: dict = Depends(enforce_all_lockdowns), token: str = Depends(oauth2_scheme)
):
    """Logout user (invalidate token on server side)."""
    # Extract request info and set context
    request_info = extract_request_info(request)
    set_auth_logging_context(user_id=current_user["username"], ip_address=request_info["ip_address"])

    await security_manager.check_rate_limit(request, "logout")

    try:
        await blacklist_token(token)

        # Log successful logout
        auth_logger.log_logout_attempt(
            user_id=current_user["username"], ip_address=request_info["ip_address"], success=True
        )

        logger.info("User logged out: %s", current_user["username"])
        return {"message": "Successfully logged out"}
    except Exception as e:
        # Log failed logout
        auth_logger.log_logout_attempt(
            user_id=current_user["username"], ip_address=request_info["ip_address"], success=False, reason=str(e)
        )
        logger.error("Logout failed for user %s: %s", current_user["username"], e)
        raise HTTPException(status_code=500, detail="Logout failed")


# Rate limit: change-password: 100 requests per 60 seconds per IP (default)
@router.put("/change-password")
async def change_password(
    password_request: PasswordChangeRequest, current_user: dict = Depends(enforce_all_lockdowns), request: Request = None
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
async def forgot_password(request: Request, payload: Optional[Dict[str, Any]] = Body(default=None)) -> Dict[str, Any]:
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
            raise HTTPException(
                status_code=429,
                detail="Please wait at least 60 seconds before requesting another password reset email.",
            )
        await redis_conn.set(resend_key, now_ts, ex=RESET_EMAIL_EXPIRY)
        await log_password_reset_request(email, ip, user_agent, request_time)
        user = await db_manager.get_collection("users").find_one({"email": email})
        if user and user.get("abuse_suspended", False):
            logger.warning("Account suspended for abuse: %s", email)
            raise HTTPException(
                status_code=403, detail="Account suspended due to repeated password reset abuse. Contact support."
            )
        if await is_pair_blocked(email, ip):
            logger.warning("Password reset blocked for %s from IP %s", email, ip)
            raise HTTPException(
                status_code=403,
                detail="Password reset requests from this device are temporarily blocked due to abuse. Try again later.",
            )
        abuse_result = await detect_password_reset_abuse(email, ip)
        if abuse_result["suspicious"]:
            abuse_msgs = []
            targeted_abuse = False
            for reason in abuse_result["reasons"]:
                if "High volume" in reason:
                    abuse_msgs.append(
                        "Too many password reset requests have been made for this account in a short period. This is a security measure to protect your account."
                    )
                elif "Many unique IPs" in reason:
                    abuse_msgs.append(
                        "Password reset requests for your account are coming from multiple locations. This could indicate that someone else is trying to reset your password (targeted abuse). If this wasn't you, please secure your account and contact support."
                    )
                    targeted_abuse = True
                elif "Pair blocked" in reason:
                    abuse_msgs.append(
                        "Password reset requests from your device are temporarily blocked due to previous abuse. Please try again later or contact support if this is a mistake."
                    )
                elif "Pair whitelisted" in reason:
                    abuse_msgs.append(
                        "Your device is whitelisted for password resets. If you are having trouble, please contact support."
                    )
                elif "VPN/proxy" in reason or "abuse/relay" in reason:
                    abuse_msgs.append(
                        "Password reset requests from VPNs, proxies, or relays may be restricted for security reasons."
                    )
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
                    "abuse_reasons": abuse_result["reasons"],
                },
            )

        location: Optional[str] = None
        isp: Optional[str] = None
        try:
            async with httpx.AsyncClient() as client:
                geo = await client.get(f"https://ipinfo.io/{ip}/json")
                geo_data = geo.json()
                location = f"{geo_data.get('city', '')}, {geo_data.get('country', '')}".strip(", ")
                isp = geo_data.get("org")
        except httpx.HTTPError as geo_exc:
            logger.warning("GeoIP lookup failed for IP %s: %s", ip, geo_exc, exc_info=True)
            location = None
            isp = None
        await send_password_reset_email(
            email, ip=ip, user_agent=user_agent, request_time=request_time, location=location, isp=isp
        )
        logger.info("Password reset email sent to %s", email)
        return {
            "message": "Password reset email sent",
            "suspicious": abuse_result["suspicious"],
            "abuse_reasons": abuse_result["reasons"],
        }
    except HTTPException as e:
        logger.warning("Forgot password HTTP error for email %s: %s", email, e.detail, exc_info=True)
        raise
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        logger.error("Forgot password failed for email %s: %s", email, str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initiate password reset"
        ) from e


# --- Admin endpoints for password reset abuse management have been moved ---
# See: second_brain_database.routes.admin.routes
# All admin logic for whitelist/blocklist and abuse event review is now in the admin module.


# Rate limit: resend-verification-email: 1 request per 600 seconds per IP
@router.post("/resend-verification-email")
async def resend_verification_email(request: Request):
    """Resend verification email to a user if not already verified. Accepts email or username in JSON body. Heavily rate-limited to prevent abuse."""
    await security_manager.check_rate_limit(
        request, "resend-verification-email", rate_limit_requests=50, rate_limit_period=600
    )
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
            raise HTTPException(
                status_code=403,
                detail="Requests from this device are temporarily blocked due to abuse. Try again later.",
            )
        abuse_result = await detect_password_reset_abuse(abuse_id, ip)
        if abuse_result["suspicious"]:
            abuse_msgs = []
            for reason in abuse_result["reasons"]:
                if "High volume" in reason:
                    abuse_msgs.append(
                        "Too many requests have been made for this account in a short period. This is a security measure to protect your account."
                    )
                elif "Many unique IPs" in reason:
                    abuse_msgs.append(
                        "Requests for your account are coming from multiple locations. This could indicate that someone else is trying to abuse this endpoint. If this wasn't you, please secure your account and contact support."
                    )
                elif "Pair blocked" in reason:
                    abuse_msgs.append(
                        "Requests from your device are temporarily blocked due to previous abuse. Please try again later or contact support if this is a mistake."
                    )
                elif "Pair whitelisted" in reason:
                    abuse_msgs.append(
                        "Your device is whitelisted for this endpoint. If you are having trouble, please contact support."
                    )
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
                    "abuse_reasons": abuse_result["reasons"],
                },
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
async def setup_two_fa(req: Request, request: TwoFASetupRequest, current_user: dict = Depends(enforce_all_lockdowns)):
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
async def verify_two_fa(req: Request, request: TwoFAVerifyRequest, current_user: dict = Depends(enforce_all_lockdowns)):
    """Verify a 2FA code for the current user."""
    await security_manager.check_rate_limit(req, "2fa-verify")
    return await verify_2fa(current_user, request)


# Rate limit: 2fa-status: 100 requests per 60 seconds per IP (default)
@router.get("/2fa/status", response_model=TwoFAStatus)
async def get_two_fa_status(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """Get 2FA status for the current user."""
    await security_manager.check_rate_limit(request, "2fa-status")
    return await get_2fa_status(current_user)


# Rate limit: 2fa-disable: 100 requests per 60 seconds per IP (default)
@router.post("/2fa/disable", response_model=TwoFAStatus)
async def disable_two_fa(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """Disable all 2FA for the current user."""
    await security_manager.check_rate_limit(request, "2fa-disable")
    # Recent password confirmation or re-login should be required for sensitive actions in production
    return await disable_2fa(current_user)


# Rate limit: is-verified: 100 requests per 60 seconds per IP (default)
@router.get("/is-verified")
async def is_verified(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
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
                "email": user.get("email", None),
            }
        else:
            return {"token": "invalid", "reason": "User is not verified"}
    except HTTPException as e:
        return {"token": "invalid", "reason": str(e.detail) if hasattr(e, "detail") else str(e)}
    except (ValueError, KeyError, TypeError, RuntimeError) as e:
        return {"token": "invalid", "reason": str(e)}


# Rate limit: 2fa-guide: 100 requests per 60 seconds per IP (default)
@router.get("/2fa/guide")
async def get_2fa_setup_guide(current_user: dict = Depends(enforce_all_lockdowns), request: Request = None):
    """Get basic 2FA setup information."""
    await security_manager.check_rate_limit(request, "2fa-guide")

    return {
        "enabled": current_user.get("two_fa_enabled", False),
        "methods": current_user.get("two_fa_methods", []),
        "apps": ["Google Authenticator", "Microsoft Authenticator", "Authy", "1Password", "Bitwarden"],
    }


# Rate limit: security-dashboard: 100 requests per 60 seconds per IP (default)
@router.get("/security-dashboard")
async def get_security_dashboard(current_user: dict = Depends(enforce_all_lockdowns), request: Request = None):
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
        "account_active": current_user.get("is_active", True),
    }


# Rate limit: 2fa-backup-codes: 5 requests per 300 seconds per IP (restricted)
@router.get("/2fa/backup-codes")
async def get_backup_codes_status(current_user: dict = Depends(enforce_all_lockdowns), request: Request = None):
    """Get backup codes status (count remaining, not the actual codes for security)."""
    await security_manager.check_rate_limit(request, "2fa-backup-codes", rate_limit_requests=5, rate_limit_period=300)

    if not current_user.get("two_fa_enabled", False):
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    backup_codes = current_user.get("backup_codes", [])
    backup_codes_used = current_user.get("backup_codes_used", [])

    total_codes = len(backup_codes)
    used_codes = len(backup_codes_used)
    remaining_codes = total_codes - used_codes

    return {"total_codes": total_codes, "used_codes": used_codes, "remaining_codes": remaining_codes}


# Rate limit: 2fa-regenerate-backup: 20 requests per 3600 (1hr) seconds per IP (increased for testing)
@router.post("/2fa/regenerate-backup-codes")
async def regenerate_backup_codes(current_user: dict = Depends(enforce_all_lockdowns), request: Request = None):
    """Regenerate backup codes for 2FA recovery. This invalidates all existing backup codes."""
    # Increased rate limit for testing purposes doing it 200 times per hour
    await security_manager.check_rate_limit(
        request, "2fa-regenerate-backup", rate_limit_requests=200, rate_limit_period=3600
    )

    if not current_user.get("two_fa_enabled", False):
        raise HTTPException(status_code=400, detail="2FA is not enabled")

    # Generate new backup codes
    backup_codes = [secrets.token_hex(BACKUP_CODE_LENGTH).upper() for _ in range(MAX_BACKUP_CODES)]
    hashed_backup_codes = [
        bcrypt.hashpw(code.encode("utf-8"), bcrypt.gensalt()).decode("utf-8") for code in backup_codes
    ]

    # Update user with new backup codes
    await db_manager.get_collection("users").update_one(
        {"username": current_user["username"]},
        {"$set": {"backup_codes": hashed_backup_codes, "backup_codes_used": []}},  # Reset used codes
    )

    logger.info("Backup codes regenerated for user %s", current_user["username"])

    return {"message": "New backup codes generated successfully", "backup_codes": backup_codes}


# Rate limit: 2fa-reset: 5 requests per 3600 seconds per IP (very restricted)
@router.post("/2fa/reset", response_model=TwoFASetupResponse)
async def reset_two_fa(
    request: TwoFASetupRequest, current_user: dict = Depends(enforce_all_lockdowns), req: Request = None
):
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
    user = await db_manager.get_collection("users").find_one(
        {"password_reset_token": hashlib.sha256(token.encode()).hexdigest()}
    )
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired token.")
    expiry = user.get("password_reset_token_expiry")
    if not expiry or datetime.utcnow() > datetime.fromisoformat(expiry):
        raise HTTPException(status_code=400, detail="Token has expired.")
    # Validate password strength
    if not validate_password_strength(new_password):
        raise HTTPException(status_code=400, detail="Password does not meet strength requirements.")
    # Hash and update password
    hashed_pw = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    # Increment token_version for stateless JWT invalidation
    new_token_version = (user.get("token_version") or 0) + 1
    await db_manager.get_collection("users").update_one(
        {"_id": user["_id"]},
        {
            "$set": {"hashed_password": hashed_pw, "token_version": new_token_version},
            "$unset": {"password_reset_token": "", "password_reset_token_expiry": ""},
        },
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
    return HTMLResponse(
        f"<h2>Device whitelisted!</h2><p>Password reset requests from this device (IP: {ip}) are now allowed for {email} (for 30 minutes).</p>"
    )


@router.get("/block-reset-abuse", response_class=HTMLResponse)
async def block_reset_abuse(token: str):
    """
    Endpoint for user to block a suspicious password reset attempt via secure email link.
    """
    email, ip = await consume_abuse_action_token(token, expected_action="block")
    if not email or not ip:
        return HTMLResponse("<h2>Invalid or expired block link.</h2>", status_code=400)
    await block_reset_pair(email, ip)
    return HTMLResponse(
        f"<h2>Device blocked!</h2><p>Password reset requests from this device (IP: {ip}) are now blocked for {email} (for 24 hours).</p>"
    )


# --- Dual Authentication Management ---
@router.get("/auth-methods", response_model=AuthMethodsResponse)
async def get_user_auth_methods(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Get available authentication methods for the current user.
    
    Returns information about what authentication methods are available,
    user preferences, and usage statistics.
    
    **Response includes:**
    - Available authentication methods (password, webauthn)
    - User's preferred authentication method
    - WebAuthn credential count
    - Recent authentication method usage
    """
    from second_brain_database.routes.auth.services.auth.login import get_user_auth_methods
    
    user_id = str(current_user["_id"])
    auth_methods = await get_user_auth_methods(user_id)
    
    logger.info("Retrieved auth methods for user %s: %s", current_user["username"], auth_methods)
    
    return {
        "available_methods": auth_methods["available_methods"],
        "preferred_method": auth_methods["preferred_method"],
        "has_password": auth_methods["has_password"],
        "has_webauthn": auth_methods["has_webauthn"],
        "webauthn_credential_count": auth_methods["webauthn_credential_count"],
        "recent_auth_methods": auth_methods["recent_auth_methods"],
        "last_auth_method": auth_methods["last_auth_method"],
    }


@router.put("/auth-methods/preference", response_model=AuthPreferenceResponse)
async def set_auth_preference(
    request: Request, 
    preferred_method: str = Body(..., embed=True),
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Set the user's preferred authentication method.
    
    The preferred method will be suggested first during login flows.
    The method must be available for the user (e.g., they must have WebAuthn credentials
    to set webauthn as preferred).
    
    **Supported methods:**
    - password: Traditional password authentication
    - webauthn: WebAuthn/FIDO2 passwordless authentication
    """
    from second_brain_database.routes.auth.services.auth.login import set_user_auth_preference
    
    user_id = str(current_user["_id"])
    
    # Validate method
    if preferred_method not in ["password", "webauthn"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid authentication method. Must be 'password' or 'webauthn'"
        )
    
    success = await set_user_auth_preference(user_id, preferred_method)
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot set preferred method. Method may not be available for your account."
        )
    
    logger.info("Updated auth preference for user %s: %s", current_user["username"], preferred_method)
    
    return {
        "message": "Authentication preference updated successfully",
        "preferred_method": preferred_method
    }


@router.get("/auth-methods/fallback/{failed_method}", response_model=AuthFallbackResponse)
async def check_auth_fallback(
    request: Request,
    failed_method: str,
    current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Check available authentication fallback options when one method fails.
    
    This endpoint helps determine what alternative authentication methods
    are available if the primary method fails or is unavailable.
    
    **Parameters:**
    - failed_method: The authentication method that failed ("password" or "webauthn")
    
    **Response includes:**
    - Whether fallback options are available
    - List of available fallback methods
    - Recommended fallback method
    """
    from second_brain_database.routes.auth.services.auth.login import check_auth_fallback_available
    
    user_id = str(current_user["_id"])
    
    # Validate failed method
    if failed_method not in ["password", "webauthn"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid authentication method. Must be 'password' or 'webauthn'"
        )
    
    fallback_info = await check_auth_fallback_available(user_id, failed_method)
    
    logger.info("Checked auth fallback for user %s, failed method %s: %s", 
               current_user["username"], failed_method, fallback_info)
    
    return fallback_info


# --- Trusted IP Lockdown: 2FA-like Enable/Disable Flow (IP-bound confirmation) ---
@router.post("/trusted-ips/lockdown-request")
async def trusted_ips_lockdown_request(
    request: Request,
    action: str = Body(..., embed=True),  # 'enable' or 'disable'
    trusted_ips: List[str] = Body(
        default=None, embed=True
    ),  # List of IPs to allow confirmation from (optional for disable)
    current_user: dict = Depends(enforce_all_lockdowns),
):
    logger.info(
        "[trusted_ips_lockdown_request] user=%s action=%s trusted_ips=%s request_ip=%s headers=%s",
        current_user.get("username"),
        action,
        trusted_ips,
        request.client.host,
        dict(request.headers),
    )
    await security_manager.check_rate_limit(
        request, "trusted-ips-lockdown-request", rate_limit_requests=5, rate_limit_period=3600
    )
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
            logger.info(
                "No trusted_ips set for user %s; cannot disable lockdown without any trusted IPs",
                current_user.get("username"),
            )
            raise HTTPException(
                status_code=400, detail="No trusted IPs set. Cannot disable lockdown without any trusted IPs."
            )
    elif not trusted_ips or not isinstance(trusted_ips, list):
        logger.info("No trusted_ips provided for lockdown by user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="trusted_ips must be a non-empty list.")
    code = secrets.token_urlsafe(8)
    expiry = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    await db_manager.get_collection("users").update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "lockdown_code": code,
                "lockdown_code_expiry": expiry,
                "lockdown_code_action": action,
                "lockdown_code_ips": trusted_ips,
            }
        },
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
        logger.info(
            "Lockdown disable email sent to user %s (allowed IPs: %s)", current_user.get("username"), trusted_ips
        )
    try:
        await send_trusted_ip_lockdown_code_email(email, code, action, trusted_ips)
        logger.info(
            "Lockdown %s code sent to user %s (allowed IPs: %s)", action, current_user.get("username"), trusted_ips
        )
    except Exception as e:
        logger.error("Failed to send lockdown code to %s: %s", email, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send confirmation code.") from e
    logger.info("Lockdown request completed for user %s (action: %s)", current_user.get("username"), action)
    return {"message": f"Confirmation code sent to {email}. Must confirm from one of the provided IPs."}


@router.post("/trusted-ips/lockdown-confirm")
async def trusted_ips_lockdown_confirm(
    request: Request, code: str = Body(..., embed=True), current_user: dict = Depends(enforce_all_lockdowns)
):
    user = await db_manager.get_collection("users").find_one({"_id": current_user["_id"]})
    logger.info(
        "[trusted_ips_lockdown_confirm] user=%s code=%s request_ip=%s allowed_ips=%s headers=%s",
        current_user.get("username"),
        code,
        request.client.host,
        user.get("lockdown_code_ips", []),
        dict(request.headers),
    )
    await security_manager.check_rate_limit(
        request, "trusted-ips-lockdown-confirm", rate_limit_requests=10, rate_limit_period=3600
    )
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
            logger.info(
                "Lockdown disable confirm from non-trusted IP %s for user %s (trusted_ips: %s)",
                request_ip,
                current_user.get("username"),
                db_trusted_ips,
            )
            raise HTTPException(
                status_code=403, detail="Disabling lockdown must be confirmed from one of your existing trusted IPs."
            )
    else:
        if request_ip not in allowed_ips:
            logger.info(
                "Lockdown confirm from disallowed IP %s for user %s (allowed: %s)",
                request_ip,
                current_user.get("username"),
                allowed_ips,
            )
            raise HTTPException(status_code=403, detail="Confirmation must be from one of the allowed IPs.")
    lockdown_flag = True if action == "enable" else False
    update_fields = {"trusted_ip_lockdown": lockdown_flag}
    if action == "enable":
        update_fields["trusted_ips"] = allowed_ips
    await db_manager.get_collection("users").update_one(
        {"_id": current_user["_id"]},
        {
            "$set": update_fields,
            "$unset": {
                "lockdown_code": "",
                "lockdown_code_expiry": "",
                "lockdown_code_action": "",
                "lockdown_code_ips": "",
            },
        },
    )
    
    # Log lockdown configuration change security event
    log_security_event(
        event_type="lockdown_config_change",
        user_id=current_user.get("username"),
        ip_address=request_ip,
        success=True,
        details={
            "lockdown_type": "ip",
            "action": action,
            "previous_status": user.get("trusted_ip_lockdown", False),
            "new_status": lockdown_flag,
            "trusted_ips_count": len(allowed_ips) if action == "enable" else 0,
            "confirmed_from_ip": request_ip,
            "endpoint": f"{request.method} {request.url.path}",
            "user_agent": request.headers.get("user-agent", ""),
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    logger.info(
        "Trusted IP lockdown %s for user %s (confirmed from IP %s, trusted_ips updated if enabled)",
        action,
        current_user.get("username"),
        request_ip,
    )
    return {
        "message": f"Trusted IP lockdown {action}d successfully.{ ' Trusted IPs updated.' if action == 'enable' else ''}"
    }


@router.get("/trusted-ips/lockdown-status")
async def trusted_ips_lockdown_status(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    logger.info("[trusted_ips_lockdown_status] user=%s", current_user.get("username"))
    lockdown_status = bool(current_user.get("trusted_ip_lockdown", False))
    return {"trusted_ip_lockdown": lockdown_status, "your_ip": request.client.host}


# --- Trusted User Agent Lockdown: 2FA-like Enable/Disable Flow (User Agent-bound confirmation) ---
@router.post("/trusted-user-agents/lockdown-request")
async def trusted_user_agents_lockdown_request(
    request: Request,
    action: str = Body(..., embed=True),  # 'enable' or 'disable'
    trusted_user_agents: List[str] = Body(
        default=None, embed=True
    ),  # List of User Agents to allow confirmation from (optional for disable)
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Request to enable or disable User Agent lockdown with email confirmation.
    
    For 'enable': requires a list of trusted User Agents.
    For 'disable': uses existing trusted User Agents from database.
    
    Generates a confirmation code and sends it via email.
    """
    logger.info(
        "[trusted_user_agents_lockdown_request] user=%s action=%s trusted_user_agents=%s request_user_agent=%s",
        current_user.get("username"),
        action,
        trusted_user_agents,
        security_manager.get_client_user_agent(request),
    )
    await security_manager.check_rate_limit(
        request, "trusted-user-agents-lockdown-request", rate_limit_requests=5, rate_limit_period=3600
    )
    
    # Validate action parameter
    if action not in ("enable", "disable"):
        logger.info("Invalid User Agent lockdown action requested: %s by user %s", action, current_user.get("username"))
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'enable' or 'disable'.")
    
    if action == "disable":
        # First, check if trusted_user_agent_lockdown is enabled before proceeding
        user_doc = await db_manager.get_collection("users").find_one({"_id": current_user["_id"]})
        if not user_doc.get("trusted_user_agent_lockdown", False):
            logger.info("Trusted User Agent Lockdown is not enabled for user %s; cannot disable", current_user.get("username"))
            raise HTTPException(status_code=400, detail="Trusted User Agent Lockdown is not enabled.")
        
        # For disabling, ignore user-provided trusted_user_agents and use the current trusted_user_agents from the DB
        trusted_user_agents = user_doc.get("trusted_user_agents", [])
        if not trusted_user_agents:
            logger.info(
                "No trusted_user_agents set for user %s; cannot disable lockdown without any trusted User Agents",
                current_user.get("username"),
            )
            raise HTTPException(
                status_code=400, detail="No trusted User Agents set. Cannot disable lockdown without any trusted User Agents."
            )
    elif not trusted_user_agents or not isinstance(trusted_user_agents, list):
        logger.info("No trusted_user_agents provided for lockdown by user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="trusted_user_agents must be a non-empty list.")
    
    # Generate confirmation code
    code = secrets.token_urlsafe(8)
    expiry = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
    
    # Store confirmation code in user document
    await db_manager.get_collection("users").update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "trusted_user_agent_lockdown_codes": [{
                    "code": code,
                    "expires_at": expiry,
                    "action": action,
                    "allowed_user_agents": trusted_user_agents,
                }]
            }
        },
    )
    
    email = current_user.get("email")
    
    if action == "disable":
        # Notify user of the User Agents that will be allowed to disable lockdown (before confirmation)
        from second_brain_database.managers.email import email_manager

        subject = "[Security Notice] Trusted User Agent Lockdown Disable Requested"
        html_content = f"""
        <html><body>
        <h2>Trusted User Agent Lockdown Disable Requested</h2>
        <p>A request was made to disable Trusted User Agent Lockdown on your account.</p>
        <p><b>The following User Agents will be allowed to confirm this action:</b></p>
        <ul>{''.join(f'<li>{ua}</li>' for ua in trusted_user_agents)}</ul>
        <p>If you did not request this, your account may be at risk. Please review your account security and contact support immediately.</p>
        </body></html>
        """
        await email_manager._send_via_console(current_user["email"], subject, html_content)
        logger.info(
            "User Agent lockdown disable email sent to user %s (allowed User Agents: %s)", 
            current_user.get("username"), 
            trusted_user_agents
        )
    
    try:
        await send_user_agent_lockdown_code_email(email, code, action, trusted_user_agents)
        logger.info(
            "User Agent lockdown %s code sent to user %s (allowed User Agents: %s)", 
            action, 
            current_user.get("username"), 
            trusted_user_agents
        )
    except Exception as e:
        logger.error("Failed to send User Agent lockdown code to %s: %s", email, str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send confirmation code.") from e
    
    logger.info("User Agent lockdown request completed for user %s (action: %s)", current_user.get("username"), action)
    return {"message": f"Confirmation code sent to {email}. Must confirm from one of the provided User Agents."}


@router.post("/trusted-user-agents/lockdown-confirm")
async def trusted_user_agents_lockdown_confirm(
    request: Request, code: str = Body(..., embed=True), current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Confirm User Agent lockdown enable/disable action using the confirmation code.
    
    Validates the confirmation code and User Agent, then updates the user's lockdown settings.
    """
    user = await db_manager.get_collection("users").find_one({"_id": current_user["_id"]})
    request_user_agent = security_manager.get_client_user_agent(request)
    
    logger.info(
        "[trusted_user_agents_lockdown_confirm] user=%s code=%s request_user_agent=%s",
        current_user.get("username"),
        code,
        request_user_agent,
    )
    
    await security_manager.check_rate_limit(
        request, "trusted-user-agents-lockdown-confirm", rate_limit_requests=10, rate_limit_period=3600
    )
    
    # Get the stored confirmation codes
    lockdown_codes = user.get("trusted_user_agent_lockdown_codes", [])
    if not lockdown_codes:
        logger.info("No User Agent lockdown codes found for user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="No pending User Agent lockdown action.")
    
    # Find the matching code
    matching_code = None
    for stored_code_data in lockdown_codes:
        if stored_code_data.get("code") == code:
            matching_code = stored_code_data
            break
    
    if not matching_code:
        logger.info("Invalid User Agent lockdown code for user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="Invalid code.")
    
    # Check if code has expired
    expiry = matching_code.get("expires_at")
    if not expiry or datetime.utcnow() > datetime.fromisoformat(expiry):
        logger.info("Expired User Agent lockdown code for user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="Code expired.")
    
    action = matching_code.get("action")
    allowed_user_agents = matching_code.get("allowed_user_agents", [])
    
    if not action or not allowed_user_agents:
        logger.info("Invalid User Agent lockdown code data for user %s", current_user.get("username"))
        raise HTTPException(status_code=400, detail="Invalid code data.")
    
    # Validate that the request is coming from an allowed User Agent
    if action == "disable":
        # For disable, check against current trusted User Agents in database
        db_trusted_user_agents = user.get("trusted_user_agents", [])
        if request_user_agent not in db_trusted_user_agents:
            logger.info(
                "User Agent lockdown disable confirm from non-trusted User Agent %s for user %s (trusted_user_agents: %s)",
                request_user_agent,
                current_user.get("username"),
                db_trusted_user_agents,
            )
            raise HTTPException(
                status_code=403, 
                detail="Disabling lockdown must be confirmed from one of your existing trusted User Agents."
            )
    else:  # action == "enable"
        # For enable, check against the allowed User Agents from the confirmation code
        if request_user_agent not in allowed_user_agents:
            logger.info(
                "User Agent lockdown confirm from disallowed User Agent %s for user %s (allowed: %s)",
                request_user_agent,
                current_user.get("username"),
                allowed_user_agents,
            )
            raise HTTPException(
                status_code=403, 
                detail="Confirmation must be from one of the allowed User Agents."
            )
    
    # Update user document with lockdown settings
    lockdown_flag = True if action == "enable" else False
    update_fields = {"trusted_user_agent_lockdown": lockdown_flag}
    
    if action == "enable":
        update_fields["trusted_user_agents"] = allowed_user_agents
    
    # Clear the used confirmation codes
    await db_manager.get_collection("users").update_one(
        {"_id": current_user["_id"]},
        {
            "$set": update_fields,
            "$unset": {
                "trusted_user_agent_lockdown_codes": "",
            },
        },
    )
    
    # Log lockdown configuration change security event
    log_security_event(
        event_type="lockdown_config_change",
        user_id=current_user.get("username"),
        ip_address=security_manager.get_client_ip(request),
        success=True,
        details={
            "lockdown_type": "user_agent",
            "action": action,
            "previous_status": user.get("trusted_user_agent_lockdown", False),
            "new_status": lockdown_flag,
            "trusted_user_agents_count": len(allowed_user_agents) if action == "enable" else 0,
            "confirmed_from_user_agent": request_user_agent,
            "endpoint": f"{request.method} {request.url.path}",
            "user_agent": request_user_agent,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    logger.info(
        "Trusted User Agent lockdown %s for user %s (confirmed from User Agent %s, trusted_user_agents updated if enabled)",
        action,
        current_user.get("username"),
        request_user_agent,
    )
    
    return {
        "message": f"Trusted User Agent lockdown {action}d successfully.{' Trusted User Agents updated.' if action == 'enable' else ''}"
    }


@router.get("/trusted-user-agents/lockdown-status")
async def trusted_user_agents_lockdown_status(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Get current User Agent lockdown status and requesting User Agent string.
    
    Returns the current lockdown status and the User Agent string of the requesting client.
    This helps users understand their current lockdown configuration and identify their User Agent.
    """
    logger.info("[trusted_user_agents_lockdown_status] user=%s", current_user.get("username"))
    lockdown_status = bool(current_user.get("trusted_user_agent_lockdown", False))
    request_user_agent = security_manager.get_client_user_agent(request)
    
    return {
        "trusted_user_agent_lockdown": lockdown_status,
        "your_user_agent": request_user_agent
    }


# --- "Allow Once" Temporary Access Endpoints ---

@router.post("/lockdown/allow-once/ip")
async def allow_once_ip_access(
    request: Request,
    token: str = Body(..., embed=True)
):
    """
    Grant temporary IP access using a token from blocked access notification email.
    
    This endpoint allows users to bypass IP lockdown restrictions for 15 minutes
    using a secure token received via email when their access was blocked.
    
    **Process:**
    1. User attempts to access account from untrusted IP
    2. Access is blocked and notification email is sent with "allow once" link
    3. User clicks link or uses token with this endpoint
    4. Temporary bypass is created for 15 minutes
    
    **Security:**
    - Tokens are single-use and expire in 15 minutes
    - Tokens are stored in Redis with automatic expiration
    - All actions are logged for security monitoring
    
    **Requirements:** 1.4, 2.4
    """
    await security_manager.check_rate_limit(
        request, "allow-once-ip", rate_limit_requests=10, rate_limit_period=3600
    )
    
    try:
        from second_brain_database.routes.auth.services.temporary_access import (
            validate_and_use_temporary_ip_token,
            execute_allow_once_ip_access
        )
        
        # Validate and consume the token (single use)
        token_data = await validate_and_use_temporary_ip_token(token)
        if not token_data:
            logger.warning("Invalid or expired allow-once IP token used")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired token. Please request a new access link."
            )
        
        # Verify this is an "allow_once" action
        if token_data.get("action") != "allow_once":
            logger.warning("Token used for wrong action type: %s", token_data.get("action"))
            raise HTTPException(
                status_code=400,
                detail="Invalid token type for this action."
            )
        
        # Execute the allow once action
        success = await execute_allow_once_ip_access(token_data)
        if not success:
            logger.error("Failed to execute allow-once IP access for token: %s", token_data)
            raise HTTPException(
                status_code=500,
                detail="Failed to grant temporary access. Please try again."
            )
        
        logger.info("Granted temporary IP access for user %s, IP %s", 
                   token_data.get("user_email"), token_data.get("ip_address"))
        
        return {
            "message": "Temporary access granted successfully",
            "ip_address": token_data.get("ip_address"),
            "expires_in_minutes": 15,
            "endpoint": token_data.get("endpoint")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in allow-once IP access: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again or contact support."
        )


@router.post("/lockdown/allow-once/user-agent")
async def allow_once_user_agent_access(
    request: Request,
    token: str = Body(..., embed=True)
):
    """
    Grant temporary User Agent access using a token from blocked access notification email.
    
    This endpoint allows users to bypass User Agent lockdown restrictions for 15 minutes
    using a secure token received via email when their access was blocked.
    
    **Process:**
    1. User attempts to access account from untrusted User Agent
    2. Access is blocked and notification email is sent with "allow once" link
    3. User clicks link or uses token with this endpoint
    4. Temporary bypass is created for 15 minutes
    
    **Security:**
    - Tokens are single-use and expire in 15 minutes
    - Tokens are stored in Redis with automatic expiration
    - All actions are logged for security monitoring
    
    **Requirements:** 1.4, 2.4
    """
    await security_manager.check_rate_limit(
        request, "allow-once-user-agent", rate_limit_requests=10, rate_limit_period=3600
    )
    
    try:
        from second_brain_database.routes.auth.services.temporary_access import (
            validate_and_use_temporary_user_agent_token,
            execute_allow_once_user_agent_access
        )
        
        # Validate and consume the token (single use)
        token_data = await validate_and_use_temporary_user_agent_token(token)
        if not token_data:
            logger.warning("Invalid or expired allow-once User Agent token used")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired token. Please request a new access link."
            )
        
        # Verify this is an "allow_once" action
        if token_data.get("action") != "allow_once":
            logger.warning("Token used for wrong action type: %s", token_data.get("action"))
            raise HTTPException(
                status_code=400,
                detail="Invalid token type for this action."
            )
        
        # Execute the allow once action
        success = await execute_allow_once_user_agent_access(token_data)
        if not success:
            logger.error("Failed to execute allow-once User Agent access for token: %s", token_data)
            raise HTTPException(
                status_code=500,
                detail="Failed to grant temporary access. Please try again."
            )
        
        logger.info("Granted temporary User Agent access for user %s, User Agent %s", 
                   token_data.get("user_email"), 
                   token_data.get("user_agent")[:50] + "..." if len(token_data.get("user_agent", "")) > 50 else token_data.get("user_agent"))
        
        return {
            "message": "Temporary access granted successfully",
            "user_agent": token_data.get("user_agent"),
            "expires_in_minutes": 15,
            "endpoint": token_data.get("endpoint")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in allow-once User Agent access: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again or contact support."
        )


# --- "Add to Trusted List" Permanent Access Endpoints ---

@router.post("/lockdown/add-trusted/ip")
async def add_ip_to_trusted_list(
    request: Request,
    token: str = Body(..., embed=True)
):
    """
    Add an IP address to the trusted list using a token from blocked access notification email.
    
    This endpoint allows users to permanently add an IP address to their trusted list
    using a secure token received via email when their access was blocked.
    
    **Process:**
    1. User attempts to access account from untrusted IP
    2. Access is blocked and notification email is sent with "add to trusted list" link
    3. User clicks link or uses token with this endpoint
    4. IP is permanently added to their trusted IP list
    
    **Security:**
    - Tokens are single-use and expire in 1 hour
    - Tokens are stored in Redis with automatic expiration
    - All actions are logged for security monitoring
    - Requires email confirmation for permanent additions
    
    **Requirements:** 1.4, 2.4
    """
    await security_manager.check_rate_limit(
        request, "add-trusted-ip", rate_limit_requests=10, rate_limit_period=3600
    )
    
    try:
        from second_brain_database.routes.auth.services.temporary_access import (
            validate_and_use_temporary_ip_token,
            execute_add_to_trusted_ip_list
        )
        
        # Validate and consume the token (single use)
        token_data = await validate_and_use_temporary_ip_token(token)
        if not token_data:
            logger.warning("Invalid or expired add-to-trusted IP token used")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired token. Please request a new access link."
            )
        
        # Verify this is an "add_to_trusted" action
        if token_data.get("action") != "add_to_trusted":
            logger.warning("Token used for wrong action type: %s", token_data.get("action"))
            raise HTTPException(
                status_code=400,
                detail="Invalid token type for this action."
            )
        
        # Execute the add to trusted list action
        success = await execute_add_to_trusted_ip_list(token_data)
        if not success:
            logger.error("Failed to execute add-to-trusted IP action for token: %s", token_data)
            raise HTTPException(
                status_code=500,
                detail="Failed to add IP to trusted list. Please try again."
            )
        
        logger.info("Added IP to trusted list for user %s, IP %s", 
                   token_data.get("user_email"), token_data.get("ip_address"))
        
        return {
            "message": "IP address added to trusted list successfully",
            "ip_address": token_data.get("ip_address"),
            "endpoint": token_data.get("endpoint")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in add-to-trusted IP action: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again or contact support."
        )


@router.post("/lockdown/add-trusted/user-agent")
async def add_user_agent_to_trusted_list(
    request: Request,
    token: str = Body(..., embed=True)
):
    """
    Add a User Agent to the trusted list using a token from blocked access notification email.
    
    This endpoint allows users to permanently add a User Agent to their trusted list
    using a secure token received via email when their access was blocked.
    
    **Process:**
    1. User attempts to access account from untrusted User Agent
    2. Access is blocked and notification email is sent with "add to trusted list" link
    3. User clicks link or uses token with this endpoint
    4. User Agent is permanently added to their trusted User Agent list
    
    **Security:**
    - Tokens are single-use and expire in 1 hour
    - Tokens are stored in Redis with automatic expiration
    - All actions are logged for security monitoring
    - Requires email confirmation for permanent additions
    
    **Requirements:** 1.4, 2.4
    """
    await security_manager.check_rate_limit(
        request, "add-trusted-user-agent", rate_limit_requests=10, rate_limit_period=3600
    )
    
    try:
        from second_brain_database.routes.auth.services.temporary_access import (
            validate_and_use_temporary_user_agent_token,
            execute_add_to_trusted_user_agent_list
        )
        
        # Validate and consume the token (single use)
        token_data = await validate_and_use_temporary_user_agent_token(token)
        if not token_data:
            logger.warning("Invalid or expired add-to-trusted User Agent token used")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired token. Please request a new access link."
            )
        
        # Verify this is an "add_to_trusted" action
        if token_data.get("action") != "add_to_trusted":
            logger.warning("Token used for wrong action type: %s", token_data.get("action"))
            raise HTTPException(
                status_code=400,
                detail="Invalid token type for this action."
            )
        
        # Execute the add to trusted list action
        success = await execute_add_to_trusted_user_agent_list(token_data)
        if not success:
            logger.error("Failed to execute add-to-trusted User Agent action for token: %s", token_data)
            raise HTTPException(
                status_code=500,
                detail="Failed to add User Agent to trusted list. Please try again."
            )
        
        logger.info("Added User Agent to trusted list for user %s, User Agent %s", 
                   token_data.get("user_email"), 
                   token_data.get("user_agent")[:50] + "..." if len(token_data.get("user_agent", "")) > 50 else token_data.get("user_agent"))
        
        return {
            "message": "User Agent added to trusted list successfully",
            "user_agent": token_data.get("user_agent"),
            "endpoint": token_data.get("endpoint")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in add-to-trusted User Agent action: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred. Please try again or contact support."
        )


@router.get("/recent-logins")
async def get_recent_successful_logins(limit: int = 10, current_user: dict = Depends(enforce_all_lockdowns)):
    """Get the most recent successful login attempts (default 10). Requires authentication. Returns a JSON object."""
    logs_collection = db_manager.get_collection("logs")
    cursor = logs_collection.find({"outcome": "success"}).sort("timestamp", -1).limit(limit)
    results = []
    async for doc in cursor:
        doc.pop("_id", None)
        results.append(LoginLog(**doc).model_dump())
    return {"logins": results}


# --- Permanent API Tokens ---

# Rate limit: permanent-tokens: 10 requests per 60 seconds per IP (restricted)
PERMANENT_TOKEN_CREATE_RATE_LIMIT: int = 10
PERMANENT_TOKEN_CREATE_RATE_PERIOD: int = 60
PERMANENT_TOKEN_LIST_RATE_LIMIT: int = 50
PERMANENT_TOKEN_LIST_RATE_PERIOD: int = 60
PERMANENT_TOKEN_REVOKE_RATE_LIMIT: int = 20
PERMANENT_TOKEN_REVOKE_RATE_PERIOD: int = 60


@router.post("/permanent-tokens", response_model=PermanentTokenResponse)
async def create_permanent_token(
    request: Request, token_request: PermanentTokenRequest, current_user: dict = Depends(enforce_all_lockdowns)
):
    """
    Create a new permanent API token for the authenticated user.

    Permanent tokens:
    - Never expire (until manually revoked)
    - Can be used with any API endpoint that accepts Bearer tokens
    - Are rate-limited to prevent abuse
    - Include optional description for identification

    Returns the actual token (only shown once) and metadata.
    """
    await security_manager.check_rate_limit(
        request,
        "permanent-token-create",
        rate_limit_requests=PERMANENT_TOKEN_CREATE_RATE_LIMIT,
        rate_limit_period=PERMANENT_TOKEN_CREATE_RATE_PERIOD,
    )

    from second_brain_database.routes.auth.services.permanent_tokens import create_permanent_token

    try:
        # Create the permanent token
        token_response = await create_permanent_token(
            user_id=str(current_user["_id"]),
            username=current_user["username"],
            email=current_user["email"],
            role=current_user.get("role", "user"),
            is_verified=current_user.get("is_verified", False),
            description=token_request.description,
        )

        logger.info(
            "Permanent token created for user %s (token_id: %s)", current_user["username"], token_response.token_id
        )

        return token_response

    except Exception as e:
        logger.error("Failed to create permanent token for user %s: %s", current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create permanent token"
        )


@router.get("/permanent-tokens", response_model=PermanentTokenListResponse)
async def list_permanent_tokens(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    List all permanent tokens for the authenticated user.

    Returns token metadata (ID, description, created date, last used, etc.)
    but never returns the actual token values for security.
    """
    await security_manager.check_rate_limit(
        request,
        "permanent-token-list",
        rate_limit_requests=PERMANENT_TOKEN_LIST_RATE_LIMIT,
        rate_limit_period=PERMANENT_TOKEN_LIST_RATE_PERIOD,
    )

    from second_brain_database.routes.auth.services.permanent_tokens import get_user_tokens

    try:
        tokens = await get_user_tokens(str(current_user["_id"]), include_revoked=False)

        return PermanentTokenListResponse(tokens=tokens)

    except Exception as e:
        logger.error("Failed to list permanent tokens for user %s: %s", current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve permanent tokens"
        )


@router.delete("/permanent-tokens/{token_id}", response_model=TokenRevocationResponse)
async def revoke_permanent_token(request: Request, token_id: str, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Revoke a permanent token by its ID.

    Only the token owner can revoke their own tokens.
    Revoked tokens are immediately invalidated and cannot be used.
    """
    await security_manager.check_rate_limit(
        request,
        "permanent-token-revoke",
        rate_limit_requests=PERMANENT_TOKEN_REVOKE_RATE_LIMIT,
        rate_limit_period=PERMANENT_TOKEN_REVOKE_RATE_PERIOD,
    )

    from second_brain_database.routes.auth.services.permanent_tokens import revoke_token_by_id

    try:
        revocation_response = await revoke_token_by_id(user_id=str(current_user["_id"]), token_id=token_id)

        if revocation_response is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found or already revoked")

        logger.info("Permanent token revoked: token_id=%s, user=%s", token_id, current_user["username"])

        return revocation_response

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to revoke permanent token %s for user %s: %s", token_id, current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to revoke permanent token"
        )


# WebAuthn Registration Endpoints


@router.post(
    "/webauthn/register/begin",
    response_model=WebAuthnRegistrationBeginResponse,
    summary="Begin WebAuthn credential registration",
    description="""
    Start the WebAuthn credential registration process for the authenticated user.
    
    **Process:**
    1. Generates a unique cryptographic challenge
    2. Retrieves user's existing credentials to exclude duplicates
    3. Returns WebAuthn credential creation options for the client
    
    **Security Features:**
    - Requires valid JWT authentication
    - Challenge expires in 5 minutes
    - Rate limiting (50 requests per 60 seconds per IP)
    - Enhanced request validation and sanitization
    - Origin and referer validation
    - Comprehensive security logging and monitoring
    - Security headers for WebAuthn operations
    
    **Usage:**
    - Call this endpoint first to get registration options
    - Use the response with WebAuthn API on the client side
    - Complete registration with /webauthn/register/complete
    
    **Response:**
    Returns WebAuthn credential creation options including challenge, 
    relying party info, user info, and supported algorithms.
    """,
    responses={
        200: {
            "description": "Registration options generated successfully",
            "model": WebAuthnRegistrationBeginResponse,
        },
        400: {"description": "Invalid request format or security validation failed", "model": StandardErrorResponse},
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        403: {"description": "Origin not allowed or security check failed", "model": StandardErrorResponse},
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
        500: {"description": "Failed to generate registration options", "model": StandardErrorResponse},
    },
    tags=["WebAuthn"],
)
@log_performance("webauthn_register_begin")
async def webauthn_register_begin(
    request: Request,
    registration_request: WebAuthnRegistrationBeginRequest,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Begin WebAuthn credential registration for authenticated user.
    
    Generates WebAuthn credential creation options following existing auth patterns
    with enhanced security validation, request sanitization, and comprehensive monitoring.
    """
    # Apply rate limiting following existing patterns
    await security_manager.check_rate_limit(
        request,
        "webauthn-register-begin",
        rate_limit_requests=WEBAUTHN_REGISTER_BEGIN_RATE_LIMIT,
        rate_limit_period=WEBAUTHN_REGISTER_BEGIN_RATE_PERIOD,
    )

    # Enhanced security validation using existing patterns
    from second_brain_database.routes.auth.services.webauthn.security_validation import webauthn_security_validator
    
    # Apply comprehensive security validation
    validation_context = await webauthn_security_validator.validate_webauthn_request(
        request=request,
        operation_type="registration",
        user_id=current_user["username"],
        additional_checks={"authenticated_user": current_user}
    )
    
    # Apply additional request integrity validation
    integrity_context = await webauthn_security_validator.validate_request_integrity(
        request=request,
        operation_type="registration",
        user_id=current_user["username"]
    )

    # Sanitize request data following existing sanitization patterns
    sanitized_request_data = webauthn_security_validator.sanitize_webauthn_data(
        data=registration_request.model_dump(),
        operation_type="registration"
    )

    # Extract request info and set logging context
    request_info = extract_request_info(request)
    set_auth_logging_context(user_id=current_user["username"], ip_address=request_info["ip_address"])

    logger.info("WebAuthn registration begin for user: %s", current_user["username"])

    try:
        # Use the registration service following existing auth patterns
        # Call the registration service with user and sanitized device name
        options_dict = await begin_registration(
            user=current_user,
            device_name=sanitized_request_data.get("device_name")
        )

        # Convert to response model for API consistency
        options = WebAuthnRegistrationBeginResponse(**options_dict)

        logger.info("WebAuthn registration options generated for user: %s", current_user["username"])
        
        # Create response with enhanced security headers
        from fastapi.responses import JSONResponse
        response_data = options.model_dump()
        response = JSONResponse(content=response_data)
        
        # Add security headers following existing patterns
        response = webauthn_security_validator.add_security_headers(response, "registration")
        
        return response

    except HTTPException:
        # Re-raise HTTP exceptions from service layer
        raise
    except Exception as e:
        logger.error("Failed to generate WebAuthn registration options for user %s: %s", current_user["username"], e, exc_info=True)
        
        # Log authentication failure following existing patterns
        log_auth_failure(
            event_type="webauthn_registration_begin_failed",
            user_id=current_user["username"],
            ip_address=request_info["ip_address"],
            details={
                "error": str(e), 
                "device_name": sanitized_request_data.get("device_name"),
                "validation_context": validation_context
            },
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate WebAuthn registration options"
        )


@router.post(
    "/webauthn/register/complete",
    response_model=WebAuthnRegistrationCompleteResponse,
    summary="Complete WebAuthn credential registration",
    description="""
    Complete the WebAuthn credential registration process.
    
    **Process:**
    1. Validates the WebAuthn credential creation response
    2. Verifies the challenge and attestation
    3. Stores the credential public key and metadata
    4. Returns confirmation with credential details
    
    **Security Features:**
    - Challenge validation (one-time use, 5-minute expiry)
    - Attestation verification (simplified for "none" attestation)
    - Credential deduplication (updates existing if same authenticator)
    - Rate limiting (50 requests per 60 seconds per IP)
    - Enhanced request validation and sanitization
    - Origin and referer validation
    - Comprehensive audit logging and monitoring
    - Security headers for WebAuthn operations
    
    **Usage:**
    - Call after successful WebAuthn credential creation on client
    - Provide the complete WebAuthn credential creation response
    - Optionally specify a friendly device name
    
    **Response:**
    Returns confirmation with credential metadata and registration timestamp.
    """,
    responses={
        201: {
            "description": "Credential registered successfully",
            "model": WebAuthnRegistrationCompleteResponse,
        },
        400: {"description": "Invalid credential response, expired challenge, or security validation failed", "model": StandardErrorResponse},
        401: {"description": "Authentication required", "model": StandardErrorResponse},
        403: {"description": "Origin not allowed or security check failed", "model": StandardErrorResponse},
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
        500: {"description": "Failed to register credential", "model": StandardErrorResponse},
    },
    tags=["WebAuthn"],
)
@log_performance("webauthn_register_complete")
async def webauthn_register_complete(
    request: Request,
    registration_request: WebAuthnRegistrationCompleteRequest,
    current_user: dict = Depends(enforce_all_lockdowns),
):
    """
    Complete WebAuthn credential registration for authenticated user.
    
    Validates credential response and stores credential following existing 
    validation and error handling patterns with enhanced security validation.
    """
    # Apply rate limiting following existing patterns
    await security_manager.check_rate_limit(
        request,
        "webauthn-register-complete",
        rate_limit_requests=WEBAUTHN_REGISTER_COMPLETE_RATE_LIMIT,
        rate_limit_period=WEBAUTHN_REGISTER_COMPLETE_RATE_PERIOD,
    )

    # Enhanced security validation using existing patterns
    from second_brain_database.routes.auth.services.webauthn.security_validation import webauthn_security_validator
    
    # Apply comprehensive security validation
    validation_context = await webauthn_security_validator.validate_webauthn_request(
        request=request,
        operation_type="registration",
        user_id=current_user["username"],
        additional_checks={"authenticated_user": current_user}
    )
    
    # Apply additional request integrity validation for registration complete
    integrity_context = await webauthn_security_validator.validate_request_integrity(
        request=request,
        operation_type="registration",
        user_id=current_user["username"]
    )

    # Sanitize request data following existing sanitization patterns
    sanitized_request_data = webauthn_security_validator.sanitize_webauthn_data(
        data=registration_request.model_dump(),
        operation_type="registration"
    )

    # Extract request info and set logging context
    request_info = extract_request_info(request)
    set_auth_logging_context(user_id=current_user["username"], ip_address=request_info["ip_address"])

    logger.info("WebAuthn registration complete for user: %s", current_user["username"])

    try:
        # Use the complete_registration service function following existing patterns
        from second_brain_database.routes.auth.services.webauthn.registration import complete_registration

        # Convert sanitized request to dictionary format expected by service
        credential_response = {
            "id": sanitized_request_data.get("id"),
            "rawId": sanitized_request_data.get("rawId"),
            "response": sanitized_request_data.get("response"),
            "type": sanitized_request_data.get("type")
        }

        # Call the registration service following existing service layer patterns
        result = await complete_registration(
            user=current_user,
            credential_response=credential_response,
            device_name=sanitized_request_data.get("device_name")
        )

        logger.info("WebAuthn credential registered successfully for user: %s", current_user["username"])
        
        # Log successful registration using existing auth success pattern
        log_auth_success(
            event_type="webauthn_registration_completed",
            user_id=current_user["username"],
            ip_address=request_info["ip_address"],
            details={
                "credential_id": result["credential_id"],
                "device_name": result["device_name"],
                "authenticator_type": result["authenticator_type"],
                "operation": "credential_registration",
                "validation_context": validation_context
            },
        )

        # Create response with enhanced security headers
        from fastapi.responses import JSONResponse
        response_data = WebAuthnRegistrationCompleteResponse(
            message=result["message"],
            credential_id=result["credential_id"],
            device_name=result["device_name"],
            authenticator_type=result["authenticator_type"],
            created_at=result["created_at"]
        ).model_dump()
        
        response = JSONResponse(content=response_data, status_code=201)
        
        # Add security headers following existing patterns
        response = webauthn_security_validator.add_security_headers(response, "registration")
        
        return response

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, etc.)
        raise
    except Exception as e:
        logger.error("Failed to complete WebAuthn registration for user %s: %s", current_user["username"], e, exc_info=True)
        
        # Log authentication failure following existing patterns
        log_auth_failure(
            event_type="webauthn_registration_complete_failed",
            user_id=current_user["username"],
            ip_address=request_info["ip_address"],
            details={
                "error": str(e),
                "credential_id": sanitized_request_data.get("id"),
                "device_name": sanitized_request_data.get("device_name"),
                "validation_context": validation_context
            },
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register WebAuthn credential"
        )


# WebAuthn Credential Management Endpoints


@router.get("/webauthn/credentials", response_model=WebAuthnCredentialListResponse)
async def list_webauthn_credentials(request: Request, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    List all WebAuthn credentials for the authenticated user.

    Returns credential metadata (ID, device name, created date, last used, etc.)
    but never returns sensitive cryptographic data for security.
    
    **Security Features:**
    - Requires authentication
    - Only returns user's own credentials
    - Excludes sensitive cryptographic data (public keys, signature counters)
    - Comprehensive audit logging
    
    **Response Data:**
    - Credential ID (for management operations)
    - Device name (user-friendly identifier)
    - Authenticator type (platform/cross-platform)
    - Transport methods (usb, nfc, internal, etc.)
    - Registration and last used timestamps
    - Active status
    """
    await security_manager.check_rate_limit(
        request,
        "webauthn-credentials-list",
        rate_limit_requests=WEBAUTHN_CREDENTIALS_LIST_RATE_LIMIT,
        rate_limit_period=WEBAUTHN_CREDENTIALS_LIST_RATE_PERIOD,
    )

    from second_brain_database.routes.auth.services.webauthn.credentials import get_user_credential_list

    try:
        credentials = await get_user_credential_list(str(current_user["_id"]), include_inactive=False)

        return WebAuthnCredentialListResponse(
            credentials=credentials,
            total_count=len(credentials)
        )

    except Exception as e:
        logger.error("Failed to list WebAuthn credentials for user %s: %s", current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve WebAuthn credentials"
        )


@router.delete("/webauthn/credentials/{credential_id}", response_model=WebAuthnCredentialDeletionResponse)
async def delete_webauthn_credential(request: Request, credential_id: str, current_user: dict = Depends(enforce_all_lockdowns)):
    """
    Delete a WebAuthn credential by its ID.

    Only the credential owner can delete their own credentials.
    Deleted credentials are immediately invalidated and cannot be used for authentication.
    
    **Security Features:**
    - Requires authentication
    - Ownership verification (users can only delete their own credentials)
    - Comprehensive security logging
    - Cache invalidation for immediate effect
    - Soft delete with audit trail
    
    **Important Notes:**
    - This action cannot be undone
    - The credential will no longer work for authentication
    - Consider the impact on user's ability to access their account
    - Users should have alternative authentication methods available
    """
    await security_manager.check_rate_limit(
        request,
        "webauthn-credentials-delete",
        rate_limit_requests=WEBAUTHN_CREDENTIALS_DELETE_RATE_LIMIT,
        rate_limit_period=WEBAUTHN_CREDENTIALS_DELETE_RATE_PERIOD,
    )

    from second_brain_database.routes.auth.services.webauthn.credentials import delete_credential_by_id

    try:
        deletion_response = await delete_credential_by_id(user_id=str(current_user["_id"]), credential_id=credential_id)

        if deletion_response is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found or already deleted")

        logger.info("WebAuthn credential deleted: credential_id=%s, user=%s", credential_id, current_user["username"])

        return WebAuthnCredentialDeletionResponse(**deletion_response)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error("Failed to delete WebAuthn credential %s for user %s: %s", credential_id, current_user["username"], e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete WebAuthn credential"
        )


# WebAuthn Authentication Endpoints


@router.post(
    "/webauthn/authenticate/begin",
    response_model=WebAuthnAuthenticationBeginResponse,
    summary="Begin WebAuthn passwordless authentication",
    description="""
    Start the WebAuthn authentication process for passwordless login.
    
    **Process:**
    1. Validates user exists and account is active
    2. Retrieves user's registered WebAuthn credentials
    3. Generates a unique cryptographic challenge
    4. Returns WebAuthn credential request options for the client
    
    **Authentication Methods:**
    - Username-based authentication
    - Email-based authentication
    
    **Security Features:**
    - Account status validation (active, verified, not suspended)
    - Challenge generation with secure randomness
    - Credential filtering (only active credentials)
    - Rate limiting (50 requests per 60 seconds per IP)
    - Enhanced request validation and sanitization
    - Origin and referer validation
    - Comprehensive audit logging and monitoring
    - Security headers for WebAuthn operations
    - IP-based security checks (if trusted IP lockdown enabled)
    
    **Usage:**
    - Call this endpoint first to get authentication options
    - Use the response with WebAuthn API on the client side
    - Complete authentication with /webauthn/authenticate/complete
    
    **Response:**
    Returns WebAuthn credential request options including challenge,
    allowed credentials, and authentication parameters.
    """,
    responses={
        200: {
            "description": "Authentication options generated successfully",
            "model": WebAuthnAuthenticationBeginResponse,
        },
        400: {"description": "Invalid request format or security validation failed", "model": StandardErrorResponse},
        401: {"description": "Invalid credentials or user not found", "model": StandardErrorResponse},
        403: {
            "description": "Account inactive, email not verified, account suspended, or origin not allowed",
            "model": StandardErrorResponse,
        },
        404: {
            "description": "No WebAuthn credentials found for user",
            "model": StandardErrorResponse,
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
        500: {"description": "Failed to generate authentication options", "model": StandardErrorResponse},
    },
    tags=["WebAuthn"],
)
@log_performance("webauthn_authenticate_begin")
async def webauthn_authenticate_begin(
    request: Request,
    auth_request: WebAuthnAuthenticationBeginRequest,
):
    """
    Begin WebAuthn authentication process for passwordless login.
    
    Generates WebAuthn credential request options following existing auth patterns
    with enhanced security validation, request sanitization, and comprehensive monitoring.
    """
    # Apply rate limiting following existing patterns
    await security_manager.check_rate_limit(
        request,
        "webauthn-authenticate-begin",
        rate_limit_requests=WEBAUTHN_AUTH_BEGIN_RATE_LIMIT,
        rate_limit_period=WEBAUTHN_AUTH_BEGIN_RATE_PERIOD,
    )

    # Enhanced security validation using existing patterns
    from second_brain_database.routes.auth.services.webauthn.security_validation import webauthn_security_validator
    
    identifier = auth_request.username or auth_request.email or "unknown"
    
    # Apply comprehensive security validation
    validation_context = await webauthn_security_validator.validate_webauthn_request(
        request=request,
        operation_type="authentication",
        user_id=identifier,
        additional_checks={"public_endpoint": True}  # No auth required for this endpoint
    )
    
    # Apply additional request integrity validation for authentication begin
    integrity_context = await webauthn_security_validator.validate_request_integrity(
        request=request,
        operation_type="authentication",
        user_id=identifier
    )

    # Sanitize request data following existing sanitization patterns
    sanitized_request_data = webauthn_security_validator.sanitize_webauthn_data(
        data=auth_request.model_dump(),
        operation_type="authentication"
    )

    # Extract request info and set logging context
    request_info = extract_request_info(request)
    set_auth_logging_context(user_id=identifier, ip_address=request_info["ip_address"])

    logger.info("WebAuthn authentication begin for identifier: %s", identifier)

    try:
        # Call the authentication service following existing service layer patterns
        options_dict = await begin_authentication(
            username=sanitized_request_data.get("username"),
            email=sanitized_request_data.get("email"),
            user_verification=sanitized_request_data.get("user_verification", "preferred"),
            ip_address=request_info["ip_address"]
        )

        # Convert to response model for API consistency
        options = WebAuthnAuthenticationBeginResponse(**options_dict)

        logger.info("WebAuthn authentication options generated for identifier: %s", identifier)

        # Create response with enhanced security headers
        from fastapi.responses import JSONResponse
        response_data = options.model_dump()
        response = JSONResponse(content=response_data)
        
        # Add security headers following existing patterns
        response = webauthn_security_validator.add_security_headers(response, "authentication")
        
        return response

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, user not found, etc.)
        raise
    except Exception as e:
        logger.error("Failed to generate WebAuthn authentication options for identifier %s: %s", identifier, e, exc_info=True)
        
        # Log authentication failure following existing patterns
        log_auth_failure(
            event_type="webauthn_authentication_begin_failed",
            user_id=identifier,
            ip_address=request_info["ip_address"],
            details={
                "error": str(e),
                "has_username": bool(sanitized_request_data.get("username")),
                "has_email": bool(sanitized_request_data.get("email")),
                "validation_context": validation_context
            },
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate WebAuthn authentication options"
        )


@router.post(
    "/webauthn/authenticate/complete",
    response_model=WebAuthnAuthenticationCompleteResponse,
    summary="Complete WebAuthn passwordless authentication",
    description="""
    Complete the WebAuthn authentication process and obtain JWT token.
    
    **Process:**
    1. Validates the WebAuthn assertion response from the client
    2. Verifies the challenge and cryptographic signature
    3. Updates credential usage statistics
    4. Generates JWT token for authenticated session
    5. Returns authentication result with user information
    
    **Security Features:**
    - Challenge validation (one-time use, 60-second expiry)
    - Cryptographic signature verification (simulated for now)
    - Origin validation for security
    - Credential ownership verification
    - Signature counter validation (replay attack prevention)
    - Rate limiting (50 requests per 60 seconds per IP)
    - Comprehensive audit logging
    - JWT token generation with user context
    
    **Usage:**
    - Call after successful WebAuthn assertion on client
    - Provide the complete WebAuthn assertion response
    - Receive JWT token for API access
    
    **Response:**
    Returns JWT token and user information, similar to standard login response,
    plus additional WebAuthn-specific metadata about the credential used.
    """,
    responses={
        200: {
            "description": "Authentication successful",
            "model": WebAuthnAuthenticationCompleteResponse,
        },
        400: {
            "description": "Invalid assertion response, expired challenge, or invalid origin",
            "model": StandardErrorResponse,
        },
        401: {
            "description": "Invalid credential or authentication failed",
            "model": StandardErrorResponse,
        },
        429: {"description": "Rate limit exceeded", "model": StandardErrorResponse},
        500: {"description": "Failed to complete authentication", "model": StandardErrorResponse},
    },
    tags=["WebAuthn"],
)
@log_performance("webauthn_authenticate_complete")
async def webauthn_authenticate_complete(
    request: Request,
    auth_request: WebAuthnAuthenticationCompleteRequest,
):
    """
    Complete WebAuthn authentication process and return JWT token.
    
    Validates assertion response and generates JWT token following existing 
    authentication patterns with enhanced security validation, request sanitization,
    and comprehensive monitoring.
    """
    # Apply rate limiting following existing patterns
    await security_manager.check_rate_limit(
        request,
        "webauthn-authenticate-complete",
        rate_limit_requests=WEBAUTHN_AUTH_COMPLETE_RATE_LIMIT,
        rate_limit_period=WEBAUTHN_AUTH_COMPLETE_RATE_PERIOD,
    )

    # Enhanced security validation using existing patterns
    from second_brain_database.routes.auth.services.webauthn.security_validation import webauthn_security_validator
    
    credential_id_short = auth_request.id[:16] + "..." if len(auth_request.id) > 16 else auth_request.id
    
    # Apply comprehensive security validation
    validation_context = await webauthn_security_validator.validate_webauthn_request(
        request=request,
        operation_type="authentication",
        user_id="unknown",  # Will be determined from credential
        additional_checks={"public_endpoint": True}  # No auth required for this endpoint
    )
    
    # Apply additional request integrity validation for authentication complete
    integrity_context = await webauthn_security_validator.validate_request_integrity(
        request=request,
        operation_type="authentication",
        user_id="unknown"
    )

    # Sanitize request data following existing sanitization patterns
    sanitized_request_data = webauthn_security_validator.sanitize_webauthn_data(
        data=auth_request.model_dump(),
        operation_type="authentication"
    )

    # Extract request info and set logging context
    request_info = extract_request_info(request)
    set_auth_logging_context(user_id="unknown", ip_address=request_info["ip_address"])

    logger.info("WebAuthn authentication complete for credential: %s", credential_id_short)

    try:
        # Call the authentication service following existing service layer patterns
        result = await complete_authentication(
            credential_id=sanitized_request_data.get("id"),
            authenticator_data=sanitized_request_data.get("response", {}).get("authenticatorData"),
            client_data_json=sanitized_request_data.get("response", {}).get("clientDataJSON"),
            signature=sanitized_request_data.get("response", {}).get("signature"),
            user_handle=sanitized_request_data.get("response", {}).get("userHandle"),
            ip_address=request_info["ip_address"]
        )

        # Update logging context with authenticated user
        set_auth_logging_context(user_id=result["username"], ip_address=request_info["ip_address"])

        logger.info("WebAuthn authentication successful for user: %s", result["username"])
        
        # Log successful authentication using existing auth success pattern
        log_auth_success(
            event_type="webauthn_authentication_successful",
            user_id=result["username"],
            ip_address=request_info["ip_address"],
            details={
                "credential_id": credential_id_short,
                "authentication_method": "webauthn",
                "device_name": result["credential_used"]["device_name"],
                "authenticator_type": result["credential_used"]["authenticator_type"],
                "validation_context": validation_context
            },
        )

        # Create response with enhanced security headers
        from fastapi.responses import JSONResponse
        response_data = WebAuthnAuthenticationCompleteResponse(
            access_token=result["access_token"],
            token_type=result["token_type"],
            client_side_encryption=result["client_side_encryption"],
            issued_at=result["issued_at"],
            expires_at=result["expires_at"],
            is_verified=result["is_verified"],
            role=result["role"],
            username=result["username"],
            email=result["email"],
            authentication_method=result["authentication_method"],
            credential_used=result["credential_used"]
        ).model_dump()
        
        response = JSONResponse(content=response_data)
        
        # Add security headers following existing patterns
        response = webauthn_security_validator.add_security_headers(response, "authentication")
        
        return response

    except HTTPException:
        # Re-raise HTTP exceptions (validation errors, authentication failures, etc.)
        raise
    except Exception as e:
        logger.error("Failed to complete WebAuthn authentication for credential %s: %s", credential_id_short, e, exc_info=True)
        
        # Log authentication failure following existing patterns
        log_auth_failure(
            event_type="webauthn_authentication_complete_failed",
            user_id="unknown",
            ip_address=request_info["ip_address"],
            details={
                "error": str(e),
                "credential_id": credential_id_short,
                "validation_context": validation_context
            },
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete WebAuthn authentication"
        )


# WebAuthn Web Interface Endpoints


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Serve secure login page with both password and WebAuthn authentication options.
    
    For mobile/desktop apps (like Flutter), returns JSON error instead of HTML.
    For web browsers, HTML rendering is currently disabled.
    """
    await security_manager.check_rate_limit(
        request,
        "login-page",
        rate_limit_requests=100,
        rate_limit_period=60,
    )
    request_info = extract_request_info(request)
    logger.info("Login page accessed from IP: %s", request_info["ip_address"])
    
    # Check if request is from a mobile/desktop app (not a web browser)
    user_agent = request.headers.get("user-agent", "").lower()
    is_mobile_app = any(app in user_agent for app in ["emotion_tracker", "dart", "flutter"])
    
    if is_mobile_app:
        # Return JSON error for mobile/desktop apps instead of HTML/redirect
        logger.warning(
            "GET /auth/login accessed from mobile app - User-Agent: %s, Headers: %s", 
            user_agent, 
            dict(request.headers)
        )
        return JSONResponse(
            status_code=405,
            content={
                "error": "METHOD_NOT_ALLOWED",
                "message": "GET method not allowed. Please use POST /auth/login for authentication.",
                "hint": "This endpoint only accepts POST requests with JSON body containing username/email and password.",
                "debug_info": {
                    "received_method": "GET",
                    "expected_method": "POST",
                    "correct_endpoint": "POST /auth/login",
                    "your_user_agent": request.headers.get("user-agent", "unknown")
                }
            }
        )
    
    # Disabled: do not render HTML page for web browsers
    # try:
    #     from second_brain_database.routes.auth.routes_html import render_login_page
    #     return render_login_page()
    # except Exception as e:
    #     logger.error("Failed to serve login page: %s", e)
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Failed to load login page"
    #     )
    raise HTTPException(status_code=405, detail="Method not allowed: HTML login page rendering is disabled.")


@router.get("/webauthn/setup", response_class=HTMLResponse)
async def webauthn_setup_page(request: Request):
    """
    Serve web interface for passkey setup and management.
    """
    await security_manager.check_rate_limit(
        request,
        "webauthn-setup-page",
        rate_limit_requests=50,
        rate_limit_period=60,
    )
    request_info = extract_request_info(request)
    logger.info("WebAuthn setup page accessed from IP: %s", request_info["ip_address"])
    # Disabled: do not render HTML page
    # try:
    #     from second_brain_database.routes.auth.routes_html import render_webauthn_setup_page
    #     return render_webauthn_setup_page()
    # except Exception as e:
    #     logger.error("Failed to serve WebAuthn setup page: %s", e)
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Failed to load passkey setup page"
    #     )
    raise HTTPException(status_code=405, detail="Method not allowed: HTML WebAuthn setup page rendering is disabled.")


@router.get("/webauthn/manage", response_class=HTMLResponse)
async def webauthn_manage_page(request: Request):
    """
    Serve web interface for passkey management.
    """
    await security_manager.check_rate_limit(
        request,
        "webauthn-manage-page",
        rate_limit_requests=50,
        rate_limit_period=60,
    )
    request_info = extract_request_info(request)
    logger.info("WebAuthn manage page accessed from IP: %s", request_info["ip_address"])
    # Disabled: do not render HTML page
    # try:
    #     from second_brain_database.routes.auth.routes_html import render_webauthn_manage_page
    #     return render_webauthn_manage_page()
    # except Exception as e:
    #     logger.error("Failed to serve WebAuthn manage page: %s", e)
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Failed to load passkey management page"
    #     )
    raise HTTPException(status_code=405, detail="Method not allowed: HTML WebAuthn manage page rendering is disabled.")


# --- Temporary Access Token Endpoints for IP Lockdown Action Buttons ---

@router.get("/temporary-access/allow-once")
async def handle_allow_once_ip_access(request: Request, token: str = Query(...)):
    """
    Handle "allow once" action from blocked IP notification email.
    
    This endpoint validates the temporary access token and creates a temporary
    bypass that allows the IP to access the account for 15 minutes.
    """
    from second_brain_database.routes.auth.services.temporary_access import (
        validate_and_use_temporary_ip_token,
        execute_allow_once_ip_access
    )
    
    await security_manager.check_rate_limit(request, "temporary-access", rate_limit_requests=10, rate_limit_period=60)
    
    try:
        # Validate and use the token
        token_data = await validate_and_use_temporary_ip_token(token)
        if not token_data:
            logger.warning("Invalid or expired allow once token from IP %s", 
                          security_manager.get_client_ip(request))
            raise HTTPException(
                status_code=400, 
                detail="Invalid or expired token. Please request a new blocked access notification."
            )
        
        # Verify this is an allow_once token
        if token_data.get("action") != "allow_once":
            logger.warning("Wrong token type for allow once: %s", token_data.get("action"))
            raise HTTPException(status_code=400, detail="Invalid token type for this action.")
        
        # Execute the allow once action
        success = await execute_allow_once_ip_access(token_data)
        if not success:
            logger.error("Failed to execute allow once action for token: %s", token_data)
            raise HTTPException(
                status_code=500, 
                detail="Failed to process allow once request. Please try again or contact support."
            )
        
        # Return success page
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Access Granted - IP Lockdown</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .success-icon {{ font-size: 48px; color: #28a745; margin-bottom: 20px; }}
                h1 {{ color: #28a745; margin-bottom: 20px; }}
                .details {{ background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0; }}
                .detail-item {{ margin: 10px 0; }}
                .detail-label {{ font-weight: 600; }}
                .detail-value {{ font-family: monospace; background: #e9ecef; padding: 4px 8px; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Access Granted!</h1>
                <p>Your IP address has been temporarily allowed to access your account.</p>
                
                <div class="details">
                    <div class="detail-item">
                        <span class="detail-label">IP Address:</span><br>
                        <span class="detail-value">{token_data.get('ip_address')}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Access Duration:</span><br>
                        <span class="detail-value">15 minutes</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Original Endpoint:</span><br>
                        <span class="detail-value">{token_data.get('endpoint')}</span>
                    </div>
                </div>
                
                <p><strong>You can now access your account from this IP address for the next 15 minutes.</strong></p>
                <p>After this time expires, normal IP lockdown restrictions will resume.</p>
                
                <p style="margin-top: 30px; font-size: 14px; color: #6c757d;">
                    If you frequently access your account from this location, consider adding this IP to your trusted list.
                </p>
            </div>
        </body>
        </html>
        """)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in allow once handler: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again or contact support."
        )


@router.get("/temporary-access/add-to-trusted")
async def handle_add_to_trusted_ip_list(request: Request, token: str = Query(...)):
    """
    Handle "add to trusted list" action from blocked IP notification email.
    
    This endpoint validates the temporary access token and adds the IP address
    to the user's trusted IP list permanently.
    """
    from second_brain_database.routes.auth.services.temporary_access import (
        validate_and_use_temporary_ip_token,
        execute_add_to_trusted_ip_list
    )
    
    await security_manager.check_rate_limit(request, "temporary-access", rate_limit_requests=10, rate_limit_period=60)
    
    try:
        # Validate and use the token
        token_data = await validate_and_use_temporary_ip_token(token)
        if not token_data:
            logger.warning("Invalid or expired add to trusted token from IP %s", 
                          security_manager.get_client_ip(request))
            raise HTTPException(
                status_code=400, 
                detail="Invalid or expired token. Please request a new blocked access notification."
            )
        
        # Verify this is an add_to_trusted token
        if token_data.get("action") != "add_to_trusted":
            logger.warning("Wrong token type for add to trusted: %s", token_data.get("action"))
            raise HTTPException(status_code=400, detail="Invalid token type for this action.")
        
        # Execute the add to trusted action
        success = await execute_add_to_trusted_ip_list(token_data)
        if not success:
            logger.error("Failed to execute add to trusted action for token: %s", token_data)
            raise HTTPException(
                status_code=500, 
                detail="Failed to add IP to trusted list. Please try again or contact support."
            )
        
        # Return success page
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>IP Added to Trusted List</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    max-width: 600px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #f8f9fa;
                }}
                .container {{
                    background: white;
                    padding: 40px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .success-icon {{ font-size: 48px; color: #28a745; margin-bottom: 20px; }}
                h1 {{ color: #28a745; margin-bottom: 20px; }}
                .details {{ background: #f8f9fa; padding: 20px; border-radius: 6px; margin: 20px 0; }}
                .detail-item {{ margin: 10px 0; }}
                .detail-label {{ font-weight: 600; }}
                .detail-value {{ font-family: monospace; background: #e9ecef; padding: 4px 8px; border-radius: 4px; }}
                .security-notice {{ background: #d1ecf1; border: 1px solid #bee5eb; border-radius: 6px; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">🔒</div>
                <h1>IP Added to Trusted List!</h1>
                <p>Your IP address has been permanently added to your trusted list.</p>
                
                <div class="details">
                    <div class="detail-item">
                        <span class="detail-label">IP Address:</span><br>
                        <span class="detail-value">{token_data.get('ip_address')}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Original Endpoint:</span><br>
                        <span class="detail-value">{token_data.get('endpoint')}</span>
                    </div>
                </div>
                
                <p><strong>You can now access your account from this IP address without restrictions.</strong></p>
                
                <div class="security-notice">
                    <h4>🛡️ Security Reminder</h4>
                    <p>This IP address will now have permanent access to your account. Make sure this is a location you trust and use regularly.</p>
                    <p>You can manage your trusted IP list through the API or by contacting support if you need to remove this IP later.</p>
                </div>
                
                <p style="margin-top: 30px; font-size: 14px; color: #6c757d;">
                    Your IP lockdown settings remain active for all other IP addresses.
                </p>
            </div>
        </body>
        </html>
        """)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in add to trusted handler: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again or contact support."
        )


# --- User Agent Temporary Access Token Endpoints for Email Action Buttons ---

@router.get("/temporary-access/allow-once-user-agent")
async def handle_allow_once_user_agent_access(request: Request, token: str = Query(...)):
    """
    Handle "allow once" action from blocked User Agent notification email.
    
    This endpoint validates the temporary access token and creates a temporary bypass
    for the User Agent, allowing access for a limited time without adding to trusted list.
    """
    from second_brain_database.routes.auth.services.temporary_access import (
        validate_and_use_temporary_user_agent_token,
        execute_allow_once_user_agent_access
    )
    
    try:
        logger.info("Processing allow once User Agent access from IP %s", 
                   security_manager.get_client_ip(request))
        
        # Validate and use the token (single use)
        token_data = await validate_and_use_temporary_user_agent_token(token)
        if not token_data:
            logger.warning("Invalid or expired allow once User Agent token from IP %s", 
                          security_manager.get_client_ip(request))
            raise HTTPException(
                status_code=400, 
                detail="Invalid or expired token. Please request a new one."
            )
        
        # Verify this is an allow_once token
        if token_data.get("action") != "allow_once":
            logger.warning("Wrong token type for allow once: %s", token_data.get("action"))
            raise HTTPException(status_code=400, detail="Invalid token type for this action.")
        
        # Execute the allow once action
        success = await execute_allow_once_user_agent_access(token_data)
        if not success:
            logger.error("Failed to execute allow once action for token: %s", token_data)
            raise HTTPException(
                status_code=500, 
                detail="Failed to create temporary access. Please try again or contact support."
            )
        
        # Return success page
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Temporary Access Granted</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    background: white;
                    border-radius: 12px;
                    padding: 40px;
                    text-align: center;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    max-width: 500px;
                }}
                .success-icon {{ font-size: 64px; margin-bottom: 20px; }}
                h1 {{ color: #28a745; margin-bottom: 20px; }}
                .details {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .user-agent {{ font-family: monospace; word-break: break-all; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">🔓</div>
                <h1>Temporary Access Granted!</h1>
                <p>Your User Agent has been granted temporary access for 15 minutes.</p>
                
                <div class="details">
                    <strong>User Agent:</strong><br>
                    <span class="user-agent">{token_data.get('user_agent', 'Unknown')}</span>
                </div>
                
                <p style="margin-top: 30px; font-size: 14px; color: #6c757d;">
                    If you frequently access your account from this browser/application, consider adding this User Agent to your trusted list.
                </p>
            </div>
        </body>
        </html>
        """)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in allow once User Agent handler: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again or contact support."
        )


@router.get("/temporary-access/add-to-trusted-user-agent")
async def handle_add_to_trusted_user_agent_list(request: Request, token: str = Query(...)):
    """
    Handle "add to trusted list" action from blocked User Agent notification email.
    
    This endpoint validates the temporary access token and adds the User Agent address
    to the user's permanent trusted User Agent list.
    """
    from second_brain_database.routes.auth.services.temporary_access import (
        validate_and_use_temporary_user_agent_token,
        execute_add_to_trusted_user_agent_list
    )
    
    try:
        logger.info("Processing add User Agent to trusted list from IP %s", 
                   security_manager.get_client_ip(request))
        
        # Validate and use the token (single use)
        token_data = await validate_and_use_temporary_user_agent_token(token)
        if not token_data:
            logger.warning("Invalid or expired add to trusted User Agent token from IP %s", 
                          security_manager.get_client_ip(request))
            raise HTTPException(
                status_code=400, 
                detail="Invalid or expired token. Please request a new one."
            )
        
        # Verify this is an add_to_trusted token
        if token_data.get("action") != "add_to_trusted":
            logger.warning("Wrong token type for add to trusted: %s", token_data.get("action"))
            raise HTTPException(status_code=400, detail="Invalid token type for this action.")
        
        # Execute the add to trusted action
        success = await execute_add_to_trusted_user_agent_list(token_data)
        if not success:
            logger.error("Failed to execute add to trusted action for token: %s", token_data)
            raise HTTPException(
                status_code=500, 
                detail="Failed to add User Agent to trusted list. Please try again or contact support."
            )
        
        # Return success page
        return HTMLResponse(content=f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>User Agent Added to Trusted List</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    background: white;
                    border-radius: 12px;
                    padding: 40px;
                    text-align: center;
                    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                    max-width: 500px;
                }}
                .success-icon {{ font-size: 64px; margin-bottom: 20px; }}
                h1 {{ color: #28a745; margin-bottom: 20px; }}
                .details {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .user-agent {{ font-family: monospace; word-break: break-all; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">🔒</div>
                <h1>User Agent Added to Trusted List!</h1>
                <p>Your User Agent has been permanently added to your trusted list.</p>
                
                <div class="details">
                    <strong>User Agent:</strong><br>
                    <span class="user-agent">{token_data.get('user_agent', 'Unknown')}</span>
                </div>
                
                <p style="margin-top: 30px; font-size: 14px; color: #6c757d;">
                    You will no longer receive blocking notifications for this User Agent.
                </p>
            </div>
        </body>
        </html>
        """)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error in add to trusted User Agent handler: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail="An unexpected error occurred. Please try again or contact support."
        )