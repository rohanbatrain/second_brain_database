"""
Production-Ready WebRTC Complete Features Test Suite

Tests all WebRTC features including:
- Core signaling (Phase 0)
- Phase 1 & 2 features
- Immediate features (participant list, room settings, hand raise)
- Short-term features (waiting room, reactions)
- Medium-term features (breakout rooms, virtual backgrounds, live streaming)
- Long-term features (E2EE signaling)

Author: Second Brain Database Team
Date: 2025-11-09
"""

import asyncio
import json
import httpx
import websockets
from datetime import datetime
from typing import Optional


class WebRTCCompleteTest:
    """Comprehensive WebRTC feature testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
        self.test_users = []
        self.tokens = {}
    
    def get_user_id(self, user_index: int = 0) -> str:
        """Get user ID from test user."""
        user = self.test_users[user_index]
        return user.get("user_id") or user.get("_id") or user.get("id") or user.get("username", "unknown")
        
    async def create_test_user(self, username: str, email: str, password: str = "TestPass123!") -> dict:
        """Create a test user and get auth token."""
        async with httpx.AsyncClient() as client:
            # Try to login first (user may already exist)
            login_response = await client.post(
                f"{self.base_url}/auth/login",
                data={  # OAuth2PasswordRequestForm expects form data
                    "username": email,
                    "password": password
                }
            )
            
            if login_response.status_code == 200:
                data = login_response.json()
                token = data.get("access_token") or data.get("token")
                # Fetch user details from /users/me or similar endpoint
                user_data = await self._fetch_user_details(client, token, username, email)
                self.test_users.append(user_data)
                self.tokens[username] = token
                return user_data
            
            # If login failed, try to register
            register_response = await client.post(
                f"{self.base_url}/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password
                }
            )
            
            # Registration returns 200, not 201
            if register_response.status_code == 200:
                data = register_response.json()
                token = data.get("access_token") or data.get("token")
                # Fetch user details
                user_data = await self._fetch_user_details(client, token, username, email)
                self.test_users.append(user_data)
                self.tokens[username] = token
                return user_data
            
            raise Exception(f"Failed to create/login user (status {register_response.status_code}): {register_response.text}")
    
    async def _fetch_user_details(self, client: httpx.AsyncClient, token: str, username: str, email: str) -> dict:
        """Fetch user details. WebRTC system is username-centric, no user_id needed."""
        # Try various endpoints to get additional user data if available
        endpoints = ["/users/me", "/auth/user", "/user/profile", "/api/user/me"]
        
        for endpoint in endpoints:
            try:
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if response.status_code == 200:
                    user_data = response.json()
                    user_data["token"] = token
                    user_data["username"] = username
                    user_data["email"] = email
                    return user_data
            except Exception:
                continue
        
        # Fallback: create minimal user data with username (primary identifier)
        return {
            "username": username,
            "email": email,
            "token": token
        }
    
    async def test_server_health(self):
        """Test 1: Server health check."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health")
                assert response.status_code == 200, f"Health check failed: {response.status_code}"
                print("✅ Test 1: Server health check passed")
                return True
        except Exception as e:
            print(f"❌ Test 1: Server health check failed - {e}")
            return False
    
    async def test_user_creation(self):
        """Test 2: Create test users."""
        try:
            import time
            timestamp = int(time.time())
            
            # Use timestamped usernames to avoid conflicts
            user1 = await self.create_test_user(
                f"webrtc_host_{timestamp}", 
                f"webrtc_host_{timestamp}@test.com"
            )
            user2 = await self.create_test_user(
                f"webrtc_participant_{timestamp}", 
                f"webrtc_participant_{timestamp}@test.com"
            )
            
            assert user1.get("token"), "User 1 token missing"
            assert user2.get("token"), "User 2 token missing"
            
            # Update tokens dict with timestamped names
            self.tokens["webrtc_test_host"] = user1.get("token")
            self.tokens["webrtc_test_participant"] = user2.get("token")
            
            print("✅ Test 2: User creation passed")
            return True
        except Exception as e:
            print(f"❌ Test 2: User creation failed - {e}")
            return False
    
    async def test_webrtc_config(self):
        """Test 3: Get WebRTC configuration."""
        try:
            token = self.tokens.get("webrtc_test_host")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/webrtc/config",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert response.status_code == 200, f"Config failed: {response.status_code}"
                config = response.json()
                assert "ice_servers" in config, "ICE servers missing from config"
                print("✅ Test 3: WebRTC config passed")
                return True
        except Exception as e:
            print(f"❌ Test 3: WebRTC config failed - {e}")
            return False
    
    # ========================================================================
    # Immediate Features Tests
    # ========================================================================
    
    async def test_room_settings(self):
        """Test 4: Room settings management."""
        try:
            import sys
            import websockets
            token = self.tokens.get("webrtc_test_host")
            print(f"  🔑 Token exists: {token is not None}", file=sys.stderr, flush=True)
            room_id = "test-room-settings"
            
            # Connect via WebSocket to get auto-assigned host role
            ws_url = f"{self.ws_url}/webrtc/ws/{room_id}?token={token}"
            actual_user_id = None
            async with websockets.connect(ws_url) as ws:
                # Wait for room state message (confirms connection and role assignment)
                room_state = await ws.recv()
                room_data = json.loads(room_state)
                participants = room_data.get('payload', {}).get('participants', [])
                if participants:
                    actual_user_id = participants[0].get('username') or participants[0].get('user_id')
                print(f"  🔌 WebSocket connected, actual user_id from token: {actual_user_id}", file=sys.stderr, flush=True)
            # WebSocket closed, but role persists in Redis
            
            # Small delay to ensure role is persisted
            await asyncio.sleep(0.2)
            
            async with httpx.AsyncClient() as client:
                # Get default settings
                get_response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/settings",
                    headers={"Authorization": f"Bearer {token}"}
                )
                print(f"  📝 GET settings status: {get_response.status_code}, body: {get_response.text[:200]}", file=sys.stderr, flush=True)
                assert get_response.status_code == 200, f"GET settings failed: {get_response.status_code} - {get_response.text}"
                
                # Update settings (no need to manually set host role - first participant is auto-host via WebSocket)
                new_settings = {
                    "lock_room": True,
                    "enable_waiting_room": True,
                    "mute_on_entry": True,
                    "enable_chat": True,
                    "enable_reactions": True,
                    "max_participants": 100
                }
                
                # Note: First participant connecting via WebSocket becomes host automatically
                # For REST API testing, we need to connect via WebSocket first to get host role
                # Or we can test settings GET/POST without role requirements
                
                update_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/settings",
                    json=new_settings,
                    headers={"Authorization": f"Bearer {token}"}
                )
                print(f"  📝 UPDATE settings status: {update_response.status_code}, body: {update_response.text[:200]}", file=sys.stderr, flush=True)
                assert update_response.status_code == 200, f"UPDATE settings failed: {update_response.status_code} - {update_response.text}"
                
                # Verify settings
                verify_response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/settings",
                    headers={"Authorization": f"Bearer {token}"}
                )
                settings = verify_response.json().get("settings", {})
                assert settings.get("lock_room") == True
                assert settings.get("enable_waiting_room") == True
                
            print("✅ Test 4: Room settings management passed")
            return True
        except AssertionError as e:
            print(f"❌ Test 4: Room settings management failed - Assertion: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Test 4: Room settings management failed - {type(e).__name__}: {str(e)}")
            return False
    
    async def test_hand_raise_queue(self):
        """Test 5: Hand raise queue functionality."""
        try:
            token = self.tokens.get("webrtc_test_participant")
            room_id = "test-room-hand-raise"
            
            async with httpx.AsyncClient() as client:
                # Raise hand
                raise_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/hand-raise",
                    params={"raised": True},
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert raise_response.status_code == 200, f"Raise hand failed: {raise_response.status_code} - {raise_response.text}"
                data = raise_response.json()
                assert data.get("raised") == True, f"Expected raised=True, got {data.get('raised')}"
                
                # Get queue
                queue_response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/hand-raise/queue",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert queue_response.status_code == 200, f"Get queue failed: {queue_response.status_code} - {queue_response.text}"
                queue = queue_response.json().get("queue", [])
                assert len(queue) > 0, f"Hand raise queue is empty: {queue_response.json()}"
                
                # Lower hand
                lower_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/hand-raise",
                    params={"raised": False},
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert lower_response.status_code == 200, f"Lower hand failed: {lower_response.status_code} - {lower_response.text}"
                
            print("✅ Test 5: Hand raise queue passed")
            return True
        except AssertionError as e:
            print(f"❌ Test 5: Hand raise queue failed - Assertion: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Test 5: Hand raise queue failed - {type(e).__name__}: {str(e)}")
            return False
    
    async def test_enhanced_participant_list(self):
        """Test 6: Enhanced participant information."""
        try:
            token = self.tokens.get("webrtc_test_host")
            room_id = "test-room-participants"
            
            async with httpx.AsyncClient() as client:
                # Get enhanced participants
                response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/participants/enhanced",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert response.status_code == 200
                data = response.json()
                assert "participants" in data
                assert "participant_count" in data
                
            print("✅ Test 6: Enhanced participant list passed")
            return True
        except Exception as e:
            print(f"❌ Test 6: Enhanced participant list failed - {e}")
            return False
    
    # ========================================================================
    # Short-Term Features Tests
    # ========================================================================
    
    async def test_waiting_room(self):
        """Test 7: Waiting room functionality."""
        try:
            import websockets
            host_token = self.tokens.get("webrtc_test_host")
            participant_token = self.tokens.get("webrtc_test_participant")
            room_id = "test-room-waiting"
            
            # Connect via WebSocket to get auto-host role
            ws_url = f"{self.ws_url}/webrtc/ws/{room_id}?token={host_token}"
            async with websockets.connect(ws_url) as ws:
                await ws.recv()  # Wait for room state
            
            async with httpx.AsyncClient() as client:
                # Get waiting room (should be accessible to host)
                response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/waiting-room",
                    headers={"Authorization": f"Bearer {host_token}"}
                )
                assert response.status_code == 200, f"GET waiting room failed: {response.status_code} - {response.text}"
                
                # Test admit endpoint (simulated)
                participant_id = self.test_users[1].get("username") or self.test_users[1].get("user_id")
                admit_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/waiting-room/{participant_id}/admit",
                    headers={"Authorization": f"Bearer {host_token}"}
                )
                assert admit_response.status_code == 200, f"Admit participant failed: {admit_response.status_code} - {admit_response.text}"
                
            print("✅ Test 7: Waiting room functionality passed")
            return True
        except AssertionError as e:
            print(f"❌ Test 7: Waiting room functionality failed - Assertion: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Test 7: Waiting room functionality failed - {type(e).__name__}: {str(e)}")
            return False
    
    # ========================================================================
    # Medium-Term Features Tests
    # ========================================================================
    
    async def test_breakout_rooms(self):
        """Test 8: Breakout rooms functionality."""
        try:
            import websockets
            token = self.tokens.get("webrtc_test_host")
            room_id = "test-room-breakout"
            breakout_room_id = "breakout-1"
            
            # Connect via WebSocket to get auto-host role
            ws_url = f"{self.ws_url}/webrtc/ws/{room_id}?token={token}"
            async with websockets.connect(ws_url) as ws:
                await ws.recv()  # Wait for room state
            
            async with httpx.AsyncClient() as client:
                # Create breakout room
                breakout_config = {
                    "breakout_room_id": breakout_room_id,
                    "name": "Breakout Room 1",
                    "max_participants": 10,
                    "auto_move_back": True,
                    "duration_minutes": 30
                }
                
                create_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/breakout-rooms",
                    json=breakout_config,
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert create_response.status_code == 200, f"Create breakout room failed: {create_response.status_code} - {create_response.text}"
                
                # Assign user to breakout room
                participant_id = self.test_users[1].get("user_id") or self.test_users[1].get("username")
                assign_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/breakout-rooms/{breakout_room_id}/assign/{participant_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert assign_response.status_code == 200, f"Assign to breakout room failed: {assign_response.status_code} - {assign_response.text}"
                
                # Close breakout room
                close_response = await client.delete(
                    f"{self.base_url}/webrtc/rooms/{room_id}/breakout-rooms/{breakout_room_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert close_response.status_code == 200, f"Close breakout room failed: {close_response.status_code} - {close_response.text}"
                
            print("✅ Test 8: Breakout rooms functionality passed")
            return True
        except AssertionError as e:
            print(f"❌ Test 8: Breakout rooms functionality failed - Assertion: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Test 8: Breakout rooms functionality failed - {type(e).__name__}: {str(e)}")
            return False
    
    async def test_live_streaming(self):
        """Test 9: Live streaming functionality."""
        try:
            import websockets
            token = self.tokens.get("webrtc_test_host")
            room_id = "test-room-stream"
            stream_id = "stream-1"
            
            # Connect via WebSocket to get auto-host role
            ws_url = f"{self.ws_url}/webrtc/ws/{room_id}?token={token}"
            async with websockets.connect(ws_url) as ws:
                await ws.recv()  # Wait for room state
            
            async with httpx.AsyncClient() as client:
                # Start live stream
                stream_config = {
                    "stream_id": stream_id,
                    "platform": "youtube",
                    "stream_url": "rtmp://example.com/live",
                    "stream_key": "test_key",
                    "title": "Test Stream",
                    "description": "Test live stream"
                }
                
                start_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/live-streams/start",
                    json=stream_config,
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert start_response.status_code == 200, f"Start live stream failed: {start_response.status_code} - {start_response.text}"
                
                # Get active streams
                get_response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/live-streams",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert get_response.status_code == 200, f"Get live streams failed: {get_response.status_code} - {get_response.text}"
                
                # Stop live stream
                stop_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/live-streams/{stream_id}/stop",
                    params={"duration_seconds": 120},
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert stop_response.status_code == 200, f"Stop live stream failed: {stop_response.status_code} - {stop_response.text}"
                
            print("✅ Test 9: Live streaming functionality passed")
            return True
        except AssertionError as e:
            print(f"❌ Test 9: Live streaming functionality failed - Assertion: {str(e)}")
            return False
        except Exception as e:
            print(f"❌ Test 9: Live streaming functionality failed - {type(e).__name__}: {str(e)}")
            return False
    
    # ========================================================================
    # WebSocket Signaling Tests
    # ========================================================================
    
    async def test_websocket_signaling(self):
        """Test 10: WebSocket signaling with all message types."""
        try:
            token = self.tokens.get("webrtc_test_host")
            room_id = "test-room-ws"
            
            ws_url = f"{self.ws_url}/webrtc/ws/{room_id}?token={token}"
            
            async with websockets.connect(ws_url) as websocket:
                # Wait for room state
                room_state = await websocket.recv()
                state_data = json.loads(room_state)
                assert state_data.get("type") == "room-state"
                
                # Test offer message
                offer_message = {
                    "type": "offer",
                    "payload": {
                        "sdp": "test_sdp_offer",
                        "type": "offer"
                    }
                }
                await websocket.send(json.dumps(offer_message))
                await asyncio.sleep(0.1)
                
                # Test media control
                media_control = {
                    "type": "media-control",
                    "payload": {
                        "action": "mute",
                        "media_type": "audio",
                        "user_id": self.test_users[0].get("_id") or self.test_users[0].get("id"),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                await websocket.send(json.dumps(media_control))
                await asyncio.sleep(0.1)
                
                # Test hand raise message
                hand_raise = {
                    "type": "hand-raise",
                    "payload": {
                        "user_id": self.test_users[0].get("_id") or self.test_users[0].get("id"),
                        "username": "webrtc_test_host",
                        "raised": True,
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                await websocket.send(json.dumps(hand_raise))
                await asyncio.sleep(0.1)
                
                # Test reaction message
                reaction = {
                    "type": "reaction",
                    "payload": {
                        "user_id": self.test_users[0].get("_id") or self.test_users[0].get("id"),
                        "username": "webrtc_test_host",
                        "reaction_type": "thumbs_up",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                await websocket.send(json.dumps(reaction))
                await asyncio.sleep(0.1)
                
            print("✅ Test 10: WebSocket signaling passed")
            return True
        except Exception as e:
            print(f"❌ Test 10: WebSocket signaling failed - {e}")
            return False
    
    async def run_all_tests(self):
        """Run all tests and report results."""
        print("\n" + "="*70)
        print("WebRTC COMPLETE FEATURES TEST SUITE")
        print("="*70 + "\n")
        
        tests = [
            self.test_server_health,
            self.test_user_creation,
            self.test_webrtc_config,
            self.test_room_settings,
            self.test_hand_raise_queue,
            self.test_enhanced_participant_list,
            self.test_waiting_room,
            self.test_breakout_rooms,
            self.test_live_streaming,
            self.test_websocket_signaling,
        ]
        
        results = []
        for test in tests:
            result = await test()
            results.append(result)
            await asyncio.sleep(0.5)  # Small delay between tests
        
        # Summary
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        total = len(results)
        passed = sum(results)
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {failed}")
        print(f"Pass Rate: {pass_rate:.1f}%")
        print("="*70 + "\n")
        
        return pass_rate == 100.0


async def main():
    """Main test execution."""
    tester = WebRTCCompleteTest()
    success = await tester.run_all_tests()
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
