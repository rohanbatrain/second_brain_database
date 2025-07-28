"""
Unit tests for OAuth2 data models.

Tests validation, serialization, and utility functions for OAuth2 provider models.
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from src.second_brain_database.routes.oauth2.models import (
    ClientType,
    GrantType,
    ResponseType,
    TokenType,
    PKCEMethod,
    OAuthClientRegistration,
    OAuthClientResponse,
    OAuthClient,
    AuthorizationRequest,
    AuthorizationCode,
    TokenRequest,
    TokenResponse,
    ConsentRequest,
    UserConsent,
    ConsentInfo,
    RefreshTokenData,
    OAuth2Error,
    generate_client_id,
    generate_client_secret,
    generate_authorization_code,
    generate_refresh_token,
    validate_scopes,
    get_scope_descriptions,
    AVAILABLE_SCOPES
)


class TestOAuth2Models:
    """Test OAuth2 data models."""
    
    def test_client_registration_valid(self):
        """Test valid OAuth2 client registration."""
        registration = OAuthClientRegistration(
            name="Test App",
            description="A test application",
            redirect_uris=["https://example.com/callback"],
            client_type=ClientType.CONFIDENTIAL,
            scopes=["read:profile", "write:data"],
            website_url="https://example.com"
        )
        
        assert registration.name == "Test App"
        assert registration.client_type == ClientType.CONFIDENTIAL
        assert len(registration.redirect_uris) == 1
        assert "read:profile" in registration.scopes
    
    def test_client_registration_invalid_redirect_uri(self):
        """Test OAuth2 client registration with invalid redirect URI."""
        with pytest.raises(ValidationError) as exc_info:
            OAuthClientRegistration(
                name="Test App",
                redirect_uris=["http://example.com/callback"],  # HTTP not allowed
                client_type=ClientType.CONFIDENTIAL
            )
        
        assert "Invalid redirect URI" in str(exc_info.value)
    
    def test_client_registration_localhost_allowed(self):
        """Test OAuth2 client registration allows localhost."""
        registration = OAuthClientRegistration(
            name="Test App",
            redirect_uris=["http://localhost:3000/callback", "http://127.0.0.1:8080/callback"],
            client_type=ClientType.PUBLIC
        )
        
        assert len(registration.redirect_uris) == 2
    
    def test_oauth_client_response(self):
        """Test OAuth2 client response model."""
        response = OAuthClientResponse(
            client_id="oauth2_client_123",
            client_secret="cs_secret123",
            name="Test App",
            client_type=ClientType.CONFIDENTIAL,
            redirect_uris=["https://example.com/callback"],
            scopes=["read:profile"],
            created_at=datetime.utcnow()
        )
        
        assert response.client_id.startswith("oauth2_client_")
        assert response.client_secret.startswith("cs_")
        assert response.is_active is True
    
    def test_oauth_client_database_model(self):
        """Test OAuth2 client database model."""
        client = OAuthClient(
            client_id="oauth2_client_123",
            client_secret_hash="hashed_secret",
            name="Test App",
            client_type=ClientType.CONFIDENTIAL,
            redirect_uris=["https://example.com/callback"],
            scopes=["read:profile"]
        )
        
        assert client.is_active is True
        assert client.created_at is not None
        assert client.updated_at is not None
    
    def test_authorization_request(self):
        """Test OAuth2 authorization request model."""
        request = AuthorizationRequest(
            response_type=ResponseType.CODE,
            client_id="oauth2_client_123",
            redirect_uri="https://example.com/callback",
            scope="read:profile write:data",
            state="random_state_123",
            code_challenge="challenge123",
            code_challenge_method=PKCEMethod.S256
        )
        
        assert request.response_type == ResponseType.CODE
        assert request.code_challenge_method == PKCEMethod.S256
    
    def test_authorization_code(self):
        """Test authorization code model."""
        expires_at = datetime.utcnow() + timedelta(minutes=10)
        
        auth_code = AuthorizationCode(
            code="auth_code_123",
            client_id="oauth2_client_123",
            user_id="user_123",
            redirect_uri="https://example.com/callback",
            scopes=["read:profile"],
            code_challenge="challenge123",
            code_challenge_method=PKCEMethod.S256,
            expires_at=expires_at
        )
        
        assert auth_code.used is False
        assert auth_code.expires_at == expires_at
        assert auth_code.created_at is not None
    
    def test_token_request_authorization_code(self):
        """Test token request for authorization code grant."""
        request = TokenRequest(
            grant_type=GrantType.AUTHORIZATION_CODE,
            code="auth_code_123",
            redirect_uri="https://example.com/callback",
            client_id="oauth2_client_123",
            client_secret="cs_secret123",
            code_verifier="verifier123"
        )
        
        assert request.grant_type == GrantType.AUTHORIZATION_CODE
        assert request.code == "auth_code_123"
    
    def test_token_request_refresh_token(self):
        """Test token request for refresh token grant."""
        request = TokenRequest(
            grant_type=GrantType.REFRESH_TOKEN,
            client_id="oauth2_client_123",
            client_secret="cs_secret123",
            refresh_token="rt_refresh123"
        )
        
        assert request.grant_type == GrantType.REFRESH_TOKEN
        assert request.refresh_token == "rt_refresh123"
    
    def test_token_response(self):
        """Test OAuth2 token response model."""
        response = TokenResponse(
            access_token="jwt_token_123",
            expires_in=3600,
            refresh_token="rt_refresh123",
            scope="read:profile write:data"
        )
        
        assert response.token_type == TokenType.BEARER
        assert response.expires_in == 3600
        assert "read:profile" in response.scope
    
    def test_consent_request(self):
        """Test user consent request model."""
        request = ConsentRequest(
            client_id="oauth2_client_123",
            scopes=["read:profile", "write:data"],
            approved=True,
            state="random_state_123"
        )
        
        assert request.approved is True
        assert len(request.scopes) == 2
    
    def test_user_consent(self):
        """Test user consent database model."""
        consent = UserConsent(
            user_id="user_123",
            client_id="oauth2_client_123",
            scopes=["read:profile"]
        )
        
        assert consent.is_active is True
        assert consent.granted_at is not None
        assert consent.last_used_at is None
    
    def test_consent_info(self):
        """Test consent information model."""
        info = ConsentInfo(
            client_name="Test App",
            client_description="A test application",
            website_url="https://example.com",
            requested_scopes=[
                {"scope": "read:profile", "description": "Read your profile"},
                {"scope": "write:data", "description": "Modify your data"}
            ]
        )
        
        assert info.existing_consent is False
        assert len(info.requested_scopes) == 2
    
    def test_refresh_token_data(self):
        """Test refresh token data model."""
        expires_at = datetime.utcnow() + timedelta(days=30)
        
        token_data = RefreshTokenData(
            token_hash="hashed_token",
            client_id="oauth2_client_123",
            user_id="user_123",
            scopes=["read:profile"],
            expires_at=expires_at
        )
        
        assert token_data.is_active is True
        assert token_data.expires_at == expires_at
        assert token_data.created_at is not None
    
    def test_oauth2_error(self):
        """Test OAuth2 error response model."""
        error = OAuth2Error(
            error="invalid_request",
            error_description="Missing required parameter",
            error_uri="https://docs.example.com/errors",
            state="random_state_123"
        )
        
        assert error.error == "invalid_request"
        assert error.state == "random_state_123"


class TestOAuth2Utilities:
    """Test OAuth2 utility functions."""
    
    def test_generate_client_id(self):
        """Test client ID generation."""
        client_id = generate_client_id()
        
        assert client_id.startswith("oauth2_client_")
        assert len(client_id) == len("oauth2_client_") + 24
        
        # Test uniqueness
        client_id2 = generate_client_id()
        assert client_id != client_id2
    
    def test_generate_client_secret(self):
        """Test client secret generation."""
        secret = generate_client_secret()
        
        assert secret.startswith("cs_")
        assert len(secret) == len("cs_") + 32
        
        # Test uniqueness
        secret2 = generate_client_secret()
        assert secret != secret2
    
    def test_generate_authorization_code(self):
        """Test authorization code generation."""
        code = generate_authorization_code()
        
        assert code.startswith("auth_code_")
        assert len(code) == len("auth_code_") + 32
        
        # Test uniqueness
        code2 = generate_authorization_code()
        assert code != code2
    
    def test_generate_refresh_token(self):
        """Test refresh token generation."""
        token = generate_refresh_token()
        
        assert token.startswith("rt_")
        assert len(token) == len("rt_") + 32
        
        # Test uniqueness
        token2 = generate_refresh_token()
        assert token != token2
    
    def test_validate_scopes_valid(self):
        """Test scope validation with valid scopes."""
        scopes = ["read:profile", "write:data", "read:tokens"]
        validated = validate_scopes(scopes)
        
        assert validated == scopes
    
    def test_validate_scopes_invalid(self):
        """Test scope validation with invalid scope."""
        scopes = ["read:profile", "invalid:scope"]
        
        with pytest.raises(ValueError) as exc_info:
            validate_scopes(scopes)
        
        assert "Invalid scope: invalid:scope" in str(exc_info.value)
    
    def test_get_scope_descriptions(self):
        """Test getting scope descriptions."""
        scopes = ["read:profile", "write:data"]
        descriptions = get_scope_descriptions(scopes)
        
        assert len(descriptions) == 2
        assert descriptions[0]["scope"] == "read:profile"
        assert "profile information" in descriptions[0]["description"]
        assert descriptions[1]["scope"] == "write:data"
    
    def test_available_scopes_defined(self):
        """Test that available scopes are properly defined."""
        assert "read:profile" in AVAILABLE_SCOPES
        assert "write:data" in AVAILABLE_SCOPES
        assert "admin" in AVAILABLE_SCOPES
        
        # Test descriptions are meaningful
        assert len(AVAILABLE_SCOPES["read:profile"]) > 10
        assert "profile" in AVAILABLE_SCOPES["read:profile"].lower()


class TestOAuth2Enums:
    """Test OAuth2 enumeration types."""
    
    def test_client_type_enum(self):
        """Test ClientType enum."""
        assert ClientType.CONFIDENTIAL == "confidential"
        assert ClientType.PUBLIC == "public"
    
    def test_grant_type_enum(self):
        """Test GrantType enum."""
        assert GrantType.AUTHORIZATION_CODE == "authorization_code"
        assert GrantType.REFRESH_TOKEN == "refresh_token"
    
    def test_response_type_enum(self):
        """Test ResponseType enum."""
        assert ResponseType.CODE == "code"
    
    def test_token_type_enum(self):
        """Test TokenType enum."""
        assert TokenType.BEARER == "Bearer"
    
    def test_pkce_method_enum(self):
        """Test PKCEMethod enum."""
        assert PKCEMethod.PLAIN == "plain"
        assert PKCEMethod.S256 == "S256"


if __name__ == "__main__":
    pytest.main([__file__])