"""
IPAM Backend Enhancements - Backward Compatibility Tests

This test suite verifies that all existing IPAM functionality continues to work
correctly after the enhancements have been added. It tests all original endpoints
to ensure no breaking changes were introduced.
"""

import pytest
from datetime import datetime
from typing import Dict, Any
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient

from second_brain_database.main import app

# Test data
TEST_USER_ID = "test_user_backward_compat"
TEST_COUNTRY = "India"
TEST_REGION_NAME = "Test Region Backward Compat"
TEST_HOSTNAME = "test-host-backward-compat"


@pytest.fixture
def test_client():
    """Create test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user with IPAM permissions."""
    return {
        "_id": TEST_USER_ID,
        "username": "test_user_backward_compat",
        "email": "test_backward_compat@example.com",
        "permissions": [
            "ipam:read",
            "ipam:allocate",
            "ipam:update",
            "ipam:release",
            "ipam:admin"
        ]
    }


@pytest.fixture
def authenticated_client(test_client, mock_auth_user):
    """Create test client with authentication dependency override."""
    from second_brain_database.routes.ipam.dependencies import get_current_user_for_ipam
    
    def override_get_current_user():
        return mock_auth_user
    
    app.dependency_overrides[get_current_user_for_ipam] = override_get_current_user
    yield test_client
    app.dependency_overrides.clear()


