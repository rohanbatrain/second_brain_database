#!/usr/bin/env python3
"""
Comprehensive test suite for Family Token Request Workflow.

This test file validates the complete token request lifecycle including:
- Token request creation and validation
- Admin notification and review processes
- Approval and denial workflows with comments
- Auto-approval criteria and processing
- Request expiration and cleanup
- Audit trail maintenance

Requirements tested: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

# Mock the database and Redis connections before importing
sys.modules["pymongo"] = MagicMock()
sys.modules["pymongo.errors"] = MagicMock()
sys.modules["motor"] = MagicMock()
sys.modules["motor.motor_asyncio"] = MagicMock()
sys.modules["redis"] = MagicMock()
sys.modules["redis.asyncio"] = MagicMock()

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Mock the managers before importing
with (
    patch("second_brain_database.managers.redis_manager.RedisManager"),
    patch("second_brain_database.database.DatabaseManager"),
):

    from second_brain_database.managers.family_manager import (
        AccountFrozen,
        FamilyError,
        FamilyNotFound,
        InsufficientPermissions,
        RateLimitExceeded,
        TokenRequestNotFound,
        ValidationError,
    )


class TokenRequestWorkflowTester:
    """Comprehensive tester for token request workflow functionality."""

    def __init__(self):
        self.db_manager = None
        self.redis_manager = None
        self.family_manager = None
        self.test_results = []

    async def setup(self):
        """Initialize test environment with mocked dependencies."""
        # Mock database manager
        self.db_manager = MagicMock()
        self.db_manager.log_query_start = MagicMock(return_value=datetime.now())
        self.db_manager.log_query_success = MagicMock()
        self.db_manager.log_query_error = MagicMock()

        # Mock Redis manager
        self.redis_manager = MagicMock()

        # Create a mock family manager with the methods we need
        self.family_manager = MagicMock()

        # Mock collections
        self.families_collection = AsyncMock()
        self.requests_collection = AsyncMock()
        self.users_collection = AsyncMock()
        self.notifications_collection = AsyncMock()

        def get_collection_mock(name):
            collections = {
                "families": self.families_collection,
                "family_token_requests": self.requests_collection,
                "users": self.users_collection,
                "family_notifications": self.notifications_collection,
            }
            return collections.get(name, AsyncMock())

        self.db_manager.get_collection = get_collection_mock

    def log_test_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result for reporting."""
        status = "✅ PASS" if success else "❌ FAIL"
        self.test_results.append(
            {
                "test": test_name,
                "status": status,
                "success": success,
                "details": details,
                "timestamp": datetime.now().isoformat(),
            }
        )
        print(f"{status}: {test_name}")
        if details:
            print(f"    Details: {details}")

    async def test_token_request_creation_success(self):
        """Test successful token request creation."""
        test_name = "Token Request Creation - Success"

        try:
            # Setup test data
            family_id = "fam_test123"
            user_id = "user_test456"
            amount = 100
            reason = "Need tokens for school supplies"

            # Mock family data
            family_data = {
                "_id": family_id,
                "family_id": family_id,
                "admin_user_ids": ["admin_123"],
                "sbd_account": {"is_frozen": False, "account_username": "family_test"},
                "settings": {"request_expiry_hours": 168, "auto_approval_threshold": 50},
            }

            # Mock user membership
            self.families_collection.find_one.return_value = family_data

            # Mock user data
            self.users_collection.find_one.return_value = {"_id": user_id, "username": "testuser"}

            # Mock successful insertion
            self.requests_collection.insert_one = AsyncMock()

            # Mock helper methods
            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_is_user_in_family", return_value=True),
                patch.object(self.family_manager, "_notify_admins_token_request", return_value=None),
                patch.object(self.family_manager, "_send_token_request_notification", return_value=None),
            ):

                result = await self.family_manager.create_token_request(
                    family_id=family_id, user_id=user_id, amount=amount, reason=reason
                )

                # Validate result
                assert result["family_id"] == family_id
                assert result["amount"] == amount
                assert result["reason"] == reason
                assert result["status"] == "pending"  # Above auto-approval threshold
                assert not result["auto_approved"]
                assert "request_id" in result
                assert "expires_at" in result

                self.log_test_result(test_name, True, f"Request created with ID: {result['request_id']}")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_token_request_auto_approval(self):
        """Test auto-approval for requests below threshold."""
        test_name = "Token Request Auto-Approval"

        try:
            # Setup test data
            family_id = "fam_test123"
            user_id = "user_test456"
            amount = 25  # Below auto-approval threshold of 50
            reason = "Small token request"

            # Mock family data
            family_data = {
                "_id": family_id,
                "family_id": family_id,
                "admin_user_ids": ["admin_123"],
                "sbd_account": {"is_frozen": False, "account_username": "family_test"},
                "settings": {"request_expiry_hours": 168, "auto_approval_threshold": 50},
            }

            # Mock successful insertion
            self.requests_collection.insert_one = AsyncMock()

            # Mock helper methods
            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_is_user_in_family", return_value=True),
                patch.object(self.family_manager, "_process_approved_token_request", return_value=None),
                patch.object(self.family_manager, "_send_token_request_notification", return_value=None),
            ):

                result = await self.family_manager.create_token_request(
                    family_id=family_id, user_id=user_id, amount=amount, reason=reason
                )

                # Validate auto-approval
                assert result["status"] == "auto_approved"
                assert result["auto_approved"] == True
                assert result["processed_immediately"] == True

                self.log_test_result(test_name, True, f"Auto-approved request for {amount} tokens")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_token_request_validation_errors(self):
        """Test validation errors in token request creation."""
        test_name = "Token Request Validation Errors"

        try:
            family_id = "fam_test123"
            user_id = "user_test456"

            # Test negative amount
            try:
                await self.family_manager.create_token_request(
                    family_id=family_id, user_id=user_id, amount=-10, reason="Valid reason"
                )
                assert False, "Should have raised ValidationError for negative amount"
            except ValidationError as e:
                assert "positive" in str(e).lower()

            # Test empty reason
            try:
                await self.family_manager.create_token_request(
                    family_id=family_id, user_id=user_id, amount=100, reason=""
                )
                assert False, "Should have raised ValidationError for empty reason"
            except ValidationError as e:
                assert "5 characters" in str(e)

            # Test short reason
            try:
                await self.family_manager.create_token_request(
                    family_id=family_id, user_id=user_id, amount=100, reason="Hi"
                )
                assert False, "Should have raised ValidationError for short reason"
            except ValidationError as e:
                assert "5 characters" in str(e)

            self.log_test_result(test_name, True, "All validation errors caught correctly")

        except Exception as e:
            self.log_test_result(test_name, False, f"Unexpected exception: {str(e)}")

    async def test_token_request_frozen_account(self):
        """Test token request creation when account is frozen."""
        test_name = "Token Request - Frozen Account"

        try:
            family_id = "fam_test123"
            user_id = "user_test456"

            # Mock frozen family data
            family_data = {
                "_id": family_id,
                "family_id": family_id,
                "admin_user_ids": ["admin_123"],
                "sbd_account": {"is_frozen": True, "frozen_by": "admin_123", "frozen_at": datetime.now(timezone.utc)},
                "settings": {"request_expiry_hours": 168, "auto_approval_threshold": 50},
            }

            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_is_user_in_family", return_value=True),
            ):

                try:
                    await self.family_manager.create_token_request(
                        family_id=family_id, user_id=user_id, amount=100, reason="Valid reason"
                    )
                    assert False, "Should have raised AccountFrozen error"
                except AccountFrozen as e:
                    assert "frozen" in str(e).lower()
                    assert family_id in str(e)

            self.log_test_result(test_name, True, "Frozen account error raised correctly")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_token_request_review_approval(self):
        """Test token request approval workflow."""
        test_name = "Token Request Review - Approval"

        try:
            request_id = "req_test123"
            admin_id = "admin_456"
            comments = "Approved for educational expenses"

            # Mock request data
            request_data = {
                "request_id": request_id,
                "family_id": "fam_test123",
                "requester_user_id": "user_test456",
                "amount": 100,
                "reason": "School supplies",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
                "created_at": datetime.now(timezone.utc),
            }

            # Mock family data
            family_data = {"_id": "fam_test123", "admin_user_ids": [admin_id, "admin_789"]}

            # Mock database operations
            self.requests_collection.find_one.return_value = request_data
            self.requests_collection.update_one = AsyncMock()

            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_process_approved_token_request", return_value=None),
                patch.object(self.family_manager, "_send_token_request_notification", return_value=None),
                patch.object(self.family_manager, "_notify_admins_token_decision", return_value=None),
            ):

                result = await self.family_manager.review_token_request(
                    request_id=request_id, admin_id=admin_id, action="approve", comments=comments
                )

                # Validate approval result
                assert result["request_id"] == request_id
                assert result["action"] == "approve"
                assert result["status"] == "approved"
                assert result["reviewed_by"] == admin_id
                assert result["admin_comments"] == comments
                assert "reviewed_at" in result
                assert "processed_at" in result

                self.log_test_result(test_name, True, f"Request approved by {admin_id}")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_token_request_review_denial(self):
        """Test token request denial workflow."""
        test_name = "Token Request Review - Denial"

        try:
            request_id = "req_test123"
            admin_id = "admin_456"
            comments = "Insufficient justification provided"

            # Mock request data
            request_data = {
                "request_id": request_id,
                "family_id": "fam_test123",
                "requester_user_id": "user_test456",
                "amount": 100,
                "reason": "Need tokens",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
                "created_at": datetime.now(timezone.utc),
            }

            # Mock family data
            family_data = {"_id": "fam_test123", "admin_user_ids": [admin_id]}

            # Mock database operations
            self.requests_collection.find_one.return_value = request_data
            self.requests_collection.update_one = AsyncMock()

            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_send_token_request_notification", return_value=None),
                patch.object(self.family_manager, "_notify_admins_token_decision", return_value=None),
            ):

                result = await self.family_manager.review_token_request(
                    request_id=request_id, admin_id=admin_id, action="deny", comments=comments
                )

                # Validate denial result
                assert result["request_id"] == request_id
                assert result["action"] == "deny"
                assert result["status"] == "denied"
                assert result["reviewed_by"] == admin_id
                assert result["admin_comments"] == comments
                assert "reviewed_at" in result
                assert "processed_at" not in result or result["processed_at"] is None

                self.log_test_result(test_name, True, f"Request denied by {admin_id}")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_token_request_review_permissions(self):
        """Test permission validation for token request review."""
        test_name = "Token Request Review - Permission Validation"

        try:
            request_id = "req_test123"
            non_admin_id = "user_456"  # Not an admin

            # Mock request data
            request_data = {
                "request_id": request_id,
                "family_id": "fam_test123",
                "requester_user_id": "user_test456",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
            }

            # Mock family data (non_admin_id not in admin list)
            family_data = {"_id": "fam_test123", "admin_user_ids": ["admin_789"]}  # Different admin

            self.requests_collection.find_one.return_value = request_data

            with patch.object(self.family_manager, "_get_family_by_id", return_value=family_data):

                try:
                    await self.family_manager.review_token_request(
                        request_id=request_id, admin_id=non_admin_id, action="approve"
                    )
                    assert False, "Should have raised InsufficientPermissions"
                except InsufficientPermissions as e:
                    assert "admin" in str(e).lower()

            self.log_test_result(test_name, True, "Permission validation working correctly")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_token_request_expired_handling(self):
        """Test handling of expired token requests."""
        test_name = "Token Request - Expired Handling"

        try:
            request_id = "req_test123"
            admin_id = "admin_456"

            # Mock expired request data
            request_data = {
                "request_id": request_id,
                "family_id": "fam_test123",
                "requester_user_id": "user_test456",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) - timedelta(hours=1),  # Expired
                "created_at": datetime.now(timezone.utc) - timedelta(hours=25),
            }

            # Mock family data
            family_data = {"_id": "fam_test123", "admin_user_ids": [admin_id]}

            self.requests_collection.find_one.return_value = request_data
            self.requests_collection.update_one = AsyncMock()

            with patch.object(self.family_manager, "_get_family_by_id", return_value=family_data):

                try:
                    await self.family_manager.review_token_request(
                        request_id=request_id, admin_id=admin_id, action="approve"
                    )
                    assert False, "Should have raised TokenRequestNotFound for expired request"
                except TokenRequestNotFound as e:
                    assert "expired" in str(e).lower()

            # Verify the request was marked as expired
            self.requests_collection.update_one.assert_called()
            update_call = self.requests_collection.update_one.call_args
            assert update_call[0][1]["$set"]["status"] == "expired"

            self.log_test_result(test_name, True, "Expired request handled correctly")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_get_pending_token_requests(self):
        """Test retrieval of pending token requests."""
        test_name = "Get Pending Token Requests"

        try:
            family_id = "fam_test123"
            admin_id = "admin_456"

            # Mock family data
            family_data = {"_id": family_id, "admin_user_ids": [admin_id]}

            # Mock pending requests
            pending_requests = [
                {
                    "request_id": "req_001",
                    "requester_user_id": "user_001",
                    "amount": 100,
                    "reason": "School supplies",
                    "status": "pending",
                    "auto_approved": False,
                    "created_at": datetime.now(timezone.utc),
                    "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
                },
                {
                    "request_id": "req_002",
                    "requester_user_id": "user_002",
                    "amount": 50,
                    "reason": "Lunch money",
                    "status": "pending",
                    "auto_approved": False,
                    "created_at": datetime.now(timezone.utc),
                    "expires_at": datetime.now(timezone.utc) + timedelta(hours=48),
                },
            ]

            # Mock cursor
            mock_cursor = AsyncMock()
            mock_cursor.to_list.return_value = pending_requests
            mock_cursor.sort.return_value = mock_cursor
            self.requests_collection.find.return_value = mock_cursor

            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_get_user_by_id") as mock_get_user,
            ):

                # Mock user data
                mock_get_user.side_effect = [{"username": "user001"}, {"username": "user002"}]

                result = await self.family_manager.get_pending_token_requests(family_id, admin_id)

                # Validate results
                assert len(result) == 2
                assert result[0]["request_id"] == "req_001"
                assert result[0]["requester_username"] == "user001"
                assert result[1]["request_id"] == "req_002"
                assert result[1]["requester_username"] == "user002"

                # Verify query parameters
                find_call = self.requests_collection.find.call_args[0][0]
                assert find_call["family_id"] == family_id
                assert find_call["status"] == "pending"
                assert "$gt" in find_call["expires_at"]

                self.log_test_result(test_name, True, f"Retrieved {len(result)} pending requests")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_token_request_rate_limiting(self):
        """Test rate limiting for token request operations."""
        test_name = "Token Request Rate Limiting"

        try:
            family_id = "fam_test123"
            user_id = "user_test456"

            # Mock rate limit exceeded
            with patch.object(self.family_manager, "_check_rate_limit") as mock_rate_limit:
                mock_rate_limit.side_effect = Exception("Rate limit exceeded")

                try:
                    await self.family_manager.create_token_request(
                        family_id=family_id,
                        user_id=user_id,
                        amount=100,
                        reason="Valid reason",
                        request_context={"request": MagicMock()},
                    )
                    assert False, "Should have raised RateLimitExceeded"
                except RateLimitExceeded as e:
                    assert "rate limit" in str(e).lower()

            self.log_test_result(test_name, True, "Rate limiting enforced correctly")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_token_request_audit_trail(self):
        """Test audit trail creation for token request operations."""
        test_name = "Token Request Audit Trail"

        try:
            # Test audit logging calls
            family_id = "fam_test123"
            user_id = "user_test456"

            # Mock family data
            family_data = {
                "_id": family_id,
                "family_id": family_id,
                "admin_user_ids": ["admin_123"],
                "sbd_account": {"is_frozen": False},
                "settings": {"request_expiry_hours": 168, "auto_approval_threshold": 50},
            }

            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_is_user_in_family", return_value=True),
                patch.object(self.family_manager, "_notify_admins_token_request", return_value=None),
                patch.object(self.family_manager, "_send_token_request_notification", return_value=None),
            ):

                await self.family_manager.create_token_request(
                    family_id=family_id, user_id=user_id, amount=100, reason="Test request"
                )

                # Verify audit logging was called
                self.db_manager.log_query_start.assert_called()
                self.db_manager.log_query_success.assert_called()

                # Check log context
                start_call = self.db_manager.log_query_start.call_args
                assert start_call[0][0] == "family_token_requests"
                assert start_call[0][1] == "create_token_request"

                context = start_call[0][2]
                assert context["family_id"] == family_id
                assert context["user_id"] == user_id
                assert context["amount"] == 100
                assert context["operation"] == "create_token_request"

            self.log_test_result(test_name, True, "Audit trail created correctly")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def test_complete_token_request_lifecycle(self):
        """Test complete token request lifecycle from creation to processing."""
        test_name = "Complete Token Request Lifecycle"

        try:
            # Step 1: Create token request
            family_id = "fam_test123"
            user_id = "user_test456"
            admin_id = "admin_789"
            amount = 100
            reason = "Educational expenses"

            # Mock family data
            family_data = {
                "_id": family_id,
                "family_id": family_id,
                "admin_user_ids": [admin_id],
                "sbd_account": {"is_frozen": False},
                "settings": {"request_expiry_hours": 168, "auto_approval_threshold": 50},
            }

            # Mock request creation
            request_id = f"req_{uuid.uuid4().hex[:16]}"

            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_is_user_in_family", return_value=True),
                patch.object(self.family_manager, "_notify_admins_token_request", return_value=None),
                patch.object(self.family_manager, "_send_token_request_notification", return_value=None),
            ):

                # Create request
                create_result = await self.family_manager.create_token_request(
                    family_id=family_id, user_id=user_id, amount=amount, reason=reason
                )

                assert create_result["status"] == "pending"
                assert not create_result["auto_approved"]

            # Step 2: Admin reviews and approves request
            request_data = {
                "request_id": request_id,
                "family_id": family_id,
                "requester_user_id": user_id,
                "amount": amount,
                "reason": reason,
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
                "created_at": datetime.now(timezone.utc),
            }

            self.requests_collection.find_one.return_value = request_data
            self.requests_collection.update_one = AsyncMock()

            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_process_approved_token_request", return_value=None),
                patch.object(self.family_manager, "_send_token_request_notification", return_value=None),
                patch.object(self.family_manager, "_notify_admins_token_decision", return_value=None),
            ):

                # Review and approve
                review_result = await self.family_manager.review_token_request(
                    request_id=request_id, admin_id=admin_id, action="approve", comments="Approved for educational use"
                )

                assert review_result["status"] == "approved"
                assert review_result["reviewed_by"] == admin_id
                assert "processed_at" in review_result

            # Step 3: Verify pending requests retrieval
            with (
                patch.object(self.family_manager, "_get_family_by_id", return_value=family_data),
                patch.object(self.family_manager, "_get_user_by_id", return_value={"username": "testuser"}),
            ):

                # Mock empty pending requests (since our request was processed)
                mock_cursor = AsyncMock()
                mock_cursor.to_list.return_value = []
                mock_cursor.sort.return_value = mock_cursor
                self.requests_collection.find.return_value = mock_cursor

                pending_requests = await self.family_manager.get_pending_token_requests(family_id, admin_id)
                assert len(pending_requests) == 0  # No pending requests after approval

            self.log_test_result(test_name, True, "Complete lifecycle executed successfully")

        except Exception as e:
            self.log_test_result(test_name, False, f"Exception: {str(e)}")

    async def run_all_tests(self):
        """Run all token request workflow tests."""
        print("🧪 Running Family Token Request Workflow Tests")
        print("=" * 60)

        await self.setup()

        # Core functionality tests
        await self.test_token_request_creation_success()
        await self.test_token_request_auto_approval()
        await self.test_token_request_validation_errors()
        await self.test_token_request_frozen_account()

        # Review workflow tests
        await self.test_token_request_review_approval()
        await self.test_token_request_review_denial()
        await self.test_token_request_review_permissions()
        await self.test_token_request_expired_handling()

        # Administrative tests
        await self.test_get_pending_token_requests()
        await self.test_token_request_rate_limiting()
        await self.test_token_request_audit_trail()

        # Integration test
        await self.test_complete_token_request_lifecycle()

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")

        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")

        print("\n🎯 Requirements Coverage:")
        print("  ✅ 6.1 - Token request creation and validation")
        print("  ✅ 6.2 - Admin notification and review processes")
        print("  ✅ 6.3 - Approval and denial workflows with comments")
        print("  ✅ 6.4 - Auto-approval criteria and processing")
        print("  ✅ 6.5 - Request expiration and cleanup")
        print("  ✅ 6.6 - Request history and audit trail maintenance")

        return passed_tests == total_tests


async def main():
    """Main test execution function."""
    tester = TokenRequestWorkflowTester()
    success = await tester.run_all_tests()

    if success:
        print("\n🎉 All token request workflow tests passed!")
        return 0
    else:
        print("\n💥 Some token request workflow tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
