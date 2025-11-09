#!/usr/bin/env python3
"""
End-to-end tests for complete MCP workflows.

Tests complete MCP workflows from authentication through tool execution
to audit logging, simulating real-world usage scenarios.
"""

import asyncio
from datetime import datetime, timezone
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

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
from second_brain_database.integrations.mcp.exceptions import (
    MCPAuthenticationError,
    MCPAuthorizationError,
    MCPRateLimitError,
)
from second_brain_database.integrations.mcp.security import authenticated_tool, mcp_audit_logger, secure_mcp_tool

# Test imports
from second_brain_database.integrations.mcp.server import MCPServerManager


class TestMCPEndToEndWorkflows:
    """End-to-end tests for complete MCP workflows."""

    @pytest.fixture
    def mock_fastapi_user(self):
        """Create a mock FastAPI user object."""
        return {
            "_id": "e2e_user_123",
            "username": "e2e_test_user",
            "email": "e2e@example.com",
            "role": "user",
            "permissions": ["family:read", "family:write", "profile:read"],
            "workspaces": [{"_id": "workspace_1", "name": "Test Workspace", "role": "member"}],
            "family_memberships": [
                {"family_id": "family_1", "role": "admin"},
                {"family_id": "family_2", "role": "member"},
            ],
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "trusted_ips": [],
            "trusted_user_agents": [],
        }

    @pytest.fixture
    def mock_admin_user(self):
        """Create a mock admin FastAPI user object."""
        return {
            "_id": "admin_e2e_123",
            "username": "admin_e2e_user",
            "email": "admin_e2e@example.com",
            "role": "admin",
            "permissions": ["admin", "family:read", "family:write", "profile:read", "system:read"],
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
    async def test_complete_family_management_workflow(self, mock_fastapi_user):
        """Test complete family management workflow from authentication to audit."""
        # Step 1: Create user context from FastAPI user
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_fastapi_user,
            ip_address="192.168.1.100",
            user_agent="E2ETestClient/1.0",
            token_type="jwt",
            token_id="jwt_e2e_123",
        )

        # Step 2: Create request context
        request_context = create_mcp_request_context(
            operation_type="tool",
            tool_name="family_management_workflow",
            parameters={"family_id": "family_1", "action": "get_info"},
        )

        # Step 3: Set contexts
        set_mcp_user_context(user_context)
        set_mcp_request_context(request_context)

        # Step 4: Mock family manager and dependencies
        with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

            # Mock family data
            mock_family = Mock()
            mock_family.dict.return_value = {
                "id": "family_1",
                "name": "E2E Test Family",
                "description": "End-to-end test family",
                "owner_id": "e2e_user_123",
                "member_count": 3,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_family_manager.get_family.return_value = mock_family

            # Step 5: Execute secured family tool
            @secure_mcp_tool(permissions=["family:read"], audit=True)
            async def get_family_workflow():
                # Simulate family manager call
                family_info = await mock_family_manager.get_family("family_1", user_context.user_id)
                return family_info.dict() if family_info else None

            # Step 6: Execute workflow
            result = await get_family_workflow()

            # Step 7: Verify workflow results
            assert result is not None
            assert result["id"] == "family_1"
            assert result["name"] == "E2E Test Family"
            assert result["owner_id"] == "e2e_user_123"

            # Step 8: Verify manager was called correctly
            mock_family_manager.get_family.assert_called_once_with("family_1", "e2e_user_123")

            # Step 9: Verify context state
            final_user_context = get_mcp_user_context()
            final_request_context = get_mcp_request_context()

            assert final_user_context.user_id == "e2e_user_123"
            assert final_request_context.tool_name == "family_management_workflow"
            assert final_request_context.security_checks_passed is True

    @pytest.mark.asyncio
    async def test_multi_step_family_operations_workflow(self, mock_fastapi_user):
        """Test multi-step family operations workflow."""
        # Create user context
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_fastapi_user, ip_address="192.168.1.100", user_agent="MultiStepClient/1.0"
        )
        set_mcp_user_context(user_context)

        workflow_results = []

        # Mock family manager for all operations
        with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

            # Step 1: Get family info
            mock_family = Mock()
            mock_family.dict.return_value = {"id": "family_1", "name": "Multi-Step Family"}
            mock_family_manager.get_family.return_value = mock_family

            @secure_mcp_tool(permissions=["family:read"])
            async def step1_get_family():
                family = await mock_family_manager.get_family("family_1", user_context.user_id)
                return family.dict()

            result1 = await step1_get_family()
            workflow_results.append(("get_family", result1))

            # Step 2: Get family members
            mock_members = [
                {"user_id": "user_1", "username": "member1", "role": "admin"},
                {"user_id": "user_2", "username": "member2", "role": "member"},
            ]
            mock_family_manager.validate_family_access.return_value = True
            mock_family_manager.get_family_members.return_value = mock_members

            @secure_mcp_tool(permissions=["family:read"])
            async def step2_get_members():
                await mock_family_manager.validate_family_access("family_1", user_context.user_id)
                members = await mock_family_manager.get_family_members("family_1")
                return members

            result2 = await step2_get_members()
            workflow_results.append(("get_members", result2))

            # Step 3: Update family settings (requires write permission)
            mock_updated_family = Mock()
            mock_updated_family.dict.return_value = {"id": "family_1", "name": "Updated Family"}
            mock_family_manager.update_family_settings.return_value = mock_updated_family

            @secure_mcp_tool(permissions=["family:write"])
            async def step3_update_family():
                updated = await mock_family_manager.update_family_settings(
                    "family_1", user_context.user_id, {"name": "Updated Family"}
                )
                return updated.dict()

            result3 = await step3_update_family()
            workflow_results.append(("update_family", result3))

            # Verify all steps completed successfully
            assert len(workflow_results) == 3
            assert workflow_results[0][0] == "get_family"
            assert workflow_results[1][0] == "get_members"
            assert workflow_results[2][0] == "update_family"

            # Verify manager calls
            assert mock_family_manager.get_family.call_count == 1
            assert mock_family_manager.get_family_members.call_count == 1
            assert mock_family_manager.update_family_settings.call_count == 1

    @pytest.mark.asyncio
    async def test_authentication_failure_workflow(self):
        """Test workflow when authentication fails."""
        # Don't set user context to simulate authentication failure

        @secure_mcp_tool(permissions=["family:read"])
        async def unauthenticated_tool():
            return {"should_not_reach": True}

        # Verify authentication error is raised
        with pytest.raises(MCPAuthenticationError) as exc_info:
            await unauthenticated_tool()

        assert "Authentication required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authorization_failure_workflow(self, mock_fastapi_user):
        """Test workflow when authorization fails."""
        # Create user context with limited permissions
        limited_user = mock_fastapi_user.copy()
        limited_user["permissions"] = ["profile:read"]  # No family permissions

        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=limited_user, ip_address="192.168.1.100", user_agent="LimitedClient/1.0"
        )
        set_mcp_user_context(user_context)

        @secure_mcp_tool(permissions=["family:write", "admin"])
        async def unauthorized_tool():
            return {"should_not_reach": True}

        # Verify authorization error is raised
        with pytest.raises(MCPAuthorizationError) as exc_info:
            await unauthorized_tool()

        assert "Missing required permissions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_rate_limiting_workflow(self, mock_fastapi_user):
        """Test workflow with rate limiting."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_fastapi_user, ip_address="192.168.1.100", user_agent="RateLimitClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock rate limiting to exceed limit
        with patch("src.second_brain_database.integrations.mcp.security.security_manager") as mock_sm:
            from fastapi import HTTPException

            mock_sm.check_rate_limit = AsyncMock(
                side_effect=HTTPException(status_code=429, detail="Rate limit exceeded")
            )

            @secure_mcp_tool(rate_limit_action="test_rate_limit")
            async def rate_limited_tool():
                return {"should_not_reach": True}

            # Verify rate limit error is raised
            with pytest.raises(MCPRateLimitError) as exc_info:
                await rate_limited_tool()

            assert "Rate limit exceeded" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_admin_workflow_with_elevated_permissions(self, mock_admin_user):
        """Test admin workflow with elevated permissions."""
        admin_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_admin_user, ip_address="192.168.1.100", user_agent="AdminClient/1.0"
        )
        set_mcp_user_context(admin_context)

        # Mock system operations that require admin permissions
        with patch("src.second_brain_database.integrations.mcp.tools.admin_tools.get_system_health") as mock_health:
            mock_health.return_value = {
                "status": "healthy",
                "uptime": 3600,
                "active_users": 150,
                "database_status": "connected",
            }

            @secure_mcp_tool(permissions=["admin", "system:read"])
            async def admin_system_check():
                return await mock_health()

            result = await admin_system_check()

            # Verify admin operation succeeded
            assert result["status"] == "healthy"
            assert result["active_users"] == 150
            mock_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_concurrent_user_workflows(self, mock_fastapi_user):
        """Test concurrent workflows from different users."""

        async def user_workflow(user_id: str, family_id: str):
            # Create unique user context
            user_data = mock_fastapi_user.copy()
            user_data["_id"] = user_id
            user_data["username"] = f"user_{user_id}"

            user_context = await create_mcp_user_context_from_fastapi_user(
                fastapi_user=user_data,
                ip_address=f"192.168.1.{user_id[-1]}",
                user_agent=f"ConcurrentClient_{user_id}/1.0",
            )

            request_context = create_mcp_request_context(
                operation_type="tool", tool_name=f"concurrent_workflow_{user_id}", parameters={"family_id": family_id}
            )

            set_mcp_user_context(user_context)
            set_mcp_request_context(request_context)

            # Mock family manager for this user
            with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
                mock_family_manager = AsyncMock()
                mock_fm.return_value = mock_family_manager

                mock_family = Mock()
                mock_family.dict.return_value = {"id": family_id, "name": f"Family for {user_id}", "owner_id": user_id}
                mock_family_manager.get_family.return_value = mock_family

                @secure_mcp_tool(permissions=["family:read"])
                async def concurrent_family_tool():
                    # Simulate some processing time
                    await asyncio.sleep(0.01)
                    family = await mock_family_manager.get_family(family_id, user_id)
                    return {"user_id": user_id, "family_data": family.dict(), "timestamp": time.time()}

                return await concurrent_family_tool()

        # Execute concurrent workflows
        tasks = [
            user_workflow("user_001", "family_001"),
            user_workflow("user_002", "family_002"),
            user_workflow("user_003", "family_003"),
        ]

        results = await asyncio.gather(*tasks)

        # Verify all workflows completed successfully
        assert len(results) == 3
        for i, result in enumerate(results, 1):
            expected_user_id = f"user_00{i}"
            expected_family_id = f"family_00{i}"

            assert result["user_id"] == expected_user_id
            assert result["family_data"]["id"] == expected_family_id
            assert result["family_data"]["owner_id"] == expected_user_id
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_audit_logging_workflow(self, mock_fastapi_user):
        """Test complete audit logging workflow."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_fastapi_user, ip_address="192.168.1.100", user_agent="AuditClient/1.0"
        )
        set_mcp_user_context(user_context)

        audit_events = []

        # Mock audit logging to capture events
        with patch("src.second_brain_database.integrations.mcp.security._log_mcp_tool_execution") as mock_audit:
            mock_audit.side_effect = lambda *args, **kwargs: audit_events.append(("tool_execution", args, kwargs))

            with patch(
                "src.second_brain_database.integrations.mcp.security.log_mcp_security_event"
            ) as mock_security_log:
                mock_security_log.side_effect = lambda *args, **kwargs: audit_events.append(
                    ("security_event", args, kwargs)
                )

                @secure_mcp_tool(permissions=["family:read"], audit=True)
                async def audited_tool():
                    return {"audited_operation": True, "timestamp": time.time()}

                result = await audited_tool()

                # Verify operation succeeded
                assert result["audited_operation"] is True

                # Verify audit events were logged
                assert len(audit_events) >= 1  # At least tool execution should be logged

                # Check for tool execution audit
                tool_execution_events = [event for event in audit_events if event[0] == "tool_execution"]
                assert len(tool_execution_events) >= 1

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(self, mock_fastapi_user):
        """Test error recovery in MCP workflows."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_fastapi_user, ip_address="192.168.1.100", user_agent="ErrorRecoveryClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Test workflow that encounters and recovers from errors
        with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

            # First call fails, second succeeds (simulating retry logic)
            call_count = 0

            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise ConnectionError("Database temporarily unavailable")
                else:
                    mock_family = Mock()
                    mock_family.dict.return_value = {"id": "family_1", "name": "Recovered Family"}
                    return mock_family

            mock_family_manager.get_family.side_effect = side_effect

            @secure_mcp_tool(permissions=["family:read"])
            async def error_recovery_tool():
                try:
                    family = await mock_family_manager.get_family("family_1", user_context.user_id)
                    return family.dict()
                except ConnectionError:
                    # Simulate retry logic
                    await asyncio.sleep(0.01)
                    family = await mock_family_manager.get_family("family_1", user_context.user_id)
                    return family.dict()

            result = await error_recovery_tool()

            # Verify recovery succeeded
            assert result["name"] == "Recovered Family"
            assert mock_family_manager.get_family.call_count == 2

    @pytest.mark.asyncio
    async def test_mcp_server_lifecycle_workflow(self):
        """Test MCP server lifecycle in workflow context."""
        server_manager = MCPServerManager()

        # Test server initialization
        with patch("src.second_brain_database.integrations.mcp.server.FastMCP") as mock_fastmcp:
            mock_mcp_instance = Mock()
            mock_fastmcp.return_value = mock_mcp_instance

            # Mock monitoring systems
            with patch(
                "src.second_brain_database.integrations.mcp.server.mcp_monitoring_integration"
            ) as mock_monitoring:
                mock_monitoring.initialize = AsyncMock()
                mock_monitoring.start_monitoring = AsyncMock()
                mock_monitoring.stop_monitoring = AsyncMock()

                # Initialize server
                await server_manager.initialize()
                assert server_manager.is_initialized is True

                # Start server
                with patch.object(server_manager, "_create_mock_process") as mock_process:
                    mock_proc = Mock()
                    mock_proc.pid = 12345
                    mock_proc.returncode = None
                    mock_process.return_value = mock_proc

                    process = await server_manager.start_server(port=3001)
                    assert process is not None
                    assert server_manager.is_running is True

                # Get server status
                status = await server_manager.get_server_status()
                assert status["initialized"] is True
                assert status["running"] is True
                assert status["port"] == 3001

                # Health check
                health = await server_manager.health_check()
                assert health["healthy"] is True

                # Stop server
                await server_manager.stop_server()
                assert server_manager.is_running is False


class TestMCPWorkflowPerformance:
    """Performance tests for MCP workflows."""

    @pytest.mark.asyncio
    async def test_workflow_performance_under_load(self):
        """Test MCP workflow performance under concurrent load."""

        async def single_workflow(workflow_id: int):
            # Create user context
            user_context = MCPUserContext(
                user_id=f"perf_user_{workflow_id}",
                username=f"perf_user_{workflow_id}",
                permissions=["family:read"],
                ip_address="127.0.0.1",
                user_agent="PerfTestClient/1.0",
            )

            request_context = create_mcp_request_context(operation_type="tool", tool_name=f"perf_tool_{workflow_id}")

            set_mcp_user_context(user_context)
            set_mcp_request_context(request_context)

            start_time = time.time()

            @secure_mcp_tool(permissions=["family:read"])
            async def perf_tool():
                # Simulate some work
                await asyncio.sleep(0.001)
                return {"workflow_id": workflow_id, "completed": True}

            result = await perf_tool()
            end_time = time.time()

            return {"workflow_id": workflow_id, "result": result, "duration": end_time - start_time}

        # Execute multiple concurrent workflows
        num_workflows = 50
        start_time = time.time()

        tasks = [single_workflow(i) for i in range(num_workflows)]
        results = await asyncio.gather(*tasks)

        total_time = time.time() - start_time

        # Verify all workflows completed
        assert len(results) == num_workflows
        for i, result in enumerate(results):
            assert result["workflow_id"] == i
            assert result["result"]["completed"] is True
            assert result["duration"] < 1.0  # Each workflow should complete quickly

        # Verify overall performance
        assert total_time < 5.0  # All workflows should complete within 5 seconds
        avg_duration = sum(r["duration"] for r in results) / len(results)
        assert avg_duration < 0.1  # Average workflow duration should be reasonable


class TestMCPShopWorkflows:
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

        # Mock database manager directly instead of importing shop_tools
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
        mock_shop_collection.find.return_value.to_list.return_value = mock_shop_items

        @secure_mcp_tool(permissions=["shop:read"])
        async def browse_shop_items():
            items = await mock_shop_collection.find({"available": True}).to_list(length=None)
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

        with patch("src.second_brain_database.integrations.mcp.tools.shop_tools.db_manager") as mock_db:
            mock_rentals_collection = AsyncMock()
            mock_users_collection = AsyncMock()
            mock_shop_collection = AsyncMock()

            def get_collection_side_effect(name):
                collections = {
                    "asset_rentals": mock_rentals_collection,
                    "users": mock_users_collection,
                    "shop_items": mock_shop_collection,
                }
                return collections.get(name, AsyncMock())

            mock_db.get_collection.side_effect = get_collection_side_effect

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
            mock_shop_collection.find.return_value.to_list.return_value = [mock_rental_item]

            @secure_mcp_tool(permissions=["shop:read"])
            async def browse_rental_items():
                items = await mock_shop_collection.find({"available_for_rental": True}).to_list(length=None)
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
                rental_end = datetime.now(timezone.utc)
                if duration == "weekly":
                    rental_end = rental_end.replace(day=rental_end.day + 7)

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

            rental_result = await rent_asset("banner_rental_123", "weekly")

            # Step 3: Verify rental workflow
            assert rental_result["status"] == "active"
            assert rental_result["cost"] == 50
            assert rental_result["duration"] == "weekly"

            # Verify database operations
            mock_rentals_collection.insert_one.assert_called_once()
            mock_users_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_shop_error_handling_workflow(self, mock_shop_user):
        """Test shop workflow error handling and recovery."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_shop_user, ip_address="192.168.1.100", user_agent="ErrorTestClient/1.0"
        )
        set_mcp_user_context(user_context)

        with patch("src.second_brain_database.integrations.mcp.tools.shop_tools.db_manager") as mock_db:
            mock_shop_collection = AsyncMock()
            mock_users_collection = AsyncMock()
            mock_db.get_collection.return_value = mock_shop_collection

            # Test insufficient balance error
            mock_expensive_item = {
                "_id": "expensive_item_123",
                "name": "Expensive Theme",
                "price": 2000,  # More than user's balance
                "item_type": "theme",
            }
            mock_shop_collection.find_one.return_value = mock_expensive_item

            mock_user_doc = {"_id": "shop_user_123", "sbd_balance": 1000}
            mock_users_collection.find_one.return_value = mock_user_doc

            @secure_mcp_tool(permissions=["shop:purchase"])
            async def purchase_expensive_item(item_id: str):
                item = await mock_shop_collection.find_one({"_id": item_id})
                user = await mock_users_collection.find_one({"_id": user_context.user_id})

                if user["sbd_balance"] < item["price"]:
                    raise ValueError(
                        f"Insufficient balance. Required: {item['price']}, Available: {user['sbd_balance']}"
                    )

                return {"status": "success"}

            # Test error handling
            with pytest.raises(ValueError) as exc_info:
                await purchase_expensive_item("expensive_item_123")

            assert "Insufficient balance" in str(exc_info.value)
            assert "Required: 2000" in str(exc_info.value)
            assert "Available: 1000" in str(exc_info.value)


