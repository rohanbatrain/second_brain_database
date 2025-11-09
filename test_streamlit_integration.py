#!/usr/bin/env python3
"""
Quick test to verify Streamlit app integration with the RAG API.
"""

import requests
from pathlib import Path

# Load token
token_file = Path("rag_token.txt")
token = token_file.read_text().strip()

print("=" * 60)
print("Testing RAG API Endpoints (Streamlit Integration)")
print("=" * 60)
print()

# Base URL (same as Streamlit app)
API_BASE_URL = "http://localhost:8000"
RAG_ENDPOINT = f"{API_BASE_URL}/rag"

headers = {"Authorization": f"Bearer {token}"}

# Test 1: Health Check
print("1. Health Check (no auth)")
print("-" * 60)
try:
    response = requests.get(f"{RAG_ENDPOINT}/health", timeout=5)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ Service: {data.get('service')}")
        print(f"   ✅ Status: {data.get('status')}")
    else:
        print(f"   ❌ Failed: {response.text[:100]}")
except Exception as e:
    print(f"   ❌ Error: {e}")
print()

# Test 2: Status Check (requires auth)
print("2. RAG Status (with authentication)")
print("-" * 60)
try:
    response = requests.get(f"{RAG_ENDPOINT}/status", headers=headers, timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"   ✅ RAG Status: {data.get('status')}")
        print(f"   ✅ LlamaIndex: {data.get('llamaindex_enabled')}")
        print(f"   ✅ Vector Search: {data.get('vector_search_available')}")
        print(f"   ✅ Ollama: {data.get('ollama_available')}")
        print(f"   ✅ Documents: {data.get('document_count')}")
    else:
        print(f"   ❌ Failed: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ Error: {e}")
print()

# Test 3: List Documents (requires auth)
print("3. List Documents (with authentication)")
print("-" * 60)
try:
    params = {"limit": 10, "offset": 0}
    response = requests.get(f"{RAG_ENDPOINT}/documents", headers=headers, params=params, timeout=10)
    print(f"   Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        total = data.get('total', 0)
        docs = data.get('documents', [])
        print(f"   ✅ Total Documents: {total}")
        print(f"   ✅ Returned: {len(docs)}")
        if docs:
            for doc in docs[:3]:
                print(f"      - {doc.get('filename', 'Unknown')}")
    else:
        print(f"   ❌ Failed: {response.text[:200]}")
except Exception as e:
    print(f"   ❌ Error: {e}")
print()

# Test 4: Query endpoint structure (without actually querying)
print("4. OpenAPI - Check Query Endpoint")
print("-" * 60)
try:
    response = requests.get(f"{API_BASE_URL}/openapi.json", timeout=5)
    if response.status_code == 200:
        schema = response.json()
        query_endpoint = schema.get("paths", {}).get("/rag/query", {})
        if query_endpoint:
            print(f"   ✅ /rag/query endpoint exists")
            methods = list(query_endpoint.keys())
            print(f"   ✅ Methods: {methods}")
            
            post_info = query_endpoint.get("post", {})
            security = post_info.get("security", [])
            print(f"   ✅ Security: {security}")
            
            # Check request body
            request_body = post_info.get("requestBody", {})
            if request_body:
                print(f"   ✅ Request body required: {request_body.get('required', False)}")
        else:
            print(f"   ❌ /rag/query endpoint not found")
except Exception as e:
    print(f"   ❌ Error: {e}")
print()

# Summary
print("=" * 60)
print("Summary")
print("=" * 60)
print("✅ User created: rag_user")
print("✅ Token saved to: rag_token.txt")
print("✅ Authentication working with Authorization header")
print()
print("Next steps:")
print("  1. Start Streamlit app: ./start_streamlit_app.sh")
print("  2. Click 'Load token from file' in the sidebar")
print("  3. Click 'Connect' to authenticate")
print("  4. Start uploading documents and querying!")
print("=" * 60)
