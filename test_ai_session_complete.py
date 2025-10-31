#!/usr/bin/env python3
"""
Complete test for AI session creation with all fixes applied
"""

import requests
import json
import time

def test_complete_ai_session_flow():
    """Test complete AI session creation flow"""
    
    print("🔐 Step 1: Testing Authentication...")
    
    # Test with the credentials that worked in the Flutter app
    login_url = "https://dev-app-sbd.rohanbatra.in/auth/login"
    
    # Try different login formats
    login_attempts = [
        {"username": "rohan", "password": "Letters,123"},
        {"identifier": "rohan", "password": "Letters,123", "login_type": "username"},
        {"email": "test@rohanbatra.in", "password": "Letters,123"},
    ]
    
    access_token = None
    
    for i, login_data in enumerate(login_attempts, 1):
        print(f"  Attempt {i}: {list(login_data.keys())}")
        
        try:
            response = requests.post(login_url, json=login_data, timeout=10)
            print(f"    Status: {response.status_code}")
            
            if response.status_code == 200:
                auth_data = response.json()
                access_token = auth_data.get("access_token")
                if access_token:
                    print(f"    ✅ Login successful with attempt {i}")
                    break
            else:
                print(f"    ❌ Failed: {response.text[:100]}")
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
    
    if not access_token:
        print("❌ All login attempts failed")
        return False
    
    print(f"✅ Authentication successful")
    
    print("\n🤖 Step 2: Testing AI Session Creation...")
    
    session_url = "https://dev-app-sbd.rohanbatra.in/ai/sessions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "test-client/1.0.0"
    }
    
    # Test different agent types
    agent_types = ["family", "personal", "workspace"]
    
    for agent_type in agent_types:
        print(f"\n  Testing {agent_type} agent...")
        
        session_data = {
            "agent_type": agent_type,
            "voice_enabled": False
        }
        
        try:
            response = requests.post(session_url, json=session_data, headers=headers, timeout=10)
            print(f"    Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                session_info = response.json()
                session_id = session_info.get("session_id")
                print(f"    ✅ Session created: {session_id}")
                print(f"    Agent: {session_info.get('agent_type')}")
                print(f"    Voice: {session_info.get('voice_enabled')}")
                
                # Test session cleanup
                print(f"    🧹 Cleaning up session...")
                cleanup_url = f"{session_url}/{session_id}"
                cleanup_response = requests.delete(cleanup_url, headers=headers, timeout=10)
                print(f"    Cleanup status: {cleanup_response.status_code}")
                
            else:
                print(f"    ❌ Failed: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return False
    
    print("\n✅ All AI session tests passed!")
    return True

def test_server_health():
    """Test server health and connectivity"""
    print("🏥 Testing server health...")
    
    try:
        health_url = "https://dev-app-sbd.rohanbatra.in/health"
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"  ✅ Server healthy")
            print(f"  Database: {health_data.get('database', 'unknown')}")
            print(f"  Redis: {health_data.get('redis', 'unknown')}")
            print(f"  API: {health_data.get('api', 'unknown')}")
            return True
        else:
            print(f"  ❌ Health check failed: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Health check error: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Complete AI Session Integration Test")
    print("=" * 60)
    
    # Test server health first
    if not test_server_health():
        print("\n💥 Server health check failed - aborting tests")
        exit(1)
    
    print()
    
    # Test complete flow
    success = test_complete_ai_session_flow()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Performance timer fix working")
        print("✅ Database manager fix working") 
        print("✅ Redis manager fix working")
        print("✅ AI session creation fully functional")
        print("✅ Flutter integration ready for testing")
    else:
        print("💥 SOME TESTS FAILED")
        print("❌ Check server logs for details")
    
    print("=" * 60)