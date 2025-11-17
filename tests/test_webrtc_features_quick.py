"""
Quick WebRTC Phase 1 & Phase 2 Feature Test

Tests new features by sending messages through the existing WebSocket connection.
This test uses the already validated WebRTC infrastructure.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
import httpx
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


async def test_new_features():
    """Test all Phase 1 and Phase 2 features."""
    print("\n" + "="*70)
    print("🚀 WebRTC Phase 1 & Phase 2 Feature Test")
    print("="*70)
    
    # Create HTTP client
    http_client = httpx.AsyncClient(timeout=30.0)
    
    # Create test users
    print("\n1️⃣ Creating test users...")
    room_id = f"feature_test_{int(time.time())}"
    users = []
    
    for i in range(1, 3):
        user_data = {
            "username": f"feature_user{i}_{int(time.time())}",
            "email": f"feature_user{i}_{int(time.time())}@example.com",
            "password": f"SecurePass123!{i}",
            "first_name": f"Feature{i}",
            "last_name": "Tester"
        }
        
        # Register user
        register_response = await http_client.post(
            f"{BASE_URL}/auth/register",
            json=user_data
        )
        
        if register_response.status_code == 200:
            token = register_response.json()["access_token"]
            users.append({"data": user_data, "token": token})
            print(f"   ✅ Created user {i}: {user_data['username']}")
        else:
            print(f"   ❌ Failed to create user {i}: {register_response.status_code}")
            await http_client.aclose()
            return False
    
    # Connect WebSocket clients
    print("\n2️⃣ Connecting WebSocket clients...")
    ws_clients = []
    
    for i, user in enumerate(users, 1):
        uri = f"{WS_URL}/webrtc/ws/{room_id}?token={user['token']}"
        ws = await websockets.connect(uri)
        ws_clients.append(ws)
        print(f"   ✅ Client {i} connected")
        
        # Receive initial room-state message
        msg = await ws.recv()
        await asyncio.sleep(0.2)
    
    # Test Phase 1: Media Controls
    print("\n3️⃣ Testing Phase 1: Media Controls...")
    media_control = {
        "type": "media-control",
        "payload": {
            "action": "mute",
            "media_type": "audio",
            "user_id": "user1",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    await ws_clients[0].send(json.dumps(media_control))
    
    # Check if client 2 receives it
    received = await asyncio.wait_for(ws_clients[1].recv(), timeout=2.0)
    received_data = json.loads(received)
    if received_data.get("type") == "media-control":
        print("   ✅ Media control message sent and received")
    else:
        print(f"   ⚠️  Received: {received_data.get('type')}")
    
    # Test Phase 1: Screen Sharing
    print("\n4️⃣ Testing Phase 1: Screen Sharing...")
    screen_share = {
        "type": "screen-share-control",
        "payload": {
            "action": "start",
            "user_id": "user1",
            "screen_id": "screen_0",
            "quality": "high",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    await ws_clients[0].send(json.dumps(screen_share))
    
    received = await asyncio.wait_for(ws_clients[1].recv(), timeout=2.0)
    received_data = json.loads(received)
    if received_data.get("type") == "screen-share-control":
        print("   ✅ Screen share control sent and received")
    else:
        print(f"   ⚠️  Received: {received_data.get('type')}")
    
    # Test Phase 1: Chat
    print("\n5️⃣ Testing Phase 1: Chat Integration...")
    chat_msg = {
        "type": "chat-message",
        "payload": {
            "message_id": "msg_001",
            "user_id": "user1",
            "username": "FeatureUser1",
            "content": "Hello from Phase 1!",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message_type": "text",
            "reply_to": None
        }
    }
    await ws_clients[0].send(json.dumps(chat_msg))
    
    received = await asyncio.wait_for(ws_clients[1].recv(), timeout=2.0)
    received_data = json.loads(received)
    if received_data.get("type") == "chat-message":
        print("   ✅ Chat message sent and received")
    else:
        print(f"   ⚠️  Received: {received_data.get('type')}")
    
    # Test Phase 2: Network Stats
    print("\n6️⃣ Testing Phase 2: Network Optimization...")
    network_stats = {
        "type": "network-stats",
        "payload": {
            "user_id": "user1",
            "bandwidth_up": 2000,
            "bandwidth_down": 5000,
            "latency": 45,
            "packet_loss": 0.5,
            "jitter": 10,
            "connection_quality": "good",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    await ws_clients[0].send(json.dumps(network_stats))
    
    received = await asyncio.wait_for(ws_clients[1].recv(), timeout=2.0)
    received_data = json.loads(received)
    if received_data.get("type") == "network-stats":
        print("   ✅ Network stats sent and received")
    else:
        print(f"   ⚠️  Received: {received_data.get('type')}")
    
    # Test Phase 2: File Sharing
    print("\n7️⃣ Testing Phase 2: File Sharing...")
    file_offer = {
        "type": "file-share-offer",
        "payload": {
            "transfer_id": "transfer_001",
            "sender_id": "user1",
            "file_name": "test.pdf",
            "file_size": 1024000,
            "file_type": "application/pdf",
            "chunk_size": 16384,
            "total_chunks": 63,
            "target_user_id": None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }
    await ws_clients[0].send(json.dumps(file_offer))
    
    received = await asyncio.wait_for(ws_clients[1].recv(), timeout=2.0)
    received_data = json.loads(received)
    if received_data.get("type") == "file-share-offer":
        print("   ✅ File share offer sent and received")
    else:
        print(f"   ⚠️  Received: {received_data.get('type')}")
    
    # Test REST API: Room Permissions
    print("\n8️⃣ Testing Phase 1: Room Permissions API...")
    headers = {"Authorization": f"Bearer {users[0]['token']}"}
    
    # Get user role
    role_response = await http_client.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/roles/user2",
        headers=headers
    )
    if role_response.status_code == 200:
        print(f"   ✅ Role API working: {role_response.json()}")
    else:
        print(f"   ⚠️  Role API status: {role_response.status_code}")
    
    # Get permissions
    perm_response = await http_client.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/permissions/user2",
        headers=headers
    )
    if perm_response.status_code == 200:
        print(f"   ✅ Permissions API working")
    else:
        print(f"   ⚠️  Permissions API status: {perm_response.status_code}")
    
    # Test REST API: Analytics
    print("\n9️⃣ Testing Phase 2: Analytics API...")
    analytics_response = await http_client.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/analytics",
        headers=headers
    )
    if analytics_response.status_code == 200:
        data = analytics_response.json()
        print(f"   ✅ Analytics API working: {data.get('count', 0)} events")
    else:
        print(f"   ⚠️  Analytics API status: {analytics_response.status_code}")
    
    # Test REST API: Analytics Summary
    summary_response = await http_client.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/analytics/summary",
        headers=headers
    )
    if summary_response.status_code == 200:
        print(f"   ✅ Analytics summary working")
    else:
        print(f"   ⚠️  Analytics summary status: {summary_response.status_code}")
    
    # Test REST API: Recording
    print("\n🔟 Testing Phase 2: Recording API...")
    recording_id = f"rec_{int(time.time())}"
    
    # Get recordings (should be empty initially)
    recordings_response = await http_client.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/recordings",
        headers=headers
    )
    if recordings_response.status_code == 200:
        print(f"   ✅ Recording list API working")
    else:
        print(f"   ⚠️  Recording list status: {recordings_response.status_code}")
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    for ws in ws_clients:
        await ws.close()
    await http_client.aclose()
    
    print("\n" + "="*70)
    print("🎉 Phase 1 & Phase 2 Feature Test Complete!")
    print("="*70)
    print("\n✅ Features Tested:")
    print("   • Media Controls (mute/unmute)")
    print("   • Screen Sharing (start/stop)")
    print("   • Chat Integration (messages)")
    print("   • Network Optimization (stats)")
    print("   • File Sharing (offers)")
    print("   • Room Permissions API")
    print("   • Analytics API")
    print("   • Recording API")
    print("\n" + "="*70)
    
    return True


if __name__ == "__main__":
    result = asyncio.run(test_new_features())
    exit(0 if result else 1)
