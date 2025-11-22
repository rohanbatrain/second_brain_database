"""
Migration script to add tenant_id to all existing collections.

This migration adds the tenant_id field to all documents in collections
that don't already have it, setting them to the default tenant for
backward compatibility.
"""

from datetime import datetime
from typing import List

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.migrations.migration_manager import BaseMigration

logger = get_logger(prefix="[Tenant Migration]")


class AddTenantIdMigration(BaseMigration):
    """Migration to add tenant_id to all collections."""

    def __init__(self):
        super().__init__(
            migration_id="add_tenant_id_001",
            description="Add tenant_id field to all collections for multi-tenancy support",
            version="1.0.0",
        )

    def get_collections_to_migrate(self) -> List[str]:
        """
        Get list of collections that need tenant_id field.

        Returns:
            List of collection names
        """
        return [
            # User and authentication
            "users",
            "permanent_tokens",
            # Family management
            "families",
            "family_relationships",
            "family_invitations",
            "family_notifications",
            "family_token_requests",
            "family_admin_actions",
            # Workspace management
            "workspaces",
            # Skills and user data
            "user_skills",
            # Chat system
            "chat_sessions",
            "chat_messages",
            "token_usage",
            "message_votes",
            # Blog platform
            "blog_websites",
            "blog_posts",
            "blog_categories",
            "blog_comments",
            "blog_analytics",
            "blog_subscribers",
            # Documents
            "documents",
            # SBD tokens
            "sbd_transactions",
            "sbd_accounts",
            # Shop
            "shop_items",
            "shop_purchases",
            # Themes and customization
            "themes",
            "avatars",
            "banners",
        ]

    async def up(self) -> bool:
        """
        Run the migration to add tenant_id to all collections.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Starting tenant_id migration")
            default_tenant_id = settings.DEFAULT_TENANT_ID
            collections_to_migrate = self.get_collections_to_migrate()

            total_updated = 0
            total_collections = len(collections_to_migrate)

            for idx, collection_name in enumerate(collections_to_migrate, 1):
                logger.info(
                    "Migrating collection %d/%d: %s",
                    idx,
                    total_collections,
                    collection_name,
                )

                try:
                    collection = db_manager.get_collection(collection_name)

                    # Count documents without tenant_id
                    count_without_tenant = await collection.count_documents(
                        {"tenant_id": {"$exists": False}}
                    )

                    if count_without_tenant == 0:
                        logger.info("Collection %s: No documents to migrate", collection_name)
                        continue

                    # Add tenant_id to documents that don't have it
                    result = await collection.update_many(
                        {"tenant_id": {"$exists": False}},
                        {"$set": {"tenant_id": default_tenant_id}},
                    )

                    total_updated += result.modified_count
                    logger.info(
                        "Collection %s: Updated %d documents with tenant_id=%s",
                        collection_name,
                        result.modified_count,
                        default_tenant_id,
                    )

                except Exception as e:
                    logger.error("Failed to migrate collection %s: %s", collection_name, e)
                    # Continue with other collections
                    continue

            logger.info(
                "Tenant_id migration completed: %d documents updated across %d collections",
                total_updated,
                total_collections,
            )

            # Record migration
            await self.record_migration()

            return True

        except Exception as e:
            logger.error("Tenant_id migration failed: %s", e, exc_info=True)
            return False

    async def down(self) -> bool:
        """
        Rollback the migration by removing tenant_id from all collections.

        WARNING: This will remove tenant isolation! Use with caution.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.warning("Rolling back tenant_id migration - this will remove tenant isolation!")
            collections_to_migrate = self.get_collections_to_migrate()

            total_updated = 0

            for collection_name in collections_to_migrate:
                try:
                    collection = db_manager.get_collection(collection_name)

                    # Remove tenant_id field
                    result = await collection.update_many(
                        {},
                        {"$unset": {"tenant_id": ""}},
                    )

                    total_updated += result.modified_count
                    logger.info(
                        "Collection %s: Removed tenant_id from %d documents",
                        collection_name,
                        result.modified_count,
                    )

                except Exception as e:
                    logger.error("Failed to rollback collection %s: %s", collection_name, e)
                    continue

            logger.info("Tenant_id rollback completed: %d documents updated", total_updated)

            # Remove migration record
            await self.remove_migration_record()

            return True

        except Exception as e:
            logger.error("Tenant_id rollback failed: %s", e, exc_info=True)
            return False

    async def create_tenant_indexes(self) -> bool:
        """
        Create compound indexes with tenant_id for all collections.

        This should be run after the migration to improve query performance.

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("Creating compound indexes with tenant_id")
            collections_to_migrate = self.get_collections_to_migrate()

            for collection_name in collections_to_migrate:
                try:
                    collection = db_manager.get_collection(collection_name)

                    # Create compound index with tenant_id
                    # This will vary by collection, but a common pattern is (tenant_id, created_at)
                    await collection.create_index([("tenant_id", 1), ("created_at", -1)])
                    logger.info("Created index on %s: (tenant_id, created_at)", collection_name)

                    # For user-scoped collections, also create (tenant_id, user_id)
                    if collection_name in [
                        "user_skills",
                        "chat_sessions",
                        "chat_messages",
                        "documents",
                        "shop_purchases",
                    ]:
                        await collection.create_index([("tenant_id", 1), ("user_id", 1)])
                        logger.info("Created index on %s: (tenant_id, user_id)", collection_name)

                except Exception as e:
                    logger.error("Failed to create indexes for %s: %s", collection_name, e)
                    continue

            logger.info("Compound index creation completed")
            return True

        except Exception as e:
            logger.error("Index creation failed: %s", e, exc_info=True)
            return False


# Create migration instance
add_tenant_id_migration = AddTenantIdMigration()
