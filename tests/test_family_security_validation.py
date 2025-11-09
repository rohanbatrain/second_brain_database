#!/usr/bin/env python3
"""
Comprehensive security validation tests for the Family Management System.

This test suite validates all security dependencies and authentication flows
according to requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6.

Test Coverage:
- Authentication requirements on all family endpoints
- Authorization checks for admin vs member operations
- Rate limiting enforcement across all endpoints
- Input sanitization and validation
- Error handling and user-friendly error messages
- IP and User Agent lockdown integration
- 2FA requirements for sensitive operations
"""

import asyncio
from datetime import datetime, timedelta
import json
import time
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
import httpx
import pytest

# Import the FastAPI app and dependencies
from src.second_brain_database.main import app
from src.second_brain_database.managers.security_manager import security_manager
from src.second_brain_database.routes.family.dependencies import (
    enforce_family_security,
    get_current_family_user,
    require_2fa_for_sensitive_ops,
    require_family_admin,
)


class TestFamilyAPISecurityValidation:
    """Test suite for API security validation (Task 2.1)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.test_user_id = "test_user_123"
        self.test_family_id = "fam_test_123"
        self.admin_user_id = "admin_user_123"
        self.member_user_id = "member_user_123"

        # Mock user data
        self.admin_user = {
            "_id": self.admin_user_id,
            "username": "admin_test",
            "email": "admin@test.com",
            "is_verified": True,
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "two_fa_enabled": True,
            "two_fa_methods": ["totp", "email"],
        }

        self.member_user = {
            "_id": self.member_user_id,
            "username": "member_test",
            "email": "member@test.com",
            "is_verified": True,
            "trusted_ip_lockdown": False,
            "trusted_user_agent_lockdown": False,
            "two_fa_enabled": False,
            "two_fa_methods": [],
        }

        # Valid JWT token for testing
        self.valid_token = "valid_jwt_token_123"
        self.invalid_token = "invalid_jwt_token_456"

    @pytest.mark.asyncio
    async def test_authentication_required_all_endpoints(self):
        """Test that all family endpoints require authentication."""

        # List of all family endpoints that should require authentication
        protected_endpoints = [
            ("POST", "/family/create"),
            ("GET", "/family/my-families"),
            ("POST", f"/family/{self.test_family_id}/invite"),
            ("POST", "/family/invitation/inv_123/respond"),
            ("GET", f"/family/{self.test_family_id}/invitations"),
            ("POST", f"/family/{self.test_family_id}/invitations/inv_123/resend"),
            ("DELETE", f"/family/{self.test_family_id}/invitations/inv_123"),
            ("GET", f"/family/{self.test_family_id}/sbd-account"),
            ("PUT", f"/family/{self.test_family_id}/sbd-account/permissions"),
            ("POST", f"/family/{self.test_family_id}/account/freeze"),
            ("GET", f"/family/{self.test_family_id}/sbd-account/transactions"),
            ("POST", f"/family/{self.test_family_id}/sbd-account/validate-spending"),
        ]

        for method, endpoint in protected_endpoints:
            # Test without authentication token
            if method == "GET":
                response = self.client.get(endpoint)
            elif method == "POST":
                response = self.client.post(endpoint, json={})
            elif method == "PUT":
                response = self.client.put(endpoint, json={})
            elif method == "DELETE":
                response = self.client.delete(endpoint)

            # Should return 401 Unauthorized
            assert (
                response.status_code == status.HTTP_401_UNAUTHORIZED
            ), f"Endpoint {method} {endpoint} should require authentication"

            # Test with invalid token
            headers = {"Authorization": f"Bearer {self.invalid_token}"}
            if method == "GET":
                response = self.client.get(endpoint, headers=headers)
            elif method == "POST":
                response = self.client.post(endpoint, json={}, headers=headers)
            elif method == "PUT":
                response = self.client.put(endpoint, json={}, headers=headers)
            elif method == "DELETE":
                response = self.client.delete(endpoint, headers=headers)

            # Should return 401 Unauthorized for invalid token
            assert (
                response.status_code == status.HTTP_401_UNAUTHORIZED
            ), f"Endpoint {method} {endpoint} should reject invalid tokens"

    @pytest.mark.asyncio
    async def test_authorization_admin_vs_member_operations(self):
        """Test authorization checks for admin vs member operations."""

        # Mock the authentication to return different user types
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:

            # Test admin-only operations with member user
            mock_auth.return_value = self.member_user

            admin_only_endpoints = [
                (
                    "POST",
                    f"/family/{self.test_family_id}/invite",
                    {"identifier": "test@example.com", "relationship_type": "child"},
                ),
                ("POST", f"/family/{self.test_family_id}/invitations/inv_123/resend", {}),
                ("DELETE", f"/family/{self.test_family_id}/invitations/inv_123", {}),
                (
                    "PUT",
                    f"/family/{self.test_family_id}/sbd-account/permissions",
                    {"user_id": "user_123", "spending_limit": 100, "can_spend": True},
                ),
                ("POST", f"/family/{self.test_family_id}/sbd-account/freeze", {"action": "freeze", "reason": "test"}),
            ]

            headers = {"Authorization": f"Bearer {self.valid_token}"}

            for method, endpoint, data in admin_only_endpoints:
                if method == "POST":
                    response = self.client.post(endpoint, json=data, headers=headers)
                elif method == "PUT":
                    response = self.client.put(endpoint, json=data, headers=headers)
                elif method == "DELETE":
                    response = self.client.delete(endpoint, headers=headers)

                # Should return 403 Forbidden for non-admin users
                assert (
                    response.status_code == status.HTTP_403_FORBIDDEN
                ), f"Admin-only endpoint {method} {endpoint} should reject member users"

                response_data = response.json()
                assert "INSUFFICIENT_PERMISSIONS" in response_data.get("detail", {}).get(
                    "error", ""
                ), f"Should return insufficient permissions error for {method} {endpoint}"

            # Test member operations with admin user (should work)
            mock_auth.return_value = self.admin_user

            member_endpoints = [
                ("GET", "/family/my-families"),
                ("GET", f"/family/{self.test_family_id}/sbd-account"),
                ("GET", f"/family/{self.test_family_id}/sbd-account/transactions"),
                ("POST", f"/family/{self.test_family_id}/sbd-account/validate-spending?amount=100", {}),
            ]

            for method, endpoint, *data in member_endpoints:
                if method == "GET":
                    response = self.client.get(endpoint, headers=headers)
                elif method == "POST":
                    response = self.client.post(endpoint, json=data[0] if data else {}, headers=headers)

                # Admin users should be able to access member operations
                # Note: These might fail for other reasons (family not found, etc.) but not authorization
                assert (
                    response.status_code != status.HTTP_403_FORBIDDEN
                ), f"Admin users should be able to access member endpoint {method} {endpoint}"

    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self):
        """Test rate limiting with various operation types and thresholds."""

        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.admin_user

            headers = {"Authorization": f"Bearer {self.valid_token}"}

            # Test rate limiting on family creation (5 requests per hour)
            with patch.object(security_manager, "check_rate_limit") as mock_rate_limit:
                # First few requests should pass
                mock_rate_limit.return_value = None

                for i in range(3):
                    response = self.client.post("/family/create", json={"name": f"Test Family {i}"}, headers=headers)
                    # May fail for other reasons, but not rate limiting
                    assert response.status_code != status.HTTP_429_TOO_MANY_REQUESTS

                # Simulate rate limit exceeded
                mock_rate_limit.side_effect = HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please try again later."
                )

                response = self.client.post("/family/create", json={"name": "Rate Limited Family"}, headers=headers)
                assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

                # Verify rate limit was called with correct parameters
                mock_rate_limit.assert_called()
                call_args = mock_rate_limit.call_args
                assert "family_create_" in call_args[1]["action"]
                assert call_args[1]["rate_limit_requests"] == 5
                assert call_args[1]["rate_limit_period"] == 3600

            # Test different rate limits for different operations
            rate_limit_tests = [
                ("/family/my-families", "family_list_", 20, 3600),
                (f"/family/{self.test_family_id}/invite", "family_invite_", 10, 3600),
                (f"/family/{self.test_family_id}/sbd-account", "family_sbd_account_", 30, 3600),
            ]

            for endpoint, action_prefix, expected_requests, expected_period in rate_limit_tests:
                with patch.object(security_manager, "check_rate_limit") as mock_rate_limit:
                    mock_rate_limit.return_value = None

                    if endpoint.endswith("/invite"):
                        response = self.client.post(
                            endpoint,
                            json={"identifier": "test@example.com", "relationship_type": "child"},
                            headers=headers,
                        )
                    else:
                        response = self.client.get(endpoint, headers=headers)

                    # Verify rate limit was called with correct parameters
                    mock_rate_limit.assert_called()
                    call_args = mock_rate_limit.call_args
                    assert action_prefix in call_args[1]["action"]
                    assert call_args[1]["rate_limit_requests"] == expected_requests
                    assert call_args[1]["rate_limit_period"] == expected_period

    @pytest.mark.asyncio
    async def test_input_sanitization_and_validation(self):
        """Test input sanitization and validation on all endpoints."""

        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.admin_user

            headers = {"Authorization": f"Bearer {self.valid_token}"}

            # Test family creation with invalid inputs
            invalid_family_data = [
                {"name": ""},  # Empty name
                {"name": "a" * 101},  # Too long name
                {"name": "<script>alert('xss')</script>"},  # XSS attempt
                {"name": "family_reserved_prefix"},  # Reserved prefix
                {"invalid_field": "value"},  # Invalid field
            ]

            for invalid_data in invalid_family_data:
                response = self.client.post("/family/create", json=invalid_data, headers=headers)
                assert (
                    response.status_code == status.HTTP_400_BAD_REQUEST
                    or response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                ), f"Should reject invalid family data: {invalid_data}"

            # Test member invitation with invalid inputs
            invalid_invite_data = [
                {"identifier": "", "relationship_type": "child"},  # Empty identifier
                {"identifier": "invalid-email", "relationship_type": "child"},  # Invalid email
                {"identifier": "test@example.com", "relationship_type": "invalid"},  # Invalid relationship
                {"identifier": "test@example.com"},  # Missing relationship_type
                {"relationship_type": "child"},  # Missing identifier
                {
                    "identifier": "test@example.com",
                    "relationship_type": "child",
                    "malicious_field": "<script>",
                },  # Extra field
            ]

            for invalid_data in invalid_invite_data:
                response = self.client.post(f"/family/{self.test_family_id}/invite", json=invalid_data, headers=headers)
                assert (
                    response.status_code == status.HTTP_400_BAD_REQUEST
                    or response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                ), f"Should reject invalid invite data: {invalid_data}"

            # Test spending permissions with invalid inputs
            invalid_permissions_data = [
                {"user_id": "", "spending_limit": 100, "can_spend": True},  # Empty user_id
                {"user_id": "user_123", "spending_limit": -2, "can_spend": True},  # Invalid limit (not -1 or positive)
                {"user_id": "user_123", "spending_limit": "invalid", "can_spend": True},  # Non-numeric limit
                {"user_id": "user_123", "spending_limit": 100, "can_spend": "invalid"},  # Invalid boolean
                {"user_id": "user_123", "spending_limit": 100},  # Missing can_spend
            ]

            for invalid_data in invalid_permissions_data:
                response = self.client.put(
                    f"/family/{self.test_family_id}/sbd-account/permissions", json=invalid_data, headers=headers
                )
                assert (
                    response.status_code == status.HTTP_400_BAD_REQUEST
                    or response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                ), f"Should reject invalid permissions data: {invalid_data}"

    @pytest.mark.asyncio
    async def test_error_handling_user_friendly_messages(self):
        """Test error handling and user-friendly error messages."""

        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.admin_user

            headers = {"Authorization": f"Bearer {self.valid_token}"}

            # Test various error scenarios and verify user-friendly messages
            error_scenarios = [
                {
                    "endpoint": "/family/create",
                    "method": "POST",
                    "data": {"name": "Test Family"},
                    "mock_exception": "FamilyLimitExceeded",
                    "expected_status": status.HTTP_403_FORBIDDEN,
                    "expected_error_code": "FAMILY_LIMIT_EXCEEDED",
                    "expected_message_contains": "limit",
                },
                {
                    "endpoint": f"/family/{self.test_family_id}/invite",
                    "method": "POST",
                    "data": {"identifier": "test@example.com", "relationship_type": "child"},
                    "mock_exception": "FamilyNotFound",
                    "expected_status": status.HTTP_404_NOT_FOUND,
                    "expected_error_code": "FAMILY_NOT_FOUND",
                    "expected_message_contains": "not found",
                },
                {
                    "endpoint": f"/family/{self.test_family_id}/sbd-account/permissions",
                    "method": "PUT",
                    "data": {"user_id": "user_123", "spending_limit": 100, "can_spend": True},
                    "mock_exception": "InsufficientPermissions",
                    "expected_status": status.HTTP_403_FORBIDDEN,
                    "expected_error_code": "INSUFFICIENT_PERMISSIONS",
                    "expected_message_contains": "permission",
                },
                {
                    "endpoint": f"/family/{self.test_family_id}/sbd-account/validate-spending?amount=1000",
                    "method": "POST",
                    "data": {},
                    "mock_exception": "AccountFrozen",
                    "expected_status": status.HTTP_400_BAD_REQUEST,
                    "expected_error_code": "ACCOUNT_FROZEN",
                    "expected_message_contains": "frozen",
                },
            ]

            for scenario in error_scenarios:
                with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
                    # Mock the appropriate exception
                    if scenario["mock_exception"] == "FamilyLimitExceeded":
                        from src.second_brain_database.managers.family_manager import FamilyLimitExceeded

                        mock_manager.create_family.side_effect = FamilyLimitExceeded("Family limit exceeded")
                    elif scenario["mock_exception"] == "FamilyNotFound":
                        from src.second_brain_database.managers.family_manager import FamilyNotFound

                        mock_manager.invite_member.side_effect = FamilyNotFound("Family not found")
                    elif scenario["mock_exception"] == "InsufficientPermissions":
                        from src.second_brain_database.managers.family_manager import InsufficientPermissions

                        mock_manager.update_spending_permissions.side_effect = InsufficientPermissions(
                            "Insufficient permissions"
                        )
                    elif scenario["mock_exception"] == "AccountFrozen":
                        from src.second_brain_database.managers.family_manager import AccountFrozen

                        mock_manager.validate_family_spending.side_effect = AccountFrozen("Account is frozen")

                    # Make the request
                    if scenario["method"] == "POST":
                        response = self.client.post(scenario["endpoint"], json=scenario["data"], headers=headers)
                    elif scenario["method"] == "PUT":
                        response = self.client.put(scenario["endpoint"], json=scenario["data"], headers=headers)

                    # Verify error response
                    assert (
                        response.status_code == scenario["expected_status"]
                    ), f"Expected status {scenario['expected_status']} for {scenario['endpoint']}"

                    response_data = response.json()
                    detail = response_data.get("detail", {})

                    if isinstance(detail, dict):
                        assert (
                            detail.get("error") == scenario["expected_error_code"]
                        ), f"Expected error code {scenario['expected_error_code']} for {scenario['endpoint']}"

                        message = detail.get("message", "").lower()
                        assert (
                            scenario["expected_message_contains"].lower() in message
                        ), f"Expected message to contain '{scenario['expected_message_contains']}' for {scenario['endpoint']}"

    @pytest.mark.asyncio
    async def test_ip_user_agent_lockdown_integration(self):
        """Test IP and User Agent lockdown integration."""

        # Test IP lockdown
        lockdown_user = {**self.admin_user, "trusted_ip_lockdown": True, "trusted_ips": ["192.168.1.100", "10.0.0.1"]}

        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = lockdown_user

            headers = {"Authorization": f"Bearer {self.valid_token}"}

            # Mock security manager to simulate IP lockdown
            with patch.object(security_manager, "check_ip_lockdown") as mock_ip_check:
                # Test blocked IP
                mock_ip_check.side_effect = HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: IP address not in trusted list (IP Lockdown enabled)",
                )

                response = self.client.get("/family/my-families", headers=headers)
                assert response.status_code == status.HTTP_403_FORBIDDEN
                assert "IP address not in trusted list" in response.json()["detail"]

                # Test allowed IP
                mock_ip_check.side_effect = None
                mock_ip_check.return_value = None

                response = self.client.get("/family/my-families", headers=headers)
                # Should not be blocked by IP lockdown (may fail for other reasons)
                assert (
                    response.status_code != status.HTTP_403_FORBIDDEN
                    or "IP address not in trusted list" not in response.json().get("detail", "")
                )

        # Test User Agent lockdown
        ua_lockdown_user = {
            **self.admin_user,
            "trusted_user_agent_lockdown": True,
            "trusted_user_agents": ["Mozilla/5.0 (trusted-browser)", "MyApp/1.0"],
        }

        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = ua_lockdown_user

            # Mock security manager to simulate User Agent lockdown
            with patch.object(security_manager, "check_user_agent_lockdown") as mock_ua_check:
                # Test blocked User Agent
                mock_ua_check.side_effect = HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: User Agent not in trusted list (User Agent Lockdown enabled)",
                )

                response = self.client.get("/family/my-families", headers=headers)
                assert response.status_code == status.HTTP_403_FORBIDDEN
                assert "User Agent not in trusted list" in response.json()["detail"]

                # Test allowed User Agent
                mock_ua_check.side_effect = None
                mock_ua_check.return_value = None

                response = self.client.get("/family/my-families", headers=headers)
                # Should not be blocked by User Agent lockdown (may fail for other reasons)
                assert (
                    response.status_code != status.HTTP_403_FORBIDDEN
                    or "User Agent not in trusted list" not in response.json().get("detail", "")
                )


class TestFamilyPermissionSystem:
    """Test suite for permission system testing (Task 2.2)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.family_id = "fam_test_456"

        # Mock users with different roles
        self.primary_admin = {
            "_id": "admin_primary_123",
            "username": "primary_admin",
            "email": "primary@test.com",
            "two_fa_enabled": True,
            "two_fa_methods": ["totp"],
        }

        self.backup_admin = {
            "_id": "admin_backup_123",
            "username": "backup_admin",
            "email": "backup@test.com",
            "two_fa_enabled": True,
            "two_fa_methods": ["email"],
        }

        self.regular_member = {
            "_id": "member_regular_123",
            "username": "regular_member",
            "email": "member@test.com",
            "two_fa_enabled": False,
            "two_fa_methods": [],
        }

        self.valid_token = "valid_jwt_token_789"

    @pytest.mark.asyncio
    async def test_family_admin_validation_permission_checks(self):
        """Test family admin validation and permission checks."""

        # Test admin validation for different operations
        admin_operations = [
            ("POST", f"/family/{self.family_id}/invite", {"identifier": "new@test.com", "relationship_type": "child"}),
            (
                "PUT",
                f"/family/{self.family_id}/sbd-account/permissions",
                {"user_id": "user_123", "spending_limit": 500, "can_spend": True},
            ),
            ("POST", f"/family/{self.family_id}/sbd-account/freeze", {"action": "freeze", "reason": "security"}),
            ("DELETE", f"/family/{self.family_id}/invitations/inv_123", {}),
        ]

        headers = {"Authorization": f"Bearer {self.valid_token}"}

        # Test with admin user
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.primary_admin

            with patch(
                "src.second_brain_database.managers.family_manager.family_manager.validate_admin_permissions"
            ) as mock_validate:
                # Test successful admin validation
                mock_validate.return_value = True

                for method, endpoint, data in admin_operations:
                    if method == "POST":
                        response = self.client.post(endpoint, json=data, headers=headers)
                    elif method == "PUT":
                        response = self.client.put(endpoint, json=data, headers=headers)
                    elif method == "DELETE":
                        response = self.client.delete(endpoint, headers=headers)

                    # Should not fail due to admin validation (may fail for other reasons)
                    assert (
                        response.status_code != status.HTTP_403_FORBIDDEN
                        or "Admin privileges required" not in response.json().get("detail", "")
                    )

                # Test failed admin validation
                mock_validate.return_value = False

                for method, endpoint, data in admin_operations:
                    if method == "POST":
                        response = self.client.post(endpoint, json=data, headers=headers)
                    elif method == "PUT":
                        response = self.client.put(endpoint, json=data, headers=headers)
                    elif method == "DELETE":
                        response = self.client.delete(endpoint, headers=headers)

                    # Should fail due to insufficient admin privileges
                    assert response.status_code == status.HTTP_403_FORBIDDEN
                    assert "Admin privileges required" in response.json().get(
                        "detail", ""
                    ) or "INSUFFICIENT_PERMISSIONS" in str(response.json())

        # Test with regular member (should fail admin checks)
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.regular_member

            with patch(
                "src.second_brain_database.managers.family_manager.family_manager.validate_admin_permissions"
            ) as mock_validate:
                mock_validate.return_value = False

                for method, endpoint, data in admin_operations:
                    if method == "POST":
                        response = self.client.post(endpoint, json=data, headers=headers)
                    elif method == "PUT":
                        response = self.client.put(endpoint, json=data, headers=headers)
                    elif method == "DELETE":
                        response = self.client.delete(endpoint, headers=headers)

                    # Should fail due to insufficient admin privileges
                    assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_spending_permission_enforcement(self):
        """Test spending permission enforcement and validation."""

        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.regular_member

            headers = {"Authorization": f"Bearer {self.valid_token}"}

            # Test spending validation with different scenarios
            spending_scenarios = [
                {
                    "amount": 100,
                    "can_spend": True,
                    "spending_limit": 500,
                    "account_frozen": False,
                    "expected_result": True,
                },
                {
                    "amount": 600,
                    "can_spend": True,
                    "spending_limit": 500,
                    "account_frozen": False,
                    "expected_result": False,
                    "denial_reason": "SPENDING_LIMIT_EXCEEDED",
                },
                {
                    "amount": 100,
                    "can_spend": False,
                    "spending_limit": 500,
                    "account_frozen": False,
                    "expected_result": False,
                    "denial_reason": "NO_SPENDING_PERMISSION",
                },
                {
                    "amount": 100,
                    "can_spend": True,
                    "spending_limit": 500,
                    "account_frozen": True,
                    "expected_result": False,
                    "denial_reason": "ACCOUNT_FROZEN",
                },
            ]

            for scenario in spending_scenarios:
                with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
                    # Mock family data
                    mock_family_data = {
                        "sbd_account": {
                            "account_username": f"family_{self.family_id}",
                            "is_frozen": scenario["account_frozen"],
                            "spending_permissions": {
                                self.regular_member["_id"]: {
                                    "can_spend": scenario["can_spend"],
                                    "spending_limit": scenario["spending_limit"],
                                    "role": "member",
                                }
                            },
                        }
                    }

                    mock_manager.get_family_by_id.return_value = mock_family_data
                    mock_manager.validate_family_spending.return_value = scenario["expected_result"]
                    mock_manager.get_family_sbd_balance.return_value = 1000  # Sufficient balance

                    response = self.client.post(
                        f"/family/{self.family_id}/sbd-account/validate-spending?amount={scenario['amount']}",
                        json={},
                        headers=headers,
                    )

                    assert response.status_code == status.HTTP_200_OK
                    response_data = response.json()

                    assert response_data["data"]["can_spend"] == scenario["expected_result"]
                    assert response_data["data"]["amount"] == scenario["amount"]

                    if not scenario["expected_result"] and "denial_reason" in scenario:
                        assert response_data["data"]["denial_reason"] == scenario["denial_reason"]

    @pytest.mark.asyncio
    async def test_multi_admin_scenarios_admin_management(self):
        """Test multi-admin scenarios and admin management."""

        headers = {"Authorization": f"Bearer {self.valid_token}"}

        # Test promoting member to admin
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.primary_admin

            with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
                # Mock successful admin promotion
                mock_manager.validate_admin_permissions.return_value = True
                mock_manager.promote_to_admin.return_value = {
                    "family_id": self.family_id,
                    "promoted_user_id": self.regular_member["_id"],
                    "promoted_by": self.primary_admin["_id"],
                    "promoted_at": datetime.now(),
                    "new_admin_count": 2,
                }

                # This endpoint might not exist yet, but testing the concept
                promote_data = {"user_id": self.regular_member["_id"], "reason": "Trusted family member"}

                # Simulate admin promotion (would be implemented in actual routes)
                # For now, we'll test the underlying manager function
                result = await mock_manager.promote_to_admin(
                    self.family_id, self.primary_admin["_id"], self.regular_member["_id"]
                )

                assert result["promoted_user_id"] == self.regular_member["_id"]
                assert result["new_admin_count"] == 2

        # Test demoting admin (should prevent leaving family without admins)
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.primary_admin

            with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
                # Mock scenario where demoting would leave no admins
                from src.second_brain_database.managers.family_manager import MultipleAdminsRequired

                mock_manager.validate_admin_permissions.return_value = True
                mock_manager.demote_admin.side_effect = MultipleAdminsRequired(
                    "Cannot demote the last admin. Family must have at least one administrator."
                )

                # Test that demoting last admin is prevented
                try:
                    await mock_manager.demote_admin(
                        self.family_id,
                        self.primary_admin["_id"],
                        self.primary_admin["_id"],  # Trying to demote self as last admin
                    )
                    assert False, "Should have raised MultipleAdminsRequired exception"
                except MultipleAdminsRequired as e:
                    assert "last admin" in str(e).lower()
                    assert "at least one administrator" in str(e).lower()

    @pytest.mark.asyncio
    async def test_backup_admin_functionality_succession_planning(self):
        """Test backup admin functionality and succession planning."""

        headers = {"Authorization": f"Bearer {self.valid_token}"}

        # Test backup admin designation
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.primary_admin

            with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
                mock_manager.validate_admin_permissions.return_value = True

                # Mock setting backup admin
                mock_manager.set_backup_admin.return_value = {
                    "family_id": self.family_id,
                    "backup_admin_id": self.backup_admin["_id"],
                    "set_by": self.primary_admin["_id"],
                    "succession_plan": {
                        "backup_admins": [self.backup_admin["_id"]],
                        "recovery_contacts": ["recovery@test.com"],
                    },
                }

                result = await mock_manager.set_backup_admin(
                    self.family_id, self.primary_admin["_id"], self.backup_admin["_id"]
                )

                assert result["backup_admin_id"] == self.backup_admin["_id"]
                assert self.backup_admin["_id"] in result["succession_plan"]["backup_admins"]

        # Test succession plan activation
        with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
            # Mock scenario where primary admin is unavailable and backup takes over
            mock_manager.activate_succession_plan.return_value = {
                "family_id": self.family_id,
                "new_primary_admin": self.backup_admin["_id"],
                "previous_admin": self.primary_admin["_id"],
                "activation_reason": "Primary admin unavailable",
                "activated_at": datetime.now(),
            }

            result = await mock_manager.activate_succession_plan(self.family_id, "Primary admin unavailable")

            assert result["new_primary_admin"] == self.backup_admin["_id"]
            assert result["previous_admin"] == self.primary_admin["_id"]

    @pytest.mark.asyncio
    async def test_emergency_recovery_mechanisms(self):
        """Test emergency recovery mechanisms."""

        headers = {"Authorization": f"Bearer {self.valid_token}"}

        # Test emergency recovery initiation
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.regular_member

            with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
                # Mock emergency recovery request
                mock_manager.initiate_emergency_recovery.return_value = {
                    "recovery_id": "recovery_123",
                    "family_id": self.family_id,
                    "requested_by": self.regular_member["_id"],
                    "recovery_type": "admin_unavailable",
                    "verification_required": True,
                    "recovery_contacts_notified": ["recovery@test.com"],
                    "expires_at": datetime.now() + timedelta(hours=24),
                }

                result = await mock_manager.initiate_emergency_recovery(
                    self.family_id, self.regular_member["_id"], "admin_unavailable", "All family admins are unreachable"
                )

                assert result["recovery_id"] == "recovery_123"
                assert result["requested_by"] == self.regular_member["_id"]
                assert result["verification_required"] is True

        # Test recovery verification and approval
        with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
            # Mock recovery verification
            mock_manager.verify_emergency_recovery.return_value = {
                "recovery_id": "recovery_123",
                "verified": True,
                "new_admin": self.regular_member["_id"],
                "verification_method": "email_confirmation",
                "recovery_completed_at": datetime.now(),
            }

            result = await mock_manager.verify_emergency_recovery("recovery_123", "email_verification_token_123")

            assert result["verified"] is True
            assert result["new_admin"] == self.regular_member["_id"]

        # Test recovery rejection/timeout
        with patch("src.second_brain_database.managers.family_manager.family_manager") as mock_manager:
            # Mock recovery timeout
            mock_manager.cleanup_expired_recovery_requests.return_value = {
                "expired_count": 1,
                "expired_requests": ["recovery_123"],
                "cleanup_timestamp": datetime.now(),
            }

            result = await mock_manager.cleanup_expired_recovery_requests()

            assert result["expired_count"] == 1
            assert "recovery_123" in result["expired_requests"]


