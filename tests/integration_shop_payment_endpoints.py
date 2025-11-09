#!/usr/bin/env python3
"""
Comprehensive test suite for shop payment method endpoints.

Tests all payment-related functionality including:
- Personal token payments
- Family token payments with permissions
- Payment validation and processing
- Error handling for insufficient funds
- Family spending limits and permissions
- Account freezing protection
- Transaction logging and notifications
- Backward compatibility (legacy vs new formats)
"""

import asyncio
from datetime import datetime, timezone
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from unittest.mock import patch

import bcrypt
from fastapi.testclient import TestClient
import pytest

from second_brain_database.database import db_manager
from second_brain_database.main import app
from second_brain_database.managers.family_manager import family_manager
from second_brain_database.routes.auth.services.auth.login import create_access_token


async def _create_test_family(client, user_token, family_token, test_user, family_user):
    """Create a test family for testing family payments."""
    # Create family
    headers = {"Authorization": f"Bearer {user_token}"}
    family_data = {"name": "Test Payment Family"}
    response = client.post("/family/create", json=family_data, headers=headers)
    assert response.status_code == 201
    family_id = response.json()["family"]["family_id"]

    # Invite family member
    invite_data = {"identifier": family_user["email"], "relationship_type": "child", "identifier_type": "email"}
    response = client.post(f"/family/{family_id}/invite", json=invite_data, headers=headers)
    assert response.status_code == 201

    # Accept invitation as family member
    headers = {"Authorization": f"Bearer {family_token}"}
    response = client.get("/family/invitations/received", headers=headers)
    assert response.status_code == 200
    invitations = response.json()["invitations"]
    assert len(invitations) > 0

    invitation_id = invitations[0]["invitation_id"]
    response = client.post(f"/family/invitation/{invitation_id}/respond", json={"action": "accept"}, headers=headers)
    assert response.status_code == 200

    # Set up family SBD account with tokens and permissions
    await family_manager.setup_family_sbd_account(family_id, test_user["username"])

    # Add tokens to family account and set permissions
    family_data = await family_manager.get_family_by_id(family_id)
    family_username = family_data["sbd_account"]["account_username"]

    users_collection = db_manager.get_collection("users")
    await users_collection.update_one({"username": family_username}, {"$set": {"sbd_tokens": 500}})

    # Set spending permissions for family member
    await family_manager.update_spending_permissions(
        family_id,
        test_user["username"],  # admin_id
        family_user["username"],  # target_user_id
        {"can_spend": True, "spending_limit": 200},  # Limited spending for testing
    )

    return family_id


