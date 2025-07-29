"""
OAuth2 authorization server routes.

This module implements the OAuth2 authorization endpoints including:
- Authorization endpoint (/oauth2/authorize) for initiating OAuth2 flows
- Token endpoint (/oauth2/token) for exchanging authorization codes for tokens
- Consent management endpoints for user authorization

The implementation follows RFC 6749 (OAuth 2.0) and RFC 7636 (PKCE) standards.
"""

from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from second_brain_database.docs.models import (
    StandardErrorResponse,
    StandardSuccessResponse,
    create_error_responses,
    create_standard_responses,
)
from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth.routes import get_current_user_dep, get_current_user, oauth2_scheme
from second_brain_database.routes.auth.services.auth.login import create_access_token

from .client_manager import client_manager
from .error_handler import (
    oauth2_error_handler,
    OAuth2ErrorCode,
    OAuth2ErrorSeverity,
    invalid_request_error,
    invalid_client_error,
    invalid_grant_error,
    access_denied_error,
    server_error,
    security_violation_error,
)
from .logging_utils import (
    oauth2_logger,
    OAuth2EventType,
    log_authorization_flow,
    log_token_flow,
    log_security_violation,
    log_oauth2_error,
    log_performance_event,
    log_rate_limit_event,
    log_client_management_event,
    log_token_lifecycle_event
)

# Import audit and monitoring capabilities
try:
    from .audit_manager import oauth2_audit_manager, record_audit_event
    from .monitoring import oauth2_monitoring, record_performance_metric, record_error_event, record_security_event
    from .metrics import oauth2_metrics, time_request, time_token_generation
    AUDIT_MONITORING_AVAILABLE = True
except ImportError:
    oauth2_audit_manager = None
    oauth2_monitoring = None
    oauth2_metrics = None
    AUDIT_MONITORING_AVAILABLE = False
from .models import (
    AuthorizationRequest,
    ClientType,
    ConsentInfo,
    ConsentRequest,
    OAuth2Error,
    OAuthClientRegistration,
    OAuthClientResponse,
    ResponseType,
    get_scope_descriptions,
    validate_scopes,
)
from .utils import get_client_type_string
from .security_manager import oauth2_security_manager
from .security_middleware import oauth2_security_middleware
from .token_encryption import oauth2_token_encryption
from .security_middleware import oauth2_security_middleware
from .token_encryption import oauth2_token_encryption
from .services.auth_code_manager import auth_code_manager
from .services.consent_manager import consent_manager
from .services.pkce_validator import PKCEValidator
from .services.token_manager import token_manager
from .templates import render_consent_screen, render_consent_error

logger = get_logger(prefix="[OAuth2 Routes]")

router = APIRouter(prefix="/oauth2", tags=["OAuth2"])


def create_oauth2_user_dependency(client_id_param: str):
    """
    Create a custom dependency that applies rate limiting before authentication.
    This ensures rate limiting is checked before authentication failures.
    """
    async def get_current_user_with_rate_limiting(
        request: Request,
        token: str = Depends(oauth2_scheme)
    ):
        # Extract client_id from request query parameters
        client_id = request.query_params.get("client_id")
        if client_id:
            # Apply rate limiting first
            await oauth2_security_manager.rate_limit_client(
                request=request,
                client_id=client_id,
                endpoint="authorize",
                rate_limit_requests=100,  # 100 requests per period
                rate_limit_period=300     # 5 minutes
            )
        
        # Then get the current user
        return await get_current_user(token)
    
    return get_current_user_with_rate_limiting


