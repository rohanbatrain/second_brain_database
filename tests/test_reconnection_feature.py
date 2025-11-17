#!/usr/bin/env python3
"""
Test script for WebRTC Reconnection & State Recovery feature.

Tests:
1. Message buffering
2. Reconnection detection
3. Missed message replay
4. State tracking
5. Connection quality detection
6. Room cleanup
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from datetime import datetime, timezone
from second_brain_database.webrtc.reconnection import reconnection_manager
from second_brain_database.webrtc.schemas import WebRtcMessage, MessageType
from second_brain_database.managers.redis_manager import redis_manager


async def test_message_buffering():
    """Test message buffering functionality."""
    print("\n🧪 Test 1: Message Buffering")
    print("=" * 60)
    
    room_id = "test_room_buffer"
    
    # Buffer some messages
    messages = [
        WebRtcMessage(type=MessageType.CHAT_MESSAGE, payload={"content": "Hello"}, room_id=room_id),
        WebRtcMessage(type=MessageType.CHAT_MESSAGE, payload={"content": "World"}, room_id=room_id),
        WebRtcMessage(type=MessageType.OFFER, payload={"sdp": "test_sdp", "type": "offer"}, room_id=room_id),
    ]
    
    for i, msg in enumerate(messages, 1):
        await reconnection_manager.buffer_message(room_id, msg)
        print(f"  ✓ Buffered message {i}: {msg.payload.get('content', msg.type)}")
    
    # Retrieve messages
    retrieved = await reconnection_manager.get_missed_messages(room_id, last_sequence=0)
    
    if len(retrieved) == len(messages):
        print(f"\n✅ SUCCESS: Retrieved {len(retrieved)} messages")
        return True
    else:
        print(f"\n❌ FAILED: Expected {len(messages)}, got {len(retrieved)}")
        return False


async def test_reconnection_detection():
    """Test reconnection detection."""
    print("\n🧪 Test 2: Reconnection Detection")
    print("=" * 60)
    
    room_id = "test_room_reconnect"
    user_id = "test_user"
    
    # Simulate first connection
    await reconnection_manager.track_user_state(room_id, user_id, is_connected=True)
    print(f"  ✓ Tracked initial connection for {user_id}")
    
    # Simulate disconnection
    await reconnection_manager.track_user_state(room_id, user_id, is_connected=False)
    print(f"  ✓ Tracked disconnection for {user_id}")
    
    # Small delay to simulate time passing
    await asyncio.sleep(0.1)
    
    # Simulate reconnection
    reconnect_info = await reconnection_manager.handle_reconnect(room_id, user_id)
    
    if reconnect_info.get("is_reconnect"):
        print(f"\n✅ SUCCESS: Reconnection detected!")
        print(f"  - Disconnect duration: {reconnect_info.get('disconnect_duration_seconds')}s")
        return True
    else:
        print(f"\n❌ FAILED: Reconnection not detected")
        return False


async def test_missed_message_replay():
    """Test missed message replay."""
    print("\n🧪 Test 3: Missed Message Replay")
    print("=" * 60)
    
    room_id = "test_room_replay"
    user_id = "test_user_replay"
    
    # User connects first time
    await reconnection_manager.track_user_state(room_id, user_id, is_connected=True)
    
    # Get initial sequence
    state = await reconnection_manager.get_user_state(room_id, user_id)
    initial_seq = state.get("last_sequence", 0)
    print(f"  ✓ Initial sequence: {initial_seq}")
    
    # User disconnects
    await reconnection_manager.track_user_state(room_id, user_id, is_connected=False)
    
    # Buffer messages while user is offline
    offline_messages = [
        WebRtcMessage(type=MessageType.CHAT_MESSAGE, payload={"content": "Message 1"}, room_id=room_id),
        WebRtcMessage(type=MessageType.CHAT_MESSAGE, payload={"content": "Message 2"}, room_id=room_id),
        WebRtcMessage(type=MessageType.CHAT_MESSAGE, payload={"content": "Message 3"}, room_id=room_id),
    ]
    
    for msg in offline_messages:
        await reconnection_manager.buffer_message(room_id, msg)
    
    print(f"  ✓ Buffered {len(offline_messages)} messages while offline")
    
    # User reconnects
    reconnect_info = await reconnection_manager.handle_reconnect(room_id, user_id)
    missed = reconnect_info.get("missed_messages", [])
    
    if len(missed) == len(offline_messages):
        print(f"\n✅ SUCCESS: Retrieved {len(missed)} missed messages")
        for i, msg in enumerate(missed, 1):
            content = msg['message'].get('payload', {}).get('content', 'N/A')
            print(f"  {i}. {content}")
        return True
    else:
        print(f"\n❌ FAILED: Expected {len(offline_messages)} missed messages, got {len(missed)}")
        return False


async def test_connection_quality():
    """Test connection quality detection."""
    print("\n🧪 Test 4: Connection Quality Detection")
    print("=" * 60)
    
    room_id = "test_room_quality"
    user_id = "test_user_quality"
    
    # Track user first
    await reconnection_manager.track_user_state(room_id, user_id, is_connected=True)
    
    # Test good connection
    good_metrics = {"latency_ms": 50, "packet_loss_percent": 0.5, "jitter_ms": 10}
    quality = await reconnection_manager.detect_connection_quality(room_id, user_id, good_metrics)
    print(f"  ✓ Good connection (50ms latency): {quality}")
    
    # Test fair connection
    fair_metrics = {"latency_ms": 180, "packet_loss_percent": 2.5, "jitter_ms": 35}
    quality = await reconnection_manager.detect_connection_quality(room_id, user_id, fair_metrics)
    print(f"  ✓ Fair connection (180ms latency): {quality}")
    
    # Test poor connection
    poor_metrics = {"latency_ms": 400, "packet_loss_percent": 8, "jitter_ms": 80}
    quality = await reconnection_manager.detect_connection_quality(room_id, user_id, poor_metrics)
    print(f"  ✓ Poor connection (400ms latency): {quality}")
    
    if quality == "poor":
        print(f"\n✅ SUCCESS: Connection quality detection working")
        return True
    else:
        print(f"\n❌ FAILED: Expected 'poor', got '{quality}'")
        return False


async def test_room_cleanup():
    """Test room cleanup functionality."""
    print("\n🧪 Test 5: Room Cleanup")
    print("=" * 60)
    
    room_id = "test_room_cleanup"
    
    # Create some state
    msg1 = WebRtcMessage(type=MessageType.CHAT_MESSAGE, payload={"content": "test 1"}, room_id=room_id)
    msg2 = WebRtcMessage(type=MessageType.CHAT_MESSAGE, payload={"content": "test 2"}, room_id=room_id)
    await reconnection_manager.buffer_message(room_id, msg1)
    await reconnection_manager.buffer_message(room_id, msg2)
    await reconnection_manager.track_user_state(room_id, "user1", is_connected=True)
    await reconnection_manager.track_user_state(room_id, "user2", is_connected=True)
    
    print(f"  ✓ Created state for room {room_id}")
    
    # Cleanup
    await reconnection_manager.cleanup_room(room_id)
    print(f"  ✓ Cleaned up room {room_id}")
    
    # Verify cleanup
    messages = await reconnection_manager.get_missed_messages(room_id, last_sequence=0)
    state1 = await reconnection_manager.get_user_state(room_id, "user1")
    
    if len(messages) == 0 and state1 is None:
        print(f"\n✅ SUCCESS: Room cleaned up successfully")
        return True
    else:
        print(f"\n❌ FAILED: Cleanup incomplete (messages: {len(messages)}, state: {state1 is not None})")
        return False


async def test_buffer_limit():
    """Test that buffer respects 50-message limit."""
    print("\n🧪 Test 6: Buffer Size Limit (50 messages)")
    print("=" * 60)
    
    room_id = "test_room_limit"
    
    # Buffer 60 messages
    for i in range(60):
        msg = WebRtcMessage(
            type=MessageType.CHAT_MESSAGE,
            payload={"content": f"Message {i}"},
            room_id=room_id
        )
        await reconnection_manager.buffer_message(room_id, msg)
    
    print(f"  ✓ Buffered 60 messages")
    
    # Should only keep last 50
    messages = await reconnection_manager.get_missed_messages(room_id, last_sequence=0)
    
    if len(messages) == 50:
        print(f"\n✅ SUCCESS: Buffer limited to 50 messages (oldest discarded)")
        print(f"  - First message seq: {messages[0].get('sequence')}")
        print(f"  - Last message seq: {messages[-1].get('sequence')}")
        return True
    else:
        print(f"\n❌ FAILED: Expected 50 messages, got {len(messages)}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("🚀 WebRTC Reconnection Feature Test Suite")
    print("=" * 60)
    
    try:
        # Initialize Redis connection
        await redis_manager.get_redis()
        print("✓ Redis connection established")
        
        # Run tests
        results = []
        results.append(await test_message_buffering())
        results.append(await test_reconnection_detection())
        results.append(await test_missed_message_replay())
        results.append(await test_connection_quality())
        results.append(await test_room_cleanup())
        results.append(await test_buffer_limit())
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(results)
        total = len(results)
        
        print(f"\nPassed: {passed}/{total} tests")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! Reconnection feature is working correctly.")
            print("\n📋 Feature Complete:")
            print("  ✓ Message buffering (50 messages, 5-min TTL)")
            print("  ✓ Reconnection detection")
            print("  ✓ Missed message replay")
            print("  ✓ Connection quality monitoring")
            print("  ✓ Room cleanup")
            print("  ✓ Buffer size limiting")
            return 0
        else:
            print(f"\n⚠️  {total - passed} test(s) failed")
            return 1
            
    except Exception as e:
        print(f"\n❌ TEST SUITE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # Cleanup test data
        print("\n🧹 Cleaning up test data...")
        test_rooms = [
            "test_room_buffer",
            "test_room_reconnect", 
            "test_room_replay",
            "test_room_quality",
            "test_room_cleanup",
            "test_room_limit"
        ]
        for room in test_rooms:
            try:
                await reconnection_manager.cleanup_room(room)
            except:
                pass
        print("✓ Cleanup complete")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