class TestShopPaymentEndpoints:
    @patch("second_brain_database.routes.auth.services.auth.login.get_current_user")
    @patch("second_brain_database.database.db_manager.get_collection")
    @patch("second_brain_database.managers.family_manager.family_manager.get_user_families")
    @patch("second_brain_database.managers.family_manager.family_manager.get_family_sbd_account")
    def test_payment_options_endpoint(
        self, mock_get_family_sbd_account, mock_get_user_families, mock_get_collection, mock_get_current_user
    ):
        """Test getting payment options for a user."""
        # Mock the current user
        mock_user = {"_id": "test_user_id", "username": "testuser", "email": "test@example.com"}
        mock_get_current_user.return_value = mock_user

        # Mock database collection
        mock_collection = AsyncMock()
        mock_get_collection.return_value = mock_collection

        # Mock user families
        mock_get_user_families.return_value = [{"family_id": "test_family_id", "name": "Test Family"}]

        # Mock family SBD account
        mock_get_family_sbd_account.return_value = {
            "spending_permissions": {"test_user_id": {"can_spend": True, "spending_limit": 1000}},
            "is_frozen": False,
            "balance": 500,
        }

        # Mock user document in database
        mock_collection.find_one.return_value = mock_user

        # Create test client
        from second_brain_database.main import app

        client = TestClient(app)

        # Make request with mock JWT token
        headers = {"Authorization": "Bearer mock_token"}
        response = client.get("/shop/payment-options", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "payment_options" in data["data"]
        assert "personal" in data["data"]["payment_options"]
        assert "family" in data["data"]["payment_options"]

    @pytest.mark.asyncio
    async def test_theme_purchase_personal_legacy_format(self):
        """Test theme purchase with personal tokens using legacy format."""
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker/1.0.0"}

        # Legacy format - no payment_method field
        purchase_data = {"theme_id": "emotion_tracker-serenityGreen"}

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "theme" in data
        assert data["theme"]["theme_id"] == "emotion_tracker-serenityGreen"
        assert data["theme"]["price"] == 250

        # Check that payment details are NOT included in legacy format
        assert "payment" not in data

        # Verify tokens were deducted
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"username": self.test_user["username"]})
        assert user["sbd_tokens"] == 750  # 1000 - 250

    @pytest.mark.asyncio
    async def test_theme_purchase_personal_new_format(self):
        """Test theme purchase with personal tokens using new format."""
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-pacificBlue", "payment_method": {"type": "personal"}}

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "theme" in data
        assert "payment" in data

        payment = data["payment"]
        assert payment["payment_type"] == "personal"
        assert payment["from_account"] == self.test_user["username"]
        assert payment["amount"] == 250

        # Verify tokens were deducted
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"username": self.test_user["username"]})
        assert user["sbd_tokens"] == 500  # 750 - 250

    @pytest.mark.asyncio
    async def test_theme_purchase_family_success(self):
        """Test theme purchase with family tokens - success case."""
        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-blushRose",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "theme" in data
        assert "payment" in data

        payment = data["payment"]
        assert payment["payment_type"] == "family"
        assert payment["family_id"] == self.test_family_id
        assert payment["amount"] == 250
        assert payment["family_member"] == self.family_user["username"]

        # Verify family tokens were deducted
        family_data = await family_manager.get_family_by_id(self.test_family_id)
        family_username = family_data["sbd_account"]["account_username"]
        users_collection = db_manager.get_collection("users")
        family_account = await users_collection.find_one({"username": family_username})
        assert family_account["sbd_tokens"] == 250  # 500 - 250

    @pytest.mark.asyncio
    async def test_theme_purchase_family_insufficient_funds(self):
        """Test theme purchase with family tokens - insufficient funds."""
        # First spend most of the family tokens
        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        # Spend 200 tokens (leaving 50, but theme costs 250)
        purchase_data = {
            "theme_id": "emotion_tracker-cloudGray",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 400

        data = response.json()
        assert data["status"] == "error"
        assert "INSUFFICIENT_PERSONAL_TOKENS" in data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_theme_purchase_family_no_permission(self):
        """Test theme purchase with family tokens - no spending permission."""
        # Remove spending permission
        await family_manager.update_spending_permissions(
            self.test_family_id,
            self.test_user["username"],  # admin_id
            self.family_user["username"],  # target_user_id
            {"can_spend": False, "spending_limit": 200},
        )

        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-sunsetPeach",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 403

        data = response.json()
        assert data["status"] == "error"
        assert "FAMILY_SPENDING_DENIED" in data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_theme_purchase_family_exceeds_limit(self):
        """Test theme purchase with family tokens - exceeds spending limit."""
        # Set low spending limit
        await family_manager.update_spending_permissions(
            self.test_family_id,
            self.test_user["username"],  # admin_id
            self.family_user["username"],  # target_user_id
            {"can_spend": True, "spending_limit": 200},  # Theme costs 250, so this should fail
        )

        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-goldenYellow",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 403

        data = response.json()
        assert data["status"] == "error"
        assert "FAMILY_SPENDING_DENIED" in data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_theme_purchase_family_frozen_account(self):
        """Test theme purchase with family tokens - frozen account."""
        # Freeze the family account
        await family_manager.freeze_family_account(
            self.test_family_id, self.test_user["username"], "Test freeze"  # admin_id
        )

        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-forestGreen",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 403

        data = response.json()
        assert data["status"] == "error"
        assert "FAMILY_SPENDING_DENIED" in data["detail"]["error"]
        assert "frozen" in data["detail"]["message"].lower()

    @pytest.mark.asyncio
    async def test_theme_purchase_invalid_theme(self):
        """Test theme purchase with invalid theme ID."""
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "invalid_theme_id", "payment_method": {"type": "personal"}}

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 400

        data = response.json()
        assert data["status"] == "error"
        assert "Invalid or missing theme_id" in data["detail"]

    @pytest.mark.asyncio
    async def test_theme_purchase_already_owned(self):
        """Test theme purchase when user already owns the theme."""
        # First purchase
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-midnightLavender", "payment_method": {"type": "personal"}}

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        # Try to purchase again
        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 400

        data = response.json()
        assert data["status"] == "error"
        assert "Theme already owned" in data["detail"]

    @pytest.mark.asyncio
    async def test_theme_purchase_invalid_client(self):
        """Test theme purchase with invalid client (wrong user agent)."""
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "invalid_client/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-crimsonRed", "payment_method": {"type": "personal"}}

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 403

        data = response.json()
        assert data["status"] == "error"
        assert "Shop access denied: invalid client" in data["detail"]

    @pytest.mark.asyncio
    async def test_avatar_purchase_endpoints(self):
        """Test avatar purchase endpoints with both payment methods."""
        # Test personal token purchase
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"avatar_id": "emotion_tracker-static-avatar-cat-1", "payment_method": {"type": "personal"}}

        response = self.client.post("/shop/avatars/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "avatar" in data
        assert data["avatar"]["avatar_id"] == "emotion_tracker-static-avatar-cat-1"

        # Test family token purchase
        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "avatar_id": "emotion_tracker-static-avatar-dog-1",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        response = self.client.post("/shop/avatars/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "avatar" in data
        assert "payment" in data
        assert data["payment"]["payment_type"] == "family"

    @pytest.mark.asyncio
    async def test_banner_purchase_endpoints(self):
        """Test banner purchase endpoints with both payment methods."""
        # Test personal token purchase
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"banner_id": "emotion_tracker-static-banner-earth-1", "payment_method": {"type": "personal"}}

        response = self.client.post("/shop/banners/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "banner" in data

        # Test family token purchase
        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "banner_id": "emotion_tracker-static-banner-earth-1",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        response = self.client.post("/shop/banners/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "banner" in data
        assert "payment" in data

    @pytest.mark.asyncio
    async def test_bundle_purchase_with_auto_population(self):
        """Test bundle purchase with automatic content population."""
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"bundle_id": "emotion_tracker-avatars-cat-bundle", "payment_method": {"type": "personal"}}

        response = self.client.post("/shop/bundles/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "bundle" in data
        assert "bundle_contents" in data

        # Check that bundle contents were auto-populated
        bundle_contents = data["bundle_contents"]
        assert "avatars" in bundle_contents
        assert len(bundle_contents["avatars"]) == 20  # Cat bundle has 20 avatars

        # Verify avatars were added to user's owned collection
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"username": self.test_user["username"]})
        owned_avatars = user.get("avatars_owned", [])

        # Check that some avatars from the bundle were added
        cat_avatars = [avatar for avatar in owned_avatars if "cat" in avatar.get("avatar_id", "")]
        assert len(cat_avatars) > 0

    @pytest.mark.asyncio
    async def test_cart_checkout_functionality(self):
        """Test cart checkout with payment methods."""
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker_app/1.0.0"}

        # Add items to cart
        cart_items = [
            {"item_id": "emotion_tracker-serenityGreen", "item_type": "theme"},
            {"item_id": "emotion_tracker-static-avatar-cat-2", "item_type": "avatar"},
        ]

        for item in cart_items:
            add_data = {"item_id": item["item_id"], "item_type": item["item_type"]}
            response = self.client.post("/shop/cart/add", json=add_data, headers=headers)
            assert response.status_code == 200

        # Checkout with personal tokens
        checkout_data = {"payment_method": {"type": "personal"}}

        response = self.client.post("/shop/cart/checkout", json=checkout_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert "checked_out" in data
        assert len(data["checked_out"]) == 2
        assert "payment" in data
        assert data["payment"]["payment_type"] == "personal"

        # Verify cart is empty
        response = self.client.get("/shop/cart", headers=headers)
        assert response.status_code == 200
        cart_data = response.json()
        assert len(cart_data["cart"]) == 0

    @pytest.mark.asyncio
    async def test_family_notifications_on_purchase(self):
        """Test that family notifications are sent for family token purchases."""
        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-deepPurple",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        # Mock the notification sending to verify it's called
        with patch.object(family_manager, "send_family_notification") as mock_notify:
            response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
            assert response.status_code == 200

            # Verify notification was sent
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert call_args[0][0] == self.test_family_id  # family_id
            assert call_args[0][1] == "sbd_spend"  # notification_type
            notification_data = call_args[0][2]
            assert notification_data["amount"] == 250
            assert notification_data["spender_username"] == self.family_user["username"]
            assert notification_data["shop_item_type"] == "theme"


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])


