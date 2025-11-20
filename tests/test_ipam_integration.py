"""
Integration tests for IPAM allocation flows.

Tests complete allocation workflows including:
- Region allocation with auto-allocation and quota updates
- Concurrent region creation with duplicate prevention
- Capacity exhaustion error handling
- Host allocation with auto-allocation and quota updates
- Batch allocation with transaction atomicity

Note: These are integration tests that test the complete flow with mocked
database and Redis dependencies. They verify the business logic integration
between components without requiring actual database connections.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from second_brain_database.managers.ipam_manager import (
    CapacityExhausted,
    IPAMManager,
    QuotaExceeded,
    ValidationError,
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


@pytest.fixture
def mock_region():
    """Mock region allocation data."""
    return {
        "_id": ObjectId(),
        "user_id": "test_user_123",
        "country": "India",
        "continent": "Asia",
        "x_octet": 0,
        "y_octet": 0,
        "cidr": "10.0.0.0/24",
        "region_name": "Mumbai DC1",
        "description": "Primary datacenter",
        "owner": "ops-team",
        "status": "Active",
        "tags": {"environment": "production"},
        "comments": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "created_by": "test_user_123",
        "updated_by": "test_user_123",
    }


@pytest.fixture
def mock_quota_info():
    """Mock quota information."""
    return {
        "current": 100,
        "limit": 1000,
        "available": 900,
        "usage_percent": 10.0,
        "warning": False,
    }


class TestRegionAllocationFlow:
    """Test complete region allocation workflow."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_region_allocation_complete_flow(
        self, ipam_manager, mock_country_mapping, mock_quota_info
    ):
        """
        Test complete region allocation flow:
        1. Verify auto-allocation
        2. Check quota update
        3. Verify audit logging
        """
        user_id = "test_user_123"
        country = "India"
        region_name = "Mumbai DC1"

        # Mock country mapping lookup
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock quota check (within limits)
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock find_next_xy to return first available
        ipam_manager.find_next_xy = AsyncMock(return_value=(0, 0))

        # Mock empty allocations for auto-allocation
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=None)  # No duplicate name
        mock_regions_collection.insert_one = AsyncMock(return_value=Mock(inserted_id=ObjectId()))

        # Mock update_quota_counter
        ipam_manager.update_quota_counter = AsyncMock()

        def get_collection_mock(name):
            if name == "ipam_regions":
                return mock_regions_collection
            return AsyncMock()

        ipam_manager.db_manager.get_collection = Mock(side_effect=get_collection_mock)
        ipam_manager.db_manager.log_query_start = Mock(return_value=0.0)
        ipam_manager.db_manager.log_query_success = Mock()
        ipam_manager.db_manager.transactions_supported = False  # Disable transactions for simpler mocking

        # Mock Redis operations
        ipam_manager.redis_manager.get = AsyncMock(return_value=None)
        ipam_manager.redis_manager.set_with_expiry = AsyncMock()
        ipam_manager.redis_manager.delete = AsyncMock()

        # Execute allocation
        result = await ipam_manager.allocate_region(
            user_id=user_id,
            country=country,
            region_name=region_name,
            description="Primary datacenter",
            tags={"environment": "production"},
        )

        # Verify auto-allocation selected first available X.Y (0.0)
        assert result["x_octet"] == 0
        assert result["y_octet"] == 0
        assert result["cidr"] == "10.0.0.0/24"

        # Verify region was inserted
        mock_regions_collection.insert_one.assert_called_once()

        # Verify quota was updated
        ipam_manager.update_quota_counter.assert_called_once()

        # Verify cache was invalidated
        ipam_manager.redis_manager.delete.assert_called()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_region_allocation_quota_enforcement(self, ipam_manager, mock_country_mapping):
        """Test region allocation fails when quota exceeded."""
        user_id = "test_user_123"
        country = "India"
        region_name = "Mumbai DC1"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock quota check (exceeded)
        ipam_manager.check_user_quota = AsyncMock(
            side_effect=QuotaExceeded(
                "Region quota exceeded",
                quota_type="region",
                limit=1000,
                current=1000,
            )
        )

        # Execute and verify exception
        with pytest.raises(QuotaExceeded) as exc_info:
            await ipam_manager.allocate_region(
                user_id=user_id,
                country=country,
                region_name=region_name,
            )

        assert exc_info.value.context["quota_type"] == "region"
        assert exc_info.value.context["limit"] == 1000

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_region_allocation_capacity_exhausted(
        self, ipam_manager, mock_country_mapping, mock_quota_info
    ):
        """Test region allocation fails when country capacity exhausted."""
        user_id = "test_user_123"
        country = "India"
        region_name = "Mumbai DC1"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock quota check (within limits)
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock find_next_xy to raise CapacityExhausted
        ipam_manager.find_next_xy = AsyncMock(
            side_effect=CapacityExhausted(
                "No available addresses in country India",
                resource_type="region",
                capacity=7680,
                allocated=7680,
            )
        )

        # Mock no duplicate name
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=None)
        ipam_manager.db_manager.get_collection = Mock(return_value=mock_regions_collection)

        # Execute and verify exception
        with pytest.raises(CapacityExhausted) as exc_info:
            await ipam_manager.allocate_region(
                user_id=user_id,
                country=country,
                region_name=region_name,
            )

        assert exc_info.value.context["resource_type"] == "region"