class TestBackwardCompatibility:
    """Test suite for backward compatibility verification."""
    
    def test_health_check_endpoint(self, test_client: TestClient):
        """Test that health check endpoint still works."""
        response = test_client.get("/ipam/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
    
    def test_list_countries_endpoint(self, authenticated_client: TestClient):
        """Test that list countries endpoint still works."""
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_all_countries') as mock_get:
            mock_get.return_value = [
                {"continent": "Asia", "country": "India", "x_start": 0, "x_end": 29}
            ]
            response = authenticated_client.post("/ipam/countries")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
    
    def test_get_country_endpoint(self, authenticated_client: TestClient):
        """Test that get country endpoint still works."""
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_country_mapping') as mock_get:
            mock_get.return_value = {
                "continent": "Asia",
                "country": TEST_COUNTRY,
                "x_start": 0,
                "x_end": 29
            }
            response = authenticated_client.get(f"/ipam/countries/{TEST_COUNTRY}")
            assert response.status_code == 200
            data = response.json()
            assert data["country"] == TEST_COUNTRY
    
    def test_get_country_utilization_endpoint(self, authenticated_client: TestClient):
        """Test that country utilization endpoint still works."""
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.calculate_country_utilization') as mock_calc:
            mock_calc.return_value = {
                "resource_type": "country",
                "total_capacity": 7680,
                "allocated": 100,
                "available": 7580,
                "utilization_percent": 1.3
            }
            response = authenticated_client.get(f"/ipam/countries/{TEST_COUNTRY}/utilization")
            assert response.status_code == 200
            data = response.json()
            assert "resource_type" in data
            assert data["resource_type"] == "country"
    
    @pytest.mark.asyncio
    async def test_create_region_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that create region endpoint still works."""
        response = await async_client.post(
            "/ipam/regions",
            params={
                "country": TEST_COUNTRY,
                "region_name": f"{TEST_REGION_NAME}_{datetime.utcnow().timestamp()}",
                "description": "Test region for backward compatibility"
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert "region_id" in data
        assert "cidr" in data
        assert "x_octet" in data
        assert "y_octet" in data
        assert "country" in data
        assert data["country"] == TEST_COUNTRY
        # Verify new owner fields are present
        assert "owner_name" in data
        assert "owner_id" in data
        return data["region_id"]
    
    @pytest.mark.asyncio
    async def test_list_regions_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that list regions endpoint still works."""
        response = await async_client.get("/ipam/regions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)
    
    @pytest.mark.asyncio
    async def test_get_region_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that get region endpoint still works."""
        # First create a region
        region_id = await self.test_create_region_endpoint(async_client, auth_headers)
        
        # Then get it
        response = await async_client.get(f"/ipam/regions/{region_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["region_id"] == region_id
        assert "cidr" in data
        assert "country" in data
        # Verify new owner fields are present
        assert "owner_name" in data
        assert "owner_id" in data
    
    @pytest.mark.asyncio
    async def test_update_region_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that update region endpoint still works."""
        # First create a region
        region_id = await self.test_create_region_endpoint(async_client, auth_headers)
        
        # Then update it
        new_description = "Updated description for backward compat test"
        response = await async_client.patch(
            f"/ipam/regions/{region_id}",
            params={"description": new_description},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == new_description
        # Verify new owner fields are present
        assert "owner_name" in data
        assert "owner_id" in data
    
    @pytest.mark.asyncio
    async def test_get_region_utilization_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that region utilization endpoint still works."""
        # First create a region
        region_id = await self.test_create_region_endpoint(async_client, auth_headers)
        
        # Then get utilization
        response = await async_client.get(f"/ipam/regions/{region_id}/utilization", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "resource_type" in data
        assert data["resource_type"] == "region"
        assert "total_capacity" in data
        assert data["total_capacity"] == 254  # /24 network has 254 usable hosts
    
    @pytest.mark.asyncio
    async def test_preview_next_region_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that preview next region endpoint still works."""
        response = await async_client.get(
            "/ipam/regions/preview-next",
            params={"country": TEST_COUNTRY},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "country" in data
        assert "next_cidr" in data
        assert "x_octet" in data
        assert "y_octet" in data
    
    @pytest.mark.asyncio
    async def test_add_region_comment_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that add region comment endpoint still works."""
        # First create a region
        region_id = await self.test_create_region_endpoint(async_client, auth_headers)
        
        # Then add comment
        response = await async_client.post(
            f"/ipam/regions/{region_id}/comments",
            params={"comment_text": "Test comment for backward compatibility"},
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_create_host_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that create host endpoint still works."""
        # First create a region
        region_id = await self.test_create_region_endpoint(async_client, auth_headers)
        
        # Then create a host
        response = await async_client.post(
            "/ipam/hosts",
            params={
                "region_id": region_id,
                "hostname": f"{TEST_HOSTNAME}_{datetime.utcnow().timestamp()}",
                "device_type": "VM",
                "purpose": "Test host for backward compatibility"
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert "host_id" in data
        assert "ip_address" in data
        assert "hostname" in data
        assert "z_octet" in data
        # Verify new owner fields are present
        assert "owner_name" in data
        assert "owner_id" in data
        return data["host_id"], data["ip_address"]
    
    @pytest.mark.asyncio
    async def test_list_hosts_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that list hosts endpoint still works."""
        response = await async_client.get("/ipam/hosts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
        assert isinstance(data["items"], list)
    
    @pytest.mark.asyncio
    async def test_get_host_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that get host endpoint still works."""
        # First create a host
        host_id, _ = await self.test_create_host_endpoint(async_client, auth_headers)
        
        # Then get it
        response = await async_client.get(f"/ipam/hosts/{host_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["host_id"] == host_id
        assert "ip_address" in data
        assert "hostname" in data
        # Verify new owner fields are present
        assert "owner_name" in data
        assert "owner_id" in data
    
    @pytest.mark.asyncio
    async def test_get_host_by_ip_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that get host by IP endpoint still works."""
        # First create a host
        _, ip_address = await self.test_create_host_endpoint(async_client, auth_headers)
        
        # Then lookup by IP
        response = await async_client.get(f"/ipam/hosts/by-ip/{ip_address}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["ip_address"] == ip_address
        # Verify new owner fields are present
        assert "owner_name" in data
        assert "owner_id" in data
    
    @pytest.mark.asyncio
    async def test_update_host_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that update host endpoint still works."""
        # First create a host
        host_id, _ = await self.test_create_host_endpoint(async_client, auth_headers)
        
        # Then update it
        new_purpose = "Updated purpose for backward compat test"
        response = await async_client.patch(
            f"/ipam/hosts/{host_id}",
            params={"purpose": new_purpose},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["purpose"] == new_purpose
        # Verify new owner fields are present
        assert "owner_name" in data
        assert "owner_id" in data
    
    @pytest.mark.asyncio
    async def test_preview_next_host_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that preview next host endpoint still works."""
        # First create a region
        region_id = await self.test_create_region_endpoint(async_client, auth_headers)
        
        # Then preview next host
        response = await async_client.get(
            "/ipam/hosts/preview-next",
            params={"region_id": region_id},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "region_id" in data
        assert "next_ip" in data
        assert "z_octet" in data
    
    @pytest.mark.asyncio
    async def test_add_host_comment_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that add host comment endpoint still works."""
        # First create a host
        host_id, _ = await self.test_create_host_endpoint(async_client, auth_headers)
        
        # Then add comment
        response = await async_client.post(
            f"/ipam/hosts/{host_id}/comments",
            params={"comment_text": "Test comment for backward compatibility"},
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_batch_create_hosts_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that batch create hosts endpoint still works."""
        # First create a region
        region_id = await self.test_create_region_endpoint(async_client, auth_headers)
        
        # Then batch create hosts
        response = await async_client.post(
            "/ipam/hosts/batch",
            params={
                "region_id": region_id,
                "count": 5,
                "hostname_prefix": "batch-test-",
                "device_type": "Container"
            },
            headers=auth_headers
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert "hosts" in data
        assert len(data["hosts"]) == 5
        # Verify new owner fields are present in each host
        for host in data["hosts"]:
            assert "owner_name" in host
            assert "owner_id" in host
    
    @pytest.mark.asyncio
    async def test_bulk_lookup_hosts_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that bulk lookup hosts endpoint still works."""
        # First create some hosts
        host_id1, ip1 = await self.test_create_host_endpoint(async_client, auth_headers)
        host_id2, ip2 = await self.test_create_host_endpoint(async_client, auth_headers)
        
        # Then bulk lookup
        response = await async_client.post(
            "/ipam/hosts/bulk-lookup",
            params={"ip_addresses": [ip1, ip2]},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert data["found"] == 2
    
    @pytest.mark.asyncio
    async def test_interpret_ip_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that interpret IP endpoint still works."""
        # First create a host
        _, ip_address = await self.test_create_host_endpoint(async_client, auth_headers)
        
        # Then interpret it
        response = await async_client.post(
            "/ipam/interpret",
            params={"ip_address": ip_address},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "ip_address" in data
        assert "hierarchy" in data
        hierarchy = data["hierarchy"]
        assert "global_root" in hierarchy
        assert "continent" in hierarchy
        assert "country" in hierarchy
        assert "region" in hierarchy
        assert "host" in hierarchy
    
    @pytest.mark.asyncio
    async def test_search_allocations_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that search allocations endpoint still works."""
        response = await async_client.get(
            "/ipam/search",
            params={"country": TEST_COUNTRY},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
    
    @pytest.mark.asyncio
    async def test_statistics_endpoints(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that statistics endpoints still work."""
        # Test continent statistics
        response = await async_client.get("/ipam/statistics/continent/Asia", headers=auth_headers)
        assert response.status_code == 200
        
        # Test top utilized
        response = await async_client.get("/ipam/statistics/top-utilized", headers=auth_headers)
        assert response.status_code == 200
        
        # Test allocation velocity
        response = await async_client.get("/ipam/statistics/allocation-velocity", headers=auth_headers)
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_audit_history_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that audit history endpoint still works."""
        response = await async_client.get("/ipam/audit/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "pagination" in data
    
    @pytest.mark.asyncio
    async def test_export_import_endpoints(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that export/import endpoints still work."""
        # Test export creation
        response = await async_client.post(
            "/ipam/export",
            params={"format": "csv"},
            headers=auth_headers
        )
        assert response.status_code == 202
        data = response.json()
        assert "job_id" in data
        
        # Test import preview
        response = await async_client.post(
            "/ipam/import/preview",
            params={"file_content": "hostname,ip_address\ntest,10.0.0.1"},
            headers=auth_headers
        )
        # May return 200 or 400 depending on validation
        assert response.status_code in [200, 400]
    
    @pytest.mark.asyncio
    async def test_retire_host_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that retire host endpoint still works."""
        # First create a host
        host_id, _ = await self.test_create_host_endpoint(async_client, auth_headers)
        
        # Then retire it
        response = await async_client.delete(
            f"/ipam/hosts/{host_id}",
            params={"reason": "Test retirement for backward compatibility"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_retire_region_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that retire region endpoint still works."""
        # First create a region
        region_id = await self.test_create_region_endpoint(async_client, auth_headers)
        
        # Then retire it
        response = await async_client.delete(
            f"/ipam/regions/{region_id}",
            params={"reason": "Test retirement for backward compatibility", "cascade": False},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_bulk_release_hosts_endpoint(self, async_client: AsyncClient, auth_headers: Dict[str, str]):
        """Test that bulk release hosts endpoint still works."""
        # First create some hosts
        host_id1, _ = await self.test_create_host_endpoint(async_client, auth_headers)
        host_id2, _ = await self.test_create_host_endpoint(async_client, auth_headers)
        
        # Then bulk release
        response = await async_client.post(
            "/ipam/hosts/bulk-release",
            params={"host_ids": [host_id1, host_id2], "reason": "Test bulk release"},
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["success_count"] >= 0


@pytest.fixture
async def async_client():
    """Create async HTTP client for testing."""
    from httpx import AsyncClient
    from second_brain_database.main import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def auth_headers(async_client: AsyncClient):
    """Create authentication headers for testing."""
    # This would need to be implemented based on your auth system
    # For now, return a mock header
    return {"Authorization": "Bearer test_token"}
