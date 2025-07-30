"""
OAuth2 consent screen system.

This module implements the OAuth2 consent screen endpoints for handling user authorization
decisions in the OAuth2 authorization code flow. It provides secure consent handling with
CSRF protection, consent persistence, and comprehensive audit logging.

Features:
- GET /oauth2/consent endpoint for rendering consent screens
- POST /oauth2/consent endpoint for handling user approval/denial
- CSRF protection for consent forms
- Consent decision storage and retrieval
- HTML consent screen templates with scope descriptions
- Comprehensive security and audit logging
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from second_brain_database.managers.logging_manager import get_logger
from .auth_middleware import get_current_user_flexible
from .client_manager import client_manager
from .error_handler import (
    OAuth2ErrorCode,
    access_denied_error,
    invalid_request_error,
    server_error,
)
from .models import (
    ConsentRequest,
    get_scope_descriptions,
    validate_scopes,
)
from .services.consent_manager import consent_manager
from .templates import render_consent_screen, render_consent_error

logger = get_logger(prefix="[OAuth2 Consent]")

router = APIRouter(prefix="/oauth2", tags=["OAuth2 Consent"])


@router.get(
    "/consent",
    response_class=HTMLResponse,
    summary="OAuth2 Consent Screen",
    description="""
    Display OAuth2 consent screen for user authorization.
    
    This endpoint renders an HTML consent screen that shows the user what permissions
    a client application is requesting. The user can then approve or deny the request.
    
    **Security Features:**
    - CSRF protection with secure tokens
    - Session validation and fingerprinting
    - Comprehensive audit logging
    - Client validation and verification
    - Scope validation and descriptions
    
    **Flow:**
    1. User is redirected here from /oauth2/authorize after authentication
    2. System validates the request parameters and user session
    3. Displays consent screen with client info and requested permissions
    4. User can approve or deny the consent request
    5. Form submission goes to POST /oauth2/consent
    
    **Parameters are typically passed via OAuth2 state preservation:**
    - client_id: OAuth2 client identifier
    - state: OAuth2 state parameter for CSRF protection
    - scopes: Comma-separated list of requested scopes
    - redirect_uri: Where to redirect after consent decision
    """,
    responses={
        200: {"description": "Consent screen HTML", "content": {"text/html": {"example": "HTML consent form"}}},
        400: {"description": "Invalid request parameters"},
        401: {"description": "User not authenticated"},
        403: {"description": "Access denied or invalid client"},
        404: {"description": "Client not found"},
        500: {"description": "Internal server error"}
    }
)
async def get_consent_screen(
    request: Request,
    client_id: str = Query(..., description="OAuth2 client identifier"),
    state: str = Query(..., description="OAuth2 state parameter"),
    scopes: str = Query(..., description="Comma-separated list of requested scopes"),
    redirect_uri: Optional[str] = Query(None, description="OAuth2 redirect URI"),
    current_user: Dict = Depends(get_current_user_flexible)
) -> HTMLResponse:
    """
    Display OAuth2 consent screen for user authorization.
    
    Args:
        request: FastAPI request object
        client_id: OAuth2 client identifier
        state: OAuth2 state parameter for CSRF protection
        scopes: Comma-separated list of requested scopes
        redirect_uri: Optional redirect URI for validation
        current_user: Authenticated user from session or JWT
        
    Returns:
        HTMLResponse: HTML consent screen
        
    Raises:
        HTTPException: For various error conditions
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # Log consent screen request
        logger.info(
            "Consent screen requested for client %s by user %s",
            client_id,
            current_user.get("username", "unknown"),
            extra={
                "client_id": client_id,
                "user_id": current_user.get("_id"),
                "username": current_user.get("username"),
                "state": state,
                "scopes": scopes,
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
                "event_type": "consent_screen_requested"
            }
        )
        
        # Validate and parse scopes
        try:
            scope_list = [scope.strip() for scope in scopes.split(",") if scope.strip()]
            validated_scopes = validate_scopes(scope_list)
        except ValueError as e:
            logger.warning(
                "Invalid scopes requested for client %s: %s",
                client_id,
                str(e),
                extra={
                    "client_id": client_id,
                    "user_id": current_user.get("_id"),
                    "invalid_scopes": scopes,
                    "error": str(e)
                }
            )
            return HTMLResponse(
                content=render_consent_error(
                    error_message="Invalid permissions requested. Please contact the application developer.",
                    client_name=client_id
                ),
                status_code=400
            )
        
        # Get client information
        client = await client_manager.get_client(client_id)
        if not client:
            logger.error(
                "Consent requested for non-existent client: %s",
                client_id,
                extra={
                    "client_id": client_id,
                    "user_id": current_user.get("_id"),
                    "state": state
                }
            )
            return HTMLResponse(
                content=render_consent_error(
                    error_message="Application not found. The requested application may have been removed or is invalid.",
                    client_name=client_id
                ),
                status_code=404
            )
        
        # Validate client is active
        if not client.is_active:
            logger.warning(
                "Consent requested for inactive client: %s",
                client_id,
                extra={
                    "client_id": client_id,
                    "client_name": client.name,
                    "user_id": current_user.get("_id"),
                    "state": state
                }
            )
            return HTMLResponse(
                content=render_consent_error(
                    error_message="This application is currently unavailable. Please try again later.",
                    client_name=client.name
                ),
                status_code=403
            )
        
        # Validate requested scopes are allowed for this client
        client_scopes = set(client.scopes)
        requested_scopes_set = set(validated_scopes)
        if not requested_scopes_set.issubset(client_scopes):
            invalid_scopes = requested_scopes_set - client_scopes
            logger.warning(
                "Client %s requested unauthorized scopes: %s",
                client_id,
                invalid_scopes,
                extra={
                    "client_id": client_id,
                    "client_name": client.name,
                    "user_id": current_user.get("_id"),
                    "invalid_scopes": list(invalid_scopes),
                    "client_scopes": list(client_scopes),
                    "state": state
                }
            )
            return HTMLResponse(
                content=render_consent_error(
                    error_message="This application is requesting permissions it's not authorized to access.",
                    client_name=client.name
                ),
                status_code=403
            )
        
        # Validate redirect URI if provided
        if redirect_uri and redirect_uri not in client.redirect_uris:
            logger.warning(
                "Invalid redirect URI for client %s: %s",
                client_id,
                redirect_uri,
                extra={
                    "client_id": client_id,
                    "client_name": client.name,
                    "user_id": current_user.get("_id"),
                    "invalid_redirect_uri": redirect_uri,
                    "allowed_redirect_uris": client.redirect_uris,
                    "state": state
                }
            )
            return HTMLResponse(
                content=render_consent_error(
                    error_message="Invalid redirect configuration. Please contact the application developer.",
                    client_name=client.name
                ),
                status_code=400
            )
        
        # Check for existing consent
        existing_consent = await consent_manager.check_existing_consent(
            current_user["_id"], client_id, validated_scopes
        )
        has_existing_consent = existing_consent is not None
        
        # Get scope descriptions for display
        scope_descriptions = get_scope_descriptions(validated_scopes)
        
        # Generate CSRF token for the consent form
        csrf_token = _generate_csrf_token()
        
        # Store CSRF token in session or temporary storage
        await _store_consent_csrf_token(request, csrf_token, current_user["_id"], client_id, state)
        
        # Render consent screen
        consent_html = render_consent_screen(
            client_name=client.name,
            client_description=client.description or "",
            website_url=client.website_url or "",
            requested_scopes=scope_descriptions,
            client_id=client_id,
            state=state,
            csrf_token=csrf_token,
            existing_consent=has_existing_consent
        )
        
        # Log successful consent screen display
        logger.info(
            "Consent screen displayed for client %s to user %s",
            client.name,
            current_user.get("username", "unknown"),
            extra={
                "client_id": client_id,
                "client_name": client.name,
                "user_id": current_user.get("_id"),
                "username": current_user.get("username"),
                "scopes": validated_scopes,
                "has_existing_consent": has_existing_consent,
                "duration_ms": (time.time() - start_time) * 1000,
                "event_type": "consent_screen_displayed"
            }
        )
        
        return HTMLResponse(content=consent_html, status_code=200)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            "Unexpected error displaying consent screen: %s",
            e,
            exc_info=True,
            extra={
                "client_id": client_id,
                "user_id": current_user.get("_id"),
                "state": state,
                "duration_ms": (time.time() - start_time) * 1000
            }
        )
        return HTMLResponse(
            content=render_consent_error(
                error_message="An unexpected error occurred. Please try again later.",
                client_name=client_id
            ),
            status_code=500
        )


