#!/usr/bin/env python3
"""Quick test for OAuth2 authorization endpoint."""

import sys
sys.path.append('.')

from fastapi.testclient import TestClient
from src.second_brain_database.main import app

def test_oauth2_health():
    """Test OAuth2 health endpoint."""
    client = TestClient(app)
    response = client.get("/oauth2/health")
    print(f"Health endpoint status: {response.status_code}")
    if response.status_code == 200:
        print("Health endpoint test passed!")
        print(f"Response: {response.json()}")
    else:
        print(f"Health endpoint test failed: {response.text}")

def test_oauth2_authorize_no_auth():
    """Test OAuth2 authorize endpoint without authentication."""
    client = TestClient(app)
    response = client.get("/oauth2/authorize")
    print(f"Authorize endpoint status (no params): {response.status_code}")
    
    # Test with some parameters but no auth
    params = {
        "response_type": "code",
        "client_id": "test_client",
        "redirect_uri": "https://example.com/callback",
        "scope": "read:profile",
        "state": "test_state",
        "code_challenge": "test_challenge_123456789012345678901234567890123",
        "code_challenge_method": "S256"
    }
    response = client.get("/oauth2/authorize", params=params)
    print(f"Authorize endpoint status (with params, no auth): {response.status_code}")
    if response.status_code == 401:
        print("Authorization endpoint correctly requires authentication!")
    else:
        print(f"Unexpected response: {response.text}")

if __name__ == "__main__":
    print("Testing OAuth2 endpoints...")
    test_oauth2_health()
    print()
    test_oauth2_authorize_no_auth()