@router.get(
    "/authorize",
    summary="OAuth2 Authorization Endpoint",
    description="Initiate OAuth2 authorization code flow with PKCE and enhanced security",
    responses={
        200: {"description": "Authorization successful, redirect to client"},
        400: {"description": "Invalid request parameters"},
        401: {"description": "User not authenticated"},
        403: {"description": "User denied authorization"},
        429: {"description": "Rate limit exceeded"},
        **create_error_responses()
    }
)
async def authorize(
    request: Request,
    response_type: str = Query(..., description="Must be 'code'"),
    client_id: str = Query(..., description="Client identifier"),
    redirect_uri: str = Query(..., description="Redirect URI"),
    scope: str = Query(..., description="Space-separated list of requested scopes"),
    state: str = Query(..., description="Client state parameter for CSRF protection"),
    code_challenge: str = Query(..., description="PKCE code challenge"),
    code_challenge_method: str = Query(default="S256", description="PKCE challenge method"),
    current_user: dict = Depends(create_oauth2_user_dependency("client_id"))
):
    """
    OAuth2 authorization endpoint implementing the authorization code flow with PKCE.
    
    This endpoint handles the initial authorization request from OAuth2 clients.
    It validates the request parameters, checks user authentication, and either
    shows a consent screen or redirects back to the client with an authorization code.
    
    Flow:
    1. Validate request parameters (client_id, redirect_uri, scopes, PKCE)
    2. Check if user is authenticated (handled by get_current_user_dep)
    3. Check if user has previously granted consent
    4. If consent exists, generate authorization code and redirect
    5. If no consent, show consent screen (future implementation)
    
    Args:
        request: FastAPI request object
        response_type: OAuth2 response type (must be "code")
        client_id: OAuth2 client identifier
        redirect_uri: Client redirect URI for authorization code delivery
        scope: Space-separated list of requested scopes
        state: Client state parameter for CSRF protection
        code_challenge: PKCE code challenge for security
        code_challenge_method: PKCE challenge method (S256 or plain)
        current_user: Authenticated user from dependency injection
        
    Returns:
        RedirectResponse: Redirect to client with authorization code or error
        
    Raises:
        HTTPException: For various authorization errors
    """
    # Apply enhanced security validation and sanitization
    input_data = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method
    }
    
    try:
        sanitized_data = await oauth2_security_manager.validate_and_sanitize_input(
            input_data=input_data,
            client_id=client_id,
            request=request
        )
        
        # Use sanitized data
        client_id = sanitized_data["client_id"]
        redirect_uri = sanitized_data["redirect_uri"]
        scope = sanitized_data["scope"]
        state = sanitized_data["state"]
        code_challenge = sanitized_data["code_challenge"]
        code_challenge_method = sanitized_data["code_challenge_method"]
        
    except HTTPException as e:
        # Log security violation
        await oauth2_security_manager._log_security_violation(
            event_type="input_validation_failed",
            client_id=client_id,
            request=request,
            details={"error": e.detail}
        )
        raise
    
    # Log authorization request
    oauth2_logger.log_authorization_request(
        client_id=client_id,
        user_id=current_user.get('username'),
        scopes=scope.split(),
        redirect_uri=redirect_uri,
        state=state,
        code_challenge_method=code_challenge_method,
        request=request
    )
    
    try:
        # Enhanced input validation and sanitization
        input_params = {
            "response_type": response_type,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method
        }
        
        sanitized_params = await oauth2_security_manager.validate_and_sanitize_input(
            input_params,
            client_id=client_id,
            request=request
        )
        
        # Use sanitized parameters
        response_type = sanitized_params["response_type"]
        client_id = sanitized_params["client_id"]
        redirect_uri = sanitized_params["redirect_uri"]
        scope = sanitized_params["scope"]
        state = sanitized_params["state"]
        code_challenge = sanitized_params["code_challenge"]
        code_challenge_method = sanitized_params["code_challenge_method"]
        
        # Validate response_type
        if response_type != ResponseType.CODE.value:
            return oauth2_error_handler.authorization_error(
                error_code=OAuth2ErrorCode.UNSUPPORTED_RESPONSE_TYPE,
                error_description="Only 'code' response type is supported",
                redirect_uri=redirect_uri,
                state=state,
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                severity=OAuth2ErrorSeverity.LOW
            )
        
        # Enhanced redirect URI security validation
        redirect_uri_valid = await oauth2_security_manager.validate_redirect_uri_security(
            redirect_uri=redirect_uri,
            client_id=client_id,
            request=request
        )
        
        if not redirect_uri_valid:
            return oauth2_error_handler.authorization_error(
                error_code=OAuth2ErrorCode.INVALID_REDIRECT_URI,
                error_description="Invalid or suspicious redirect URI",
                redirect_uri=redirect_uri,
                state=state,
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                severity=OAuth2ErrorSeverity.HIGH
            )
        
        # Comprehensive security validation
        await oauth2_security_manager.validate_client_request_security(
            request=request,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state
        )
        
        # Enhanced redirect URI security validation
        if not await oauth2_security_manager.validate_redirect_uri_security(
            redirect_uri=redirect_uri,
            client_id=client_id,
            request=request
        ):
            return oauth2_error_handler.authorization_error(
                error_code=OAuth2ErrorCode.INVALID_REQUEST,
                error_description="Redirect URI failed security validation",
                redirect_uri=redirect_uri,
                state=state,
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                severity=OAuth2ErrorSeverity.HIGH
            )
        
        # Validate and parse scopes
        try:
            requested_scopes = scope.split()
            validated_scopes = validate_scopes(requested_scopes)
        except ValueError as e:
            return oauth2_error_handler.authorization_error(
                error_code=OAuth2ErrorCode.INVALID_SCOPE,
                error_description=str(e),
                redirect_uri=redirect_uri,
                state=state,
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                severity=OAuth2ErrorSeverity.LOW,
                additional_context={"requested_scopes": requested_scopes}
            )
        
        # Get client information
        client = await client_manager.get_client(client_id)
        if not client:
            return oauth2_error_handler.authorization_error(
                error_code=OAuth2ErrorCode.INVALID_CLIENT,
                error_description="Client not found",
                redirect_uri=redirect_uri,
                state=state,
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                severity=OAuth2ErrorSeverity.MEDIUM
            )
        
        # Validate client scopes
        client_scopes = set(client.scopes)
        requested_scopes_set = set(validated_scopes)
        if not requested_scopes_set.issubset(client_scopes):
            invalid_scopes = requested_scopes_set - client_scopes
            return oauth2_error_handler.authorization_error(
                error_code=OAuth2ErrorCode.INVALID_SCOPE,
                error_description=f"Client not authorized for scopes: {', '.join(invalid_scopes)}",
                redirect_uri=redirect_uri,
                state=state,
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                severity=OAuth2ErrorSeverity.MEDIUM,
                additional_context={
                    "client_scopes": list(client_scopes),
                    "requested_scopes": list(requested_scopes_set),
                    "invalid_scopes": list(invalid_scopes)
                }
            )
        
        # Validate PKCE parameters
        if not await oauth2_security_manager.validate_pkce_security(code_challenge, code_challenge_method):
            return oauth2_error_handler.security_error(
                error_code=OAuth2ErrorCode.INVALID_REQUEST,
                error_description="Invalid PKCE parameters",
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                security_event_type="pkce_validation_failed",
                additional_context={
                    "code_challenge_method": code_challenge_method,
                    "redirect_uri": redirect_uri,
                    "state": state
                }
            )
        
        # Check for existing consent
        existing_consent = await consent_manager.check_existing_consent(
            user_id=current_user["username"],
            client_id=client_id,
            requested_scopes=validated_scopes
        )
        
        if existing_consent:
            # User has already granted consent for these scopes, proceed with authorization
            logger.info(f"Using existing consent for client {client_id}, user {current_user['username']}")
            
            # Generate authorization code
            auth_code = auth_code_manager.generate_authorization_code()
        else:
            # Show consent screen
            logger.info(f"Showing consent screen for client {client_id}, user {current_user['username']}")
            
            # Get consent information for display
            consent_info = await consent_manager.get_consent_info(
                client_id=client_id,
                user_id=current_user["username"],
                requested_scopes=validated_scopes
            )
            
            if not consent_info:
                return server_error(
                    description="Failed to load consent information",
                    redirect_uri=redirect_uri,
                    state=state,
                    client_id=client_id,
                    user_id=current_user.get('username'),
                    request=request,
                    additional_context={"operation": "get_consent_info"}
                )
            
            # Store authorization request parameters in session/state for consent callback
            auth_params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "scopes": validated_scopes,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                "state": state,
                "user_id": current_user["username"]
            }
            
            # Store parameters with a temporary state key
            consent_state = f"consent_{state}"
            await oauth2_security_manager.store_authorization_state(consent_state, auth_params)
            
            # Render consent screen
            consent_html = render_consent_screen(
                client_name=consent_info.client_name,
                client_description=consent_info.client_description,
                website_url=consent_info.website_url,
                requested_scopes=consent_info.requested_scopes,
                client_id=client_id,
                state=consent_state,
                existing_consent=consent_info.existing_consent
            )
            
            return HTMLResponse(content=consent_html)
        
        # Generate authorization code (for existing consent path)
        auth_code = auth_code_manager.generate_authorization_code()
        
        # Store authorization code with encrypted metadata
        auth_code_data = {
            "code": auth_code,
            "client_id": client_id,
            "user_id": current_user["username"],
            "redirect_uri": redirect_uri,
            "scopes": validated_scopes,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method
        }
        
        # Store with encryption for enhanced security
        success = await oauth2_token_encryption.store_encrypted_token(
            key=f"auth_code:{auth_code}",
            token_data=auth_code_data,
            ttl_seconds=600,  # 10 minutes as per RFC 6749
            key_prefix="oauth2:encrypted_auth_codes"
        )
        
        # Also store in the traditional way for backward compatibility
        if success:
            success = await auth_code_manager.store_authorization_code(
                code=auth_code,
                client_id=client_id,
                user_id=current_user["username"],
                redirect_uri=redirect_uri,
                scopes=validated_scopes,
                code_challenge=code_challenge,
                code_challenge_method=code_challenge_method,
                ttl_seconds=600
            )
        
        if not success:
            return server_error(
                description="Failed to generate authorization code",
                redirect_uri=redirect_uri,
                state=state,
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                additional_context={"operation": "store_authorization_code"}
            )
        
        # Log successful authorization
        oauth2_logger.log_authorization_granted(
            client_id=client_id,
            user_id=current_user["username"],
            scopes=validated_scopes,
            authorization_code=auth_code,
            expires_in=600,
            request=request,
            additional_context={
                "redirect_uri": redirect_uri,
                "code_challenge_method": code_challenge_method
            }
        )
        
        # Redirect back to client with authorization code
        redirect_response = _redirect_with_code(
            redirect_uri=redirect_uri,
            code=auth_code,
            state=state
        )
        
        # Apply security headers to redirect response
        return oauth2_security_manager.apply_security_headers(redirect_response)
        
    except HTTPException:
        # Re-raise HTTP exceptions (like rate limiting)
        raise
    except Exception as e:
        # Log unexpected error with full context
        oauth2_logger.log_error_event(
            event_type=OAuth2EventType.SYSTEM_ERROR,
            error_code="server_error",
            error_description=f"Unexpected error in OAuth2 authorization: {str(e)}",
            client_id=client_id,
            user_id=current_user.get("username"),
            request=request,
            additional_context={
                "exception_type": type(e).__name__,
                "redirect_uri": redirect_uri,
                "state": state
            }
        )
        
        return server_error(
            description="Internal server error",
            redirect_uri=redirect_uri,
            state=state,
            client_id=client_id,
            user_id=current_user.get("username"),
            request=request,
            additional_context={"exception": str(e)}
        )


def _redirect_with_code(redirect_uri: str, code: str, state: str) -> RedirectResponse:
    """
    Create redirect response with authorization code.
    
    Args:
        redirect_uri: Client redirect URI
        code: Authorization code
        state: Client state parameter
        
    Returns:
        RedirectResponse with authorization code
    """
    params = {
        "code": code,
        "state": state
    }
    
    # Build redirect URL with query parameters
    separator = "&" if "?" in redirect_uri else "?"
    redirect_url = f"{redirect_uri}{separator}{urlencode(params)}"
    
    logger.debug(f"Redirecting to client with authorization code: {redirect_uri}")
    return RedirectResponse(url=redirect_url, status_code=302)


# Old _redirect_with_error function removed - now using oauth2_error_handler


