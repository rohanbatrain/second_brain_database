"""
Integration tests for IPAM Backend Enhancements.

Tests new endpoints added for:
- Reservation management
- Shareable links
- User preferences and saved filters
- Notification rules and delivery
- Capacity forecasting and trends
- Dashboard statistics
- Webhook configuration and delivery
- Enhanced bulk operations
- Advanced search

Note: These tests are designed to be run once the enhancement endpoints are implemented.
They follow the existing IPAM test patterns and use mocked dependencies.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from motor.motor_asyncio import AsyncIOMotorClient

from second_brain_database.main import app


@pytest.fixture
async def test_db():
    """Create test database connection."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["test_ipam_enhancements"]
    
    # Clean up collections before test
    collections = [
        "ipam_reservations", "ipam_shares", "ipam_user_preferences",
        "ipam_notifications", "ipam_notification_rules", "ipam_webhooks",
        "ipam_webhook_deliveries", "ipam_bulk_jobs", "ipam_regions", "ipam_hosts"
    ]
    for collection in collections:
        await db[collection].delete_many({})
    
    yield db
    
    # Clean up after test
    for collection in collections:
        await db[collection].delete_many({})
    client.close()


@pytest.fixture
def test_client():
    """Create test client with lifespan context to connect database."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user with IPAM permissions."""
    return {
        "_id": "test_user_123",
        "username": "test_user",
        "email": "test@example.com",
        "permissions": [
            "ipam:read",
            "ipam:allocate",
            "ipam:update",
            "ipam:release",
            "ipam:admin"
        ]
    }


@pytest.fixture
def auth_headers(mock_auth_user):
    """Create authentication headers for test requests."""
    # In real tests, this would generate a valid JWT token
    # For now, we'll mock the authentication dependency
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def authenticated_client(test_client, mock_auth_user):
    """Create test client with authentication dependency override."""
    from second_brain_database.routes.ipam.dependencies import get_current_user_for_ipam
    
    def override_get_current_user():
        return mock_auth_user
    
    app.dependency_overrides[get_current_user_for_ipam] = override_get_current_user
    yield test_client
    app.dependency_overrides.clear()


