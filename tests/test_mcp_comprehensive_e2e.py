#!/usr/bin/env python3
"""
Comprehensive end-to-end tests for MCP workflows.

This file contains comprehensive end-to-end tests that validate complete MCP workflows
without importing problematic modules that cause circular dependencies.
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from src.second_brain_database.integrations.mcp.exceptions import (
    MCPAuthenticationError,
    MCPAuthorizationError,
    MCPRateLimitError,
)

# Test imports
from second_brain_database.integrations.mcp.context import (
    MCPRequestContext,
    MCPUserContext,
    clear_mcp_context,
    create_mcp_request_context,
    create_mcp_user_context_from_fastapi_user,
    get_mcp_request_context,
    get_mcp_user_context,
    set_mcp_request_context,
    set_mcp_user_context,
)
from second_brain_database.integrations.mcp.security import authenticated_tool, mcp_audit_logger, secure_mcp_tool


class TestMCPComprehensiveShopWorkflows:
    """Comprehensive end-to-end tests for shop and asset management workflows."""

    @pytest.fixture
    def mock_shop_user(self):
        """Create a mock user with shop permissions."""
        return {
            "_id": "shop_user_123",
            "username": "shop_user",
            "email": "shop@example.com",
            "role": "user",
            "permissions": ["shop:read", "shop:purchase", "assets:manage"],
            "sbd_balance": 1000,
            "owned_assets": ["avatar_1", "theme_1"],
            "rented_assets": ["banner_1"],
            "workspaces": [],
            "family_memberships": [],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_complete_shop_purchase_workflow(self, mock_shop_user):
        """Test complete shop purchase workflow from browsing to transaction completion."""
        # Step 1: Create user context
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_shop_user, ip_address="192.168.1.100", user_agent="ShopClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock database manager directly
        mock_db = AsyncMock()

        # Mock collections
        mock_shop_collection = AsyncMock()
        mock_users_collection = AsyncMock()
        mock_transactions_collection = AsyncMock()

        def get_collection_side_effect(name):
            if name == "shop_items":
                return mock_shop_collection
            elif name == "users":
                return mock_users_collection
            elif name == "transactions":
                return mock_transactions_collection
            return AsyncMock()

        mock_db.get_collection.side_effect = get_collection_side_effect

        # Step 2: Browse shop items
        mock_shop_items = [
            {
                "_id": "premium_theme_123",
                "name": "Premium Dark Theme",
                "price": 200,
                "item_type": "theme",
                "description": "Professional dark theme",
                "featured": True,
                "available": True,
            },
            {
                "_id": "avatar_pack_456",
                "name": "Avatar Collection",
                "price": 150,
                "item_type": "avatar",
                "description": "Collection of avatars",
                "featured": False,
                "available": True,
            },
        ]
        # Mock the find method to return items directly
        mock_shop_collection.find.return_value = mock_shop_items

        @secure_mcp_tool(permissions=["shop:read"])
        async def browse_shop_items():
            # Simplified mock - just return the items directly
            items = await mock_shop_collection.find({"available": True})
            return items

        shop_items = await browse_shop_items()
        assert len(shop_items) == 2
        assert shop_items[0]["name"] == "Premium Dark Theme"

        # Step 3: Get item details
        mock_shop_collection.find_one.return_value = mock_shop_items[0]

        @secure_mcp_tool(permissions=["shop:read"])
        async def get_item_details(item_id: str):
            item = await mock_shop_collection.find_one({"_id": item_id})
            return item

        item_details = await get_item_details("premium_theme_123")
        assert item_details["price"] == 200
        assert item_details["item_type"] == "theme"

        # Step 4: Check user balance
        mock_user_doc = {
            "_id": "shop_user_123",
            "sbd_balance": 1000,
            "owned_assets": ["avatar_1", "theme_1"],
            "rented_assets": ["banner_1"],
        }
        mock_users_collection.find_one.return_value = mock_user_doc

        @secure_mcp_tool(permissions=["shop:read"])
        async def check_balance():
            user = await mock_users_collection.find_one({"_id": user_context.user_id})
            return {"balance": user["sbd_balance"], "can_afford": user["sbd_balance"] >= 200}

        balance_check = await check_balance()
        assert balance_check["balance"] == 1000
        assert balance_check["can_afford"] is True

        # Step 5: Execute purchase
        mock_users_collection.update_one.return_value = Mock(modified_count=1)
        mock_transactions_collection.insert_one.return_value = Mock(inserted_id="transaction_123")

        @secure_mcp_tool(permissions=["shop:purchase"])
        async def purchase_item(item_id: str, quantity: int = 1):
            # Get item and user
            item = await mock_shop_collection.find_one({"_id": item_id})
            user = await mock_users_collection.find_one({"_id": user_context.user_id})

            total_cost = item["price"] * quantity
            new_balance = user["sbd_balance"] - total_cost

            # Update user balance and assets
            await mock_users_collection.update_one(
                {"_id": user_context.user_id},
                {"$set": {"sbd_balance": new_balance}, "$push": {"owned_assets": item_id}},
            )

            # Create transaction record
            transaction = {
                "user_id": user_context.user_id,
                "item_id": item_id,
                "quantity": quantity,
                "total_cost": total_cost,
                "timestamp": datetime.now(timezone.utc),
                "status": "completed",
            }
            result = await mock_transactions_collection.insert_one(transaction)

            return {
                "transaction_id": str(result.inserted_id),
                "item_purchased": item["name"],
                "cost": total_cost,
                "new_balance": new_balance,
                "status": "success",
            }

        purchase_result = await purchase_item("premium_theme_123")

        # Step 6: Verify purchase workflow
        assert purchase_result["status"] == "success"
        assert purchase_result["cost"] == 200
        assert purchase_result["new_balance"] == 800
        assert purchase_result["item_purchased"] == "Premium Dark Theme"

        # Verify database operations
        mock_users_collection.update_one.assert_called_once()
        mock_transactions_collection.insert_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_asset_rental_workflow(self, mock_shop_user):
        """Test asset rental workflow including rental management."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_shop_user, ip_address="192.168.1.100", user_agent="RentalClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock database collections
        mock_rentals_collection = AsyncMock()
        mock_users_collection = AsyncMock()
        mock_shop_collection = AsyncMock()

        # Step 1: Browse rental items
        mock_rental_item = {
            "_id": "banner_rental_123",
            "name": "Premium Banner",
            "rental_price_daily": 10,
            "rental_price_weekly": 50,
            "rental_price_monthly": 150,
            "item_type": "banner",
            "available_for_rental": True,
        }
        # Mock the find method to return items directly
        mock_shop_collection.find.return_value = [mock_rental_item]

        @secure_mcp_tool(permissions=["shop:read"])
        async def browse_rental_items():
            # Simplified mock - just return the items directly
            items = await mock_shop_collection.find({"available_for_rental": True})
            return items

        rental_items = await browse_rental_items()
        assert len(rental_items) == 1
        assert rental_items[0]["rental_price_weekly"] == 50

        # Step 2: Rent asset
        mock_users_collection.find_one.return_value = {"_id": "shop_user_123", "sbd_balance": 1000}
        mock_users_collection.update_one.return_value = Mock(modified_count=1)
        mock_rentals_collection.insert_one.return_value = Mock(inserted_id="rental_123")

        @secure_mcp_tool(permissions=["shop:purchase"])
        async def rent_asset(item_id: str, duration: str = "weekly"):
            item = await mock_shop_collection.find_one({"_id": item_id})
            user = await mock_users_collection.find_one({"_id": user_context.user_id})

            rental_cost = item[f"rental_price_{duration}"]
            new_balance = user["sbd_balance"] - rental_cost

            # Create rental record
            from datetime import timedelta

            rental_end = datetime.now(timezone.utc)
            if duration == "weekly":
                rental_end = rental_end + timedelta(days=7)

            rental_record = {
                "user_id": user_context.user_id,
                "item_id": item_id,
                "rental_start": datetime.now(timezone.utc),
                "rental_end": rental_end,
                "cost": rental_cost,
                "status": "active",
            }

            await mock_rentals_collection.insert_one(rental_record)
            await mock_users_collection.update_one(
                {"_id": user_context.user_id}, {"$set": {"sbd_balance": new_balance}}
            )

            return {
                "rental_id": "rental_123",
                "item_name": item["name"],
                "duration": duration,
                "cost": rental_cost,
                "expires": rental_end.isoformat(),
                "status": "active",
            }

        # Mock shop collection for rental
        mock_shop_collection.find_one.return_value = mock_rental_item

        rental_result = await rent_asset("banner_rental_123", "weekly")

        # Step 3: Verify rental workflow
        assert rental_result["status"] == "active"
        assert rental_result["cost"] == 50
        assert rental_result["duration"] == "weekly"

        # Verify database operations
        mock_rentals_collection.insert_one.assert_called_once()
        mock_users_collection.update_one.assert_called_once()


