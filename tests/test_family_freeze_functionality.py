"""
Comprehensive tests for family account freezing functionality.

This test suite covers all aspects of the account freezing controls:
- Family account freeze/unfreeze functionality
- Frozen account validation in spending operations
- Freeze status tracking and notifications
- Emergency unfreeze procedures
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
import pytest

from second_brain_database.managers.family_manager import (
    AccountFrozen,
    FamilyError,
    FamilyManager,
    FamilyNotFound,
    InsufficientPermissions,
    family_manager,
)


class TestFamilyFreezeControls:
    """Test family account freezing controls."""

    @pytest.fixture
    def mock_family_data(self):
        """Mock family data for testing."""
        return {
            "family_id": "fam_test123",
            "name": "Test Family",
            "admin_user_ids": ["admin_user_1", "admin_user_2"],
            "member_user_ids": ["member_user_1", "member_user_2"],
            "sbd_account": {
                "account_username": "family_test",
                "balance": 5000,
                "is_frozen": False,
                "frozen_by": None,
                "frozen_at": None,
                "freeze_reason": None,
                "spending_permissions": {"member_user_1": {"can_spend": True, "spending_limit": 1000}},
            },
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    @pytest.fixture
    def mock_frozen_family_data(self, mock_family_data):
        """Mock frozen family data for testing."""
        frozen_data = mock_family_data.copy()
        frozen_data["sbd_account"]["is_frozen"] = True
        frozen_data["sbd_account"]["frozen_by"] = "admin_user_1"
        frozen_data["sbd_account"]["frozen_at"] = datetime.now(timezone.utc)
        frozen_data["sbd_account"]["freeze_reason"] = "Suspicious activity"
        return frozen_data

    @pytest.mark.asyncio
    async def test_freeze_family_account_success(self, mock_family_data):
        """Test successful family account freezing."""
        with (
            patch.object(family_manager, "_get_family_by_id", return_value=mock_family_data),
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
            patch.object(family_manager, "_send_account_freeze_notification") as mock_notify,
        ):

            mock_collection = AsyncMock()
            mock_get_collection.return_value = mock_collection
            mock_collection.update_one = AsyncMock()

            result = await family_manager.freeze_family_account(
                "fam_test123", "admin_user_1", "Suspicious activity detected"
            )

            # Verify result
            assert result["is_frozen"] is True
            assert result["frozen_by"] == "admin_user_1"
            assert result["freeze_reason"] == "Suspicious activity detected"
            assert "frozen_at" in result

            # Verify database update was called
            mock_collection.update_one.assert_called_once()
            update_call = mock_collection.update_one.call_args
            assert update_call[0][0] == {"family_id": "fam_test123"}
            assert update_call[0][1]["$set"]["sbd_account.is_frozen"] is True
            assert update_call[0][1]["$set"]["sbd_account.frozen_by"] == "admin_user_1"
            assert update_call[0][1]["$set"]["sbd_account.freeze_reason"] == "Suspicious activity detected"

            # Verify notification was sent
            mock_notify.assert_called_once_with("fam_test123", "admin_user_1", "Suspicious activity detected", "frozen")

    @pytest.mark.asyncio
    async def test_freeze_family_account_insufficient_permissions(self, mock_family_data):
        """Test freezing account with insufficient permissions."""
        with patch.object(family_manager, "_get_family_by_id", return_value=mock_family_data):

            with pytest.raises(InsufficientPermissions) as exc_info:
                await family_manager.freeze_family_account("fam_test123", "non_admin_user", "Test reason")

            assert "Only family admins can freeze the account" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_freeze_already_frozen_account(self, mock_frozen_family_data):
        """Test freezing an already frozen account."""
        with patch.object(family_manager, "_get_family_by_id", return_value=mock_frozen_family_data):

            with pytest.raises(FamilyError) as exc_info:
                await family_manager.freeze_family_account("fam_test123", "admin_user_1", "Test reason")

            assert "Family account is already frozen" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_unfreeze_family_account_success(self, mock_frozen_family_data):
        """Test successful family account unfreezing."""
        with (
            patch.object(family_manager, "_get_family_by_id", return_value=mock_frozen_family_data),
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
            patch.object(family_manager, "_send_account_freeze_notification") as mock_notify,
        ):

            mock_collection = AsyncMock()
            mock_get_collection.return_value = mock_collection
            mock_collection.update_one = AsyncMock()

            result = await family_manager.unfreeze_family_account("fam_test123", "admin_user_1")

            # Verify result
            assert result["is_frozen"] is False
            assert result["frozen_by"] is None
            assert result["frozen_at"] is None
            assert result["unfrozen_by"] == "admin_user_1"
            assert "unfrozen_at" in result

            # Verify database update was called
            mock_collection.update_one.assert_called_once()
            update_call = mock_collection.update_one.call_args
            assert update_call[0][0] == {"family_id": "fam_test123"}
            assert update_call[0][1]["$set"]["sbd_account.is_frozen"] is False
            assert "$unset" in update_call[0][1]

            # Verify notification was sent
            mock_notify.assert_called_once_with("fam_test123", "admin_user_1", None, "unfrozen")

    @pytest.mark.asyncio
    async def test_unfreeze_not_frozen_account(self, mock_family_data):
        """Test unfreezing an account that is not frozen."""
        with patch.object(family_manager, "_get_family_by_id", return_value=mock_family_data):

            with pytest.raises(FamilyError) as exc_info:
                await family_manager.unfreeze_family_account("fam_test123", "admin_user_1")

            assert "Family account is not frozen" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_family_spending_frozen_account(self):
        """Test that spending validation fails for frozen accounts."""
        mock_virtual_account = {
            "username": "family_test",
            "is_virtual_account": True,
            "account_type": "family_virtual",
            "status": "active",
            "managed_by_family": "fam_test123",
        }

        mock_frozen_family = {
            "family_id": "fam_test123",
            "sbd_account": {
                "is_frozen": True,
                "frozen_by": "admin_user_1",
                "spending_permissions": {"member_user_1": {"can_spend": True, "spending_limit": 1000}},
            },
        }

        with (
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
            patch.object(family_manager, "_get_family_by_id", return_value=mock_frozen_family),
            patch.object(family_manager, "_is_user_family_member", return_value=True),
            patch.object(family_manager, "_log_spending_validation_failure") as mock_log_failure,
        ):

            mock_users_collection = AsyncMock()
            mock_get_collection.return_value = mock_users_collection
            mock_users_collection.find_one.return_value = mock_virtual_account

            result = await family_manager.validate_family_spending("family_test", "member_user_1", 500)

            # Should return False for frozen account
            assert result is False

            # Verify failure was logged with correct reason
            mock_log_failure.assert_called_once()
            log_call = mock_log_failure.call_args
            assert log_call[0][3] == "account_frozen"  # failure reason
            assert "frozen_by" in log_call[0][4]  # context should include frozen_by

    @pytest.mark.asyncio
    async def test_validate_family_spending_unfrozen_account(self):
        """Test that spending validation succeeds for unfrozen accounts with proper permissions."""
        mock_virtual_account = {
            "username": "family_test",
            "is_virtual_account": True,
            "account_type": "family_virtual",
            "status": "active",
            "managed_by_family": "fam_test123",
        }

        mock_family = {
            "family_id": "fam_test123",
            "sbd_account": {
                "is_frozen": False,
                "spending_permissions": {"member_user_1": {"can_spend": True, "spending_limit": 1000}},
            },
        }

        with (
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
            patch.object(family_manager, "_get_family_by_id", return_value=mock_family),
            patch.object(family_manager, "_is_user_family_member", return_value=True),
            patch.object(family_manager, "_log_spending_validation_success") as mock_log_success,
        ):

            mock_users_collection = AsyncMock()
            mock_get_collection.return_value = mock_users_collection
            mock_users_collection.find_one.return_value = mock_virtual_account

            result = await family_manager.validate_family_spending("family_test", "member_user_1", 500)

            # Should return True for unfrozen account with proper permissions
            assert result is True

            # Verify success was logged
            mock_log_success.assert_called_once()


class TestEmergencyUnfreezeControls:
    """Test emergency unfreeze procedures."""

    @pytest.fixture
    def mock_frozen_family(self):
        """Mock frozen family for emergency unfreeze tests."""
        return {
            "family_id": "fam_test123",
            "name": "Test Family",
            "admin_user_ids": ["admin_user_1"],
            "member_user_ids": ["member_user_1", "member_user_2", "member_user_3"],
            "member_count": 4,  # Include admin in count
            "sbd_account": {
                "is_frozen": True,
                "frozen_by": "admin_user_1",
                "frozen_at": datetime.now(timezone.utc),
                "freeze_reason": "Admin unavailable",
            },
        }

    @pytest.mark.asyncio
    async def test_initiate_emergency_unfreeze_success(self, mock_frozen_family):
        """Test successful emergency unfreeze initiation."""
        with (
            patch.object(family_manager, "_get_family_by_id", return_value=mock_frozen_family),
            patch.object(family_manager, "_is_user_family_member", return_value=True),
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
            patch.object(family_manager, "_send_emergency_unfreeze_notification") as mock_notify,
        ):

            mock_emergency_collection = AsyncMock()
            mock_get_collection.return_value = mock_emergency_collection
            mock_emergency_collection.find_one.return_value = None  # No existing request
            mock_emergency_collection.insert_one = AsyncMock()

            result = await family_manager.initiate_emergency_unfreeze(
                "fam_test123", "member_user_1", "Admin is unavailable and we need access"
            )

            # Verify result
            assert "request_id" in result
            assert result["family_id"] == "fam_test123"
            assert result["status"] == "pending"
            assert result["required_approvals"] == 2  # Should require 2 approvals for 4 members
            assert result["current_approvals"] == 1  # Requester automatically approves
            assert "expires_at" in result

            # Verify database insert was called
            mock_emergency_collection.insert_one.assert_called_once()

            # Verify notification was sent
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_initiate_emergency_unfreeze_existing_request(self, mock_frozen_family):
        """Test initiating emergency unfreeze when request already exists."""
        existing_request = {"family_id": "fam_test123", "request_type": "emergency_unfreeze", "status": "pending"}

        with (
            patch.object(family_manager, "_get_family_by_id", return_value=mock_frozen_family),
            patch.object(family_manager, "_is_user_family_member", return_value=True),
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
        ):

            mock_emergency_collection = AsyncMock()
            mock_get_collection.return_value = mock_emergency_collection
            mock_emergency_collection.find_one.return_value = existing_request

            with pytest.raises(FamilyError) as exc_info:
                await family_manager.initiate_emergency_unfreeze("fam_test123", "member_user_1", "Test reason")

            assert "emergency unfreeze request is already pending" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_approve_emergency_unfreeze_success(self):
        """Test successful emergency unfreeze approval."""
        mock_request = {
            "request_id": "req_test123",
            "family_id": "fam_test123",
            "request_type": "emergency_unfreeze",
            "status": "pending",
            "required_approvals": 2,
            "approvals": ["member_user_2"],  # One existing approval
            "rejections": [],  # Add rejections field
            "reason": "Admin unavailable",
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        }

        mock_family = {
            "family_id": "fam_test123",
            "member_user_ids": ["member_user_1", "member_user_2", "member_user_3"],
            "sbd_account": {"is_frozen": True},
        }

        with (
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
            patch.object(family_manager, "_is_user_family_member", return_value=True),
            patch.object(family_manager, "_get_family_by_id", return_value=mock_family),
            patch.object(family_manager, "unfreeze_family_account") as mock_unfreeze,
            patch.object(family_manager, "_send_emergency_unfreeze_executed_notification") as mock_notify,
        ):

            mock_emergency_collection = AsyncMock()
            mock_get_collection.return_value = mock_emergency_collection

            # First call returns original request, second call returns updated request
            mock_emergency_collection.find_one.side_effect = [
                mock_request,
                {**mock_request, "approvals": ["member_user_2", "member_user_1"]},
            ]
            mock_emergency_collection.update_one = AsyncMock()

            mock_unfreeze.return_value = {"is_frozen": False}

            result = await family_manager.approve_emergency_unfreeze("req_test123", "member_user_1")

            # Verify result
            assert result["approved"] is True
            assert result["current_approvals"] == 2
            assert result["threshold_met"] is True
            assert result["executed"] is True

            # Verify unfreeze was called
            mock_unfreeze.assert_called_once_with("fam_test123", "member_user_1")

            # Verify notification was sent
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_approve_emergency_unfreeze_insufficient_approvals(self):
        """Test emergency unfreeze approval with insufficient approvals."""
        mock_request = {
            "request_id": "req_test123",
            "family_id": "fam_test123",
            "request_type": "emergency_unfreeze",
            "status": "pending",
            "required_approvals": 3,
            "approvals": [],  # No existing approvals
            "rejections": [],  # Add rejections field
            "reason": "Admin unavailable",
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        }

        mock_family = {
            "family_id": "fam_test123",
            "member_user_ids": ["member_user_1", "member_user_2", "member_user_3", "member_user_4"],
        }

        with (
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
            patch.object(family_manager, "_is_user_family_member", return_value=True),
            patch.object(family_manager, "_get_family_by_id", return_value=mock_family),
        ):

            mock_emergency_collection = AsyncMock()
            mock_get_collection.return_value = mock_emergency_collection

            # First call returns original request, second call returns updated request
            mock_emergency_collection.find_one.side_effect = [
                mock_request,
                {**mock_request, "approvals": ["member_user_1"]},
            ]
            mock_emergency_collection.update_one = AsyncMock()

            result = await family_manager.approve_emergency_unfreeze("req_test123", "member_user_1")

            # Verify result
            assert result["approved"] is True
            assert result["current_approvals"] == 1
            assert result["threshold_met"] is False  # Not enough approvals yet

    @pytest.mark.asyncio
    async def test_reject_emergency_unfreeze_success(self):
        """Test successful emergency unfreeze rejection."""
        mock_request = {
            "request_id": "req_test123",
            "family_id": "fam_test123",
            "request_type": "emergency_unfreeze",
            "status": "pending",
            "approvals": [],
            "rejections": [],
            "reason": "Admin unavailable",
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=24),
        }

        with (
            patch.object(family_manager.db_manager, "get_collection") as mock_get_collection,
            patch.object(family_manager, "_is_user_family_member", return_value=True),
        ):

            mock_emergency_collection = AsyncMock()
            mock_get_collection.return_value = mock_emergency_collection
            mock_emergency_collection.find_one.return_value = mock_request
            mock_emergency_collection.update_one = AsyncMock()

            result = await family_manager.reject_emergency_unfreeze("req_test123", "member_user_1", "Not necessary")

            # Verify result
            assert result["rejected"] is True
            assert result["rejector_id"] == "member_user_1"
            assert result["reason"] == "Not necessary"

            # Verify database update was called
            mock_emergency_collection.update_one.assert_called_once()


class TestFreezeNotifications:
    """Test freeze status tracking and notifications."""

    @pytest.mark.asyncio
    async def test_send_account_freeze_notification(self):
        """Test sending account freeze notifications."""
        mock_family = {
            "family_id": "fam_test123",
            "member_user_ids": ["admin_user_1", "member_user_1", "member_user_2"],
        }

        mock_admin_user = {"username": "admin_user", "email": "admin@test.com"}

        with (
            patch.object(family_manager, "_get_family_by_id", return_value=mock_family),
            patch.object(family_manager, "_get_user_by_id", return_value=mock_admin_user),
        ):

            # This should not raise an exception
            await family_manager._send_account_freeze_notification(
                "fam_test123", "admin_user_1", "Suspicious activity", "frozen"
            )

            # The method logs the notification, so we just verify it completes successfully
            # In a real implementation, this would integrate with the notification system

    @pytest.mark.asyncio
    async def test_send_account_unfreeze_notification(self):
        """Test sending account unfreeze notifications."""
        mock_family = {
            "family_id": "fam_test123",
            "member_user_ids": ["admin_user_1", "member_user_1", "member_user_2"],
        }

        mock_admin_user = {"username": "admin_user", "email": "admin@test.com"}

        with (
            patch.object(family_manager, "_get_family_by_id", return_value=mock_family),
            patch.object(family_manager, "_get_user_by_id", return_value=mock_admin_user),
        ):

            # This should not raise an exception
            await family_manager._send_account_freeze_notification("fam_test123", "admin_user_1", None, "unfrozen")

            # The method logs the notification, so we just verify it completes successfully
            # In a real implementation, this would integrate with the notification system


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