@router.post(
    "/consent",
    summary="Handle OAuth2 Consent Decision",
    description="""
    Handle user consent decision (approve or deny) for OAuth2 authorization.
    
    This endpoint processes the user's consent decision from the consent form.
    It validates the request, stores the consent decision, and redirects back
    to the OAuth2 authorization flow.
    
    **Security Features:**
    - CSRF token validation to prevent cross-site request forgery
    - Session validation and user authentication
    - Comprehensive audit logging of consent decisions
    - Secure consent storage and management
    - Rate limiting and abuse protection
    
    **Flow:**
    1. User submits consent form (approve or deny)
    2. System validates CSRF token and user session
    3. Processes consent decision and stores in database
    4. Redirects back to OAuth2 authorization endpoint
    5. Authorization endpoint continues with code generation or error
    
    **Form Parameters:**
    - client_id: OAuth2 client identifier
    - state: OAuth2 state parameter
    - scopes: Comma-separated list of scopes
    - approved: "true" for approval, "false" for denial
    - csrf_token: CSRF protection token
    """,
    responses={
        302: {"description": "Redirect to OAuth2 authorization endpoint"},
        400: {"description": "Invalid request or CSRF token"},
        401: {"description": "User not authenticated"},
        403: {"description": "Access denied or security violation"},
        500: {"description": "Internal server error"}
    }
)
async def handle_consent_decision(
    request: Request,
    client_id: str = Form(..., description="OAuth2 client identifier"),
    state: str = Form(..., description="OAuth2 state parameter"),
    scopes: str = Form(..., description="Comma-separated list of requested scopes"),
    approved: str = Form(..., description="User consent decision: 'true' or 'false'"),
    csrf_token: str = Form(..., description="CSRF protection token"),
    current_user: Dict = Depends(get_current_user_flexible)
) -> RedirectResponse:
    """
    Handle user consent decision for OAuth2 authorization.
    
    Args:
        request: FastAPI request object
        client_id: OAuth2 client identifier
        state: OAuth2 state parameter
        scopes: Comma-separated list of requested scopes
        approved: User consent decision ("true" or "false")
        csrf_token: CSRF protection token
        current_user: Authenticated user from session or JWT
        
    Returns:
        RedirectResponse: Redirect to OAuth2 authorization endpoint
        
    Raises:
        HTTPException: For various error conditions
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # Parse approval decision
        is_approved = approved.lower() == "true"
        
        # Log consent decision attempt
        logger.info(
            "Consent decision submitted for client %s by user %s: %s",
            client_id,
            current_user.get("username", "unknown"),
            "APPROVED" if is_approved else "DENIED",
            extra={
                "client_id": client_id,
                "user_id": current_user.get("_id"),
                "username": current_user.get("username"),
                "state": state,
                "scopes": scopes,
                "approved": is_approved,
                "client_ip": client_ip,
                "user_agent": request.headers.get("user-agent", ""),
                "event_type": "consent_decision_submitted"
            }
        )
        
        # Validate CSRF token
        if not await _validate_consent_csrf_token(request, csrf_token, current_user["_id"], client_id, state):
            logger.warning(
                "CSRF token validation failed for consent decision",
                extra={
                    "client_id": client_id,
                    "user_id": current_user.get("_id"),
                    "username": current_user.get("username"),
                    "state": state,
                    "client_ip": client_ip,
                    "event_type": "consent_csrf_validation_failed"
                }
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid security token. Please try again."
            )
        
        # Validate and parse scopes
        try:
            scope_list = [scope.strip() for scope in scopes.split(",") if scope.strip()]
            validated_scopes = validate_scopes(scope_list)
        except ValueError as e:
            logger.warning(
                "Invalid scopes in consent decision: %s",
                str(e),
                extra={
                    "client_id": client_id,
                    "user_id": current_user.get("_id"),
                    "invalid_scopes": scopes,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid permissions specified"
            )
        
        # Create consent request
        consent_request = ConsentRequest(
            client_id=client_id,
            scopes=validated_scopes,
            approved=is_approved,
            state=state
        )
        
        # Process consent decision
        consent_granted = await consent_manager.grant_consent(current_user["_id"], consent_request)
        
        if is_approved and not consent_granted:
            logger.error(
                "Failed to grant consent for client %s, user %s",
                client_id,
                current_user.get("username", "unknown"),
                extra={
                    "client_id": client_id,
                    "user_id": current_user.get("_id"),
                    "scopes": validated_scopes,
                    "state": state
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process consent decision"
            )
        
        # Build redirect URL back to authorization endpoint
        redirect_params = {
            "response_type": "code",
            "client_id": client_id,
            "state": state,
            "scope": " ".join(validated_scopes),
            "consent_processed": "true",
            "consent_decision": "approved" if is_approved else "denied"
        }
        
        # Add redirect_uri if it was in the original request
        # (This would typically be preserved in the OAuth2 state)
        redirect_uri = await _get_preserved_redirect_uri(request, current_user["_id"], client_id, state)
        if redirect_uri:
            redirect_params["redirect_uri"] = redirect_uri
        
        # Add code_challenge if it was in the original request
        # (This would typically be preserved in the OAuth2 state)
        code_challenge_info = await _get_preserved_pkce_info(request, current_user["_id"], client_id, state)
        if code_challenge_info:
            redirect_params.update(code_challenge_info)
        
        authorization_url = f"/oauth2/authorize?{urlencode(redirect_params)}"
        
        # Log successful consent processing
        logger.info(
            "Consent decision processed successfully for client %s by user %s: %s",
            client_id,
            current_user.get("username", "unknown"),
            "APPROVED" if is_approved else "DENIED",
            extra={
                "client_id": client_id,
                "user_id": current_user.get("_id"),
                "username": current_user.get("username"),
                "scopes": validated_scopes,
                "approved": is_approved,
                "consent_granted": consent_granted,
                "redirect_url": authorization_url,
                "duration_ms": (time.time() - start_time) * 1000,
                "event_type": "consent_decision_processed"
            }
        )
        
        # Clean up CSRF token
        await _cleanup_consent_csrf_token(request, current_user["_id"], client_id, state)
        
        return RedirectResponse(url=authorization_url, status_code=302)
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(
            "Unexpected error processing consent decision: %s",
            e,
            exc_info=True,
            extra={
                "client_id": client_id,
                "user_id": current_user.get("_id"),
                "state": state,
                "approved": approved,
                "duration_ms": (time.time() - start_time) * 1000
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process consent decision"
        )


# Helper functions for CSRF protection

def _generate_csrf_token() -> str:
    """Generate a secure CSRF token for consent forms."""
    import secrets
    import string
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


async def _store_consent_csrf_token(
    request: Request,
    csrf_token: str,
    user_id: str,
    client_id: str,
    state: str
) -> None:
    """
    Store CSRF token for consent form validation.
    
    Args:
        request: FastAPI request object
        csrf_token: Generated CSRF token
        user_id: User identifier
        client_id: OAuth2 client identifier
        state: OAuth2 state parameter
    """
    try:
        from second_brain_database.managers.redis_manager import redis_manager
        
        # Create unique key for this consent request
        csrf_key = f"oauth2:consent_csrf:{user_id}:{client_id}:{state}"
        
        # Store with 10 minute expiration
        await redis_manager.setex(csrf_key, 600, csrf_token)
        
        logger.debug(
            "Stored CSRF token for consent request",
            extra={
                "user_id": user_id,
                "client_id": client_id,
                "state": state,
                "csrf_key": csrf_key
            }
        )
        
    except Exception as e:
        logger.error("Failed to store consent CSRF token: %s", e, exc_info=True)
        # Don't raise exception to avoid breaking the flow


async def _validate_consent_csrf_token(
    request: Request,
    csrf_token: str,
    user_id: str,
    client_id: str,
    state: str
) -> bool:
    """
    Validate CSRF token for consent form submission.
    
    Args:
        request: FastAPI request object
        csrf_token: Submitted CSRF token
        user_id: User identifier
        client_id: OAuth2 client identifier
        state: OAuth2 state parameter
        
    Returns:
        bool: True if CSRF token is valid
    """
    try:
        from second_brain_database.managers.redis_manager import redis_manager
        
        # Create unique key for this consent request
        csrf_key = f"oauth2:consent_csrf:{user_id}:{client_id}:{state}"
        
        # Get stored token
        stored_token = await redis_manager.get(csrf_key)
        
        if not stored_token:
            logger.warning(
                "CSRF token not found or expired",
                extra={
                    "user_id": user_id,
                    "client_id": client_id,
                    "state": state,
                    "csrf_key": csrf_key
                }
            )
            return False
        
        # Validate token
        is_valid = csrf_token == stored_token
        
        if is_valid:
            logger.debug(
                "CSRF token validated successfully",
                extra={
                    "user_id": user_id,
                    "client_id": client_id,
                    "state": state
                }
            )
        else:
            logger.warning(
                "CSRF token mismatch",
                extra={
                    "user_id": user_id,
                    "client_id": client_id,
                    "state": state,
                    "expected_length": len(stored_token) if stored_token else 0,
                    "actual_length": len(csrf_token) if csrf_token else 0
                }
            )
        
        return is_valid
        
    except Exception as e:
        logger.error("Failed to validate consent CSRF token: %s", e, exc_info=True)
        return False


async def _cleanup_consent_csrf_token(
    request: Request,
    user_id: str,
    client_id: str,
    state: str
) -> None:
    """
    Clean up CSRF token after consent processing.
    
    Args:
        request: FastAPI request object
        user_id: User identifier
        client_id: OAuth2 client identifier
        state: OAuth2 state parameter
    """
    try:
        from second_brain_database.managers.redis_manager import redis_manager
        
        # Create unique key for this consent request
        csrf_key = f"oauth2:consent_csrf:{user_id}:{client_id}:{state}"
        
        # Delete the token
        await redis_manager.delete(csrf_key)
        
        logger.debug(
            "Cleaned up CSRF token for consent request",
            extra={
                "user_id": user_id,
                "client_id": client_id,
                "state": state
            }
        )
        
    except Exception as e:
        logger.error("Failed to cleanup consent CSRF token: %s", e, exc_info=True)
        # Don't raise exception to avoid breaking the flow


def _inject_csrf_token(html_content: str, csrf_token: str) -> str:
    """
    Inject CSRF token into the consent form HTML.
    
    Args:
        html_content: Original HTML content
        csrf_token: CSRF token to inject
        
    Returns:
        str: HTML content with CSRF token injected
    """
    try:
        # Find the form and inject the CSRF token as a hidden input
        csrf_input = f'<input type="hidden" name="csrf_token" value="{csrf_token}">'
        
        # Look for the form tag and inject after it
        form_start = html_content.find('<form method="post"')
        if form_start != -1:
            # Find the end of the form opening tag
            form_end = html_content.find('>', form_start)
            if form_end != -1:
                # Insert CSRF token after the form opening tag
                injection_point = form_end + 1
                html_content = (
                    html_content[:injection_point] +
                    '\n                ' + csrf_input +
                    html_content[injection_point:]
                )
        
        return html_content
        
    except Exception as e:
        logger.error("Failed to inject CSRF token into HTML: %s", e)
        # Return original content if injection fails
        return html_content


async def _get_preserved_redirect_uri(
    request: Request,
    user_id: str,
    client_id: str,
    state: str
) -> Optional[str]:
    """
    Get preserved redirect URI from OAuth2 state.
    
    This would typically retrieve the redirect_uri that was preserved
    during the initial authorization request.
    
    Args:
        request: FastAPI request object
        user_id: User identifier
        client_id: OAuth2 client identifier
        state: OAuth2 state parameter
        
    Returns:
        Optional[str]: Preserved redirect URI if found
    """
    try:
        # This is a placeholder implementation
        # In a real implementation, this would retrieve the redirect_uri
        # from the OAuth2 state preservation system
        
        # For now, we'll try to get it from the user's session OAuth2 context
        if hasattr(request, 'session') and 'oauth2_context' in request.session:
            oauth2_context = request.session['oauth2_context']
            if oauth2_context and oauth2_context.get('state') == state:
                return oauth2_context.get('redirect_uri')
        
        return None
        
    except Exception as e:
        logger.error("Failed to get preserved redirect URI: %s", e)
        return None


async def _get_preserved_pkce_info(
    request: Request,
    user_id: str,
    client_id: str,
    state: str
) -> Optional[Dict[str, str]]:
    """
    Get preserved PKCE information from OAuth2 state.
    
    This would typically retrieve the code_challenge and code_challenge_method
    that were preserved during the initial authorization request.
    
    Args:
        request: FastAPI request object
        user_id: User identifier
        client_id: OAuth2 client identifier
        state: OAuth2 state parameter
        
    Returns:
        Optional[Dict[str, str]]: Preserved PKCE info if found
    """
    try:
        # This is a placeholder implementation
        # In a real implementation, this would retrieve the PKCE info
        # from the OAuth2 state preservation system
        
        # For now, we'll try to get it from the user's session OAuth2 context
        if hasattr(request, 'session') and 'oauth2_context' in request.session:
            oauth2_context = request.session['oauth2_context']
            if oauth2_context and oauth2_context.get('state') == state:
                pkce_info = {}
                if oauth2_context.get('code_challenge'):
                    pkce_info['code_challenge'] = oauth2_context['code_challenge']
                if oauth2_context.get('code_challenge_method'):
                    pkce_info['code_challenge_method'] = oauth2_context['code_challenge_method']
                return pkce_info if pkce_info else None
        
        return None
        
    except Exception as e:
        logger.error("Failed to get preserved PKCE info: %s", e)
        return None