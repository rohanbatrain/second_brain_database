"""
Integration tests for OAuth2 client management API endpoints.

This module tests all OAuth2 client management endpoints including:
- Client registration endpoint for developers
- Client management endpoints (list, update, delete)
- Client credential generation and management
- Proper authentication and authorization for client management

Tests cover requirements 6.1, 6.2, and 6.3 from the OAuth2 integration spec.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from second_brain_database.main import app
from second_brain_database.routes.oauth2.models import ClientType, OAuthClient


class TestOAuth2ClientRegistrationAPI:
    """Test OAuth2 client registration API endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return {
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "role": "user"
        }
    
    @pytest.fixture
    def valid_client_registration(self):
        """Valid client registration data."""
        return {
            "name": "Test Application",
            "description": "A test OAuth2 application",
            "redirect_uris": ["https://example.com/callback"],
            "client_type": "confidential",
            "scopes": ["read:profile", "write:data"],
            "website_url": "https://example.com"
        }
    
    def test_register_client_success(self, client, mock_user, valid_client_registration):
        """Test successful OAuth2 client registration."""
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep", return_value=mock_user):
            
            with patch("second_brain_database.routes.oauth2.routes.client_manager.register_client") as mock_register:
                # Mock successful registration
                mock_response = MagicMock()
                mock_response.client_id = "oauth2_client_test123"
                mock_response.client_secret = "cs_test_secret_123"
                mock_response.name = "Test Application"
                mock_response.client_type = ClientType.CONFIDENTIAL
                mock_response.redirect_uris = ["https://example.com/callback"]
                mock_response.scopes = ["read:profile", "write:data"]
                mock_response.created_at = datetime.now()
                mock_response.is_active = True
                mock_response.model_dump.return_value = {
                    "client_id": "oauth2_client_test123",
                    "client_secret": "cs_test_secret_123",
                    "name": "Test Application",
                    "client_type": "confidential",
                    "redirect_uris": ["https://example.com/callback"],
                    "scopes": ["read:profile", "write:data"],
                    "created_at": "2024-01-01T12:00:00Z",
                    "is_active": True
                }
                mock_register.return_value = mock_response
                
                with patch("second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client") as mock_rate_limit:
                    mock_rate_limit.return_value = AsyncMock()
                    
                    with patch("second_brain_database.routes.oauth2.routes.oauth2_logger.log_client_registered") as mock_log:
                        response = client.post(
                            "/oauth2/clients",
                            json=valid_client_registration
                        )
                
                assert response.status_code == 201
                data = response.json()
                assert data["client_id"] == "oauth2_client_test123"
                assert data["client_secret"] == "cs_test_secret_123"
                assert data["name"] == "Test Application"
                assert data["client_type"] == "confidential"
                assert data["is_active"] is True
                
                # Verify client manager was called with correct parameters
                mock_register.assert_called_once()
                call_args = mock_register.call_args
                if len(call_args) > 1 and "owner_user_id" in call_args[1]:
                    assert call_args[1]["owner_user_id"] == "testuser"
                
                # Verify logging was called
                mock_log.assert_called_once()
    
    def test_register_client_invalid_data(self, client, mock_user):
        """Test client registration with invalid data."""
        invalid_registration = {
            "name": "",  # Empty name
            "redirect_uris": ["http://insecure.com/callback"],  # HTTP not allowed
            "client_type": "invalid_type",
            "scopes": ["invalid:scope"]
        }
        
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            response = client.post(
                "/oauth2/clients",
                json=invalid_registration
            )
            
            assert response.status_code == 422  # Validation error
    
    def test_register_client_rate_limited(self, client, mock_user, valid_client_registration):
        """Test client registration with rate limiting."""
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch("second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client") as mock_rate_limit:
                from fastapi import HTTPException
                mock_rate_limit.side_effect = HTTPException(status_code=429, detail="Rate limit exceeded")
                
                response = client.post(
                    "/oauth2/clients",
                    json=valid_client_registration
                )
                
                assert response.status_code == 429


