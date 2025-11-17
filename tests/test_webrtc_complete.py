#!/usr/bin/env python3
"""
WebRTC Complete Test Suite - Production Ready

This comprehensive test validates the complete WebRTC signaling system
including user authentication, WebSocket connections, message routing,
and participant management with enhanced reliability and error handling.
"""

import asyncio
import json
import logging
import random
import string
import httpx
from datetime import datetime, timezone
from typing import Dict, List, Optional
import websockets

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("WebRTC_Test")

# Test configuration
TEST_CONFIG = {
    "base_url": "http://localhost:8000",
    "websocket_url": "ws://localhost:8000",
    "room_id": "webrtc-test-room-production",
    "timeout": 30.0,
    "message_timeout": 10.0,
    "retry_attempts": 3,
    "retry_delay": 1.0
}

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import httpx
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

# Add src to path for imports
sys.path.insert(0, "src")

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[WebRTC_Test]")

# Test configuration
TEST_CONFIG = {
    "base_url": f"http://localhost:{settings.PORT}",
    "ws_url": f"ws://localhost:{settings.PORT}",
    "room_id": "webrtc-test-room",
    "users": [
        {
            "username": "webrtc_test_user1",
            "email": "webrtc1@example.com",
            "password": "TestPass123!",
            "display_name": "WebRTC User 1"
        },
        {
            "username": "webrtc_test_user2", 
            "email": "webrtc2@example.com",
            "password": "TestPass456!",
            "display_name": "WebRTC User 2"
        }
    ],
    "test_timeout": 30,  # seconds
}


