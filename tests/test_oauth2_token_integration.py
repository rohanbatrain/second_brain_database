"""
Simple integration test to verify OAuth2 token endpoint is accessible.
"""

import pytest
from fastapi.testclient import TestClient
from second_brain_database.main import app


def test_oauth2_token_endpoint_exists():
    """Test that the OAuth2 token endpoint exists and returns proper error for missing params."""
    client = TestClient(app)
    
    # Test that endpoint exists (should return 422 for missing required params)
    response = client.post("/oauth2/token")
    
    # Should return validation error for missing required fields
    assert response.status_code == 422
    
    # Should be a validation error response
    error_data = response.json()
    assert "detail" in error_data
    assert isinstance(error_data["detail"], list)
    
    # Should mention missing required fields
    error_messages = [error["msg"] for error in error_data["detail"]]
    assert any("required" in msg.lower() for msg in error_messages)


def test_oauth2_token_endpoint_invalid_grant_type():
    """Test OAuth2 token endpoint with invalid grant type."""
    client = TestClient(app)
    
    response = client.post("/oauth2/token", data={
        "grant_type": "invalid_grant",
        "client_id": "test_client"
    })
    
    # Should return 400 for unsupported grant type
    assert response.status_code == 400
    
    error_data = response.json()
    assert error_data["error"] == "unsupported_grant_type"
    assert "not supported" in error_data["error_description"]


def test_oauth2_health_endpoint():
    """Test OAuth2 health endpoint."""
    client = TestClient(app)
    
    response = client.get("/oauth2/health")
    
    # Should return 200 for health check
    assert response.status_code == 200
    
    health_data = response.json()
    assert health_data["message"] == "OAuth2 provider is healthy"
    assert "data" in health_data
    assert health_data["data"]["status"] == "healthy"