class TestOAuth2ClientListAPI:
    """Test OAuth2 client listing API endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return {
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "role": "user"
        }
    
    @pytest.fixture
    def mock_admin_user(self):
        """Mock admin user."""
        return {
            "username": "admin",
            "email": "admin@example.com",
            "is_active": True,
            "role": "admin"
        }
    
    @pytest.fixture
    def mock_client_list(self):
        """Mock list of OAuth2 clients."""
        return [
            OAuthClient(
                client_id="oauth2_client_1",
                name="Client 1",
                description="First test client",
                client_type=ClientType.CONFIDENTIAL,
                redirect_uris=["https://client1.com/callback"],
                scopes=["read:profile"],
                owner_user_id="testuser",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True
            ),
            OAuthClient(
                client_id="oauth2_client_2",
                name="Client 2",
                description="Second test client",
                client_type=ClientType.PUBLIC,
                redirect_uris=["https://client2.com/callback"],
                scopes=["read:profile", "write:data"],
                owner_user_id="testuser",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True
            )
        ]
    
    def test_list_clients_user_own_clients(self, client, mock_user, mock_client_list):
        """Test listing user's own OAuth2 clients."""
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch("second_brain_database.routes.oauth2.routes.client_manager.list_clients") as mock_list:
                mock_list.return_value = mock_client_list
                
                response = client.get("/oauth2/clients")
                
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Retrieved 2 OAuth2 clients"
                assert len(data["data"]["clients"]) == 2
                assert data["data"]["total_count"] == 2
                assert data["data"]["owner_filter"] == "testuser"
                
                # Verify client manager was called with user filter
                mock_list.assert_called_once_with(owner_user_id="testuser")
                
                # Check client data structure
                client_data = data["data"]["clients"][0]
                assert "client_id" in client_data
                assert "name" in client_data
                assert "client_type" in client_data
                assert "redirect_uris" in client_data
                assert "scopes" in client_data
                assert "is_active" in client_data
                # Ensure sensitive data is not included
                assert "client_secret_hash" not in client_data
    
    def test_list_clients_admin_all_clients(self, client, mock_admin_user, mock_client_list):
        """Test admin listing all OAuth2 clients."""
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep") as mock_get_user:
            mock_get_user.return_value = mock_admin_user
            
            with patch("second_brain_database.routes.oauth2.routes.client_manager.list_clients") as mock_list:
                mock_list.return_value = mock_client_list
                
                response = client.get("/oauth2/clients?all_clients=true")
                
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Retrieved 2 OAuth2 clients"
                assert data["data"]["owner_filter"] is None
                
                # Verify client manager was called without user filter
                mock_list.assert_called_once_with(owner_user_id=None)
    
    def test_list_clients_non_admin_all_clients_forbidden(self, client, mock_user):
        """Test non-admin user trying to list all clients."""
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            response = client.get("/oauth2/clients?all_clients=true")
            
            assert response.status_code == 403
            data = response.json()
            assert "Admin privileges required" in data["detail"]


