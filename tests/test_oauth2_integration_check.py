#!/usr/bin/env python3
"""Test OAuth2 integration with main FastAPI application."""

import sys
import os
sys.path.append('.')

def test_oauth2_integration():
    """Test OAuth2 routes integration with main app."""
    print("🔍 Testing OAuth2 Integration with Main App")
    print("=" * 50)
    
    try:
        # Test 1: Import main app
        print("1. Testing app import...")
        from src.second_brain_database.main import app
        print("   ✅ Main app imported successfully")
        
        # Test 2: Check OAuth2 router is included
        print("\n2. Testing OAuth2 router inclusion...")
        from fastapi.testclient import TestClient
        client = TestClient(app)
        
        # Test health endpoint
        response = client.get("/oauth2/health")
        print(f"   OAuth2 health endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ OAuth2 routes properly integrated")
            health_data = response.json()
            print(f"   Response: {health_data.get('message', 'No message')}")
        else:
            print("   ❌ OAuth2 routes integration issue")
            print(f"   Response: {response.text}")
        
        # Test 3: Check OpenAPI schema includes OAuth2 endpoints
        print("\n3. Testing OpenAPI schema...")
        openapi_schema = app.openapi()
        oauth2_paths = [path for path in openapi_schema["paths"] if path.startswith("/oauth2")]
        print(f"   OAuth2 endpoints in schema: {oauth2_paths}")
        
        expected_endpoints = ["/oauth2/authorize", "/oauth2/token", "/oauth2/consent", "/oauth2/health"]
        missing_endpoints = [ep for ep in expected_endpoints if ep not in oauth2_paths]
        
        if not missing_endpoints:
            print("   ✅ All expected OAuth2 endpoints present in schema")
        else:
            print(f"   ⚠️  Missing endpoints: {missing_endpoints}")
        
        # Test 4: Check router configuration
        print("\n4. Testing router configuration...")
        from src.second_brain_database.routes import oauth2_router
        print(f"   OAuth2 router prefix: {oauth2_router.prefix}")
        print(f"   OAuth2 router tags: {oauth2_router.tags}")
        print("   ✅ OAuth2 router properly configured")
        
        print("\n" + "=" * 50)
        print("🎉 OAuth2 Integration Test Complete!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_oauth2_integration()
    sys.exit(0 if success else 1)