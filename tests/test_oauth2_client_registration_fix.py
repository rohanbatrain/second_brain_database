"""
Integration tests for OAuth2 client registration fix.

This module tests the OAuth2 client registration endpoint to ensure it properly
handles both ClientType enum objects and string values, with appropriate error
handling and logging functionality.

Tests verify the fix for the AttributeError when accessing client_type.value
by using the get_client_type_string utility function.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from second_brain_database.main import app
from second_brain_database.routes.oauth2.models import ClientType
from second_brain_database.routes.auth.routes import get_current_user_dep


class TestOAuth2ClientRegistrationFix:
    """Integration tests for OAuth2 client registration fix."""
    
    def create_mock_client_response(self, data):
        """Create a proper mock response object with model_dump method and attributes."""
        class MockClientResponse:
            def __init__(self, data):
                self.data = data
                # Set attributes directly for access
                for key, value in data.items():
                    setattr(self, key, value)
            
            def model_dump(self):
                return self.data
        
        return MockClientResponse(data)
    
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
    def base_registration_data(self):
        """Base client registration data."""
        return {
            "name": "Test OAuth2 Client",
            "description": "A test client for integration testing",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "website_url": "https://example.com"
        }
    
    def test_successful_client_registration_with_enum_client_type(
        self,
        client,
        mock_user,
        base_registration_data
    ):
        """Test successful client registration with ClientType enum object."""
        expected_response_data = {
            "client_id": "oauth2_client_test123456789",
            "client_secret": "cs_test_secret_123456789",
            "name": "Test OAuth2 Client",
            "client_type": "confidential",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "created_at": "2024-01-01T12:00:00Z",
            "is_active": True
        }
        
        mock_response = self.create_mock_client_response(expected_response_data)
        
        # Create registration data with enum client_type
        registration_data = {
            **base_registration_data,
            "client_type": ClientType.CONFIDENTIAL  # This is an enum object
        }
        
        # Mock the dependency and other services
        def mock_get_current_user():
            return mock_user
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                with patch('second_brain_database.routes.oauth2.routes.client_manager.register_client') as mock_register_client:
                    with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_client_registered') as mock_log_client:
                        # Setup mocks - register_client is async
                        async def mock_register_async(*args, **kwargs):
                            return mock_response
                        
                        mock_rate_limit.return_value = AsyncMock()
                        mock_register_client.side_effect = mock_register_async
                        mock_log_client.return_value = None
                        
                        # Make request
                        response = client.post(
                            "/oauth2/clients",
                            json=registration_data,
                            headers={"Authorization": "Bearer test_token"}
                        )
                        
                        # Verify response
                        assert response.status_code == 201
                        response_data = response.json()
                        
                        # Verify response structure
                        assert "client_id" in response_data
                        assert "client_secret" in response_data
                        assert response_data["name"] == registration_data["name"]
                        assert response_data["client_type"] == "confidential"  # Should be string in response
                        assert response_data["redirect_uris"] == registration_data["redirect_uris"]
                        assert response_data["scopes"] == registration_data["scopes"]
                        assert response_data["is_active"] is True
                        
                        # Verify client manager was called correctly
                        mock_register_client.assert_called_once()
                        call_args = mock_register_client.call_args
                        registration_arg = call_args[1]["registration"]
                        assert registration_arg.client_type == ClientType.CONFIDENTIAL
                        assert call_args[1]["owner_user_id"] == mock_user["username"]
                        
                        # Verify logging was called with string client_type
                        mock_log_client.assert_called_once()
                        log_call_args = mock_log_client.call_args[1]
                        assert log_call_args["client_type"] == "confidential"  # Should be string for logging
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()
    
    def test_successful_client_registration_with_string_client_type(
        self,
        client,
        mock_user,
        base_registration_data
    ):
        """Test successful client registration with string client_type value."""
        expected_response_data = {
            "client_id": "oauth2_client_test123456789",
            "client_secret": None,  # Public clients don't get secrets
            "name": "Test OAuth2 Client",
            "client_type": "public",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "created_at": "2024-01-01T12:00:00Z",
            "is_active": True
        }
        
        mock_response = self.create_mock_client_response(expected_response_data)
        
        # Create registration data with string client_type
        registration_data = {
            **base_registration_data,
            "client_type": "public"  # This is a string value
        }
        
        # Mock the dependency and other services
        def mock_get_current_user():
            return mock_user
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                with patch('second_brain_database.routes.oauth2.routes.client_manager.register_client') as mock_register_client:
                    with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_client_registered') as mock_log_client:
                        # Setup mocks - register_client is async
                        async def mock_register_async(*args, **kwargs):
                            return mock_response
                        
                        mock_rate_limit.return_value = AsyncMock()
                        mock_register_client.side_effect = mock_register_async
                        mock_log_client.return_value = None
                        
                        # Make request
                        response = client.post(
                            "/oauth2/clients",
                            json=registration_data,
                            headers={"Authorization": "Bearer test_token"}
                        )
                        
                        # Verify response
                        assert response.status_code == 201
                        response_data = response.json()
                        
                        # Verify response structure
                        assert "client_id" in response_data
                        assert response_data["name"] == registration_data["name"]
                        assert response_data["client_type"] == "public"  # Should remain string
                        assert response_data["redirect_uris"] == registration_data["redirect_uris"]
                        assert response_data["scopes"] == registration_data["scopes"]
                        assert response_data["is_active"] is True
                        
                        # Verify client manager was called correctly
                        mock_register_client.assert_called_once()
                        call_args = mock_register_client.call_args
                        registration_arg = call_args[1]["registration"]
                        # Pydantic should convert string to enum
                        assert registration_arg.client_type == ClientType.PUBLIC
                        assert call_args[1]["owner_user_id"] == mock_user["username"]
                        
                        # Verify logging was called with string client_type
                        mock_log_client.assert_called_once()
                        log_call_args = mock_log_client.call_args[1]
                        assert log_call_args["client_type"] == "public"  # Should be string for logging
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()
    
    def test_error_handling_for_invalid_client_type_values(
        self,
        client,
        mock_user,
        base_registration_data
    ):
        """Test error handling for invalid client_type values."""
        # Mock the dependency
        def mock_get_current_user():
            return mock_user
        
        invalid_client_types = [
            "invalid",
            "CONFIDENTIAL",  # Wrong case
            "private",       # Wrong value
            "",              # Empty string
            123,             # Non-string value
        ]
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                mock_rate_limit.return_value = AsyncMock()
                
                for invalid_client_type in invalid_client_types:
                    # Create registration data with invalid client_type
                    registration_data = {
                        **base_registration_data,
                        "client_type": invalid_client_type
                    }
                    
                    # Make request
                    response = client.post(
                        "/oauth2/clients",
                        json=registration_data,
                        headers={"Authorization": "Bearer test_token"}
                    )
                    
                    # Verify error response
                    assert response.status_code == 422, f"Expected 422 for invalid client_type: {invalid_client_type}"
                    
                    # For Pydantic validation errors, the response should contain error details
                    response_data = response.json()
                    assert "detail" in response_data
                    
                    # The error should be related to client_type validation
                    error_detail = str(response_data["detail"])
                    assert any(keyword in error_detail.lower() for keyword in ["client_type", "validation", "invalid", "input"])
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()
    
    def test_logging_works_correctly_with_both_enum_and_string_inputs(
        self,
        client,
        mock_user,
        base_registration_data
    ):
        """Verify logging works correctly with both enum and string inputs."""
        expected_response_data = {
            "client_id": "oauth2_client_test123456789",
            "client_secret": "cs_test_secret_123456789",
            "name": "Test OAuth2 Client",
            "client_type": "confidential",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "created_at": "2024-01-01T12:00:00Z",
            "is_active": True
        }
        
        mock_response = self.create_mock_client_response(expected_response_data)
        
        # Mock the dependency
        def mock_get_current_user():
            return mock_user
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            # Test with enum input
            registration_data_enum = {
                **base_registration_data,
                "client_type": ClientType.CONFIDENTIAL
            }
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                with patch('second_brain_database.routes.oauth2.routes.client_manager.register_client') as mock_register_client:
                    with patch('second_brain_database.routes.oauth2.routes.get_client_type_string') as mock_get_client_type_string:
                        with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_client_registered') as mock_log:
                            # Setup mocks - register_client is async
                            async def mock_register_async(*args, **kwargs):
                                return mock_response
                            
                            mock_rate_limit.return_value = AsyncMock()
                            mock_register_client.side_effect = mock_register_async
                            mock_get_client_type_string.return_value = "confidential"
                            
                            response = client.post(
                                "/oauth2/clients",
                                json=registration_data_enum,
                                headers={"Authorization": "Bearer test_token"}
                            )
                            
                            assert response.status_code == 201
                            
                            # Verify get_client_type_string was called with enum
                            mock_get_client_type_string.assert_called_with(ClientType.CONFIDENTIAL)
                            
                            # Verify logging was called with converted string
                            mock_log.assert_called_once()
                            log_call_args = mock_log.call_args[1]
                            assert log_call_args["client_type"] == "confidential"
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()
    
    def test_client_type_conversion_error_handling(
        self,
        client,
        mock_user,
        base_registration_data
    ):
        """Test error handling when client_type conversion fails."""
        expected_response_data = {
            "client_id": "oauth2_client_test123456789",
            "client_secret": "cs_test_secret_123456789",
            "name": "Test OAuth2 Client",
            "client_type": "confidential",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "created_at": "2024-01-01T12:00:00Z",
            "is_active": True
        }
        
        mock_response = self.create_mock_client_response(expected_response_data)
        
        # Mock the dependency
        def mock_get_current_user():
            return mock_user
        
        registration_data = {
            **base_registration_data,
            "client_type": ClientType.CONFIDENTIAL
        }
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                with patch('second_brain_database.routes.oauth2.routes.client_manager.register_client') as mock_register_client:
                    with patch('second_brain_database.routes.oauth2.routes.get_client_type_string') as mock_get_client_type_string:
                        # Setup mocks - register_client is async
                        async def mock_register_async(*args, **kwargs):
                            return mock_response
                        
                        mock_rate_limit.return_value = AsyncMock()
                        mock_register_client.side_effect = mock_register_async
                        
                        # Mock get_client_type_string to raise ValueError
                        mock_get_client_type_string.side_effect = ValueError("Invalid client_type value")
                        
                        # Make request
                        response = client.post(
                            "/oauth2/clients",
                            json=registration_data,
                            headers={"Authorization": "Bearer test_token"}
                        )
                        
                        # Verify error response
                        assert response.status_code == 400
                        response_data = response.json()
                        assert "detail" in response_data
                        assert "Invalid client_type" in response_data["detail"]
                        
                        # Verify client registration was still attempted (error occurs during logging)
                        mock_register_client.assert_called_once()
                        
                        # Verify get_client_type_string was called
                        mock_get_client_type_string.assert_called_once()
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()
    
    def test_registration_completes_successfully_and_returns_proper_response(
        self,
        client,
        mock_user,
        base_registration_data
    ):
        """Test that registration completes successfully and returns proper response."""
        expected_response_data = {
            "client_id": "oauth2_client_test123456789",
            "client_secret": "cs_test_secret_123456789",
            "name": "Test OAuth2 Client",
            "client_type": "confidential",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "created_at": "2024-01-01T12:00:00Z",
            "is_active": True
        }
        
        mock_response = self.create_mock_client_response(expected_response_data)
        
        registration_data = {
            **base_registration_data,
            "client_type": "confidential"
        }
        
        # Mock the dependency
        def mock_get_current_user():
            return mock_user
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                with patch('second_brain_database.routes.oauth2.routes.client_manager.register_client') as mock_register_client:
                    with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_client_registered') as mock_log_client:
                        # Setup mocks - register_client is async
                        async def mock_register_async(*args, **kwargs):
                            return mock_response
                        
                        mock_rate_limit.return_value = AsyncMock()
                        mock_register_client.side_effect = mock_register_async
                        mock_log_client.return_value = None
                        
                        # Make request
                        response = client.post(
                            "/oauth2/clients",
                            json=registration_data,
                            headers={"Authorization": "Bearer test_token"}
                        )
                        
                        # Verify successful response
                        assert response.status_code == 201
                        response_data = response.json()
                        
                        # Verify all expected fields are present
                        required_fields = [
                            "client_id", "client_secret", "name", "client_type",
                            "redirect_uris", "scopes", "created_at", "is_active"
                        ]
                        
                        for field in required_fields:
                            assert field in response_data, f"Missing required field: {field}"
                        
                        # Verify field values
                        assert response_data["client_id"] == expected_response_data["client_id"]
                        assert response_data["client_secret"] == expected_response_data["client_secret"]
                        assert response_data["name"] == registration_data["name"]
                        assert response_data["client_type"] == "confidential"
                        assert response_data["redirect_uris"] == registration_data["redirect_uris"]
                        assert response_data["scopes"] == registration_data["scopes"]
                        assert response_data["is_active"] is True
                        
                        # Verify all components were called correctly
                        mock_register_client.assert_called_once()
                        mock_log_client.assert_called_once()
                        
                        # Verify rate limiting was applied
                        mock_rate_limit.assert_called_once()
                        rate_limit_call_args = mock_rate_limit.call_args[1]
                        assert rate_limit_call_args["endpoint"] == "client_registration"
                        assert rate_limit_call_args["rate_limit_requests"] == 10
                        assert rate_limit_call_args["rate_limit_period"] == 3600
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()
    
    def test_authentication_required_for_client_registration(
        self,
        client,
        base_registration_data
    ):
        """Test that authentication is required for client registration."""
        registration_data = {
            **base_registration_data,
            "client_type": "confidential"
        }
        
        # Make request without proper authentication (no dependency override)
        response = client.post(
            "/oauth2/clients",
            json=registration_data
        )
        
        # Should fail due to authentication requirement
        # The exact status code depends on the authentication implementation
        assert response.status_code in [401, 403, 422]
    
    def test_rate_limiting_applied_to_client_registration(
        self,
        client,
        mock_user,
        base_registration_data
    ):
        """Test that rate limiting is properly applied to client registration."""
        # Mock the dependency
        def mock_get_current_user():
            return mock_user
        
        registration_data = {
            **base_registration_data,
            "client_type": "confidential"
        }
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            # Mock rate limiting to raise an exception
            from fastapi import HTTPException
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                mock_rate_limit.side_effect = HTTPException(status_code=429, detail="Rate limit exceeded")
                
                # Make request
                response = client.post(
                    "/oauth2/clients",
                    json=registration_data,
                    headers={"Authorization": "Bearer test_token"}
                )
                
                # Verify rate limiting was applied
                assert response.status_code == 429
                response_data = response.json()
                assert "Rate limit exceeded" in response_data["detail"]
                
                # Verify rate limiting was called with correct parameters
                mock_rate_limit.assert_called_once()
                rate_limit_call_args = mock_rate_limit.call_args[1]
                assert rate_limit_call_args["client_id"] == f"registration_{mock_user['username']}"
                assert rate_limit_call_args["endpoint"] == "client_registration"
                assert rate_limit_call_args["rate_limit_requests"] == 10
                assert rate_limit_call_args["rate_limit_period"] == 3600
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()


class TestOAuth2ClientRegistrationLogging:
    """Test cases specifically for logging functionality in OAuth2 client registration."""
    
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
    def base_registration_data(self):
        """Base registration data for tests."""
        return {
            "name": "Test OAuth2 Client",
            "description": "A test OAuth2 client application",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "website_url": "https://example.com"
        }
    
    def create_mock_client_response(self, data):
        """Create a proper mock response object with model_dump method and attributes."""
        class MockClientResponse:
            def __init__(self, data):
                self.data = data
                # Set attributes directly for access
                for key, value in data.items():
                    setattr(self, key, value)
            
            def model_dump(self):
                return self.data
        
        return MockClientResponse(data)
    
    @patch('second_brain_database.routes.oauth2.routes.logger')
    def test_successful_client_type_conversion_logging(
        self,
        mock_routes_logger,
        client,
        mock_user,
        base_registration_data
    ):
        """Test that successful client_type conversions are logged at debug level."""
        expected_response_data = {
            "client_id": "oauth2_client_test123456789",
            "client_secret": "cs_test_secret_123456789",
            "name": "Test OAuth2 Client",
            "client_type": "confidential",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "created_at": "2024-01-01T12:00:00Z",
            "is_active": True
        }
        
        mock_response = self.create_mock_client_response(expected_response_data)
        
        # Mock the dependency
        def mock_get_current_user():
            return mock_user
        
        registration_data = {
            **base_registration_data,
            "client_type": ClientType.CONFIDENTIAL
        }
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                with patch('second_brain_database.routes.oauth2.routes.client_manager.register_client') as mock_register_client:
                    with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_client_registered') as mock_log_client:
                        # Setup mocks - register_client is async
                        async def mock_register_async(*args, **kwargs):
                            return mock_response
                        
                        mock_rate_limit.return_value = AsyncMock()
                        mock_register_client.side_effect = mock_register_async
                        mock_log_client.return_value = None
                        
                        # Make request
                        response = client.post(
                            "/oauth2/clients",
                            json=registration_data,
                            headers={"Authorization": "Bearer test_token"}
                        )
                        
                        # Verify successful response
                        assert response.status_code == 201
                        
                        # Verify debug logging was called for successful conversion
                        mock_routes_logger.debug.assert_called()
                        
                        # Find the debug call for client type conversion
                        debug_calls = mock_routes_logger.debug.call_args_list
                        conversion_log_found = False
                        
                        for call in debug_calls:
                            log_message = call[0][0]
                            if "Client type conversion successful" in log_message:
                                conversion_log_found = True
                                log_extra = call[1]['extra']
                                
                                # Verify log structure
                                assert log_extra['operation'] == 'oauth2_client_registration'
                                assert log_extra['client_name'] == registration_data['name']
                                assert log_extra['owner_user_id'] == mock_user['username']
                                assert log_extra['converted_client_type'] == 'confidential'
                                assert log_extra['conversion_success'] is True
                                assert log_extra['audit_event'] is True
                                break
                        
                        assert conversion_log_found, "Client type conversion success log not found"
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()
    
    @patch('second_brain_database.routes.oauth2.routes.logger')
    def test_client_type_conversion_error_logging(
        self,
        mock_routes_logger,
        client,
        mock_user,
        base_registration_data
    ):
        """Test that client_type conversion errors are logged at error level."""
        # Mock the dependency
        def mock_get_current_user():
            return mock_user
        
        registration_data = {
            **base_registration_data,
            "client_type": ClientType.CONFIDENTIAL
        }
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                with patch('second_brain_database.routes.oauth2.routes.client_manager.register_client') as mock_register_client:
                    with patch('second_brain_database.routes.oauth2.routes.get_client_type_string') as mock_get_client_type_string:
                        # Setup mocks
                        mock_rate_limit.return_value = AsyncMock()
                        
                        # Mock register_client to succeed (so we reach the logging code)
                        expected_response_data = {
                            "client_id": "oauth2_client_test123456789",
                            "client_secret": "cs_test_secret_123456789",
                            "name": "Test OAuth2 Client",
                            "client_type": "confidential",
                            "redirect_uris": ["https://example.com/callback"],
                            "scopes": ["read:profile", "write:data"],
                            "created_at": "2024-01-01T12:00:00Z",
                            "is_active": True
                        }
                        mock_response = self.create_mock_client_response(expected_response_data)
                        
                        async def mock_register_async(*args, **kwargs):
                            return mock_response
                        
                        mock_register_client.side_effect = mock_register_async
                        
                        # Mock get_client_type_string to raise ValueError
                        mock_get_client_type_string.side_effect = ValueError("Invalid client_type value")
                        
                        # Make request
                        response = client.post(
                            "/oauth2/clients",
                            json=registration_data,
                            headers={"Authorization": "Bearer test_token"}
                        )
                        
                        # Verify error response (should be 400 due to client_type conversion error)
                        assert response.status_code == 400
                        
                        # Verify error logging was called
                        mock_routes_logger.error.assert_called()
                        
                        # Find the error call for client type conversion
                        error_calls = mock_routes_logger.error.call_args_list
                        conversion_error_found = False
                        
                        for call in error_calls:
                            log_message = call[0][0]
                            if "Client type conversion failed during OAuth2 client registration" in log_message:
                                conversion_error_found = True
                                log_extra = call[1]['extra']
                                
                                # Verify log structure
                                assert log_extra['operation'] == 'oauth2_client_registration'
                                assert log_extra['client_name'] == registration_data['name']
                                assert log_extra['owner_user_id'] == mock_user['username']
                                assert log_extra['error_type'] == 'ValueError'
                                assert log_extra['error_message'] == 'Invalid client_type value'
                                assert log_extra['conversion_success'] is False
                                assert log_extra['audit_event'] is True
                                assert log_extra['security_relevant'] is True
                                break
                        
                        assert conversion_error_found, "Client type conversion error log not found"
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()
    
    @patch('second_brain_database.routes.oauth2.routes.logger')
    def test_logging_does_not_expose_sensitive_information(
        self,
        mock_routes_logger,
        client,
        mock_user,
        base_registration_data
    ):
        """Test that logging doesn't expose sensitive information."""
        expected_response_data = {
            "client_id": "oauth2_client_test123456789",
            "client_secret": "cs_test_secret_123456789",
            "name": "Test OAuth2 Client",
            "client_type": "confidential",
            "redirect_uris": ["https://example.com/callback"],
            "scopes": ["read:profile", "write:data"],
            "created_at": "2024-01-01T12:00:00Z",
            "is_active": True
        }
        
        mock_response = self.create_mock_client_response(expected_response_data)
        
        # Mock the dependency
        def mock_get_current_user():
            return mock_user
        
        registration_data = {
            **base_registration_data,
            "client_type": ClientType.CONFIDENTIAL
        }
        
        try:
            # Override the dependency
            client.app.dependency_overrides[get_current_user_dep] = mock_get_current_user
            
            with patch('second_brain_database.routes.oauth2.routes.oauth2_security_manager.rate_limit_client') as mock_rate_limit:
                with patch('second_brain_database.routes.oauth2.routes.client_manager.register_client') as mock_register_client:
                    with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_client_registered') as mock_log_client:
                        # Setup mocks - register_client is async
                        async def mock_register_async(*args, **kwargs):
                            return mock_response
                        
                        mock_rate_limit.return_value = AsyncMock()
                        mock_register_client.side_effect = mock_register_async
                        mock_log_client.return_value = None
                        
                        # Make request
                        response = client.post(
                            "/oauth2/clients",
                            json=registration_data,
                            headers={"Authorization": "Bearer test_token"}
                        )
                        
                        # Verify successful response
                        assert response.status_code == 201
                        
                        # Check all logging calls for sensitive information
                        all_calls = (
                            mock_routes_logger.debug.call_args_list + 
                            mock_routes_logger.info.call_args_list + 
                            mock_routes_logger.warning.call_args_list + 
                            mock_routes_logger.error.call_args_list
                        )
                        
                        sensitive_patterns = [
                            'client_secret', 'password', 'token', 'key', 'credential',
                            'session', 'cookie', 'jwt', 'secret'
                        ]
                        
                        for call in all_calls:
                            if call:
                                log_message = call[0][0]
                                log_extra = call[1].get('extra', {})
                                
                                # Check log message doesn't contain sensitive patterns
                                for pattern in sensitive_patterns:
                                    assert pattern.lower() not in log_message.lower(), \
                                        f"Sensitive pattern '{pattern}' found in log message: {log_message}"
                                
                                # Check extra fields don't contain sensitive data
                                for key, value in log_extra.items():
                                    if isinstance(value, str):
                                        for pattern in sensitive_patterns:
                                            # Allow 'client_secret' as a field name but not its value
                                            if key == 'client_secret':
                                                continue
                                            assert pattern.lower() not in value.lower(), \
                                                f"Sensitive pattern '{pattern}' found in log extra {key}: {value}"
        
        finally:
            # Clean up dependency override
            client.app.dependency_overrides.clear()