class TestShopPaymentSystemErrorProof:
    """Comprehensive error-proof tests using real database operations and authentication."""

    @pytest.fixture
    async def test_db_setup(self):
        """Set up test database with real users, families, and accounts."""
        # Connect to database
        await db_manager.connect()

        # Create test users
        test_user = {
            "username": "test_user_comprehensive",
            "email": "test_comprehensive@example.com",
            "password": "testpass123",
        }

        family_user = {
            "username": "test_family_member_comprehensive",
            "email": "family_comprehensive@example.com",
            "password": "testpass123",
        }

        # Create users in database
        users_collection = db_manager.get_collection("users")

        # Clean up any existing test data
        await users_collection.delete_many({"username": {"$in": [test_user["username"], family_user["username"]]}})

        # Create test users with tokens
        test_user_doc = {
            **test_user,
            "sbd_tokens": 1000,
            "themes_owned": [],
            "avatars_owned": [],
            "banners_owned": [],
            "bundles_owned": [],
            "cart": [],
            "hashed_password": bcrypt.hashpw(test_user["password"].encode(), bcrypt.gensalt()).decode(),
            "created_at": datetime.now(timezone.utc),
        }

        family_user_doc = {
            **family_user,
            "sbd_tokens": 100,
            "themes_owned": [],
            "avatars_owned": [],
            "banners_owned": [],
            "bundles_owned": [],
            "cart": [],
            "hashed_password": bcrypt.hashpw(family_user["password"].encode(), bcrypt.gensalt()).decode(),
            "created_at": datetime.now(timezone.utc),
        }

        await users_collection.insert_many([test_user_doc, family_user_doc])

        # Create JWT tokens
        user_token = await create_access_token({"sub": test_user["username"]})
        family_token = await create_access_token({"sub": family_user["username"]})

        # Create test family
        test_family_id = await _create_test_family(TestClient(app), user_token, family_token, test_user, family_user)

        # Get test family data
        test_family = await family_manager.get_family_by_id(test_family_id)

        yield {
            "test_user": test_user,
            "family_user": family_user,
            "user_token": user_token,
            "family_token": family_token,
            "test_family_id": test_family_id,
            "test_family": test_family,
            "jwt_token": user_token,  # For backward compatibility
        }

        # Cleanup
        await users_collection.delete_many({"username": {"$in": [test_user["username"], family_user["username"]]}})

    @patch("second_brain_database.routes.auth.dependencies.enforce_all_lockdowns")
    async def test_payment_options_comprehensive(self, mock_enforce_lockdowns, test_db_setup):
        """Test comprehensive payment options retrieval with real database operations."""
        # Setup mock to return the test user directly
        users_collection = db_manager.get_collection("users")
        user_doc = await users_collection.find_one({"username": test_db_setup["test_user"]["username"]})
        mock_enforce_lockdowns.return_value = user_doc

        # Create test client with proper headers
        client = TestClient(app)
        headers = {
            "Authorization": f"Bearer {test_db_setup['jwt_token']}",
            "User-Agent": "emotion_tracker/1.0.0",
            "X-Forwarded-For": "127.0.0.1",
        }

        # Test payment options endpoint
        response = client.get("/shop/payment-options", headers=headers)

        # Assert successful response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "payment_options" in data["data"]

        # Verify personal balance
        personal_balance = data["data"]["payment_options"]["personal"]["balance"]
        assert personal_balance == 1000  # From test setup

        # Verify family accounts (should include test family)
        family_accounts = data["data"]["payment_options"]["family"]
        assert len(family_accounts) >= 1

        # Find the test family account
        test_family = None
        for family in family_accounts:
            if family["family_id"] == test_db_setup["test_family"]["family_id"]:
                test_family = family
                break

        assert test_family is not None
        assert test_family["balance"] == 5000  # From test setup
        assert test_family["can_spend"] is True  # User has spending permissions

    @pytest.mark.asyncio
    async def test_personal_payment_success(self, setup_test_data):
        """Test successful personal token payment."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-oceanBlue", "payment_method": {"type": "personal"}}

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["theme"]["theme_id"] == "emotion_tracker-oceanBlue"
        assert response_data["payment"]["payment_type"] == "personal"
        assert response_data["payment"]["amount"] == 250

        # Verify database state
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"username": data["test_user"]["username"]})
        assert user["sbd_tokens"] == 750  # 1000 - 250
        assert "emotion_tracker-oceanBlue" in [t["theme_id"] for t in user["themes_owned"]]

    @pytest.mark.asyncio
    async def test_family_payment_success(self, setup_test_data):
        """Test successful family token payment."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['family_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-forestGreen",
            "payment_method": {"type": "family", "family_id": data["test_family_id"]},
        }

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["status"] == "success"
        assert response_data["payment"]["payment_type"] == "family"
        assert response_data["payment"]["family_id"] == data["test_family_id"]

        # Verify family account was charged
        family_data = await family_manager.get_family_by_id(data["test_family_id"])
        family_username = family_data["sbd_account"]["account_username"]
        users_collection = db_manager.get_collection("users")
        family_account = await users_collection.find_one({"username": family_username})
        assert family_account["sbd_tokens"] == 250  # 500 - 250

    @pytest.mark.asyncio
    async def test_family_payment_success(self):
        """Test successful family token payment."""
        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-forestGreen",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "success"
        assert data["payment"]["payment_type"] == "family"
        assert data["payment"]["family_id"] == self.test_family_id

        # Verify family account was charged
        family_data = await family_manager.get_family_by_id(self.test_family_id)
        family_username = family_data["sbd_account"]["account_username"]
        users_collection = db_manager.get_collection("users")
        family_account = await users_collection.find_one({"username": family_username})
        assert family_account["sbd_tokens"] == 250  # 500 - 250

    @pytest.mark.asyncio
    async def test_insufficient_personal_tokens(self, setup_test_data):
        """Test payment failure due to insufficient personal tokens."""
        data = setup_test_data
        # Reduce user tokens
        users_collection = db_manager.get_collection("users")
        await users_collection.update_one(
            {"username": data["test_user"]["username"]}, {"$set": {"sbd_tokens": 100}}  # Less than theme price of 250
        )

        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-sunsetOrange", "payment_method": {"type": "personal"}}

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 400

        response_data = response.json()
        assert response_data["status"] == "error"
        assert "INSUFFICIENT_PERSONAL_TOKENS" in response_data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_family_no_spending_permission(self, setup_test_data):
        """Test family payment failure due to no spending permission."""
        data = setup_test_data
        await family_manager.update_spending_permissions(
            data["test_family_id"],
            data["test_user"]["username"],
            data["family_user"]["username"],
            {"can_spend": False, "spending_limit": 1000},
        )

        headers = {"Authorization": f"Bearer {data['family_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-midnightBlue",
            "payment_method": {"type": "family", "family_id": data["test_family_id"]},
        }

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 403

        response_data = response.json()
        assert response_data["status"] == "error"
        assert "FAMILY_SPENDING_DENIED" in response_data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_family_exceeds_spending_limit(self, setup_test_data):
        """Test family payment failure due to exceeding spending limit."""
        data = setup_test_data
        await family_manager.update_spending_permissions(
            data["test_family_id"],
            data["test_user"]["username"],
            data["family_user"]["username"],
            {"can_spend": True, "spending_limit": 100},  # Less than theme price
        )

        headers = {"Authorization": f"Bearer {data['family_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-dawnPink",
            "payment_method": {"type": "family", "family_id": data["test_family_id"]},
        }

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 403

        response_data = response.json()
        assert response_data["status"] == "error"
        assert "FAMILY_SPENDING_DENIED" in response_data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_family_frozen_account(self, setup_test_data):
        """Test family payment failure due to frozen account."""
        data = setup_test_data
        await family_manager.freeze_family_account(
            data["test_family_id"], data["test_user"]["username"], "Test freeze for payment testing"
        )

        headers = {"Authorization": f"Bearer {data['family_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-stormGray",
            "payment_method": {"type": "family", "family_id": data["test_family_id"]},
        }

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 403

        response_data = response.json()
        assert response_data["status"] == "error"
        assert "FAMILY_SPENDING_DENIED" in response_data["detail"]["error"]

    @pytest.mark.asyncio
    async def test_invalid_theme_id(self, setup_test_data):
        """Test payment failure due to invalid theme ID."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "invalid_theme_12345", "payment_method": {"type": "personal"}}

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 400

        response_data = response.json()
        assert response_data["status"] == "error"
        assert "Invalid or missing theme_id" in response_data["detail"]

    @pytest.mark.asyncio
    async def test_already_owned_theme(self, setup_test_data):
        """Test payment failure when theme is already owned."""
        data = setup_test_data
        # First purchase
        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-lavenderPurple", "payment_method": {"type": "personal"}}

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        # Attempt to purchase again
        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 400

        response_data = response.json()
        assert response_data["status"] == "error"
        assert "Theme already owned" in response_data["detail"]

    @pytest.mark.asyncio
    async def test_invalid_client_user_agent(self, setup_test_data):
        """Test payment failure due to invalid client user agent."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "invalid_client/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-coralRed", "payment_method": {"type": "personal"}}

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 403

        response_data = response.json()
        assert response_data["status"] == "error"
        assert "Shop access denied: invalid client" in response_data["detail"]

    @pytest.mark.asyncio
    async def test_cart_operations(self, setup_test_data):
        """Test cart add, view, and checkout operations."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker_app/1.0.0"}

        # Add items to cart
        cart_items = [
            {"item_id": "emotion_tracker-static-avatar-dog-1", "item_type": "avatar"},
            {"item_id": "emotion_tracker-static-banner-space-1", "item_type": "banner"},
        ]

        for item in cart_items:
            add_data = {"item_id": item["item_id"], "item_type": item["item_type"]}
            response = data["client"].post("/shop/cart/add", json=add_data, headers=headers)
            assert response.status_code == 200

        # Verify cart contents
        response = data["client"].get("/shop/cart", headers=headers)
        assert response.status_code == 200
        cart_data = response.json()
        assert len(cart_data["cart"]) == 2

        # Checkout cart
        checkout_data = {"payment_method": {"type": "personal"}}
        response = data["client"].post("/shop/cart/checkout", json=checkout_data, headers=headers)
        assert response.status_code == 200

        checkout_result = response.json()
        assert checkout_result["status"] == "success"
        assert len(checkout_result["checked_out"]) == 2

        # Verify cart is empty
        response = data["client"].get("/shop/cart", headers=headers)
        cart_data = response.json()
        assert len(cart_data["cart"]) == 0

        # Verify items were added to owned collections
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"username": data["test_user"]["username"]})
        assert len(user["avatars_owned"]) > 0
        assert len(user["banners_owned"]) > 0

    @pytest.mark.asyncio
    async def test_bundle_purchase_auto_population(self, setup_test_data):
        """Test bundle purchase with automatic content population."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"bundle_id": "emotion_tracker-avatars-dog-bundle", "payment_method": {"type": "personal"}}

        response = data["client"].post("/shop/bundles/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        response_data = response.json()
        assert response_data["status"] == "success"
        assert "bundle_contents" in response_data

        # Verify bundle contents were populated
        bundle_contents = response_data["bundle_contents"]
        assert "avatars" in bundle_contents
        assert len(bundle_contents["avatars"]) > 0

        # Verify avatars were added to user's collection
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"username": data["test_user"]["username"]})
        owned_avatars = user.get("avatars_owned", [])
        dog_avatars = [a for a in owned_avatars if "dog" in a.get("avatar_id", "")]
        assert len(dog_avatars) > 0

    @pytest.mark.asyncio
    async def test_concurrent_payments_race_condition(self, setup_test_data):
        """Test concurrent payments to detect race conditions."""
        data = setup_test_data
        import asyncio

        async def make_payment(attempt_id):
            """Make a payment attempt."""
            headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker/1.0.0"}

            purchase_data = {
                "theme_id": f"emotion_tracker-test-theme-{attempt_id}",
                "payment_method": {"type": "personal"},
            }

            # Create a unique theme ID for this test
            purchase_data["theme_id"] = "emotion_tracker-concurrent-test"

            response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
            return response.status_code, response.json() if response.status_code != 200 else None

        # Run multiple concurrent payments
        tasks = [make_payment(i) for i in range(5)]
        results = await asyncio.gather(*tasks)

        # Only one should succeed, others should fail
        success_count = sum(1 for status, _ in results if status == 200)
        assert success_count <= 1  # At most one success due to theme ownership check

        failure_count = sum(1 for status, _ in results if status != 200)
        assert failure_count >= 4  # At least 4 failures

    @pytest.mark.asyncio
    async def test_family_notification_on_spend(self, setup_test_data):
        """Test that family notifications are sent for family token spends."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['family_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-notification-test",
            "payment_method": {"type": "family", "family_id": data["test_family_id"]},
        }

        # Mock notification sending to verify it's called
        with patch.object(family_manager, "send_family_notification") as mock_notify:
            response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
            assert response.status_code == 200

            # Verify notification was sent
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert call_args[0][0] == data["test_family_id"]
            assert call_args[0][1] == "sbd_spend"
            notification_data = call_args[0][2]
            assert notification_data["amount"] == 250
            assert notification_data["spender_username"] == data["family_user"]["username"]

    @pytest.mark.asyncio
    async def test_transaction_logging(self, setup_test_data):
        """Test that transactions are properly logged."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-log-test", "payment_method": {"type": "personal"}}

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        # Check transaction log
        transactions_collection = db_manager.get_collection("transactions")
        transaction = await transactions_collection.find_one(
            {"user_id": data["test_user"]["username"], "transaction_type": "shop_purchase", "item_type": "theme"}
        )

        assert transaction is not None
        assert transaction["amount"] == 250
        assert transaction["item_id"] == "emotion_tracker-log-test"
        assert transaction["payment_type"] == "personal"

    @pytest.mark.asyncio
    async def test_family_notification_on_spend(self):
        """Test that family notifications are sent for family token spends."""
        headers = {"Authorization": f"Bearer {self.family_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {
            "theme_id": "emotion_tracker-notification-test",
            "payment_method": {"type": "family", "family_id": self.test_family_id},
        }

        # Mock notification sending to verify it's called
        with patch.object(family_manager, "send_family_notification") as mock_notify:
            response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
            assert response.status_code == 200

            # Verify notification was sent
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert call_args[0][0] == self.test_family_id
            assert call_args[0][1] == "sbd_spend"
            notification_data = call_args[0][2]
            assert notification_data["amount"] == 250
            assert notification_data["spender_username"] == self.family_user["username"]

    @pytest.mark.asyncio
    async def test_transaction_logging(self):
        """Test that transactions are properly logged."""
        headers = {"Authorization": f"Bearer {self.user_token}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-log-test", "payment_method": {"type": "personal"}}

        response = self.client.post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 200

        # Check transaction log
        transactions_collection = db_manager.get_collection("transactions")
        transaction = await transactions_collection.find_one(
            {"user_id": self.test_user["username"], "transaction_type": "shop_purchase", "item_type": "theme"}
        )

        assert transaction is not None
        assert transaction["amount"] == 250
        assert transaction["item_id"] == "emotion_tracker-log-test"
        assert transaction["payment_type"] == "personal"

    @pytest.mark.asyncio
    async def test_authentication_failures(self, setup_test_data):
        """Test various authentication failure scenarios."""
        data = setup_test_data
        # Test missing token
        response = data["client"].get("/shop/payment-options")
        assert response.status_code == 401

        # Test invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        response = data["client"].get("/shop/payment-options", headers=headers)
        assert response.status_code == 401

        # Test expired token (would need token generation with past expiry)
        # This is complex to test without token manipulation

    @pytest.mark.asyncio
    async def test_invalid_payment_method_types(self, setup_test_data):
        """Test invalid payment method types."""
        data = setup_test_data
        headers = {"Authorization": f"Bearer {data['user_token']}", "user-agent": "emotion_tracker/1.0.0"}

        purchase_data = {"theme_id": "emotion_tracker-invalid-payment", "payment_method": {"type": "invalid_type"}}

        response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
        assert response.status_code == 400

        response_data = response.json()
        assert response_data["status"] == "error"

    @pytest.mark.asyncio
    async def test_family_not_member(self, setup_test_data):
        """Test payment attempt by non-family member."""
        data = setup_test_data
        # Create another user not in the family
        other_user = {
            "username": "other_user_error_proof",
            "email": "other_error_proof@example.com",
            "password": "testpass123",
        }

        users_collection = db_manager.get_collection("users")
        other_user_doc = {
            **other_user,
            "sbd_tokens": 1000,
            "hashed_password": bcrypt.hashpw(other_user["password"].encode(), bcrypt.gensalt()).decode(),
            "created_at": datetime.now(timezone.utc),
        }

        await users_collection.insert_one(other_user_doc)
        other_token = await create_access_token({"sub": other_user["username"]})

        try:
            headers = {"Authorization": f"Bearer {other_token}", "user-agent": "emotion_tracker/1.0.0"}

            purchase_data = {
                "theme_id": "emotion_tracker-not-member",
                "payment_method": {"type": "family", "family_id": data["test_family_id"]},
            }

            response = data["client"].post("/shop/themes/buy", json=purchase_data, headers=headers)
            assert response.status_code == 403

            response_data = response.json()
            assert response_data["status"] == "error"
            assert "FAMILY_SPENDING_DENIED" in response_data["detail"]["error"]

        finally:
            # Cleanup
            await users_collection.delete_one({"username": other_user["username"]})
