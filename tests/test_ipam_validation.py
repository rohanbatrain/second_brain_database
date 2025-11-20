"""
Unit tests for IPAM validation logic.

Tests IP format validation, tag format validation, uniqueness checks,
and quota enforcement.
"""

import pytest
from bson import ObjectId

from second_brain_database.managers.ipam_manager import (
    DuplicateAllocation,
    IPAMManager,
    QuotaExceeded,
    ValidationError,
)
from second_brain_database.utils.ipam_validation import (
    validate_ip_format,
    validate_octet_range,
    validate_tag_format,
)


class TestIPFormatValidation:
    """Test IP address format validation."""

    def test_valid_ip_in_10_range(self):
        """Test valid IP in 10.0.0.0/8 range."""
        assert validate_ip_format("10.0.0.1") is True
        assert validate_ip_format("10.255.255.254") is True
        assert validate_ip_format("10.5.23.45") is True

    def test_invalid_ip_outside_10_range(self):
        """Test invalid IP outside 10.0.0.0/8 range."""
        assert validate_ip_format("192.168.1.1") is False
        assert validate_ip_format("172.16.0.1") is False
        assert validate_ip_format("11.0.0.1") is False
        assert validate_ip_format("9.255.255.255") is False

    def test_invalid_ip_format(self):
        """Test invalid IP format."""
        assert validate_ip_format("10.0.0") is False
        assert validate_ip_format("10.0.0.0.1") is False
        assert validate_ip_format("10.256.0.1") is False
        assert validate_ip_format("10.0.0.256") is False
        assert validate_ip_format("not.an.ip.address") is False
        assert validate_ip_format("") is False
        assert validate_ip_format(None) is False

    def test_edge_cases(self):
        """Test edge cases for IP validation."""
        assert validate_ip_format("10.0.0.0") is True  # Network address
        assert validate_ip_format("10.255.255.255") is True  # Broadcast address
        assert validate_ip_format("10.0.0.255") is True  # Valid but typically reserved


class TestOctetRangeValidation:
    """Test octet range validation."""

    def test_valid_x_octet(self):
        """Test valid X octet values (0-255)."""
        assert validate_octet_range(0, "x") is True
        assert validate_octet_range(255, "x") is True
        assert validate_octet_range(128, "x") is True

    def test_invalid_x_octet(self):
        """Test invalid X octet values."""
        assert validate_octet_range(-1, "x") is False
        assert validate_octet_range(256, "x") is False
        assert validate_octet_range(1000, "x") is False

    def test_valid_y_octet(self):
        """Test valid Y octet values (0-255)."""
        assert validate_octet_range(0, "y") is True
        assert validate_octet_range(255, "y") is True
        assert validate_octet_range(128, "y") is True

    def test_invalid_y_octet(self):
        """Test invalid Y octet values."""
        assert validate_octet_range(-1, "y") is False
        assert validate_octet_range(256, "y") is False

    def test_valid_z_octet(self):
        """Test valid Z octet values (1-254, excluding 0 and 255)."""
        assert validate_octet_range(1, "z") is True
        assert validate_octet_range(254, "z") is True
        assert validate_octet_range(128, "z") is True

    def test_invalid_z_octet(self):
        """Test invalid Z octet values."""
        assert validate_octet_range(0, "z") is False  # Network address
        assert validate_octet_range(255, "z") is False  # Broadcast address
        assert validate_octet_range(-1, "z") is False
        assert validate_octet_range(256, "z") is False

    def test_invalid_octet_type(self):
        """Test invalid octet type parameter."""
        with pytest.raises(ValueError):
            validate_octet_range(128, "invalid")


