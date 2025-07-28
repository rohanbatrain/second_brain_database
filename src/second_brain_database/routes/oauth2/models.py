"""
OAuth2 provider data models.

This module defines all data models for the OAuth2 authorization server implementation,
including client applications, authorization codes, user consents, and token responses.
"""

import secrets
import string
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from second_brain_database.docs.models import BaseDocumentedModel
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[OAuth2 Models]")


class ClientType(str, Enum):
    """OAuth2 client types as defined in RFC 6749."""
    
    CONFIDENTIAL = "confidential"  # Can securely store credentials (server-side apps)
    PUBLIC = "public"  # Cannot securely store credentials (mobile/SPA apps)


class GrantType(str, Enum):
    """Supported OAuth2 grant types."""
    
    AUTHORIZATION_CODE = "authorization_code"
    REFRESH_TOKEN = "refresh_token"


class ResponseType(str, Enum):
    """Supported OAuth2 response types."""
    
    CODE = "code"


class TokenType(str, Enum):
    """OAuth2 token types."""
    
    BEARER = "Bearer"


class PKCEMethod(str, Enum):
    """PKCE code challenge methods."""
    
    PLAIN = "plain"
    S256 = "S256"


# OAuth2 Client Models

class OAuthClientRegistration(BaseDocumentedModel):
    """
    OAuth2 client application registration request.
    
    Used when registering a new OAuth2 client application with the authorization server.
    """
    
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Human-readable name of the client application",
        example="My Web Application"
    )
    
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional description of the client application",
        example="A web application for managing user data"
    )
    
    redirect_uris: List[str] = Field(
        ...,
        min_length=1,
        description="List of allowed redirect URIs for this client",
        example=["https://myapp.com/oauth/callback", "https://myapp.com/auth/callback"]
    )
    
    client_type: ClientType = Field(
        ...,
        description="Type of OAuth2 client (confidential or public)",
        example=ClientType.CONFIDENTIAL
    )
    
    scopes: List[str] = Field(
        default_factory=lambda: ["read:profile"],
        description="List of scopes this client is allowed to request",
        example=["read:profile", "write:data"]
    )
    
    website_url: Optional[str] = Field(
        None,
        description="Optional website URL for the client application",
        example="https://myapp.com"
    )
    
    @field_validator("redirect_uris")
    @classmethod
    def validate_redirect_uris(cls, v: List[str]) -> List[str]:
        """Validate redirect URIs are properly formatted."""
        for uri in v:
            if not uri.startswith(("https://", "http://localhost", "http://127.0.0.1")):
                raise ValueError(f"Invalid redirect URI: {uri}. Must use HTTPS or localhost")
        return v
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "My Web Application",
                "description": "A web application for managing user data",
                "redirect_uris": ["https://myapp.com/oauth/callback"],
                "client_type": "confidential",
                "scopes": ["read:profile", "write:data"],
                "website_url": "https://myapp.com"
            }
        }
    }


