#!/usr/bin/env python3
"""
Quick WebRTC Manual Test

A simple manual test to check if WebRTC endpoints are accessible
and JWT authentication is working.
"""

import asyncio
import json
import sys

import httpx

# Add src to path
sys.path.insert(0, "src")

from second_brain_database.config import settings

BASE_URL = f"http://localhost:{settings.PORT}"


async def test_basic_webrtc():
    """Test basic WebRTC functionality."""
    print("🔧 Quick WebRTC Manual Test")
    print("=" * 30)
    
    async with httpx.AsyncClient() as client:
        # Test 1: Check server health
        print("\n1️⃣ Testing server health...")
        try:
            health_response = await client.get(f"{BASE_URL}/health")
            if health_response.status_code == 200:
                print(f"   ✅ Server is healthy: {health_response.json()}")
            else:
                print(f"   ❌ Server health check failed: {health_response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Cannot connect to server: {e}")
            return False
        
        # Test 2: Try to get WebRTC config without auth (should fail)
        print("\n2️⃣ Testing WebRTC config without auth (should fail)...")
        try:
            config_response = await client.get(f"{BASE_URL}/webrtc/config")
            if config_response.status_code == 401:
                print("   ✅ Correctly rejected unauthenticated request")
            else:
                print(f"   ⚠️  Unexpected response: {config_response.status_code}")
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
        
        # Test 3: Create a test user and get token
        print("\n3️⃣ Creating test user and getting JWT token...")
        import time
        timestamp = int(time.time())
        test_user = {
            "username": f"manual_test_user_{timestamp}",
            "email": f"manual_{timestamp}@example.com",
            "password": "TestPass123!"
        }
        
        # Register user
        register_response = await client.post(
            f"{BASE_URL}/auth/register",
            json={
                "username": test_user["username"],
                "email": test_user["email"],
                "password": test_user["password"]
            }
        )
        print(f"   Registration: {register_response.status_code}")
        
        if register_response.status_code == 200:
            # Registration successful, get token from response
            token_data = register_response.json()
            token = token_data["access_token"]
            print(f"   ✅ Got JWT token from registration: {token[:20]}...")
        else:
            print(f"   ❌ Registration failed: {register_response.text}")
            return False
        
        # Test 4: Get WebRTC config with auth
        print("\n4️⃣ Testing WebRTC config with authentication...")
        config_response = await client.get(
            f"{BASE_URL}/webrtc/config",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if config_response.status_code == 200:
            config = config_response.json()
            ice_servers = config.get("ice_servers", [])
            print(f"   ✅ Got WebRTC config with {len(ice_servers)} ICE servers")
            for i, server in enumerate(ice_servers):
                print(f"      Server {i+1}: {server.get('urls', [])}")
        else:
            print(f"   ❌ WebRTC config failed: {config_response.status_code}")
            return False
        
        # Test 5: Check room participants endpoint
        print("\n5️⃣ Testing room participants endpoint...")
        participants_response = await client.get(
            f"{BASE_URL}/webrtc/rooms/test-room/participants",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if participants_response.status_code == 200:
            participants_data = participants_response.json()
            participant_count = participants_data.get("participant_count", 0)
            print(f"   ✅ Room participants: {participant_count}")
        else:
            print(f"   ❌ Room participants failed: {participants_response.status_code}")
            return False
        
        print("\n🎉 All basic tests passed!")
        print("✅ WebRTC endpoints are accessible")
        print("✅ JWT authentication is working")
        print("✅ WebRTC configuration is available")
        
        return True


async def main():
    """Main test execution."""
    try:
        success = await test_basic_webrtc()
        return 0 if success else 1
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)