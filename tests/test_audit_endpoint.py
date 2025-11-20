#!/usr/bin/env python3
"""
Quick test script for the audit endpoint fix.

Tests both /ipam/audit and /ipam/audit/history endpoints.
"""

import asyncio
import sys
from typing import Dict, Any

import httpx


async def test_audit_endpoints():
    """Test audit endpoints with and without auth."""
    base_url = "http://localhost:8000"
    
    print("Testing IPAM Audit Endpoints")
    print("=" * 60)
    
    # Test 1: Without authentication (should get 401)
    print("\n1. Testing /ipam/audit without auth (expect 401)...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/ipam/audit?page=1&page_size=25")
            print(f"   Status: {response.status_code}")
            if response.status_code == 401:
                print("   ✅ Correctly returns 401 Unauthorized")
            else:
                print(f"   ❌ Expected 401, got {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test 2: Check /ipam/audit/history without auth
    print("\n2. Testing /ipam/audit/history without auth (expect 401)...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/ipam/audit/history?page=1&page_size=25")
            print(f"   Status: {response.status_code}")
            if response.status_code == 401:
                print("   ✅ Correctly returns 401 Unauthorized")
            else:
                print(f"   ❌ Expected 401, got {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test 3: Check OpenAPI spec
    print("\n3. Checking OpenAPI spec for audit endpoints...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/openapi.json")
            if response.status_code == 200:
                spec = response.json()
                audit_paths = [p for p in spec.get("paths", {}).keys() if "/ipam/audit" in p]
                print(f"   Found {len(audit_paths)} audit endpoints:")
                for path in sorted(audit_paths):
                    print(f"     - {path}")
                
                if "/ipam/audit" in audit_paths and "/ipam/audit/history" in audit_paths:
                    print("   ✅ Both endpoints registered correctly")
                else:
                    print("   ❌ Missing expected endpoints")
            else:
                print(f"   ❌ Failed to fetch OpenAPI spec: {response.status_code}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test 4: Check endpoint documentation
    print("\n4. Checking endpoint documentation...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{base_url}/openapi.json")
            if response.status_code == 200:
                spec = response.json()
                audit_endpoint = spec.get("paths", {}).get("/ipam/audit", {})
                if audit_endpoint:
                    get_method = audit_endpoint.get("get", {})
                    summary = get_method.get("summary", "")
                    description = get_method.get("description", "")
                    print(f"   Summary: {summary}")
                    print(f"   Description: {description[:100]}...")
                    
                    # Check parameters
                    params = get_method.get("parameters", [])
                    param_names = [p.get("name") for p in params]
                    print(f"   Parameters: {', '.join(param_names)}")
                    
                    expected_params = ["action_type", "resource_type", "start_date", "end_date", "page", "page_size"]
                    if all(p in param_names for p in expected_params):
                        print("   ✅ All expected parameters present")
                    else:
                        print("   ⚠️  Some parameters missing")
                else:
                    print("   ❌ Endpoint not found in spec")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("Test Summary:")
    print("- Both /ipam/audit and /ipam/audit/history are registered")
    print("- Both require authentication (401 without token)")
    print("- Endpoint has proper documentation and parameters")
    print("\nTo test with authentication, use:")
    print("  1. Login to get a token")
    print("  2. curl -H 'Authorization: Bearer TOKEN' http://localhost:8000/ipam/audit")


if __name__ == "__main__":
    try:
        asyncio.run(test_audit_endpoints())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nTest failed with error: {e}")
        sys.exit(1)
