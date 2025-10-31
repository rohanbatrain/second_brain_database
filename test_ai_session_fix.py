#!/usr/bin/env python3
"""
Test script to verify AI session creation fix
"""

import requests
import json

def test_ai_session_creation():
    """Test AI session creation endpoint"""
    
    # First, login to get auth token
    login_url = "https://dev-app-sbd.rohanbatra.in/auth/login"
    login_data = {
        "username": "rohan",
        "password": "Letters,123"
    }
    
    print("🔐 Logging in...")
    login_response = requests.post(login_url, json=login_data)
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(f"Response: {login_response.text}")
        return False
    
    auth_data = login_response.json()
    access_token = auth_data.get("access_token")
    
    if not access_token:
        print("❌ No access token received")
        return False
    
    print("✅ Login successful")
    
    # Now test AI session creation
    session_url = "https://dev-app-sbd.rohanbatra.in/ai/sessions"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    session_data = {
        "agent_type": "family",
        "voice_enabled": False
    }
    
    print("🤖 Creating AI session...")
    session_response = requests.post(session_url, json=session_data, headers=headers)
    
    print(f"Status Code: {session_response.status_code}")
    print(f"Response: {session_response.text}")
    
    if session_response.status_code == 200:
        print("✅ AI session creation successful!")
        session_info = session_response.json()
        print(f"Session ID: {session_info.get('session_id')}")
        print(f"Agent Type: {session_info.get('agent_type')}")
        return True
    else:
        print(f"❌ AI session creation failed: {session_response.status_code}")
        return False

if __name__ == "__main__":
    print("Testing AI Session Creation Fix...")
    print("=" * 50)
    
    success = test_ai_session_creation()
    
    print("=" * 50)
    if success:
        print("🎉 Test PASSED - AI session creation is working!")
    else:
        print("💥 Test FAILED - AI session creation still has issues")