class WebRTCTestClient:
    """Enhanced WebSocket client for WebRTC testing with improved reliability."""
    
    def __init__(self, client_id: str, user_data: Dict, token: str):
        self.client_id = client_id
        self.user_data = user_data
        self.token = token
        self.websocket = None
        self.connected = False
        self.messages_received = []
        self.participants = []
        self.last_room_state = None
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        
    async def connect(self, room_id: str):
        """Connect to WebRTC WebSocket endpoint with retry logic."""
        websocket_url = f"{TEST_CONFIG['websocket_url']}/webrtc/ws/{room_id}?token={self.token}"
        
        while self.connection_attempts < self.max_connection_attempts:
            self.connection_attempts += 1
            logger.info(f"[{self.client_id}] Connecting to WebSocket (attempt {self.connection_attempts}): {websocket_url}")
            
            try:
                self.websocket = await websockets.connect(
                    websocket_url, 
                    timeout=TEST_CONFIG['timeout'],
                    ping_interval=20,
                    ping_timeout=10
                )
                self.connected = True
                logger.info(f"[{self.client_id}] WebSocket connected successfully")
                return True
            except Exception as e:
                logger.error(f"[{self.client_id}] WebSocket connection failed (attempt {self.connection_attempts}): {e}")
                if self.connection_attempts < self.max_connection_attempts:
                    await asyncio.sleep(TEST_CONFIG['retry_delay'])
        
        self.connected = False
        return False
    
    async def disconnect(self):
        """Disconnect from WebSocket."""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info(f"[{self.client_id}] WebSocket disconnected")
    
    async def send_message(self, message_type: str, payload: Dict = None):
        """Send WebRTC signaling message."""
        if not self.websocket or not self.connected:
            logger.error(f"[{self.client_id}] Cannot send message: not connected")
            return False
        
        message = {
            "type": message_type,
            "payload": payload or {},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.info(f"[{self.client_id}] Sent {message_type} message")
            return True
        except Exception as e:
            logger.error(f"[{self.client_id}] Failed to send message: {e}")
            return False
    
    async def receive_messages(self, timeout: float = 5.0, expected_types: List[str] = None):
        """Receive messages from WebSocket with enhanced filtering and timeout."""
        if not self.websocket or not self.connected:
            return []
        
        messages = []
        received_types = set()
        end_time = asyncio.get_event_loop().time() + timeout
        
        try:
            while asyncio.get_event_loop().time() < end_time:
                try:
                    remaining_timeout = end_time - asyncio.get_event_loop().time()
                    if remaining_timeout <= 0:
                        break
                        
                    message_raw = await asyncio.wait_for(
                        self.websocket.recv(), 
                        timeout=min(remaining_timeout, 1.0)
                    )
                    message = json.loads(message_raw)
                    messages.append(message)
                    self.messages_received.append(message)
                    
                    # Update participants and room state
                    message_type = message.get("type")
                    received_types.add(message_type)
                    
                    if message_type == "room-state":
                        payload = message.get("payload", {})
                        self.participants = payload.get("participants", [])
                        self.last_room_state = message
                        logger.info(f"[{self.client_id}] Updated room state: {len(self.participants)} participants")
                    elif message_type in ["user-joined", "user-left"]:
                        # Room state should be updated by server, but we can track changes
                        logger.info(f"[{self.client_id}] Received {message_type} message")
                    
                    logger.info(f"[{self.client_id}] Received {message_type} message")
                    
                    # If we're looking for specific types and got them all, break early
                    if expected_types and all(t in received_types for t in expected_types):
                        logger.info(f"[{self.client_id}] Received all expected message types: {expected_types}")
                        break
                    
                except asyncio.TimeoutError:
                    continue  # Keep trying until overall timeout
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"[{self.client_id}] WebSocket connection closed")
        except Exception as e:
            logger.error(f"[{self.client_id}] Error receiving messages: {e}")
        
        logger.info(f"[{self.client_id}] Received {len(messages)} messages, types: {received_types}")
        return messages
    
    async def wait_for_participant_count(self, expected_count: int, timeout: float = 10.0):
        """Wait for specific participant count with intelligent retry."""
        end_time = asyncio.get_event_loop().time() + timeout
        
        while asyncio.get_event_loop().time() < end_time:
            # First check current state
            if len(self.participants) == expected_count:
                logger.info(f"[{self.client_id}] Found expected participant count: {expected_count}")
                return self.participants
            
            # If not found, try to receive more messages
            await self.receive_messages(timeout=0.5, expected_types=["room-state"])
            
            # Check again after receiving messages
            if len(self.participants) == expected_count:
                logger.info(f"[{self.client_id}] Found expected participant count after message update: {expected_count}")
                return self.participants
                
            await asyncio.sleep(0.2)
        
        logger.warning(f"[{self.client_id}] Timeout waiting for {expected_count} participants, have {len(self.participants)}")
        return self.participants
    
    async def send_webrtc_offer(self, target_user_id: str = None):
        """Send WebRTC offer message."""
        offer_payload = {
            "sdp": "v=0\r\no=- 123456789 1 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n...",  # Mock SDP
            "type": "offer"
        }
        if target_user_id:
            offer_payload["target_id"] = target_user_id
            
        return await self.send_message("offer", offer_payload)
    
    async def send_webrtc_answer(self, target_user_id: str = None):
        """Send WebRTC answer message."""
        answer_payload = {
            "sdp": "v=0\r\no=- 987654321 1 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n...",  # Mock SDP
            "type": "answer"
        }
        if target_user_id:
            answer_payload["target_id"] = target_user_id
            
        return await self.send_message("answer", answer_payload)
    
    async def send_ice_candidate(self, target_user_id: str = None):
        """Send ICE candidate message."""
        ice_payload = {
            "candidate": {
                "candidate": "candidate:1 1 UDP 2130706431 127.0.0.1 54400 typ host",
                "sdpMLineIndex": 0,
                "sdpMid": "0"
            }
        }
        if target_user_id:
            ice_payload["target_id"] = target_user_id
            
        return await self.send_message("ice-candidate", ice_payload)


