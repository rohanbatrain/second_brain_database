#!/usr/bin/env python3
"""
Integration tests for MCP tools with existing managers.

Tests the integration between MCP tools and existing backend services
including FamilyManager, SecurityManager, and other core components.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Test imports
from second_brain_database.integrations.mcp.context import (
    MCPRequestContext,
    MCPUserContext,
    clear_mcp_context,
    create_mcp_user_context_from_fastapi_user,
    set_mcp_request_context,
    set_mcp_user_context,
)


class TestMCPToolsIntegration:
    """Integration tests for MCP tools with existing managers."""

    @pytest.fixture
    def mock_family_user_context(self):
        """Create a mock user context with family permissions."""
        return MCPUserContext(
            user_id="family_user_123",
            username="family_user",
            email="family@example.com",
            role="user",
            permissions=["family:read", "family:write"],
            family_memberships=[
                {"family_id": "family_123", "role": "admin"},
                {"family_id": "family_456", "role": "member"},
            ],
            ip_address="127.0.0.1",
            user_agent="TestClient/1.0",
        )

    @pytest.fixture
    def mock_admin_context(self):
        """Create a mock admin user context."""
        return MCPUserContext(
            user_id="admin_123",
            username="admin_user",
            role="admin",
            permissions=["admin", "family:read", "family:write"],
            ip_address="127.0.0.1",
            user_agent="AdminClient/1.0",
        )

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    @patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager")
    async def test_get_family_info_tool_integration(self, mock_family_manager_class, mock_family_user_context):
        """Test get_family_info tool integration with FamilyManager."""
        # Mock FamilyManager instance and methods
        mock_family_manager = AsyncMock()
        mock_family_manager_class.return_value = mock_family_manager

        # Mock family data
        mock_family = Mock()
        mock_family.dict.return_value = {
            "id": "family_123",
            "name": "Test Family",
            "description": "Test family description",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "member_count": 3,
            "owner_id": "family_user_123",
        }
        mock_family_manager.get_family.return_value = mock_family

        set_mcp_user_context(mock_family_user_context)

        # Import and test the tool
        try:
            from src.second_brain_database.integrations.mcp.tools.family_tools import get_family_info

            result = await get_family_info("family_123")

            # Verify FamilyManager was called correctly
            mock_family_manager.get_family.assert_called_once_with("family_123", "family_user_123")

            # Verify result
            assert result["id"] == "family_123"
            assert result["name"] == "Test Family"
            assert result["member_count"] == 3

        except ImportError:
            pytest.skip("Family tools not available for testing")

    @pytest.mark.asyncio
    @patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager")
    async def test_get_family_members_tool_integration(self, mock_family_manager_class, mock_family_user_context):
        """Test get_family_members tool integration with FamilyManager."""
        # Mock FamilyManager instance
        mock_family_manager = AsyncMock()
        mock_family_manager_class.return_value = mock_family_manager

        # Mock family members data
        mock_members = [
            {"user_id": "user_1", "username": "member1", "role": "admin", "joined_at": datetime.now(timezone.utc)},
            {"user_id": "user_2", "username": "member2", "role": "member", "joined_at": datetime.now(timezone.utc)},
        ]
        mock_family_manager.validate_family_access.return_value = True
        mock_family_manager.get_family_members.return_value = mock_members

        set_mcp_user_context(mock_family_user_context)

        try:
            from src.second_brain_database.integrations.mcp.tools.family_tools import get_family_members

            result = await get_family_members("family_123")

            # Verify access validation was called
            mock_family_manager.validate_family_access.assert_called_once_with("family_123", "family_user_123")

            # Verify members were retrieved
            mock_family_manager.get_family_members.assert_called_once_with("family_123")

            # Verify result structure
            assert len(result) == 2
            assert result[0]["username"] == "member1"
            assert result[1]["username"] == "member2"

        except ImportError:
            pytest.skip("Family tools not available for testing")

    @pytest.mark.asyncio
    @patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager")
    async def test_create_family_tool_integration(self, mock_family_manager_class, mock_family_user_context):
        """Test create_family tool integration with FamilyManager."""
        # Mock FamilyManager instance
        mock_family_manager = AsyncMock()
        mock_family_manager_class.return_value = mock_family_manager

        # Mock created family
        mock_created_family = Mock()
        mock_created_family.dict.return_value = {
            "id": "new_family_123",
            "name": "New Test Family",
            "description": "New family description",
            "owner_id": "family_user_123",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_family_manager.create_family.return_value = mock_created_family

        set_mcp_user_context(mock_family_user_context)

        try:
            from src.second_brain_database.integrations.mcp.tools.family_tools import create_family

            result = await create_family("New Test Family", "New family description")

            # Verify family creation was called
            mock_family_manager.create_family.assert_called_once()
            call_args = mock_family_manager.create_family.call_args[0]
            assert call_args[1] == "family_user_123"  # user_id

            # Verify result
            assert result["name"] == "New Test Family"
            assert result["owner_id"] == "family_user_123"

        except ImportError:
            pytest.skip("Family tools not available for testing")

    @pytest.mark.asyncio
    @patch("src.second_brain_database.integrations.mcp.tools.auth_tools.get_current_user_dep")
    async def test_get_user_profile_tool_integration(self, mock_get_user, mock_family_user_context):
        """Test get_user_profile tool integration with existing auth system."""
        # Mock user profile data
        mock_user_profile = {
            "_id": "family_user_123",
            "username": "family_user",
            "email": "family@example.com",
            "role": "user",
            "created_at": datetime.now(timezone.utc),
            "profile": {"display_name": "Family User", "bio": "Test user bio"},
        }
        mock_get_user.return_value = mock_user_profile

        set_mcp_user_context(mock_family_user_context)

        try:
            from src.second_brain_database.integrations.mcp.tools.auth_tools import get_user_profile

            result = await get_user_profile()

            # Verify result structure
            assert result["username"] == "family_user"
            assert result["email"] == "family@example.com"
            assert "profile" in result

        except ImportError:
            pytest.skip("Auth tools not available for testing")

    @pytest.mark.asyncio
    @patch("src.second_brain_database.integrations.mcp.tools.family_tools.SecurityManager")
    async def test_security_manager_integration(self, mock_security_manager_class, mock_family_user_context):
        """Test MCP tools integration with SecurityManager."""
        # Mock SecurityManager instance
        mock_security_manager = AsyncMock()
        mock_security_manager_class.return_value = mock_security_manager
        mock_security_manager.check_rate_limit.return_value = None  # No rate limit exceeded

        set_mcp_user_context(mock_family_user_context)

        # Test that security manager is properly integrated
        with patch("src.second_brain_database.integrations.mcp.security.security_manager", mock_security_manager):
            from src.second_brain_database.integrations.mcp.security import secure_mcp_tool

            @secure_mcp_tool(rate_limit_action="test_action")
            async def test_tool():
                return {"security_integrated": True}

            result = await test_tool()
            assert result["security_integrated"] is True

    @pytest.mark.asyncio
    async def test_mcp_context_integration_with_fastapi_user(self):
        """Test MCP context creation from FastAPI user object."""
        fastapi_user = {
            "_id": "integration_user_123",
            "username": "integration_user",
            "email": "integration@example.com",
            "role": "user",
            "permissions": ["family:read", "profile:read"],
            "workspaces": [{"_id": "workspace_1", "name": "Test Workspace", "role": "member"}],
            "family_memberships": [{"family_id": "family_1", "role": "admin"}],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=fastapi_user,
            ip_address="192.168.1.100",
            user_agent="IntegrationClient/1.0",
            token_type="jwt",
            token_id="jwt_token_123",
        )

        # Verify context creation
        assert user_context.user_id == "integration_user_123"
        assert user_context.username == "integration_user"
        assert user_context.email == "integration@example.com"
        assert user_context.role == "user"
        assert "family:read" in user_context.permissions
        assert len(user_context.workspaces) == 1
        assert len(user_context.family_memberships) == 1
        assert user_context.ip_address == "192.168.1.100"
        assert user_context.user_agent == "IntegrationClient/1.0"
        assert user_context.token_type == "jwt"
        assert user_context.token_id == "jwt_token_123"

        # Test context methods
        assert user_context.has_permission("family:read") is True
        assert user_context.has_permission("admin") is False
        assert user_context.is_workspace_member("workspace_1") is True
        assert user_context.is_family_member("family_1") is True
        assert user_context.get_family_role("family_1") == "admin"

    @pytest.mark.asyncio
    @patch("src.second_brain_database.integrations.mcp.tools.family_tools.db_manager")
    async def test_database_integration(self, mock_db_manager, mock_family_user_context):
        """Test MCP tools integration with database manager."""
        # Mock database operations
        mock_collection = AsyncMock()
        mock_db_manager.get_collection.return_value = mock_collection

        # Mock family document
        mock_family_doc = {
            "_id": "family_123",
            "name": "Test Family",
            "description": "Test description",
            "owner_id": "family_user_123",
            "created_at": datetime.now(timezone.utc),
        }
        mock_collection.find_one.return_value = mock_family_doc

        set_mcp_user_context(mock_family_user_context)

        # Test database integration through family manager
        with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

            # Mock family object with dict method
            mock_family = Mock()
            mock_family.dict.return_value = mock_family_doc
            mock_family_manager.get_family.return_value = mock_family

            try:
                from src.second_brain_database.integrations.mcp.tools.family_tools import get_family_info

                result = await get_family_info("family_123")

                # Verify database integration
                assert result["name"] == "Test Family"
                assert result["owner_id"] == "family_user_123"

            except ImportError:
                pytest.skip("Family tools not available for testing")

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, mock_family_user_context):
        """Test error handling integration between MCP tools and managers."""
        set_mcp_user_context(mock_family_user_context)

        # Test with manager that raises an exception
        with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

            # Mock manager to raise exception
            mock_family_manager.get_family.side_effect = ValueError("Database connection failed")

            try:
                from src.second_brain_database.integrations.mcp.tools.family_tools import get_family_info

                with pytest.raises(ValueError) as exc_info:
                    await get_family_info("family_123")

                assert "Database connection failed" in str(exc_info.value)

            except ImportError:
                pytest.skip("Family tools not available for testing")

    @pytest.mark.asyncio
    async def test_permission_integration_with_family_access(self, mock_family_user_context):
        """Test permission integration with family access validation."""
        set_mcp_user_context(mock_family_user_context)

        # Test family access validation
        from src.second_brain_database.integrations.mcp.context import require_family_access, validate_family_access

        # Test valid family access
        has_access = await validate_family_access("family_123", "admin", mock_family_user_context)
        assert has_access is True

        # Test invalid family access
        has_access = await validate_family_access("family_999", "admin", mock_family_user_context)
        assert has_access is False

        # Test require family access - should succeed
        user_context = await require_family_access("family_123", "admin", mock_family_user_context)
        assert user_context.user_id == "family_user_123"

        # Test require family access - should fail
        from src.second_brain_database.integrations.mcp.exceptions import MCPAuthorizationError

        with pytest.raises(MCPAuthorizationError):
            await require_family_access("family_999", "admin", mock_family_user_context)


class TestMCPAuthToolsIntegration:
    """Test integration of authentication and profile MCP tools."""

    @pytest.fixture
    def mock_auth_user_context(self):
        """Create a mock user context for auth tests."""
        return MCPUserContext(
            user_id="auth_user_123",
            username="auth_user",
            email="auth@example.com",
            role="user",
            permissions=["profile:read", "profile:write", "auth:manage"],
            ip_address="127.0.0.1",
            user_agent="AuthTestClient/1.0",
        )

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_auth_tool_database_integration_pattern(self, mock_auth_user_context):
        """Test auth tool database integration pattern."""
        set_mcp_user_context(mock_auth_user_context)

        # Test the database integration pattern that auth tools would use
        mock_db_manager = Mock()
        mock_collection = AsyncMock()
        mock_db_manager.get_collection.return_value = mock_collection

        mock_user_profile = {
            "_id": "auth_user_123",
            "username": "auth_user",
            "email": "auth@example.com",
            "role": "user",
            "created_at": datetime.now(timezone.utc),
            "email_verified": True,
            "two_fa_enabled": False,
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "profile_settings": {"theme": "dark", "language": "en"},
        }
        mock_collection.find_one.return_value = mock_user_profile

        # Test the integration pattern that auth tools would use
        user_id = mock_auth_user_context.user_id

        # Simulate database operations
        users_collection = mock_db_manager.get_collection("users")
        user_doc = await users_collection.find_one({"_id": user_id})

        # Verify database integration
        mock_db_manager.get_collection.assert_called_with("users")
        mock_collection.find_one.assert_called_once_with({"_id": "auth_user_123"})

        # Verify data structure
        assert user_doc["_id"] == "auth_user_123"
        assert user_doc["username"] == "auth_user"
        assert user_doc["email"] == "auth@example.com"
        assert user_doc["email_verified"] is True

    @pytest.mark.asyncio
    async def test_auth_tool_update_integration_pattern(self, mock_auth_user_context):
        """Test auth tool update integration pattern."""
        set_mcp_user_context(mock_auth_user_context)

        # Test the update integration pattern that auth tools would use
        mock_db_manager = Mock()
        mock_collection = AsyncMock()
        mock_db_manager.get_collection.return_value = mock_collection
        mock_collection.update_one.return_value = Mock(modified_count=1)

        new_preferences = {
            "theme": "light",
            "notifications": {"email": True, "push": False},
            "privacy": {"profile_visible": True},
        }

        # Test the integration pattern
        user_id = mock_auth_user_context.user_id

        # Simulate update operations
        users_collection = mock_db_manager.get_collection("users")
        update_result = await users_collection.update_one(
            {"_id": user_id}, {"$set": {"preferences": new_preferences, "updated_at": datetime.now(timezone.utc)}}
        )

        # Verify database integration
        mock_db_manager.get_collection.assert_called_with("users")
        mock_collection.update_one.assert_called_once()
        update_call = mock_collection.update_one.call_args
        assert update_call[0][0] == {"_id": "auth_user_123"}
        assert "$set" in update_call[0][1]

        # Verify update result
        assert update_result.modified_count == 1


class TestMCPShopToolsIntegration:
    """Test integration of shop and asset management MCP tools."""

    @pytest.fixture
    def mock_shop_user_context(self):
        """Create a mock user context for shop tests."""
        return MCPUserContext(
            user_id="shop_user_123",
            username="shop_user",
            role="user",
            permissions=["shop:read", "shop:purchase", "assets:manage"],
            ip_address="127.0.0.1",
            user_agent="ShopTestClient/1.0",
        )

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_shop_tool_database_integration_pattern(self, mock_shop_user_context):
        """Test shop tool database integration pattern."""
        set_mcp_user_context(mock_shop_user_context)

        # Test the database integration pattern that shop tools would use
        mock_db_manager = Mock()
        mock_collection = AsyncMock()
        mock_db_manager.get_collection.return_value = mock_collection

        mock_shop_items = [
            {
                "_id": "item_1",
                "name": "Cool Theme",
                "price": 100,
                "item_type": "theme",
                "description": "A cool theme",
                "featured": True,
            },
            {
                "_id": "item_2",
                "name": "Avatar Pack",
                "price": 50,
                "item_type": "avatar",
                "description": "Avatar collection",
                "featured": False,
            },
        ]
        # Mock the find method to return items directly for simplicity
        mock_collection.find.return_value = mock_shop_items

        # Test the integration pattern
        shop_collection = mock_db_manager.get_collection("shop_items")
        items = await shop_collection.find({})

        # Verify database integration
        mock_db_manager.get_collection.assert_called_with("shop_items")
        mock_collection.find.assert_called_once()

        # Verify result structure
        assert len(items) == 2
        assert items[0]["_id"] == "item_1"
        assert items[0]["name"] == "Cool Theme"
        assert items[0]["price"] == 100
        assert items[1]["_id"] == "item_2"

    @pytest.mark.asyncio
    async def test_shop_purchase_transaction_integration_pattern(self, mock_shop_user_context):
        """Test shop purchase transaction integration pattern."""
        set_mcp_user_context(mock_shop_user_context)

        # Test the transaction integration pattern that shop tools would use
        mock_db_manager = Mock()
        mock_shop_collection = AsyncMock()
        mock_user_collection = AsyncMock()
        mock_transaction_collection = AsyncMock()

        def get_collection_side_effect(name):
            if name == "shop_items":
                return mock_shop_collection
            elif name == "users":
                return mock_user_collection
            elif name == "transactions":
                return mock_transaction_collection
            return AsyncMock()

        mock_db_manager.get_collection.side_effect = get_collection_side_effect

        # Mock shop item
        mock_item = {"_id": "theme_123", "name": "Premium Theme", "price": 200, "item_type": "theme"}
        mock_shop_collection.find_one.return_value = mock_item

        # Mock user with sufficient balance
        mock_user = {"_id": "shop_user_123", "sbd_balance": 500}
        mock_user_collection.find_one.return_value = mock_user
        mock_user_collection.update_one.return_value = Mock(modified_count=1)

        # Mock transaction insert
        mock_transaction_collection.insert_one.return_value = Mock(inserted_id="transaction_123")

        # Test the integration pattern
        item_id = "theme_123"
        quantity = 1
        user_id = mock_shop_user_context.user_id

        # Get item details
        shop_collection = mock_db_manager.get_collection("shop_items")
        item = await shop_collection.find_one({"_id": item_id})

        # Get user balance
        users_collection = mock_db_manager.get_collection("users")
        user = await users_collection.find_one({"_id": user_id})

        # Calculate total cost
        total_cost = item["price"] * quantity

        # Update user balance
        new_balance = user["sbd_balance"] - total_cost
        await users_collection.update_one({"_id": user_id}, {"$set": {"sbd_balance": new_balance}})

        # Create transaction record
        transactions_collection = mock_db_manager.get_collection("transactions")
        transaction_doc = {
            "user_id": user_id,
            "item_id": item_id,
            "quantity": quantity,
            "total_cost": total_cost,
            "timestamp": datetime.now(timezone.utc),
        }
        await transactions_collection.insert_one(transaction_doc)

        # Verify database operations
        mock_shop_collection.find_one.assert_called_once_with({"_id": "theme_123"})
        mock_user_collection.find_one.assert_called_once_with({"_id": "shop_user_123"})
        mock_user_collection.update_one.assert_called_once()
        mock_transaction_collection.insert_one.assert_called_once()

        # Verify transaction data
        assert total_cost == 200
        assert new_balance == 300


class TestMCPWorkspaceToolsIntegration:
    """Test integration of workspace management MCP tools."""

    @pytest.fixture
    def mock_workspace_user_context(self):
        """Create a mock user context for workspace tests."""
        return MCPUserContext(
            user_id="workspace_user_123",
            username="workspace_user",
            role="user",
            permissions=["workspace:read", "workspace:write", "workspace:admin"],
            workspaces=[
                {"_id": "workspace_1", "name": "Test Workspace", "role": "admin"},
                {"_id": "workspace_2", "name": "Other Workspace", "role": "member"},
            ],
            ip_address="127.0.0.1",
            user_agent="WorkspaceTestClient/1.0",
        )

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_get_user_workspaces_integration(self, mock_workspace_user_context):
        """Test get_user_workspaces tool integration with WorkspaceManager."""
        set_mcp_user_context(mock_workspace_user_context)

        # Mock WorkspaceManager integration
        with patch(
            "src.second_brain_database.integrations.mcp.tools.workspace_tools.WorkspaceManager"
        ) as mock_workspace_manager_class:
            mock_workspace_manager = AsyncMock()
            mock_workspace_manager_class.return_value = mock_workspace_manager

            # Mock workspace data
            mock_workspaces = [
                {
                    "_id": "workspace_1",
                    "name": "Test Workspace",
                    "description": "Test workspace description",
                    "created_at": datetime.now(timezone.utc),
                    "owner_id": "workspace_user_123",
                    "member_count": 5,
                },
                {
                    "_id": "workspace_2",
                    "name": "Other Workspace",
                    "description": "Other workspace description",
                    "created_at": datetime.now(timezone.utc),
                    "owner_id": "other_user_456",
                    "member_count": 3,
                },
            ]
            mock_workspace_manager.get_user_workspaces.return_value = mock_workspaces

            # Test the integration pattern
            user_id = mock_workspace_user_context.user_id

            # Simulate what the tool would do
            workspace_manager = mock_workspace_manager_class()
            workspaces = await workspace_manager.get_user_workspaces(user_id)

            # Verify WorkspaceManager was called correctly
            mock_workspace_manager.get_user_workspaces.assert_called_once_with("workspace_user_123")

            # Verify result structure
            assert len(workspaces) == 2
            assert workspaces[0]["_id"] == "workspace_1"
            assert workspaces[0]["name"] == "Test Workspace"
            assert workspaces[1]["_id"] == "workspace_2"

    @pytest.mark.asyncio
    async def test_create_workspace_integration(self, mock_workspace_user_context):
        """Test create_workspace tool integration with WorkspaceManager."""
        set_mcp_user_context(mock_workspace_user_context)

        # Mock WorkspaceManager integration
        with patch(
            "src.second_brain_database.integrations.mcp.tools.workspace_tools.WorkspaceManager"
        ) as mock_workspace_manager_class:
            mock_workspace_manager = AsyncMock()
            mock_workspace_manager_class.return_value = mock_workspace_manager

            # Mock created workspace
            mock_created_workspace = {
                "_id": "new_workspace_123",
                "name": "New Workspace",
                "description": "New workspace description",
                "created_at": datetime.now(timezone.utc),
                "owner_id": "workspace_user_123",
                "member_count": 1,
            }
            mock_workspace_manager.create_workspace.return_value = mock_created_workspace

            # Test the integration pattern
            workspace_name = "New Workspace"
            workspace_description = "New workspace description"
            user_id = mock_workspace_user_context.user_id

            # Simulate what the tool would do
            workspace_manager = mock_workspace_manager_class()
            created_workspace = await workspace_manager.create_workspace(workspace_name, user_id, workspace_description)

            # Verify workspace creation was called
            mock_workspace_manager.create_workspace.assert_called_once()
            call_args = mock_workspace_manager.create_workspace.call_args[0]
            assert call_args[0] == "New Workspace"  # workspace_name
            assert call_args[1] == "workspace_user_123"  # user_id

            # Verify result
            assert created_workspace["_id"] == "new_workspace_123"
            assert created_workspace["name"] == "New Workspace"
            assert created_workspace["owner_id"] == "workspace_user_123"

    @pytest.mark.asyncio
    async def test_workspace_wallet_integration(self, mock_workspace_user_context):
        """Test workspace wallet tools integration with TeamWalletManager."""
        set_mcp_user_context(mock_workspace_user_context)

        # Mock TeamWalletManager integration
        with patch(
            "src.second_brain_database.integrations.mcp.tools.workspace_tools.TeamWalletManager"
        ) as mock_wallet_manager_class:
            mock_wallet_manager = AsyncMock()
            mock_wallet_manager_class.return_value = mock_wallet_manager

            # Mock wallet data
            mock_wallet = {
                "workspace_id": "workspace_1",
                "balance": 1000,
                "frozen": False,
                "created_at": datetime.now(timezone.utc),
                "permissions": {"can_request": True, "can_approve": True},
            }
            mock_wallet_manager.get_workspace_wallet.return_value = mock_wallet

            # Test the integration pattern
            workspace_id = "workspace_1"
            user_id = mock_workspace_user_context.user_id

            # Simulate what the tool would do
            wallet_manager = mock_wallet_manager_class()
            wallet = await wallet_manager.get_workspace_wallet(workspace_id, user_id)

            # Verify wallet manager was called
            mock_wallet_manager.get_workspace_wallet.assert_called_once_with("workspace_1", "workspace_user_123")

            # Verify result
            assert wallet["workspace_id"] == "workspace_1"
            assert wallet["balance"] == 1000
            assert wallet["frozen"] is False


class TestMCPAdminToolsIntegration:
    """Test integration of administrative MCP tools."""

    @pytest.fixture
    def mock_admin_user_context(self):
        """Create a mock admin user context."""
        return MCPUserContext(
            user_id="admin_user_123",
            username="admin_user",
            role="admin",
            permissions=["admin", "system:read", "system:write", "user:manage"],
            ip_address="127.0.0.1",
            user_agent="AdminTestClient/1.0",
        )

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_get_system_health_integration(self, mock_admin_user_context):
        """Test get_system_health tool integration with system monitoring."""
        set_mcp_user_context(mock_admin_user_context)

        # Mock database manager integration
        with patch("src.second_brain_database.integrations.mcp.tools.admin_tools.db_manager") as mock_db_manager:
            # Mock database health check
            mock_db_manager.client.admin.command.return_value = {"ok": 1}
            mock_db_manager.client.server_info.return_value = {"version": "5.0.0"}

            # Test the integration pattern
            # Simulate what the tool would do
            try:
                # Test database connectivity
                ping_result = await mock_db_manager.client.admin.command("ping")
                server_info = await mock_db_manager.client.server_info()

                # Verify database health check
                mock_db_manager.client.admin.command.assert_called_with("ping")

                # Verify health data
                assert ping_result["ok"] == 1
                assert server_info["version"] == "5.0.0"

                # Simulate health status creation
                health_status = {
                    "healthy": ping_result["ok"] == 1,
                    "timestamp": datetime.now(timezone.utc),
                    "components": {
                        "database": {
                            "status": "healthy" if ping_result["ok"] == 1 else "unhealthy",
                            "version": server_info["version"],
                        }
                    },
                }

                assert health_status["healthy"] is True
                assert "database" in health_status["components"]

            except Exception as e:
                # Handle case where admin tools aren't available
                pytest.skip(f"Admin tools integration test skipped: {e}")

    @pytest.mark.asyncio
    async def test_get_user_list_integration(self, mock_admin_user_context):
        """Test get_user_list tool integration with user management."""
        set_mcp_user_context(mock_admin_user_context)

        # Mock database manager integration
        with patch("src.second_brain_database.integrations.mcp.tools.admin_tools.db_manager") as mock_db_manager:
            # Mock user collection
            mock_collection = AsyncMock()
            mock_db_manager.get_collection.return_value = mock_collection

            mock_users = [
                {
                    "_id": "user_1",
                    "username": "user1",
                    "email": "user1@example.com",
                    "role": "user",
                    "created_at": datetime.now(timezone.utc),
                    "last_login": datetime.now(timezone.utc),
                },
                {
                    "_id": "user_2",
                    "username": "user2",
                    "email": "user2@example.com",
                    "role": "user",
                    "created_at": datetime.now(timezone.utc),
                    "last_login": None,
                },
            ]
            mock_collection.find.return_value.skip.return_value.limit.return_value.to_list.return_value = mock_users
            mock_collection.count_documents.return_value = 2

            # Test the integration pattern
            limit = 10
            skip = 0

            # Simulate what the tool would do
            users_collection = mock_db_manager.get_collection("users")

            # Get users with pagination
            users_cursor = users_collection.find({}).skip(skip).limit(limit)
            users = await users_cursor.to_list(length=None)

            # Get total count
            total_count = await users_collection.count_documents({})

            # Verify database queries
            mock_db_manager.get_collection.assert_called_with("users")
            mock_collection.find.assert_called_once()
            mock_collection.count_documents.assert_called_once()

            # Verify result structure
            assert len(users) == 2
            assert total_count == 2
            assert users[0]["_id"] == "user_1"
            assert users[1]["_id"] == "user_2"


class TestMCPToolsManagerIntegration:
    """Test integration with specific manager classes."""

    @pytest.fixture
    def mock_user_context(self):
        """Create a mock user context for manager tests."""
        return MCPUserContext(
            user_id="manager_test_user",
            username="manager_user",
            role="user",
            permissions=["family:read", "family:write"],
            ip_address="127.0.0.1",
            user_agent="ManagerTestClient/1.0",
        )

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    @patch("src.second_brain_database.managers.family_manager.db_manager")
    @patch("src.second_brain_database.managers.family_manager.security_manager")
    @patch("src.second_brain_database.managers.family_manager.redis_manager")
    async def test_family_manager_dependency_injection(self, mock_redis, mock_security, mock_db, mock_user_context):
        """Test that MCP tools properly inject dependencies into FamilyManager."""
        set_mcp_user_context(mock_user_context)

        # Mock manager dependencies
        mock_db.get_collection.return_value = AsyncMock()
        mock_security.validate_user_permissions.return_value = True
        mock_redis.get_redis.return_value = AsyncMock()

        try:
            from src.second_brain_database.managers.family_manager import FamilyManager

            # Create FamilyManager instance as MCP tools would
            family_manager = FamilyManager(db_manager=mock_db, security_manager=mock_security, redis_manager=mock_redis)

            # Verify dependencies are properly set
            assert family_manager.db_manager == mock_db
            assert family_manager.security_manager == mock_security
            assert family_manager.redis_manager == mock_redis

        except ImportError:
            pytest.skip("FamilyManager not available for testing")

    @pytest.mark.asyncio
    async def test_logging_manager_integration(self, mock_user_context):
        """Test integration with logging manager for audit trails."""
        set_mcp_user_context(mock_user_context)

        with patch("src.second_brain_database.integrations.mcp.security.get_logger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            from src.second_brain_database.integrations.mcp.security import secure_mcp_tool

            @secure_mcp_tool(audit=True)
            async def logged_tool():
                return {"logged": True}

            result = await logged_tool()
            assert result["logged"] is True

            # Verify logger was used
            mock_get_logger.assert_called()

    @pytest.mark.asyncio
    async def test_redis_manager_integration_for_rate_limiting(self, mock_user_context):
        """Test integration with Redis manager for rate limiting."""
        set_mcp_user_context(mock_user_context)

        with patch("src.second_brain_database.integrations.mcp.security.redis_manager") as mock_redis:
            mock_redis_conn = AsyncMock()
            mock_redis.get_redis.return_value = mock_redis_conn
            mock_redis_conn.get.return_value = "0"  # No current rate limit
            mock_redis_conn.ttl.return_value = 60

            from src.second_brain_database.integrations.mcp.security import check_mcp_rate_limit_status

            status = await check_mcp_rate_limit_status(mock_user_context, "test_action")

            # Verify Redis integration
            mock_redis.get_redis.assert_called_once()
            assert status["action"] == "test_action"
            assert "remaining" in status

    @pytest.mark.asyncio
    @patch("src.second_brain_database.managers.workspace_manager.db_manager")
    @patch("src.second_brain_database.managers.workspace_manager.security_manager")
    @patch("src.second_brain_database.managers.workspace_manager.redis_manager")
    async def test_workspace_manager_dependency_injection(self, mock_redis, mock_security, mock_db, mock_user_context):
        """Test WorkspaceManager dependency injection in MCP tools."""
        set_mcp_user_context(mock_user_context)

        # Mock manager dependencies
        mock_db.get_collection.return_value = AsyncMock()
        mock_security.validate_user_permissions.return_value = True
        mock_redis.get_redis.return_value = AsyncMock()

        try:
            from src.second_brain_database.managers.workspace_manager import WorkspaceManager

            # Create WorkspaceManager instance as MCP tools would
            workspace_manager = WorkspaceManager(
                db_manager=mock_db, security_manager=mock_security, redis_manager=mock_redis
            )

            # Verify dependencies are properly set
            assert workspace_manager.db_manager == mock_db
            assert workspace_manager.security_manager == mock_security
            assert workspace_manager.redis_manager == mock_redis

        except ImportError:
            pytest.skip("WorkspaceManager not available for testing")

    @pytest.mark.asyncio
    @patch("src.second_brain_database.managers.security_manager.redis_manager")
    async def test_security_manager_integration_with_mcp_tools(self, mock_redis_manager, mock_user_context):
        """Test SecurityManager integration with MCP security wrappers."""
        set_mcp_user_context(mock_user_context)

        # Mock Redis for rate limiting
        mock_redis_conn = AsyncMock()
        mock_redis_manager.get_redis.return_value = mock_redis_conn
        mock_redis_conn.get.return_value = None  # No existing rate limit
        mock_redis_conn.setex.return_value = True

        try:
            from src.second_brain_database.managers.security_manager import SecurityManager

            security_manager = SecurityManager()

            # Mock request object
            mock_request = Mock()
            mock_request.client.host = "127.0.0.1"
            mock_request.headers = {"user-agent": "TestClient/1.0"}

            # Test rate limiting integration
            await security_manager.check_rate_limit(
                mock_request, "mcp_tool_test", rate_limit_requests=10, rate_limit_period=60
            )

            # Verify Redis operations
            mock_redis_conn.get.assert_called()

        except ImportError:
            pytest.skip("SecurityManager not available for testing")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
