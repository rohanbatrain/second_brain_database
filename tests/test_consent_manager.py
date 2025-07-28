"""
Unit tests for OAuth2 consent management system.

Tests cover consent granting, revocation, persistence, retrieval, and validation operations.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from second_brain_database.routes.oauth2.models import (
    ConsentInfo,
    ConsentRequest,
    OAuthClient,
    UserConsent,
    ClientType,
)
from second_brain_database.routes.oauth2.services.consent_manager import consent_manager


class TestConsentManager:
    """Test cases for OAuth2 consent management operations."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock OAuth2 client for testing."""
        return OAuthClient(
            client_id="test_client_123",
            client_secret_hash="hashed_secret",
            name="Test Application",
            description="A test OAuth2 application",
            client_type=ClientType.CONFIDENTIAL,
            redirect_uris=["https://example.com/callback"],
            scopes=["read:profile", "write:data"],
            website_url="https://example.com",
            owner_user_id="owner_user",
            is_active=True
        )
    
    @pytest.fixture
    def mock_consent(self):
        """Mock user consent for testing."""
        return UserConsent(
            user_id="test_user",
            client_id="test_client_123",
            scopes=["read:profile", "write:data"],
            granted_at=datetime.utcnow(),
            is_active=True
        )
    
    @pytest.fixture
    def consent_request_approved(self):
        """Mock approved consent request."""
        return ConsentRequest(
            client_id="test_client_123",
            scopes=["read:profile", "write:data"],
            approved=True,
            state="test_state_123"
        )
    
    @pytest.fixture
    def consent_request_denied(self):
        """Mock denied consent request."""
        return ConsentRequest(
            client_id="test_client_123",
            scopes=["read:profile", "write:data"],
            approved=False,
            state="test_state_123"
        )

    @pytest.mark.asyncio
    async def test_get_consent_info_success(self, mock_client):
        """Test successful consent info retrieval."""
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            # Mock database responses as async
            mock_db.get_client = AsyncMock(return_value=mock_client)
            mock_db.get_user_consent = AsyncMock(return_value=None)  # No existing consent
            
            # Test consent info retrieval
            consent_info = await consent_manager.get_consent_info(
                client_id="test_client_123",
                user_id="test_user",
                requested_scopes=["read:profile", "write:data"]
            )
            
            # Verify result
            assert consent_info is not None
            assert isinstance(consent_info, ConsentInfo)
            assert consent_info.client_name == "Test Application"
            assert consent_info.client_description == "A test OAuth2 application"
            assert consent_info.website_url == "https://example.com"
            assert consent_info.existing_consent is False
            assert len(consent_info.requested_scopes) == 2
            
            # Verify scope descriptions
            scope_names = [s["scope"] for s in consent_info.requested_scopes]
            assert "read:profile" in scope_names
            assert "write:data" in scope_names

    @pytest.mark.asyncio
    async def test_grant_consent_success(self, mock_client, consent_request_approved):
        """Test successful consent granting."""
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            # Mock database responses as async
            mock_db.get_client = AsyncMock(return_value=mock_client)
            mock_db.store_user_consent = AsyncMock(return_value=True)
            
            # Test consent granting
            success = await consent_manager.grant_consent(
                user_id="test_user",
                consent_request=consent_request_approved
            )
            
            # Verify success
            assert success is True
            
            # Verify database calls
            mock_db.get_client.assert_called_once_with("test_client_123")
            mock_db.store_user_consent.assert_called_once()

    @pytest.mark.asyncio
    async def test_grant_consent_denied(self, mock_client, consent_request_denied):
        """Test consent granting when user denies."""
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            # Mock database responses as async
            mock_db.get_client = AsyncMock(return_value=mock_client)
            
            # Test consent granting with denial
            success = await consent_manager.grant_consent(
                user_id="test_user",
                consent_request=consent_request_denied
            )
            
            # Verify denial is handled
            assert success is False
            
            # Verify no database storage attempted
            mock_db.store_user_consent.assert_not_called()

    @pytest.mark.asyncio
    async def test_revoke_consent_success(self):
        """Test successful consent revocation."""
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            # Mock successful revocation as async
            mock_db.revoke_user_consent = AsyncMock(return_value=True)
            
            # Test consent revocation
            success = await consent_manager.revoke_consent(
                user_id="test_user",
                client_id="test_client_123"
            )
            
            # Verify success
            assert success is True
            mock_db.revoke_user_consent.assert_called_once_with("test_user", "test_client_123")

    @pytest.mark.asyncio
    async def test_list_user_consents_success(self, mock_consent, mock_client):
        """Test successful user consents listing."""
        with patch('second_brain_database.routes.oauth2.services.consent_manager.oauth2_db') as mock_db:
            # Mock database responses as async
            mock_db.list_user_consents = AsyncMock(return_value=[mock_consent])
            mock_db.get_client = AsyncMock(return_value=mock_client)
            
            # Test listing consents
            consents = await consent_manager.list_user_consents("test_user")
            
            # Verify result
            assert len(consents) == 1
            consent_info = consents[0]
            
            # Verify consent information
            assert consent_info["client_id"] == "test_client_123"
            assert consent_info["client_name"] == "Test Application"
            assert consent_info["scopes"] == ["read:profile", "write:data"]
            assert consent_info["is_active"] is True

    @pytest.mark.asyncio
    async def test_validate_consent_for_authorization_valid(self, mock_consent):
        """Test consent validation for authorization with valid consent."""
        with patch.object(consent_manager, 'check_existing_consent', return_value=mock_consent):
            # Test consent validation
            is_valid = await consent_manager.validate_consent_for_authorization(
                user_id="test_user",
                client_id="test_client_123",
                requested_scopes=["read:profile"]
            )
            
            # Verify validation success
            assert is_valid is True

    @pytest.mark.asyncio
    async def test_validate_consent_for_authorization_invalid(self):
        """Test consent validation for authorization with invalid consent."""
        with patch.object(consent_manager, 'check_existing_consent', return_value=None):
            # Test consent validation
            is_valid = await consent_manager.validate_consent_for_authorization(
                user_id="test_user",
                client_id="test_client_123",
                requested_scopes=["read:profile"]
            )
            
            # Verify validation failure
            assert is_valid is False