class TestMCPWorkspaceWorkflows:
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

        with patch("src.second_brain_database.integrations.mcp.tools.workspace_tools.WorkspaceManager") as mock_wm:
            mock_workspace_manager = AsyncMock()
            mock_wm.return_value = mock_workspace_manager

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

            # Step 4: Manage workspace wallet
            mock_wallet_info = {
                "workspace_id": "new_workspace_123",
                "balance": 500,
                "frozen": False,
                "permissions": {"can_request": True, "can_approve": True},
            }
            mock_workspace_manager.get_workspace_wallet.return_value = mock_wallet_info

            @secure_mcp_tool(permissions=["workspace:read"])
            async def get_workspace_wallet(workspace_id: str):
                await mock_workspace_manager.validate_workspace_access(workspace_id, user_context.user_id)
                wallet = await mock_workspace_manager.get_workspace_wallet(workspace_id, user_context.user_id)
                return wallet

            wallet_info = await get_workspace_wallet("new_workspace_123")
            assert wallet_info["balance"] == 500
            assert wallet_info["frozen"] is False

            # Step 5: Delete workspace (cleanup)
            mock_workspace_manager.delete_workspace.return_value = True

            @secure_mcp_tool(permissions=["workspace:admin"])
            async def delete_workspace(workspace_id: str, confirm: bool = False):
                if not confirm:
                    raise ValueError("Deletion must be confirmed")

                await mock_workspace_manager.validate_workspace_access(workspace_id, user_context.user_id, "admin")
                result = await mock_workspace_manager.delete_workspace(workspace_id, user_context.user_id)
                return {"deleted": result, "workspace_id": workspace_id}

            deletion_result = await delete_workspace("new_workspace_123", confirm=True)
            assert deletion_result["deleted"] is True
            assert deletion_result["workspace_id"] == "new_workspace_123"

            # Verify all manager calls
            mock_workspace_manager.create_workspace.assert_called_once()
            mock_workspace_manager.add_workspace_member.assert_called_once()
            mock_workspace_manager.update_workspace.assert_called_once()
            mock_workspace_manager.get_workspace_wallet.assert_called_once()
            mock_workspace_manager.delete_workspace.assert_called_once()

    @pytest.mark.asyncio
    async def test_workspace_token_request_workflow(self, mock_workspace_user):
        """Test workspace SBD token request and approval workflow."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_workspace_user, ip_address="192.168.1.100", user_agent="TokenClient/1.0"
        )
        set_mcp_user_context(user_context)

        with patch("src.second_brain_database.integrations.mcp.tools.workspace_tools.TeamWalletManager") as mock_twm:
            mock_wallet_manager = AsyncMock()
            mock_twm.return_value = mock_wallet_manager

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
                request = await mock_wallet_manager.create_token_request(
                    workspace_id, user_context.user_id, amount, reason
                )
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

            # Step 3: Get updated workspace wallet balance
            mock_wallet_manager.get_workspace_wallet.return_value = {
                "workspace_id": "workspace_1",
                "balance": 600,  # Increased after approval
                "pending_requests": 0,
            }

            @secure_mcp_tool(permissions=["workspace:read"])
            async def get_updated_wallet(workspace_id: str):
                wallet = await mock_wallet_manager.get_workspace_wallet(workspace_id, user_context.user_id)
                return wallet

            updated_wallet = await get_updated_wallet("workspace_1")
            assert updated_wallet["balance"] == 600
            assert updated_wallet["pending_requests"] == 0

            # Verify workflow calls
            mock_wallet_manager.create_token_request.assert_called_once()
            mock_wallet_manager.review_token_request.assert_called_once()
            mock_wallet_manager.get_workspace_wallet.assert_called_once()


class TestMCPResourcesAndPrompts:
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

        # Mock family resource data
        with patch("src.second_brain_database.integrations.mcp.resources.family_resources.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

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
    async def test_workspace_resources_workflow(self, mock_resource_user):
        """Test workspace resources access and content generation."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_resource_user, ip_address="192.168.1.100", user_agent="WorkspaceResourceClient/1.0"
        )
        set_mcp_user_context(user_context)

        with patch(
            "src.second_brain_database.integrations.mcp.resources.workspace_resources.WorkspaceManager"
        ) as mock_wm:
            mock_workspace_manager = AsyncMock()
            mock_wm.return_value = mock_workspace_manager

            # Mock workspace info
            mock_workspace = {
                "_id": "workspace_1",
                "name": "Test Workspace",
                "description": "Test workspace for resources",
                "owner_id": "other_user_456",
                "member_count": 5,
                "created_at": datetime.now(timezone.utc),
            }
            mock_workspace_manager.get_workspace_details.return_value = mock_workspace

            @secure_mcp_tool(permissions=["workspace:read"])
            async def get_workspace_resource(workspace_id: str):
                """Simulate workspace resource access."""
                workspace = await mock_workspace_manager.get_workspace_details(workspace_id, user_context.user_id)

                return {
                    "resource_type": "workspace_info",
                    "workspace_id": workspace_id,
                    "content": workspace,
                    "user_role": next(
                        (ws.get("role") for ws in user_context.workspaces if ws.get("_id") == workspace_id), "none"
                    ),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }

            workspace_resource = await get_workspace_resource("workspace_1")

            assert workspace_resource["resource_type"] == "workspace_info"
            assert workspace_resource["workspace_id"] == "workspace_1"
            assert workspace_resource["content"]["name"] == "Test Workspace"
            assert workspace_resource["user_role"] == "member"

    @pytest.mark.asyncio
    async def test_shop_resources_workflow(self, mock_resource_user):
        """Test shop resources access and content generation."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_resource_user, ip_address="192.168.1.100", user_agent="ShopResourceClient/1.0"
        )
        set_mcp_user_context(user_context)

        with patch("src.second_brain_database.integrations.mcp.resources.shop_resources.db_manager") as mock_db:
            mock_shop_collection = AsyncMock()
            mock_db.get_collection.return_value = mock_shop_collection

            # Mock shop catalog
            mock_shop_items = [
                {"_id": "theme_1", "name": "Dark Theme", "price": 100, "item_type": "theme", "featured": True},
                {"_id": "avatar_1", "name": "Cool Avatar", "price": 50, "item_type": "avatar", "featured": False},
            ]
            mock_shop_collection.find.return_value.to_list.return_value = mock_shop_items

            @secure_mcp_tool(permissions=["shop:read"])
            async def get_shop_catalog_resource():
                """Simulate shop catalog resource access."""
                items = await mock_shop_collection.find({"available": True}).to_list(length=None)

                # Categorize items
                categories = {}
                for item in items:
                    item_type = item["item_type"]
                    if item_type not in categories:
                        categories[item_type] = []
                    categories[item_type].append(item)

                return {
                    "resource_type": "shop_catalog",
                    "total_items": len(items),
                    "categories": categories,
                    "featured_items": [item for item in items if item.get("featured", False)],
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }

            catalog_resource = await get_shop_catalog_resource()

            assert catalog_resource["resource_type"] == "shop_catalog"
            assert catalog_resource["total_items"] == 2
            assert "theme" in catalog_resource["categories"]
            assert "avatar" in catalog_resource["categories"]
            assert len(catalog_resource["featured_items"]) == 1

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

        # Test workspace management guidance prompt
        @secure_mcp_tool(permissions=["workspace:read"])
        async def get_workspace_management_prompt():
            """Generate workspace management guidance prompt."""
            user_workspaces = len(user_context.workspaces)
            admin_workspaces = sum(1 for ws in user_context.workspaces if ws.get("role") == "admin")

            prompt_content = f"""
            You are helping {user_context.username} manage workspace accounts in the Second Brain Database.

            Current Status:
            - Member of {user_workspaces} workspaces
            - Admin of {admin_workspaces} workspaces

            Available workspace operations:
            - View workspace information and member lists
            - Access workspace SBD wallet information
            - Request SBD tokens for workspace projects
            """

            if admin_workspaces > 0:
                prompt_content += """
            - Manage workspace members and roles (admin workspaces only)
            - Approve SBD token requests
            - Update workspace settings and configuration
                """

            prompt_content += """

            Best practices:
            - Coordinate with team members before making changes
            - Document token requests with clear justification
            - Monitor workspace resource usage
            - Maintain workspace security and access controls
            """

            return {
                "prompt_type": "workspace_management_guide",
                "content": prompt_content.strip(),
                "context": {
                    "user_id": user_context.user_id,
                    "username": user_context.username,
                    "workspace_count": user_workspaces,
                    "admin_workspace_count": admin_workspaces,
                },
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        workspace_prompt = await get_workspace_management_prompt()

        assert workspace_prompt["prompt_type"] == "workspace_management_guide"
        assert user_context.username in workspace_prompt["content"]
        assert "Member of 1 workspaces" in workspace_prompt["content"]
        assert "Admin of 0 workspaces" in workspace_prompt["content"]
        assert workspace_prompt["context"]["workspace_count"] == 1
        assert workspace_prompt["context"]["admin_workspace_count"] == 0


class TestMCPComplexErrorRecovery:
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

        # Simulate database connection failures with recovery
        with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

            # Simulate connection failure followed by recovery
            call_count = 0

            def connection_failure_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:  # First two calls fail
                    raise ConnectionError("Database connection lost")
                else:  # Third call succeeds
                    mock_family = Mock()
                    mock_family.dict.return_value = {
                        "id": "family_1",
                        "name": "Recovered Family",
                        "status": "recovered",
                    }
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
                        return {
                            "success": True,
                            "family": family.dict(),
                            "attempts": attempt + 1,
                            "recovered": attempt > 0,
                        }
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
    async def test_partial_service_failure_graceful_degradation(self, mock_error_user):
        """Test graceful degradation when some services are unavailable."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_error_user, ip_address="192.168.1.100", user_agent="DegradationClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Mock multiple services with some failing
        with (
            patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm,
            patch("src.second_brain_database.integrations.mcp.tools.family_tools.redis_manager") as mock_redis,
        ):

            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

            # Family service works
            mock_family = Mock()
            mock_family.dict.return_value = {"id": "family_1", "name": "Test Family", "member_count": 3}
            mock_family_manager.get_family.return_value = mock_family

            # Redis service fails
            mock_redis.get_redis.side_effect = ConnectionError("Redis unavailable")

            @secure_mcp_tool(permissions=["family:read"])
            async def degraded_family_dashboard():
                """Family dashboard with graceful degradation."""
                result = {
                    "family_info": None,
                    "cached_stats": None,
                    "service_status": {"family_service": "available", "cache_service": "unavailable"},
                    "degraded_mode": False,
                }

                # Try to get family info
                try:
                    family = await mock_family_manager.get_family("family_1", user_context.user_id)
                    result["family_info"] = family.dict()
                except Exception as e:
                    result["service_status"]["family_service"] = "unavailable"
                    result["degraded_mode"] = True

                # Try to get cached statistics
                try:
                    redis_conn = await mock_redis.get_redis()
                    # This would normally get cached stats
                    result["cached_stats"] = {"last_activity": "2024-01-01"}
                except Exception as e:
                    result["service_status"]["cache_service"] = "unavailable"
                    result["degraded_mode"] = True
                    result["cached_stats"] = {"message": "Statistics unavailable - cache service down"}

                return result

            dashboard_result = await degraded_family_dashboard()

            # Verify graceful degradation
            assert dashboard_result["family_info"] is not None
            assert dashboard_result["family_info"]["name"] == "Test Family"
            assert dashboard_result["service_status"]["family_service"] == "available"
            assert dashboard_result["service_status"]["cache_service"] == "unavailable"
            assert dashboard_result["degraded_mode"] is True
            assert "Statistics unavailable" in dashboard_result["cached_stats"]["message"]

    @pytest.mark.asyncio
    async def test_concurrent_operation_conflict_resolution(self, mock_error_user):
        """Test conflict resolution during concurrent operations."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_error_user, ip_address="192.168.1.100", user_agent="ConcurrencyClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Simulate concurrent operations with conflicts
        with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

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

    @pytest.mark.asyncio
    async def test_cascading_failure_circuit_breaker(self, mock_error_user):
        """Test circuit breaker pattern for cascading failures."""
        user_context = await create_mcp_user_context_from_fastapi_user(
            fastapi_user=mock_error_user, ip_address="192.168.1.100", user_agent="CircuitBreakerClient/1.0"
        )
        set_mcp_user_context(user_context)

        # Simulate circuit breaker for failing service
        circuit_breaker_state = {
            "failure_count": 0,
            "last_failure_time": None,
            "state": "closed",  # closed, open, half_open
            "failure_threshold": 3,
            "recovery_timeout": 0.05,  # 50ms for testing
        }

        with patch("src.second_brain_database.integrations.mcp.tools.family_tools.FamilyManager") as mock_fm:
            mock_family_manager = AsyncMock()
            mock_fm.return_value = mock_family_manager

            # Simulate service that keeps failing
            def failing_service(*args, **kwargs):
                raise ConnectionError("Service consistently failing")

            mock_family_manager.get_family_members.side_effect = failing_service

            @secure_mcp_tool(permissions=["family:read"])
            async def circuit_breaker_operation():
                """Operation with circuit breaker pattern."""
                current_time = time.time()

                # Check circuit breaker state
                if circuit_breaker_state["state"] == "open":
                    if (current_time - circuit_breaker_state["last_failure_time"]) > circuit_breaker_state[
                        "recovery_timeout"
                    ]:
                        circuit_breaker_state["state"] = "half_open"
                    else:
                        return {
                            "success": False,
                            "error": "Circuit breaker open - service unavailable",
                            "circuit_state": "open",
                            "retry_after": circuit_breaker_state["recovery_timeout"],
                        }

                try:
                    # Attempt operation
                    members = await mock_family_manager.get_family_members("family_1")

                    # Success - reset circuit breaker
                    circuit_breaker_state["failure_count"] = 0
                    circuit_breaker_state["state"] = "closed"

                    return {"success": True, "members": members, "circuit_state": "closed"}

                except Exception as e:
                    # Failure - update circuit breaker
                    circuit_breaker_state["failure_count"] += 1
                    circuit_breaker_state["last_failure_time"] = current_time

                    if circuit_breaker_state["failure_count"] >= circuit_breaker_state["failure_threshold"]:
                        circuit_breaker_state["state"] = "open"

                    return {
                        "success": False,
                        "error": str(e),
                        "circuit_state": circuit_breaker_state["state"],
                        "failure_count": circuit_breaker_state["failure_count"],
                    }

            # Test circuit breaker progression
            results = []

            # First few calls should fail and increment failure count
            for i in range(4):
                result = await circuit_breaker_operation()
                results.append(result)
                if i < 3:
                    assert result["success"] is False
                    assert result["failure_count"] == i + 1
                    assert "Service consistently failing" in result["error"]

            # After threshold, circuit should be open
            assert results[3]["circuit_state"] == "open"
            assert "Circuit breaker open" in results[3]["error"]

            # Wait for recovery timeout
            await asyncio.sleep(circuit_breaker_state["recovery_timeout"] + 0.01)

            # Next call should attempt half-open state
            result = await circuit_breaker_operation()
            assert result["success"] is False  # Still fails, but attempts the call
            assert result["circuit_state"] == "open"  # Goes back to open


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
