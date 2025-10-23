#!/usr/bin/env python3
"""
Migration script to fix incorrect notification types in family_notifications collection.

This script updates existing notifications that have incorrect types:
- 'token_request_approve' -> 'token_request_approved'
- 'token_request_deny' -> 'token_request_denied'
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from second_brain_database.database import db_manager


async def migrate_notification_types():
    """Migrate incorrect notification types in the database."""
    print("Starting notification type migration...")

    try:
        # Connect to database
        await db_manager.connect()
        print("Connected to database")

        # Get notifications collection
        notifications_collection = db_manager.get_collection("family_notifications")

        # Count notifications with incorrect types
        incorrect_approve_count = await notifications_collection.count_documents({"type": "token_request_approve"})
        incorrect_deny_count = await notifications_collection.count_documents({"type": "token_request_deny"})

        print(f"Found {incorrect_approve_count} notifications with type 'token_request_approve'")
        print(f"Found {incorrect_deny_count} notifications with type 'token_request_deny'")

        total_incorrect = incorrect_approve_count + incorrect_deny_count

        if total_incorrect == 0:
            print("No incorrect notification types found. Migration complete.")
            return

        # Update notifications with incorrect types
        now = datetime.now(timezone.utc)

        # Update 'token_request_approve' to 'token_request_approved'
        if incorrect_approve_count > 0:
            result_approve = await notifications_collection.update_many(
                {"type": "token_request_approve"},
                {
                    "$set": {
                        "type": "token_request_approved",
                        "migrated_at": now,
                        "migration_version": "1.0"
                    }
                }
            )
            print(f"Updated {result_approve.modified_count} notifications from 'token_request_approve' to 'token_request_approved'")

        # Update 'token_request_deny' to 'token_request_denied'
        if incorrect_deny_count > 0:
            result_deny = await notifications_collection.update_many(
                {"type": "token_request_deny"},
                {
                    "$set": {
                        "type": "token_request_denied",
                        "migrated_at": now,
                        "migration_version": "1.0"
                    }
                }
            )
            print(f"Updated {result_deny.modified_count} notifications from 'token_request_deny' to 'token_request_denied'")

        # Verify the migration
        final_incorrect_count = await notifications_collection.count_documents({
            "type": {"$in": ["token_request_approve", "token_request_deny"]}
        })

        if final_incorrect_count == 0:
            print("✅ Migration successful! All incorrect notification types have been fixed.")
        else:
            print(f"❌ Migration incomplete! {final_incorrect_count} notifications still have incorrect types.")

        # Show final counts
        correct_approved_count = await notifications_collection.count_documents({"type": "token_request_approved"})
        correct_denied_count = await notifications_collection.count_documents({"type": "token_request_denied"})

        print(f"Final counts:")
        print(f"  - token_request_approved: {correct_approved_count}")
        print(f"  - token_request_denied: {correct_denied_count}")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        await db_manager.disconnect()
        print("Disconnected from database")


if __name__ == "__main__":
    asyncio.run(migrate_notification_types())