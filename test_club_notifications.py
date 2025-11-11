#!/usr/bin/env python3
"""
Test script for ClubNotificationManager
Tests email notifications for club events using existing EmailManager infrastructure
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.managers.club_notification_manager import ClubNotificationManager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger("ClubNotificationsTest")

async def test_club_notifications():
    """Test club notification functionality"""

    logger.info("Starting club notification tests...")

    try:
        # Initialize notification manager
        notification_manager = ClubNotificationManager()

        # Test data
        test_club = {
            "name": "Test University AI Club",
            "description": "A club for AI enthusiasts",
            "university": "Test University"
        }

        test_user = {
            "username": "testuser",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User"
        }

        test_event = {
            "title": "AI Workshop 2024",
            "description": "Learn about machine learning basics",
            "start_time": "2024-01-15T14:00:00Z",
            "end_time": "2024-01-15T16:00:00Z",
            "location": "Room 101, Tech Building"
        }

        # Test 1: Club invitation email
        logger.info("Testing club invitation email...")
        success = await notification_manager.send_club_invitation_email(
            club_id="test_club_123",
            invitee_email=test_user["email"],
            inviter_username="clubadmin",
            invitation_token="test_invitation_token_123",
            club_name=test_club["name"],
            club_description=test_club["description"],
            expires_at="2024-02-15T14:00:00Z"
        )
        logger.info(f"Club invitation email sent: {success}")

        # Test 2: Event announcement email
        logger.info("Testing event announcement email...")
        success = await notification_manager.send_event_announcement_email(
            club_id="test_club_123",
            event_title=test_event["title"],
            event_description=test_event["description"],
            event_date=test_event["start_time"],
            event_location=test_event["location"],
            recipient_emails=[test_user["email"]],
            organizer_username="clubadmin",
            rsvp_link="http://localhost:3000/clubs/test_club_123/events/test_event_456/rsvp"
        )
        logger.info(f"Event announcement email sent: {success}")

        # Test 3: Role change notification
        logger.info("Testing role change notification...")
        success = await notification_manager.send_role_change_notification_email(
            club_id="test_club_123",
            user_email=test_user["email"],
            username=test_user["username"],
            old_role="member",
            new_role="lead",
            changed_by_username="clubadmin",
            club_name=test_club["name"]
        )
        logger.info(f"Role change notification sent: {success}")

        # Test 4: Event reminder
        logger.info("Testing event reminder...")
        success = await notification_manager.send_event_reminder_email(
            club_id="test_club_123",
            event_title=test_event["title"],
            event_date=test_event["start_time"],
            event_location=test_event["location"],
            recipient_emails=[test_user["email"]],
            club_name=test_club["name"],
            hours_until_event=24
        )
        logger.info(f"Event reminder sent: {success}")

        logger.info("All club notification tests completed successfully!")

    except Exception as e:
        logger.error(f"Club notification test failed: {e}", exc_info=True)
        return False

    return True

if __name__ == "__main__":
    # Run the test
    success = asyncio.run(test_club_notifications())
    sys.exit(0 if success else 1)