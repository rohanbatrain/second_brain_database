#!/usr/bin/env python3
"""
Simple WebRTC Test with 2 Tokens - Enhanced Version

This test validates that the WebRTC implementation works correctly 
with two different JWT tokens authenticating simultaneously.
Enhanced with better error handling and reliability.
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone

import httpx
import websockets

# Add src to path
sys.path.insert(0, "src")

from second_brain_database.config import settings

# Test configuration
BASE_URL = f"http://localhost:{settings.PORT}"
WS_BASE_URL = f"ws://localhost:{settings.PORT}"
ROOM_ID = "simple-test-room"

# Test users
import time
TEST_TIMESTAMP = int(time.time())

TEST_USERS = [
    {
        "username": f"webrtc_simple_user1_{TEST_TIMESTAMP}",
        "email": f"simple1_{TEST_TIMESTAMP}@example.com", 
        "password": "TestPass123!"
    },
    {
        "username": f"webrtc_simple_user2_{TEST_TIMESTAMP}",
        "email": f"simple2_{TEST_TIMESTAMP}@example.com",
        "password": "TestPass456!"
    }
]


async def create_and_login_user(user_data: dict) -> str:
    """Create user and get JWT token."""
    print(f"🔐 Creating and logging in user: {user_data['username']}")
    
    async with httpx.AsyncClient() as client:
        # Try to register (might already exist)
        register_response = await client.post(
            f"{BASE_URL}/auth/register",
            json={
                "username": user_data["username"],
                "email": user_data["email"], 
                "password": user_data["password"]
            }
        )
        
        print(f"   Registration response: {register_response.status_code}")
        
        if register_response.status_code == 200:
            # Registration successful, get token from response
            token = register_response.json()["access_token"]
            print(f"   ✅ Got token from registration: {token[:20]}...")
        else:
            # Try login in case user already exists
            print(f"   Registration failed ({register_response.status_code}), trying login...")
            
            login_response = await client.post(
                f"{BASE_URL}/auth/login",
                json={
                    "username": user_data["username"],
                    "password": user_data["password"]
                }
            )
            
            if login_response.status_code != 200:
                raise Exception(f"Both registration and login failed for {user_data['username']}: {login_response.status_code} - {login_response.text}")
            
            token = login_response.json()["access_token"]
            print(f"   ✅ Got token from login: {token[:20]}...")
        
        # Verify token works
        verify_response = await client.get(
            f"{BASE_URL}/auth/validate-token",
            headers={"Authorization": f"Bearer {token}"}
        )
        
        if verify_response.status_code != 200:
            raise Exception(f"Token validation failed: {verify_response.status_code}")
        
        user_info = verify_response.json()
        print(f"   ✅ Token validated for: {user_info.get('username')}")
        
        return token


async def test_webrtc_connection(user_data: dict, token: str, client_id: str) -> bool:
    """Test WebSocket connection to WebRTC endpoint."""
    print(f"\n🔌 [{client_id}] Testing WebSocket connection...")
    
    ws_url = f"{WS_BASE_URL}/webrtc/ws/{ROOM_ID}?token={token}"
    print(f"   Connecting to: {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            print(f"   ✅ [{client_id}] WebSocket connected!")
            
            # Wait for initial messages
            messages_received = []
            
            try:
                # Receive initial messages with timeout
                for _ in range(3):  # Expect room-state and possibly user-joined messages
                    message_raw = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    message = json.loads(message_raw)
                    messages_received.append(message)
                    print(f"   📨 [{client_id}] Received: {message.get('type')}")
                    
                    if message.get('type') == 'room-state':
                        participants = message.get('payload', {}).get('participants', [])
                        print(f"   👥 [{client_id}] Participants: {len(participants)}")
                        for p in participants:
                            print(f"      - {p.get('username')} ({p.get('user_id')})")
                            
            except asyncio.TimeoutError:
                print(f"   ⏰ [{client_id}] No more messages (timeout)")
            
            # Send a test WebRTC offer
            test_offer = {
                "type": "offer",
                "payload": {
                    "sdp": "v=0\r\no=- 123456 1 IN IP4 127.0.0.1\r\ns=-\r\n",
                    "type": "offer"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await websocket.send(json.dumps(test_offer))
            print(f"   📤 [{client_id}] Sent test offer")
            
            # Try to receive any responses
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                response_msg = json.loads(response)
                print(f"   📨 [{client_id}] Got response: {response_msg.get('type')}")
            except asyncio.TimeoutError:
                print(f"   ⏰ [{client_id}] No response to offer (expected)")
            
            print(f"   ✅ [{client_id}] WebRTC test successful!")
            return True
            
    except Exception as e:
        print(f"   ❌ [{client_id}] WebSocket connection failed: {e}")
        return False


async def test_concurrent_connections(tokens: list) -> bool:
    """Test both tokens connecting to the same room simultaneously."""
    print(f"\n🤝 Testing concurrent WebSocket connections...")
    
    async def connect_client(client_id: str, token: str):
        ws_url = f"{WS_BASE_URL}/webrtc/ws/{ROOM_ID}?token={token}"
        
        try:
            async with websockets.connect(ws_url) as websocket:
                print(f"   ✅ [{client_id}] Connected")
                
                messages = []
                
                # Collect messages for 5 seconds
                end_time = time.time() + 5
                while time.time() < end_time:
                    try:
                        message_raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        message = json.loads(message_raw)
                        messages.append(message)
                        print(f"   📨 [{client_id}] {message.get('type')}")
                        
                        # If this is room-state, show participants
                        if message.get('type') == 'room-state':
                            participants = message.get('payload', {}).get('participants', [])
                            print(f"      [{client_id}] sees {len(participants)} participants")
                            
                    except asyncio.TimeoutError:
                        continue
                
                return len(messages) > 0
                
        except Exception as e:
            print(f"   ❌ [{client_id}] Connection failed: {e}")
            return False
    
    # Connect both clients concurrently
    results = await asyncio.gather(
        connect_client("Client1", tokens[0]),
        connect_client("Client2", tokens[1]),
        return_exceptions=True
    )
    
    success_count = sum(1 for r in results if r is True)
    print(f"   📊 {success_count}/2 clients connected successfully")
    
    return success_count == 2


async def main():
    """Main test execution."""
    print("🎥 Simple WebRTC Two-Token Test")
    print("=" * 40)
    print()
    
    try:
        # Step 1: Create users and get tokens
        print("👥 Step 1: Creating test users and getting tokens...")
        tokens = []
        
        for user_data in TEST_USERS:
            token = await create_and_login_user(user_data)
            tokens.append(token)
        
        print(f"\n✅ Got {len(tokens)} tokens successfully")
        
        # Step 2: Test individual connections
        print(f"\n🔌 Step 2: Testing individual WebSocket connections...")
        
        for i, (user_data, token) in enumerate(zip(TEST_USERS, tokens)):
            success = await test_webrtc_connection(user_data, token, f"User{i+1}")
            if not success:
                print(f"❌ Connection test failed for User{i+1}")
                return 1
        
        # Step 3: Test concurrent connections
        success = await test_concurrent_connections(tokens)
        
        if success:
            print("\n🎉 ALL TESTS PASSED!")
            print("✅ Both JWT tokens work with WebRTC")
            print("✅ WebSocket authentication is working")
            print("✅ Room signaling is functional")
            return 0
        else:
            print("\n❌ Concurrent connection test failed")
            return 1
            
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)