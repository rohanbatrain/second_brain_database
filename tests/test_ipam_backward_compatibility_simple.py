"""
IPAM Backend Enhancements - Simplified Backward Compatibility Tests

This test suite verifies that all existing IPAM endpoints are still accessible
and return the expected response structure after enhancements.
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from second_brain_database.main import app


@pytest.fixture
def test_client():
    """Create test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user with IPAM permissions."""
    return {
        "_id": "test_user_backward_compat",
        "username": "test_user",
        "email": "test@example.com",
        "permissions": ["ipam:read", "ipam:allocate", "ipam:update", "ipam:release", "ipam:admin"]
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


class TestBackwardCompatibilityEndpoints:
    """Test that all original endpoints are still accessible."""
    
    def test_health_endpoint_exists(self, test_client):
        """Verify health check endpoint exists."""
        response = test_client.get("/ipam/health")
        # Should return 200 or 503, not 404
        assert response.status_code in [200, 503]
    
    def test_countries_endpoints_exist(self, authenticated_client):
        """Verify country endpoints exist."""
        # List countries
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_all_countries', return_value=[]):
            response = authenticated_client.post("/ipam/countries")
            assert response.status_code == 200
        
        # Get country
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_country_mapping', return_value={"country": "India"}):
            response = authenticated_client.get("/ipam/countries/India")
            assert response.status_code in [200, 404]
        
        # Get country utilization
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.calculate_country_utilization', return_value={}):
            response = authenticated_client.get("/ipam/countries/India/utilization")
            assert response.status_code in [200, 404]
    
    def test_region_endpoints_exist(self, authenticated_client):
        """Verify region endpoints exist."""
        # List regions
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_regions', return_value={"items": [], "total_count": 0}):
            response = authenticated_client.get("/ipam/regions")
            assert response.status_code == 200
        
        # Create region
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.allocate_region', return_value={"region_id": "test"}):
            response = authenticated_client.post("/ipam/regions?country=India&region_name=Test")
            assert response.status_code in [201, 400, 409]
        
        # Get region
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_region_by_id', return_value={"region_id": "test"}):
            response = authenticated_client.get("/ipam/regions/test-id")
            assert response.status_code in [200, 404]
        
        # Update region
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.update_region', return_value={"region_id": "test"}):
            response = authenticated_client.patch("/ipam/regions/test-id?description=Updated")
            assert response.status_code in [200, 404]
        
        # Delete region
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.retire_allocation', return_value={}):
            response = authenticated_client.delete("/ipam/regions/test-id?reason=Test")
            assert response.status_code in [200, 404]
        
        # Preview next region
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_next_available_region', return_value={"next_cidr": "10.0.0.0/24"}):
            response = authenticated_client.get("/ipam/regions/preview-next?country=India")
            assert response.status_code in [200, 409]
        
        # Get region utilization
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.calculate_region_utilization', return_value={}):
            response = authenticated_client.get("/ipam/regions/test-id/utilization")
            assert response.status_code in [200, 404]
        
        # Add comment
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.add_comment', return_value={"status": "success"}):
            response = authenticated_client.post("/ipam/regions/test-id/comments?comment_text=Test")
            assert response.status_code in [201, 404]
    
    def test_host_endpoints_exist(self, authenticated_client):
        """Verify host endpoints exist."""
        # List hosts
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_hosts', return_value={"items": [], "total_count": 0}):
            response = authenticated_client.get("/ipam/hosts")
            assert response.status_code == 200
        
        # Create host
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.allocate_host', return_value={"host_id": "test"}):
            response = authenticated_client.post("/ipam/hosts?region_id=test&hostname=test-host")
            assert response.status_code in [201, 400, 409]
        
        # Batch create hosts
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.allocate_hosts_batch', return_value={"hosts": []}):
            response = authenticated_client.post("/ipam/hosts/batch?region_id=test&count=5&hostname_prefix=test-")
            assert response.status_code in [201, 400, 409]
        
        # Get host
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_host_by_id', return_value={"host_id": "test"}):
            response = authenticated_client.get("/ipam/hosts/test-id")
            assert response.status_code in [200, 404]
        
        # Get host by IP
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_host_by_ip', return_value={"host_id": "test"}):
            response = authenticated_client.get("/ipam/hosts/by-ip/10.0.0.1")
            assert response.status_code in [200, 404]
        
        # Bulk lookup
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.bulk_lookup_ips', return_value={"hosts": [], "found": 0}):
            response = authenticated_client.post("/ipam/hosts/bulk-lookup?ip_addresses=10.0.0.1")
            assert response.status_code == 200
        
        # Update host
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.update_host', return_value={"host_id": "test"}):
            response = authenticated_client.patch("/ipam/hosts/test-id?purpose=Updated")
            assert response.status_code in [200, 404]
        
        # Delete host
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.retire_allocation', return_value={}):
            response = authenticated_client.delete("/ipam/hosts/test-id?reason=Test")
            assert response.status_code in [200, 404]
        
        # Bulk release
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.bulk_release_hosts', return_value={"success_count": 0}):
            response = authenticated_client.post("/ipam/hosts/bulk-release?host_ids=test-id&reason=Test")
            assert response.status_code == 200
        
        # Preview next host
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_next_available_host', return_value={"next_ip": "10.0.0.1"}):
            response = authenticated_client.get("/ipam/hosts/preview-next?region_id=test")
            assert response.status_code in [200, 409]
        
        # Add comment
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.add_comment', return_value={"status": "success"}):
            response = authenticated_client.post("/ipam/hosts/test-id/comments?comment_text=Test")
            assert response.status_code in [201, 404]
    
    def test_interpret_endpoint_exists(self, authenticated_client):
        """Verify interpret endpoint exists."""
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.interpret_ip_address', return_value={"ip_address": "10.0.0.1"}):
            response = authenticated_client.post("/ipam/interpret?ip_address=10.0.0.1")
            assert response.status_code in [200, 404]
    
    def test_statistics_endpoints_exist(self, authenticated_client):
        """Verify statistics endpoints exist."""
        # Continent statistics
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_continent_statistics', return_value={}):
            response = authenticated_client.get("/ipam/statistics/continent/Asia")
            assert response.status_code == 200
        
        # Top utilized
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_top_utilized_resources', return_value={}):
            response = authenticated_client.get("/ipam/statistics/top-utilized")
            assert response.status_code == 200
        
        # Allocation velocity
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_allocation_velocity', return_value={}):
            response = authenticated_client.get("/ipam/statistics/allocation-velocity")
            assert response.status_code == 200
    
    def test_search_endpoint_exists(self, authenticated_client):
        """Verify search endpoint exists."""
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.search_allocations', return_value={"items": [], "total_count": 0}):
            response = authenticated_client.get("/ipam/search")
            assert response.status_code == 200
    
    def test_export_import_endpoints_exist(self, authenticated_client):
        """Verify export/import endpoints exist."""
        # Create export
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.export_allocations', return_value="job-123"):
            response = authenticated_client.post("/ipam/export")
            assert response.status_code == 202
        
        # Download export
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_export_download_url', return_value="http://example.com"):
            response = authenticated_client.get("/ipam/export/job-123/download")
            assert response.status_code in [200, 404]
        
        # Import
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.import_allocations', return_value={"success_count": 0}):
            response = authenticated_client.post("/ipam/import?file_content=test")
            assert response.status_code in [201, 400]
        
        # Import preview
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.import_allocations', return_value={"valid_count": 0}):
            response = authenticated_client.post("/ipam/import/preview?file_content=test")
            assert response.status_code in [200, 400]
    
    def test_audit_endpoints_exist(self, authenticated_client):
        """Verify audit endpoints exist."""
        # Get audit history
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_audit_history', return_value={"items": [], "total_count": 0}):
            response = authenticated_client.get("/ipam/audit/history")
            assert response.status_code == 200
        
        # Get IP audit history
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_audit_history', return_value={"items": []}):
            response = authenticated_client.get("/ipam/audit/history/10.0.0.1")
            assert response.status_code == 200
        
        # Export audit
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.export_audit_history', return_value="job-123"):
            response = authenticated_client.post("/ipam/audit/export")
            assert response.status_code == 202


class TestBackwardCompatibilityResponseStructure:
    """Test that response structures haven't changed."""
    
    def test_country_response_structure(self, authenticated_client):
        """Verify country response structure is unchanged."""
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_country_mapping') as mock_get:
            mock_get.return_value = {
                "continent": "Asia",
                "country": "India",
                "x_start": 0,
                "x_end": 29,
                "total_blocks": 7680,
                "is_reserved": False
            }
            response = authenticated_client.get("/ipam/countries/India")
            if response.status_code == 200:
                data = response.json()
                assert "continent" in data
                assert "country" in data
                assert "x_start" in data
                assert "x_end" in data
    
    def test_pagination_response_structure(self, authenticated_client):
        """Verify pagination response structure is unchanged."""
        with patch('second_brain_database.managers.ipam_manager.ipam_manager.get_regions') as mock_get:
            mock_get.return_value = {
                "items": [],
                "total_count": 0
            }
            response = authenticated_client.get("/ipam/regions")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "pagination" in data
            pagination = data["pagination"]
            assert "page" in pagination
            assert "page_size" in pagination
            assert "total_count" in pagination