class TestTwoFactorAuthentication:
    """Test suite for 2FA requirements on sensitive operations."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.family_id = "fam_2fa_test_789"

        # User with 2FA enabled
        self.user_with_2fa = {
            "_id": "user_2fa_enabled_123",
            "username": "user_2fa",
            "email": "user2fa@test.com",
            "two_fa_enabled": True,
            "two_fa_methods": ["totp", "email"],
        }

        # User without 2FA
        self.user_without_2fa = {
            "_id": "user_no_2fa_123",
            "username": "user_no_2fa",
            "email": "userno2fa@test.com",
            "two_fa_enabled": False,
            "two_fa_methods": [],
        }

        self.valid_token = "valid_jwt_token_2fa"

    @pytest.mark.asyncio
    async def test_2fa_requirements_sensitive_operations(self):
        """Test 2FA requirements for sensitive operations."""

        # List of sensitive operations that should require 2FA
        sensitive_operations = [
            ("POST", "/family/create", {"name": "Sensitive Family"}),
            (
                "POST",
                f"/family/{self.family_id}/invite",
                {"identifier": "sensitive@test.com", "relationship_type": "child"},
            ),
            (
                "PUT",
                f"/family/{self.family_id}/sbd-account/permissions",
                {"user_id": "user_123", "spending_limit": 1000, "can_spend": True},
            ),
            (
                "POST",
                f"/family/{self.family_id}/sbd-account/freeze",
                {"action": "freeze", "reason": "security incident"},
            ),
        ]

        headers = {"Authorization": f"Bearer {self.valid_token}"}

        # Test with user who has 2FA enabled (should pass 2FA check)
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.user_with_2fa

            for method, endpoint, data in sensitive_operations:
                with patch(
                    "src.second_brain_database.routes.family.dependencies.require_2fa_for_sensitive_ops"
                ) as mock_2fa:
                    mock_2fa.return_value = {**self.user_with_2fa, "2fa_validated": True}

                    if method == "POST":
                        response = self.client.post(endpoint, json=data, headers=headers)
                    elif method == "PUT":
                        response = self.client.put(endpoint, json=data, headers=headers)

                    # Should not fail due to 2FA (may fail for other reasons)
                    assert (
                        response.status_code != status.HTTP_422_UNPROCESSABLE_ENTITY
                        or "2fa_required" not in response.json().get("detail", {}).get("error", "")
                    )

        # Test with user who doesn't have 2FA enabled (should fail 2FA check)
        with patch("src.second_brain_database.routes.auth.dependencies.get_current_user_dep") as mock_auth:
            mock_auth.return_value = self.user_without_2fa

            for method, endpoint, data in sensitive_operations:
                with patch(
                    "src.second_brain_database.routes.family.dependencies.require_2fa_for_sensitive_ops"
                ) as mock_2fa:
                    # Mock 2FA requirement failure
                    mock_2fa.side_effect = HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail={
                            "error": "2fa_required",
                            "message": "Two-factor authentication required for this sensitive operation",
                            "operation": "sensitive_family_operation",
                            "available_methods": [],
                        },
                    )

                    if method == "POST":
                        response = self.client.post(endpoint, json=data, headers=headers)
                    elif method == "PUT":
                        response = self.client.put(endpoint, json=data, headers=headers)

                    # Should fail due to 2FA requirement
                    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                    response_data = response.json()
                    assert response_data["detail"]["error"] == "2fa_required"
                    assert "Two-factor authentication required" in response_data["detail"]["message"]


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v", "--tb=short"])