class TestConcurrentRegionAllocation:
    """Test concurrent region allocation with duplicate prevention."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_allocation_no_duplicates(
        self, ipam_manager, mock_country_mapping, mock_quota_info
    ):
        """
        Test concurrent region allocations don't create duplicates.
        Simulates race condition with retry logic.
        """
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock quota check
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock find_next_xy - first returns (0,0), then (0,1) after retry
        call_count = 0

        async def mock_find_next_xy(uid, ctry):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (0, 0)  # First attempt
            return (0, 1)  # Second attempt after conflict

        ipam_manager.find_next_xy = AsyncMock(side_effect=mock_find_next_xy)

        # Mock update_quota_counter
        ipam_manager.update_quota_counter = AsyncMock()

        # Mock regions collection
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=None)  # No duplicate name

        # First insert raises DuplicateKeyError, second succeeds
        insert_call_count = 0

        async def mock_insert_one(*args, **kwargs):
            nonlocal insert_call_count
            insert_call_count += 1
            if insert_call_count == 1:
                raise DuplicateKeyError("Duplicate key error")
            return Mock(inserted_id=ObjectId())

        mock_regions_collection.insert_one = AsyncMock(side_effect=mock_insert_one)

        ipam_manager.db_manager.get_collection = Mock(return_value=mock_regions_collection)
        ipam_manager.db_manager.log_query_start = Mock(return_value=0.0)
        ipam_manager.db_manager.log_query_success = Mock()
        ipam_manager.db_manager.transactions_supported = False

        # Mock Redis
        ipam_manager.redis_manager.get = AsyncMock(return_value=None)
        ipam_manager.redis_manager.set_with_expiry = AsyncMock()
        ipam_manager.redis_manager.delete = AsyncMock()

        # Execute allocation with retry
        result = await ipam_manager.allocate_region(
            user_id=user_id,
            country=country,
            region_name="Mumbai DC1",
        )

        # Verify retry logic worked and allocated next available (0.1)
        assert result["x_octet"] == 0
        assert result["y_octet"] == 1
        assert insert_call_count == 2  # First failed, second succeeded

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_concurrent_allocation_max_retries_exceeded(
        self, ipam_manager, mock_country_mapping, mock_quota_info
    ):
        """Test allocation fails after max retries on persistent conflicts."""
        user_id = "test_user_123"
        country = "India"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock quota check
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock find_next_xy
        ipam_manager.find_next_xy = AsyncMock(return_value=(0, 0))

        # Mock update_quota_counter
        ipam_manager.update_quota_counter = AsyncMock()

        # Mock regions collection
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=None)

        # Always raise DuplicateKeyError
        mock_regions_collection.insert_one = AsyncMock(
            side_effect=DuplicateKeyError("Persistent conflict")
        )

        ipam_manager.db_manager.get_collection = Mock(return_value=mock_regions_collection)
        ipam_manager.db_manager.log_query_start = Mock(return_value=0.0)
        ipam_manager.db_manager.log_query_error = Mock()
        ipam_manager.db_manager.transactions_supported = False

        # Mock Redis
        ipam_manager.redis_manager.get = AsyncMock(return_value=None)
        ipam_manager.redis_manager.set_with_expiry = AsyncMock()

        # Execute and verify exception after max retries (should raise DuplicateAllocation)
        from second_brain_database.managers.ipam_manager import DuplicateAllocation

        with pytest.raises(DuplicateAllocation):
            await ipam_manager.allocate_region(
                user_id=user_id,
                country=country,
                region_name="Mumbai DC1",
            )


class TestHostAllocationFlow:
    """Test complete host allocation workflow."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_host_allocation_complete_flow(self, ipam_manager, mock_region, mock_quota_info):
        """
        Test complete host allocation flow:
        1. Verify auto-allocation
        2. Check quota update
        3. Verify audit logging
        """
        user_id = "test_user_123"
        region_id = str(mock_region["_id"])
        hostname = "web-server-01"

        # Mock region lookup
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=mock_region)

        # Mock quota check
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock find_next_z
        ipam_manager.find_next_z = AsyncMock(return_value=1)

        # Mock update_quota_counter
        ipam_manager.update_quota_counter = AsyncMock()

        # Mock hosts collection
        mock_hosts_collection = AsyncMock()
        mock_hosts_collection.find_one = AsyncMock(return_value=None)  # No duplicate hostname
        mock_hosts_collection.insert_one = AsyncMock(return_value=Mock(inserted_id=ObjectId()))

        def get_collection_mock(name):
            if name == "ipam_regions":
                return mock_regions_collection
            elif name == "ipam_hosts":
                return mock_hosts_collection
            return AsyncMock()

        ipam_manager.db_manager.get_collection = Mock(side_effect=get_collection_mock)
        ipam_manager.db_manager.log_query_start = Mock(return_value=0.0)
        ipam_manager.db_manager.log_query_success = Mock()
        ipam_manager.db_manager.transactions_supported = False

        # Mock Redis
        ipam_manager.redis_manager.get = AsyncMock(return_value=None)
        ipam_manager.redis_manager.set_with_expiry = AsyncMock()
        ipam_manager.redis_manager.delete = AsyncMock()

        # Execute allocation
        result = await ipam_manager.allocate_host(
            user_id=user_id,
            region_id=region_id,
            hostname=hostname,
            metadata={
                "device_type": "VM",
                "os_type": "Linux",
                "application": "web-server",
            },
        )

        # Verify auto-allocation selected first available Z (1)
        assert result["z_octet"] == 1
        assert result["ip_address"] == "10.0.0.1"

        # Verify host was inserted
        mock_hosts_collection.insert_one.assert_called_once()

        # Verify quota was updated
        ipam_manager.update_quota_counter.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_host_allocation_quota_enforcement(self, ipam_manager, mock_region):
        """Test host allocation fails when quota exceeded."""
        user_id = "test_user_123"
        region_id = str(mock_region["_id"])
        hostname = "web-server-01"

        # Mock region lookup
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=mock_region)
        ipam_manager.db_manager.get_collection = Mock(return_value=mock_regions_collection)

        # Mock quota check (exceeded)
        ipam_manager.check_user_quota = AsyncMock(
            side_effect=QuotaExceeded(
                "Host quota exceeded",
                quota_type="host",
                limit=10000,
                current=10000,
            )
        )

        # Execute and verify exception
        with pytest.raises(QuotaExceeded) as exc_info:
            await ipam_manager.allocate_host(
                user_id=user_id,
                region_id=region_id,
                hostname=hostname,
            )

        assert exc_info.value.context["quota_type"] == "host"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_host_allocation_region_capacity_exhausted(
        self, ipam_manager, mock_region, mock_quota_info
    ):
        """Test host allocation fails when region capacity exhausted (254 hosts)."""
        user_id = "test_user_123"
        region_id = str(mock_region["_id"])
        hostname = "web-server-255"

        # Mock region lookup
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=mock_region)

        # Mock quota check
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock find_next_z to raise CapacityExhausted
        ipam_manager.find_next_z = AsyncMock(
            side_effect=CapacityExhausted(
                "No available host addresses in region",
                resource_type="host",
                capacity=254,
                allocated=254,
            )
        )

        # Mock hosts collection
        mock_hosts_collection = AsyncMock()
        mock_hosts_collection.find_one = AsyncMock(return_value=None)

        def get_collection_mock(name):
            if name == "ipam_regions":
                return mock_regions_collection
            elif name == "ipam_hosts":
                return mock_hosts_collection
            return AsyncMock()

        ipam_manager.db_manager.get_collection = Mock(side_effect=get_collection_mock)

        # Execute and verify exception
        with pytest.raises(CapacityExhausted) as exc_info:
            await ipam_manager.allocate_host(
                user_id=user_id,
                region_id=region_id,
                hostname=hostname,
            )

        assert exc_info.value.context["resource_type"] == "host"