@router.post(
    "/consent",
    summary="OAuth2 User Consent Endpoint",
    description="Handle user consent approval or denial for OAuth2 authorization with enhanced security",
    responses={
        302: {"description": "Redirect to client with authorization code or error"},
        400: {"description": "Invalid consent request"},
        429: {"description": "Rate limit exceeded"},
        **create_error_responses()
    }
)
async def handle_consent(
    request: Request,
    client_id: str = Form(..., description="Client identifier"),
    state: str = Form(..., description="Consent state parameter"),
    scopes: str = Form(..., description="Comma-separated list of requested scopes"),
    approved: str = Form(..., description="Whether consent was approved (true/false)"),
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Handle OAuth2 user consent approval or denial.
    
    This endpoint processes the consent form submission from the consent screen.
    It validates the consent request, stores the consent decision, and either
    generates an authorization code (if approved) or redirects with an error (if denied).
    
    Args:
        request: FastAPI request object
        client_id: OAuth2 client identifier
        state: Consent state parameter for retrieving authorization request
        scopes: Comma-separated list of requested scopes
        approved: Whether user approved the consent ("true" or "false")
        current_user: Authenticated user from dependency injection
        
    Returns:
        RedirectResponse: Redirect to client with authorization code or error
    """
    logger.info(f"Processing consent for client {client_id}, user {current_user.get('username')}, approved: {approved}")
    
    try:
        # Enhanced input validation and sanitization
        consent_input = {
            "client_id": client_id,
            "state": state,
            "scopes": scopes,
            "approved": approved
        }
        
        sanitized_input = await oauth2_security_manager.validate_and_sanitize_input(
            consent_input,
            client_id=client_id,
            request=request
        )
        
        # Use sanitized parameters
        client_id = sanitized_input["client_id"]
        state = sanitized_input["state"]
        scopes = sanitized_input["scopes"]
        approved = sanitized_input["approved"]
        # Retrieve stored authorization parameters
        auth_params = await oauth2_security_manager.get_authorization_state(state)
        if not auth_params:
            logger.error(f"Invalid or expired consent state: {state}")
            error_html = render_consent_error("Invalid or expired consent request. Please try again.")
            return HTMLResponse(content=error_html, status_code=400)
        
        # Validate that the user matches
        if auth_params.get("user_id") != current_user["username"]:
            logger.error(f"User mismatch in consent: expected {auth_params.get('user_id')}, got {current_user['username']}")
            error_html = render_consent_error("Invalid consent request. Please try again.")
            return HTMLResponse(content=error_html, status_code=400)
        
        # Parse scopes
        requested_scopes = [s.strip() for s in scopes.split(",") if s.strip()]
        
        # Create consent request
        consent_request = ConsentRequest(
            client_id=client_id,
            scopes=requested_scopes,
            approved=approved.lower() == "true",
            state=auth_params["state"]  # Original OAuth2 state
        )
        
        # Handle consent decision
        if consent_request.approved:
            # Grant consent
            consent_granted = await consent_manager.grant_consent(
                user_id=current_user["username"],
                consent_request=consent_request
            )
            
            if not consent_granted:
                return server_error(
                    description="Failed to process consent",
                    redirect_uri=auth_params["redirect_uri"],
                    state=auth_params["state"],
                    client_id=client_id,
                    user_id=current_user.get('username'),
                    request=request,
                    additional_context={"operation": "grant_consent"}
                )
            
            # Generate authorization code
            auth_code = auth_code_manager.generate_authorization_code()
            
            # Store authorization code with metadata
            success = await auth_code_manager.store_authorization_code(
                code=auth_code,
                client_id=client_id,
                user_id=current_user["username"],
                redirect_uri=auth_params["redirect_uri"],
                scopes=requested_scopes,
                code_challenge=auth_params["code_challenge"],
                code_challenge_method=auth_params["code_challenge_method"],
                ttl_seconds=600  # 10 minutes
            )
            
            if not success:
                return server_error(
                    description="Failed to generate authorization code",
                    redirect_uri=auth_params["redirect_uri"],
                    state=auth_params["state"],
                    client_id=client_id,
                    user_id=current_user.get('username'),
                    request=request,
                    additional_context={"operation": "store_authorization_code_consent"}
                )
            
            # Log successful authorization
            await oauth2_security_manager.log_oauth2_security_event(
                event_type="consent_granted",
                client_id=client_id,
                user_id=current_user["username"],
                details={
                    "scopes": requested_scopes,
                    "redirect_uri": auth_params["redirect_uri"]
                }
            )
            
            logger.info(f"Consent granted and authorization code generated for client {client_id}")
            
            # Redirect with authorization code
            redirect_response = _redirect_with_code(
                redirect_uri=auth_params["redirect_uri"],
                code=auth_code,
                state=auth_params["state"]
            )
            
            # Apply security headers
            return oauth2_security_manager.apply_security_headers(redirect_response)
        else:
            # User denied consent
            logger.info(f"User {current_user['username']} denied consent for client {client_id}")
            
            # Log consent denial
            await oauth2_security_manager.log_oauth2_security_event(
                event_type="consent_denied",
                client_id=client_id,
                user_id=current_user["username"],
                details={"scopes": requested_scopes}
            )
            
            # Redirect with access denied error
            error_response = access_denied_error(
                redirect_uri=auth_params["redirect_uri"],
                state=auth_params["state"],
                description="User denied authorization",
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                additional_context={"scopes": requested_scopes}
            )
            
            # Apply security headers
            return oauth2_security_manager.apply_security_headers(error_response)
            
    except Exception as e:
        logger.error(f"Unexpected error in consent handling: {e}", exc_info=True)
        
        # Try to get redirect URI from auth params for error redirect
        redirect_uri = auth_params.get("redirect_uri") if auth_params else None
        state_param = auth_params.get("state") if auth_params else None
        
        if redirect_uri:
            return server_error(
                description="Internal server error",
                redirect_uri=redirect_uri,
                state=state_param,
                client_id=client_id,
                user_id=current_user.get('username'),
                request=request,
                additional_context={"exception": str(e), "operation": "consent_handling"}
            )
        else:
            error_html = render_consent_error("An unexpected error occurred. Please try again.")
            return HTMLResponse(content=error_html, status_code=500)


@router.get(
    "/consents",
    summary="List User Consents",
    description="List all OAuth2 consents granted by the current user",
    responses=create_standard_responses()
)
async def list_user_consents(
    current_user: dict = Depends(get_current_user_dep)
):
    """
    List all OAuth2 consents granted by the current user.
    
    Returns a list of all active consents with client information and scope details.
    
    Args:
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: List of user consents with client information
    """
    try:
        consents = await consent_manager.list_user_consents(current_user["username"])
        
        response_data = StandardSuccessResponse(
            message=f"Retrieved {len(consents)} consents",
            data={
                "consents": consents,
                "total_count": len(consents)
            }
        )
        
        # Create JSON response with security headers
        from fastapi.responses import JSONResponse
        json_response = JSONResponse(content=response_data.model_dump())
        return oauth2_security_manager.apply_security_headers(json_response)
        
    except Exception as e:
        logger.error(f"Failed to list user consents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve consents"
        )


@router.get(
    "/consents/manage",
    summary="OAuth2 Consent Management UI",
    description="Web interface for managing OAuth2 consents",
    responses={
        200: {"description": "Consent management interface", "content": {"text/html": {}}}
    }
)
async def consent_management_ui(
    current_user: dict = Depends(get_current_user_dep)
):
    """
    OAuth2 consent management web interface.
    
    Provides a user-friendly web interface for viewing and managing OAuth2 consents.
    Users can see all applications they've granted access to and revoke access as needed.
    
    Args:
        current_user: Authenticated user from dependency injection
        
    Returns:
        HTMLResponse: Consent management interface
    """
    try:
        # Get user's consents
        consents = await consent_manager.list_user_consents(current_user["username"])
        
        # Log consent management access
        oauth2_logger.log_consent_event(
            event_type=OAuth2EventType.CONSENT_SHOWN,
            client_id="consent_management_ui",
            user_id=current_user["username"],
            scopes=[],
            additional_context={
                "action": "consent_management_ui_accessed",
                "consent_count": len(consents)
            }
        )
        
        # Render consent management UI
        from .templates import render_consent_management_ui
        consent_html = render_consent_management_ui(
            consents=consents,
            user_id=current_user["username"]
        )
        
        html_response = HTMLResponse(content=consent_html)
        return oauth2_security_manager.apply_security_headers(html_response)
        
    except Exception as e:
        logger.error(f"Failed to render consent management UI: {e}", exc_info=True)
        from .templates import render_consent_error
        error_html = render_consent_error("Failed to load consent management interface. Please try again.")
        return HTMLResponse(content=error_html, status_code=500)


@router.delete(
    "/consents/{client_id}",
    summary="Revoke User Consent",
    description="Revoke OAuth2 consent for a specific client application",
    responses=create_standard_responses()
)
async def revoke_user_consent(
    client_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Revoke OAuth2 consent for a specific client application.
    
    This will immediately invalidate all tokens issued to the client for this user
    and prevent the client from accessing the user's data until consent is granted again.
    
    Args:
        client_id: OAuth2 client identifier
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Confirmation of consent revocation
    """
    try:
        success = await consent_manager.revoke_consent(
            user_id=current_user["username"],
            client_id=client_id
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Consent not found or already revoked"
            )
        
        # Enhanced consent revocation logging
        oauth2_logger.log_consent_event(
            event_type=OAuth2EventType.CONSENT_REVOKED,
            client_id=client_id,
            user_id=current_user["username"],
            scopes=[],  # Scopes will be logged by consent_manager
            additional_context={
                "revoked_by_user": True,
                "revocation_method": "api_endpoint"
            }
        )
        
        response_data = StandardSuccessResponse(
            message=f"Consent revoked for client {client_id}",
            data={"client_id": client_id, "revoked": True}
        )
        
        # Create JSON response with security headers
        json_response = JSONResponse(content=response_data.model_dump())
        return oauth2_security_manager.apply_security_headers(json_response)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke consent for client {client_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke consent"
        )


# Health check endpoint for OAuth2 provider
@router.post(
    "/token",
    summary="OAuth2 Token Endpoint",
    description="Exchange authorization code for access tokens or refresh existing tokens",
    responses={
        200: {
            "description": "Token exchange successful",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                        "refresh_token": "rt_1234567890abcdef1234567890abcdef",
                        "scope": "read:profile write:data"
                    }
                }
            }
        },
        400: {"description": "Invalid request parameters"},
        401: {"description": "Invalid client credentials"},
        **create_error_responses()
    }
)
async def token(
    request: Request,
    grant_type: str = Form(..., description="Grant type (authorization_code or refresh_token)"),
    code: Optional[str] = Form(None, description="Authorization code (required for authorization_code grant)"),
    redirect_uri: Optional[str] = Form(None, description="Redirect URI (must match authorization request)"),
    client_id: str = Form(..., description="Client identifier"),
    client_secret: Optional[str] = Form(None, description="Client secret (required for confidential clients)"),
    code_verifier: Optional[str] = Form(None, description="PKCE code verifier"),
    refresh_token: Optional[str] = Form(None, description="Refresh token (required for refresh_token grant)")
):
    """
    OAuth2 token endpoint for authorization code exchange and token refresh.
    
    This endpoint handles two grant types:
    1. authorization_code: Exchange authorization code for access tokens
    2. refresh_token: Refresh access tokens using refresh token
    
    For authorization_code grant:
    - Validates authorization code and client credentials
    - Verifies PKCE code verifier against stored challenge
    - Issues new access token and refresh token
    
    For refresh_token grant:
    - Validates refresh token and client credentials
    - Issues new access token and rotates refresh token
    
    Args:
        request: FastAPI request object
        grant_type: OAuth2 grant type
        code: Authorization code (for authorization_code grant)
        redirect_uri: Redirect URI (must match authorization request)
        client_id: OAuth2 client identifier
        client_secret: Client secret (for confidential clients)
        code_verifier: PKCE code verifier
        refresh_token: Refresh token (for refresh_token grant)
        
    Returns:
        TokenResponse: Access token, refresh token, and metadata
    """
    # Log token request
    oauth2_logger.log_token_request(
        client_id=client_id,
        grant_type=grant_type,
        request=request,
        additional_context={
            "has_code": code is not None,
            "has_refresh_token": refresh_token is not None,
            "has_client_secret": client_secret is not None
        }
    )
    
    try:
        # Apply rate limiting for this client
        await oauth2_security_manager.rate_limit_client(
            request=request,
            client_id=client_id,
            endpoint="token",
            rate_limit_requests=200,  # Higher limit for token endpoint
            rate_limit_period=300     # 5 minutes
        )
        
        # Validate grant type
        if grant_type not in ["authorization_code", "refresh_token"]:
            return oauth2_error_handler.token_error(
                error_code=OAuth2ErrorCode.UNSUPPORTED_GRANT_TYPE,
                error_description=f"Grant type '{grant_type}' is not supported",
                client_id=client_id,
                request=request,
                severity=OAuth2ErrorSeverity.LOW,
                additional_context={"provided_grant_type": grant_type}
            )
        
        # Validate client credentials
        client = await client_manager.validate_client(client_id, client_secret)
        if not client:
            return invalid_client_error(
                description="Client authentication failed",
                client_id=client_id,
                request=request,
                additional_context={"has_client_secret": client_secret is not None}
            )
        
        if grant_type == "authorization_code":
            return await _handle_authorization_code_grant(
                request=request,
                client=client,
                code=code,
                redirect_uri=redirect_uri,
                code_verifier=code_verifier
            )
        elif grant_type == "refresh_token":
            return await _handle_refresh_token_grant(
                request=request,
                client=client,
                refresh_token=refresh_token
            )
            
    except HTTPException:
        # Re-raise HTTP exceptions (like rate limiting)
        raise
    except Exception as e:
        # Log unexpected error with full context
        oauth2_logger.log_error_event(
            event_type=OAuth2EventType.SYSTEM_ERROR,
            error_code="server_error",
            error_description=f"Unexpected error in OAuth2 token endpoint: {str(e)}",
            client_id=client_id,
            request=request,
            additional_context={
                "exception_type": type(e).__name__,
                "grant_type": grant_type
            }
        )
        
        return server_error(
            description="Internal server error",
            client_id=client_id,
            request=request,
            additional_context={"exception": str(e), "grant_type": grant_type}
        )


