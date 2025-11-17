"""
Comprehensive WebRTC Phase 1 & Phase 2 Feature Tests

Tests all new features including:
- Phase 1: Media Controls, Screen Sharing, Room Permissions, Chat
- Phase 2: Recording, File Sharing, Network Optimization, Analytics
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Dict, List
import websockets
import requests


BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"


class WebRTCTestClient:
    """WebRTC test client with Phase 1 & 2 feature support."""
    
    def __init__(self, token: str, room_id: str, user_id: str, username: str):
        self.token = token
        self.room_id = room_id
        self.user_id = user_id
        self.username = username
        self.ws = None
        self.received_messages: List[Dict] = []
        self.running = False
    
    async def connect(self):
        """Connect to WebRTC signaling server."""
        uri = f"{WS_URL}/webrtc/ws/{self.room_id}?token={self.token}"
        self.ws = await websockets.connect(uri)
        self.running = True
        print(f"✓ {self.username} connected to room {self.room_id}")
    
    async def send_message(self, message: Dict):
        """Send a message to the room."""
        await self.ws.send(json.dumps(message))
    
    async def receive_messages(self):
        """Continuously receive messages."""
        try:
            while self.running:
                message = await asyncio.wait_for(self.ws.recv(), timeout=1.0)
                msg_data = json.loads(message)
                self.received_messages.append(msg_data)
                
                msg_type = msg_data.get("type", "unknown")
                sender = msg_data.get("sender_id", "system")
                print(f"  📨 {self.username} received: {msg_type} from {sender}")
                
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            if self.running:
                print(f"  ❌ {self.username} receive error: {e}")
    
    async def disconnect(self):
        """Disconnect from the room."""
        self.running = False
        if self.ws:
            await self.ws.close()
        print(f"✓ {self.username} disconnected")
    
    def get_messages_by_type(self, message_type: str) -> List[Dict]:
        """Filter received messages by type."""
        return [msg for msg in self.received_messages if msg.get("type") == message_type]


async def test_phase1_media_controls(token1: str, token2: str, room_id: str):
    """Test Phase 1: Media Controls (mute/unmute, video toggle)."""
    print("\n" + "="*70)
    print("TEST: Phase 1 - Media Controls")
    print("="*70)
    
    client1 = WebRTCTestClient(token1, room_id, "user1", "Alice")
    client2 = WebRTCTestClient(token2, room_id, "user2", "Bob")
    
    try:
        # Connect both clients
        await client1.connect()
        await asyncio.sleep(0.5)
        await client2.connect()
        await asyncio.sleep(0.5)
        
        # Start receiving messages
        receive_task1 = asyncio.create_task(client1.receive_messages())
        receive_task2 = asyncio.create_task(client2.receive_messages())
        
        # Test 1: Mute audio
        print("\n  Testing audio mute...")
        media_control_msg = {
            "type": "media-control",
            "payload": {
                "action": "mute",
                "media_type": "audio",
                "user_id": "user1",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "sender_id": "user1",
            "room_id": room_id
        }
        await client1.send_message(media_control_msg)
        await asyncio.sleep(0.3)
        
        # Verify client2 received the media control
        media_controls = client2.get_messages_by_type("media-control")
        assert len(media_controls) > 0, "Client2 should receive media control message"
        assert media_controls[0]["payload"]["action"] == "mute"
        print("  ✓ Audio mute signal sent and received")
        
        # Test 2: Unmute audio
        print("  Testing audio unmute...")
        media_control_msg["payload"]["action"] = "unmute"
        await client1.send_message(media_control_msg)
        await asyncio.sleep(0.3)
        
        media_controls = client2.get_messages_by_type("media-control")
        assert any(m["payload"]["action"] == "unmute" for m in media_controls)
        print("  ✓ Audio unmute signal sent and received")
        
        # Test 3: Video on/off
        print("  Testing video toggle...")
        media_control_msg["payload"]["media_type"] = "video"
        media_control_msg["payload"]["action"] = "video_off"
        await client1.send_message(media_control_msg)
        await asyncio.sleep(0.3)
        
        media_controls = client2.get_messages_by_type("media-control")
        assert any(m["payload"]["action"] == "video_off" for m in media_controls)
        print("  ✓ Video toggle signal sent and received")
        
        print("\n✅ Phase 1 - Media Controls: PASSED")
        
    finally:
        await client1.disconnect()
        await client2.disconnect()


async def test_phase1_screen_sharing(token1: str, token2: str, room_id: str):
    """Test Phase 1: Screen Sharing."""
    print("\n" + "="*70)
    print("TEST: Phase 1 - Screen Sharing")
    print("="*70)
    
    client1 = WebRTCTestClient(token1, room_id, "user1", "Alice")
    client2 = WebRTCTestClient(token2, room_id, "user2", "Bob")
    
    try:
        await client1.connect()
        await asyncio.sleep(0.5)
        await client2.connect()
        await asyncio.sleep(0.5)
        
        receive_task1 = asyncio.create_task(client1.receive_messages())
        receive_task2 = asyncio.create_task(client2.receive_messages())
        
        # Test screen share start
        print("\n  Testing screen share start...")
        screen_share_msg = {
            "type": "screen-share-control",
            "payload": {
                "action": "start",
                "user_id": "user1",
                "screen_id": "screen_0",
                "quality": "high",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "sender_id": "user1",
            "room_id": room_id
        }
        await client1.send_message(screen_share_msg)
        await asyncio.sleep(0.3)
        
        screen_shares = client2.get_messages_by_type("screen-share-control")
        assert len(screen_shares) > 0, "Client2 should receive screen share message"
        assert screen_shares[0]["payload"]["action"] == "start"
        print("  ✓ Screen share start signal sent and received")
        
        # Test screen share stop
        print("  Testing screen share stop...")
        screen_share_msg["payload"]["action"] = "stop"
        await client1.send_message(screen_share_msg)
        await asyncio.sleep(0.3)
        
        screen_shares = client2.get_messages_by_type("screen-share-control")
        assert any(m["payload"]["action"] == "stop" for m in screen_shares)
        print("  ✓ Screen share stop signal sent and received")
        
        print("\n✅ Phase 1 - Screen Sharing: PASSED")
        
    finally:
        await client1.disconnect()
        await client2.disconnect()


async def test_phase1_chat_integration(token1: str, token2: str, room_id: str):
    """Test Phase 1: Chat Integration."""
    print("\n" + "="*70)
    print("TEST: Phase 1 - Chat Integration")
    print("="*70)
    
    client1 = WebRTCTestClient(token1, room_id, "user1", "Alice")
    client2 = WebRTCTestClient(token2, room_id, "user2", "Bob")
    
    try:
        await client1.connect()
        await asyncio.sleep(0.5)
        await client2.connect()
        await asyncio.sleep(0.5)
        
        receive_task1 = asyncio.create_task(client1.receive_messages())
        receive_task2 = asyncio.create_task(client2.receive_messages())
        
        # Test sending chat messages
        print("\n  Testing chat message sending...")
        chat_msg = {
            "type": "chat-message",
            "payload": {
                "message_id": "msg_001",
                "user_id": "user1",
                "username": "Alice",
                "content": "Hello everyone!",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_type": "text",
                "reply_to": None
            },
            "sender_id": "user1",
            "room_id": room_id
        }
        await client1.send_message(chat_msg)
        await asyncio.sleep(0.3)
        
        chat_messages = client2.get_messages_by_type("chat-message")
        assert len(chat_messages) > 0, "Client2 should receive chat message"
        assert chat_messages[0]["payload"]["content"] == "Hello everyone!"
        print("  ✓ Chat message sent and received")
        
        # Test reply to message
        print("  Testing message reply...")
        reply_msg = chat_msg.copy()
        reply_msg["payload"]["message_id"] = "msg_002"
        reply_msg["payload"]["user_id"] = "user2"
        reply_msg["payload"]["username"] = "Bob"
        reply_msg["payload"]["content"] = "Hi Alice!"
        reply_msg["payload"]["reply_to"] = "msg_001"
        reply_msg["sender_id"] = "user2"
        await client2.send_message(reply_msg)
        await asyncio.sleep(0.3)
        
        replies = client1.get_messages_by_type("chat-message")
        assert any(m["payload"].get("reply_to") == "msg_001" for m in replies)
        print("  ✓ Message reply functionality works")
        
        print("\n✅ Phase 1 - Chat Integration: PASSED")
        
    finally:
        await client1.disconnect()
        await client2.disconnect()


async def test_phase1_room_permissions(token1: str, room_id: str):
    """Test Phase 1: Room Permissions & Roles."""
    print("\n" + "="*70)
    print("TEST: Phase 1 - Room Permissions")
    print("="*70)
    
    # Test via REST API
    headers = {"Authorization": f"Bearer {token1}"}
    
    # Test 1: Set user role
    print("\n  Testing role assignment...")
    role_response = requests.post(
        f"{BASE_URL}/webrtc/rooms/{room_id}/roles/user2?role=moderator",
        headers=headers
    )
    assert role_response.status_code in [200, 403], f"Unexpected status: {role_response.status_code}"
    print(f"  ✓ Role API responded (status: {role_response.status_code})")
    
    # Test 2: Get user role
    print("  Testing role retrieval...")
    get_role_response = requests.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/roles/user2",
        headers=headers
    )
    assert get_role_response.status_code == 200
    print(f"  ✓ Role retrieved: {get_role_response.json()}")
    
    # Test 3: Set permissions
    print("  Testing permission assignment...")
    permissions = {
        "can_speak": True,
        "can_share_video": True,
        "can_share_screen": False,
        "can_send_chat": True,
        "can_share_files": True,
        "can_manage_participants": False,
        "can_record": False
    }
    perm_response = requests.post(
        f"{BASE_URL}/webrtc/rooms/{room_id}/permissions/user2",
        headers=headers,
        json=permissions
    )
    assert perm_response.status_code in [200, 403]
    print(f"  ✓ Permissions API responded (status: {perm_response.status_code})")
    
    # Test 4: Get permissions
    print("  Testing permission retrieval...")
    get_perm_response = requests.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/permissions/user2",
        headers=headers
    )
    assert get_perm_response.status_code == 200
    print(f"  ✓ Permissions retrieved")
    
    print("\n✅ Phase 1 - Room Permissions: PASSED")


async def test_phase2_recording_system(token1: str, room_id: str):
    """Test Phase 2: Recording System."""
    print("\n" + "="*70)
    print("TEST: Phase 2 - Recording System")
    print("="*70)
    
    headers = {"Authorization": f"Bearer {token1}"}
    recording_id = f"rec_{int(time.time())}"
    
    # Test 1: Start recording
    print("\n  Testing recording start...")
    start_response = requests.post(
        f"{BASE_URL}/webrtc/rooms/{room_id}/recordings/start",
        headers=headers,
        params={"recording_id": recording_id},
        json={"format": "mp4", "quality": "high"}
    )
    assert start_response.status_code in [200, 403], f"Unexpected status: {start_response.status_code}"
    print(f"  ✓ Recording start API responded (status: {start_response.status_code})")
    
    # Test 2: Get active recordings
    print("  Testing active recordings retrieval...")
    get_recordings_response = requests.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/recordings",
        headers=headers
    )
    assert get_recordings_response.status_code == 200
    print(f"  ✓ Active recordings retrieved")
    
    # Test 3: Stop recording
    print("  Testing recording stop...")
    stop_response = requests.post(
        f"{BASE_URL}/webrtc/rooms/{room_id}/recordings/{recording_id}/stop",
        headers=headers
    )
    assert stop_response.status_code == 200
    print(f"  ✓ Recording stopped")
    
    print("\n✅ Phase 2 - Recording System: PASSED")


async def test_phase2_file_sharing(token1: str, token2: str, room_id: str):
    """Test Phase 2: File Sharing."""
    print("\n" + "="*70)
    print("TEST: Phase 2 - File Sharing")
    print("="*70)
    
    client1 = WebRTCTestClient(token1, room_id, "user1", "Alice")
    client2 = WebRTCTestClient(token2, room_id, "user2", "Bob")
    
    try:
        await client1.connect()
        await asyncio.sleep(0.5)
        await client2.connect()
        await asyncio.sleep(0.5)
        
        receive_task1 = asyncio.create_task(client1.receive_messages())
        receive_task2 = asyncio.create_task(client2.receive_messages())
        
        # Test file share offer
        print("\n  Testing file share offer...")
        file_share_msg = {
            "type": "file-share-offer",
            "payload": {
                "transfer_id": "transfer_001",
                "sender_id": "user1",
                "file_name": "document.pdf",
                "file_size": 1024000,
                "file_type": "application/pdf",
                "chunk_size": 16384,
                "total_chunks": 63,
                "target_user_id": "user2",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "sender_id": "user1",
            "room_id": room_id
        }
        await client1.send_message(file_share_msg)
        await asyncio.sleep(0.3)
        
        file_offers = client2.get_messages_by_type("file-share-offer")
        assert len(file_offers) > 0, "Client2 should receive file share offer"
        print("  ✓ File share offer sent and received")
        
        # Test file share accept
        print("  Testing file share accept...")
        accept_msg = {
            "type": "file-share-accept",
            "payload": {
                "transfer_id": "transfer_001",
                "user_id": "user2",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "sender_id": "user2",
            "room_id": room_id
        }
        await client2.send_message(accept_msg)
        await asyncio.sleep(0.3)
        
        accepts = client1.get_messages_by_type("file-share-accept")
        assert len(accepts) > 0
        print("  ✓ File share accepted")
        
        # Test progress update
        print("  Testing file share progress...")
        progress_msg = {
            "type": "file-share-progress",
            "payload": {
                "transfer_id": "transfer_001",
                "chunks_received": 30,
                "total_chunks": 63,
                "percentage": 47.6,
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "sender_id": "user2",
            "room_id": room_id
        }
        await client2.send_message(progress_msg)
        await asyncio.sleep(0.3)
        
        progress = client1.get_messages_by_type("file-share-progress")
        assert len(progress) > 0
        print("  ✓ File share progress tracked")
        
        print("\n✅ Phase 2 - File Sharing: PASSED")
        
    finally:
        await client1.disconnect()
        await client2.disconnect()


async def test_phase2_network_optimization(token1: str, token2: str, room_id: str):
    """Test Phase 2: Network Optimization."""
    print("\n" + "="*70)
    print("TEST: Phase 2 - Network Optimization")
    print("="*70)
    
    client1 = WebRTCTestClient(token1, room_id, "user1", "Alice")
    client2 = WebRTCTestClient(token2, room_id, "user2", "Bob")
    
    try:
        await client1.connect()
        await asyncio.sleep(0.5)
        await client2.connect()
        await asyncio.sleep(0.5)
        
        receive_task1 = asyncio.create_task(client1.receive_messages())
        receive_task2 = asyncio.create_task(client2.receive_messages())
        
        # Test network stats
        print("\n  Testing network stats reporting...")
        stats_msg = {
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
            },
            "sender_id": "user1",
            "room_id": room_id
        }
        await client1.send_message(stats_msg)
        await asyncio.sleep(0.3)
        
        stats = client2.get_messages_by_type("network-stats")
        assert len(stats) > 0
        print("  ✓ Network stats sent and received")
        
        # Test quality update
        print("  Testing adaptive quality update...")
        quality_msg = {
            "type": "quality-update",
            "payload": {
                "user_id": "user1",
                "video_resolution": "720p",
                "video_bitrate": 1500,
                "audio_bitrate": 128,
                "frame_rate": 30,
                "reason": "network_adaptation",
                "timestamp": datetime.now(timezone.utc).isoformat()
            },
            "sender_id": "user1",
            "room_id": room_id
        }
        await client1.send_message(quality_msg)
        await asyncio.sleep(0.3)
        
        quality_updates = client2.get_messages_by_type("quality-update")
        assert len(quality_updates) > 0
        print("  ✓ Quality update sent and received")
        
        print("\n✅ Phase 2 - Network Optimization: PASSED")
        
    finally:
        await client1.disconnect()
        await client2.disconnect()


async def test_phase2_analytics(token1: str, room_id: str):
    """Test Phase 2: Analytics Dashboard."""
    print("\n" + "="*70)
    print("TEST: Phase 2 - Analytics Dashboard")
    print("="*70)
    
    headers = {"Authorization": f"Bearer {token1}"}
    
    # Test 1: Get analytics
    print("\n  Testing analytics retrieval...")
    analytics_response = requests.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/analytics",
        headers=headers,
        params={"limit": 50}
    )
    assert analytics_response.status_code == 200
    analytics_data = analytics_response.json()
    print(f"  ✓ Retrieved {analytics_data.get('count', 0)} analytics events")
    
    # Test 2: Get analytics summary
    print("  Testing analytics summary...")
    summary_response = requests.get(
        f"{BASE_URL}/webrtc/rooms/{room_id}/analytics/summary",
        headers=headers
    )
    assert summary_response.status_code == 200
    summary = summary_response.json()
    print(f"  ✓ Analytics summary: {summary.get('total_events', 0)} events, "
          f"{summary.get('unique_users', 0)} unique users")
    
    print("\n✅ Phase 2 - Analytics Dashboard: PASSED")


async def run_all_tests():
    """Run all Phase 1 and Phase 2 tests."""
    print("\n" + "="*70)
    print("WEBRTC PHASE 1 & PHASE 2 COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    # Get auth tokens (reusing from production tests)
    print("\nObtaining auth tokens...")
    
    # Try to use existing test users or prompt for tokens
    print("\n⚠️  This test requires valid auth tokens.")
    print("Please ensure the Second Brain Database server is running.")
    print("Using test credentials from previous tests...")
    
    # Login user 1
    login1_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": "webrtc_user1@test.com",
            "password": "WebRTC_Test_Pass_123!"
        }
    )
    
    # Login user 2
    login2_response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "email": "webrtc_user2@test.com",
            "password": "WebRTC_Test_Pass_123!"
        }
    )
    
    # If login fails, try signup (this may fail due to turnstile)
    if login1_response.status_code != 200:
        print("⚠️  Please create test users manually or disable turnstile for testing")
        print("   User 1: webrtc_user1@test.com / WebRTC_Test_Pass_123!")
        print("   User 2: webrtc_user2@test.com / WebRTC_Test_Pass_123!")
        return
    
    token1 = login1_response.json().get("access_token") or login1_response.json().get("token")
    token2 = login2_response.json().get("access_token") or login2_response.json().get("token")
    
    if not token1 or not token2:
        print(f"❌ Failed to obtain tokens. Response 1: {login1_response.json()}")
        print(f"❌ Response 2: {login2_response.json()}")
        return
    
    room_id = f"test_room_phase1_phase2_{int(time.time())}"
    
    print(f"✓ Tokens obtained for room: {room_id}\n")
    
    # Run all tests
    try:
        await test_phase1_media_controls(token1, token2, room_id)
        await asyncio.sleep(1)
        
        await test_phase1_screen_sharing(token1, token2, room_id)
        await asyncio.sleep(1)
        
        await test_phase1_chat_integration(token1, token2, room_id)
        await asyncio.sleep(1)
        
        await test_phase1_room_permissions(token1, room_id)
        await asyncio.sleep(1)
        
        await test_phase2_recording_system(token1, room_id)
        await asyncio.sleep(1)
        
        await test_phase2_file_sharing(token1, token2, room_id)
        await asyncio.sleep(1)
        
        await test_phase2_network_optimization(token1, token2, room_id)
        await asyncio.sleep(1)
        
        await test_phase2_analytics(token1, room_id)
        
        print("\n" + "="*70)
        print("🎉 ALL PHASE 1 & PHASE 2 TESTS PASSED!")
        print("="*70)
        print("\nFeatures Tested:")
        print("  ✅ Phase 1: Media Controls (mute/unmute, video toggle)")
        print("  ✅ Phase 1: Screen Sharing (start/stop)")
        print("  ✅ Phase 1: Chat Integration (messages, replies)")
        print("  ✅ Phase 1: Room Permissions (roles, permissions)")
        print("  ✅ Phase 2: Recording System (start/stop/list)")
        print("  ✅ Phase 2: File Sharing (offer/accept/progress)")
        print("  ✅ Phase 2: Network Optimization (stats, quality)")
        print("  ✅ Phase 2: Analytics Dashboard (events, summary)")
        print("\n" + "="*70)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
