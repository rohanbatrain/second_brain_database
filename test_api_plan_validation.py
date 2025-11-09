#!/usr/bin/env python3
"""
Test plan validation via API calls to ensure endpoint security.
"""

import asyncio
import json
import httpx


async def test_api_plan_validation():
    """Test plan validation through the actual API endpoint."""
    base_url = "http://localhost:8000"
    
    print("🌐 Testing Plan Validation via API Endpoints")
    print("=" * 55)
    
    async with httpx.AsyncClient() as client:
        # Test 1: Valid free plan registration (should work)
        print("\n1️⃣ Testing valid free plan registration...")
        try:
            response = await client.post(f"{base_url}/auth/register", json={
                "username": "freeuser",
                "email": "free@example.com",
                "password": "FreePass123!",
                "plan": "free"
            })
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Free plan registration successful: {data.get('access_token', 'No token')[:20]}...")
            else:
                print(f"❌ Free plan registration failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"⚠️ Connection error: {e}")
        
        # Test 2: Invalid premium plan registration (should fail)
        print("\n2️⃣ Testing premium plan bypass attempt...")
        try:
            response = await client.post(f"{base_url}/auth/register", json={
                "username": "premiumhacker",
                "email": "premium@example.com", 
                "password": "PremiumPass123!",
                "plan": "premium"
            })
            if response.status_code == 422:  # Validation error
                print("✅ Premium plan correctly blocked by validation")
            elif response.status_code == 400:
                print("✅ Premium plan blocked by business logic")
            elif response.status_code == 200:
                print("❌ SECURITY VULNERABILITY: Premium plan registration allowed!")
            else:
                print(f"⚠️ Unexpected response: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"⚠️ Connection error: {e}")
        
        # Test 3: Invalid enterprise plan registration (should fail)
        print("\n3️⃣ Testing enterprise plan bypass attempt...")
        try:
            response = await client.post(f"{base_url}/auth/register", json={
                "username": "enterprisehacker",
                "email": "enterprise@example.com",
                "password": "EnterprisePass123!",
                "plan": "enterprise"
            })
            if response.status_code == 422:  # Validation error
                print("✅ Enterprise plan correctly blocked by validation")
            elif response.status_code == 400:
                print("✅ Enterprise plan blocked by business logic")
            elif response.status_code == 200:
                print("❌ SECURITY VULNERABILITY: Enterprise plan registration allowed!")
            else:
                print(f"⚠️ Unexpected response: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"⚠️ Connection error: {e}")
        
        # Test 4: Default plan (no plan specified) - should default to free
        print("\n4️⃣ Testing default plan behavior...")
        try:
            response = await client.post(f"{base_url}/auth/register", json={
                "username": "defaultuser",
                "email": "default@example.com",
                "password": "DefaultPass123!"
                # No plan specified - should default to free
            })
            if response.status_code == 200:
                print("✅ Default plan registration successful (defaults to free)")
            else:
                print(f"❌ Default plan registration failed: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"⚠️ Connection error: {e}")
    
    print("\n" + "=" * 55)
    print("🔒 API plan validation test complete!")
    print("✅ Signup endpoint should only allow 'free' plan registrations")


if __name__ == "__main__":
    asyncio.run(test_api_plan_validation())