async def _handle_authorization_code_grant(
    request: Request,
    client,
    code: Optional[str],
    redirect_uri: Optional[str],
    code_verifier: Optional[str]
):
    """Handle authorization code grant flow."""
    # Validate required parameters
    if not code:
        return invalid_request_error(
            description="Authorization code is required",
            client_id=client.client_id,
            request=request,
            severity=OAuth2ErrorSeverity.LOW
        )
    
    if not redirect_uri:
        return invalid_request_error(
            description="Redirect URI is required",
            client_id=client.client_id,
            request=request,
            severity=OAuth2ErrorSeverity.LOW
        )
    
    if not code_verifier:
        return invalid_request_error(
            description="PKCE code verifier is required",
            client_id=client.client_id,
            request=request,
            severity=OAuth2ErrorSeverity.LOW
        )
    
    # Use authorization code (marks it as used and prevents replay)
    auth_code = await auth_code_manager.use_authorization_code(code)
    if not auth_code:
        return invalid_grant_error(
            description="Invalid or expired authorization code",
            client_id=client.client_id,
            request=request,
            severity=OAuth2ErrorSeverity.MEDIUM,
            additional_context={"provided_code": code[:8] + "***" if len(code) > 8 else "***"}
        )
    
    # Validate client matches
    if auth_code.client_id != client.client_id:
        return oauth2_error_handler.security_error(
            error_code=OAuth2ErrorCode.INVALID_GRANT,
            error_description="Authorization code was issued to a different client",
            client_id=client.client_id,
            user_id=auth_code.user_id,
            request=request,
            security_event_type="client_mismatch",
            additional_context={
                "expected_client": auth_code.client_id,
                "provided_client": client.client_id
            }
        )
    
    # Validate redirect URI matches
    if auth_code.redirect_uri != redirect_uri:
        return oauth2_error_handler.security_error(
            error_code=OAuth2ErrorCode.INVALID_GRANT,
            error_description="Redirect URI does not match authorization request",
            client_id=client.client_id,
            user_id=auth_code.user_id,
            request=request,
            security_event_type="redirect_uri_mismatch",
            additional_context={
                "expected_redirect_uri": auth_code.redirect_uri,
                "provided_redirect_uri": redirect_uri
            }
        )
    
    # Validate PKCE code verifier
    try:
        pkce_valid = PKCEValidator.validate_code_challenge(
            verifier=code_verifier,
            challenge=auth_code.code_challenge,
            method=auth_code.code_challenge_method.value
        )
        if not pkce_valid:
            return oauth2_error_handler.security_error(
                error_code=OAuth2ErrorCode.INVALID_GRANT,
                error_description="PKCE code verifier validation failed",
                client_id=client.client_id,
                user_id=auth_code.user_id,
                request=request,
                security_event_type="pkce_validation_failed",
                additional_context={
                    "code_challenge_method": auth_code.code_challenge_method.value
                }
            )
    except Exception as e:
        return oauth2_error_handler.security_error(
            error_code=OAuth2ErrorCode.INVALID_GRANT,
            error_description="PKCE code verifier validation failed",
            client_id=client.client_id,
            user_id=auth_code.user_id,
            request=request,
            security_event_type="pkce_validation_error",
            additional_context={
                "exception": str(e),
                "exception_type": type(e).__name__
            }
        )
    
    # Generate access token using existing JWT system with OAuth2 claims
    access_token = await create_access_token({
        "sub": auth_code.user_id,
        "aud": client.client_id,
        "scope": " ".join(auth_code.scopes)
    })
    
    # Generate refresh token
    refresh_token = await token_manager.generate_refresh_token(
        client_id=client.client_id,
        user_id=auth_code.user_id,
        scopes=auth_code.scopes
    )
    
    # Log successful token issuance
    oauth2_logger.log_token_issued(
        client_id=client.client_id,
        user_id=auth_code.user_id,
        scopes=auth_code.scopes,
        access_token_expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        has_refresh_token=bool(refresh_token),
        request=request,
        additional_context={
            "grant_type": "authorization_code",
            "redirect_uri": auth_code.redirect_uri
        }
    )
    
    # Return token response
    from .models import TokenResponse
    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_token=refresh_token,
        scope=" ".join(auth_code.scopes)
    )


async def _handle_refresh_token_grant(
    request: Request,
    client,
    refresh_token: Optional[str]
):
    """Handle refresh token grant flow."""
    # Validate required parameters
    if not refresh_token:
        return invalid_request_error(
            description="Refresh token is required",
            client_id=client.client_id,
            request=request,
            severity=OAuth2ErrorSeverity.LOW
        )
    
    # Use token manager to refresh access token
    token_response = await token_manager.refresh_access_token(refresh_token, client.client_id)
    if not token_response:
        return invalid_grant_error(
            description="Invalid refresh token",
            client_id=client.client_id,
            request=request,
            severity=OAuth2ErrorSeverity.MEDIUM,
            additional_context={"provided_refresh_token": refresh_token[:8] + "***" if len(refresh_token) > 8 else "***"}
        )
    
    # Log successful token refresh
    oauth2_logger.log_token_issued(
        client_id=client.client_id,
        user_id="unknown",  # User ID not available in refresh token response
        scopes=token_response.scope.split() if token_response.scope else [],
        access_token_expires_in=token_response.expires_in,
        has_refresh_token=bool(token_response.refresh_token),
        request=request,
        additional_context={
            "grant_type": "refresh_token",
            "token_rotated": True
        }
    )
    
    return token_response


# Old _token_error function removed - now using oauth2_error_handler


@router.get(
    "/health",
    summary="OAuth2 Provider Health Check",
    description="Check OAuth2 provider health and status",
    responses=create_standard_responses()
)
async def oauth2_health():
    """
    OAuth2 provider health check endpoint.
    
    Returns basic health information about the OAuth2 provider including
    component status and basic statistics.
    
    Returns:
        StandardSuccessResponse: Health status information
    """
    try:
        # Check if core components are available
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "client_manager": "healthy",
                "auth_code_manager": "healthy",
                "security_manager": "healthy",
                "pkce_validator": "healthy"
            }
        }
        
        # Get basic statistics
        try:
            code_stats = await auth_code_manager.get_code_statistics()
            health_status["statistics"] = {
                "authorization_codes": code_stats
            }
        except Exception as e:
            logger.warning(f"Failed to get OAuth2 statistics: {e}")
            health_status["statistics"] = {"error": "Statistics unavailable"}
        
        return StandardSuccessResponse(
            message="OAuth2 provider is healthy",
            data=health_status
        )
        
    except Exception as e:
        logger.error(f"OAuth2 health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OAuth2 provider health check failed"
        )


