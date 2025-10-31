#!/usr/bin/env python3
"""
Emergency cleanup script for stuck AI sessions
"""

import requests
import json

def cleanup_sessions():
    """Clean up stuck AI sessions"""
    
    print("🧹 AI Session Cleanup Script")
    print("=" * 50)
    
    # Login first
    print("1️⃣ Logging in...")
    login_response = requests.post(
        "https://dev-app-sbd.rohanbatra.in/auth/login",
        json={"username": "rohan", "password": "Letters,123"},
        timeout=10
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        return False
    
    access_token = login_response.json().get("access_token")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print("✅ Login successful")
    
    # Get current sessions
    print("\n2️⃣ Getting current sessions...")
    try:
        sessions_response = requests.get(
            "https://dev-app-sbd.rohanbatra.in/ai/sessions",
            headers=headers,
            timeout=10
        )
        
        if sessions_response.status_code == 200:
            sessions = sessions_response.json()
            print(f"📊 Found {len(sessions)} active sessions")
            
            # Try to delete each session
            print("\n3️⃣ Cleaning up sessions...")
            for i, session in enumerate(sessions, 1):
                session_id = session.get("session_id")
                if session_id:
                    print(f"   Deleting session {i}: {session_id}")
                    
                    # Try direct database cleanup via admin endpoint
                    cleanup_response = requests.delete(
                        f"https://dev-app-sbd.rohanbatra.in/ai/sessions/{session_id}/force-delete",
                        headers=headers,
                        timeout=10
                    )
                    
                    if cleanup_response.status_code in [200, 204, 404]:
                        print(f"   ✅ Session {session_id} cleaned up")
                    else:
                        print(f"   ⚠️ Session {session_id} cleanup status: {cleanup_response.status_code}")
            
            return True
            
        else:
            print(f"❌ Failed to get sessions: {sessions_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        return False

def test_session_creation():
    """Test if session creation works after cleanup"""
    
    print("\n4️⃣ Testing session creation...")
    
    # Login
    login_response = requests.post(
        "https://dev-app-sbd.rohanbatra.in/auth/login",
        json={"username": "rohan", "password": "password123"},
        timeout=10
    )
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        return False
    
    access_token = login_response.json().get("access_token")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Try creating a session
    session_response = requests.post(
        "https://dev-app-sbd.rohanbatra.in/ai/sessions",
        json={"agent_type": "personal", "voice_enabled": False},
        headers=headers,
        timeout=10
    )
    
    if session_response.status_code == 201:
        session_data = session_response.json()
        session_id = session_data.get("session_id")
        print(f"✅ New session created successfully: {session_id}")
        
        # Clean up the test session
        requests.delete(
            f"https://dev-app-sbd.rohanbatra.in/ai/sessions/{session_id}",
            headers=headers,
            timeout=10
        )
        
        return True
    else:
        print(f"❌ Session creation still failing: {session_response.status_code}")
        if session_response.status_code == 403:
            error_data = session_response.json()
            print(f"   Error: {error_data}")
        return False

if __name__ == "__main__":
    print("🚨 Emergency AI Session Cleanup")
    print("This script will clean up stuck sessions that are preventing new session creation")
    print()
    
    success = cleanup_sessions()
    
    if success:
        # Test if cleanup worked
        if test_session_creation():
            print("\n🎉 SUCCESS!")
            print("✅ Sessions cleaned up successfully")
            print("✅ New session creation working")
            print("✅ You can now test the Flutter AI integration")
        else:
            print("\n⚠️ PARTIAL SUCCESS")
            print("✅ Cleanup completed")
            print("❌ Session creation still has issues")
            print("💡 The datetime fix may need a server restart")
    else:
        print("\n❌ CLEANUP FAILED")
        print("💡 Try manual database cleanup or server restart")
    
    print("\n" + "=" * 50)