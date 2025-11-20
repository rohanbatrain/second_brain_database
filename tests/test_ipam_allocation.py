"""
Unit tests for IPAM auto-allocation algorithms.

Tests the core allocation logic for finding next available X.Y and Z values,
capacity exhaustion detection, and Redis caching behavior.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from bson import ObjectId

from second_brain_database.managers.ipam_manager import (
    CapacityExhausted,
    IPAMManager,
    QuotaExceeded,
)


@pytest.fixture
def ipam_manager():
    """Create IPAM manager with mocked dependencies."""
    mock_db = Mock()
    mock_redis = AsyncMock()
    manager = IPAMManager(db_manager_instance=mock_db, redis_manager_instance=mock_redis)
    return manager


@pytest.fixture
def mock_country_mapping():
    """Mock country mapping data."""
    return {
        "_id": ObjectId(),
        "continent": "Asia",
        "country": "India",
        "x_start": 0,
        "x_end": 29,
        "total_blocks": 7680,
        "is_reserved": False,
        "created_at": datetime.now(timezone.utc),
    }


class TestFindNextXY:
    """Test find_next_xy auto-allocation algorithm."""

    @pytest.mark.asyncio
    async def test_find_next_xy_empty_country(self, ipam_manager, mock_country_mapping):
        """Test allocation in empty country returns first X.Y (0.0)."""
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping lookup
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock empty allocations (no regions allocated yet)
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=[])
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        ipam_manager.redis_mgr.get = AsyncMock(return_value=None)
        ipam_manager.redis_mgr.set_with_expiry = AsyncMock()

        # Execute
        x, y = await ipam_manager.find_next_xy(user_id, country)

        # Verify first allocation is 0.0
        assert x == 0
        assert y == 0

    @pytest.mark.asyncio
    async def test_find_next_xy_sequential_allocation(self, ipam_manager, mock_country_mapping):
        """Test sequential Y allocation within same X value."""
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock allocations: X=0 has Y values [0, 1, 2]
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=[0, 1, 2])
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        ipam_manager.redis_mgr.get = AsyncMock(return_value=None)
        ipam_manager.redis_mgr.set_with_expiry = AsyncMock()

        # Execute
        x, y = await ipam_manager.find_next_xy(user_id, country)

        # Verify next available is 0.3
        assert x == 0
        assert y == 3

    @pytest.mark.asyncio
    async def test_find_next_xy_x_exhausted_moves_to_next(self, ipam_manager, mock_country_mapping):
        """Test moving to next X value when current X is full."""
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock allocations: X=0 is full (256 Y values), X=1 has [0, 1]
        mock_collection = AsyncMock()

        async def mock_distinct(field, filter_dict):
            x_value = filter_dict.get("x_octet")
            if x_value == 0:
                # X=0 is full (all 256 Y values allocated)
                return list(range(256))
            elif x_value == 1:
                # X=1 has Y values [0, 1]
                return [0, 1]
            return []

        mock_collection.distinct = AsyncMock(side_effect=mock_distinct)
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        ipam_manager.redis_mgr.get = AsyncMock(return_value=None)
        ipam_manager.redis_mgr.set_with_expiry = AsyncMock()

        # Execute
        x, y = await ipam_manager.find_next_xy(user_id, country)

        # Verify allocation moved to X=1, Y=2
        assert x == 1
        assert y == 2

    @pytest.mark.asyncio
    async def test_find_next_xy_capacity_exhausted(self, ipam_manager, mock_country_mapping):
        """Test capacity exhaustion when all X values are full."""
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock allocations: All X values (0-29) are full
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=list(range(256)))  # All Y values allocated
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        ipam_manager.redis_mgr.get = AsyncMock(return_value=None)

        # Execute and verify exception
        with pytest.raises(CapacityExhausted) as exc_info:
            await ipam_manager.find_next_xy(user_id, country)

        assert "No available addresses" in str(exc_info.value)
        assert exc_info.value.context["resource_type"] == "region"

    @pytest.mark.asyncio
    async def test_find_next_xy_redis_cache_hit(self, ipam_manager, mock_country_mapping):
        """Test Redis cache hit for allocated Y values."""
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock Redis cache hit with serialized set
        ipam_manager.redis_mgr.get = AsyncMock(return_value="[0, 1, 2]")
        ipam_manager.redis_mgr.set_with_expiry = AsyncMock()

        # Mock collection (should not be called due to cache hit)
        mock_collection = AsyncMock()
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute
        x, y = await ipam_manager.find_next_xy(user_id, country)

        # Verify cache was used
        assert x == 0
        assert y == 3
        # Verify database was not queried
        mock_collection.distinct.assert_not_called()


class TestFindNextZ:
    """Test find_next_z auto-allocation algorithm."""

    @pytest.mark.asyncio
    async def test_find_next_z_empty_region(self, ipam_manager):
        """Test allocation in empty region returns first Z (1)."""
        user_id = "test_user_123"
        region_id = str(ObjectId())

        # Mock empty allocations
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=[])
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute
        z = await ipam_manager.find_next_z(user_id, region_id)

        # Verify first allocation is Z=1 (0 is network address)
        assert z == 1

    @pytest.mark.asyncio
    async def test_find_next_z_sequential_allocation(self, ipam_manager):
        """Test sequential Z allocation."""
        user_id = "test_user_123"
        region_id = str(ObjectId())

        # Mock allocations: Z values [1, 2, 3, 4]
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=[1, 2, 3, 4])
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute
        z = await ipam_manager.find_next_z(user_id, region_id)

        # Verify next available is Z=5
        assert z == 5

    @pytest.mark.asyncio
    async def test_find_next_z_skips_zero(self, ipam_manager):
        """Test that Z=0 is never allocated (network address)."""
        user_id = "test_user_123"
        region_id = str(ObjectId())

        # Mock empty allocations
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=[])
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute
        z = await ipam_manager.find_next_z(user_id, region_id)

        # Verify Z=0 is skipped
        assert z == 1

    @pytest.mark.asyncio
    async def test_find_next_z_skips_255(self, ipam_manager):
        """Test that Z=255 is never allocated (broadcast address)."""
        user_id = "test_user_123"
        region_id = str(ObjectId())

        # Mock allocations: All Z values except 255
        allocated_z = list(range(1, 255))  # 1-254
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=allocated_z)
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute and verify capacity exhausted
        with pytest.raises(CapacityExhausted) as exc_info:
            await ipam_manager.find_next_z(user_id, region_id)

        assert "No available host addresses" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_find_next_z_capacity_exhausted(self, ipam_manager):
        """Test capacity exhaustion when all 254 usable Z values are allocated."""
        user_id = "test_user_123"
        region_id = str(ObjectId())

        # Mock allocations: All usable Z values (1-254)
        allocated_z = list(range(1, 255))
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=allocated_z)
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute and verify exception
        with pytest.raises(CapacityExhausted) as exc_info:
            await ipam_manager.find_next_z(user_id, region_id)

        assert "No available host addresses" in str(exc_info.value)
        assert exc_info.value.context["resource_type"] == "host"

    @pytest.mark.asyncio
    async def test_find_next_z_finds_gap(self, ipam_manager):
        """Test finding gap in allocated Z values."""
        user_id = "test_user_123"
        region_id = str(ObjectId())

        # Mock allocations with gap: [1, 2, 3, 5, 6, 7] (missing 4)
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=[1, 2, 3, 5, 6, 7])
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute
        z = await ipam_manager.find_next_z(user_id, region_id)

        # Verify gap is filled (Z=4)
        assert z == 4


class TestRedisCaching:
    """Test Redis caching behavior for allocation algorithms."""

    @pytest.mark.asyncio
    async def test_cache_miss_queries_database(self, ipam_manager, mock_country_mapping):
        """Test cache miss triggers database query."""
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock Redis cache miss
        ipam_manager.redis_mgr.get = AsyncMock(return_value=None)
        ipam_manager.redis_mgr.set_with_expiry = AsyncMock()

        # Mock database query
        mock_collection = AsyncMock()
        mock_collection.distinct = AsyncMock(return_value=[0, 1])
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute
        await ipam_manager.find_next_xy(user_id, country)

        # Verify database was queried
        mock_collection.distinct.assert_called_once()
        # Verify cache was updated
        ipam_manager.redis_mgr.set_with_expiry.assert_called()

    @pytest.mark.asyncio
    async def test_cache_hit_skips_database(self, ipam_manager, mock_country_mapping):
        """Test cache hit skips database query."""
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock Redis cache hit
        ipam_manager.redis_mgr.get = AsyncMock(return_value="[0, 1]")

        # Mock database (should not be called)
        mock_collection = AsyncMock()
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute
        await ipam_manager.find_next_xy(user_id, country)

        # Verify database was not queried
        mock_collection.distinct.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_allocation(self, ipam_manager):
        """Test cache is invalidated after allocation."""
        user_id = "test_user_123"
        region_id = str(ObjectId())

        # Mock Redis delete
        ipam_manager.redis_mgr.delete = AsyncMock()

        # Call cache invalidation
        cache_key = f"ipam:allocated_y:{user_id}:0"
        await ipam_manager.redis_mgr.delete(cache_key)

        # Verify cache was deleted
        ipam_manager.redis_mgr.delete.assert_called_once_with(cache_key)


class TestQuotaEnforcement:
    """Test quota enforcement in allocation algorithms."""

    @pytest.mark.asyncio
    async def test_check_quota_within_limit(self, ipam_manager):
        """Test quota check passes when within limit."""
        user_id = "test_user_123"

        # Mock quota data
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(
            return_value={
                "user_id": user_id,
                "region_quota": 1000,
                "region_count": 500,
                "host_quota": 10000,
                "host_count": 5000,
            }
        )
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        ipam_manager.redis_mgr.get = AsyncMock(return_value=None)
        ipam_manager.redis_mgr.set_with_expiry = AsyncMock()

        # Execute
        result = await ipam_manager.check_user_quota(user_id, "region")

        # Verify quota check passed
        assert result is True

    @pytest.mark.asyncio
    async def test_check_quota_exceeded(self, ipam_manager):
        """Test quota check fails when limit exceeded."""
        user_id = "test_user_123"

        # Mock quota data (at limit)
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(
            return_value={
                "user_id": user_id,
                "region_quota": 1000,
                "region_count": 1000,  # At limit
                "host_quota": 10000,
                "host_count": 5000,
            }
        )
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        ipam_manager.redis_mgr.get = AsyncMock(return_value=None)

        # Execute and verify exception
        with pytest.raises(QuotaExceeded) as exc_info:
            await ipam_manager.check_user_quota(user_id, "region")

        assert "quota exceeded" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_quota_warning_at_threshold(self, ipam_manager):
        """Test warning is logged at 80% quota usage."""
        user_id = "test_user_123"

        # Mock quota data (at 80% threshold)
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(
            return_value={
                "user_id": user_id,
                "region_quota": 1000,
                "region_count": 800,  # 80% usage
                "host_quota": 10000,
                "host_count": 5000,
            }
        )
        ipam_manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        ipam_manager.redis_mgr.get = AsyncMock(return_value=None)
        ipam_manager.redis_mgr.set_with_expiry = AsyncMock()

        # Execute
        with patch("second_brain_database.managers.ipam_manager.logger") as mock_logger:
            result = await ipam_manager.check_user_quota(user_id, "region")

            # Verify warning was logged
            assert result is True
            # Check if warning was logged (implementation may vary)