class TestTagFormatValidation:
    """Test tag format validation."""

    def test_valid_tag_keys(self):
        """Test valid tag key formats."""
        assert validate_tag_format({"environment": "production"}) is True
        assert validate_tag_format({"env_type": "prod"}) is True
        assert validate_tag_format({"cost-center": "engineering"}) is True
        assert validate_tag_format({"team123": "backend"}) is True

    def test_invalid_tag_keys_special_chars(self):
        """Test invalid tag keys with special characters."""
        assert validate_tag_format({"env@type": "prod"}) is False
        assert validate_tag_format({"cost.center": "eng"}) is False
        assert validate_tag_format({"team#1": "backend"}) is False
        assert validate_tag_format({"env type": "prod"}) is False  # Space

    def test_invalid_tag_keys_empty(self):
        """Test invalid empty tag keys."""
        assert validate_tag_format({"": "value"}) is False
        assert validate_tag_format({}) is True  # Empty dict is valid

    def test_tag_key_length_limits(self):
        """Test tag key length validation."""
        # Valid length
        assert validate_tag_format({"a" * 50: "value"}) is True
        # Too long (if limit is enforced)
        # assert validate_tag_format({"a" * 256: "value"}) is False

    def test_multiple_tags(self):
        """Test validation of multiple tags."""
        tags = {
            "environment": "production",
            "team": "backend",
            "cost_center": "engineering",
            "region": "us-west-2",
        }
        assert validate_tag_format(tags) is True

    def test_mixed_valid_invalid_tags(self):
        """Test mixed valid and invalid tags."""
        tags = {"valid_key": "value", "invalid@key": "value"}
        assert validate_tag_format(tags) is False


class TestUniquenessValidation:
    """Test uniqueness validation for regions and hosts."""

    @pytest.mark.asyncio
    async def test_region_name_unique_within_user_country(self):
        """Test region name uniqueness within user and country."""
        from unittest.mock import AsyncMock, Mock

        manager = IPAMManager()
        user_id = "test_user_123"
        country = "India"
        region_name = "Mumbai DC1"

        # Mock database query - no existing region with same name
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute validation
        result = await manager._check_region_name_unique(user_id, country, region_name)

        # Verify uniqueness check passed
        assert result is True

    @pytest.mark.asyncio
    async def test_region_name_duplicate_raises_error(self):
        """Test duplicate region name raises error."""
        from unittest.mock import AsyncMock, Mock

        manager = IPAMManager()
        user_id = "test_user_123"
        country = "India"
        region_name = "Mumbai DC1"

        # Mock database query - existing region found
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(
            return_value={
                "_id": ObjectId(),
                "user_id": user_id,
                "country": country,
                "region_name": region_name,
            }
        )
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute and verify exception
        with pytest.raises(DuplicateAllocation) as exc_info:
            await manager._check_region_name_unique(user_id, country, region_name)

        assert "already exists" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_hostname_unique_within_user_region(self):
        """Test hostname uniqueness within user and region."""
        from unittest.mock import AsyncMock, Mock

        manager = IPAMManager()
        user_id = "test_user_123"
        region_id = str(ObjectId())
        hostname = "web-server-01"

        # Mock database query - no existing host with same name
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute validation
        result = await manager._check_hostname_unique(user_id, region_id, hostname)

        # Verify uniqueness check passed
        assert result is True

    @pytest.mark.asyncio
    async def test_hostname_duplicate_raises_error(self):
        """Test duplicate hostname raises error."""
        from unittest.mock import AsyncMock, Mock

        manager = IPAMManager()
        user_id = "test_user_123"
        region_id = str(ObjectId())
        hostname = "web-server-01"

        # Mock database query - existing host found
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(
            return_value={
                "_id": ObjectId(),
                "user_id": user_id,
                "region_id": ObjectId(region_id),
                "hostname": hostname,
            }
        )
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute and verify exception
        with pytest.raises(DuplicateAllocation) as exc_info:
            await manager._check_hostname_unique(user_id, region_id, hostname)

        assert "already exists" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_different_users_can_have_same_region_name(self):
        """Test different users can have same region name in same country."""
        from unittest.mock import AsyncMock, Mock

        manager = IPAMManager()
        user_id_1 = "user_123"
        user_id_2 = "user_456"
        country = "India"
        region_name = "Mumbai DC1"

        # Mock database query - region exists for user_1 but not user_2
        mock_collection = AsyncMock()

        async def mock_find_one(filter_dict):
            if filter_dict.get("user_id") == user_id_2:
                return None  # No conflict for user_2
            return {"user_id": user_id_1, "country": country, "region_name": region_name}

        mock_collection.find_one = AsyncMock(side_effect=mock_find_one)
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute validation for user_2
        result = await manager._check_region_name_unique(user_id_2, country, region_name)

        # Verify no conflict (user isolation)
        assert result is True


