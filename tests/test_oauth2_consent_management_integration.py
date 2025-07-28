"""
Integration tests for OAuth2 consent management flows.

Tests cover complete consent management workflows including UI, API endpoints,
audit logging, and error handling scenarios.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from second_brain_database.main import app
from second_brain_database.routes.oauth2.models import (
    ConsentRequest,
    OAuthClient,
    UserConsent,
    ClientType,
)


class TestOAuth2ConsentManagementIntegration:
    """Integration tests for OAuth2 consent management system."""
    
    @pytest.fixture
    def client(self):
        """Test client for making HTTP requests."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user."""
        return {
            "username": "test_user",
            "email": "test@example.com",
            "role": "user"
        }
    
    @pytest.fixture
    def mock_oauth_client(self):
        """Mock OAuth2 client for testing."""
        return OAuthClient(
            client_id="test_client_123",
            client_secret_hash="hashed_secret",
            name="Test Application",
            description="A test OAuth2 application for integration testing",
            client_type=ClientType.CONFIDENTIAL,
            redirect_uris=["https://example.com/callback"],
            scopes=["read:profile", "write:data", "read:tokens"],
            website_url="https://example.com",
            owner_user_id="owner_user",
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def mock_user_consent(self):
        """Mock user consent for testing."""
        return UserConsent(
            user_id="test_user",
            client_id="test_client_123",
            scopes=["read:profile", "write:data"],
            granted_at=datetime.utcnow() - timedelta(days=7),
            last_used_at=datetime.utcnow() - timedelta(hours=2),
            is_active=True
        )
    
    @pytest.mark.asyncio
    async def test_consent_management_ui_access(self, client, mock_user):
        """Test accessing the consent management UI."""
        def mock_get_current_user():
            return mock_user
        
        with patch('second_brain_database.routes.oauth2.routes.consent_manager.list_user_consents') as mock_list_consents:
            with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_consent_event') as mock_log:
                # Setup mocks
                mock_list_consents.return_value = []
                
                # Override the dependency
                client.app.dependency_overrides[
                    __import__('second_brain_database.routes.oauth2.routes', fromlist=['get_current_user_dep']).get_current_user_dep
                ] = mock_get_current_user
                
                try:
                    # Make request to consent management UI
                    response = client.get("/oauth2/consents/manage")
                    
                    # Verify response
                    assert response.status_code == 200
                    assert "text/html" in response.headers["content-type"]
                    assert "OAuth2 Consent Management" in response.text
                    assert mock_user["username"] in response.text
                    
                    # Verify consent manager was called
                    mock_list_consents.assert_called_once_with(mock_user["username"])
                finally:
                    # Clean up dependency override
                    client.app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_consent_management_ui_with_consents(self, client, mock_user, mock_oauth_client, mock_user_consent):
        """Test consent management UI with existing consents."""
        def mock_get_current_user():
            return mock_user
        
        with patch('second_brain_database.routes.oauth2.routes.consent_manager.list_user_consents') as mock_list_consents:
            with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_consent_event') as mock_log:
                # Setup mocks
                mock_consent_data = {
                    "client_id": mock_oauth_client.client_id,
                    "client_name": mock_oauth_client.name,
                    "client_description": mock_oauth_client.description,
                    "website_url": mock_oauth_client.website_url,
                    "scopes": mock_user_consent.scopes,
                    "scope_descriptions": [
                        {"scope": "read:profile", "description": "Read your profile information"},
                        {"scope": "write:data", "description": "Modify your data"}
                    ],
                    "granted_at": mock_user_consent.granted_at,
                    "last_used_at": mock_user_consent.last_used_at,
                    "is_active": mock_user_consent.is_active
                }
                mock_list_consents.return_value = [mock_consent_data]
                
                # Override the dependency
                client.app.dependency_overrides[
                    __import__('second_brain_database.routes.oauth2.routes', fromlist=['get_current_user_dep']).get_current_user_dep
                ] = mock_get_current_user
                
                try:
                    # Make request
                    response = client.get("/oauth2/consents/manage")
                    
                    # Verify response contains consent information
                    assert response.status_code == 200
                    assert mock_oauth_client.name in response.text
                    assert mock_oauth_client.description in response.text
                    assert "read:profile" in response.text
                    assert "write:data" in response.text
                    assert "Revoke Access" in response.text
                finally:
                    # Clean up dependency override
                    client.app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_list_user_consents_endpoint(self, client, mock_user, mock_oauth_client):
        """Test the list user consents API endpoint."""
        def mock_get_current_user():
            return mock_user
        
        with patch('second_brain_database.routes.oauth2.routes.consent_manager.list_user_consents') as mock_list_consents:
            # Setup mocks
            mock_consent_data = {
                "client_id": mock_oauth_client.client_id,
                "client_name": mock_oauth_client.name,
                "scopes": ["read:profile", "write:data"],
                "granted_at": datetime.utcnow(),
                "is_active": True
            }
            mock_list_consents.return_value = [mock_consent_data]
            
            # Override the dependency
            client.app.dependency_overrides[
                __import__('second_brain_database.routes.oauth2.routes', fromlist=['get_current_user_dep']).get_current_user_dep
            ] = mock_get_current_user
            
            try:
                # Make request
                response = client.get("/oauth2/consents")
                
                # Verify response
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "Retrieved 1 consents" in data["message"]
                assert len(data["data"]["consents"]) == 1
                assert data["data"]["consents"][0]["client_id"] == mock_oauth_client.client_id
            finally:
                # Clean up dependency override
                client.app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_revoke_consent_endpoint_success(self, client, mock_user):
        """Test successful consent revocation via API endpoint."""
        def mock_get_current_user():
            return mock_user
        
        with patch('second_brain_database.routes.oauth2.routes.consent_manager.revoke_consent') as mock_revoke:
            with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_consent_event') as mock_log:
                # Setup mocks
                mock_revoke.return_value = True
                
                # Override the dependency
                client.app.dependency_overrides[
                    __import__('second_brain_database.routes.oauth2.routes', fromlist=['get_current_user_dep']).get_current_user_dep
                ] = mock_get_current_user
                
                try:
                    # Make request
                    response = client.delete("/oauth2/consents/test_client_123")
                    
                    # Verify response
                    assert response.status_code == 200
                    data = response.json()
                    assert data["success"] is True
                    assert "Consent revoked for client test_client_123" in data["message"]
                    assert data["data"]["client_id"] == "test_client_123"
                    assert data["data"]["revoked"] is True
                    
                    # Verify consent manager was called
                    mock_revoke.assert_called_once_with(
                        user_id=mock_user["username"],
                        client_id="test_client_123"
                    )
                    
                    # Verify audit logging
                    mock_log.assert_called_once()
                finally:
                    # Clean up dependency override
                    client.app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_revoke_consent_endpoint_not_found(self, client, mock_user):
        """Test consent revocation when consent doesn't exist."""
        def mock_get_current_user():
            return mock_user
        
        with patch('second_brain_database.routes.oauth2.routes.consent_manager.revoke_consent') as mock_revoke:
            # Setup mocks
            mock_revoke.return_value = False  # Consent not found
            
            # Override the dependency
            client.app.dependency_overrides[
                __import__('second_brain_database.routes.oauth2.routes', fromlist=['get_current_user_dep']).get_current_user_dep
            ] = mock_get_current_user
            
            try:
                # Make request
                response = client.delete("/oauth2/consents/nonexistent_client")
                
                # Verify response
                assert response.status_code == 404
                data = response.json()
                assert "Consent not found or already revoked" in data["detail"]
            finally:
                # Clean up dependency override
                client.app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_consent_grant_with_audit_logging(self, mock_oauth_client):
        """Test consent granting with comprehensive audit logging."""
        from second_brain_database.routes.oauth2.services.consent_manager import consent_manager
        
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            with patch.object(consent_manager, '_log_consent_audit_event') as mock_audit_log:
                # Setup mocks
                mock_db.get_client = AsyncMock(return_value=mock_oauth_client)
                mock_db.get_user_consent = AsyncMock(return_value=None)  # No existing consent
                mock_db.store_user_consent = AsyncMock(return_value=True)
                
                # Create consent request
                consent_request = ConsentRequest(
                    client_id=mock_oauth_client.client_id,
                    scopes=["read:profile", "write:data"],
                    approved=True,
                    state="test_state_123"
                )
                
                # Grant consent
                success = await consent_manager.grant_consent("test_user", consent_request)
                
                # Verify success
                assert success is True
                
                # Verify audit logging was called
                mock_audit_log.assert_called_once()
                call_args = mock_audit_log.call_args
                assert call_args[1]["event_type"] == "consent_granted"
                assert call_args[1]["user_id"] == "test_user"
                assert call_args[1]["client_id"] == mock_oauth_client.client_id
                assert call_args[1]["scopes"] == ["read:profile", "write:data"]
                
                # Verify additional context
                additional_context = call_args[1]["additional_context"]
                assert additional_context["client_name"] == mock_oauth_client.name
                assert additional_context["client_type"] == mock_oauth_client.client_type.value
                assert additional_context["is_update"] is False
                assert additional_context["state"] == "test_state_123"
    
    @pytest.mark.asyncio
    async def test_consent_revocation_with_audit_logging(self, mock_oauth_client, mock_user_consent):
        """Test consent revocation with comprehensive audit logging."""
        from second_brain_database.routes.oauth2.services.consent_manager import consent_manager
        
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            with patch.object(consent_manager, '_log_consent_audit_event') as mock_audit_log:
                with patch('second_brain_database.routes.oauth2.services.token_manager.token_manager') as mock_token_manager:
                    # Setup mocks
                    mock_db.get_user_consent = AsyncMock(return_value=mock_user_consent)
                    mock_db.get_client = AsyncMock(return_value=mock_oauth_client)
                    mock_db.revoke_user_consent = AsyncMock(return_value=True)
                    mock_token_manager.revoke_all_user_tokens = AsyncMock(return_value=2)  # 2 tokens revoked
                    
                    # Revoke consent
                    success = await consent_manager.revoke_consent("test_user", mock_oauth_client.client_id)
                    
                    # Verify success
                    assert success is True
                    
                    # Verify audit logging was called
                    mock_audit_log.assert_called_once()
                    call_args = mock_audit_log.call_args
                    assert call_args[1]["event_type"] == "consent_revoked"
                    assert call_args[1]["user_id"] == "test_user"
                    assert call_args[1]["client_id"] == mock_oauth_client.client_id
                    assert call_args[1]["scopes"] == mock_user_consent.scopes
                    
                    # Verify additional context
                    additional_context = call_args[1]["additional_context"]
                    assert additional_context["client_name"] == mock_oauth_client.name
                    assert additional_context["revoked_tokens_count"] == 2
                    assert "original_grant_date" in additional_context
                    assert "revocation_timestamp" in additional_context
    
    @pytest.mark.asyncio
    async def test_consent_denial_audit_logging(self, mock_oauth_client):
        """Test audit logging when user denies consent."""
        from second_brain_database.routes.oauth2.services.consent_manager import consent_manager
        
        with patch.object(consent_manager, '_log_consent_audit_event') as mock_audit_log:
            # Create denied consent request
            consent_request = ConsentRequest(
                client_id=mock_oauth_client.client_id,
                scopes=["read:profile", "write:data"],
                approved=False,  # User denied
                state="test_state_123"
            )
            
            # Attempt to grant consent (should fail due to denial)
            success = await consent_manager.grant_consent("test_user", consent_request)
            
            # Verify denial
            assert success is False
            
            # Verify audit logging was called for denial
            mock_audit_log.assert_called_once()
            call_args = mock_audit_log.call_args
            assert call_args[1]["event_type"] == "consent_denied"
            assert call_args[1]["user_id"] == "test_user"
            assert call_args[1]["client_id"] == mock_oauth_client.client_id
            
            # Verify denial context
            additional_context = call_args[1]["additional_context"]
            assert additional_context["denial_reason"] == "user_denied"
            assert additional_context["state"] == "test_state_123"
    
    @pytest.mark.asyncio
    async def test_consent_grant_failure_scenarios(self, mock_oauth_client):
        """Test various consent grant failure scenarios with audit logging."""
        from second_brain_database.routes.oauth2.services.consent_manager import consent_manager
        
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            with patch.object(consent_manager, '_log_consent_audit_event') as mock_audit_log:
                
                # Test 1: Client not found
                mock_db.get_client = AsyncMock(return_value=None)
                consent_request = ConsentRequest(
                    client_id="nonexistent_client",
                    scopes=["read:profile"],
                    approved=True,
                    state="test_state"
                )
                
                success = await consent_manager.grant_consent("test_user", consent_request)
                assert success is False
                
                # Verify audit log for client not found
                call_args = mock_audit_log.call_args
                assert call_args[1]["event_type"] == "consent_grant_failed"
                assert call_args[1]["user_id"] == "test_user"
                assert call_args[1]["client_id"] == "nonexistent_client"
                assert call_args[1]["scopes"] == ["read:profile"]
                assert call_args[1]["additional_context"]["failure_reason"] == "client_not_found"
                
                # Test 2: Inactive client
                mock_audit_log.reset_mock()
                inactive_client = mock_oauth_client.model_copy()
                inactive_client.is_active = False
                mock_db.get_client = AsyncMock(return_value=inactive_client)
                
                success = await consent_manager.grant_consent("test_user", consent_request)
                assert success is False
                
                # Verify audit log for inactive client
                call_args = mock_audit_log.call_args
                assert call_args[1]["event_type"] == "consent_grant_failed"
                assert call_args[1]["user_id"] == "test_user"
                assert call_args[1]["client_id"] == "nonexistent_client"
                assert call_args[1]["scopes"] == ["read:profile"]
                assert call_args[1]["additional_context"]["failure_reason"] == "client_inactive"
                assert call_args[1]["additional_context"]["client_name"] == inactive_client.name
                
                # Test 3: Unauthorized scopes
                mock_audit_log.reset_mock()
                mock_db.get_client = AsyncMock(return_value=mock_oauth_client)
                unauthorized_request = ConsentRequest(
                    client_id=mock_oauth_client.client_id,
                    scopes=["admin", "delete:everything"],  # Unauthorized scopes
                    approved=True,
                    state="test_state"
                )
                
                success = await consent_manager.grant_consent("test_user", unauthorized_request)
                assert success is False
                
                # Verify audit log for unauthorized scopes
                call_args = mock_audit_log.call_args
                assert call_args[1]["event_type"] == "consent_grant_failed"
                additional_context = call_args[1]["additional_context"]
                assert additional_context["failure_reason"] == "unauthorized_scopes"
                assert "admin" in additional_context["invalid_scopes"]
                assert "delete:everything" in additional_context["invalid_scopes"]
    
    @pytest.mark.asyncio
    async def test_consent_update_scenario(self, mock_oauth_client, mock_user_consent):
        """Test consent update scenario (user grants additional scopes)."""
        from second_brain_database.routes.oauth2.services.consent_manager import consent_manager
        
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            with patch.object(consent_manager, '_log_consent_audit_event') as mock_audit_log:
                # Setup mocks - existing consent with fewer scopes
                existing_consent = mock_user_consent.model_copy()
                existing_consent.scopes = ["read:profile"]  # Only one scope initially
                existing_consent.is_active = True
                
                mock_db.get_client = AsyncMock(return_value=mock_oauth_client)
                mock_db.get_user_consent = AsyncMock(return_value=existing_consent)
                mock_db.store_user_consent = AsyncMock(return_value=True)
                
                # Create consent request with additional scopes (only request scopes that client supports)
                consent_request = ConsentRequest(
                    client_id=mock_oauth_client.client_id,
                    scopes=["read:profile", "write:data"],  # Valid scopes for this client
                    approved=True,
                    state="test_state_update"
                )
                
                # Grant consent (should be treated as update)
                success = await consent_manager.grant_consent("test_user", consent_request)
                
                # Verify success
                assert success is True
                
                # Verify audit logging shows this as an update
                mock_audit_log.assert_called_once()
                call_args = mock_audit_log.call_args
                assert call_args[1]["event_type"] == "consent_updated"
                
                # Verify update context
                additional_context = call_args[1]["additional_context"]
                assert additional_context["is_update"] is True
                assert additional_context["previous_scopes"] == ["read:profile"]
    
    def test_consent_management_ui_authentication_required(self, client):
        """Test that consent management UI requires authentication."""
        response = client.get("/oauth2/consents/manage")
        assert response.status_code == 401
    
    def test_list_consents_authentication_required(self, client):
        """Test that list consents endpoint requires authentication."""
        response = client.get("/oauth2/consents")
        assert response.status_code == 401
    
    def test_revoke_consent_authentication_required(self, client):
        """Test that revoke consent endpoint requires authentication."""
        response = client.delete("/oauth2/consents/test_client_123")
        assert response.status_code == 401
    
    @pytest.mark.asyncio
    async def test_consent_management_error_handling(self, client, mock_user):
        """Test error handling in consent management UI."""
        def mock_get_current_user():
            return mock_user
        
        with patch('second_brain_database.routes.oauth2.routes.consent_manager.list_user_consents') as mock_list_consents:
            with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_consent_event') as mock_log:
                # Setup mocks
                mock_list_consents.side_effect = Exception("Database error")
                
                # Override the dependency
                client.app.dependency_overrides[
                    __import__('second_brain_database.routes.oauth2.routes', fromlist=['get_current_user_dep']).get_current_user_dep
                ] = mock_get_current_user
                
                try:
                    # Make request
                    response = client.get("/oauth2/consents/manage")
                    
                    # Verify error response
                    assert response.status_code == 500
                    assert "Failed to load consent management interface" in response.text
                finally:
                    # Clean up dependency override
                    client.app.dependency_overrides.clear()
    
    @pytest.mark.asyncio
    async def test_consent_revocation_error_handling(self, client, mock_user):
        """Test error handling in consent revocation endpoint."""
        def mock_get_current_user():
            return mock_user
        
        with patch('second_brain_database.routes.oauth2.routes.consent_manager.revoke_consent') as mock_revoke:
            with patch('second_brain_database.routes.oauth2.routes.oauth2_logger.log_consent_event') as mock_log:
                # Setup mocks
                mock_revoke.side_effect = Exception("Database error")
                
                # Override the dependency
                client.app.dependency_overrides[
                    __import__('second_brain_database.routes.oauth2.routes', fromlist=['get_current_user_dep']).get_current_user_dep
                ] = mock_get_current_user
                
                try:
                    # Make request
                    response = client.delete("/oauth2/consents/test_client_123")
                    
                    # Verify error response
                    assert response.status_code == 500
                    data = response.json()
                    assert "Failed to revoke consent" in data["detail"]
                finally:
                    # Clean up dependency override
                    client.app.dependency_overrides.clear()