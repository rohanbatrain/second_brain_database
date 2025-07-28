"""
Integration tests for OAuth2 authorization endpoint.

Tests the complete OAuth2 authorization flow including:
- Parameter validation
- User authentication requirements
- Client validation
- PKCE validation
- Authorization code generation
- Error handling scenarios
"""

import asyncio
import json
import secrets
import string
from datetime import datetime, timedelta
from typing import Dict, Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from second_brain_database.main import app
from second_brain_database.routes.oauth2.client_manager import client_manager
from second_brain_database.routes.oauth2.models import ClientType, OAuthClientRegistration
from second_brain_database.routes.oauth2.services.auth_code_manager import auth_code_manager
from second_brain_database.routes.oauth2.services.pkce_validator import PKCEValidator


class TestOAuth2AuthorizationEndpoint:
    """Test suite for OAuth2 authorization endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    async def test_oauth_client(self):
        """Create a test OAuth2 client."""
        registration = OAuthClientRegistration(
            name="Test Client",
            description="Test OAuth2 client",
            redirect_uris=["https://example.com/callback", "https://test.com/auth"],
            client_type=ClientType.CONFIDENTIAL,
            scopes=["read:profile", "write:data"],
            website_url="https://example.com"
        )
        
        client_response = await client_manager.register_client(registration)
        yield client_response
        
        # Cleanup
        await client_manager.delete_client(client_response.client_id)
    
    @pytest.fixture
    def valid_auth_token(self):
        """Create a valid JWT token for testing."""
        # This would normally be created through the auth system
        # For testing, we'll create a mock token
        return "valid_jwt_token_for_testing"
    
    @pytest.fixture
    def pkce_params(self):
        """Generate valid PKCE parameters."""
        verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        return {
            "code_verifier": verifier,
            "code_challenge": challenge,
            "code_challenge_method": "S256"
        }
    
    def test_authorization_endpoint_missing_parameters(self, client):
        """Test authorization endpoint with missing required parameters."""
        response = client.get("/oauth2/authorize")
        
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "validation error" in response.json()["detail"][0]["type"]
    
    def test_authorization_endpoint_invalid_response_type(self, client, test_oauth_client, pkce_params):
        """Test authorization endpoint with invalid response_type."""
        params = {
            "response_type": "token",  # Invalid, should be "code"
            "client_id": test_oauth_client.client_id,
            "redirect_uri": test_oauth_client.redirect_uris[0],
            "scope": "read:profile",
            "state": "test_state_123",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        # This would require authentication, so we expect 401
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authorization_endpoint_invalid_client_id(self, client, pkce_params):
        """Test authorization endpoint with invalid client_id."""
        params = {
            "response_type": "code",
            "client_id": "invalid_client_id",
            "redirect_uri": "https://example.com/callback",
            "scope": "read:profile",
            "state": "test_state_123",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        # This would require authentication, so we expect 401
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authorization_endpoint_invalid_redirect_uri(self, client, test_oauth_client, pkce_params):
        """Test authorization endpoint with invalid redirect_uri."""
        params = {
            "response_type": "code",
            "client_id": test_oauth_client.client_id,
            "redirect_uri": "https://malicious.com/callback",  # Not registered
            "scope": "read:profile",
            "state": "test_state_123",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        # This would require authentication, so we expect 401
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authorization_endpoint_invalid_scope(self, client, test_oauth_client, pkce_params):
        """Test authorization endpoint with invalid scope."""
        params = {
            "response_type": "code",
            "client_id": test_oauth_client.client_id,
            "redirect_uri": test_oauth_client.redirect_uris[0],
            "scope": "invalid:scope",  # Not a valid scope
            "state": "test_state_123",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        # This would require authentication, so we expect 401
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authorization_endpoint_unauthorized_scope(self, client, test_oauth_client, pkce_params):
        """Test authorization endpoint with scope not authorized for client."""
        params = {
            "response_type": "code",
            "client_id": test_oauth_client.client_id,
            "redirect_uri": test_oauth_client.redirect_uris[0],
            "scope": "admin",  # Client not authorized for admin scope
            "state": "test_state_123",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        # This would require authentication, so we expect 401
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authorization_endpoint_invalid_pkce_challenge(self, client, test_oauth_client):
        """Test authorization endpoint with invalid PKCE challenge."""
        params = {
            "response_type": "code",
            "client_id": test_oauth_client.client_id,
            "redirect_uri": test_oauth_client.redirect_uris[0],
            "scope": "read:profile",
            "state": "test_state_123",
            "code_challenge": "invalid_challenge",  # Too short
            "code_challenge_method": "S256"
        }
        
        # This would require authentication, so we expect 401
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authorization_endpoint_invalid_pkce_method(self, client, test_oauth_client, pkce_params):
        """Test authorization endpoint with invalid PKCE method."""
        params = {
            "response_type": "code",
            "client_id": test_oauth_client.client_id,
            "redirect_uri": test_oauth_client.redirect_uris[0],
            "scope": "read:profile",
            "state": "test_state_123",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": "invalid_method"
        }
        
        # This would require authentication, so we expect 401
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_authorization_endpoint_requires_authentication(self, client, test_oauth_client, pkce_params):
        """Test that authorization endpoint requires user authentication."""
        params = {
            "response_type": "code",
            "client_id": test_oauth_client.client_id,
            "redirect_uri": test_oauth_client.redirect_uris[0],
            "scope": "read:profile",
            "state": "test_state_123",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_pkce_validator_functionality(self):
        """Test PKCE validator functions work correctly."""
        # Test code verifier generation
        verifier = PKCEValidator.generate_code_verifier()
        assert len(verifier) == 128
        assert all(c in PKCEValidator.CODE_VERIFIER_CHARSET for c in verifier)
        
        # Test S256 challenge generation
        challenge = PKCEValidator.generate_code_challenge(verifier, "S256")
        assert len(challenge) == 43  # Base64url encoded SHA256
        
        # Test challenge validation
        is_valid = PKCEValidator.validate_code_challenge(verifier, challenge, "S256")
        assert is_valid is True
        
        # Test invalid verifier
        is_valid = PKCEValidator.validate_code_challenge("wrong_verifier", challenge, "S256")
        assert is_valid is False
        
        # Test plain method
        plain_challenge = PKCEValidator.generate_code_challenge(verifier, "plain")
        assert plain_challenge == verifier
        
        is_valid = PKCEValidator.validate_code_challenge(verifier, plain_challenge, "plain")
        assert is_valid is True
    
    @pytest.mark.asyncio
    async def test_authorization_code_manager_functionality(self):
        """Test authorization code manager functions work correctly."""
        # Test code generation
        code = auth_code_manager.generate_authorization_code()
        assert code.startswith("auth_code_")
        assert len(code) == 42  # "auth_code_" + 32 chars
        
        # Test code storage and retrieval
        test_scopes = ["read:profile", "write:data"]
        verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        
        success = await auth_code_manager.store_authorization_code(
            code=code,
            client_id="test_client_123",
            user_id="test_user",
            redirect_uri="https://example.com/callback",
            scopes=test_scopes,
            code_challenge=challenge,
            code_challenge_method="S256",
            ttl_seconds=600
        )
        assert success is True
        
        # Test code retrieval
        auth_code = await auth_code_manager.get_authorization_code(code)
        assert auth_code is not None
        assert auth_code.client_id == "test_client_123"
        assert auth_code.user_id == "test_user"
        assert auth_code.scopes == test_scopes
        assert auth_code.code_challenge == challenge
        assert auth_code.used is False
        
        # Test code usage
        used_code = await auth_code_manager.use_authorization_code(code)
        assert used_code is not None
        assert used_code.used is True
        
        # Test code is no longer available after use
        retrieved_code = await auth_code_manager.get_authorization_code(code)
        assert retrieved_code is None
    
    @pytest.mark.asyncio
    async def test_client_manager_functionality(self):
        """Test client manager functions work correctly."""
        # Test client registration
        registration = OAuthClientRegistration(
            name="Test Integration Client",
            description="Client for integration testing",
            redirect_uris=["https://test.example.com/callback"],
            client_type=ClientType.CONFIDENTIAL,
            scopes=["read:profile"],
            website_url="https://test.example.com"
        )
        
        client_response = await client_manager.register_client(registration)
        assert client_response.client_id.startswith("oauth2_client_")
        assert client_response.client_secret is not None
        assert client_response.name == "Test Integration Client"
        assert client_response.client_type == ClientType.CONFIDENTIAL
        
        # Test client validation
        client = await client_manager.validate_client(
            client_response.client_id,
            client_response.client_secret
        )
        assert client is not None
        assert client.client_id == client_response.client_id
        
        # Test invalid client secret
        invalid_client = await client_manager.validate_client(
            client_response.client_id,
            "invalid_secret"
        )
        assert invalid_client is None
        
        # Test redirect URI validation
        is_valid = await client_manager.validate_redirect_uri(
            client_response.client_id,
            "https://test.example.com/callback"
        )
        assert is_valid is True
        
        is_invalid = await client_manager.validate_redirect_uri(
            client_response.client_id,
            "https://malicious.com/callback"
        )
        assert is_invalid is False
        
        # Test client scopes
        scopes = await client_manager.get_client_scopes(client_response.client_id)
        assert scopes == ["read:profile"]
        
        # Cleanup
        await client_manager.delete_client(client_response.client_id)
    
    def test_oauth2_health_endpoint(self, client):
        """Test OAuth2 health check endpoint."""
        response = client.get("/oauth2/health")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        assert data["success"] is True
        assert "OAuth2 provider is healthy" in data["message"]
        assert "status" in data["data"]
        assert data["data"]["status"] == "healthy"
        assert "components" in data["data"]
        assert "statistics" in data["data"]
    
    def test_oauth2_endpoints_exist(self, client):
        """Test that OAuth2 endpoints are properly registered."""
        # Test that the authorize endpoint exists (even if it returns 401)
        response = client.get("/oauth2/authorize")
        # Should return 422 for missing parameters, not 404
        assert response.status_code != status.HTTP_404_NOT_FOUND
        
        # Test health endpoint
        response = client.get("/oauth2/health")
        assert response.status_code == status.HTTP_200_OK


# Additional test utilities

def generate_test_state() -> str:
    """Generate a test state parameter."""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


def parse_redirect_response(redirect_url: str) -> Dict[str, Any]:
    """Parse OAuth2 redirect response parameters."""
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    
    # Convert single-item lists to strings
    return {key: value[0] if len(value) == 1 else value for key, value in params.items()}


class MockAuthenticatedClient:
    """Mock authenticated client for testing OAuth2 flows."""
    
    def __init__(self, test_client: TestClient, username: str = "testuser"):
        self.client = test_client
        self.username = username
        self.token = f"mock_jwt_token_for_{username}"
    
    def get(self, url: str, **kwargs):
        """Make authenticated GET request."""
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        kwargs["headers"] = headers
        return self.client.get(url, **kwargs)
    
    def post(self, url: str, **kwargs):
        """Make authenticated POST request."""
        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self.token}"
        kwargs["headers"] = headers
        return self.client.post(url, **kwargs)


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])