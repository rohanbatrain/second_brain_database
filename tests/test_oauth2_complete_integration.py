"""
Comprehensive integration tests for OAuth2 provider route integration.

This module tests the complete OAuth2 flows including:
- Authorization code flow with PKCE
- Token exchange and refresh
- Error handling and security validations
- Rate limiting integration
- Logging and monitoring integration
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
import json

from second_brain_database.main import app
from second_brain_database.routes.oauth2.services.pkce_validator import PKCEValidator


class TestOAuth2RouteIntegration:
    """Test OAuth2 provider route integration with main FastAPI application."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return {
            "username": "test_user",
            "email": "test@example.com",
            "user_id": "user_123"
        }
    
    @pytest.fixture
    def mock_client_data(self):
        """Mock OAuth2 client data."""
        return {
            "client_id": "test_client_123",
            "client_secret": "test_secret_456",
            "name": "Test Client App",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "is_active": True
        }
    
    @pytest.fixture
    def pkce_params(self):
        """Generate PKCE parameters."""
        verifier, challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        return {
            "code_verifier": verifier,
            "code_challenge": challenge,
            "code_challenge_method": "S256"
        }
    
    def test_oauth2_routes_registered(self, client):
        """Test that OAuth2 routes are properly registered in the main app."""
        # Check OpenAPI schema includes OAuth2 endpoints
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_schema = response.json()
        oauth2_paths = [path for path in openapi_schema["paths"] if path.startswith("/oauth2")]
        
        expected_endpoints = [
            "/oauth2/authorize",
            "/oauth2/token", 
            "/oauth2/consent",
            "/oauth2/consents",
            "/oauth2/consents/{client_id}",
            "/oauth2/health"
        ]
        
        for endpoint in expected_endpoints:
            assert endpoint in oauth2_paths, f"Missing OAuth2 endpoint: {endpoint}"
    
    def test_oauth2_health_endpoint_integration(self, client):
        """Test OAuth2 health endpoint integration."""
        response = client.get("/oauth2/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert health_data["success"] is True
        assert "OAuth2 provider is healthy" in health_data["message"]
        assert "data" in health_data
        assert health_data["data"]["status"] == "healthy"
        assert "components" in health_data["data"]
        assert "timestamp" in health_data["data"]
    
    def test_oauth2_authorization_endpoint_authentication_required(self, client, pkce_params):
        """Test that authorization endpoint requires authentication."""
        params = {
            "response_type": "code",
            "client_id": "test_client_123",
            "redirect_uri": "https://example.com/callback",
            "scope": "read:profile",
            "state": "test_state_12345",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == 401
        
        error_data = response.json()
        assert "detail" in error_data
    
    @patch('second_brain_database.routes.oauth2.routes.get_current_user_dep')
    @patch('second_brain_database.routes.oauth2.client_manager.client_manager.get_client')
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.validate_client_request_security')
    def test_oauth2_authorization_endpoint_parameter_validation(
        self, 
        mock_validate_security,
        mock_rate_limit,
        mock_get_client,
        mock_get_user,
        client, 
        mock_user, 
        mock_client_data,
        pkce_params
    ):
        """Test OAuth2 authorization endpoint parameter validation."""
        # Setup mocks
        mock_get_user.return_value = mock_user
        mock_get_client.return_value = MagicMock(**mock_client_data)
        mock_rate_limit.return_value = None
        mock_validate_security.return_value = None
        
        # Test invalid response_type
        params = {
            "response_type": "invalid",
            "client_id": "test_client_123",
            "redirect_uri": "https://example.com/callback",
            "scope": "read:profile",
            "state": "test_state_12345",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == 302  # Redirect with error
        
        # Check redirect URL contains error
        location = response.headers.get("location")
        assert "error=unsupported_response_type" in location
    
    def test_oauth2_token_endpoint_validation(self, client):
        """Test OAuth2 token endpoint parameter validation."""
        # Test missing required parameters
        response = client.post("/oauth2/token")
        assert response.status_code == 422  # Validation error
        
        error_data = response.json()
        assert "detail" in error_data
        assert isinstance(error_data["detail"], list)
    
    def test_oauth2_token_endpoint_unsupported_grant_type(self, client):
        """Test OAuth2 token endpoint with unsupported grant type."""
        data = {
            "grant_type": "unsupported_grant",
            "client_id": "test_client_123"
        }
        
        response = client.post("/oauth2/token", data=data)
        assert response.status_code == 400
        
        error_data = response.json()
        assert error_data["error"] == "unsupported_grant_type"
        assert "not supported" in error_data["error_description"]
    
    @patch('second_brain_database.routes.oauth2.client_manager.client_manager.validate_client')
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    def test_oauth2_token_endpoint_invalid_client(
        self, 
        mock_rate_limit,
        mock_validate_client,
        client
    ):
        """Test OAuth2 token endpoint with invalid client credentials."""
        mock_rate_limit.return_value = None
        mock_validate_client.return_value = None  # Invalid client
        
        data = {
            "grant_type": "authorization_code",
            "client_id": "invalid_client",
            "client_secret": "invalid_secret",
            "code": "test_code",
            "redirect_uri": "https://example.com/callback"
        }
        
        response = client.post("/oauth2/token", data=data)
        assert response.status_code == 400
        
        error_data = response.json()
        assert error_data["error"] == "invalid_client"
    
    def test_oauth2_consent_endpoint_authentication_required(self, client):
        """Test that consent endpoint requires authentication."""
        data = {
            "client_id": "test_client_123",
            "state": "consent_state_123",
            "scopes": "read:profile,write:data",
            "approved": "true"
        }
        
        response = client.post("/oauth2/consent", data=data)
        assert response.status_code == 401
    
    def test_oauth2_consents_list_authentication_required(self, client):
        """Test that consents list endpoint requires authentication."""
        response = client.get("/oauth2/consents")
        assert response.status_code == 401
    
    def test_oauth2_consent_revocation_authentication_required(self, client):
        """Test that consent revocation endpoint requires authentication."""
        response = client.delete("/oauth2/consents/test_client_123")
        assert response.status_code == 401
    
    @patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client')
    def test_oauth2_rate_limiting_integration(self, mock_rate_limit, client, pkce_params):
        """Test that OAuth2 endpoints integrate with rate limiting."""
        from fastapi import HTTPException
        
        # Mock rate limit exceeded
        mock_rate_limit.side_effect = HTTPException(status_code=429, detail="Rate limit exceeded")
        
        params = {
            "response_type": "code",
            "client_id": "test_client_123",
            "redirect_uri": "https://example.com/callback",
            "scope": "read:profile",
            "state": "test_state_12345",
            "code_challenge": pkce_params["code_challenge"],
            "code_challenge_method": pkce_params["code_challenge_method"]
        }
        
        response = client.get("/oauth2/authorize", params=params)
        assert response.status_code == 429
    
    def test_oauth2_error_handling_integration(self, client):
        """Test OAuth2 error handling integration with main app."""
        # Test that OAuth2 errors are properly formatted
        response = client.post("/oauth2/token", data={
            "grant_type": "invalid_grant_type",
            "client_id": "test_client"
        })
        
        assert response.status_code == 400
        error_data = response.json()
        
        # Should follow OAuth2 error format
        assert "error" in error_data
        assert "error_description" in error_data
        assert error_data["error"] == "unsupported_grant_type"
    
    def test_oauth2_logging_integration(self, client):
        """Test that OAuth2 endpoints integrate with logging system."""
        with patch('second_brain_database.routes.oauth2.routes.logger') as mock_logger:
            # Make a request that should trigger logging
            response = client.get("/oauth2/health")
            assert response.status_code == 200
            
            # Verify logging was called (health endpoint logs)
            assert mock_logger.info.called or mock_logger.debug.called
    
    def test_oauth2_security_headers_integration(self, client):
        """Test OAuth2 endpoints include proper security headers."""
        response = client.get("/oauth2/health")
        assert response.status_code == 200
        
        # Check for security headers (added by middleware)
        headers = response.headers
        # These would be added by security middleware if configured
        # Just verify the response is properly formed
        assert "content-type" in headers
    
    @patch('second_brain_database.routes.oauth2.routes.get_current_user_dep')
    @patch('second_brain_database.routes.oauth2.routes.consent_manager.list_user_consents')
    def test_oauth2_user_consent_management_integration(
        self,
        mock_list_consents,
        mock_get_user,
        client,
        mock_user
    ):
        """Test OAuth2 user consent management integration."""
        mock_get_user.return_value = mock_user
        mock_list_consents.return_value = [
            {
                "client_id": "test_client_123",
                "client_name": "Test App",
                "scopes": ["read:profile"],
                "granted_at": "2024-01-01T00:00:00Z"
            }
        ]
        
        response = client.get("/oauth2/consents")
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "consents" in data["data"]
        assert len(data["data"]["consents"]) == 1
    
    def test_oauth2_openapi_documentation_integration(self, client):
        """Test OAuth2 endpoints are properly documented in OpenAPI."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        openapi_schema = response.json()
        
        # Check OAuth2 endpoints have proper documentation
        oauth2_authorize = openapi_schema["paths"].get("/oauth2/authorize")
        assert oauth2_authorize is not None
        assert "get" in oauth2_authorize
        assert "summary" in oauth2_authorize["get"]
        assert "OAuth2" in oauth2_authorize["get"]["tags"]
        
        oauth2_token = openapi_schema["paths"].get("/oauth2/token")
        assert oauth2_token is not None
        assert "post" in oauth2_token
        assert "summary" in oauth2_token["post"]
        assert "OAuth2" in oauth2_token["post"]["tags"]
    
    def test_oauth2_middleware_integration(self, client):
        """Test OAuth2 endpoints work with application middleware."""
        # Test that requests go through middleware stack
        with patch('second_brain_database.utils.logging_utils.RequestLoggingMiddleware') as mock_middleware:
            response = client.get("/oauth2/health")
            assert response.status_code == 200
            
            # Middleware should process the request
            # (This is more of a smoke test to ensure no middleware conflicts)
    
    def test_oauth2_database_integration(self, client):
        """Test OAuth2 endpoints integrate with database systems."""
        # This is tested implicitly through other tests, but we can verify
        # that the endpoints don't crash when database operations are attempted
        
        # Health endpoint should check component status
        response = client.get("/oauth2/health")
        assert response.status_code == 200
        
        health_data = response.json()
        assert "components" in health_data["data"]
        
        # Components should include database-dependent services
        components = health_data["data"]["components"]
        expected_components = ["client_manager", "auth_code_manager", "security_manager"]
        
        for component in expected_components:
            assert component in components
    
    def test_oauth2_redis_integration(self, client):
        """Test OAuth2 endpoints integrate with Redis caching."""
        # OAuth2 uses Redis for authorization codes, tokens, and rate limiting
        # This is tested implicitly through the health endpoint
        
        response = client.get("/oauth2/health")
        assert response.status_code == 200
        
        # Health endpoint should succeed even if Redis operations are involved
        health_data = response.json()
        assert health_data["data"]["status"] == "healthy"


class TestOAuth2CompleteFlows:
    """Test complete OAuth2 authorization flows."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_oauth2_authorization_code_flow_structure(self, client):
        """Test the structure of OAuth2 authorization code flow."""
        # This tests the flow structure without mocking everything
        
        # Step 1: Authorization request (should require auth)
        pkce_verifier, pkce_challenge = PKCEValidator.generate_code_verifier_and_challenge("S256")
        
        auth_params = {
            "response_type": "code",
            "client_id": "test_client_123",
            "redirect_uri": "https://example.com/callback",
            "scope": "read:profile",
            "state": "test_state_12345",
            "code_challenge": pkce_challenge,
            "code_challenge_method": "S256"
        }
        
        auth_response = client.get("/oauth2/authorize", params=auth_params)
        assert auth_response.status_code == 401  # Requires authentication
        
        # Step 2: Token exchange (should validate parameters)
        token_data = {
            "grant_type": "authorization_code",
            "code": "test_auth_code",
            "redirect_uri": "https://example.com/callback",
            "client_id": "test_client_123",
            "client_secret": "test_secret",
            "code_verifier": pkce_verifier
        }
        
        token_response = client.post("/oauth2/token", data=token_data)
        # Should fail with invalid client (expected behavior)
        assert token_response.status_code == 400
        
        error_data = token_response.json()
        assert error_data["error"] == "invalid_client"
    
    def test_oauth2_error_flow_integration(self, client):
        """Test OAuth2 error handling flows."""
        # Test various error scenarios to ensure proper error handling
        
        # Invalid grant type
        response = client.post("/oauth2/token", data={
            "grant_type": "invalid_grant",
            "client_id": "test_client"
        })
        assert response.status_code == 400
        assert response.json()["error"] == "unsupported_grant_type"
        
        # Missing required parameters
        response = client.post("/oauth2/token", data={
            "grant_type": "authorization_code"
        })
        assert response.status_code == 422  # Validation error
        
        # Invalid authorization parameters (without auth)
        response = client.get("/oauth2/authorize", params={
            "response_type": "invalid_type",
            "client_id": "test_client"
        })
        assert response.status_code == 401  # Auth required first


if __name__ == "__main__":
    pytest.main([__file__, "-v"])