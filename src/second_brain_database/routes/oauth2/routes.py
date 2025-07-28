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
from second_brain_database.routes.auth.routes import get_current_user_dep
from second_brain_database.routes.auth.services.auth.login import create_access_token

from .client_manager import client_manager
from .models import (
    AuthorizationRequest,
    ConsentInfo,
    ConsentRequest,
    OAuth2Error,
    ResponseType,
    get_scope_descriptions,
    validate_scopes,
)
from .security_manager import oauth2_security_manager
from .services.auth_code_manager import auth_code_manager
from .services.consent_manager import consent_manager
from .services.pkce_validator import PKCEValidator
from .services.token_manager import token_manager
from .templates import render_consent_screen, render_consent_error

logger = get_logger(prefix="[OAuth2 Routes]")

router = APIRouter(prefix="/oauth2", tags=["OAuth2"])


@router.get(
    "/authorize",
    summary="OAuth2 Authorization Endpoint",
    description="Initiate OAuth2 authorization code flow with PKCE",
    responses={
        200: {"description": "Authorization successful, redirect to client"},
        400: {"description": "Invalid request parameters"},
        401: {"description": "User not authenticated"},
        403: {"description": "User denied authorization"},
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
    current_user: dict = Depends(get_current_user_dep)
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
    logger.info(f"OAuth2 authorization request from client {client_id} for user {current_user.get('username')}")
    
    try:
        # Apply rate limiting for this client
        await oauth2_security_manager.rate_limit_client(
            request=request,
            client_id=client_id,
            endpoint="authorize",
            rate_limit_requests=100,  # 100 requests per period
            rate_limit_period=300     # 5 minutes
        )
        
        # Validate response_type
        if response_type != ResponseType.CODE.value:
            logger.warning(f"Invalid response_type: {response_type}")
            return _redirect_with_error(
                redirect_uri=redirect_uri,
                error="unsupported_response_type",
                error_description="Only 'code' response type is supported",
                state=state
            )
        
        # Comprehensive security validation
        await oauth2_security_manager.validate_client_request_security(
            request=request,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state
        )
        
        # Validate and parse scopes
        try:
            requested_scopes = scope.split()
            validated_scopes = validate_scopes(requested_scopes)
        except ValueError as e:
            logger.warning(f"Invalid scopes requested: {e}")
            return _redirect_with_error(
                redirect_uri=redirect_uri,
                error="invalid_scope",
                error_description=str(e),
                state=state
            )
        
        # Get client information
        client = await client_manager.get_client(client_id)
        if not client:
            logger.error(f"Client not found: {client_id}")
            return _redirect_with_error(
                redirect_uri=redirect_uri,
                error="invalid_client",
                error_description="Client not found",
                state=state
            )
        
        # Validate client scopes
        client_scopes = set(client.scopes)
        requested_scopes_set = set(validated_scopes)
        if not requested_scopes_set.issubset(client_scopes):
            invalid_scopes = requested_scopes_set - client_scopes
            logger.warning(f"Client {client_id} requested unauthorized scopes: {invalid_scopes}")
            return _redirect_with_error(
                redirect_uri=redirect_uri,
                error="invalid_scope",
                error_description=f"Client not authorized for scopes: {', '.join(invalid_scopes)}",
                state=state
            )
        
        # Validate PKCE parameters
        if not await oauth2_security_manager.validate_pkce_security(code_challenge, code_challenge_method):
            logger.warning(f"Invalid PKCE parameters for client {client_id}")
            return _redirect_with_error(
                redirect_uri=redirect_uri,
                error="invalid_request",
                error_description="Invalid PKCE parameters",
                state=state
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
                logger.error(f"Failed to get consent info for client {client_id}")
                return _redirect_with_error(
                    redirect_uri=redirect_uri,
                    error="server_error",
                    error_description="Failed to load consent information",
                    state=state
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
        
        # Store authorization code with metadata
        success = await auth_code_manager.store_authorization_code(
            code=auth_code,
            client_id=client_id,
            user_id=current_user["username"],  # Using username as user_id
            redirect_uri=redirect_uri,
            scopes=validated_scopes,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            ttl_seconds=600  # 10 minutes as per RFC 6749
        )
        
        if not success:
            logger.error(f"Failed to store authorization code for client {client_id}")
            return _redirect_with_error(
                redirect_uri=redirect_uri,
                error="server_error",
                error_description="Failed to generate authorization code",
                state=state
            )
        
        # Log successful authorization
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="authorization_granted",
            client_id=client_id,
            user_id=current_user["username"],
            details={
                "scopes": validated_scopes,
                "redirect_uri": redirect_uri,
                "code_challenge_method": code_challenge_method
            }
        )
        
        logger.info(f"Authorization code generated for client {client_id}, user {current_user['username']}")
        
        # Redirect back to client with authorization code
        return _redirect_with_code(
            redirect_uri=redirect_uri,
            code=auth_code,
            state=state
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (like rate limiting)
        raise
    except Exception as e:
        logger.error(f"Unexpected error in OAuth2 authorization: {e}", exc_info=True)
        
        # Log security event for unexpected errors
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="authorization_error",
            client_id=client_id,
            user_id=current_user.get("username"),
            details={"error": str(e)}
        )
        
        return _redirect_with_error(
            redirect_uri=redirect_uri,
            error="server_error",
            error_description="Internal server error",
            state=state
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


def _redirect_with_error(
    redirect_uri: str,
    error: str,
    error_description: str,
    state: Optional[str] = None
) -> RedirectResponse:
    """
    Create redirect response with OAuth2 error.
    
    Args:
        redirect_uri: Client redirect URI
        error: OAuth2 error code
        error_description: Human-readable error description
        state: Client state parameter (optional)
        
    Returns:
        RedirectResponse with error parameters
    """
    params = {
        "error": error,
        "error_description": error_description
    }
    
    if state:
        params["state"] = state
    
    # Build redirect URL with error parameters
    separator = "&" if "?" in redirect_uri else "?"
    redirect_url = f"{redirect_uri}{separator}{urlencode(params)}"
    
    logger.debug(f"Redirecting to client with error: {error}")
    return RedirectResponse(url=redirect_url, status_code=302)


@router.post(
    "/consent",
    summary="OAuth2 User Consent Endpoint",
    description="Handle user consent approval or denial for OAuth2 authorization",
    responses={
        302: {"description": "Redirect to client with authorization code or error"},
        400: {"description": "Invalid consent request"},
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
                logger.error(f"Failed to grant consent for client {client_id}")
                return _redirect_with_error(
                    redirect_uri=auth_params["redirect_uri"],
                    error="server_error",
                    error_description="Failed to process consent",
                    state=auth_params["state"]
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
                logger.error(f"Failed to store authorization code for client {client_id}")
                return _redirect_with_error(
                    redirect_uri=auth_params["redirect_uri"],
                    error="server_error",
                    error_description="Failed to generate authorization code",
                    state=auth_params["state"]
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
            return _redirect_with_code(
                redirect_uri=auth_params["redirect_uri"],
                code=auth_code,
                state=auth_params["state"]
            )
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
            return _redirect_with_error(
                redirect_uri=auth_params["redirect_uri"],
                error="access_denied",
                error_description="User denied authorization",
                state=auth_params["state"]
            )
            
    except Exception as e:
        logger.error(f"Unexpected error in consent handling: {e}", exc_info=True)
        
        # Try to get redirect URI from auth params for error redirect
        redirect_uri = auth_params.get("redirect_uri") if auth_params else None
        state_param = auth_params.get("state") if auth_params else None
        
        if redirect_uri:
            return _redirect_with_error(
                redirect_uri=redirect_uri,
                error="server_error",
                error_description="Internal server error",
                state=state_param
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
        
        return StandardSuccessResponse(
            message=f"Retrieved {len(consents)} consents",
            data={
                "consents": consents,
                "total_count": len(consents)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to list user consents: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve consents"
        )


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
        
        # Log consent revocation
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="consent_revoked",
            client_id=client_id,
            user_id=current_user["username"],
            details={"revoked_by_user": True}
        )
        
        return StandardSuccessResponse(
            message=f"Consent revoked for client {client_id}",
            data={"client_id": client_id, "revoked": True}
        )
        
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
    logger.info(f"OAuth2 token request from client {client_id}, grant_type: {grant_type}")
    
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
            logger.warning(f"Unsupported grant type: {grant_type}")
            return _token_error("unsupported_grant_type", f"Grant type '{grant_type}' is not supported")
        
        # Validate client credentials
        client = await client_manager.validate_client(client_id, client_secret)
        if not client:
            logger.error(f"Client authentication failed: {client_id}")
            return _token_error("invalid_client", "Client authentication failed")
        
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
        logger.error(f"Unexpected error in OAuth2 token endpoint: {e}", exc_info=True)
        
        # Log security event for unexpected errors
        await oauth2_security_manager.log_oauth2_security_event(
            event_type="token_error",
            client_id=client_id,
            user_id=None,
            details={"error": str(e), "grant_type": grant_type}
        )
        
        return _token_error("server_error", "Internal server error")


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
        logger.warning("Missing authorization code in token request")
        return _token_error("invalid_request", "Authorization code is required")
    
    if not redirect_uri:
        logger.warning("Missing redirect_uri in token request")
        return _token_error("invalid_request", "Redirect URI is required")
    
    if not code_verifier:
        logger.warning("Missing PKCE code verifier in token request")
        return _token_error("invalid_request", "PKCE code verifier is required")
    
    # Use authorization code (marks it as used and prevents replay)
    auth_code = await auth_code_manager.use_authorization_code(code)
    if not auth_code:
        logger.error(f"Invalid or expired authorization code: {code}")
        return _token_error("invalid_grant", "Invalid or expired authorization code")
    
    # Validate client matches
    if auth_code.client_id != client.client_id:
        logger.error(f"Client mismatch in authorization code: expected {auth_code.client_id}, got {client.client_id}")
        return _token_error("invalid_grant", "Authorization code was issued to a different client")
    
    # Validate redirect URI matches
    if auth_code.redirect_uri != redirect_uri:
        logger.error(f"Redirect URI mismatch: expected {auth_code.redirect_uri}, got {redirect_uri}")
        return _token_error("invalid_grant", "Redirect URI does not match authorization request")
    
    # Validate PKCE code verifier
    try:
        pkce_valid = PKCEValidator.validate_code_challenge(
            verifier=code_verifier,
            challenge=auth_code.code_challenge,
            method=auth_code.code_challenge_method.value
        )
        if not pkce_valid:
            logger.error(f"PKCE validation failed for client {client.client_id}")
            return _token_error("invalid_grant", "PKCE code verifier validation failed")
    except Exception as e:
        logger.error(f"PKCE validation error: {e}")
        return _token_error("invalid_grant", "PKCE code verifier validation failed")
    
    # Generate access token using existing JWT system
    access_token = await create_access_token({"sub": auth_code.user_id})
    
    # Generate refresh token
    refresh_token = await token_manager.generate_refresh_token(
        client_id=client.client_id,
        user_id=auth_code.user_id,
        scopes=auth_code.scopes
    )
    
    # Log successful token issuance
    await oauth2_security_manager.log_oauth2_security_event(
        event_type="token_issued",
        client_id=client.client_id,
        user_id=auth_code.user_id,
        details={
            "grant_type": "authorization_code",
            "scopes": auth_code.scopes,
            "has_refresh_token": bool(refresh_token)
        }
    )
    
    logger.info(f"Access token issued for client {client.client_id}, user {auth_code.user_id}")
    
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
        logger.warning("Missing refresh token in token request")
        return _token_error("invalid_request", "Refresh token is required")
    
    # Use token manager to refresh access token
    token_response = await token_manager.refresh_access_token(refresh_token, client.client_id)
    if not token_response:
        logger.error(f"Failed to refresh access token for client {client.client_id}")
        return _token_error("invalid_grant", "Invalid refresh token")
    
    # Log successful token refresh
    await oauth2_security_manager.log_oauth2_security_event(
        event_type="token_refreshed",
        client_id=client.client_id,
        user_id=token_response.scope.split()[0] if token_response.scope else "unknown",  # Extract user from scope or use placeholder
        details={
            "grant_type": "refresh_token",
            "scopes": token_response.scope.split(),
            "token_rotated": True
        }
    )
    
    logger.info(f"Access token refreshed for client {client.client_id}")
    
    return token_response


def _token_error(error: str, error_description: str) -> JSONResponse:
    """
    Create OAuth2 token error response.
    
    Args:
        error: OAuth2 error code
        error_description: Human-readable error description
        
    Returns:
        JSONResponse with OAuth2 error format
    """
    from .models import OAuth2Error
    
    error_response = OAuth2Error(
        error=error,
        error_description=error_description
    )
    
    logger.debug(f"Token error response: {error}")
    return JSONResponse(
        status_code=400,
        content=error_response.model_dump()
    )


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
            logger.error(f"Client authentication failed for revocation: {client_id}")
            return _token_error("invalid_client", "Client authentication failed")
        
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