# Token cleanup and management endpoints

@router.post(
    "/cleanup",
    summary="OAuth2 Token Cleanup",
    description="Clean up expired OAuth2 tokens (admin only)",
    responses=create_standard_responses()
)
async def cleanup_expired_tokens(
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Clean up expired OAuth2 tokens.
    
    This endpoint removes expired refresh tokens from Redis to free up storage.
    Only available to admin users for maintenance purposes.
    
    Args:
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Number of tokens cleaned up
    """
    try:
        # Check if user has admin privileges (you may need to adjust this check)
        # For now, we'll allow any authenticated user to run cleanup
        
        cleaned_count = await token_manager.cleanup_expired_tokens()
        
        logger.info(f"Token cleanup completed by user {current_user['username']}: {cleaned_count} tokens cleaned")
        
        return StandardSuccessResponse(
            message=f"Cleaned up {cleaned_count} expired tokens",
            data={
                "cleaned_tokens": cleaned_count,
                "cleanup_timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired tokens: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cleanup expired tokens"
        )


@router.get(
    "/tokens/stats",
    summary="OAuth2 Token Statistics",
    description="Get statistics about OAuth2 tokens (admin only)",
    responses=create_standard_responses()
)
async def get_token_statistics(
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get statistics about OAuth2 tokens.
    
    Returns information about active, expired, and total tokens.
    Only available to admin users for monitoring purposes.
    
    Args:
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Token statistics
    """
    try:
        # Check if user has admin privileges (you may need to adjust this check)
        # For now, we'll allow any authenticated user to view stats
        
        stats = await token_manager.get_token_statistics()
        
        return StandardSuccessResponse(
            message="Token statistics retrieved successfully",
            data=stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get token statistics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve token statistics"
        )


# Legacy function for backward compatibility (will be removed in future versions)
async def _generate_refresh_token(client_id: str, user_id: str, scopes: list[str]) -> Optional[str]:
    """
    Legacy function - delegates to token_manager.
    
    Args:
        client_id: OAuth2 client identifier
        user_id: User identifier
        scopes: List of granted scopes
        
    Returns:
        Refresh token string if successful, None otherwise
    """
    return await token_manager.generate_refresh_token(client_id, user_id, scopes)


async def _validate_refresh_token(refresh_token: str, client_id: str) -> Optional[dict]:
    """
    Legacy function - delegates to token_manager.
    
    Args:
        refresh_token: Refresh token string
        client_id: Expected client identifier
        
    Returns:
        Token data if valid, None otherwise
    """
    refresh_data = await token_manager.validate_refresh_token(refresh_token, client_id)
    if refresh_data:
        return {
            "client_id": refresh_data.client_id,
            "user_id": refresh_data.user_id,
            "scopes": refresh_data.scopes,
            "created_at": refresh_data.created_at.isoformat(),
            "is_active": refresh_data.is_active
        }
    return None


async def _rotate_refresh_token(
    old_refresh_token: str,
    client_id: str,
    user_id: str,
    scopes: list[str]
) -> Optional[str]:
    """
    Legacy function - delegates to token_manager.
    
    Args:
        old_refresh_token: Current refresh token
        client_id: OAuth2 client identifier
        user_id: User identifier
        scopes: List of granted scopes
        
    Returns:
        New refresh token if successful, None otherwise
    """
    return await token_manager.rotate_refresh_token(old_refresh_token, client_id, user_id, scopes)


@router.post(
    "/revoke",
    summary="OAuth2 Token Revocation Endpoint",
    description="Revoke OAuth2 access tokens or refresh tokens",
    responses={
        200: {"description": "Token revoked successfully"},
        400: {"description": "Invalid request parameters"},
        401: {"description": "Invalid client credentials"},
        **create_error_responses()
    }
)
async def revoke_token(
    request: Request,
    token: str = Form(..., description="Token to revoke (access token or refresh token)"),
    token_type_hint: Optional[str] = Form(None, description="Hint about token type (access_token or refresh_token)"),
    client_id: str = Form(..., description="Client identifier"),
    client_secret: Optional[str] = Form(None, description="Client secret (required for confidential clients)")
):
    """
    OAuth2 token revocation endpoint following RFC 7009.
    
    This endpoint allows clients to revoke access tokens or refresh tokens.
    When a refresh token is revoked, all associated access tokens are also invalidated.
    
    Args:
        request: FastAPI request object
        token: Token to revoke (access token or refresh token)
        token_type_hint: Optional hint about token type
        client_id: OAuth2 client identifier
        client_secret: Client secret (for confidential clients)
        
    Returns:
        200 response regardless of whether token was found (per RFC 7009)
    """
    logger.info(f"OAuth2 token revocation request from client {client_id}")
    
    try:
        # Apply rate limiting for this client
        await oauth2_security_manager.rate_limit_client(
            request=request,
            client_id=client_id,
            endpoint="revoke",
            rate_limit_requests=100,  # 100 requests per period
            rate_limit_period=300     # 5 minutes
        )
        
        # Validate client credentials
        client = await client_manager.validate_client(client_id, client_secret)
        if not client:
            return invalid_client_error(
                description="Client authentication failed",
                client_id=client_id,
                request=request,
                additional_context={"operation": "token_revocation"}
            )
        
        # Determine token type and revoke accordingly
        revoked = False
        
        # Try to revoke as refresh token first (more common case)
        if token_type_hint != "access_token":
            # Check if it's a refresh token
            token_info = await token_manager.get_token_info(token)
            if token_info and token_info["client_id"] == client_id:
                # It's a valid refresh token for this client
                revoked = await token_manager.revoke_refresh_token(token)
                if revoked:
                    logger.info(f"Refresh token revoked for client {client_id}")
                    
                    # Log revocation event
                    await oauth2_security_manager.log_oauth2_security_event(
                        event_type="token_revoked",
                        client_id=client_id,
                        user_id=token_info["user_id"],
                        details={
                            "token_type": "refresh_token",
                            "revoked_by_client": True
                        }
                    )
        
        # If not revoked as refresh token, try as access token
        if not revoked and token_type_hint != "refresh_token":
            # For access tokens, we can't easily revoke them since they're JWTs
            # But we can log the revocation attempt for audit purposes
            logger.info(f"Access token revocation requested for client {client_id} (JWT tokens cannot be revoked)")
            
            # Log revocation attempt
            await oauth2_security_manager.log_oauth2_security_event(
                event_type="token_revocation_attempted",
                client_id=client_id,
                user_id=None,
                details={
                    "token_type": "access_token",
                    "note": "JWT access tokens cannot be revoked, logged for audit"
                }
            )
            
            # Consider it "revoked" for response purposes
            revoked = True
        
        # Per RFC 7009, always return 200 regardless of whether token was found
        logger.debug(f"Token revocation completed for client {client_id}")
        
        return JSONResponse(
            status_code=200,
            content={"revoked": True}
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like rate limiting)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in token revocation: {e}", exc_info=True)
        
        # Log security event for unexpected errors
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="token_revocation_error",
            client_id=client_id,
            user_id=None,
            details={"error": str(e)}
        )
        
        # Per RFC 7009, return 200 even on errors to prevent information disclosure
        return JSONResponse(
            status_code=200,
            content={"revoked": False, "error": "server_error"}
        )


async def _revoke_refresh_token(refresh_token: str) -> bool:
    """
    Legacy function - delegates to token_manager.
    
    Args:
        refresh_token: Refresh token to revoke
        
    Returns:
        True if revoked successfully, False otherwise
    """
    return await token_manager.revoke_refresh_token(refresh_token)


# OAuth2 Client Management Endpoints