class OAuthClientResponse(BaseDocumentedModel):
    """
    OAuth2 client registration response.
    
    Contains the client credentials and metadata after successful registration.
    """
    
    client_id: str = Field(
        ...,
        description="Unique client identifier",
        example="oauth2_client_1234567890abcdef"
    )
    
    client_secret: Optional[str] = Field(
        None,
        description="Client secret (only for confidential clients, only shown once)",
        example="cs_1234567890abcdef1234567890abcdef"
    )
    
    name: str = Field(
        ...,
        description="Human-readable name of the client application",
        example="My Web Application"
    )
    
    client_type: ClientType = Field(
        ...,
        description="Type of OAuth2 client",
        example=ClientType.CONFIDENTIAL
    )
    
    redirect_uris: List[str] = Field(
        ...,
        description="Allowed redirect URIs for this client",
        example=["https://myapp.com/oauth/callback"]
    )
    
    scopes: List[str] = Field(
        ...,
        description="Allowed scopes for this client",
        example=["read:profile", "write:data"]
    )
    
    created_at: datetime = Field(
        ...,
        description="UTC timestamp when the client was registered",
        example="2024-01-01T12:00:00Z"
    )
    
    is_active: bool = Field(
        default=True,
        description="Whether the client is active and can be used",
        example=True
    )
    
    model_config = {
        "json_schema_extra": {
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


class OAuthClient(BaseModel):
    """
    OAuth2 client database document model.
    
    Represents the complete client document stored in MongoDB.
    """
    
    client_id: str = Field(..., description="Unique client identifier")
    client_secret_hash: Optional[str] = Field(None, description="Hashed client secret (for confidential clients)")
    name: str = Field(..., description="Human-readable client name")
    description: Optional[str] = Field(None, description="Client description")
    client_type: ClientType = Field(..., description="Client type")
    redirect_uris: List[str] = Field(..., description="Allowed redirect URIs")
    scopes: List[str] = Field(..., description="Allowed scopes")
    website_url: Optional[str] = Field(None, description="Client website URL")
    owner_user_id: Optional[str] = Field(None, description="User who registered this client")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    is_active: bool = Field(default=True, description="Whether client is active")


# Authorization Code Models

class AuthorizationRequest(BaseDocumentedModel):
    """
    OAuth2 authorization request parameters.
    
    Used for the initial authorization request to /oauth2/authorize endpoint.
    """
    
    response_type: ResponseType = Field(
        ...,
        description="OAuth2 response type, must be 'code'",
        example=ResponseType.CODE
    )
    
    client_id: str = Field(
        ...,
        description="Client identifier",
        example="oauth2_client_1234567890abcdef"
    )
    
    redirect_uri: str = Field(
        ...,
        description="Redirect URI where the authorization code will be sent",
        example="https://myapp.com/oauth/callback"
    )
    
    scope: str = Field(
        ...,
        description="Space-separated list of requested scopes",
        example="read:profile write:data"
    )
    
    state: str = Field(
        ...,
        description="Client state parameter for CSRF protection",
        example="random_state_string_12345"
    )
    
    code_challenge: str = Field(
        ...,
        description="PKCE code challenge",
        example="dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    )
    
    code_challenge_method: PKCEMethod = Field(
        default=PKCEMethod.S256,
        description="PKCE code challenge method",
        example=PKCEMethod.S256
    )


class AuthorizationCode(BaseModel):
    """
    OAuth2 authorization code database document.
    
    Represents an authorization code stored in Redis with expiration.
    """
    
    code: str = Field(..., description="Authorization code")
    client_id: str = Field(..., description="Client that requested the code")
    user_id: str = Field(..., description="User who authorized the code")
    redirect_uri: str = Field(..., description="Redirect URI used in authorization")
    scopes: List[str] = Field(..., description="Granted scopes")
    code_challenge: str = Field(..., description="PKCE code challenge")
    code_challenge_method: PKCEMethod = Field(..., description="PKCE challenge method")
    expires_at: datetime = Field(..., description="Code expiration time")
    used: bool = Field(default=False, description="Whether code has been used")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")


# Token Models

class TokenRequest(BaseDocumentedModel):
    """
    OAuth2 token request for authorization code exchange.
    
    Used at the /oauth2/token endpoint to exchange authorization code for tokens.
    """
    
    grant_type: GrantType = Field(
        ...,
        description="OAuth2 grant type",
        example=GrantType.AUTHORIZATION_CODE
    )
    
    code: Optional[str] = Field(
        None,
        description="Authorization code (required for authorization_code grant)",
        example="auth_code_1234567890abcdef"
    )
    
    redirect_uri: Optional[str] = Field(
        None,
        description="Redirect URI (must match the one used in authorization)",
        example="https://myapp.com/oauth/callback"
    )
    
    client_id: str = Field(
        ...,
        description="Client identifier",
        example="oauth2_client_1234567890abcdef"
    )
    
    client_secret: Optional[str] = Field(
        None,
        description="Client secret (required for confidential clients)",
        example="cs_1234567890abcdef1234567890abcdef"
    )
    
    code_verifier: Optional[str] = Field(
        None,
        description="PKCE code verifier",
        example="dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
    )
    
    refresh_token: Optional[str] = Field(
        None,
        description="Refresh token (for refresh_token grant)",
        example="rt_1234567890abcdef1234567890abcdef"
    )


class TokenResponse(BaseDocumentedModel):
    """
    OAuth2 token response.
    
    Contains access token, refresh token, and metadata returned after successful token exchange.
    """
    
    access_token: str = Field(
        ...,
        description="JWT access token for API authentication",
        example="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImF1ZCI6Im9hdXRoMl9jbGllbnRfMTIzNCIsInNjb3BlIjoicmVhZDpwcm9maWxlIn0.signature"
    )
    
    token_type: TokenType = Field(
        default=TokenType.BEARER,
        description="Token type, always 'Bearer'",
        example=TokenType.BEARER
    )
    
    expires_in: int = Field(
        ...,
        description="Access token lifetime in seconds",
        example=3600
    )
    
    refresh_token: Optional[str] = Field(
        None,
        description="Refresh token for obtaining new access tokens",
        example="rt_1234567890abcdef1234567890abcdef"
    )
    
    scope: str = Field(
        ...,
        description="Space-separated list of granted scopes",
        example="read:profile write:data"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJqb2huX2RvZSIsImF1ZCI6Im9hdXRoMl9jbGllbnRfMTIzNCIsInNjb3BlIjoicmVhZDpwcm9maWxlIn0.signature",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "rt_1234567890abcdef1234567890abcdef",
                "scope": "read:profile write:data"
            }
        }
    }


# User Consent Models

class ConsentRequest(BaseDocumentedModel):
    """
    User consent request for OAuth2 authorization.
    
    Used when user grants or denies consent for client application access.
    """
    
    client_id: str = Field(
        ...,
        description="Client identifier requesting access",
        example="oauth2_client_1234567890abcdef"
    )
    
    scopes: List[str] = Field(
        ...,
        description="List of scopes being requested",
        example=["read:profile", "write:data"]
    )
    
    approved: bool = Field(
        ...,
        description="Whether user approved the consent request",
        example=True
    )
    
    state: str = Field(
        ...,
        description="Client state parameter",
        example="random_state_string_12345"
    )


class UserConsent(BaseModel):
    """
    User consent database document.
    
    Represents user consent for client application access stored in MongoDB.
    """
    
    user_id: str = Field(..., description="User who granted consent")
    client_id: str = Field(..., description="Client that received consent")
    scopes: List[str] = Field(..., description="Granted scopes")
    granted_at: datetime = Field(default_factory=datetime.utcnow, description="When consent was granted")
    last_used_at: Optional[datetime] = Field(None, description="When consent was last used")
    is_active: bool = Field(default=True, description="Whether consent is still active")


class ConsentInfo(BaseDocumentedModel):
    """
    User consent information for display.
    
    Used to show user what permissions are being requested by a client application.
    """
    
    client_name: str = Field(
        ...,
        description="Human-readable name of the client application",
        example="My Web Application"
    )
    
    client_description: Optional[str] = Field(
        None,
        description="Description of the client application",
        example="A web application for managing user data"
    )
    
    website_url: Optional[str] = Field(
        None,
        description="Client application website URL",
        example="https://myapp.com"
    )
    
    requested_scopes: List[Dict[str, str]] = Field(
        ...,
        description="List of requested scopes with descriptions",
        example=[
            {"scope": "read:profile", "description": "Read your profile information"},
            {"scope": "write:data", "description": "Modify your data"}
        ]
    )
    
    existing_consent: bool = Field(
        default=False,
        description="Whether user has previously granted consent to this client",
        example=False
    )


# Refresh Token Models

class RefreshTokenData(BaseModel):
    """
    Refresh token data stored in Redis.
    
    Contains metadata about the refresh token for validation and rotation.
    """
    
    token_hash: str = Field(..., description="SHA-256 hash of the refresh token")
    client_id: str = Field(..., description="Client that owns this refresh token")
    user_id: str = Field(..., description="User associated with this refresh token")
    scopes: List[str] = Field(..., description="Granted scopes")
    expires_at: datetime = Field(..., description="Token expiration time")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    is_active: bool = Field(default=True, description="Whether token is active")


# OAuth2 Error Models

class OAuth2Error(BaseDocumentedModel):
    """
    OAuth2 error response following RFC 6749.
    
    Standard error response format for OAuth2 authorization and token endpoints.
    """
    
    error: str = Field(
        ...,
        description="OAuth2 error code",
        example="invalid_request"
    )
    
    error_description: Optional[str] = Field(
        None,
        description="Human-readable error description",
        example="The request is missing a required parameter"
    )
    
    error_uri: Optional[str] = Field(
        None,
        description="URI for additional error information",
        example="https://docs.example.com/oauth2/errors#invalid_request"
    )
    
    state: Optional[str] = Field(
        None,
        description="Client state parameter (if provided in request)",
        example="random_state_string_12345"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "invalid_request",
                "error_description": "The request is missing a required parameter",
                "error_uri": "https://docs.example.com/oauth2/errors#invalid_request",
                "state": "random_state_string_12345"
            }
        }
    }