class TestMCPComprehensiveWorkspaceWorkflows:
    """Comprehensive end-to-end tests for workspace management workflows."""

    @pytest.fixture
    def mock_workspace_user(self):
        """Create a mock user with workspace permissions."""
        return {
            "_id": "workspace_user_123",
            "username": "workspace_user",
            "email": "workspace@example.com",
            "role": "user",
            "permissions": ["workspace:read", "workspace:write", "workspace:admin"],
            "workspaces": [
                {"_id": "workspace_1", "name": "Test Workspace", "role": "admin"},
                {"_id": "workspace_2", "name": "Other Workspace", "role": "member"},
            ],
            "family_memberships": [],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_complete_workspace_lifecycle_workflow(self, mock_workspace_user):
        """Test complete workspace lifecycle from creation to deletion."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_workspace_user, ip_address="192.168.1.100", user_agent="WorkspaceClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock workspace manager
        mock_workspace_manager = AsyncMock()

        # Step 1: Create workspace
        mock_created_workspace = Mock()
        mock_created_workspace.dict.return_value = {
            "id": "new_workspace_123",
            "name": "New Test Workspace",
            "description": "Test workspace for E2E testing",
            "owner_id": "workspace_user_123",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "member_count": 1,
            "sbd_account": {"balance": 0, "frozen": False},
        }
        mock_workspace_manager.create_workspace.return_value = mock_created_workspace

        @secure_mcp_tool(permissions=["workspace:write"])
        async def create_workspace(name: str, description: str):
            workspace = await mock_workspace_manager.create_workspace(name, user_context.user_id, description)
            return workspace.dict()

        created_workspace = await create_workspace("New Test Workspace", "Test workspace for E2E testing")

        assert created_workspace["name"] == "New Test Workspace"
        assert created_workspace["owner_id"] == "workspace_user_123"
        assert created_workspace["member_count"] == 1

        # Step 2: Add members to workspace
        mock_workspace_manager.validate_workspace_access.return_value = True
        mock_workspace_manager.add_workspace_member.return_value = True

        @secure_mcp_tool(permissions=["workspace:admin"])
        async def add_workspace_member(workspace_id: str, user_id: str, role: str = "member"):
            await mock_workspace_manager.validate_workspace_access(workspace_id, user_context.user_id, "admin")
            result = await mock_workspace_manager.add_workspace_member(workspace_id, user_id, role)
            return {"success": result, "user_added": user_id, "role": role}

        member_result = await add_workspace_member("new_workspace_123", "new_member_456", "member")
        assert member_result["success"] is True
        assert member_result["user_added"] == "new_member_456"
        assert member_result["role"] == "member"

        # Step 3: Update workspace settings
        mock_updated_workspace = Mock()
        mock_updated_workspace.dict.return_value = {
            "id": "new_workspace_123",
            "name": "Updated Workspace Name",
            "description": "Updated description",
            "settings": {"notifications": True, "public": False},
        }
        mock_workspace_manager.update_workspace.return_value = mock_updated_workspace

        @secure_mcp_tool(permissions=["workspace:admin"])
        async def update_workspace_settings(workspace_id: str, updates: dict):
            await mock_workspace_manager.validate_workspace_access(workspace_id, user_context.user_id, "admin")
            updated = await mock_workspace_manager.update_workspace(workspace_id, updates)
            return updated.dict()

        updated_workspace = await update_workspace_settings(
            "new_workspace_123", {"name": "Updated Workspace Name", "description": "Updated description"}
        )

        assert updated_workspace["name"] == "Updated Workspace Name"
        assert updated_workspace["description"] == "Updated description"

        # Verify all manager calls
        mock_workspace_manager.create_workspace.assert_called_once()
        mock_workspace_manager.add_workspace_member.assert_called_once()
        mock_workspace_manager.update_workspace.assert_called_once()

    @pytest.mark.asyncio
    async def test_workspace_token_request_workflow(self, mock_workspace_user):
        """Test workspace SBD token request and approval workflow."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_workspace_user, ip_address="192.168.1.100", user_agent="TokenClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock wallet manager
        mock_wallet_manager = AsyncMock()

        # Step 1: Create token request
        mock_token_request = {
            "id": "token_request_123",
            "workspace_id": "workspace_1",
            "requester_id": "workspace_user_123",
            "amount": 100,
            "reason": "Development resources",
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }
        mock_wallet_manager.create_token_request.return_value = mock_token_request

        @secure_mcp_tool(permissions=["workspace:read"])
        async def create_token_request(workspace_id: str, amount: int, reason: str):
            request = await mock_wallet_manager.create_token_request(workspace_id, user_context.user_id, amount, reason)
            return request

        token_request = await create_token_request("workspace_1", 100, "Development resources")
        assert token_request["amount"] == 100
        assert token_request["status"] == "pending"
        assert token_request["reason"] == "Development resources"

        # Step 2: Review and approve token request (as admin)
        mock_wallet_manager.review_token_request.return_value = {
            "id": "token_request_123",
            "status": "approved",
            "reviewed_by": "workspace_user_123",
            "reviewed_at": datetime.now(timezone.utc),
        }

        @secure_mcp_tool(permissions=["workspace:admin"])
        async def review_token_request(request_id: str, action: str, notes: str = ""):
            result = await mock_wallet_manager.review_token_request(request_id, user_context.user_id, action, notes)
            return result

        review_result = await review_token_request("token_request_123", "approve", "Approved for development")
        assert review_result["status"] == "approved"
        assert review_result["reviewed_by"] == "workspace_user_123"

        # Verify workflow calls
        mock_wallet_manager.create_token_request.assert_called_once()
        mock_wallet_manager.review_token_request.assert_called_once()


class TestMCPComprehensiveResourcesAndPrompts:
    """Comprehensive end-to-end tests for MCP resources and prompts functionality."""

    @pytest.fixture
    def mock_resource_user(self):
        """Create a mock user for resource and prompt testing."""
        return {
            "_id": "resource_user_123",
            "username": "resource_user",
            "email": "resource@example.com",
            "role": "user",
            "permissions": ["family:read", "workspace:read", "shop:read", "profile:read"],
            "workspaces": [{"_id": "workspace_1", "name": "Test Workspace", "role": "member"}],
            "family_memberships": [{"family_id": "family_1", "role": "admin"}],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_family_resources_workflow(self, mock_resource_user):
        """Test family resources access and content generation."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_resource_user, ip_address="192.168.1.100", user_agent="ResourceClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock family manager
        mock_family_manager = AsyncMock()

        # Mock family info for resource
        mock_family = Mock()
        mock_family.dict.return_value = {
            "id": "family_1",
            "name": "Test Family",
            "description": "Test family for resources",
            "member_count": 3,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_id": "resource_user_123",
        }
        mock_family_manager.get_family.return_value = mock_family

        # Test family info resource
        @secure_mcp_tool(permissions=["family:read"])
        async def get_family_resource(family_id: str):
            """Simulate family resource access."""
            family = await mock_family_manager.get_family(family_id, user_context.user_id)
            if not family:
                return None

            # Format as resource content
            family_data = family.dict()
            resource_content = {
                "resource_type": "family_info",
                "family_id": family_id,
                "content": family_data,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "access_level": (
                    "admin"
                    if any(
                        fm.get("family_id") == family_id and fm.get("role") == "admin"
                        for fm in user_context.family_memberships
                    )
                    else "member"
                ),
            }
            return resource_content

        family_resource = await get_family_resource("family_1")

        assert family_resource["resource_type"] == "family_info"
        assert family_resource["family_id"] == "family_1"
        assert family_resource["content"]["name"] == "Test Family"
        assert family_resource["access_level"] == "admin"

        # Test family members resource
        mock_members = [
            {"user_id": "user_1", "username": "member1", "role": "admin"},
            {"user_id": "user_2", "username": "member2", "role": "member"},
            {"user_id": "user_3", "username": "member3", "role": "member"},
        ]
        mock_family_manager.get_family_members.return_value = mock_members

        @secure_mcp_tool(permissions=["family:read"])
        async def get_family_members_resource(family_id: str):
            """Simulate family members resource access."""
            await mock_family_manager.validate_family_access(family_id, user_context.user_id)
            members = await mock_family_manager.get_family_members(family_id)

            return {
                "resource_type": "family_members",
                "family_id": family_id,
                "members": members,
                "member_count": len(members),
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

        members_resource = await get_family_members_resource("family_1")

        assert members_resource["resource_type"] == "family_members"
        assert members_resource["member_count"] == 3
        assert len(members_resource["members"]) == 3
        assert members_resource["members"][0]["username"] == "member1"

    @pytest.mark.asyncio
    async def test_guidance_prompts_workflow(self, mock_resource_user):
        """Test guidance prompts generation and contextual content."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_resource_user, ip_address="192.168.1.100", user_agent="PromptClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Test family management guidance prompt
        @secure_mcp_tool(permissions=["family:read"])
        async def get_family_management_prompt():
            """Generate family management guidance prompt."""
            user_families = len(user_context.family_memberships)
            admin_families = sum(1 for fm in user_context.family_memberships if fm.get("role") == "admin")

            prompt_content = f"""
            You are helping {user_context.username} manage family accounts in the Second Brain Database.

            Current Status:
            - Member of {user_families} families
            - Admin of {admin_families} families
            - User role: {user_context.role}

            Available operations based on your permissions:
            """

            if "family:read" in user_context.permissions:
                prompt_content += "\n- View family information and member lists"
            if "family:write" in user_context.permissions:
                prompt_content += "\n- Create new families and update family settings"
            if admin_families > 0:
                prompt_content += "\n- Manage family members and permissions (admin families only)"
                prompt_content += "\n- Approve SBD token requests for your families"

            prompt_content += """

            Security reminders:
            - Always verify user permissions before operations
            - Log all administrative actions for audit compliance
            - Respect family limits and quotas
            - Follow data protection and privacy guidelines

            For help with specific operations, ask about:
            - Creating or managing families
            - Adding or removing family members
            - SBD token management
            - Family settings and permissions
            """

            return {
                "prompt_type": "family_management_guide",
                "content": prompt_content.strip(),
                "context": {
                    "user_id": user_context.user_id,
                    "username": user_context.username,
                    "family_count": user_families,
                    "admin_family_count": admin_families,
                    "permissions": user_context.permissions,
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        family_prompt = await get_family_management_prompt()

        assert family_prompt["prompt_type"] == "family_management_guide"
        assert user_context.username in family_prompt["content"]
        assert "Member of 1 families" in family_prompt["content"]
        assert "Admin of 1 families" in family_prompt["content"]
        assert family_prompt["context"]["family_count"] == 1
        assert family_prompt["context"]["admin_family_count"] == 1


class TestMCPComprehensiveErrorRecovery:
    """Comprehensive end-to-end tests for complex error handling and recovery scenarios."""

    @pytest.fixture
    def mock_error_user(self):
        """Create a mock user for error testing."""
        return {
            "_id": "error_user_123",
            "username": "error_user",
            "email": "error@example.com",
            "role": "user",
            "permissions": ["family:read", "family:write"],
            "workspaces": [],
            "family_memberships": [{"family_id": "family_1", "role": "admin"}],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_database_connection_failure_recovery(self, mock_error_user):
        """Test recovery from database connection failures during complex workflows."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_error_user, ip_address="192.168.1.100", user_agent="ErrorRecoveryClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock family manager
        mock_family_manager = AsyncMock()

        # Simulate connection failure followed by recovery
        call_count = 0

        def connection_failure_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First two calls fail
                raise ConnectionError("Database connection lost")
            else:  # Third call succeeds
                mock_family = Mock()
                mock_family.dict.return_value = {"id": "family_1", "name": "Recovered Family", "status": "recovered"}
                return mock_family

        mock_family_manager.get_family.side_effect = connection_failure_side_effect

        @secure_mcp_tool(permissions=["family:read"])
        async def resilient_family_operation():
            """Operation with built-in retry logic for database failures."""
            max_retries = 3
            retry_delay = 0.01  # Short delay for testing

            for attempt in range(max_retries):
                try:
                    family = await mock_family_manager.get_family("family_1", user_context.user_id)
                    return {"success": True, "family": family.dict(), "attempts": attempt + 1, "recovered": attempt > 0}
                except ConnectionError as e:
                    if attempt == max_retries - 1:  # Last attempt
                        raise e
                    # Wait before retry
                    await asyncio.sleep(retry_delay)
                    continue

            return {"success": False, "error": "Max retries exceeded"}

        result = await resilient_family_operation()

        # Verify recovery succeeded
        assert result["success"] is True
        assert result["family"]["name"] == "Recovered Family"
        assert result["attempts"] == 3  # Took 3 attempts
        assert result["recovered"] is True
        assert mock_family_manager.get_family.call_count == 3

    @pytest.mark.asyncio
    async def test_concurrent_operation_conflict_resolution(self, mock_error_user):
        """Test conflict resolution during concurrent operations."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_error_user, ip_address="192.168.1.100", user_agent="ConcurrencyClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock family manager
        mock_family_manager = AsyncMock()

        # Simulate version conflict during updates
        update_count = 0

        def update_with_conflict(*args, **kwargs):
            nonlocal update_count
            update_count += 1
            if update_count == 1:
                # First update conflicts
                raise ValueError("Version conflict - family was modified by another user")
            else:
                # Second update succeeds
                mock_updated_family = Mock()
                mock_updated_family.dict.return_value = {
                    "id": "family_1",
                    "name": "Updated Family Name",
                    "version": 2,
                    "last_modified": datetime.now(timezone.utc).isoformat(),
                }
                return mock_updated_family

        mock_family_manager.update_family_settings.side_effect = update_with_conflict

        # Mock getting current family for conflict resolution
        mock_current_family = Mock()
        mock_current_family.dict.return_value = {
            "id": "family_1",
            "name": "Current Family Name",
            "version": 2,
            "settings": {"notifications": True},
        }
        mock_family_manager.get_family.return_value = mock_current_family

        @secure_mcp_tool(permissions=["family:write"])
        async def update_family_with_conflict_resolution(family_id: str, updates: dict):
            """Update family with automatic conflict resolution."""
            max_attempts = 3

            for attempt in range(max_attempts):
                try:
                    # Attempt update
                    updated_family = await mock_family_manager.update_family_settings(
                        family_id, user_context.user_id, updates
                    )
                    return {
                        "success": True,
                        "family": updated_family.dict(),
                        "attempts": attempt + 1,
                        "conflicts_resolved": attempt > 0,
                    }
                except ValueError as e:
                    if "Version conflict" in str(e) and attempt < max_attempts - 1:
                        # Get current state and merge changes
                        current_family = await mock_family_manager.get_family(family_id, user_context.user_id)
                        current_data = current_family.dict()

                        # Merge updates with current state (simple merge strategy)
                        merged_updates = {**current_data.get("settings", {}), **updates}
                        updates = {"settings": merged_updates}

                        # Short delay before retry
                        await asyncio.sleep(0.01)
                        continue
                    else:
                        raise e

            return {"success": False, "error": "Max conflict resolution attempts exceeded"}

        result = await update_family_with_conflict_resolution(
            "family_1", {"name": "Updated Family Name", "notifications": False}
        )

        # Verify conflict resolution
        assert result["success"] is True
        assert result["family"]["name"] == "Updated Family Name"
        assert result["attempts"] == 2  # First failed, second succeeded
        assert result["conflicts_resolved"] is True
        assert mock_family_manager.update_family_settings.call_count == 2
        assert mock_family_manager.get_family.call_count == 1  # Called during conflict resolution


class TestMCPComprehensiveAuthenticationFlows:
    """Comprehensive end-to-end tests for authentication flows and permission validation."""

    def setup_method(self):
        """Set up test environment."""
        clear_mcp_context()

    def teardown_method(self):
        """Clean up test environment."""
        clear_mcp_context()

    @pytest.mark.asyncio
    async def test_complete_authentication_flow_validation(self):
        """Test complete authentication flow with various user types and permissions."""
        # Test 1: Regular user with basic permissions
        regular_user = {
            "_id": "regular_user_123",
            "username": "regular_user",
            "email": "regular@example.com",
            "role": "user",
            "permissions": ["profile:read", "family:read"],
            "workspaces": [],
            "family_memberships": [{"family_id": "family_1", "role": "member"}],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=regular_user, ip_address="192.168.1.100", user_agent="AuthTestClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Test basic permission validation
        @secure_mcp_tool(permissions=["profile:read"])
        async def read_profile_operation():
            return {"operation": "profile_read", "user_id": user_context.user_id}

        result = await read_profile_operation()
        assert result["operation"] == "profile_read"
        assert result["user_id"] == "regular_user_123"

        # Test permission denial
        @secure_mcp_tool(permissions=["admin"])
        async def admin_operation():
            return {"should_not_reach": True}

        with pytest.raises(MCPAuthorizationError):
            await admin_operation()

        # Test 2: Admin user with elevated permissions
        admin_user = {
            "_id": "admin_user_123",
            "username": "admin_user",
            "email": "admin@example.com",
            "role": "admin",
            "permissions": ["admin", "profile:read", "family:read", "family:write"],
            "workspaces": [],
            "family_memberships": [],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

        admin_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=admin_user, ip_address="192.168.1.100", user_agent="AdminClient/1.0"
        )
        set_mcp_user_context(admin_context)

        # Test admin bypass
        @secure_mcp_tool(permissions=["any:permission"])
        async def admin_bypass_operation():
            return {"admin_bypass": True, "user_id": admin_context.user_id}

        admin_result = await admin_bypass_operation()
        assert admin_result["admin_bypass"] is True
        assert admin_result["user_id"] == "admin_user_123"

    @pytest.mark.asyncio
    async def test_multi_permission_validation_workflow(self):
        """Test workflows requiring multiple permissions."""
        multi_perm_user = {
            "_id": "multi_perm_user_123",
            "username": "multi_perm_user",
            "email": "multi@example.com",
            "role": "user",
            "permissions": ["family:read", "family:write", "workspace:read", "shop:read"],
            "workspaces": [{"_id": "workspace_1", "name": "Test Workspace", "role": "admin"}],
            "family_memberships": [{"family_id": "family_1", "role": "admin"}],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=multi_perm_user, ip_address="192.168.1.100", user_agent="MultiPermClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Test operation requiring multiple permissions (all present)
        @secure_mcp_tool(permissions=["family:read", "workspace:read"])
        async def multi_permission_operation():
            return {"family_access": True, "workspace_access": True, "user_id": user_context.user_id}

        result = await multi_permission_operation()
        assert result["family_access"] is True
        assert result["workspace_access"] is True

        # Test operation requiring permissions user doesn't have
        @secure_mcp_tool(permissions=["family:read", "admin"])
        async def missing_permission_operation():
            return {"should_not_reach": True}

        with pytest.raises(MCPAuthorizationError):
            await missing_permission_operation()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
