#!/usr/bin/env python3
"""
Database indexes setup for Club Management Platform.

This script creates all necessary indexes for optimal query performance
across universities, clubs, verticals, and members collections.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[ClubIndexes]")


async def create_club_indexes():
    """Create all database indexes for club management."""
    try:
        logger.info("Starting club database indexes creation...")

        # Connect to database first
        logger.info("Connecting to database...")
        await db_manager.connect()
        logger.info("✓ Database connected")

        # Universities collection indexes
        logger.info("Creating universities collection indexes...")
        await db_manager.get_collection("universities").create_index(
            [("domain", 1)],
            unique=True,
            name="universities_domain_unique"
        )
        await db_manager.get_collection("universities").create_index(
            [("is_verified", 1), ("admin_approved", 1)],
            name="universities_verification_status"
        )
        logger.info("✓ Universities indexes created")

        # Clubs collection indexes
        logger.info("Creating clubs collection indexes...")
        await db_manager.get_collection("clubs").create_index(
            [("university_id", 1), ("is_active", 1)],
            name="clubs_university_active"
        )
        await db_manager.get_collection("clubs").create_index(
            [("slug", 1)],
            unique=True,
            name="clubs_slug_unique"
        )
        await db_manager.get_collection("clubs").create_index(
            [("owner_id", 1)],
            name="clubs_owner"
        )
        await db_manager.get_collection("clubs").create_index(
            [("category", 1), ("is_active", 1)],
            name="clubs_category_active"
        )
        await db_manager.get_collection("clubs").create_index(
            [("tags", 1), ("is_active", 1)],
            name="clubs_tags_active"
        )
        logger.info("✓ Clubs indexes created")

        # Verticals collection indexes
        logger.info("Creating club_verticals collection indexes...")
        await db_manager.get_collection("club_verticals").create_index(
            [("club_id", 1)],
            name="verticals_club"
        )
        await db_manager.get_collection("club_verticals").create_index(
            [("lead_id", 1)],
            name="verticals_lead"
        )
        await db_manager.get_collection("club_verticals").create_index(
            [("club_id", 1), ("is_active", 1)],
            name="verticals_club_active"
        )
        logger.info("✓ Verticals indexes created")

        # Members collection indexes
        logger.info("Creating club_members collection indexes...")
        await db_manager.get_collection("club_members").create_index(
            [("club_id", 1), ("user_id", 1)],
            unique=True,
            name="members_club_user_unique"
        )
        await db_manager.get_collection("club_members").create_index(
            [("user_id", 1), ("is_active", 1)],
            name="members_user_active"
        )
        await db_manager.get_collection("club_members").create_index(
            [("club_id", 1), ("role", 1)],
            name="members_club_role"
        )
        await db_manager.get_collection("club_members").create_index(
            [("club_id", 1), ("is_active", 1)],
            name="members_club_active"
        )
        await db_manager.get_collection("club_members").create_index(
            [("vertical_id", 1), ("is_active", 1)],
            name="members_vertical_active"
        )
        await db_manager.get_collection("club_members").create_index(
            [("invited_at", 1)],
            name="members_invited_at"
        )
        logger.info("✓ Members indexes created")

        # Analytics collection indexes (for future use)
        logger.info("Creating club_analytics collection indexes...")
        await db_manager.get_collection("club_analytics").create_index(
            [("club_id", 1), ("date", -1)],
            name="analytics_club_date"
        )
        await db_manager.get_collection("club_analytics").create_index(
            [("university_id", 1), ("date", -1)],
            name="analytics_university_date"
        )
        logger.info("✓ Analytics indexes created")

        logger.info("🎉 All club database indexes created successfully!")

        # Disconnect from database
        await db_manager.disconnect()
        logger.info("✓ Database disconnected")

    except Exception as e:
        logger.error("Failed to create club indexes: %s", e, exc_info=True)
        raise


async def main():
    """Main function to run index creation."""
    try:
        await create_club_indexes()
        logger.info("Club indexes setup completed successfully")
    except Exception as e:
        logger.error("Club indexes setup failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())