# Utility Functions

def generate_client_id() -> str:
    """Generate a secure client ID."""
    return f"oauth2_client_{''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(24))}"


def generate_client_secret() -> str:
    """Generate a secure client secret."""
    return f"cs_{''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))}"


def generate_authorization_code() -> str:
    """Generate a secure authorization code."""
    return f"auth_code_{''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))}"


def generate_refresh_token() -> str:
    """Generate a secure refresh token."""
    return f"rt_{''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))}"


# Scope Definitions

AVAILABLE_SCOPES = {
    "read:profile": "Read your profile information (username, email, basic details)",
    "write:profile": "Update your profile information",
    "read:data": "Read your stored data and documents",
    "write:data": "Create, update, and delete your data and documents",
    "read:tokens": "View your API tokens and their usage",
    "write:tokens": "Create and manage your API tokens",
    "admin": "Administrative access (restricted to admin users)"
}


def validate_scopes(requested_scopes: List[str]) -> List[str]:
    """
    Validate and filter requested scopes.
    
    Args:
        requested_scopes: List of requested scope strings
        
    Returns:
        List of valid scopes
        
    Raises:
        ValueError: If any scope is invalid
    """
    valid_scopes = []
    for scope in requested_scopes:
        if scope not in AVAILABLE_SCOPES:
            raise ValueError(f"Invalid scope: {scope}")
        valid_scopes.append(scope)
    return valid_scopes


def get_scope_descriptions(scopes: List[str]) -> List[Dict[str, str]]:
    """
    Get scope descriptions for display to user.
    
    Args:
        scopes: List of scope strings
        
    Returns:
        List of dictionaries with scope and description
    """
    return [
        {"scope": scope, "description": AVAILABLE_SCOPES.get(scope, "Unknown scope")}
        for scope in scopes
    ]