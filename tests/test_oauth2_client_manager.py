"""
Unit tests for OAuth2 client management system.

Tests all aspects of OAuth2 client management including:
- Client registration and validation
- Client authentication with secret hashing
- Client database operations
- Redirect URI validation
- Scope management
- Error handling scenarios
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt

from second_brain_database.routes.oauth2.client_manager import ClientManager, client_manager
from second_brain_database.routes.oauth2.models import (
    ClientType,
    OAuthClient,
    OAuthClientRegistration,
    OAuthClientResponse,
)


class TestClientManager:
    """Test cases for OAuth2 ClientManager."""
    
    @pytest.fixture
    def manager(self):
        """Create a ClientManager instance for testing."""
        return ClientManager()
    
    @pytest.fixture
    def sample_registration(self):
        """Sample client registration data."""
        return OAuthClientRegistration(
            name="Test Application",
            description="A test OAuth2 application",
            redirect_uris=["https://example.com/callback"],
            client_type=ClientType.CONFIDENTIAL,
            scopes=["read:profile", "write:data"],
            website_url="https://example.com"
        )
    
    @pytest.fixture
    def sample_client(self):
        """Sample OAuth2 client."""
        return OAuthClient(
            client_id="oauth2_client_test123",
            client_secret_hash="$2b$12$hashed_secret",
            name="Test Application",
            description="A test OAuth2 application",
            client_type=ClientType.CONFIDENTIAL,
            redirect_uris=["https://example.com/callback"],
            scopes=["read:profile", "write:data"],
            website_url="https://example.com",
            owner_user_id="user123",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
    
    @pytest.mark.asyncio
    async def test_register_confidential_client_success(self, manager, sample_registration):
        """Test successful registration of confidential client."""
        with patch.object(manager.db, 'create_client', return_value=True) as mock_create:
            result = await manager.register_client(sample_registration, "user123")
            
            # Verify result
            assert isinstance(result, OAuthClientResponse)
            assert result.name == sample_registration.name
            assert result.client_type == ClientType.CONFIDENTIAL
            assert result.client_secret is not None
            assert result.client_secret.startswith("cs_")
            assert result.client_id.startswith("oauth2_client_")
            assert result.redirect_uris == sample_registration.redirect_uris
            assert result.scopes == sample_registration.scopes
            assert result.is_active is True
            
            # Verify database call
            mock_create.assert_called_once()
            client_arg = mock_create.call_args[0][0]
            assert isinstance(client_arg, OAuthClient)
            assert client_arg.name == sample_registration.name
            assert client_arg.client_secret_hash is not None
            assert client_arg.owner_user_id == "user123"
    
    @pytest.mark.asyncio
    async def test_register_public_client_success(self, manager):
        """Test successful registration of public client."""
        registration = OAuthClientRegistration(
            name="Public App",
            redirect_uris=["https://example.com/callback"],
            client_type=ClientType.PUBLIC,
            scopes=["read:profile"]
        )
        
        with patch.object(manager.db, 'create_client', return_value=True):
            result = await manager.register_client(registration)
            
            # Public clients don't get secrets
            assert result.client_secret is None
            assert result.client_type == ClientType.PUBLIC
    
    @pytest.mark.asyncio
    async def test_register_client_invalid_scopes(self, manager, sample_registration):
        """Test client registration with invalid scopes."""
        sample_registration.scopes = ["invalid:scope", "read:profile"]
        
        with pytest.raises(ValueError, match="Invalid scopes"):
            await manager.register_client(sample_registration)
    
    @pytest.mark.asyncio
    async def test_register_client_database_failure(self, manager, sample_registration):
        """Test client registration with database failure."""
        with patch.object(manager.db, 'create_client', return_value=False):
            with pytest.raises(RuntimeError, match="Failed to create client in database"):
                await manager.register_client(sample_registration)
    
    @pytest.mark.asyncio
    async def test_validate_client_success(self, manager, sample_client):
        """Test successful client validation."""
        client_secret = "test_secret"
        hashed_secret = bcrypt.hashpw(client_secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        sample_client.client_secret_hash = hashed_secret
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.validate_client(sample_client.client_id, client_secret)
            
            assert result is not None
            assert result.client_id == sample_client.client_id
    
    @pytest.mark.asyncio
    async def test_validate_client_not_found(self, manager):
        """Test client validation when client not found."""
        with patch.object(manager.db, 'get_client', return_value=None):
            result = await manager.validate_client("nonexistent_client")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_client_inactive(self, manager, sample_client):
        """Test client validation when client is inactive."""
        sample_client.is_active = False
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.validate_client(sample_client.client_id)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_confidential_client_no_secret(self, manager, sample_client):
        """Test confidential client validation without secret."""
        sample_client.client_type = ClientType.CONFIDENTIAL
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.validate_client(sample_client.client_id)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_confidential_client_wrong_secret(self, manager, sample_client):
        """Test confidential client validation with wrong secret."""
        correct_secret = "correct_secret"
        wrong_secret = "wrong_secret"
        hashed_secret = bcrypt.hashpw(correct_secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        sample_client.client_secret_hash = hashed_secret
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.validate_client(sample_client.client_id, wrong_secret)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_validate_public_client_success(self, manager, sample_client):
        """Test public client validation (no secret required)."""
        sample_client.client_type = ClientType.PUBLIC
        sample_client.client_secret_hash = None
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.validate_client(sample_client.client_id)
            assert result is not None
            assert result.client_id == sample_client.client_id
    
    @pytest.mark.asyncio
    async def test_authenticate_client_success(self, manager, sample_client):
        """Test successful client authentication."""
        client_secret = "test_secret"
        hashed_secret = bcrypt.hashpw(client_secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        sample_client.client_secret_hash = hashed_secret
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.authenticate_client(sample_client.client_id, client_secret)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_authenticate_client_failure(self, manager):
        """Test failed client authentication."""
        with patch.object(manager.db, 'get_client', return_value=None):
            result = await manager.authenticate_client("nonexistent_client", "secret")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_success(self, manager, sample_client):
        """Test successful redirect URI validation."""
        redirect_uri = "https://example.com/callback"
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.validate_redirect_uri(sample_client.client_id, redirect_uri)
            assert result is True
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_invalid(self, manager, sample_client):
        """Test invalid redirect URI validation."""
        invalid_uri = "https://malicious.com/callback"
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.validate_redirect_uri(sample_client.client_id, invalid_uri)
            assert result is False
    
    @pytest.mark.asyncio
    async def test_validate_redirect_uri_client_not_found(self, manager):
        """Test redirect URI validation when client not found."""
        with patch.object(manager.db, 'get_client', return_value=None):
            result = await manager.validate_redirect_uri("nonexistent", "https://example.com")
            assert result is False
    
    @pytest.mark.asyncio
    async def test_get_client_scopes_success(self, manager, sample_client):
        """Test getting client scopes."""
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.get_client_scopes(sample_client.client_id)
            assert result == sample_client.scopes
    
    @pytest.mark.asyncio
    async def test_get_client_scopes_not_found(self, manager):
        """Test getting scopes for non-existent client."""
        with patch.object(manager.db, 'get_client', return_value=None):
            result = await manager.get_client_scopes("nonexistent")
            assert result == []
    
    @pytest.mark.asyncio
    async def test_get_client(self, manager, sample_client):
        """Test getting client by ID."""
        with patch.object(manager.db, 'get_client', return_value=sample_client) as mock_get:
            result = await manager.get_client(sample_client.client_id)
            
            assert result == sample_client
            mock_get.assert_called_once_with(sample_client.client_id)
    
    @pytest.mark.asyncio
    async def test_update_client_success(self, manager):
        """Test successful client update."""
        client_id = "oauth2_client_test123"
        updates = {"name": "Updated Name", "description": "Updated description"}
        
        with patch.object(manager.db, 'update_client', return_value=True) as mock_update:
            result = await manager.update_client(client_id, updates)
            
            assert result is True
            mock_update.assert_called_once_with(client_id, updates)
    
    @pytest.mark.asyncio
    async def test_update_client_with_scopes(self, manager):
        """Test client update with scope validation."""
        client_id = "oauth2_client_test123"
        updates = {"scopes": ["read:profile", "write:data"]}
        
        with patch.object(manager.db, 'update_client', return_value=True) as mock_update:
            result = await manager.update_client(client_id, updates)
            
            assert result is True
            # Scopes should be validated
            mock_update.assert_called_once_with(client_id, updates)
    
    @pytest.mark.asyncio
    async def test_update_client_invalid_scopes(self, manager):
        """Test client update with invalid scopes."""
        client_id = "oauth2_client_test123"
        updates = {"scopes": ["invalid:scope"]}
        
        with pytest.raises(ValueError, match="Invalid scopes"):
            await manager.update_client(client_id, updates)
    
    @pytest.mark.asyncio
    async def test_update_client_with_secret(self, manager):
        """Test client update with new secret."""
        client_id = "oauth2_client_test123"
        new_secret = "new_secret"
        updates = {"client_secret": new_secret}
        
        with patch.object(manager.db, 'update_client', return_value=True) as mock_update:
            result = await manager.update_client(client_id, updates)
            
            assert result is True
            # Secret should be hashed and key changed
            call_args = mock_update.call_args[0][1]
            assert "client_secret" not in call_args
            assert "client_secret_hash" in call_args
            assert bcrypt.checkpw(new_secret.encode("utf-8"), call_args["client_secret_hash"].encode("utf-8"))
    
    @pytest.mark.asyncio
    async def test_delete_client_success(self, manager):
        """Test successful client deletion."""
        client_id = "oauth2_client_test123"
        
        with patch.object(manager.db, 'delete_client', return_value=True) as mock_delete:
            result = await manager.delete_client(client_id)
            
            assert result is True
            mock_delete.assert_called_once_with(client_id)
    
    @pytest.mark.asyncio
    async def test_delete_client_failure(self, manager):
        """Test failed client deletion."""
        client_id = "oauth2_client_test123"
        
        with patch.object(manager.db, 'delete_client', return_value=False) as mock_delete:
            result = await manager.delete_client(client_id)
            
            assert result is False
            mock_delete.assert_called_once_with(client_id)
    
    @pytest.mark.asyncio
    async def test_list_clients(self, manager, sample_client):
        """Test listing clients."""
        clients = [sample_client]
        
        with patch.object(manager.db, 'list_clients', return_value=clients) as mock_list:
            result = await manager.list_clients("user123")
            
            assert result == clients
            mock_list.assert_called_once_with("user123")
    
    @pytest.mark.asyncio
    async def test_deactivate_client(self, manager):
        """Test client deactivation."""
        client_id = "oauth2_client_test123"
        
        with patch.object(manager, 'update_client', return_value=True) as mock_update:
            result = await manager.deactivate_client(client_id)
            
            assert result is True
            mock_update.assert_called_once_with(client_id, {"is_active": False})
    
    @pytest.mark.asyncio
    async def test_reactivate_client(self, manager):
        """Test client reactivation."""
        client_id = "oauth2_client_test123"
        
        with patch.object(manager, 'update_client', return_value=True) as mock_update:
            result = await manager.reactivate_client(client_id)
            
            assert result is True
            mock_update.assert_called_once_with(client_id, {"is_active": True})
    
    @pytest.mark.asyncio
    async def test_regenerate_client_secret_success(self, manager, sample_client):
        """Test successful client secret regeneration."""
        sample_client.client_type = ClientType.CONFIDENTIAL
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            with patch.object(manager, 'update_client', return_value=True):
                result = await manager.regenerate_client_secret(sample_client.client_id)
                
                assert result is not None
                assert result.startswith("cs_")
                assert len(result) == 35  # cs_ + 32 characters
    
    @pytest.mark.asyncio
    async def test_regenerate_client_secret_not_found(self, manager):
        """Test secret regeneration for non-existent client."""
        with patch.object(manager.db, 'get_client', return_value=None):
            result = await manager.regenerate_client_secret("nonexistent")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_regenerate_client_secret_public_client(self, manager, sample_client):
        """Test secret regeneration for public client (should fail)."""
        sample_client.client_type = ClientType.PUBLIC
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            result = await manager.regenerate_client_secret(sample_client.client_id)
            assert result is None
    
    @pytest.mark.asyncio
    async def test_regenerate_client_secret_update_failure(self, manager, sample_client):
        """Test secret regeneration with database update failure."""
        sample_client.client_type = ClientType.CONFIDENTIAL
        
        with patch.object(manager.db, 'get_client', return_value=sample_client):
            with patch.object(manager, 'update_client', return_value=False):
                result = await manager.regenerate_client_secret(sample_client.client_id)
                assert result is None
    
    def test_hash_client_secret(self, manager):
        """Test client secret hashing."""
        secret = "test_secret"
        hashed = manager._hash_client_secret(secret)
        
        assert hashed != secret
        assert hashed.startswith("$2b$")
        assert bcrypt.checkpw(secret.encode("utf-8"), hashed.encode("utf-8"))
    
    def test_verify_client_secret_success(self, manager):
        """Test successful client secret verification."""
        secret = "test_secret"
        hashed = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        result = manager._verify_client_secret(secret, hashed)
        assert result is True
    
    def test_verify_client_secret_failure(self, manager):
        """Test failed client secret verification."""
        secret = "test_secret"
        wrong_secret = "wrong_secret"
        hashed = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        
        result = manager._verify_client_secret(wrong_secret, hashed)
        assert result is False
    
    def test_verify_client_secret_invalid_hash(self, manager):
        """Test client secret verification with invalid hash."""
        secret = "test_secret"
        invalid_hash = "invalid_hash"
        
        result = manager._verify_client_secret(secret, invalid_hash)
        assert result is False


class TestClientManagerGlobalInstance:
    """Test the global client_manager instance."""
    
    def test_global_instance_exists(self):
        """Test that global client_manager instance exists."""
        assert client_manager is not None
        assert isinstance(client_manager, ClientManager)
    
    def test_global_instance_has_db(self):
        """Test that global instance has database connection."""
        assert hasattr(client_manager, 'db')
        assert client_manager.db is not None


class TestClientManagerIntegration:
    """Integration tests for ClientManager with database operations."""
    
    @pytest.mark.asyncio
    async def test_full_client_lifecycle(self):
        """Test complete client lifecycle: register -> validate -> update -> delete."""
        manager = ClientManager()
        
        # Mock database operations
        with patch.object(manager.db, 'create_client', return_value=True):
            with patch.object(manager.db, 'get_client') as mock_get:
                with patch.object(manager.db, 'update_client', return_value=True):
                    with patch.object(manager.db, 'delete_client', return_value=True):
                        
                        # 1. Register client
                        registration = OAuthClientRegistration(
                            name="Integration Test App",
                            redirect_uris=["https://example.com/callback"],
                            client_type=ClientType.CONFIDENTIAL,
                            scopes=["read:profile"]
                        )
                        
                        response = await manager.register_client(registration)
                        assert response.client_secret is not None
                        client_id = response.client_id
                        client_secret = response.client_secret
                        
                        # 2. Create mock client for validation
                        mock_client = OAuthClient(
                            client_id=client_id,
                            client_secret_hash=manager._hash_client_secret(client_secret),
                            name=registration.name,
                            client_type=registration.client_type,
                            redirect_uris=registration.redirect_uris,
                            scopes=registration.scopes,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                            is_active=True
                        )
                        mock_get.return_value = mock_client
                        
                        # 3. Validate client
                        validated = await manager.validate_client(client_id, client_secret)
                        assert validated is not None
                        assert validated.client_id == client_id
                        
                        # 4. Update client
                        updated = await manager.update_client(client_id, {"name": "Updated Name"})
                        assert updated is True
                        
                        # 5. Delete client
                        deleted = await manager.delete_client(client_id)
                        assert deleted is True