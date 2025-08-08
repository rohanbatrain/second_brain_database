"""
Tests for the family notification system.

This module tests the notification functionality including:
- Notification creation and delivery
- Read/unread status tracking
- Notification preferences
- API endpoints for notification management
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from second_brain_database.managers.family_manager import (
    FamilyManager,
    FamilyError,
    FamilyNotFound,
    InsufficientPermissions,
    ValidationError
)


class TestFamilyNotificationSystem:
    """Test suite for family notification system functionality."""

    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for testing."""
        mock_db = MagicMock()
        mock_db.get_collection = MagicMock()
        mock_db.log_query_start = MagicMock(return_value=0.0)
        mock_db.log_query_success = MagicMock()
        mock_db.log_query_error = MagicMock()
        return mock_db

    @pytest.fixture
    def mock_email_manager(self):
        """Mock email manager for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_security_manager(self):
        """Mock security manager for testing."""
        return MagicMock()

    @pytest.fixture
    def mock_redis_manager(self):
        """Mock Redis manager for testing."""
        return MagicMock()

    @pytest.fixture
    def family_manager(self, mock_db_manager, mock_email_manager, mock_security_manager, mock_redis_manager):
        """Create family manager instance with mocked dependencies."""
        return FamilyManager(
            db_manager=mock_db_manager,
            email_manager=mock_email_manager,
            security_manager=mock_security_manager,
            redis_manager=mock_redis_manager
        )

    @pytest.mark.asyncio
    async def test_get_family_notifications_success(self, family_manager, mock_db_manager):
        """Test successful retrieval of family notifications."""
        # Setup
        family_id = "fam_test123"
        user_id = "user_test456"
        
        # Mock family membership verification
        mock_users_collection = MagicMock()
        mock_users_collection.find_one = AsyncMock(return_value={"_id": user_id})
        
        # Mock notifications collection
        mock_notifications_collection = MagicMock()
        mock_notifications_collection.count_documents = AsyncMock(side_effect=[10, 3])  # total, unread
        
        # Mock notification data
        mock_notifications = [
            {
                "notification_id": "notif_123",
                "type": "sbd_spend",
                "title": "SBD Token Spending",
                "message": "John spent 100 SBD tokens",
                "data": {"amount": 100},
                "status": "sent",
                "created_at": datetime.now(timezone.utc),
                "read_by": {}
            },
            {
                "notification_id": "notif_456",
                "type": "sbd_deposit",
                "title": "SBD Token Deposit",
                "message": "Jane deposited 200 SBD tokens",
                "data": {"amount": 200},
                "status": "sent",
                "created_at": datetime.now(timezone.utc),
                "read_by": {user_id: datetime.now(timezone.utc)}
            }
        ]
        
        mock_cursor = MagicMock()
        mock_cursor.sort = MagicMock(return_value=mock_cursor)
        mock_cursor.skip = MagicMock(return_value=mock_cursor)
        mock_cursor.limit = MagicMock(return_value=mock_cursor)
        mock_cursor.to_list = AsyncMock(return_value=mock_notifications)
        mock_notifications_collection.find = MagicMock(return_value=mock_cursor)
        
        mock_db_manager.get_collection.side_effect = lambda name: {
            "users": mock_users_collection,
            "family_notifications": mock_notifications_collection
        }[name]
        
        # Mock _verify_family_membership
        family_manager._verify_family_membership = AsyncMock()
        
        # Execute
        result = await family_manager.get_family_notifications(
            family_id=family_id,
            user_id=user_id,
            limit=20,
            offset=0
        )
        
        # Verify
        assert result["total_count"] == 10
        assert result["unread_count"] == 3
        assert len(result["notifications"]) == 2
        assert result["notifications"][0]["notification_id"] == "notif_123"
        assert result["notifications"][0]["is_read"] is False
        assert result["notifications"][1]["notification_id"] == "notif_456"
        assert result["notifications"][1]["is_read"] is True

    @pytest.mark.asyncio
    async def test_get_family_notifications_insufficient_permissions(self, family_manager):
        """Test get notifications with insufficient permissions."""
        family_id = "fam_test123"
        user_id = "user_test456"
        
        # Mock _verify_family_membership to raise exception
        family_manager._verify_family_membership = AsyncMock(
            side_effect=InsufficientPermissions("User is not a member of this family")
        )
        
        # Execute and verify
        with pytest.raises(InsufficientPermissions):
            await family_manager.get_family_notifications(
                family_id=family_id,
                user_id=user_id
            )

    @pytest.mark.asyncio
    async def test_mark_notifications_read_success(self, family_manager, mock_db_manager):
        """Test successfully marking notifications as read."""
        # Setup
        family_id = "fam_test123"
        user_id = "user_test456"
        notification_ids = ["notif_123", "notif_456"]
        
        # Mock collections
        mock_notifications_collection = MagicMock()
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 2
        mock_notifications_collection.update_many = AsyncMock(return_value=mock_update_result)
        
        mock_db_manager.get_collection.return_value = mock_notifications_collection
        
        # Mock dependencies
        family_manager._verify_family_membership = AsyncMock()
        family_manager._update_user_notification_count = AsyncMock()
        
        # Execute
        result = await family_manager.mark_notifications_read(
            family_id=family_id,
            user_id=user_id,
            notification_ids=notification_ids
        )
        
        # Verify
        assert result["marked_count"] == 2
        assert len(result["updated_notifications"]) == 2
        mock_notifications_collection.update_many.assert_called_once()
        family_manager._update_user_notification_count.assert_called_once_with(user_id, family_id)

    @pytest.mark.asyncio
    async def test_mark_all_notifications_read_success(self, family_manager, mock_db_manager):
        """Test successfully marking all notifications as read."""
        # Setup
        family_id = "fam_test123"
        user_id = "user_test456"
        
        # Mock collections
        mock_notifications_collection = MagicMock()
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 5
        mock_notifications_collection.update_many = AsyncMock(return_value=mock_update_result)
        
        mock_db_manager.get_collection.return_value = mock_notifications_collection
        
        # Mock dependencies
        family_manager._verify_family_membership = AsyncMock()
        family_manager._update_user_notification_count = AsyncMock()
        
        # Execute
        result = await family_manager.mark_all_notifications_read(
            family_id=family_id,
            user_id=user_id
        )
        
        # Verify
        assert result["marked_count"] == 5
        mock_notifications_collection.update_many.assert_called_once()
        family_manager._update_user_notification_count.assert_called_once_with(
            user_id, family_id, force_count=0
        )

    @pytest.mark.asyncio
    async def test_update_notification_preferences_success(self, family_manager, mock_db_manager):
        """Test successfully updating notification preferences."""
        # Setup
        user_id = "user_test456"
        preferences = {
            "email_notifications": True,
            "push_notifications": False,
            "sms_notifications": False
        }
        
        # Mock collections
        mock_users_collection = MagicMock()
        mock_update_result = MagicMock()
        mock_update_result.modified_count = 1
        mock_users_collection.update_one = AsyncMock(return_value=mock_update_result)
        mock_users_collection.find_one = AsyncMock(return_value={
            "_id": user_id,
            "family_notifications": {
                "preferences": preferences
            }
        })
        
        mock_db_manager.get_collection.return_value = mock_users_collection
        
        # Execute
        result = await family_manager.update_notification_preferences(
            user_id=user_id,
            preferences=preferences
        )
        
        # Verify
        assert result["preferences"] == preferences
        mock_users_collection.update_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_notification_preferences_invalid_preferences(self, family_manager):
        """Test updating notification preferences with invalid keys."""
        user_id = "user_test456"
        invalid_preferences = {
            "invalid_key": True,
            "email_notifications": True
        }
        
        # Execute and verify
        with pytest.raises(ValidationError) as exc_info:
            await family_manager.update_notification_preferences(
                user_id=user_id,
                preferences=invalid_preferences
            )
        
        assert "Invalid preference keys" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_notification_preferences_success(self, family_manager, mock_db_manager):
        """Test successfully getting notification preferences."""
        # Setup
        user_id = "user_test456"
        
        # Mock collections
        mock_users_collection = MagicMock()
        mock_users_collection.find_one = AsyncMock(return_value={
            "_id": user_id,
            "family_notifications": {
                "preferences": {
                    "email_notifications": True,
                    "push_notifications": True,
                    "sms_notifications": False
                },
                "unread_count": 3,
                "last_checked": datetime.now(timezone.utc)
            }
        })
        
        mock_db_manager.get_collection.return_value = mock_users_collection
        
        # Execute
        result = await family_manager.get_notification_preferences(user_id=user_id)
        
        # Verify
        assert "preferences" in result
        assert result["preferences"]["email_notifications"] is True
        assert result["unread_count"] == 3
        assert "last_checked" in result

    @pytest.mark.asyncio
    async def test_send_sbd_transaction_notification_spend(self, family_manager, mock_db_manager):
        """Test sending SBD spending notification."""
        # Setup
        family_id = "fam_test123"
        from_user_id = "user_sender"
        to_user_id = "user_receiver"
        amount = 100
        
        # Mock dependencies
        family_manager._get_family_by_id = AsyncMock(return_value={
            "name": "Test Family",
            "sbd_account": {
                "account_username": "family_test",
                "notification_settings": {
                    "large_transaction_threshold": 1000,
                    "notify_admins_only": False
                }
            }
        })
        
        family_manager._get_user_by_id = AsyncMock(side_effect=lambda uid: {
            "user_sender": {"username": "sender_user"},
            "user_receiver": {"username": "receiver_user"}
        }[uid])
        
        family_manager._get_family_member_ids = AsyncMock(return_value=["user1", "user2", "user3"])
        family_manager._create_family_notification = AsyncMock()
        family_manager._update_user_notification_count = AsyncMock()
        
        # Execute
        await family_manager.send_sbd_transaction_notification(
            family_id=family_id,
            transaction_type="spend",
            amount=amount,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            transaction_id="txn_123"
        )
        
        # Verify
        family_manager._create_family_notification.assert_called_once()
        call_args = family_manager._create_family_notification.call_args
        notification_data = call_args[0][2]  # Third argument is notification_data
        
        assert notification_data["type"] == "sbd_spend"
        assert notification_data["title"] == "SBD Token Spending"
        assert "sender_user" in notification_data["message"]
        assert "receiver_user" in notification_data["message"]
        assert notification_data["data"]["amount"] == amount
        assert notification_data["data"]["transaction_id"] == "txn_123"

    @pytest.mark.asyncio
    async def test_send_sbd_transaction_notification_large_transaction(self, family_manager, mock_db_manager):
        """Test sending notification for large transaction."""
        # Setup
        family_id = "fam_test123"
        from_user_id = "user_sender"
        amount = 1500  # Above threshold
        
        # Mock dependencies
        family_manager._get_family_by_id = AsyncMock(return_value={
            "name": "Test Family",
            "admin_user_ids": ["admin1", "admin2"],
            "sbd_account": {
                "account_username": "family_test",
                "notification_settings": {
                    "large_transaction_threshold": 1000,
                    "notify_admins_only": True
                }
            }
        })
        
        family_manager._get_user_by_id = AsyncMock(return_value={"username": "sender_user"})
        family_manager._get_family_member_ids = AsyncMock(return_value=["user1", "user2", "user3"])
        family_manager._create_family_notification = AsyncMock()
        family_manager._update_user_notification_count = AsyncMock()
        
        # Execute
        await family_manager.send_sbd_transaction_notification(
            family_id=family_id,
            transaction_type="spend",
            amount=amount,
            from_user_id=from_user_id
        )
        
        # Verify
        family_manager._create_family_notification.assert_called_once()
        call_args = family_manager._create_family_notification.call_args
        
        # Should notify only admins for large transactions
        recipient_ids = call_args[0][1]  # Second argument is recipient_ids
        notification_data = call_args[0][2]  # Third argument is notification_data
        
        assert recipient_ids == ["admin1", "admin2"]
        assert notification_data["type"] == "large_transaction"
        assert "Large Transaction Alert" in notification_data["title"]

    @pytest.mark.asyncio
    async def test_send_spending_limit_notification(self, family_manager, mock_db_manager):
        """Test sending spending limit notification."""
        # Setup
        family_id = "fam_test123"
        user_id = "user_test456"
        attempted_amount = 500
        limit = 300
        
        # Mock dependencies
        family_manager._get_family_by_id = AsyncMock(return_value={
            "admin_user_ids": ["admin1", "admin2"],
            "sbd_account": {
                "account_username": "family_test"
            }
        })
        
        family_manager._get_user_by_id = AsyncMock(return_value={"username": "test_user"})
        family_manager._create_family_notification = AsyncMock()
        family_manager._update_user_notification_count = AsyncMock()
        
        # Execute
        await family_manager.send_spending_limit_notification(
            family_id=family_id,
            user_id=user_id,
            attempted_amount=attempted_amount,
            limit=limit
        )
        
        # Verify
        family_manager._create_family_notification.assert_called_once()
        call_args = family_manager._create_family_notification.call_args
        
        recipient_ids = call_args[0][1]
        notification_data = call_args[0][2]
        
        # Should notify admins and the user who reached the limit
        assert user_id in recipient_ids
        assert "admin1" in recipient_ids
        assert "admin2" in recipient_ids
        assert notification_data["type"] == "spending_limit_reached"
        assert notification_data["data"]["attempted_amount"] == attempted_amount
        assert notification_data["data"]["spending_limit"] == limit

    @pytest.mark.asyncio
    async def test_update_user_notification_count(self, family_manager, mock_db_manager):
        """Test updating user notification count."""
        # Setup
        user_id = "user_test456"
        family_id = "fam_test123"
        
        # Mock collections
        mock_users_collection = MagicMock()
        mock_users_collection.update_one = AsyncMock()
        
        mock_notifications_collection = MagicMock()
        mock_notifications_collection.count_documents = AsyncMock(return_value=5)
        
        mock_db_manager.get_collection.side_effect = lambda name: {
            "users": mock_users_collection,
            "family_notifications": mock_notifications_collection
        }[name]
        
        # Execute
        await family_manager._update_user_notification_count(user_id, family_id)
        
        # Verify
        mock_notifications_collection.count_documents.assert_called_once()
        mock_users_collection.update_one.assert_called_once()
        
        # Check the update call
        call_args = mock_users_collection.update_one.call_args
        update_data = call_args[0][1]["$set"]
        assert update_data["family_notifications.unread_count"] == 5

    @pytest.mark.asyncio
    async def test_update_user_notification_count_force_count(self, family_manager, mock_db_manager):
        """Test updating user notification count with forced value."""
        # Setup
        user_id = "user_test456"
        family_id = "fam_test123"
        force_count = 0
        
        # Mock collections
        mock_users_collection = MagicMock()
        mock_users_collection.update_one = AsyncMock()
        
        mock_db_manager.get_collection.return_value = mock_users_collection
        
        # Execute
        await family_manager._update_user_notification_count(user_id, family_id, force_count=force_count)
        
        # Verify
        mock_users_collection.update_one.assert_called_once()
        
        # Check the update call
        call_args = mock_users_collection.update_one.call_args
        update_data = call_args[0][1]["$set"]
        assert update_data["family_notifications.unread_count"] == 0