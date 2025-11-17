"""
Test Suite for WebRTC Recording Feature

Tests:
1. Start Recording
2. Stop Recording
3. Pause/Resume Recording
4. Cancel Recording
5. Recording Status
6. Concurrent Recording Limits
7. Room Recordings
8. User Recordings
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.webrtc.recording import (
    recording_manager,
    RecordingStatus,
    RecordingFormat,
    RecordingQuality
)
from second_brain_database.managers.redis_manager import redis_manager


class TestRecordingFeature:
    """Test recording feature."""
    
    def __init__(self):
        self.test_room_id = "test_room_recording"
        self.test_user_id = "test_user_recording"
        self.test_user_id_2 = "test_user_recording_2"
        self.recording_ids = []
    
    async def cleanup(self):
        """Cleanup test data."""
        try:
            # Cancel all test recordings
            for recording_id in self.recording_ids:
                try:
                    await recording_manager.cancel_recording(
                        recording_id=recording_id,
                        user_id=self.test_user_id
                    )
                except:
                    pass
            
            # Clear Redis test data
            redis_client = await redis_manager.get_redis()
            
            # Clear room recordings
            room_key = f"{recording_manager.ROOM_RECORDINGS_PREFIX}{self.test_room_id}"
            await redis_client.delete(room_key)
            
            # Clear user recordings
            user_key = f"{recording_manager.USER_RECORDINGS_PREFIX}{self.test_user_id}"
            await redis_client.delete(user_key)
            
            user_key_2 = f"{recording_manager.USER_RECORDINGS_PREFIX}{self.test_user_id_2}"
            await redis_client.delete(user_key_2)
            
            # Clear active recordings
            for recording_id in self.recording_ids:
                await redis_client.srem(recording_manager.ACTIVE_RECORDINGS_PREFIX, recording_id)
            
            # Clear recording states
            for recording_id in self.recording_ids:
                state_key = f"{recording_manager.RECORDING_STATE_PREFIX}{recording_id}"
                await redis_client.delete(state_key)
            
            print("✅ Cleanup completed")
            
        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")
    
    async def test_start_recording(self):
        """Test 1: Start Recording"""
        print("\n🧪 Test 1: Start Recording")
        
        try:
            recording_state = await recording_manager.start_recording(
                room_id=self.test_room_id,
                user_id=self.test_user_id,
                recording_format=RecordingFormat.WEBM,
                quality=RecordingQuality.MEDIUM
            )
            
            self.recording_ids.append(recording_state["recording_id"])
            
            assert recording_state["room_id"] == self.test_room_id
            assert recording_state["user_id"] == self.test_user_id
            assert recording_state["format"] == RecordingFormat.WEBM
            assert recording_state["quality"] == RecordingQuality.MEDIUM
            assert recording_state["status"] == RecordingStatus.RECORDING
            assert recording_state["started_at"] is not None
            assert recording_state["local_path"] is not None
            
            print(f"   Recording ID: {recording_state['recording_id']}")
            print(f"   Format: {recording_state['format']}")
            print(f"   Quality: {recording_state['quality']}")
            print(f"   Status: {recording_state['status']}")
            print("✅ Test 1 PASSED: Recording started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Test 1 FAILED: {e}")
            return False
    
    async def test_stop_recording(self):
        """Test 2: Stop Recording"""
        print("\n🧪 Test 2: Stop Recording")
        
        try:
            # Start a recording
            recording_state = await recording_manager.start_recording(
                room_id=self.test_room_id,
                user_id=self.test_user_id
            )
            
            recording_id = recording_state["recording_id"]
            self.recording_ids.append(recording_id)
            
            # Wait a bit
            await asyncio.sleep(1)
            
            # Stop recording
            stopped_state = await recording_manager.stop_recording(
                recording_id=recording_id,
                user_id=self.test_user_id
            )
            
            assert stopped_state["status"] == RecordingStatus.PROCESSING
            assert stopped_state["stopped_at"] is not None
            assert stopped_state["duration_seconds"] > 0
            
            print(f"   Recording ID: {recording_id}")
            print(f"   Duration: {stopped_state['duration_seconds']:.2f}s")
            print(f"   Status: {stopped_state['status']}")
            print("✅ Test 2 PASSED: Recording stopped successfully")
            return True
            
        except Exception as e:
            print(f"❌ Test 2 FAILED: {e}")
            return False
    
    async def test_pause_resume_recording(self):
        """Test 3: Pause/Resume Recording"""
        print("\n🧪 Test 3: Pause/Resume Recording")
        
        try:
            # Start a recording
            recording_state = await recording_manager.start_recording(
                room_id=self.test_room_id,
                user_id=self.test_user_id
            )
            
            recording_id = recording_state["recording_id"]
            self.recording_ids.append(recording_id)
            
            # Pause recording
            paused_state = await recording_manager.pause_recording(
                recording_id=recording_id,
                user_id=self.test_user_id
            )
            
            assert paused_state["status"] == RecordingStatus.PAUSED
            assert paused_state["paused_at"] is not None
            
            print(f"   Recording paused: {recording_id}")
            
            # Resume recording
            resumed_state = await recording_manager.resume_recording(
                recording_id=recording_id,
                user_id=self.test_user_id
            )
            
            assert resumed_state["status"] == RecordingStatus.RECORDING
            assert resumed_state["resumed_at"] is not None
            
            print(f"   Recording resumed: {recording_id}")
            print("✅ Test 3 PASSED: Pause/resume works correctly")
            return True
            
        except Exception as e:
            print(f"❌ Test 3 FAILED: {e}")
            return False
    
    async def test_cancel_recording(self):
        """Test 4: Cancel Recording"""
        print("\n🧪 Test 4: Cancel Recording")
        
        try:
            # Start a recording
            recording_state = await recording_manager.start_recording(
                room_id=self.test_room_id,
                user_id=self.test_user_id
            )
            
            recording_id = recording_state["recording_id"]
            self.recording_ids.append(recording_id)
            
            # Cancel recording
            cancelled_state = await recording_manager.cancel_recording(
                recording_id=recording_id,
                user_id=self.test_user_id
            )
            
            assert cancelled_state["status"] == RecordingStatus.CANCELLED
            assert cancelled_state["stopped_at"] is not None
            
            # Verify cleanup
            recording_dir = Path(recording_state["local_path"])
            assert not recording_dir.exists(), "Recording directory should be cleaned up"
            
            print(f"   Recording cancelled: {recording_id}")
            print(f"   Directory cleaned: {recording_dir}")
            print("✅ Test 4 PASSED: Recording cancelled and cleaned up")
            return True
            
        except Exception as e:
            print(f"❌ Test 4 FAILED: {e}")
            return False
    
    async def test_recording_status(self):
        """Test 5: Recording Status"""
        print("\n🧪 Test 5: Recording Status")
        
        try:
            # Start a recording
            recording_state = await recording_manager.start_recording(
                room_id=self.test_room_id,
                user_id=self.test_user_id
            )
            
            recording_id = recording_state["recording_id"]
            self.recording_ids.append(recording_id)
            
            # Get status
            status = await recording_manager.get_recording_status(recording_id)
            
            assert status["recording_id"] == recording_id
            assert status["status"] == RecordingStatus.RECORDING
            
            print(f"   Recording ID: {recording_id}")
            print(f"   Status: {status['status']}")
            print(f"   Format: {status['format']}")
            print(f"   Quality: {status['quality']}")
            print("✅ Test 5 PASSED: Status retrieval works")
            return True
            
        except Exception as e:
            print(f"❌ Test 5 FAILED: {e}")
            return False
    
    async def test_concurrent_recording_limits(self):
        """Test 6: Concurrent Recording Limits"""
        print("\n🧪 Test 6: Concurrent Recording Limits")
        
        try:
            # Clean up first to ensure we're at 0
            await self.cleanup()
            self.recording_ids = []
            
            # Start max concurrent recordings
            max_concurrent = recording_manager.max_concurrent_recordings
            recording_ids = []
            
            for i in range(max_concurrent):
                recording_state = await recording_manager.start_recording(
                    room_id=f"{self.test_room_id}_{i}",
                    user_id=self.test_user_id
                )
                recording_ids.append(recording_state["recording_id"])
                self.recording_ids.append(recording_state["recording_id"])
            
            print(f"   Started {len(recording_ids)} concurrent recordings")
            
            # Try to start one more (should fail)
            try:
                await recording_manager.start_recording(
                    room_id=f"{self.test_room_id}_overflow",
                    user_id=self.test_user_id
                )
                print("❌ Test 6 FAILED: Should have raised ValueError")
                return False
            except ValueError as e:
                assert "Maximum concurrent recordings" in str(e)
                print(f"   Correctly rejected: {e}")
            
            # Cancel one recording
            await recording_manager.cancel_recording(
                recording_id=recording_ids[0],
                user_id=self.test_user_id
            )
            
            # Now should be able to start another
            recording_state = await recording_manager.start_recording(
                room_id=f"{self.test_room_id}_after_cancel",
                user_id=self.test_user_id
            )
            self.recording_ids.append(recording_state["recording_id"])
            
            print(f"   Successfully started recording after cancellation")
            print("✅ Test 6 PASSED: Concurrent limits enforced correctly")
            return True
            
        except Exception as e:
            print(f"❌ Test 6 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_room_recordings(self):
        """Test 7: Room Recordings"""
        print("\n🧪 Test 7: Room Recordings")
        
        try:
            # Clean up first
            await self.cleanup()
            self.recording_ids = []
            
            # Start multiple recordings in same room
            recording_ids = []
            for i in range(3):
                recording_state = await recording_manager.start_recording(
                    room_id=self.test_room_id,
                    user_id=self.test_user_id
                )
                recording_ids.append(recording_state["recording_id"])
                self.recording_ids.append(recording_state["recording_id"])
            
            # Get room recordings
            room_recordings = await recording_manager.get_room_recordings(self.test_room_id)
            
            assert len(room_recordings) >= 3
            
            # Verify all our recordings are in the list
            room_recording_ids = [r["recording_id"] for r in room_recordings]
            for recording_id in recording_ids:
                assert recording_id in room_recording_ids
            
            print(f"   Found {len(room_recordings)} recordings for room")
            print(f"   Recording IDs: {recording_ids}")
            print("✅ Test 7 PASSED: Room recordings retrieval works")
            return True
            
        except Exception as e:
            print(f"❌ Test 7 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def test_user_recordings(self):
        """Test 8: User Recordings"""
        print("\n🧪 Test 8: User Recordings")
        
        try:
            # Clean up first
            await self.cleanup()
            self.recording_ids = []
            
            # Start recordings with different statuses
            # Active recording
            active_state = await recording_manager.start_recording(
                room_id=self.test_room_id,
                user_id=self.test_user_id
            )
            self.recording_ids.append(active_state["recording_id"])
            
            # Paused recording
            paused_state = await recording_manager.start_recording(
                room_id=self.test_room_id,
                user_id=self.test_user_id
            )
            self.recording_ids.append(paused_state["recording_id"])
            await recording_manager.pause_recording(
                recording_id=paused_state["recording_id"],
                user_id=self.test_user_id
            )
            
            # Get all user recordings
            all_recordings = await recording_manager.get_user_recordings(self.test_user_id)
            
            assert len(all_recordings) >= 2
            
            print(f"   Total recordings: {len(all_recordings)}")
            
            # Get only active recordings
            active_recordings = await recording_manager.get_user_recordings(
                user_id=self.test_user_id,
                status=RecordingStatus.RECORDING
            )
            
            assert len(active_recordings) >= 1
            print(f"   Active recordings: {len(active_recordings)}")
            
            # Get only paused recordings
            paused_recordings = await recording_manager.get_user_recordings(
                user_id=self.test_user_id,
                status=RecordingStatus.PAUSED
            )
            
            assert len(paused_recordings) >= 1
            print(f"   Paused recordings: {len(paused_recordings)}")
            
            print("✅ Test 8 PASSED: User recordings filtering works")
            return True
            
        except Exception as e:
            print(f"❌ Test 8 FAILED: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def run_all_tests(self):
        """Run all tests."""
        print("=" * 60)
        print("🧪 WebRTC Recording Feature Test Suite")
        print("=" * 60)
        
        tests = [
            ("Start Recording", self.test_start_recording),
            ("Stop Recording", self.test_stop_recording),
            ("Pause/Resume Recording", self.test_pause_resume_recording),
            ("Cancel Recording", self.test_cancel_recording),
            ("Recording Status", self.test_recording_status),
            ("Concurrent Recording Limits", self.test_concurrent_recording_limits),
            ("Room Recordings", self.test_room_recordings),
            ("User Recordings", self.test_user_recordings),
        ]
        
        results = []
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                results.append((test_name, result))
            except Exception as e:
                print(f"❌ Test '{test_name}' crashed: {e}")
                results.append((test_name, False))
        
        # Cleanup
        await self.cleanup()
        
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {test_name}")
        
        print("=" * 60)
        print(f"Passed: {passed}/{total} tests")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
        else:
            print(f"⚠️  {total - passed} test(s) failed")
        
        print("=" * 60)
        
        return passed == total


async def main():
    """Main test runner."""
    try:
        # Run tests
        tester = TestRecordingFeature()
        success = await tester.run_all_tests()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