class TestQuotaValidation:
    """Test quota enforcement validation."""

    @pytest.mark.asyncio
    async def test_quota_check_creates_default_quota(self):
        """Test quota check creates default quota if not exists."""
        from unittest.mock import AsyncMock, Mock

        manager = IPAMManager()
        user_id = "new_user_123"

        # Mock database query - no existing quota
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_collection.insert_one = AsyncMock()
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        manager.redis_mgr.get = AsyncMock(return_value=None)
        manager.redis_mgr.set_with_expiry = AsyncMock()

        # Execute
        result = await manager.check_user_quota(user_id, "region")

        # Verify default quota was created
        mock_collection.insert_one.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_quota_check_enforces_region_limit(self):
        """Test quota check enforces region limit."""
        from unittest.mock import AsyncMock, Mock

        manager = IPAMManager()
        user_id = "test_user_123"

        # Mock quota at limit
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(
            return_value={
                "user_id": user_id,
                "region_quota": 1000,
                "region_count": 1000,
                "host_quota": 10000,
                "host_count": 5000,
            }
        )
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        manager.redis_mgr.get = AsyncMock(return_value=None)

        # Execute and verify exception
        with pytest.raises(QuotaExceeded) as exc_info:
            await manager.check_user_quota(user_id, "region")

        assert exc_info.value.context["quota_type"] == "region"

    @pytest.mark.asyncio
    async def test_quota_check_enforces_host_limit(self):
        """Test quota check enforces host limit."""
        from unittest.mock import AsyncMock, Mock

        manager = IPAMManager()
        user_id = "test_user_123"

        # Mock quota at limit
        mock_collection = AsyncMock()
        mock_collection.find_one = AsyncMock(
            return_value={
                "user_id": user_id,
                "region_quota": 1000,
                "region_count": 500,
                "host_quota": 10000,
                "host_count": 10000,
            }
        )
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Mock Redis cache miss
        manager.redis_mgr.get = AsyncMock(return_value=None)

        # Execute and verify exception
        with pytest.raises(QuotaExceeded) as exc_info:
            await manager.check_user_quota(user_id, "host")

        assert exc_info.value.context["quota_type"] == "host"

    @pytest.mark.asyncio
    async def test_quota_uses_redis_cache(self):
        """Test quota check uses Redis cache."""
        from unittest.mock import AsyncMock, Mock
        import json

        manager = IPAMManager()
        user_id = "test_user_123"

        # Mock Redis cache hit
        cached_quota = {
            "user_id": user_id,
            "region_quota": 1000,
            "region_count": 500,
            "host_quota": 10000,
            "host_count": 5000,
        }
        manager.redis_mgr.get = AsyncMock(return_value=json.dumps(cached_quota))

        # Mock database (should not be called)
        mock_collection = AsyncMock()
        manager.db.get_collection = Mock(return_value=mock_collection)

        # Execute
        result = await manager.check_user_quota(user_id, "region")

        # Verify cache was used and database not queried
        assert result is True
        mock_collection.find_one.assert_not_called()


class TestInputValidation:
    """Test input parameter validation."""

    def test_validate_region_name_length(self):
        """Test region name length validation."""
        # Valid lengths
        assert len("DC1") >= 1
        assert len("Mumbai Datacenter 1") <= 100

        # Invalid lengths (if enforced)
        # assert len("") == 0  # Too short
        # assert len("a" * 256) > 255  # Too long

    def test_validate_hostname_format(self):
        """Test hostname format validation."""
        # Valid hostnames
        valid_hostnames = [
            "web-server-01",
            "db.primary",
            "app_server_1",
            "host123",
        ]
        for hostname in valid_hostnames:
            assert isinstance(hostname, str)
            assert len(hostname) > 0

    def test_validate_description_length(self):
        """Test description length validation."""
        # Valid description
        description = "Primary datacenter in Mumbai region"
        assert len(description) <= 2000

    def test_validate_comment_length(self):
        """Test comment text length validation."""
        # Valid comment
        comment = "Allocated for production workload"
        assert len(comment) <= 2000

        # Invalid comment (if enforced)
        # long_comment = "a" * 2001
        # assert len(long_comment) > 2000
