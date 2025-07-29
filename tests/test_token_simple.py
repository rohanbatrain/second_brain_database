#!/usr/bin/env python3

from fastapi.testclient import TestClient
from second_brain_database.main import app

def test_token_endpoint():
    client = TestClient(app)
    
    # Test basic token endpoint accessibility
    response = client.post('/oauth2/token', data={
        'grant_type': 'authorization_code',
        'client_id': 'test'
    })
    
    print(f'Status: {response.status_code}')
    print(f'Response: {response.json()}')
    
    # Test with missing grant_type
    response = client.post('/oauth2/token', data={
        'client_id': 'test'
    })
    
    print(f'Status (missing grant_type): {response.status_code}')
    if response.status_code != 200:
        print(f'Response: {response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text}')

if __name__ == "__main__":
    test_token_endpoint()