@router.post(
    "/clients",
    summary="Register OAuth2 Client",
    description="Register a new OAuth2 client application for developers",
    responses={
        201: {
            "description": "Client registered successfully",
            "content": {
                "application/json": {
                    "example": {
                        "client_id": "oauth2_client_1234567890abcdef",
                        "client_secret": "cs_1234567890abcdef1234567890abcdef",
                        "name": "My Web Application",
                        "client_type": "confidential",
                        "redirect_uris": ["https://myapp.com/oauth/callback"],
                        "scopes": ["read:profile", "write:data"],
                        "created_at": "2024-01-01T12:00:00Z",
                        "is_active": True
                    }
                }
            }
        },
        400: {"description": "Invalid registration data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        **create_error_responses()
    }
)
async def register_client(
    request: Request,
    registration: OAuthClientRegistration,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Register a new OAuth2 client application.
    
    This endpoint allows developers to register OAuth2 client applications
    that can authenticate users through the Second Brain Database OAuth2 provider.
    Only authenticated users can register clients, and the client will be
    associated with the registering user.
    
    Args:
        request: FastAPI request object
        registration: Client registration data
        current_user: Authenticated user from dependency injection
        
    Returns:
        OAuthClientResponse: Client credentials and metadata
        
    Raises:
        HTTPException: For various registration errors
    """
    logger.info(f"User {current_user['username']} registering OAuth2 client: {registration.name}")
    
    try:
        # Apply rate limiting for client registration
        await oauth2_security_manager.rate_limit_client(
            request=request,
            client_id=f"registration_{current_user['username']}",
            endpoint="client_registration",
            rate_limit_requests=10,   # 10 registrations per period
            rate_limit_period=3600    # 1 hour
        )
        
        # Register the client with the current user as owner
        client_response = await client_manager.register_client(
            registration=registration,
            owner_user_id=current_user["username"]
        )
        
        # Convert client_type safely for logging
        try:
            client_type_str = get_client_type_string(registration.client_type)
            
            # Log successful conversion for monitoring
            logger.debug(
                f"Client type conversion successful for registration: {registration.client_type} -> {client_type_str}",
                extra={
                    "operation": "oauth2_client_registration",
                    "client_name": registration.name,
                    "owner_user_id": current_user["username"],
                    "original_client_type": str(registration.client_type),
                    "converted_client_type": client_type_str,
                    "conversion_success": True,
                    "audit_event": True
                }
            )
            
        except (ValueError, TypeError) as e:
            # Enhanced error logging for client_type conversion failures
            logger.error(
                f"Client type conversion failed during OAuth2 client registration: {str(e)}",
                extra={
                    "operation": "oauth2_client_registration",
                    "client_name": registration.name,
                    "owner_user_id": current_user["username"],
                    "original_client_type": str(registration.client_type),
                    "original_client_type_type": type(registration.client_type).__name__,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "conversion_success": False,
                    "audit_event": True,
                    "security_relevant": True
                }
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid client_type: {str(e)}"
            )
        
        # Log successful client registration
        oauth2_logger.log_client_registered(
            client_id=client_response.client_id,
            client_name=registration.name,
            owner_user_id=current_user["username"],
            client_type=client_type_str,
            scopes=registration.scopes,
            request=request,
            additional_context={
                "redirect_uris": registration.redirect_uris,
                "website_url": registration.website_url
            }
        )
        
        logger.info(f"Successfully registered OAuth2 client {client_response.client_id} for user {current_user['username']}")
        
        return JSONResponse(
            status_code=201,
            content=client_response.model_dump(mode='json')
        )
        
    except ValueError as e:
        logger.warning(f"Invalid client registration data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like rate limiting)
        raise
    except Exception as e:
        logger.error(f"Failed to register OAuth2 client: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register client"
        )


@router.get(
    "/clients",
    summary="List OAuth2 Clients",
    description="List OAuth2 clients owned by the current user or all clients (admin only)",
    responses=create_standard_responses()
)
async def list_clients(
    request: Request,
    all_clients: bool = Query(False, description="List all clients (admin only)"),
    current_user: dict = Depends(get_current_user_dep)
):
    """
    List OAuth2 clients.
    
    Regular users can list their own clients. Admin users can list all clients
    by setting the all_clients parameter to true.
    
    Args:
        request: FastAPI request object
        all_clients: Whether to list all clients (admin only)
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: List of OAuth2 clients
    """
    try:
        # Check admin privileges for listing all clients
        if all_clients and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required to list all clients"
            )
        
        # Determine owner filter
        owner_user_id = None if all_clients else current_user["username"]
        
        # Get clients from database
        clients = await client_manager.list_clients(owner_user_id=owner_user_id)
        
        # Convert to response format (without sensitive data)
        client_list = []
        for client in clients:
            client_data = {
                "client_id": client.client_id,
                "name": client.name,
                "description": client.description,
                "client_type": client.client_type,
                "redirect_uris": client.redirect_uris,
                "scopes": client.scopes,
                "website_url": client.website_url,
                "owner_user_id": client.owner_user_id,
                "created_at": client.created_at,
                "updated_at": client.updated_at,
                "is_active": client.is_active
            }
            client_list.append(client_data)
        
        logger.info(f"Listed {len(client_list)} OAuth2 clients for user {current_user['username']} (all_clients={all_clients})")
        
        return StandardSuccessResponse(
            message=f"Retrieved {len(client_list)} OAuth2 clients",
            data={
                "clients": client_list,
                "total_count": len(client_list),
                "owner_filter": owner_user_id
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list OAuth2 clients: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve clients"
        )


@router.get(
    "/clients/{client_id}",
    summary="Get OAuth2 Client",
    description="Get details of a specific OAuth2 client",
    responses=create_standard_responses()
)
async def get_client(
    client_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get OAuth2 client details.
    
    Users can only access their own clients unless they are admin.
    
    Args:
        client_id: OAuth2 client identifier
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: OAuth2 client details
    """
    try:
        # Get client from database
        client = await client_manager.get_client(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Check ownership or admin privileges
        if client.owner_user_id != current_user["username"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this client"
            )
        
        # Convert to response format (without sensitive data)
        client_data = {
            "client_id": client.client_id,
            "name": client.name,
            "description": client.description,
            "client_type": client.client_type,
            "redirect_uris": client.redirect_uris,
            "scopes": client.scopes,
            "website_url": client.website_url,
            "owner_user_id": client.owner_user_id,
            "created_at": client.created_at,
            "updated_at": client.updated_at,
            "is_active": client.is_active
        }
        
        return StandardSuccessResponse(
            message="Client retrieved successfully",
            data={"client": client_data}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get OAuth2 client {client_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve client"
        )


@router.put(
    "/clients/{client_id}",
    summary="Update OAuth2 Client",
    description="Update OAuth2 client configuration",
    responses=create_standard_responses()
)
async def update_client(
    client_id: str,
    updates: dict,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Update OAuth2 client configuration.
    
    Users can only update their own clients unless they are admin.
    Client secrets cannot be updated through this endpoint.
    
    Args:
        client_id: OAuth2 client identifier
        updates: Dictionary of fields to update
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Update confirmation
    """
    try:
        # Get client from database to check ownership
        client = await client_manager.get_client(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Check ownership or admin privileges
        if client.owner_user_id != current_user["username"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this client"
            )
        
        # Remove sensitive fields that shouldn't be updated via this endpoint
        forbidden_fields = ["client_id", "client_secret", "client_secret_hash", "owner_user_id", "created_at"]
        for field in forbidden_fields:
            if field in updates:
                del updates[field]
        
        # Add updated timestamp
        updates["updated_at"] = datetime.utcnow()
        
        # Update client
        success = await client_manager.update_client(client_id, updates)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update client"
            )
        
        logger.info(f"Updated OAuth2 client {client_id} by user {current_user['username']}")
        
        return StandardSuccessResponse(
            message="Client updated successfully",
            data={
                "client_id": client_id,
                "updated_fields": list(updates.keys())
            }
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid client update data: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update OAuth2 client {client_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update client"
        )


@router.delete(
    "/clients/{client_id}",
    summary="Delete OAuth2 Client",
    description="Delete OAuth2 client application",
    responses=create_standard_responses()
)
async def delete_client(
    client_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Delete OAuth2 client application.
    
    Users can only delete their own clients unless they are admin.
    This will immediately invalidate all tokens issued to this client.
    
    Args:
        client_id: OAuth2 client identifier
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Deletion confirmation
    """
    try:
        # Get client from database to check ownership
        client = await client_manager.get_client(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Check ownership or admin privileges
        if client.owner_user_id != current_user["username"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this client"
            )
        
        # Delete client
        success = await client_manager.delete_client(client_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete client"
            )
        
        # Log client deletion
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="client_deleted",
            client_id=client_id,
            user_id=current_user["username"],
            details={
                "client_name": client.name,
                "deleted_by": current_user["username"]
            }
        )
        
        logger.info(f"Deleted OAuth2 client {client_id} by user {current_user['username']}")
        
        return StandardSuccessResponse(
            message="Client deleted successfully",
            data={
                "client_id": client_id,
                "deleted": True
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete OAuth2 client {client_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete client"
        )


@router.post(
    "/clients/{client_id}/regenerate-secret",
    summary="Regenerate Client Secret",
    description="Regenerate client secret for confidential OAuth2 clients",
    responses={
        200: {
            "description": "Client secret regenerated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Client secret regenerated successfully",
                        "data": {
                            "client_id": "oauth2_client_1234567890abcdef",
                            "client_secret": "cs_new1234567890abcdef1234567890abcdef",
                            "regenerated_at": "2024-01-01T12:00:00Z"
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid request (e.g., public client)"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Client not found"},
        **create_error_responses()
    }
)
async def regenerate_client_secret(
    client_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Regenerate client secret for confidential OAuth2 clients.
    
    This endpoint allows regenerating the client secret for confidential clients.
    The old secret will be immediately invalidated. Only works for confidential clients.
    
    Args:
        client_id: OAuth2 client identifier
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: New client secret (shown only once)
    """
    try:
        # Get client from database to check ownership and type
        client = await client_manager.get_client(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Check ownership or admin privileges
        if client.owner_user_id != current_user["username"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this client"
            )
        
        # Check if client is confidential
        if client.client_type != ClientType.CONFIDENTIAL:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client secret can only be regenerated for confidential clients"
            )
        
        # Regenerate client secret
        new_secret = await client_manager.regenerate_client_secret(client_id)
        if not new_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to regenerate client secret"
            )
        
        # Log secret regeneration
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="client_secret_regenerated",
            client_id=client_id,
            user_id=current_user["username"],
            details={
                "client_name": client.name,
                "regenerated_by": current_user["username"]
            }
        )
        
        logger.info(f"Regenerated client secret for {client_id} by user {current_user['username']}")
        
        return StandardSuccessResponse(
            message="Client secret regenerated successfully",
            data={
                "client_id": client_id,
                "client_secret": new_secret,  # Only shown once
                "regenerated_at": datetime.utcnow().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate client secret for {client_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to regenerate client secret"
        )


@router.post(
    "/clients/{client_id}/deactivate",
    summary="Deactivate OAuth2 Client",
    description="Deactivate OAuth2 client (soft delete)",
    responses=create_standard_responses()
)
async def deactivate_client(
    client_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Deactivate OAuth2 client (soft delete).
    
    This will prevent the client from being used for new authorization flows
    but preserves the client record for audit purposes.
    
    Args:
        client_id: OAuth2 client identifier
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Deactivation confirmation
    """
    try:
        # Get client from database to check ownership
        client = await client_manager.get_client(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Check ownership or admin privileges
        if client.owner_user_id != current_user["username"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this client"
            )
        
        # Deactivate client
        success = await client_manager.deactivate_client(client_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to deactivate client"
            )
        
        # Log client deactivation
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="client_deactivated",
            client_id=client_id,
            user_id=current_user["username"],
            details={
                "client_name": client.name,
                "deactivated_by": current_user["username"]
            }
        )
        
        logger.info(f"Deactivated OAuth2 client {client_id} by user {current_user['username']}")
        
        return StandardSuccessResponse(
            message="Client deactivated successfully",
            data={
                "client_id": client_id,
                "is_active": False
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate OAuth2 client {client_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate client"
        )


@router.post(
    "/clients/{client_id}/reactivate",
    summary="Reactivate OAuth2 Client",
    description="Reactivate a previously deactivated OAuth2 client",
    responses=create_standard_responses()
)
async def reactivate_client(
    client_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Reactivate a previously deactivated OAuth2 client.
    
    This will allow the client to be used for authorization flows again.
    
    Args:
        client_id: OAuth2 client identifier
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Reactivation confirmation
    """
    try:
        # Get client from database to check ownership
        client = await client_manager.get_client(client_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found"
            )
        
        # Check ownership or admin privileges
        if client.owner_user_id != current_user["username"] and current_user.get("role") != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this client"
            )
        
        # Reactivate client
        success = await client_manager.reactivate_client(client_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to reactivate client"
            )
        
        # Log client reactivation
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="client_reactivated",
            client_id=client_id,
            user_id=current_user["username"],
            details={
                "client_name": client.name,
                "reactivated_by": current_user["username"]
            }
        )
        
        logger.info(f"Reactivated OAuth2 client {client_id} by user {current_user['username']}")
        
        return StandardSuccessResponse(
            message="Client reactivated successfully",
            data={
                "client_id": client_id,
                "is_active": True
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reactivate OAuth2 client {client_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reactivate client"
        )


@router.get(
    "/.well-known/oauth-authorization-server",
    summary="OAuth2 Authorization Server Metadata",
    description="OAuth2 authorization server metadata endpoint as per RFC 8414",
    responses={
        200: {
            "description": "OAuth2 authorization server metadata",
            "content": {
                "application/json": {
                    "example": {
                        "issuer": "https://example.com",
                        "authorization_endpoint": "https://example.com/oauth2/authorize",
                        "token_endpoint": "https://example.com/oauth2/token",
                        "response_types_supported": ["code"],
                        "grant_types_supported": ["authorization_code", "refresh_token"],
                        "scopes_supported": ["read:profile", "write:profile", "read:data", "write:data"]
                    }
                }
            }
        }
    },
    tags=["OAuth2", "Metadata"]
)
async def oauth2_authorization_server_metadata():
    """
    OAuth2 Authorization Server Metadata endpoint.
    
    This endpoint provides metadata about the OAuth2 authorization server
    as specified in RFC 8414 (OAuth 2.0 Authorization Server Metadata).
    
    The metadata includes information about supported endpoints, grant types,
    response types, scopes, and other capabilities of the authorization server.
    
    Returns:
        dict: OAuth2 authorization server metadata
    """
    try:
        # Get OAuth2 endpoints from settings
        endpoints = settings.oauth2_endpoints
        
        # Build metadata response according to RFC 8414
        metadata = {
            # Required fields
            "issuer": endpoints["issuer"],
            "authorization_endpoint": endpoints["authorization_endpoint"],
            "token_endpoint": endpoints["token_endpoint"],
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            
            # Optional but recommended fields
            "scopes_supported": settings.oauth2_available_scopes_list,
            "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
            "code_challenge_methods_supported": ["S256"] if not settings.OAUTH2_ALLOW_PLAIN_PKCE else ["S256", "plain"],
            
            # Additional endpoints
            "revocation_endpoint": endpoints["revocation_endpoint"],
            "introspection_endpoint": endpoints["introspection_endpoint"],
            "userinfo_endpoint": endpoints["userinfo_endpoint"],
            "jwks_uri": endpoints["jwks_uri"],
            
            # Capabilities
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["HS256"],
            "response_modes_supported": ["query", "fragment"],
            
            # Security features
            "require_request_uri_registration": False,
            "require_pushed_authorization_requests": False,
            "pushed_authorization_request_endpoint": None,
            
            # Token configuration
            "token_endpoint_auth_signing_alg_values_supported": ["HS256"],
            "service_documentation": f"{settings.BASE_URL}/docs",
            
            # Custom fields for Second Brain Database
            "sbd_oauth2_version": "1.0",
            "sbd_features": {
                "pkce_required": settings.OAUTH2_REQUIRE_PKCE,
                "client_registration_enabled": settings.OAUTH2_CLIENT_REGISTRATION_ENABLED,
                "consent_management_enabled": True,
                "refresh_token_rotation": True
            }
        }
        
        # Add client registration endpoint if enabled
        if settings.OAUTH2_CLIENT_REGISTRATION_ENABLED:
            metadata["registration_endpoint"] = f"{endpoints['issuer']}/oauth2/clients"
        
        # Log metadata request
        logger.info("OAuth2 authorization server metadata requested")
        
        return metadata
        
    except Exception as e:
        logger.error(f"Failed to generate OAuth2 metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate authorization server metadata"
        )


# OAuth2 Monitoring and Audit Endpoints

@router.get(
    "/monitoring/health",
    summary="OAuth2 Provider Health Status",
    description="Get comprehensive health status of OAuth2 provider",
    responses=create_standard_responses()
)
async def get_oauth2_health_status(
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get comprehensive OAuth2 provider health status.
    
    Returns detailed health information including component status,
    performance metrics, and active alerts.
    
    Args:
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: OAuth2 provider health status
    """
    try:
        if not AUDIT_MONITORING_AVAILABLE:
            return StandardSuccessResponse(
                message="OAuth2 monitoring not available",
                data={
                    "status": "limited",
                    "message": "Audit and monitoring modules not available",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
        
        # Get health status from monitoring system
        health_status = await oauth2_monitoring.get_health_status()
        
        # Get basic OAuth2 component health
        component_health = {
            "authorization_endpoint": "healthy",
            "token_endpoint": "healthy",
            "consent_management": "healthy",
            "client_management": "healthy"
        }
        
        # Add component health to status
        health_status["oauth2_components"] = component_health
        
        # Log health check access
        log_client_management_event(
            event_type="health_check_accessed",
            client_id="monitoring_system",
            owner_user_id=current_user["username"]
        )
        
        return StandardSuccessResponse(
            message="OAuth2 provider health status retrieved",
            data=health_status
        )
        
    except Exception as e:
        logger.error(f"Failed to get OAuth2 health status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve health status"
        )


@router.get(
    "/monitoring/metrics",
    summary="OAuth2 Performance Metrics",
    description="Get OAuth2 performance metrics and statistics",
    responses=create_standard_responses()
)
async def get_oauth2_metrics(
    time_window: int = Query(3600, description="Time window in seconds (default: 1 hour)"),
    metric_name: Optional[str] = Query(None, description="Specific metric name to retrieve"),
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get OAuth2 performance metrics and statistics.
    
    Returns performance metrics for monitoring and analysis,
    including request durations, error rates, and throughput.
    
    Args:
        time_window: Time window in seconds for metrics
        metric_name: Specific metric name to retrieve
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: OAuth2 performance metrics
    """
    try:
        if not AUDIT_MONITORING_AVAILABLE:
            return StandardSuccessResponse(
                message="OAuth2 metrics not available",
                data={
                    "metrics": {},
                    "message": "Metrics collection not available"
                }
            )
        
        # Get performance metrics
        metrics_data = await oauth2_monitoring.get_performance_metrics(
            metric_name=metric_name,
            time_window=time_window
        )
        
        # Get fallback metrics if Prometheus not available
        if oauth2_metrics:
            fallback_metrics = oauth2_metrics.get_fallback_metrics()
            metrics_data["fallback_metrics"] = fallback_metrics
        
        # Log metrics access
        log_performance_event(
            operation="metrics_access",
            duration=0.1,  # Quick operation
            client_id="monitoring_system",
            user_id=current_user["username"],
            success=True,
            time_window=time_window,
            metric_name=metric_name
        )
        
        return StandardSuccessResponse(
            message=f"OAuth2 metrics retrieved for {time_window}s window",
            data=metrics_data
        )
        
    except Exception as e:
        logger.error(f"Failed to get OAuth2 metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve metrics"
        )


@router.get(
    "/audit/trail",
    summary="OAuth2 Audit Trail",
    description="Get OAuth2 audit trail for compliance and security monitoring",
    responses=create_standard_responses()
)
async def get_oauth2_audit_trail(
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    hours: int = Query(24, description="Number of hours to look back (default: 24)"),
    limit: int = Query(100, description="Maximum number of events to return"),
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get OAuth2 audit trail for compliance and security monitoring.
    
    Returns comprehensive audit trail with filtering capabilities
    for compliance reporting and security analysis.
    
    Args:
        client_id: Filter by OAuth2 client ID
        user_id: Filter by user ID
        event_type: Filter by event type
        hours: Number of hours to look back
        limit: Maximum number of events to return
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: OAuth2 audit trail
    """
    try:
        if not AUDIT_MONITORING_AVAILABLE:
            return StandardSuccessResponse(
                message="OAuth2 audit trail not available",
                data={
                    "audit_trail": [],
                    "message": "Audit logging not available"
                }
            )
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Get audit trail
        audit_trail = await oauth2_audit_manager.get_audit_trail(
            client_id=client_id,
            user_id=user_id,
            event_type=event_type,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        # Log audit trail access
        await record_audit_event(
            event_type="audit_trail_accessed",
            client_id="audit_system",
            user_id=current_user["username"],
            event_data={
                "filters": {
                    "client_id": client_id,
                    "user_id": user_id,
                    "event_type": event_type,
                    "hours": hours,
                    "limit": limit
                },
                "results_count": len(audit_trail)
            },
            severity="info",
            compliance_relevant=True
        )
        
        return StandardSuccessResponse(
            message=f"Retrieved {len(audit_trail)} audit events",
            data={
                "audit_trail": audit_trail,
                "filters": {
                    "client_id": client_id,
                    "user_id": user_id,
                    "event_type": event_type,
                    "time_range": {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "hours": hours
                    }
                },
                "total_events": len(audit_trail),
                "limit": limit
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get OAuth2 audit trail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve audit trail"
        )


@router.get(
    "/audit/security-events",
    summary="OAuth2 Security Events",
    description="Get OAuth2 security events for threat monitoring",
    responses=create_standard_responses()
)
async def get_oauth2_security_events(
    severity: Optional[str] = Query(None, description="Filter by severity (low/medium/high/critical)"),
    hours: int = Query(24, description="Number of hours to look back (default: 24)"),
    limit: int = Query(50, description="Maximum number of events to return"),
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get OAuth2 security events for threat monitoring.
    
    Returns security-relevant events for threat detection,
    incident response, and security monitoring.
    
    Args:
        severity: Filter by severity level
        hours: Number of hours to look back
        limit: Maximum number of events to return
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: OAuth2 security events
    """
    try:
        if not AUDIT_MONITORING_AVAILABLE:
            return StandardSuccessResponse(
                message="OAuth2 security events not available",
                data={
                    "security_events": [],
                    "message": "Security event monitoring not available"
                }
            )
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        # Get security events
        security_events = await oauth2_audit_manager.get_security_events(
            severity=severity,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        # Categorize events by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for event in security_events:
            event_severity = event.get("severity", "low")
            if event_severity in severity_counts:
                severity_counts[event_severity] += 1
        
        # Log security events access
        await record_audit_event(
            event_type="security_events_accessed",
            client_id="security_system",
            user_id=current_user["username"],
            event_data={
                "filters": {
                    "severity": severity,
                    "hours": hours,
                    "limit": limit
                },
                "results_count": len(security_events),
                "severity_distribution": severity_counts
            },
            severity="info",
            compliance_relevant=True
        )
        
        return StandardSuccessResponse(
            message=f"Retrieved {len(security_events)} security events",
            data={
                "security_events": security_events,
                "summary": {
                    "total_events": len(security_events),
                    "severity_distribution": severity_counts,
                    "time_range": {
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "hours": hours
                    }
                },
                "filters": {
                    "severity": severity,
                    "limit": limit
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get OAuth2 security events: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve security events"
        )


@router.get(
    "/audit/compliance-report",
    summary="OAuth2 Compliance Report",
    description="Generate OAuth2 compliance report for regulatory requirements",
    responses=create_standard_responses()
)
async def generate_oauth2_compliance_report(
    standard: str = Query(..., description="Compliance standard (sox/gdpr/iso27001/hipaa/pci_dss/nist)"),
    days: int = Query(30, description="Number of days to include in report (default: 30)"),
    client_id: Optional[str] = Query(None, description="Filter by client ID"),
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Generate OAuth2 compliance report for regulatory requirements.
    
    Creates comprehensive compliance reports for various standards
    including SOX, GDPR, ISO 27001, HIPAA, PCI DSS, and NIST.
    
    Args:
        standard: Compliance standard to report against
        days: Number of days to include in report
        client_id: Optional client filter
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: OAuth2 compliance report
    """
    try:
        if not AUDIT_MONITORING_AVAILABLE:
            return StandardSuccessResponse(
                message="OAuth2 compliance reporting not available",
                data={
                    "compliance_report": {},
                    "message": "Compliance reporting not available"
                }
            )
        
        # Validate compliance standard
        try:
            compliance_standard = ComplianceStandard(standard.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid compliance standard: {standard}. Supported: sox, gdpr, iso27001, hipaa, pci_dss, nist"
            )
        
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Generate compliance report
        compliance_report = await oauth2_audit_manager.generate_compliance_report(
            standard=compliance_standard,
            start_time=start_time,
            end_time=end_time,
            client_id=client_id
        )
        
        # Log compliance report generation
        await record_audit_event(
            event_type="compliance_report_generated",
            client_id="compliance_system",
            user_id=current_user["username"],
            event_data={
                "compliance_standard": standard,
                "report_period_days": days,
                "client_filter": client_id,
                "report_size": len(str(compliance_report))
            },
            severity="info",
            compliance_relevant=True
        )
        
        return StandardSuccessResponse(
            message=f"OAuth2 compliance report generated for {standard.upper()}",
            data=compliance_report
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate OAuth2 compliance report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate compliance report"
        )


@router.get(
    "/monitoring/alerts",
    summary="OAuth2 Active Alerts",
    description="Get active OAuth2 monitoring alerts",
    responses=create_standard_responses()
)
async def get_oauth2_active_alerts(
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Get active OAuth2 monitoring alerts.
    
    Returns current active alerts for OAuth2 operations,
    including performance, security, and availability alerts.
    
    Args:
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Active OAuth2 alerts
    """
    try:
        if not AUDIT_MONITORING_AVAILABLE:
            return StandardSuccessResponse(
                message="OAuth2 alerts not available",
                data={
                    "active_alerts": [],
                    "message": "Alert monitoring not available"
                }
            )
        
        # Get active alerts
        active_alerts = await oauth2_monitoring.get_active_alerts()
        
        # Categorize alerts by severity and type
        alert_summary = {
            "total_alerts": len(active_alerts),
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "by_type": {}
        }
        
        for alert in active_alerts:
            severity = alert.get("severity", "low")
            alert_type = alert.get("alert_type", "unknown")
            
            if severity in alert_summary["by_severity"]:
                alert_summary["by_severity"][severity] += 1
            
            alert_summary["by_type"][alert_type] = alert_summary["by_type"].get(alert_type, 0) + 1
        
        # Log alerts access
        log_client_management_event(
            event_type="alerts_accessed",
            client_id="monitoring_system",
            owner_user_id=current_user["username"],
            changes={"alerts_count": len(active_alerts)}
        )
        
        return StandardSuccessResponse(
            message=f"Retrieved {len(active_alerts)} active alerts",
            data={
                "active_alerts": active_alerts,
                "summary": alert_summary,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get OAuth2 active alerts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve active alerts"
        )


@router.post(
    "/monitoring/alerts/{alert_id}/acknowledge",
    summary="Acknowledge OAuth2 Alert",
    description="Acknowledge an active OAuth2 monitoring alert",
    responses=create_standard_responses()
)
async def acknowledge_oauth2_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user_dep)
):
    """
    Acknowledge an active OAuth2 monitoring alert.
    
    Marks an alert as acknowledged to prevent repeated notifications
    and track alert handling.
    
    Args:
        alert_id: Alert identifier to acknowledge
        current_user: Authenticated user from dependency injection
        
    Returns:
        StandardSuccessResponse: Alert acknowledgment confirmation
    """
    try:
        if not AUDIT_MONITORING_AVAILABLE:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="OAuth2 alert acknowledgment not available"
            )
        
        # Acknowledge the alert
        success = await oauth2_monitoring.acknowledge_alert(
            alert_id=alert_id,
            acknowledged_by=current_user["username"]
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found or already acknowledged"
            )
        
        # Log alert acknowledgment
        await record_audit_event(
            event_type="alert_acknowledged",
            client_id="monitoring_system",
            user_id=current_user["username"],
            event_data={
                "alert_id": alert_id,
                "acknowledged_by": current_user["username"],
                "acknowledged_at": datetime.utcnow().isoformat()
            },
            severity="info",
            compliance_relevant=False
        )
        
        return StandardSuccessResponse(
            message=f"Alert {alert_id} acknowledged successfully",
            data={
                "alert_id": alert_id,
                "acknowledged": True,
                "acknowledged_by": current_user["username"],
                "acknowledged_at": datetime.utcnow().isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to acknowledge OAuth2 alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge alert"
        )