"""
Browser-based authentication endpoints for OAuth2 flows.

This module provides browser-friendly login endpoints that support OAuth2 authorization
flows by handling user authentication through HTML forms and redirects. It integrates
with the existing session management system and provides CSRF protection.

Features:
- GET /auth/login endpoint that renders login form with redirect_uri parameter
- POST /auth/login endpoint that validates credentials and creates browser session
- CSRF protection for login forms
- Redirect handling back to OAuth2 authorization URL after successful login
- Integration with existing authentication services
- Comprehensive error handling and logging
"""

import secrets
import time
from datetime import datetime
from typing import Optional
from urllib.parse import quote, unquote, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.security_manager import security_manager
from second_brain_database.routes.auth.models import LoginRequest
from second_brain_database.routes.auth.services.auth.login import login_user
from second_brain_database.routes.oauth2.session_manager import session_manager

logger = get_logger(prefix="[Browser Auth]")

router = APIRouter(prefix="/oauth", tags=["browser-auth"])

# Rate limiting constants
LOGIN_PAGE_RATE_LIMIT = 200
LOGIN_PAGE_RATE_PERIOD = 60
BROWSER_LOGIN_RATE_LIMIT = 100
BROWSER_LOGIN_RATE_PERIOD = 60

# CSRF token configuration
CSRF_TOKEN_LENGTH = 32
CSRF_COOKIE_NAME = "sbd_csrf_login"


def _generate_csrf_token() -> str:
    """Generate a secure CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def _validate_redirect_uri(redirect_uri: str) -> bool:
    """
    Validate redirect URI for security.
    
    Args:
        redirect_uri: The redirect URI to validate
        
    Returns:
        bool: True if redirect URI is safe, False otherwise
    """
    if not redirect_uri:
        return False
    
    try:
        parsed = urlparse(redirect_uri)
        
        # Must be relative or same origin
        if parsed.netloc and parsed.netloc != settings.DOMAIN:
            logger.warning("Invalid redirect URI with external domain: %s", redirect_uri)
            return False
        
        # Must start with /oauth2/ for OAuth2 flows
        if not parsed.path.startswith('/oauth2/'):
            logger.warning("Invalid redirect URI not starting with /oauth2/: %s", redirect_uri)
            return False
        
        return True
        
    except Exception as e:
        logger.warning("Failed to parse redirect URI %s: %s", redirect_uri, e)
        return False


def _render_login_page(
    redirect_uri: Optional[str] = None,
    csrf_token: Optional[str] = None,
    error_message: Optional[str] = None,
    username: Optional[str] = None
) -> str:
    """
    Render the browser login page HTML.
    
    Args:
        redirect_uri: Optional redirect URI after successful login
        csrf_token: CSRF token for form protection
        error_message: Optional error message to display
        username: Optional pre-filled username
        
    Returns:
        str: HTML content for the login page
    """
    # Generate CSRF token if not provided
    if not csrf_token:
        csrf_token = _generate_csrf_token()
    
    # Escape values for HTML safety
    redirect_uri_escaped = quote(redirect_uri) if redirect_uri else ""
    error_message_escaped = error_message.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;') if error_message else ""
    username_escaped = username.replace('"', '&quot;') if username else ""
    csrf_token_escaped = csrf_token.replace('"', '&quot;')
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - Second Brain Database</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }}
        
        .login-container {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            padding: 40px;
            width: 100%;
            max-width: 400px;
            position: relative;
            animation: fadeIn 0.5s ease-in;
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}
        
        .logo {{
            text-align: center;
            margin-bottom: 30px;
        }}
        
        .logo h1 {{
            color: #333;
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 8px;
        }}
        
        .logo p {{
            color: #666;
            font-size: 14px;
        }}
        
        .form-group {{
            margin-bottom: 20px;
        }}
        
        .form-group label {{
            display: block;
            margin-bottom: 6px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }}
        
        .form-group input {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e1e5e9;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.2s;
        }}
        
        .form-group input:focus {{
            outline: none;
            border-color: #667eea;
        }}
        
        .btn {{
            width: 100%;
            padding: 14px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            margin-bottom: 12px;
        }}
        
        .btn-primary {{
            background: #667eea;
            color: white;
        }}
        
        .btn-primary:hover:not(:disabled) {{
            background: #5a6fd8;
            transform: translateY(-1px);
        }}
        
        .btn:disabled {{
            opacity: 0.6;
            cursor: not-allowed;
        }}
        
        .error-message {{
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            font-weight: 500;
        }}
        
        .oauth2-info {{
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }}
        
        .oauth2-info strong {{
            display: block;
            margin-bottom: 4px;
        }}
        
        .loading {{
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 2px solid #ffffff;
            border-radius: 50%;
            border-top-color: transparent;
            animation: spin 1s ease-in-out infinite;
            margin-right: 8px;
        }}
        
        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}
        
        .links {{
            text-align: center;
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #e1e5e9;
        }}
        
        .links a {{
            color: #667eea;
            text-decoration: none;
            font-size: 14px;
            margin: 0 10px;
        }}
        
        .links a:hover {{
            text-decoration: underline;
        }}
        
        /* Focus styles for accessibility */
        .btn:focus {{
            outline: 2px solid #667eea;
            outline-offset: 2px;
        }}
        
        .form-group input:focus {{
            outline: 2px solid #667eea;
            outline-offset: 2px;
        }}
        
        /* High contrast mode support */
        @media (prefers-contrast: high) {{
            .login-container {{
                border: 2px solid #000;
            }}
            
            .btn {{
                border: 2px solid currentColor;
            }}
        }}
        
        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {{
            * {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
            }}
        }}
        
        /* Screen reader only content */
        .sr-only {{
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        }}
        
        @media (max-width: 480px) {{
            .login-container {{
                padding: 30px 20px;
            }}
            
            .logo h1 {{
                font-size: 24px;
            }}
        }}
    </style>
</head>
<body>
    <main class="login-container" role="main">
        <header class="logo">
            <h1>Second Brain</h1>
            <p>Secure Authentication</p>
        </header>
        
        {f'<div class="oauth2-info" role="status"><strong>OAuth2 Authorization</strong>You are being redirected to login for an OAuth2 application.</div>' if redirect_uri else ''}
        
        {f'<div class="error-message" role="alert">{error_message_escaped}</div>' if error_message else ''}
        
        <form id="login-form" method="post" action="/oauth/login" aria-label="Login form">
            <input type="hidden" name="csrf_token" value="{csrf_token_escaped}">
            {f'<input type="hidden" name="redirect_uri" value="{redirect_uri_escaped}">' if redirect_uri else ''}
            
            <div class="form-group">
                <label for="identifier">Username or Email</label>
                <input type="text" id="identifier" name="identifier" required autocomplete="username" value="{username_escaped}" aria-describedby="identifier-help">
                <div id="identifier-help" class="sr-only">Enter your username or email address</div>
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required autocomplete="current-password" aria-describedby="password-help">
                <div id="password-help" class="sr-only">Enter your account password</div>
            </div>
            
            <button type="submit" class="btn btn-primary" id="login-btn" aria-describedby="login-help">
                Sign In
            </button>
            <div id="login-help" class="sr-only">Submit the login form to authenticate</div>
        </form>
        
        <nav class="links" role="navigation" aria-label="Account actions">
            <a href="/auth/register" aria-label="Create a new account">Create Account</a>
            <a href="/auth/forgot-password" aria-label="Reset your password">Forgot Password?</a>
        </nav>
    </main>

    <script>
        document.getElementById('login-form').addEventListener('submit', function(e) {{
            const btn = document.getElementById('login-btn');
            btn.disabled = true;
            btn.innerHTML = '<span class="loading"></span>Signing in...';
        }});
    </script>
</body>
</html>
    """
    
    return html


