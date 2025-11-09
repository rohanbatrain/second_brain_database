#!/usr/bin/env python3
"""
Direct test of token with RAG endpoint.
"""

import requests
from pathlib import Path

# Load token
token_file = Path("rag_token.txt")
if not token_file.exists():
    print("❌ rag_token.txt not found")
    exit(1)

token = token_file.read_text().strip()
print(f"Token loaded: {token[:50]}...")
print()

# Test 1: Health check (no auth)
print("Test 1: Health Check (no auth required)")
print("-" * 50)
try:
    response = requests.get("http://localhost:8000/rag/health", timeout=5)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print("✅ Health check passed")
except Exception as e:
    print(f"❌ Health check failed: {e}")
print()

# Test 2: Status check with Authorization header
print("Test 2: Status Check (with Authorization header)")
print("-" * 50)
try:
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://localhost:8000/rag/status", headers=headers, timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print(f"Response: {response.json()}")
        print("✅ Authentication successful!")
    else:
        print(f"Response: {response.text}")
        print(f"❌ Authentication failed with {response.status_code}")
except Exception as e:
    print(f"❌ Request failed: {e}")
    import traceback
    traceback.print_exc()
print()

# Test 3: Status check with token as query parameter (OAuth2 fallback)
print("Test 3: Status Check (with token as query param)")
print("-" * 50)
try:
    response = requests.get(f"http://localhost:8000/rag/status?token={token}", timeout=10)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print(f"Response: {response.json()}")
        print("✅ Query param authentication successful!")
    else:
        print(f"Response: {response.text[:300]}")
except Exception as e:
    print(f"❌ Request failed: {e}")
print()

# Test 4: Check OpenAPI docs
print("Test 4: Check OpenAPI Schema")
print("-" * 50)
try:
    response = requests.get("http://localhost:8000/openapi.json", timeout=5)
    if response.status_code == 200:
        schema = response.json()
        # Check if /rag/status endpoint exists
        paths = schema.get("paths", {})
        if "/rag/status" in paths:
            endpoint_info = paths["/rag/status"]
            print(f"✅ /rag/status endpoint found in OpenAPI schema")
            print(f"Methods: {list(endpoint_info.keys())}")
            
            # Check security requirements
            get_info = endpoint_info.get("get", {})
            security = get_info.get("security", [])
            print(f"Security: {security}")
        else:
            print(f"❌ /rag/status not found in OpenAPI schema")
            print(f"Available RAG endpoints:")
            for path in paths.keys():
                if "/rag" in path:
                    print(f"  - {path}")
except Exception as e:
    print(f"❌ Failed to fetch OpenAPI schema: {e}")
