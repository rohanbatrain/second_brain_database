#!/usr/bin/env python3
"""
WebRTC Signaling Test Client

This script demonstrates how to connect to the WebRTC signaling server
and exchange messages between multiple clients in a room.
"""

import asyncio
import json
import sys
from typing import Optional
from datetime import datetime

import websockets
from websockets.client import WebSocketClientProtocol


class WebRtcTestClient:
    """Simple WebRTC test client for signaling server."""
    
    def __init__(self, server_url: str, token: str, room_id: str, username: str):
        """
        Initialize test client.
        
        Args:
            server_url: WebSocket server URL (e.g., ws://localhost:8000)
            token: JWT authentication token
            room_id: Room identifier to join
            username: Display name for this client
        """
        self.server_url = server_url
        self.token = token
        self.room_id = room_id
        self.username = username
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.running = False
        
    async def connect(self):
        """Connect to the WebRTC signaling server."""
        # Build WebSocket URL with authentication token
        ws_url = f"{self.server_url}/webrtc/ws/{self.room_id}?token={self.token}"
        
        print(f"[{self.username}] Connecting to {ws_url}")
        
        try:
            self.websocket = await websockets.connect(ws_url)
            self.running = True
            print(f"[{self.username}] ✅ Connected to room {self.room_id}")
            
        except Exception as e:
            print(f"[{self.username}] ❌ Connection failed: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from the signaling server."""
        self.running = False
        if self.websocket:
            await self.websocket.close()
            print(f"[{self.username}] Disconnected")
    
    async def send_message(self, message_type: str, payload: dict):
        """
        Send a message to the signaling server.
        
        Args:
            message_type: Type of message (offer, answer, ice_candidate, etc.)
            payload: Message payload
        """
        if not self.websocket:
            raise RuntimeError("Not connected to signaling server")
        
        message = {
            "type": message_type,
            "payload": payload,
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        await self.websocket.send(json.dumps(message))
        print(f"[{self.username}] 📤 Sent {message_type}")
    
    async def receive_messages(self):
        """Receive and print messages from the signaling server."""
        if not self.websocket:
            raise RuntimeError("Not connected to signaling server")
        
        try:
            async for message_str in self.websocket:
                message = json.loads(message_str)
                msg_type = message.get("type")
                sender_id = message.get("sender_id", "server")
                
                print(f"[{self.username}] 📥 Received {msg_type} from {sender_id}")
                
                # Handle different message types
                if msg_type == "room_state":
                    payload = message.get("payload", {})
                    participants = payload.get("participants", [])
                    print(f"    Room has {len(participants)} participant(s): {participants}")
                    
                elif msg_type == "user_joined":
                    payload = message.get("payload", {})
                    joined_user = payload.get("username", payload.get("user_id"))
                    print(f"    User joined: {joined_user}")
                    
                elif msg_type == "user_left":
                    payload = message.get("payload", {})
                    left_user = payload.get("username", payload.get("user_id"))
                    print(f"    User left: {left_user}")
                    
                elif msg_type == "offer":
                    payload = message.get("payload", {})
                    print(f"    Received WebRTC offer (SDP type: {payload.get('type')})")
                    
                elif msg_type == "answer":
                    payload = message.get("payload", {})
                    print(f"    Received WebRTC answer (SDP type: {payload.get('type')})")
                    
                elif msg_type == "ice_candidate":
                    payload = message.get("payload", {})
                    print(f"    Received ICE candidate")
                    
                elif msg_type == "error":
                    payload = message.get("payload", {})
                    error_code = payload.get("code")
                    error_msg = payload.get("message")
                    print(f"    ⚠️  Error {error_code}: {error_msg}")
                    
        except websockets.exceptions.ConnectionClosed:
            print(f"[{self.username}] Connection closed")
        except Exception as e:
            print(f"[{self.username}] ❌ Error receiving messages: {e}")
    
    async def simulate_webrtc_offer(self, target_user_id: Optional[str] = None):
        """
        Simulate sending a WebRTC offer.
        
        Args:
            target_user_id: Optional target user ID for the offer
        """
        # Fake SDP offer (simplified for testing)
        sdp = "v=0\r\no=- 123456789 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n..."
        
        payload = {
            "type": "offer",
            "sdp": sdp
        }
        
        if target_user_id:
            payload["target_user_id"] = target_user_id
        
        await self.send_message("offer", payload)
    
    async def simulate_webrtc_answer(self, target_user_id: str):
        """
        Simulate sending a WebRTC answer.
        
        Args:
            target_user_id: Target user ID for the answer
        """
        # Fake SDP answer (simplified for testing)
        sdp = "v=0\r\no=- 987654321 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n..."
        
        payload = {
            "type": "answer",
            "sdp": sdp,
            "target_user_id": target_user_id
        }
        
        await self.send_message("answer", payload)
    
    async def simulate_ice_candidate(self, target_user_id: Optional[str] = None):
        """
        Simulate sending an ICE candidate.
        
        Args:
            target_user_id: Optional target user ID for the ICE candidate
        """
        payload = {
            "candidate": "candidate:1 1 UDP 2130706431 192.168.1.100 54321 typ host",
            "sdp_mid": "0",
            "sdp_m_line_index": 0
        }
        
        if target_user_id:
            payload["target_user_id"] = target_user_id
        
        await self.send_message("ice_candidate", payload)


async def run_single_client(server_url: str, token: str, room_id: str, username: str, duration: int = 10):
    """
    Run a single test client.
    
    Args:
        server_url: WebSocket server URL
        token: JWT authentication token
        room_id: Room to join
        username: Client username
        duration: How long to stay connected (seconds)
    """
    client = WebRtcTestClient(server_url, token, room_id, username)
    
    try:
        # Connect to server
        await client.connect()
        
        # Start receiving messages in background
        receive_task = asyncio.create_task(client.receive_messages())
        
        # Wait a bit for room state
        await asyncio.sleep(2)
        
        # Simulate some WebRTC signaling
        print(f"[{username}] Simulating WebRTC signaling...")
        await client.simulate_webrtc_offer()
        await asyncio.sleep(1)
        await client.simulate_ice_candidate()
        
        # Stay connected for specified duration
        await asyncio.sleep(duration - 3)
        
        # Cleanup
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass
        
        await client.disconnect()
        
    except Exception as e:
        print(f"[{username}] ❌ Test failed: {e}")
        raise


async def run_multiple_clients(server_url: str, token: str, room_id: str, num_clients: int = 3, duration: int = 15):
    """
    Run multiple test clients simultaneously.
    
    Args:
        server_url: WebSocket server URL
        token: JWT authentication token (same for all clients in this test)
        room_id: Room to join
        num_clients: Number of clients to simulate
        duration: How long to run the test (seconds)
    """
    print(f"\n{'='*60}")
    print(f"Running multi-client test with {num_clients} clients")
    print(f"Room: {room_id}")
    print(f"Duration: {duration} seconds")
    print(f"{'='*60}\n")
    
    # Create client tasks with staggered start times
    tasks = []
    for i in range(num_clients):
        username = f"TestUser{i+1}"
        # Stagger client connections by 2 seconds
        delay = i * 2
        
        async def delayed_client(delay_time, user):
            await asyncio.sleep(delay_time)
            await run_single_client(server_url, token, room_id, user, duration - delay_time)
        
        task = asyncio.create_task(delayed_client(delay, username))
        tasks.append(task)
    
    # Wait for all clients to finish
    try:
        await asyncio.gather(*tasks)
        print(f"\n✅ Multi-client test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Multi-client test failed: {e}")


async def main():
    """Main entry point for the test client."""
    # Configuration (update these values)
    SERVER_URL = "ws://localhost:8000"  # Your server URL
    TOKEN = "your_jwt_token_here"  # Get this from authentication
    ROOM_ID = "test-room-123"  # Room to join
    
    # Check if token is provided
    if TOKEN == "your_jwt_token_here":
        print("❌ Error: Please set your JWT token in the script")
        print("\nTo get a token:")
        print("1. Login to your account via the API")
        print("2. Copy the access_token from the response")
        print("3. Update the TOKEN variable in this script")
        sys.exit(1)
    
    # Run tests
    try:
        # Single client test
        print("\n" + "="*60)
        print("Single Client Test")
        print("="*60)
        await run_single_client(SERVER_URL, TOKEN, ROOM_ID, "TestUser1", duration=10)
        
        # Wait a bit between tests
        await asyncio.sleep(2)
        
        # Multi-client test
        await run_multiple_clients(SERVER_URL, TOKEN, ROOM_ID, num_clients=3, duration=15)
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