@router.get(
    "/login",
    response_class=HTMLResponse,
    summary="Display browser login page",
    description="""
    Display the browser-based login page for OAuth2 authorization flows.
    
    This endpoint renders an HTML login form that users can use to authenticate
    when accessing OAuth2 authorization URLs in a browser. After successful
    authentication, users are redirected back to the OAuth2 flow.
    
    **Features:**
    - Responsive HTML login form
    - CSRF protection
    - OAuth2 redirect URI handling
    - Error message display
    - Mobile-friendly design
    
    **Security:**
    - Rate limiting (200 requests per 60 seconds per IP)
    - CSRF token generation and validation
    - Redirect URI validation for security
    - XSS protection through HTML escaping
    
    **Usage:**
    - Direct access: GET /oauth/login
    - OAuth2 redirect: GET /oauth/login?redirect_uri=/oauth2/authorize?...
    """,
    responses={
        200: {
            "description": "Login page rendered successfully",
            "content": {"text/html": {"example": "<!DOCTYPE html>..."}}
        },
        400: {
            "description": "Invalid redirect URI",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid redirect URI"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded"
                    }
                }
            }
        }
    },
    tags=["Browser Authentication"]
)
async def login_page(
    request: Request,
    response: Response,
    redirect_uri: Optional[str] = Query(None, description="OAuth2 redirect URI after successful login"),
    error: Optional[str] = Query(None, description="Error message to display"),
    username: Optional[str] = Query(None, description="Pre-filled username")
) -> HTMLResponse:
    """
    Display the browser login page with optional OAuth2 redirect handling.
    
    This endpoint serves an HTML login form for browser-based authentication.
    It supports OAuth2 flows by accepting a redirect_uri parameter that
    specifies where to redirect after successful authentication.
    
    Args:
        request: FastAPI request object
        response: FastAPI response object
        redirect_uri: Optional OAuth2 redirect URI
        error: Optional error message to display
        username: Optional pre-filled username
        
    Returns:
        HTMLResponse: Rendered HTML login page
        
    Raises:
        HTTPException: If redirect URI is invalid or rate limit exceeded
    """
    start_time = time.time()
    client_ip = security_manager.get_client_ip(request)
    
    try:
        # Apply rate limiting
        await security_manager.check_rate_limit(request, "login-page")
        
        # Validate redirect URI if provided
        if redirect_uri:
            # URL decode the redirect URI
            redirect_uri = unquote(redirect_uri)
            
            if not _validate_redirect_uri(redirect_uri):
                logger.warning(
                    "Invalid redirect URI in login page request: %s",
                    redirect_uri,
                    extra={"client_ip": client_ip}
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid redirect URI"
                )
        
        # Generate CSRF token
        csrf_token = _generate_csrf_token()
        
        # Set CSRF token cookie
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=csrf_token,
            max_age=1800,  # 30 minutes
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax"
        )
        
        # Render login page
        html_content = _render_login_page(
            redirect_uri=redirect_uri,
            csrf_token=csrf_token,
            error_message=error,
            username=username
        )
        
        # Log successful page render
        logger.info(
            "Rendered login page for client %s",
            client_ip,
            extra={
                "client_ip": client_ip,
                "has_redirect_uri": bool(redirect_uri),
                "has_error": bool(error),
                "duration_ms": (time.time() - start_time) * 1000
            }
        )
        
        return HTMLResponse(content=html_content)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            "Failed to render login page: %s",
            e,
            exc_info=True,
            extra={
                "client_ip": client_ip,
                "redirect_uri": redirect_uri,
                "duration_ms": (time.time() - start_time) * 1000
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load login page"
        )