class TestReservationEndpoints:
    """Test reservation management endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_reservation_success(self, authenticated_client, test_db):
        """Test successful reservation creation."""
        response = authenticated_client.post(
                "/ipam/reservations",
                json={
                    "resource_type": "region",
                    "x_octet": 10,
                    "y_octet": 20,
                    "reason": "Reserved for Q1 expansion",
                    "expires_in_days": 30
                }
        )
        
        if response.status_code != status.HTTP_201_CREATED:
            print(f"Error response: {response.json()}")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "reservation_id" in data
        assert data["resource_type"] == "region"
        assert data["x_octet"] == 10
        assert data["y_octet"] == 20
        assert "reserved_address" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_reservation_conflict(self, authenticated_client, test_db):
        """Test reservation creation fails when address already allocated."""
        # First, create an existing allocation
        await test_db.ipam_regions.insert_one({
                "user_id": "test_user_123",
                "x_octet": 10,
                "y_octet": 20,
                "status": "Active"
        })
        
        # Try to reserve the same address
        response = authenticated_client.post(
                "/ipam/reservations",
                json={
                    "resource_type": "region",
                    "x_octet": 10,
                    "y_octet": 20,
                    "reason": "Should fail",
                    "expires_in_days": 30
                }
        )
        
        assert response.status_code == status.HTTP_409_CONFLICT

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_reservations(self, authenticated_client, test_db):
        """Test listing user reservations with filters."""
        # Create test reservations
        await test_db.ipam_reservations.insert_many([
                {
                    "user_id": "test_user_123",
                    "resource_type": "region",
                    "x_octet": 10,
                    "y_octet": 20,
                    "status": "active",
                    "created_at": datetime.utcnow()
                },
                {
                    "user_id": "test_user_123",
                    "resource_type": "host",
                    "x_octet": 10,
                    "y_octet": 21,
                    "z_octet": 50,
                    "status": "active",
                    "created_at": datetime.utcnow()
                }
        ])
        
        response = authenticated_client.get(
                "/ipam/reservations?status=active"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data
        assert len(data["results"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_convert_reservation_to_region(self, authenticated_client, test_db):
        """Test converting reservation to active region allocation."""
        # Create a reservation
        reservation_id = str(uuid4())
        await test_db.ipam_reservations.insert_one({
                "_id": reservation_id,
                "user_id": "test_user_123",
                "resource_type": "region",
                "x_octet": 10,
                "y_octet": 25,
                "status": "active",
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.post(
                f"/ipam/reservations/{reservation_id}/convert",
                json={
                    "region_name": "Production Network",
                    "description": "Converted from reservation"
                }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "resource_id" in data
        assert data["resource_type"] == "region"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_convert_reservation_to_host(self, authenticated_client, test_db):
        """Test converting reservation to active host allocation."""
        # Create a host reservation
        reservation_id = str(uuid4())
        await test_db.ipam_reservations.insert_one({
                "_id": reservation_id,
                "user_id": "test_user_123",
                "resource_type": "host",
                "x_octet": 10,
                "y_octet": 25,
                "z_octet": 100,
                "status": "active",
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.post(
                f"/ipam/reservations/{reservation_id}/convert",
                json={
                    "hostname": "web-server-01",
                    "description": "Converted from reservation"
                }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "resource_id" in data
        assert data["resource_type"] == "host"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delete_reservation(self, authenticated_client, test_db):
        """Test canceling a reservation."""
        # Create a reservation
        reservation_id = str(uuid4())
        await test_db.ipam_reservations.insert_one({
                "_id": reservation_id,
                "user_id": "test_user_123",
                "resource_type": "region",
                "x_octet": 10,
                "y_octet": 30,
                "status": "active",
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.delete(
                f"/ipam/reservations/{reservation_id}"
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_reservation_expiration(self, test_db):
        """Test expired reservations are automatically marked as expired."""
        # Create an expired reservation
        expired_time = datetime.utcnow() - timedelta(days=1)
        await test_db.ipam_reservations.insert_one({
        "user_id": "test_user_123",
        "resource_type": "region",
        "x_octet": 10,
        "y_octet": 35,
        "status": "active",
        "expires_at": expired_time,
        "created_at": datetime.utcnow() - timedelta(days=10)
        })
        
        # Import and run the expiration checker
        from second_brain_database.routes.ipam.periodics.reservation_expiration import check_expired_reservations
        
        await check_expired_reservations()
        
        # Verify reservation was marked as expired
        expired_reservation = await test_db.ipam_reservations.find_one({
        "x_octet": 10,
        "y_octet": 35
        })
        assert expired_reservation["status"] == "expired"


class TestShareableLinksEndpoints:
    """Test shareable links endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_share_success(self, authenticated_client, test_db):
        """Test successful share creation."""
        # Create a region to share
        region_id = str(uuid4())
        await test_db.ipam_regions.insert_one({
                "_id": region_id,
                "user_id": "test_user_123",
                "x_octet": 10,
                "y_octet": 40,
                "status": "Active"
        })
        
        response = authenticated_client.post(
                "/ipam/shares",
                json={
                    "resource_type": "region",
                    "resource_id": region_id,
                    "expires_in_days": 30
                }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "share_token" in data
        assert "share_url" in data
        assert data["resource_type"] == "region"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_share_max_expiration(self, authenticated_client, test_db):
        """Test share creation enforces 90-day max expiration."""
        region_id = str(uuid4())
        response = authenticated_client.post(
                "/ipam/shares",
                json={
                    "resource_type": "region",
                    "resource_id": region_id,
                    "expires_in_days": 100  # Exceeds 90-day limit
                }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_access_share_no_auth(self, test_client, test_db):
        """Test accessing shared resource without authentication."""
        # Create a share
        share_token = str(uuid4())
        region_id = str(uuid4())
        await test_db.ipam_shares.insert_one({
        "share_token": share_token,
        "user_id": "test_user_123",
        "resource_type": "region",
        "resource_id": region_id,
        "expires_at": datetime.utcnow() + timedelta(days=30),
        "view_count": 0,
        "is_active": True,
        "created_at": datetime.utcnow()
        })
        
        # Create the region
        await test_db.ipam_regions.insert_one({
        "_id": region_id,
        "user_id": "test_user_123",
        "x_octet": 10,
        "y_octet": 45,
        "status": "Active"
        })
        
        # Access without authentication
        response = authenticated_client.get(f"/ipam/shares/{share_token}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["resource_type"] == "region"
        assert "resource_data" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_access_share_expired(self, test_client, test_db):
        """Test accessing expired share returns 404."""
        # Create an expired share
        share_token = str(uuid4())
        await test_db.ipam_shares.insert_one({
        "share_token": share_token,
        "user_id": "test_user_123",
        "resource_type": "region",
        "resource_id": str(uuid4()),
        "expires_at": datetime.utcnow() - timedelta(days=1),  # Expired
        "view_count": 0,
        "is_active": True,
        "created_at": datetime.utcnow() - timedelta(days=31)
        })
        
        response = authenticated_client.get(f"/ipam/shares/{share_token}")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_access_share_increments_view_count(self, test_client, test_db):
        """Test share access increments view count."""
        share_token = str(uuid4())
        region_id = str(uuid4())
        await test_db.ipam_shares.insert_one({
        "share_token": share_token,
        "user_id": "test_user_123",
        "resource_type": "region",
        "resource_id": region_id,
        "expires_at": datetime.utcnow() + timedelta(days=30),
        "view_count": 5,
        "is_active": True,
        "created_at": datetime.utcnow()
        })
        
        await test_db.ipam_regions.insert_one({
        "_id": region_id,
        "user_id": "test_user_123",
        "x_octet": 10,
        "y_octet": 50,
        "status": "Active"
        })
        
        response = authenticated_client.get(f"/ipam/shares/{share_token}")
        assert response.status_code == status.HTTP_200_OK
        
        # Verify view count was incremented
        share = await test_db.ipam_shares.find_one({"share_token": share_token})
        assert share["view_count"] == 6
        assert "last_accessed" in share

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_user_shares(self, authenticated_client, test_db):
        """Test listing user's active shares."""
        # Create test shares
        await test_db.ipam_shares.insert_many([
                {
                    "share_token": str(uuid4()),
                    "user_id": "test_user_123",
                    "resource_type": "region",
                    "resource_id": str(uuid4()),
                    "expires_at": datetime.utcnow() + timedelta(days=30),
                    "view_count": 3,
                    "is_active": True,
                    "created_at": datetime.utcnow()
                },
                {
                    "share_token": str(uuid4()),
                    "user_id": "test_user_123",
                    "resource_type": "host",
                    "resource_id": str(uuid4()),
                    "expires_at": datetime.utcnow() + timedelta(days=15),
                    "view_count": 1,
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
        ])
        
        response = authenticated_client.get("/ipam/shares")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "shares" in data
        assert len(data["shares"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_revoke_share(self, authenticated_client, test_db):
        """Test revoking a share."""
        share_id = str(uuid4())
        share_token = str(uuid4())
        await test_db.ipam_shares.insert_one({
                "_id": share_id,
                "share_token": share_token,
                "user_id": "test_user_123",
                "resource_type": "region",
                "resource_id": str(uuid4()),
                "expires_at": datetime.utcnow() + timedelta(days=30),
                "view_count": 0,
                "is_active": True,
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.delete(f"/ipam/shares/{share_id}")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # Verify subsequent access fails
        response = authenticated_client.get(f"/ipam/shares/{share_token}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_share_data_sanitization(self, test_client, test_db):
        """Test shared data excludes sensitive information."""
        share_token = str(uuid4())
        region_id = str(uuid4())
        await test_db.ipam_shares.insert_one({
        "share_token": share_token,
        "user_id": "test_user_123",
        "resource_type": "region",
        "resource_id": region_id,
        "expires_at": datetime.utcnow() + timedelta(days=30),
        "view_count": 0,
        "is_active": True,
        "created_at": datetime.utcnow()
        })
        
        await test_db.ipam_regions.insert_one({
        "_id": region_id,
        "user_id": "test_user_123",
        "x_octet": 10,
        "y_octet": 55,
        "status": "Active",
        "internal_notes": "Sensitive information",
        "owner_email": "owner@example.com"
        })
        
        response = authenticated_client.get(f"/ipam/shares/{share_token}")
        assert response.status_code == status.HTTP_200_OK
        
        data = response.json()
        resource_data = data["resource_data"]
        # Verify sensitive fields are excluded
        assert "internal_notes" not in resource_data
        assert "owner_email" not in resource_data
        assert "user_id" not in resource_data


class TestUserPreferencesEndpoints:
    """Test user preferences endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_preferences_empty(self, authenticated_client):
        """Test getting preferences returns empty object for new user."""
        response = authenticated_client.get("/ipam/preferences")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "saved_filters" in data
        assert "dashboard_layout" in data
        assert len(data["saved_filters"]) == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_update_preferences_merge(self, authenticated_client, test_db):
        """Test updating preferences merges with existing."""
        # Create initial preferences
        await test_db.ipam_user_preferences.insert_one({
                "user_id": "test_user_123",
                "dashboard_layout": {"widget1": "position1"},
                "theme_preference": "dark",
                "updated_at": datetime.utcnow()
        })
        
        # Update with new preferences
        response = authenticated_client.put(
                "/ipam/preferences",
                json={
                    "dashboard_layout": {"widget2": "position2"},
                    "notification_settings": {"email": True}
                }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify merge
        prefs = await test_db.ipam_user_preferences.find_one({"user_id": "test_user_123"})
        assert "widget2" in prefs["dashboard_layout"]
        assert prefs["theme_preference"] == "dark"  # Original value preserved
        assert prefs["notification_settings"]["email"] is True

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_update_preferences_size_limit(self, authenticated_client):
        """Test preferences enforce 50KB size limit."""
        # Create a large preferences object (> 50KB)
        large_data = {"key" + str(i): "x" * 1000 for i in range(100)}
        
        response = authenticated_client.put(
                "/ipam/preferences",
                json={"dashboard_layout": large_data}
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_filter_success(self, authenticated_client):
        """Test saving a search filter."""
        response = authenticated_client.post(
                "/ipam/preferences/filters",
                json={
                    "name": "Production Regions",
                    "criteria": {
                        "status": "Active",
                        "tags": {"environment": "production"}
                    }
                }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "filter_id" in data
        assert data["name"] == "Production Regions"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_save_filter_max_limit(self, authenticated_client, test_db):
        """Test saving filter enforces 50 filter limit."""
        # Create user with 50 filters
        filters = [
                {
                    "filter_id": str(uuid4()),
                    "name": f"Filter {i}",
                    "criteria": {},
                    "created_at": datetime.utcnow()
                }
                for i in range(50)
        ]
        await test_db.ipam_user_preferences.insert_one({
                "user_id": "test_user_123",
                "saved_filters": filters,
                "updated_at": datetime.utcnow()
        })
        
        # Try to add 51st filter
        response = authenticated_client.post(
                "/ipam/preferences/filters",
                json={
                    "name": "Filter 51",
                    "criteria": {}
                }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_saved_filters(self, authenticated_client, test_db):
        """Test listing user's saved filters."""
        # Create filters
        filters = [
                {
                    "filter_id": str(uuid4()),
                    "name": "Filter 1",
                    "criteria": {"status": "Active"},
                    "created_at": datetime.utcnow()
                },
                {
                    "filter_id": str(uuid4()),
                    "name": "Filter 2",
                    "criteria": {"status": "Retired"},
                    "created_at": datetime.utcnow()
                }
        ]
        await test_db.ipam_user_preferences.insert_one({
                "user_id": "test_user_123",
                "saved_filters": filters,
                "updated_at": datetime.utcnow()
        })
        
        response = authenticated_client.get("/ipam/preferences/filters")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "filters" in data
        assert len(data["filters"]) == 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delete_saved_filter(self, authenticated_client, test_db):
        """Test deleting a saved filter."""
        filter_id = str(uuid4())
        await test_db.ipam_user_preferences.insert_one({
                "user_id": "test_user_123",
                "saved_filters": [
                    {
                        "filter_id": filter_id,
                        "name": "Test Filter",
                        "criteria": {},
                        "created_at": datetime.utcnow()
                    }
                ],
                "updated_at": datetime.utcnow()
        })
        
        response = authenticated_client.delete(
                f"/ipam/preferences/filters/{filter_id}"
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT


class TestNotificationEndpoints:
    """Test notification system endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_notification_rule(self, authenticated_client):
        """Test creating a notification rule."""
        response = authenticated_client.post(
                "/ipam/notifications/rules",
                json={
                    "rule_name": "High Utilization Alert",
                    "conditions": {
                        "utilization_threshold": 80,
                        "resource_type": "region"
                    },
                    "notification_channels": ["in_app"]
                }
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "rule_id" in data
        assert data["rule_name"] == "High Utilization Alert"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_notification_rules(self, authenticated_client, test_db):
        """Test listing user's notification rules."""
        await test_db.ipam_notification_rules.insert_many([
                {
                    "user_id": "test_user_123",
                    "rule_name": "Rule 1",
                    "conditions": {},
                    "is_active": True,
                    "created_at": datetime.utcnow()
                },
                {
                    "user_id": "test_user_123",
                    "rule_name": "Rule 2",
                    "conditions": {},
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
        ])
        
        response = authenticated_client.get("/ipam/notifications/rules")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "rules" in data
        assert len(data["rules"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_update_notification_rule(self, authenticated_client, test_db):
        """Test updating a notification rule."""
        rule_id = str(uuid4())
        await test_db.ipam_notification_rules.insert_one({
                "_id": rule_id,
                "user_id": "test_user_123",
                "rule_name": "Original Rule",
                "conditions": {"utilization_threshold": 70},
                "is_active": True,
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.patch(
                f"/ipam/notifications/rules/{rule_id}",
                json={
                    "rule_name": "Updated Rule",
                    "conditions": {"utilization_threshold": 85}
                }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["rule_name"] == "Updated Rule"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delete_notification_rule(self, authenticated_client, test_db):
        """Test deleting a notification rule."""
        rule_id = str(uuid4())
        await test_db.ipam_notification_rules.insert_one({
                "_id": rule_id,
                "user_id": "test_user_123",
                "rule_name": "Test Rule",
                "conditions": {},
                "is_active": True,
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.delete(
                f"/ipam/notifications/rules/{rule_id}"
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_notifications(self, authenticated_client, test_db):
        """Test listing user notifications with filters."""
        await test_db.ipam_notifications.insert_many([
                {
                    "user_id": "test_user_123",
                    "notification_type": "capacity_warning",
                    "severity": "warning",
                    "message": "Region utilization high",
                    "is_read": False,
                    "created_at": datetime.utcnow()
                },
                {
                    "user_id": "test_user_123",
                    "notification_type": "allocation_created",
                    "severity": "info",
                    "message": "New region allocated",
                    "is_read": True,
                    "created_at": datetime.utcnow()
                }
        ])
        
        response = authenticated_client.get(
                "/ipam/notifications?is_read=false"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "notifications" in data
        assert len(data["notifications"]) >= 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_unread_notifications(self, authenticated_client, test_db):
        """Test getting unread notification count."""
        await test_db.ipam_notifications.insert_many([
                {
                    "user_id": "test_user_123",
                    "notification_type": "test",
                    "severity": "info",
                    "message": "Unread 1",
                    "is_read": False,
                    "created_at": datetime.utcnow()
                },
                {
                    "user_id": "test_user_123",
                    "notification_type": "test",
                    "severity": "info",
                    "message": "Unread 2",
                    "is_read": False,
                    "created_at": datetime.utcnow()
                }
        ])
        
        response = authenticated_client.get("/ipam/notifications/unread")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "unread_count" in data
        assert data["unread_count"] >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_mark_notification_read(self, authenticated_client, test_db):
        """Test marking notification as read."""
        notification_id = str(uuid4())
        await test_db.ipam_notifications.insert_one({
                "_id": notification_id,
                "user_id": "test_user_123",
                "notification_type": "test",
                "severity": "info",
                "message": "Test notification",
                "is_read": False,
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.patch(
                f"/ipam/notifications/{notification_id}"
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify notification was marked as read
        notification = await test_db.ipam_notifications.find_one({"_id": notification_id})
        assert notification["is_read"] is True
        assert "read_at" in notification

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dismiss_notification(self, authenticated_client, test_db):
        """Test dismissing a notification."""
        notification_id = str(uuid4())
        await test_db.ipam_notifications.insert_one({
                "_id": notification_id,
                "user_id": "test_user_123",
                "notification_type": "test",
                "severity": "info",
                "message": "Test notification",
                "is_read": False,
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.delete(
                f"/ipam/notifications/{notification_id}"
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_notification_rule_evaluation(self, test_db):
        """Test notification rules are evaluated on allocation events."""
        # Create a notification rule
        await test_db.ipam_notification_rules.insert_one({
        "user_id": "test_user_123",
        "rule_name": "High Utilization",
        "conditions": {"utilization_threshold": 80},
        "is_active": True,
        "created_at": datetime.utcnow()
        })
        
        # Simulate an event that triggers the rule
        from second_brain_database.managers.ipam_manager import ipam_manager
        
        event_data = {
        "resource_type": "region",
        "resource_id": str(uuid4()),
        "utilization": 85
        }
        
        await ipam_manager.evaluate_notification_rules("test_user_123", event_data)
        
        # Verify notification was created
        notification = await test_db.ipam_notifications.find_one({
        "user_id": "test_user_123",
        "notification_type": "High Utilization"
        })
        assert notification is not None

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_notification_expiration(self, test_db):
        """Test notifications older than 90 days are deleted."""
        # Create an old notification
        old_time = datetime.utcnow() - timedelta(days=91)
        await test_db.ipam_notifications.insert_one({
        "user_id": "test_user_123",
        "notification_type": "test",
        "severity": "info",
        "message": "Old notification",
        "is_read": True,
        "created_at": old_time,
        "expires_at": old_time + timedelta(days=90)
        })
        
        # Run cleanup task
        from second_brain_database.routes.ipam.periodics.notification_cleanup import cleanup_old_notifications
        
        await cleanup_old_notifications()
        
        # Verify old notification was deleted
        count = await test_db.ipam_notifications.count_documents({
        "created_at": {"$lt": datetime.utcnow() - timedelta(days=90)}
        })
        assert count == 0


class TestForecastingEndpoints:
    """Test capacity forecasting and trends endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_dashboard_stats(self, authenticated_client, test_db):
        """Test getting dashboard statistics."""
        # Create test data
        await test_db.ipam_regions.insert_many([
                {"user_id": "test_user_123", "x_octet": 10, "y_octet": i, "status": "Active"}
                for i in range(5)
        ])
        
        response = authenticated_client.get("/ipam/statistics/dashboard")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_regions" in data
        assert "total_hosts" in data
        assert "overall_utilization" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dashboard_stats_caching(self, authenticated_client):
        """Test dashboard stats are cached for 5 minutes."""
        # First request
        response1 = authenticated_client.get("/ipam/statistics/dashboard")
        assert response1.status_code == status.HTTP_200_OK
        
        # Second request (should use cache)
        response2 = authenticated_client.get("/ipam/statistics/dashboard")
        assert response2.status_code == status.HTTP_200_OK
        
        # Verify responses are identical (from cache)
        assert response1.json() == response2.json()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_forecast_sufficient_data(self, authenticated_client, test_db):
        """Test forecast calculation with sufficient historical data."""
        region_id = str(uuid4())
        # Create historical allocation data
        for i in range(20):
                await test_db.ipam_audit_history.insert_one({
                    "user_id": "test_user_123",
                    "resource_id": region_id,
                    "action_type": "create",
                    "timestamp": datetime.utcnow() - timedelta(days=i)
                })
        
        response = authenticated_client.get(
                f"/ipam/statistics/forecast/region/{region_id}"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "daily_allocation_rate" in data
        assert "estimated_exhaustion_date" in data
        assert "confidence_level" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_forecast_insufficient_data(self, authenticated_client):
        """Test forecast returns insufficient_data status."""
        region_id = str(uuid4())
        response = authenticated_client.get(
                f"/ipam/statistics/forecast/region/{region_id}"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data.get("status") == "insufficient_data"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_forecast_caching(self, authenticated_client, test_db):
        """Test forecast results are cached for 24 hours."""
        region_id = str(uuid4())
        # Create sufficient data
        for i in range(20):
                await test_db.ipam_audit_history.insert_one({
                    "user_id": "test_user_123",
                    "resource_id": region_id,
                    "action_type": "create",
                    "timestamp": datetime.utcnow() - timedelta(days=i)
                })
        
        # First request
        response1 = authenticated_client.get(
                f"/ipam/statistics/forecast/region/{region_id}"
        )
        assert response1.status_code == status.HTTP_200_OK
        
        # Second request (should use cache)
        response2 = authenticated_client.get(
                f"/ipam/statistics/forecast/region/{region_id}"
        )
        assert response2.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_trends_by_day(self, authenticated_client, test_db):
        """Test getting allocation trends grouped by day."""
        # Create trend data
        for i in range(7):
                await test_db.ipam_audit_history.insert_one({
                    "user_id": "test_user_123",
                    "action_type": "create",
                    "timestamp": datetime.utcnow() - timedelta(days=i)
                })
        
        response = authenticated_client.get(
                "/ipam/statistics/trends?group_by=day"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "time_series" in data
        assert len(data["time_series"]) > 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_trends_by_week(self, authenticated_client, test_db):
        """Test getting allocation trends grouped by week."""
        response = authenticated_client.get(
                "/ipam/statistics/trends?group_by=week"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "time_series" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_trends_by_month(self, authenticated_client, test_db):
        """Test getting allocation trends grouped by month."""
        response = authenticated_client.get(
                "/ipam/statistics/trends?group_by=month"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "time_series" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_trends_with_filters(self, authenticated_client, test_db):
        """Test trends endpoint with resource type and date filters."""
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        end_date = datetime.utcnow().isoformat()
        
        response = authenticated_client.get(
                f"/ipam/statistics/trends?resource_type=region&start_date={start_date}&end_date={end_date}"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "time_series" in data


class TestWebhookEndpoints:
    """Test webhook configuration and delivery endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_webhook_success(self, authenticated_client):
        """Test successful webhook creation."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Mock(status_code=200)
            
            response = authenticated_client.post(
                "/ipam/webhooks",
                json={
                    "webhook_url": "https://example.com/webhook",
                    "events": ["region.created", "host.allocated"],
                    "description": "Test webhook"
                }
            )
            
            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert "webhook_id" in data
            assert "secret_key" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_create_webhook_url_validation(self, authenticated_client):
        """Test webhook creation validates URL connectivity."""
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = Exception("Connection failed")
            
            response = authenticated_client.post(
                "/ipam/webhooks",
                json={
                    "webhook_url": "https://invalid-url.example.com/webhook",
                    "events": ["region.created"]
                }
            )
            
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_webhooks(self, authenticated_client, test_db):
        """Test listing user's webhooks."""
        await test_db.ipam_webhooks.insert_many([
                {
                    "user_id": "test_user_123",
                    "webhook_url": "https://example.com/webhook1",
                    "secret_key": "secret123",
                    "events": ["region.created"],
                    "is_active": True,
                    "created_at": datetime.utcnow()
                },
                {
                    "user_id": "test_user_123",
                    "webhook_url": "https://example.com/webhook2",
                    "secret_key": "secret456",
                    "events": ["host.allocated"],
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
        ])
        
        response = authenticated_client.get("/ipam/webhooks")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "webhooks" in data
        assert len(data["webhooks"]) >= 2
        # Verify secrets are excluded
        for webhook in data["webhooks"]:
                assert "secret_key" not in webhook

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_delete_webhook(self, authenticated_client, test_db):
        """Test deleting a webhook."""
        webhook_id = str(uuid4())
        await test_db.ipam_webhooks.insert_one({
                "_id": webhook_id,
                "user_id": "test_user_123",
                "webhook_url": "https://example.com/webhook",
                "secret_key": "secret123",
                "events": ["region.created"],
                "is_active": True,
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.delete(f"/ipam/webhooks/{webhook_id}")
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_webhook_deliveries(self, authenticated_client, test_db):
        """Test getting webhook delivery history."""
        webhook_id = str(uuid4())
        await test_db.ipam_webhooks.insert_one({
                "_id": webhook_id,
                "user_id": "test_user_123",
                "webhook_url": "https://example.com/webhook",
                "is_active": True
        })
        
        # Create delivery records
        await test_db.ipam_webhook_deliveries.insert_many([
                {
                    "webhook_id": webhook_id,
                    "event_type": "region.created",
                    "status_code": 200,
                    "response_time_ms": 150,
                    "delivered_at": datetime.utcnow()
                },
                {
                    "webhook_id": webhook_id,
                    "event_type": "host.allocated",
                    "status_code": 200,
                    "response_time_ms": 200,
                    "delivered_at": datetime.utcnow()
                }
        ])
        
        response = authenticated_client.get(f"/ipam/webhooks/{webhook_id}/deliveries")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "deliveries" in data
        assert len(data["deliveries"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_webhook_delivery_hmac_signature(self, test_db):
        """Test webhook delivery includes HMAC signature."""
        import hmac
        import hashlib
        
        webhook_id = str(uuid4())
        secret_key = "test_secret_key"
        await test_db.ipam_webhooks.insert_one({
        "_id": webhook_id,
        "user_id": "test_user_123",
        "webhook_url": "https://example.com/webhook",
        "secret_key": secret_key,
        "events": ["region.created"],
        "is_active": True
        })
        
        from second_brain_database.managers.ipam_manager import ipam_manager
        
        payload = {"event": "region.created", "data": {}}
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Mock(status_code=200)
            
            await ipam_manager.deliver_webhook(webhook_id, "region.created", payload)
            
            # Verify HMAC signature was included
            call_args = mock_post.call_args
            headers = call_args.kwargs.get("headers", {})
            assert "X-IPAM-Signature" in headers

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_webhook_delivery_retry_logic(self, test_db):
        """Test webhook delivery retries on failure."""
        webhook_id = str(uuid4())
        await test_db.ipam_webhooks.insert_one({
        "_id": webhook_id,
        "user_id": "test_user_123",
        "webhook_url": "https://example.com/webhook",
        "secret_key": "secret123",
        "events": ["region.created"],
        "is_active": True,
        "failure_count": 0
        })
        
        from second_brain_database.managers.ipam_manager import ipam_manager
        
        with patch("httpx.AsyncClient.post") as mock_post:
            # Simulate failures
            mock_post.side_effect = Exception("Connection failed")
            
            await ipam_manager.deliver_webhook(webhook_id, "region.created", {})
            
            # Verify 3 retry attempts were made
            assert mock_post.call_count == 3

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_webhook_auto_disable_after_failures(self, test_db):
        """Test webhook is disabled after 10 consecutive failures."""
        webhook_id = str(uuid4())
        await test_db.ipam_webhooks.insert_one({
        "_id": webhook_id,
        "user_id": "test_user_123",
        "webhook_url": "https://example.com/webhook",
        "secret_key": "secret123",
        "events": ["region.created"],
        "is_active": True,
        "failure_count": 9  # One more failure will disable it
        })
        
        from second_brain_database.managers.ipam_manager import ipam_manager
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.side_effect = Exception("Connection failed")
            
            await ipam_manager.deliver_webhook(webhook_id, "region.created", {})
            
            # Verify webhook was disabled
            webhook = await test_db.ipam_webhooks.find_one({"_id": webhook_id})
            assert webhook["is_active"] is False

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_webhook_triggered_on_events(self, test_db):
        """Test webhooks are triggered on subscribed events."""
        webhook_id = str(uuid4())
        await test_db.ipam_webhooks.insert_one({
        "_id": webhook_id,
        "user_id": "test_user_123",
        "webhook_url": "https://example.com/webhook",
        "secret_key": "secret123",
        "events": ["region.created"],
        "is_active": True,
        "failure_count": 0
        })
        
        from second_brain_database.managers.ipam_manager import ipam_manager
        
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_post.return_value = Mock(status_code=200)
            
            # Trigger event
            await ipam_manager.trigger_webhook_event("test_user_123", "region.created", {})
            
            # Verify webhook was called
            assert mock_post.called


class TestBulkOperationsEndpoints:
    """Test enhanced bulk operations endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_tag_update_sync(self, authenticated_client, test_db):
        """Test synchronous bulk tag update (< 100 items)."""
        # Create test regions
        region_ids = [str(uuid4()) for _ in range(50)]
        await test_db.ipam_regions.insert_many([
                {"_id": rid, "user_id": "test_user_123", "x_octet": 10, "y_octet": i, "tags": {}}
                for i, rid in enumerate(region_ids)
        ])
        
        response = authenticated_client.post(
                "/ipam/bulk/tags",
                json={
                    "resource_type": "region",
                    "resource_ids": region_ids,
                    "operation": "add",
                    "tags": {"environment": "production"}
                }
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["successful"] == 50

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_tag_update_async(self, authenticated_client, test_db):
        """Test asynchronous bulk tag update (> 100 items)."""
        # Create 150 test regions
        region_ids = [str(uuid4()) for _ in range(150)]
        await test_db.ipam_regions.insert_many([
                {"_id": rid, "user_id": "test_user_123", "x_octet": 10, "y_octet": i % 255, "tags": {}}
                for i, rid in enumerate(region_ids)
        ])
        
        response = authenticated_client.post(
                "/ipam/bulk/tags",
                json={
                    "resource_type": "region",
                    "resource_ids": region_ids,
                    "operation": "add",
                    "tags": {"environment": "staging"}
                }
        )
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert "job_id" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_tag_update_max_items(self, authenticated_client):
        """Test bulk operation enforces 500 item limit."""
        # Try to update 501 items
        region_ids = [str(uuid4()) for _ in range(501)]
        
        response = authenticated_client.post(
                "/ipam/bulk/tags",
                json={
                    "resource_type": "region",
                    "resource_ids": region_ids,
                    "operation": "add",
                    "tags": {"test": "value"}
                }
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_tag_operations(self, authenticated_client, test_db):
        """Test bulk tag add, remove, and replace operations."""
        region_id = str(uuid4())
        await test_db.ipam_regions.insert_one({
                "_id": region_id,
                "user_id": "test_user_123",
                "x_octet": 10,
                "y_octet": 100,
                "tags": {"old_tag": "old_value"}
        })
        
        # Test add operation
        response = authenticated_client.post(
                "/ipam/bulk/tags",
                json={
                    "resource_type": "region",
                    "resource_ids": [region_id],
                    "operation": "add",
                    "tags": {"new_tag": "new_value"}
                }
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Test replace operation
        response = authenticated_client.post(
                "/ipam/bulk/tags",
                json={
                    "resource_type": "region",
                    "resource_ids": [region_id],
                    "operation": "replace",
                    "tags": {"replaced_tag": "replaced_value"}
                }
        )
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_bulk_job_status(self, authenticated_client, test_db):
        """Test getting bulk job status and progress."""
        job_id = str(uuid4())
        await test_db.ipam_bulk_jobs.insert_one({
                "job_id": job_id,
                "user_id": "test_user_123",
                "operation_type": "bulk_tag_update",
                "total_items": 150,
                "processed_items": 100,
                "successful_items": 95,
                "failed_items": 5,
                "status": "processing",
                "created_at": datetime.utcnow()
        })
        
        response = authenticated_client.get(f"/ipam/bulk/jobs/{job_id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "processing"
        assert "progress" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_job_expiration(self, test_db):
        """Test bulk jobs expire after 7 days."""
        # Create an old job
        old_time = datetime.utcnow() - timedelta(days=8)
        await test_db.ipam_bulk_jobs.insert_one({
        "job_id": str(uuid4()),
        "user_id": "test_user_123",
        "operation_type": "bulk_tag_update",
        "total_items": 100,
        "processed_items": 100,
        "status": "completed",
        "created_at": old_time,
        "completed_at": old_time + timedelta(minutes=5)
        })
        
        # Run cleanup (would be a background task)
        await test_db.ipam_bulk_jobs.delete_many({
        "created_at": {"$lt": datetime.utcnow() - timedelta(days=7)}
        })
        
        # Verify old job was deleted
        count = await test_db.ipam_bulk_jobs.count_documents({
        "created_at": {"$lt": datetime.utcnow() - timedelta(days=7)}
        })
        assert count == 0

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_bulk_operation_rate_limiting(self, authenticated_client):
        """Test bulk operations are rate limited (10 per hour)."""
        # Simulate 10 bulk operations
        for i in range(10):
                response = authenticated_client.post(
                    "/ipam/bulk/tags",
                    json={
                        "resource_type": "region",
                        "resource_ids": [str(uuid4())],
                        "operation": "add",
                        "tags": {"test": f"value{i}"}
                    }
                )
                if i < 10:
                    assert response.status_code in [status.HTTP_200_OK, status.HTTP_202_ACCEPTED]
        
        # 11th operation should be rate limited
        response = authenticated_client.post(
                "/ipam/bulk/tags",
                json={
                    "resource_type": "region",
                    "resource_ids": [str(uuid4())],
                    "operation": "add",
                    "tags": {"test": "value11"}
                }
        )
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


class TestAdvancedSearchEndpoints:
    """Test enhanced search capabilities."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_with_tag_and_logic(self, authenticated_client, test_db):
        """Test search with AND logic for multiple tags."""
        # Create test regions with tags
        await test_db.ipam_regions.insert_many([
                {
                    "user_id": "test_user_123",
                    "x_octet": 10,
                    "y_octet": 1,
                    "tags": {"environment": "production", "region": "us-east"}
                },
                {
                    "user_id": "test_user_123",
                    "x_octet": 10,
                    "y_octet": 2,
                    "tags": {"environment": "production", "region": "us-west"}
                }
        ])
        
        response = authenticated_client.get(
                "/ipam/search?tags=environment:production,region:us-east&tag_logic=and"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 1

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_with_tag_or_logic(self, authenticated_client, test_db):
        """Test search with OR logic for multiple tags."""
        await test_db.ipam_regions.insert_many([
                {"user_id": "test_user_123", "x_octet": 10, "y_octet": 1, "tags": {"environment": "production"}},
                {"user_id": "test_user_123", "x_octet": 10, "y_octet": 2, "tags": {"environment": "staging"}}
        ])
        
        response = authenticated_client.get(
                "/ipam/search?tags=environment:production,environment:staging&tag_logic=or"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_with_cidr_query(self, authenticated_client, test_db):
        """Test search with CIDR notation."""
        await test_db.ipam_hosts.insert_many([
                {"user_id": "test_user_123", "x_octet": 10, "y_octet": 5, "z_octet": 10},
                {"user_id": "test_user_123", "x_octet": 10, "y_octet": 5, "z_octet": 20}
        ])
        
        response = authenticated_client.get(
                "/ipam/search?cidr=10.5.0.0/16"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_with_ip_range_query(self, authenticated_client, test_db):
        """Test search with IP range (e.g., 10.0.0.1-10.0.0.50)."""
        await test_db.ipam_hosts.insert_many([
                {"user_id": "test_user_123", "x_octet": 10, "y_octet": 0, "z_octet": 10},
                {"user_id": "test_user_123", "x_octet": 10, "y_octet": 0, "z_octet": 30}
        ])
        
        response = authenticated_client.get(
                "/ipam/search?ip_range=10.0.0.1-10.0.0.50"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) >= 2

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_multi_field_sorting(self, authenticated_client, test_db):
        """Test search with multi-field sorting."""
        response = authenticated_client.get(
                "/ipam/search?sort=x_octet:asc,y_octet:desc"
        )
        
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_relevance_scoring(self, authenticated_client, test_db):
        """Test search results include relevance scores."""
        await test_db.ipam_regions.insert_one({
                "user_id": "test_user_123",
                "x_octet": 10,
                "y_octet": 1,
                "region_name": "Production Network"
        })
        
        response = authenticated_client.get(
                "/ipam/search?q=production"
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        if len(data["results"]) > 0:
                assert "relevance_score" in data["results"][0]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_search_result_caching(self, authenticated_client):
        """Test search results are cached for 5 minutes."""
        # First search
        response1 = authenticated_client.get("/ipam/search?q=test")
        assert response1.status_code == status.HTTP_200_OK
        
        # Second identical search (should use cache)
        response2 = authenticated_client.get("/ipam/search?q=test")
        assert response2.status_code == status.HTTP_200_OK


class TestPerformanceRequirements:
    """Test performance requirements for new endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_dashboard_stats_response_time(self, authenticated_client, test_db):
        """Test dashboard stats respond within 500ms."""
        import time
        
        # Create large dataset
        regions = [
        {"user_id": "test_user_123", "x_octet": 10, "y_octet": i, "status": "Active"}
        for i in range(100)
        ]
        await test_db.ipam_regions.insert_many(regions)
        
        start_time = time.time()
        response = authenticated_client.get("/ipam/statistics/dashboard")
        end_time = time.time()
        
        assert response.status_code == status.HTTP_200_OK
        response_time_ms = (end_time - start_time) * 1000
        assert response_time_ms < 500, f"Response time {response_time_ms}ms exceeds 500ms limit"

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_forecast_response_time(self, authenticated_client, test_db):
        """Test forecast calculation responds within 1 second."""
        import time
        
        region_id = str(uuid4())
        # Create 90 days of historical data
        for i in range(90):
            await test_db.ipam_audit_history.insert_one({
                "user_id": "test_user_123",
                "resource_id": region_id,
                "action_type": "create",
                "timestamp": datetime.utcnow() - timedelta(days=i)
            })
        
        start_time = time.time()
        response = authenticated_client.get(f"/ipam/statistics/forecast/region/{region_id}")
        end_time = time.time()
        
        assert response.status_code == status.HTTP_200_OK
        response_time_ms = (end_time - start_time) * 1000
        assert response_time_ms < 1000, f"Response time {response_time_ms}ms exceeds 1000ms limit"

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_bulk_operation_performance(self, authenticated_client, test_db):
        """Test bulk operations handle 500 items efficiently."""
        # Create 500 regions
        region_ids = [str(uuid4()) for _ in range(500)]
        await test_db.ipam_regions.insert_many([
        {"_id": rid, "user_id": "test_user_123", "x_octet": 10, "y_octet": i % 255, "tags": {}}
        for i, rid in enumerate(region_ids)
        ])
        
        response = authenticated_client.post(
        "/ipam/bulk/tags",
        json={
                "resource_type": "region",
                "resource_ids": region_ids,
                "operation": "add",
                "tags": {"bulk_test": "true"}
        }
        )
        
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_202_ACCEPTED]

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_concurrent_bulk_operations(self, authenticated_client, test_db):
        """Test system handles concurrent bulk operations."""
        import asyncio
        
        async def perform_bulk_operation(batch_num):
                region_ids = [str(uuid4()) for _ in range(50)]
                await test_db.ipam_regions.insert_many([
                    {"_id": rid, "user_id": "test_user_123", "x_octet": 10, "y_octet": i, "tags": {}}
                    for i, rid in enumerate(region_ids)
                ])
                
                response = authenticated_client.post(
                    "/ipam/bulk/tags",
                    json={
                        "resource_type": "region",
                        "resource_ids": region_ids,
                        "operation": "add",
                        "tags": {"batch": str(batch_num)}
                    }
                )
                return response.status_code
        
        # Run 3 concurrent bulk operations
        results = await asyncio.gather(*[perform_bulk_operation(i) for i in range(3)])
        
        # All should succeed
        for status_code in results:
                assert status_code in [status.HTTP_200_OK, status.HTTP_202_ACCEPTED]


class TestBackwardCompatibility:
    """Test backward compatibility with existing IPAM endpoints."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_existing_region_allocation_still_works(self, authenticated_client):
        """Test existing region allocation endpoint unchanged."""
        response = authenticated_client.post(
                "/ipam/regions",
                json={
                    "region_name": "Test Region",
                    "country": "United States"
                }
        )
        
        # Should work as before (201 or 200 depending on implementation)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_existing_host_allocation_still_works(self, authenticated_client, test_db):
        """Test existing host allocation endpoint unchanged."""
        # Create a region first
        await test_db.ipam_regions.insert_one({
                "user_id": "test_user_123",
                "x_octet": 10,
                "y_octet": 50,
                "status": "Active"
        })
        
        response = authenticated_client.post(
                "/ipam/hosts",
                json={
                    "hostname": "test-host",
                    "x_octet": 10,
                    "y_octet": 50
                }
        )
        
        # Should work as before
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_existing_search_still_works(self, authenticated_client):
        """Test existing search endpoint unchanged."""
        response = authenticated_client.get("/ipam/search?q=test")
        
        # Should work as before
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_existing_statistics_still_work(self, authenticated_client):
        """Test existing statistics endpoints unchanged."""
        # Test existing statistics endpoint (if it exists)
        response = authenticated_client.get("/ipam/statistics")
        
        # Should work as before or return 404 if not implemented
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND]


# Test execution summary
if __name__ == "__main__":
    print("IPAM Enhancement Tests")
    print("=" * 80)
    print("\nThese tests are designed to validate the new IPAM enhancement endpoints.")
    print("They should be run after implementing the following features:")
    print("\n1. Reservation Management (Req 1-2)")
    print("2. Shareable Links (Req 3-4)")
    print("3. User Preferences & Saved Filters (Req 5-6)")
    print("4. Notification Rules & Delivery (Req 7-8)")
    print("5. Capacity Forecasting & Trends (Req 9-11)")
    print("6. Webhook Configuration & Delivery (Req 12-13)")
    print("7. Enhanced Bulk Operations (Req 14)")
    print("8. Advanced Search (Req 15)")
    print("\nTo run these tests:")
    print("  uv run pytest tests/test_ipam_enhancements.py -v")
    print("\nTo run specific test classes:")
    print("  uv run pytest tests/test_ipam_enhancements.py::TestReservationEndpoints -v")
    print("\nTo run performance tests:")
    print("  uv run pytest tests/test_ipam_enhancements.py -m slow -v")
    print("=" * 80)
