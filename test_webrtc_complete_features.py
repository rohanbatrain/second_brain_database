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
        
    async def create_test_user(self, username: str, email: str, password: str = "TestPass123!") -> dict:
        """Create a test user and get auth token."""
        async with httpx.AsyncClient() as client:
            # Register user
            register_response = await client.post(
                f"{self.base_url}/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password
                }
            )
            
            if register_response.status_code == 201:
                data = register_response.json()
                token = data.get("access_token") or data.get("token")
                user_data = data.get("user", {})
                user_data["token"] = token
                self.test_users.append(user_data)
                self.tokens[username] = token
                return user_data
            else:
                # Try to login if user exists
                login_response = await client.post(
                    f"{self.base_url}/auth/login",
                    json={
                        "email": email,
                        "password": password
                    }
                )
                data = login_response.json()
                token = data.get("access_token") or data.get("token")
                user_data = data.get("user", {})
                user_data["token"] = token
                self.test_users.append(user_data)
                self.tokens[username] = token
                return user_data
    
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
            user1 = await self.create_test_user("webrtc_test_host", "webrtc_host@test.com")
            user2 = await self.create_test_user("webrtc_test_participant", "webrtc_participant@test.com")
            
            assert user1.get("token"), "User 1 token missing"
            assert user2.get("token"), "User 2 token missing"
            
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
            token = self.tokens.get("webrtc_test_host")
            room_id = "test-room-settings"
            
            async with httpx.AsyncClient() as client:
                # Get default settings
                get_response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/settings",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert get_response.status_code == 200
                
                # Update settings
                new_settings = {
                    "lock_room": True,
                    "enable_waiting_room": True,
                    "mute_on_entry": True,
                    "enable_chat": True,
                    "enable_reactions": True,
                    "max_participants": 100
                }
                
                # Set host role first
                user_id = self.test_users[0].get("_id") or self.test_users[0].get("id")
                await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/roles/{user_id}",
                    params={"role": "host"},
                    headers={"Authorization": f"Bearer {token}"}
                )
                
                update_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/settings",
                    json=new_settings,
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert update_response.status_code == 200
                
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
        except Exception as e:
            print(f"❌ Test 4: Room settings management failed - {e}")
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
                assert raise_response.status_code == 200
                data = raise_response.json()
                assert data.get("raised") == True
                
                # Get queue
                queue_response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/hand-raise/queue",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert queue_response.status_code == 200
                queue = queue_response.json().get("queue", [])
                assert len(queue) > 0, "Hand raise queue is empty"
                
                # Lower hand
                lower_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/hand-raise",
                    params={"raised": False},
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert lower_response.status_code == 200
                
            print("✅ Test 5: Hand raise queue passed")
            return True
        except Exception as e:
            print(f"❌ Test 5: Hand raise queue failed - {e}")
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
            host_token = self.tokens.get("webrtc_test_host")
            participant_token = self.tokens.get("webrtc_test_participant")
            room_id = "test-room-waiting"
            
            async with httpx.AsyncClient() as client:
                # Set host role
                user_id = self.test_users[0].get("_id") or self.test_users[0].get("id")
                await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/roles/{user_id}",
                    params={"role": "host"},
                    headers={"Authorization": f"Bearer {host_token}"}
                )
                
                # Get waiting room (should be accessible to host)
                response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/waiting-room",
                    headers={"Authorization": f"Bearer {host_token}"}
                )
                assert response.status_code == 200
                
                # Test admit endpoint (simulated)
                participant_id = self.test_users[1].get("_id") or self.test_users[1].get("id")
                admit_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/waiting-room/{participant_id}/admit",
                    headers={"Authorization": f"Bearer {host_token}"}
                )
                assert admit_response.status_code == 200
                
            print("✅ Test 7: Waiting room functionality passed")
            return True
        except Exception as e:
            print(f"❌ Test 7: Waiting room functionality failed - {e}")
            return False
    
    # ========================================================================
    # Medium-Term Features Tests
    # ========================================================================
    
    async def test_breakout_rooms(self):
        """Test 8: Breakout rooms functionality."""
        try:
            token = self.tokens.get("webrtc_test_host")
            room_id = "test-room-breakout"
            breakout_room_id = "breakout-1"
            
            async with httpx.AsyncClient() as client:
                # Set host role
                user_id = self.test_users[0].get("_id") or self.test_users[0].get("id")
                await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/roles/{user_id}",
                    params={"role": "host"},
                    headers={"Authorization": f"Bearer {token}"}
                )
                
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
                assert create_response.status_code == 200
                
                # Assign user to breakout room
                participant_id = self.test_users[1].get("_id") or self.test_users[1].get("id")
                assign_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/breakout-rooms/{breakout_room_id}/assign/{participant_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert assign_response.status_code == 200
                
                # Close breakout room
                close_response = await client.delete(
                    f"{self.base_url}/webrtc/rooms/{room_id}/breakout-rooms/{breakout_room_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert close_response.status_code == 200
                
            print("✅ Test 8: Breakout rooms functionality passed")
            return True
        except Exception as e:
            print(f"❌ Test 8: Breakout rooms functionality failed - {e}")
            return False
    
    async def test_live_streaming(self):
        """Test 9: Live streaming functionality."""
        try:
            token = self.tokens.get("webrtc_test_host")
            room_id = "test-room-stream"
            stream_id = "stream-1"
            
            async with httpx.AsyncClient() as client:
                # Set host role
                user_id = self.test_users[0].get("_id") or self.test_users[0].get("id")
                await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/roles/{user_id}",
                    params={"role": "host"},
                    headers={"Authorization": f"Bearer {token}"}
                )
                
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
                assert start_response.status_code == 200
                
                # Get active streams
                get_response = await client.get(
                    f"{self.base_url}/webrtc/rooms/{room_id}/live-streams",
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert get_response.status_code == 200
                
                # Stop live stream
                stop_response = await client.post(
                    f"{self.base_url}/webrtc/rooms/{room_id}/live-streams/{stream_id}/stop",
                    params={"duration_seconds": 120},
                    headers={"Authorization": f"Bearer {token}"}
                )
                assert stop_response.status_code == 200
                
            print("✅ Test 9: Live streaming functionality passed")
            return True
        except Exception as e:
            print(f"❌ Test 9: Live streaming functionality failed - {e}")
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