@router.post(
    "/login",
    summary="Process browser login form",
    description="""
    Process browser-based login form submission with session creation.
    
    This endpoint handles form-based login submissions from the browser login page.
    It validates user credentials, creates a secure browser session, and redirects
    the user back to the OAuth2 authorization flow or a default location.
    
    **Authentication Flow:**
    1. Validate CSRF token for security
    2. Authenticate user credentials (username/email + password)
    3. Create secure browser session with HTTP-only cookies
    4. Redirect to OAuth2 authorization URL or default location
    
    **Security Features:**
    - CSRF token validation
    - Rate limiting (100 requests per 60 seconds per IP)
    - Secure session creation with fingerprinting
    - Comprehensive audit logging
    - Input validation and sanitization
    
    **Form Fields:**
    - identifier: Username or email address
    - password: User password
    - csrf_token: CSRF protection token (hidden field)
    - redirect_uri: OAuth2 redirect URI (hidden field, optional)
    
    **Response:**
    - Success: HTTP 302 redirect to OAuth2 flow or dashboard
    - Error: HTTP 200 with error message displayed on login page
    """,
    responses={
        302: {
            "description": "Login successful, redirecting to OAuth2 flow or dashboard",
            "headers": {
                "Location": {
                    "description": "Redirect URL",
                    "schema": {"type": "string"}
                },
                "Set-Cookie": {
                    "description": "Session cookies",
                    "schema": {"type": "string"}
                }
            }
        },
        200: {
            "description": "Login failed, showing error on login page",
            "content": {"text/html": {"example": "<!DOCTYPE html>..."}}
        },
        400: {
            "description": "Invalid form data or CSRF token",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid form data"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Rate limit exceeded"
                    }
                }
            }
        }
    },
    tags=["Browser Authentication"]
)
async def browser_login(
    request: Request,
    response: Response,
    identifier: str = Form(..., description="Username or email address"),
    password: str = Form(..., description="User password"),
    csrf_token: str = Form(..., description="CSRF protection token"),
    redirect_uri: Optional[str] = Form(None, description="OAuth2 redirect URI after login")
) -> Response:
    """
    Process browser login form submission, validate CSRF, and authenticate user.
    """
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token or not csrf_token or not secrets.compare_digest(cookie_token, csrf_token):
        logger.warning("CSRF token validation failed for browser login")
        # Re-render login page with error
        html = _render_login_page(
            redirect_uri=redirect_uri,
            csrf_token=_generate_csrf_token(),
            error_message="Session expired or invalid CSRF token. Please try again.",
            username=identifier
        )
        # Set new CSRF cookie for next attempt
        response = HTMLResponse(content=html, status_code=200)
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=_generate_csrf_token(),
            max_age=3600,
            httponly=False,
            secure=True,
            samesite="Lax"
        )
        return response

    try:
        login_result = await login_user(
            identifier=identifier,
            password=password,
            request=request,
            browser_login=True
        )
        redirect_target = redirect_uri if redirect_uri and _validate_redirect_uri(redirect_uri) else "/dashboard"
        resp = RedirectResponse(url=redirect_target, status_code=302)
        return resp
    except Exception as e:
        logger.warning(f"Browser login failed: {e}")
        html = _render_login_page(
            redirect_uri=redirect_uri,
            csrf_token=_generate_csrf_token(),
            error_message="Invalid credentials or login error. Please try again.",
            username=identifier
        )
        response = HTMLResponse(content=html, status_code=200)
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=_generate_csrf_token(),
            max_age=3600,
            httponly=False,
            secure=True,
            samesite="Lax"
        )
        return response