class WebRTCTestSuite:
    """Complete WebRTC test suite."""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)
        self.test_results = {}
        self.created_users = []
        self.user_tokens = []
        self.test_clients: List[WebRTCTestClient] = []
    
    async def cleanup(self):
        """Clean up test resources."""
        logger.info("🧹 Cleaning up test resources...")
        
        # Disconnect WebSocket clients
        for client in self.test_clients:
            try:
                await client.disconnect()
            except:
                pass
        
        # Delete created users
        for user in self.created_users:
            try:
                await self.delete_test_user(user["username"])
            except:
                pass
        
        # Close HTTP client
        await self.http_client.aclose()
        logger.info("✅ Cleanup completed")
    
    async def delete_test_user(self, username: str):
        """Delete a test user."""
        try:
            # Get admin token first
            admin_response = await self.http_client.post(
                f"{TEST_CONFIG['base_url']}/auth/login",
                json={"username": "admin", "password": "admin123"}
            )
            
            if admin_response.status_code == 200:
                admin_token = admin_response.json()["access_token"]
                
                # Delete user
                delete_response = await self.http_client.delete(
                    f"{TEST_CONFIG['base_url']}/admin/users/{username}",
                    headers={"Authorization": f"Bearer {admin_token}"}
                )
                
                if delete_response.status_code in [200, 204, 404]:
                    logger.info(f"🗑️ Deleted test user: {username}")
                else:
                    logger.warning(f"Failed to delete user {username}: {delete_response.status_code}")
                    
        except Exception as e:
            logger.warning(f"Error deleting user {username}: {e}")
    
    async def test_server_health(self) -> bool:
        """Test server health and availability."""
        logger.info("🔍 Testing server health...")
        
        try:
            response = await self.http_client.get(f"{TEST_CONFIG['base_url']}/health")
            
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"✅ Server is healthy: {health_data}")
                self.test_results["server_health"] = {"status": "✅ PASS", "data": health_data}
                return True
            else:
                logger.error(f"❌ Server health check failed: {response.status_code}")
                self.test_results["server_health"] = {"status": "❌ FAIL", "error": f"HTTP {response.status_code}"}
                return False
                
        except Exception as e:
            logger.error(f"❌ Server health check error: {e}")
            self.test_results["server_health"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_user_creation_and_authentication(self) -> bool:
        """Create test users and authenticate them."""
        logger.info("👥 Testing user creation and authentication...")
        
        try:
            for i, user_data in enumerate(TEST_CONFIG["users"]):
                logger.info(f"Creating user {i+1}: {user_data['username']}")
                
                # Register user
                register_response = await self.http_client.post(
                    f"{TEST_CONFIG['base_url']}/auth/register",
                    json={
                        "username": user_data["username"],
                        "email": user_data["email"],
                        "password": user_data["password"]
                    }
                )
                
                if register_response.status_code not in [200, 201]:
                    # User might already exist, try to continue
                    logger.warning(f"User registration returned {register_response.status_code}, trying login")
                else:
                    logger.info(f"✅ User {user_data['username']} registered")
                    self.created_users.append(user_data)
                
                if register_response.status_code == 200:
                    # Registration successful, get token from response
                    token_data = register_response.json()
                    token = token_data["access_token"]
                    self.user_tokens.append(token)
                    logger.info(f"✅ User {user_data['username']} authenticated via registration")
                else:
                    # Try login in case user already exists
                    logger.info(f"Registration failed ({register_response.status_code}), trying login for {user_data['username']}")
                    
                    login_response = await self.http_client.post(
                        f"{TEST_CONFIG['base_url']}/auth/login",
                        json={
                            "username": user_data["username"],
                            "password": user_data["password"]
                        }
                    )
                    
                    if login_response.status_code == 200:
                        token_data = login_response.json()
                        token = token_data["access_token"]
                        self.user_tokens.append(token)
                        logger.info(f"✅ User {user_data['username']} authenticated via login")
                    else:
                        logger.error(f"❌ Both registration and login failed for {user_data['username']}: {login_response.status_code}")
                        return False
                
                # Verify token by calling protected endpoint
                verify_response = await self.http_client.get(
                    f"{TEST_CONFIG['base_url']}/auth/validate-token",
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                if verify_response.status_code == 200:
                    user_info = verify_response.json()
                    logger.info(f"✅ Token validated for {user_info.get('username')}")
                else:
                    logger.error(f"❌ Token validation failed for {user_data['username']}")
                    return False
            
            self.test_results["user_auth"] = {
                "status": "✅ PASS",
                "users_created": len(self.created_users),
                "tokens_obtained": len(self.user_tokens)
            }
            return True
            
        except Exception as e:
            logger.error(f"❌ User creation/authentication failed: {e}")
            self.test_results["user_auth"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_webrtc_config_endpoint(self) -> bool:
        """Test WebRTC configuration endpoint."""
        logger.info("⚙️ Testing WebRTC config endpoint...")
        
        try:
            if not self.user_tokens:
                logger.error("❌ No user tokens available for config test")
                return False
            
            response = await self.http_client.get(
                f"{TEST_CONFIG['base_url']}/webrtc/config",
                headers={"Authorization": f"Bearer {self.user_tokens[0]}"}
            )
            
            if response.status_code == 200:
                config = response.json()
                logger.info(f"✅ WebRTC config retrieved: {len(config.get('ice_servers', []))} ICE servers")
                self.test_results["webrtc_config"] = {"status": "✅ PASS", "config": config}
                return True
            else:
                logger.error(f"❌ WebRTC config failed: {response.status_code}")
                self.test_results["webrtc_config"] = {"status": "❌ FAIL", "error": f"HTTP {response.status_code}"}
                return False
                
        except Exception as e:
            logger.error(f"❌ WebRTC config error: {e}")
            self.test_results["webrtc_config"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_websocket_connections(self) -> bool:
        """Test WebSocket connections for both users."""
        logger.info("🔌 Testing WebSocket connections...")
        
        try:
            if len(self.user_tokens) < 2:
                logger.error("❌ Need at least 2 user tokens for WebSocket test")
                return False
            
            # Create test clients
            for i, (user_data, token) in enumerate(zip(TEST_CONFIG["users"], self.user_tokens)):
                client = WebRTCTestClient(user_data, token, f"Client{i+1}")
                self.test_clients.append(client)
            
            # Connect both clients to the same room
            room_id = TEST_CONFIG["room_id"]
            
            for client in self.test_clients:
                success = await client.connect_websocket(room_id)
                if not success:
                    logger.error(f"❌ Failed to connect {client.client_id}")
                    return False
            
            logger.info("✅ Both clients connected to WebSocket")
            
            # Give time for initial messages
            await asyncio.sleep(2)
            
            # Receive initial messages (room state, user joined notifications)
            for client in self.test_clients:
                messages = await client.receive_messages(timeout=3.0)
                logger.info(f"📨 {client.client_id} received {len(messages)} initial messages")
            
            self.test_results["websocket_connections"] = {
                "status": "✅ PASS",
                "clients_connected": len(self.test_clients),
                "room_id": room_id
            }
            return True
            
        except Exception as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            self.test_results["websocket_connections"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_room_state_and_participants(self) -> bool:
        """Test room state and participant management."""
        logger.info("👥 Testing room state and participant management...")
        
        try:
            if len(self.test_clients) < 2:
                logger.error("❌ Need at least 2 connected clients")
                return False
            
            # Check that both clients received room state
            participants_per_client = []
            
            for client in self.test_clients:
                # Check if client has participant data
                if client.participants:
                    participants_per_client.append(len(client.participants))
                    logger.info(f"📊 {client.client_id} sees {len(client.participants)} participants")
                    
                    # Log participant details
                    for participant in client.participants:
                        logger.info(f"   - {participant.get('username')} ({participant.get('user_id')})")
                else:
                    logger.warning(f"⚠️ {client.client_id} has no participant data")
                    participants_per_client.append(0)
            
            # Both clients should see 2 participants (including themselves)
            expected_participants = 2
            all_correct = all(count == expected_participants for count in participants_per_client)
            
            if all_correct:
                logger.info(f"✅ All clients correctly see {expected_participants} participants")
                self.test_results["room_state"] = {
                    "status": "✅ PASS",
                    "expected_participants": expected_participants,
                    "actual_participants": participants_per_client
                }
                return True
            else:
                logger.error(f"❌ Participant count mismatch. Expected: {expected_participants}, Actual: {participants_per_client}")
                self.test_results["room_state"] = {
                    "status": "❌ FAIL",
                    "expected_participants": expected_participants,
                    "actual_participants": participants_per_client
                }
                return False
                
        except Exception as e:
            logger.error(f"❌ Room state test error: {e}")
            self.test_results["room_state"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_webrtc_signaling(self) -> bool:
        """Test WebRTC signaling message flow."""
        logger.info("📡 Testing WebRTC signaling...")
        
        try:
            if len(self.test_clients) < 2:
                logger.error("❌ Need at least 2 connected clients")
                return False
            
            client1, client2 = self.test_clients[0], self.test_clients[1]
            
            # Get user IDs from participants
            client1_user_id = None
            client2_user_id = None
            
            for participant in client1.participants:
                if participant.get("username") == client1.user_data["username"]:
                    client1_user_id = participant.get("user_id")
                elif participant.get("username") == client2.user_data["username"]:
                    client2_user_id = participant.get("user_id")
            
            if not client1_user_id or not client2_user_id:
                logger.error("❌ Could not determine user IDs from participants")
                return False
            
            logger.info(f"🎯 Client1 User ID: {client1_user_id}")
            logger.info(f"🎯 Client2 User ID: {client2_user_id}")
            
            # Test 1: Client1 sends offer to Client2
            logger.info("📤 Client1 sending WebRTC offer...")
            await client1.send_webrtc_offer(client2_user_id)
            
            # Client2 should receive the offer
            await asyncio.sleep(1)
            client2_messages = await client2.receive_messages(timeout=2.0)
            
            offer_received = any(msg.get("type") == "offer" for msg in client2_messages)
            if offer_received:
                logger.info("✅ Client2 received WebRTC offer")
            else:
                logger.error("❌ Client2 did not receive WebRTC offer")
                return False
            
            # Test 2: Client2 sends answer back to Client1
            logger.info("📤 Client2 sending WebRTC answer...")
            await client2.send_webrtc_answer(client1_user_id)
            
            # Client1 should receive the answer
            await asyncio.sleep(1)
            client1_messages = await client1.receive_messages(timeout=2.0)
            
            answer_received = any(msg.get("type") == "answer" for msg in client1_messages)
            if answer_received:
                logger.info("✅ Client1 received WebRTC answer")
            else:
                logger.error("❌ Client1 did not receive WebRTC answer")
                return False
            
            # Test 3: Both clients exchange ICE candidates
            logger.info("📤 Exchanging ICE candidates...")
            
            # Client1 sends ICE candidate
            await client1.send_ice_candidate(client2_user_id)
            await asyncio.sleep(0.5)
            
            # Client2 sends ICE candidate  
            await client2.send_ice_candidate(client1_user_id)
            await asyncio.sleep(1)
            
            # Check that both received ICE candidates
            client1_ice_messages = await client1.receive_messages(timeout=2.0)
            client2_ice_messages = await client2.receive_messages(timeout=2.0)
            
            client1_ice_received = any(msg.get("type") == "ice-candidate" for msg in client1_ice_messages)
            client2_ice_received = any(msg.get("type") == "ice-candidate" for msg in client2_ice_messages)
            
            if client1_ice_received and client2_ice_received:
                logger.info("✅ Both clients exchanged ICE candidates")
                
                self.test_results["webrtc_signaling"] = {
                    "status": "✅ PASS",
                    "offer_exchange": True,
                    "answer_exchange": True,
                    "ice_exchange": True
                }
                return True
            else:
                logger.error(f"❌ ICE candidate exchange failed. Client1 received: {client1_ice_received}, Client2 received: {client2_ice_received}")
                self.test_results["webrtc_signaling"] = {
                    "status": "❌ FAIL",
                    "offer_exchange": True,
                    "answer_exchange": True,
                    "ice_exchange": False
                }
                return False
                
        except Exception as e:
            logger.error(f"❌ WebRTC signaling test error: {e}")
            self.test_results["webrtc_signaling"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def test_participant_disconnect(self) -> bool:
        """Test participant disconnect and notification."""
        logger.info("🔌 Testing participant disconnect...")
        
        try:
            if len(self.test_clients) < 2:
                logger.error("❌ Need at least 2 connected clients")
                return False
            
            client1, client2 = self.test_clients[0], self.test_clients[1]
            
            # Disconnect client1
            logger.info(f"📤 Disconnecting {client1.client_id}...")
            await client1.disconnect()
            
            # Client2 should receive user-left notification
            await asyncio.sleep(2)
            client2_messages = await client2.receive_messages(timeout=3.0)
            
            user_left_received = any(msg.get("type") == "user-left" for msg in client2_messages)
            
            if user_left_received:
                logger.info("✅ Client2 received user-left notification")
                
                # Check updated participant count
                if len(client2.participants) == 1:
                    logger.info("✅ Participant count correctly updated")
                    self.test_results["participant_disconnect"] = {
                        "status": "✅ PASS",
                        "user_left_notification": True,
                        "participant_count_updated": True
                    }
                    return True
                else:
                    logger.error(f"❌ Participant count not updated. Expected: 1, Actual: {len(client2.participants)}")
                    return False
            else:
                logger.error("❌ Client2 did not receive user-left notification")
                self.test_results["participant_disconnect"] = {
                    "status": "❌ FAIL",
                    "user_left_notification": False
                }
                return False
                
        except Exception as e:
            logger.error(f"❌ Participant disconnect test error: {e}")
            self.test_results["participant_disconnect"] = {"status": "❌ FAIL", "error": str(e)}
            return False
    
    async def run_all_tests(self) -> bool:
        """Run all WebRTC tests."""
        logger.info("🚀 Starting Complete WebRTC Test Suite")
        logger.info("=" * 60)
        
        tests = [
            ("Server Health", self.test_server_health),
            ("User Creation & Authentication", self.test_user_creation_and_authentication),
            ("WebRTC Configuration", self.test_webrtc_config_endpoint),
            ("WebSocket Connections", self.test_websocket_connections),
            ("Room State & Participants", self.test_room_state_and_participants),
            ("WebRTC Signaling", self.test_webrtc_signaling),
            ("Participant Disconnect", self.test_participant_disconnect),
        ]
        
        passed = 0
        failed = 0
        
        try:
            for test_name, test_func in tests:
                logger.info(f"\n🧪 Running: {test_name}")
                logger.info("-" * 40)
                
                try:
                    # Run test with timeout
                    result = await asyncio.wait_for(
                        test_func(),
                        timeout=TEST_CONFIG["test_timeout"]
                    )
                    
                    if result:
                        logger.info(f"✅ {test_name} PASSED")
                        passed += 1
                    else:
                        logger.error(f"❌ {test_name} FAILED")
                        failed += 1
                        
                except asyncio.TimeoutError:
                    logger.error(f"⏰ {test_name} TIMED OUT")
                    self.test_results[test_name.lower().replace(" ", "_")] = {"status": "⏰ TIMEOUT"}
                    failed += 1
                    
                except Exception as e:
                    logger.error(f"💥 {test_name} ERROR: {e}")
                    self.test_results[test_name.lower().replace(" ", "_")] = {"status": "💥 ERROR", "error": str(e)}
                    failed += 1
            
            # Print final results
            logger.info("\n" + "=" * 60)
            logger.info("🎯 FINAL TEST RESULTS")
            logger.info("=" * 60)
            
            for test_name, result in self.test_results.items():
                logger.info(f"  {test_name}: {result['status']}")
            
            logger.info(f"\n📊 SUMMARY: {passed} passed, {failed} failed")
            
            if failed == 0:
                logger.info("🎉 ALL TESTS PASSED! WebRTC implementation is working correctly.")
                return True
            else:
                logger.error(f"❌ {failed} test(s) failed. WebRTC implementation needs attention.")
                return False
                
        finally:
            await self.cleanup()


async def main():
    """Main test execution."""
    print("🎥 WebRTC Complete Test with 2 Tokens")
    print("=" * 50)
    print()
    print("This test will:")
    print("  1. Create 2 test users")
    print("  2. Authenticate and get JWT tokens")
    print("  3. Test WebRTC configuration endpoint")
    print("  4. Connect both users via WebSocket")
    print("  5. Test WebRTC signaling (offer/answer/ICE)")
    print("  6. Test participant management")
    print("  7. Test disconnect handling")
    print()
    
    test_suite = WebRTCTestSuite()
    
    try:
        success = await test_suite.run_all_tests()
        
        if success:
            print("\n🎉 WebRTC test completed successfully!")
            print("✅ Both tokens work correctly")
            print("✅ WebRTC signaling is functional")
            print("✅ Room management works properly")
            return 0
        else:
            print("\n❌ WebRTC test failed!")
            print("🔍 Check the logs above for details")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        await test_suite.cleanup()
        return 1
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        await test_suite.cleanup()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)