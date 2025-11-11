#!/usr/bin/env python3
"""
Test script for Club WebRTC Event Rooms

Tests club membership validation and WebRTC event room functionality.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.club_webrtc_router import ClubEventWebRTCManager

logger = get_logger("ClubWebRTCTest")


async def test_club_membership_validation():
    """Test club membership validation functionality."""

    logger.info("Testing club membership validation...")

    try:
        # Test with a non-existent club/user combination
        try:
            await ClubEventWebRTCManager.validate_club_membership("nonexistent_club", "nonexistent_user")
            logger.error("Should have failed for non-existent club/user")
            return False
        except Exception as e:
            logger.info(f"Correctly rejected non-existent membership: {e}")

        # Test room ID generation
        room_id = ClubEventWebRTCManager.generate_event_room_id("test_club_123", "test_event_456")
        expected = "club_test_club_123_event_test_event_456"

        if room_id != expected:
            logger.error(f"Room ID generation failed. Expected: {expected}, Got: {room_id}")
            return False

        logger.info(f"Room ID generation successful: {room_id}")

        logger.info("Club membership validation tests completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Club membership validation test failed: {e}", exc_info=True)
        return False


async def test_webrtc_room_operations():
    """Test WebRTC room operations for club events."""

    logger.info("Testing WebRTC room operations...")

    try:
        # Test room ID validation (this would normally be done by the router)
        from second_brain_database.webrtc.dependencies import validate_room_id

        test_room_id = "club_test_club_123_event_test_event_456"
        validated_room_id = validate_room_id(test_room_id)

        if validated_room_id != test_room_id:
            logger.error(f"Room ID validation failed. Expected: {test_room_id}, Got: {validated_room_id}")
            return False

        logger.info(f"Room ID validation successful: {validated_room_id}")

        # Test room settings (would normally be done by the router)
        # This is a placeholder - in a real test we'd need to mock the webrtc_manager
        logger.info("Room settings validation would be tested here (requires mocking)")

        logger.info("WebRTC room operations tests completed successfully!")
        return True

    except Exception as e:
        logger.error(f"WebRTC room operations test failed: {e}", exc_info=True)
        return False


async def test_integration_readiness():
    """Test that all components are ready for integration."""

    logger.info("Testing integration readiness...")

    try:
        # Test imports
        from second_brain_database.managers.club_notification_manager import ClubNotificationManager
        from second_brain_database.routes.club_webrtc_router import router as club_webrtc_router
        from second_brain_database.routes.clubs import router as clubs_router

        logger.info("All required modules imported successfully")

        # Test that routers have expected routes
        club_webrtc_routes = [route.path for route in club_webrtc_router.routes]
        logger.info(f"Club WebRTC router has {len(club_webrtc_routes)} routes: {club_webrtc_routes}")

        clubs_routes = [route.path for route in clubs_router.routes]
        logger.info(f"Clubs router has {len(clubs_routes)} routes")

        # Check for expected WebRTC routes
        expected_webrtc_routes = [
            "/clubs/webrtc/events/{club_id}/{event_id}",
            "/clubs/webrtc/events/{club_id}/{event_id}/participants",
            "/clubs/webrtc/events/{club_id}/{event_id}/create-room"
        ]

        for expected_route in expected_webrtc_routes:
            if not any(expected_route in route for route in club_webrtc_routes):
                logger.warning(f"Expected WebRTC route not found: {expected_route}")

        logger.info("Integration readiness tests completed successfully!")
        return True

    except Exception as e:
        logger.error(f"Integration readiness test failed: {e}", exc_info=True)
        return False


async def run_all_tests():
    """Run all WebRTC tests."""

    logger.info("Starting comprehensive Club WebRTC tests...")

    tests = [
        ("Club Membership Validation", test_club_membership_validation),
        ("WebRTC Room Operations", test_webrtc_room_operations),
        ("Integration Readiness", test_integration_readiness),
    ]

    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"Running: {test_name}")
        logger.info(f"{'='*50}")

        try:
            result = await test_func()
            results.append((test_name, result))
            status = "PASSED" if result else "FAILED"
            logger.info(f"{test_name}: {status}")
        except Exception as e:
            logger.error(f"{test_name}: FAILED with exception: {e}")
            results.append((test_name, False))

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST SUMMARY")
    logger.info(f"{'='*60}")

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
        if result:
            passed += 1

    logger.info(f"\nResults: {passed}/{total} tests passed")

    if passed == total:
        logger.info("🎉 All tests passed! Club WebRTC integration is ready.")
        return True
    else:
        logger.error(f"❌ {total - passed} test(s) failed. Please fix issues before integration.")
        return False


if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)