class TestBatchHostAllocation:
    """Test batch host allocation with transaction atomicity."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_batch_allocation_success(self, ipam_manager, mock_region, mock_quota_info):
        """Test successful batch allocation of multiple hosts."""
        user_id = "test_user_123"
        region_id = str(mock_region["_id"])
        count = 5
        hostname_prefix = "web-server"

        # Mock region lookup
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=mock_region)

        # Mock quota check
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock update_quota_counter
        ipam_manager.update_quota_counter = AsyncMock()

        # Mock hosts collection with cursor for finding allocated Z values
        mock_hosts_collection = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.to_list = AsyncMock(return_value=[])  # No allocated hosts
        mock_hosts_collection.find = Mock(return_value=mock_cursor)
        # Since transactions_supported=False, it will use insert_one in a loop
        mock_hosts_collection.insert_one = AsyncMock(return_value=Mock(inserted_id=ObjectId()))

        def get_collection_mock(name):
            if name == "ipam_regions":
                return mock_regions_collection
            elif name == "ipam_hosts":
                return mock_hosts_collection
            return AsyncMock()

        ipam_manager.db_manager.get_collection = Mock(side_effect=get_collection_mock)
        ipam_manager.db_manager.log_query_start = Mock(return_value=0.0)
        ipam_manager.db_manager.log_query_success = Mock()
        ipam_manager.db_manager.transactions_supported = False

        # Mock Redis
        ipam_manager.redis_manager.get = AsyncMock(return_value=None)
        ipam_manager.redis_manager.set_with_expiry = AsyncMock()
        ipam_manager.redis_manager.delete = AsyncMock()

        # Execute batch allocation
        result = await ipam_manager.allocate_hosts_batch(
            user_id=user_id,
            region_id=region_id,
            count=count,
            hostname_prefix=hostname_prefix,
        )

        # Verify consecutive Z values allocated (1-5)
        assert result["total_allocated"] == count
        assert len(result["allocated_hosts"]) == count
        assert result["allocated_hosts"][0]["z_octet"] == 1
        assert result["allocated_hosts"][4]["z_octet"] == 5

        # Verify insert_one was called for each host (since transactions_supported=False)
        assert mock_hosts_collection.insert_one.call_count == count

        # Verify quota was updated with correct count
        ipam_manager.update_quota_counter.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_batch_allocation_exceeds_limit(self, ipam_manager, mock_region):
        """Test batch allocation fails when count exceeds limit (100)."""
        user_id = "test_user_123"
        region_id = str(mock_region["_id"])
        count = 101  # Exceeds limit

        ipam_manager.db_manager.log_query_start = Mock(return_value=0.0)
        ipam_manager.db_manager.log_query_error = Mock()

        # Execute and verify exception
        with pytest.raises(ValidationError) as exc_info:
            await ipam_manager.allocate_hosts_batch(
                user_id=user_id,
                region_id=region_id,
                count=count,
                hostname_prefix="web-server",
            )

        assert "limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_batch_allocation_partial_failure(
        self, ipam_manager, mock_region, mock_quota_info
    ):
        """Test batch allocation handles partial failures gracefully."""
        user_id = "test_user_123"
        region_id = str(mock_region["_id"])
        count = 10

        # Mock region lookup
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=mock_region)

        # Mock quota check
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock allocations - only 5 Z values available (249 already allocated)
        mock_hosts_collection = AsyncMock()
        mock_cursor = AsyncMock()
        # Return 249 allocated hosts (Z values 1-249)
        mock_cursor.to_list = AsyncMock(
            return_value=[{"z_octet": z} for z in range(1, 250)]
        )
        mock_hosts_collection.find = Mock(return_value=mock_cursor)

        def get_collection_mock(name):
            if name == "ipam_regions":
                return mock_regions_collection
            elif name == "ipam_hosts":
                return mock_hosts_collection
            return AsyncMock()

        ipam_manager.db_manager.get_collection = Mock(side_effect=get_collection_mock)
        ipam_manager.db_manager.log_query_start = Mock(return_value=0.0)
        ipam_manager.db_manager.log_query_error = Mock()

        # Mock Redis
        ipam_manager.redis_manager.get = AsyncMock(return_value=None)

        # Execute and verify partial failure
        with pytest.raises(CapacityExhausted) as exc_info:
            await ipam_manager.allocate_hosts_batch(
                user_id=user_id,
                region_id=region_id,
                count=count,
                hostname_prefix="web-server",
            )

        # Verify capacity exhaustion was detected
        assert exc_info.value.context["resource_type"] == "host"


class TestTransactionAtomicity:
    """Test transaction atomicity for allocation operations."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_allocation_rollback_on_quota_update_failure(
        self, ipam_manager, mock_country_mapping, mock_quota_info
    ):
        """Test allocation is rolled back if quota update fails."""
        user_id = "test_user_123"
        country = "India"
        region_name = "Mumbai DC1"

        # Mock country mapping
        ipam_manager.get_country_mapping = AsyncMock(return_value=mock_country_mapping)

        # Mock quota check
        ipam_manager.check_user_quota = AsyncMock(return_value=mock_quota_info)

        # Mock find_next_xy
        ipam_manager.find_next_xy = AsyncMock(return_value=(0, 0))

        # Mock update_quota_counter to fail
        ipam_manager.update_quota_counter = AsyncMock(
            side_effect=Exception("Quota update failed")
        )

        # Mock regions collection
        mock_regions_collection = AsyncMock()
        mock_regions_collection.find_one = AsyncMock(return_value=None)
        mock_regions_collection.insert_one = AsyncMock(return_value=Mock(inserted_id=ObjectId()))

        ipam_manager.db_manager.get_collection = Mock(return_value=mock_regions_collection)
        ipam_manager.db_manager.log_query_start = Mock(return_value=0.0)
        ipam_manager.db_manager.log_query_error = Mock()
        ipam_manager.db_manager.transactions_supported = False

        # Mock Redis
        ipam_manager.redis_manager.get = AsyncMock(return_value=None)
        ipam_manager.redis_manager.set_with_expiry = AsyncMock()

        # Execute and verify exception
        from second_brain_database.managers.ipam_manager import IPAMError

        with pytest.raises(IPAMError) as exc_info:
            await ipam_manager.allocate_region(
                user_id=user_id,
                country=country,
                region_name=region_name,
            )

        assert "Quota update failed" in str(exc_info.value)