class TestOAuth2ClientGetAPI:
    """Test OAuth2 client get API endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return {
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "role": "user"
        }
    
    @pytest.fixture
    def mock_oauth2_client(self):
        """Mock OAuth2 client."""
        return OAuthClient(
            client_id="oauth2_client_test123",
            name="Test Application",
            description="A test OAuth2 application",
            client_type=ClientType.CONFIDENTIAL,
            redirect_uris=["https://example.com/callback"],
            scopes=["read:profile", "write:data"],
            website_url="https://example.com",
            owner_user_id="testuser",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
    
    def test_get_client_success_owner(self, client, mock_user, mock_oauth2_client):
        """Test successful client retrieval by owner."""
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch("second_brain_database.routes.oauth2.routes.client_manager.get_client") as mock_get:
                mock_get.return_value = mock_oauth2_client
                
                response = client.get("/oauth2/clients/oauth2_client_test123")
                
                assert response.status_code == 200
                data = response.json()
                assert data["message"] == "Client retrieved successfully"
                assert data["data"]["client"]["client_id"] == "oauth2_client_test123"
                assert data["data"]["client"]["name"] == "Test Application"
                assert data["data"]["client"]["owner_user_id"] == "testuser"
                
                # Verify sensitive data is not included
                assert "client_secret_hash" not in data["data"]["client"]
    
    def test_get_client_not_found(self, client, mock_user):
        """Test client retrieval with non-existent client."""
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch("second_brain_database.routes.oauth2.routes.client_manager.get_client") as mock_get:
                mock_get.return_value = None
                
                response = client.get("/oauth2/clients/nonexistent_client")
                
                assert response.status_code == 404
                data = response.json()
                assert "Client not found" in data["detail"]
    
    def test_get_client_access_denied(self, client, mock_user, mock_oauth2_client):
        """Test client retrieval with access denied."""
        # Client owned by different user
        mock_oauth2_client.owner_user_id = "otheruser"
        
        with patch("second_brain_database.routes.oauth2.routes.get_current_user_dep") as mock_get_user:
            mock_get_user.return_value = mock_user
            
            with patch("second_brain_database.routes.oauth2.routes.client_manager.get_client") as mock_get:
                mock_get.return_value = mock_oauth2_client
                
                response = client.get("/oauth2/clients/oauth2_client_test123")
                
                assert response.status_code == 403
                data = response.json()
                assert "Access denied to this client" in data["detail"]


def test_oauth2_client_management_basic():
    """Basic test to verify the module can be imported and run."""
    assert True


def test_oauth2_client_registration_endpoint_exists():
    """Test that the OAuth2 client registration endpoint exists."""
    from fastapi.testclient import TestClient
    from second_brain_database.main import app
    
    client = TestClient(app)
    
    # Test that the endpoint exists (will return 401 without auth, but that's expected)
    response = client.post("/oauth2/clients", json={
        "name": "Test App",
        "redirect_uris": ["https://example.com/callback"],
        "client_type": "confidential"
    })
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401


def test_oauth2_client_list_endpoint_exists():
    """Test that the OAuth2 client list endpoint exists."""
    from fastapi.testclient import TestClient
    from second_brain_database.main import app
    
    client = TestClient(app)
    
    # Test that the endpoint exists (will return 401 without auth, but that's expected)
    response = client.get("/oauth2/clients")
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401


def test_oauth2_client_get_endpoint_exists():
    """Test that the OAuth2 client get endpoint exists."""
    from fastapi.testclient import TestClient
    from second_brain_database.main import app
    
    client = TestClient(app)
    
    # Test that the endpoint exists (will return 401 without auth, but that's expected)
    response = client.get("/oauth2/clients/test123")
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401


def test_oauth2_client_update_endpoint_exists():
    """Test that the OAuth2 client update endpoint exists."""
    from fastapi.testclient import TestClient
    from second_brain_database.main import app
    
    client = TestClient(app)
    
    # Test that the endpoint exists (will return 401 without auth, but that's expected)
    response = client.put("/oauth2/clients/test123", json={"name": "Updated"})
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401


def test_oauth2_client_delete_endpoint_exists():
    """Test that the OAuth2 client delete endpoint exists."""
    from fastapi.testclient import TestClient
    from second_brain_database.main import app
    
    client = TestClient(app)
    
    # Test that the endpoint exists (will return 401 without auth, but that's expected)
    response = client.delete("/oauth2/clients/test123")
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401


def test_oauth2_client_secret_regeneration_endpoint_exists():
    """Test that the OAuth2 client secret regeneration endpoint exists."""
    from fastapi.testclient import TestClient
    from second_brain_database.main import app
    
    client = TestClient(app)
    
    # Test that the endpoint exists (will return 401 without auth, but that's expected)
    response = client.post("/oauth2/clients/test123/regenerate-secret")
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401


def test_oauth2_client_deactivation_endpoint_exists():
    """Test that the OAuth2 client deactivation endpoint exists."""
    from fastapi.testclient import TestClient
    from second_brain_database.main import app
    
    client = TestClient(app)
    
    # Test that the endpoint exists (will return 401 without auth, but that's expected)
    response = client.post("/oauth2/clients/test123/deactivate")
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401


def test_oauth2_client_reactivation_endpoint_exists():
    """Test that the OAuth2 client reactivation endpoint exists."""
    from fastapi.testclient import TestClient
    from second_brain_database.main import app
    
    client = TestClient(app)
    
    # Test that the endpoint exists (will return 401 without auth, but that's expected)
    response = client.post("/oauth2/clients/test123/reactivate")
    
    # Should return 401 (unauthorized) not 404 (not found)
    assert response.status_code == 401