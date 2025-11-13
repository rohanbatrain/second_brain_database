#!/usr/bin/env python3
"""
Script to run the chat collections migration.

This script creates all necessary MongoDB collections and indexes for the
LangGraph-based chat system.

Usage:
    python scripts/run_chat_migration.py
    
    # Or with uv:
    uv run python scripts/run_chat_migration.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.migrations import ChatCollectionsMigration
from second_brain_database.migrations.migration_manager import migration_manager

logger = get_logger(prefix="[ChatMigrationScript]")


async def run_migration():
    """Run the chat collections migration."""
    try:
        logger.info("=" * 80)
        logger.info("Starting Chat Collections Migration")
        logger.info("=" * 80)

        # Initialize database connection
        logger.info("Connecting to database...")
        await db_manager.connect()

        # Check database health
        if not await db_manager.health_check():
            logger.error("Database health check failed. Please check your MongoDB connection.")
            return False

        logger.info("Database connection successful")

        # Create migration instance
        migration = ChatCollectionsMigration()

        logger.info("Migration Details:")
        logger.info("  Name: %s", migration.name)
        logger.info("  Version: %s", migration.version)
        logger.info("  Description: %s", migration.description)
        logger.info("")

        # Validate migration
        logger.info("Validating migration...")
        if not await migration.validate():
            logger.error("Migration validation failed")
            return False

        logger.info("Migration validation passed")
        logger.info("")

        # Run migration
        logger.info("Executing migration...")
        result = await migration_manager.run_migration(migration)

        logger.info("")
        logger.info("=" * 80)
        logger.info("Migration Results:")
        logger.info("=" * 80)
        logger.info("Status: %s", result.get("status", "unknown"))

        if result.get("status") == "completed":
            logger.info("Duration: %.2f seconds", result.get("duration_seconds", 0))
            logger.info("Collections affected: %s", ", ".join(result.get("collections_affected", [])))
            logger.info("Records processed: %d", result.get("records_processed", 0))
            logger.info("")
            logger.info("✅ Chat collections migration completed successfully!")
            logger.info("")
            logger.info("Created collections:")
            for collection in result.get("collections_affected", []):
                logger.info("  - %s", collection)
            logger.info("")
            logger.info("Next steps:")
            logger.info("  1. Verify collections exist: db.getCollectionNames()")
            logger.info("  2. Check indexes: db.chat_sessions.getIndexes()")
            logger.info("  3. Start using the chat system via API endpoints")
            return True
        elif result.get("status") == "skipped":
            logger.warning("⚠️  Migration was skipped (already applied)")
            logger.info("")
            logger.info("To re-run the migration:")
            logger.info("  1. Drop existing collections manually")
            logger.info("  2. Remove migration record from migration_history collection")
            logger.info("  3. Run this script again")
            return True
        else:
            logger.error("❌ Migration failed with status: %s", result.get("status"))
            return False

    except Exception as e:
        logger.error("=" * 80)
        logger.error("Migration Error")
        logger.error("=" * 80)
        logger.error("Error: %s", str(e), exc_info=True)
        logger.error("")
        logger.error("❌ Migration failed!")
        return False

    finally:
        # Close database connection
        logger.info("")
        logger.info("Closing database connection...")
        await db_manager.close()
        logger.info("Database connection closed")


async def rollback_migration():
    """Rollback the chat collections migration."""
    try:
        logger.info("=" * 80)
        logger.info("Rolling Back Chat Collections Migration")
        logger.info("=" * 80)

        # Initialize database connection
        logger.info("Connecting to database...")
        await db_manager.connect()

        # Check database health
        if not await db_manager.health_check():
            logger.error("Database health check failed. Please check your MongoDB connection.")
            return False

        logger.info("Database connection successful")

        # Get migration history
        history = await migration_manager.get_migration_history()

        # Find the chat collections migration
        chat_migration = None
        for record in history:
            if record.get("name") == "create_chat_collections" and record.get("status") == "completed":
                chat_migration = record
                break

        if not chat_migration:
            logger.warning("No completed chat collections migration found to rollback")
            return False

        logger.info("Found migration to rollback:")
        logger.info("  Migration ID: %s", chat_migration["migration_id"])
        logger.info("  Completed at: %s", chat_migration.get("completed_at"))
        logger.info("")

        # Confirm rollback
        logger.warning("⚠️  WARNING: This will drop all chat collections and data!")
        logger.warning("This action cannot be undone.")
        logger.info("")

        # Create migration instance and run down()
        migration = ChatCollectionsMigration()
        logger.info("Executing rollback...")
        result = await migration.down()

        logger.info("")
        logger.info("=" * 80)
        logger.info("Rollback Results:")
        logger.info("=" * 80)
        logger.info("Collections dropped: %s", ", ".join(result.get("collections_dropped", [])))
        logger.info("")
        logger.info("✅ Rollback completed successfully!")

        return True

    except Exception as e:
        logger.error("=" * 80)
        logger.error("Rollback Error")
        logger.error("=" * 80)
        logger.error("Error: %s", str(e), exc_info=True)
        logger.error("")
        logger.error("❌ Rollback failed!")
        return False

    finally:
        # Close database connection
        logger.info("")
        logger.info("Closing database connection...")
        await db_manager.close()
        logger.info("Database connection closed")


async def show_migration_status():
    """Show the status of the chat collections migration."""
    try:
        logger.info("=" * 80)
        logger.info("Chat Collections Migration Status")
        logger.info("=" * 80)

        # Initialize database connection
        await db_manager.connect()

        # Check database health
        if not await db_manager.health_check():
            logger.error("Database health check failed")
            return False

        # Get migration history
        history = await migration_manager.get_migration_history()

        # Find chat collections migrations
        chat_migrations = [
            record for record in history if record.get("name") == "create_chat_collections"
        ]

        if not chat_migrations:
            logger.info("Status: Not applied")
            logger.info("")
            logger.info("Run 'python scripts/run_chat_migration.py' to apply the migration")
            return True

        logger.info("Found %d migration record(s):", len(chat_migrations))
        logger.info("")

        for record in chat_migrations:
            logger.info("Migration ID: %s", record.get("migration_id"))
            logger.info("  Status: %s", record.get("status"))
            logger.info("  Version: %s", record.get("version"))
            logger.info("  Started: %s", record.get("started_at"))
            logger.info("  Completed: %s", record.get("completed_at"))

            if record.get("status") == "completed":
                logger.info("  Collections: %s", ", ".join(record.get("collections_affected", [])))
                logger.info("  Records: %d", record.get("records_processed", 0))

            if record.get("error_message"):
                logger.info("  Error: %s", record.get("error_message"))

            logger.info("")

        return True

    except Exception as e:
        logger.error("Error checking migration status: %s", str(e), exc_info=True)
        return False

    finally:
        await db_manager.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run chat collections migration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run migration
  python scripts/run_chat_migration.py
  
  # Check migration status
  python scripts/run_chat_migration.py --status
  
  # Rollback migration (WARNING: destroys data!)
  python scripts/run_chat_migration.py --rollback
        """,
    )

    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration (WARNING: destroys all chat data!)",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status without running",
    )

    args = parser.parse_args()

    if args.status:
        success = asyncio.run(show_migration_status())
    elif args.rollback:
        logger.warning("=" * 80)
        logger.warning("ROLLBACK MODE")
        logger.warning("=" * 80)
        logger.warning("This will DROP all chat collections and DELETE all chat data!")
        logger.warning("This action CANNOT be undone!")
        logger.warning("")
        response = input("Type 'yes' to confirm rollback: ")

        if response.lower() == "yes":
            success = asyncio.run(rollback_migration())
        else:
            logger.info("Rollback cancelled")
            success = True
    else:
        success = asyncio.run(run_migration())

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
