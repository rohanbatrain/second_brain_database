"""
Migration for creating IPAM backend enhancements collections and indexes.

This migration creates all necessary collections for the IPAM backend enhancements
including reservations, shares, preferences, notifications, webhooks, and bulk operations.
"""

from datetime import datetime, timezone
from typing import Any, Dict
import uuid

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.migrations.migration_manager import BaseMigration

logger = get_logger(prefix="[IPAMEnhancementsMigration]")


class IPAMEnhancementsMigration(BaseMigration):
    """
    Migration to create IPAM backend enhancements collections with proper schema and indexes.

    This migration creates:
    - ipam_reservations collection with indexes
    - ipam_shares collection with indexes
    - ipam_user_preferences collection with indexes
    - ipam_notifications collection with indexes
    - ipam_notification_rules collection with indexes
    - ipam_webhooks collection with indexes
    - ipam_webhook_deliveries collection with indexes
    - ipam_bulk_jobs collection with indexes
    """

    @property
    def name(self) -> str:
        return "create_ipam_enhancements_collections"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Create IPAM backend enhancements collections with proper indexes and constraints"

    async def validate(self) -> bool:
        """Validate that the migration can be applied."""
        try:
            # Check database connection
            if not await db_manager.health_check():
                self.logger.error("Database health check failed")
                return False

            # Check if collections already exist
            if self.database is None:
                self.logger.error("Database not connected")
                return False

            existing_collections = await self.database.list_collection_names()
            ipam_collections = [
                "ipam_reservations",
                "ipam_shares",
                "ipam_user_preferences",
                "ipam_notifications",
                "ipam_notification_rules",
                "ipam_webhooks",
                "ipam_webhook_deliveries",
                "ipam_bulk_jobs",
            ]

            for collection_name in ipam_collections:
                if collection_name in existing_collections:
                    self.logger.warning("Collection %s already exists", collection_name)

            self.logger.info("Migration validation passed")
            return True

        except Exception as e:
            self.logger.error("Migration validation failed: %s", e, exc_info=True)
            return False

    @property
    def database(self):
        """Get database instance."""
        return db_manager.database

    async def up(self) -> Dict[str, Any]:
        """Execute the migration to create IPAM enhancements collections."""
        collections_affected = []
        records_processed = 0
        rollback_data = {}

        try:
            self.logger.info("Starting IPAM enhancements collections migration")

            # Create ipam_reservations collection
            await self._create_reservations_collection()
            collections_affected.append("ipam_reservations")

            # Create ipam_shares collection
            await self._create_shares_collection()
            collections_affected.append("ipam_shares")

            # Create ipam_user_preferences collection
            await self._create_user_preferences_collection()
            collections_affected.append("ipam_user_preferences")

            # Create ipam_notifications collection
            await self._create_notifications_collection()
            collections_affected.append("ipam_notifications")

            # Create ipam_notification_rules collection
            await self._create_notification_rules_collection()
            collections_affected.append("ipam_notification_rules")

            # Create ipam_webhooks collection
            await self._create_webhooks_collection()
            collections_affected.append("ipam_webhooks")

            # Create ipam_webhook_deliveries collection
            await self._create_webhook_deliveries_collection()
            collections_affected.append("ipam_webhook_deliveries")

            # Create ipam_bulk_jobs collection
            await self._create_bulk_jobs_collection()
            collections_affected.append("ipam_bulk_jobs")

            # Create all indexes
            await self._create_all_indexes()

            # Store rollback data
            rollback_data = {
                "collections_created": collections_affected,
                "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info("IPAM enhancements collections migration completed successfully")

            return {
                "collections_affected": collections_affected,
                "records_processed": records_processed,
                "rollback_data": rollback_data,
            }

        except Exception as e:
            self.logger.error("IPAM enhancements collections migration failed: %s", e, exc_info=True)
            raise Exception(f"Migration failed: {str(e)}")

    async def down(self) -> Dict[str, Any]:
        """Rollback the migration by dropping created collections."""
        collections_dropped = []

        try:
            self.logger.info("Starting IPAM enhancements collections migration rollback")

            # Drop IPAM enhancements collections
            ipam_collections = [
                "ipam_reservations",
                "ipam_shares",
                "ipam_user_preferences",
                "ipam_notifications",
                "ipam_notification_rules",
                "ipam_webhooks",
                "ipam_webhook_deliveries",
                "ipam_bulk_jobs",
            ]

            for collection_name in ipam_collections:
                try:
                    await self.database.drop_collection(collection_name)
                    collections_dropped.append(collection_name)
                    self.logger.info("Dropped collection: %s", collection_name)
                except Exception as e:
                    self.logger.warning("Failed to drop collection %s: %s", collection_name, e)

            self.logger.info("IPAM enhancements collections migration rollback completed")

            return {"collections_dropped": collections_dropped}

        except Exception as e:
            self.logger.error("Migration rollback failed: %s", e, exc_info=True)
            raise Exception(f"Rollback failed: {str(e)}")

    async def _create_reservations_collection(self):
        """Create the ipam_reservations collection with proper schema."""
        try:
            collection = db_manager.get_collection("ipam_reservations")

            # Create a sample document to establish schema (will be removed)
            sample_doc = {
                "_schema_version": "1.0.0",
                "user_id": "sample_user",
                "resource_type": "region",  # region or host
                "x_octet": 10,
                "y_octet": 0,
                "z_octet": None,  # Only for host reservations
                "reason": "Sample reservation",
                "status": "active",  # active, expired, converted
                "expires_at": None,
                "created_at": datetime.now(timezone.utc),
                "created_by": "sample_user",
                "metadata": {},
            }

            await collection.insert_one(sample_doc)
            await collection.delete_one({"user_id": "sample_user"})

            self.logger.info("Created ipam_reservations collection")

        except Exception as e:
            self.logger.error("Failed to create ipam_reservations collection: %s", e, exc_info=True)
            raise

    async def _create_shares_collection(self):
        """Create the ipam_shares collection."""
        try:
            collection = db_manager.get_collection("ipam_shares")

            sample_doc = {
                "_schema_version": "1.0.0",
                "share_token": str(uuid.uuid4()),
                "user_id": "sample_user",
                "resource_type": "region",  # country, region, or host
                "resource_id": "sample_resource_id",
                "expires_at": datetime.now(timezone.utc),
                "view_count": 0,
                "last_accessed": None,
                "created_at": datetime.now(timezone.utc),
                "created_by": "sample_user",
                "is_active": True,
            }

            await collection.insert_one(sample_doc)
            await collection.delete_one({"share_token": sample_doc["share_token"]})

            self.logger.info("Created ipam_shares collection")

        except Exception as e:
            self.logger.error("Failed to create ipam_shares collection: %s", e, exc_info=True)
            raise

    async def _create_user_preferences_collection(self):
        """Create the ipam_user_preferences collection."""
        try:
            collection = db_manager.get_collection("ipam_user_preferences")

            sample_doc = {
                "_schema_version": "1.0.0",
                "user_id": "sample_user",
                "saved_filters": [],
                "dashboard_layout": {},
                "notification_settings": {},
                "theme_preference": "default",
                "updated_at": datetime.now(timezone.utc),
            }

            await collection.insert_one(sample_doc)
            await collection.delete_one({"user_id": "sample_user"})

            self.logger.info("Created ipam_user_preferences collection")

        except Exception as e:
            self.logger.error("Failed to create ipam_user_preferences collection: %s", e, exc_info=True)
            raise

    async def _create_notifications_collection(self):
        """Create the ipam_notifications collection."""
        try:
            collection = db_manager.get_collection("ipam_notifications")

            sample_doc = {
                "_schema_version": "1.0.0",
                "user_id": "sample_user",
                "notification_type": "capacity_warning",
                "severity": "warning",  # info, warning, critical
                "message": "Sample notification",
                "resource_type": None,
                "resource_id": None,
                "resource_link": None,
                "is_read": False,
                "read_at": None,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc),
            }

            await collection.insert_one(sample_doc)
            await collection.delete_one({"user_id": "sample_user"})

            self.logger.info("Created ipam_notifications collection")

        except Exception as e:
            self.logger.error("Failed to create ipam_notifications collection: %s", e, exc_info=True)
            raise

    async def _create_notification_rules_collection(self):
        """Create the ipam_notification_rules collection."""
        try:
            collection = db_manager.get_collection("ipam_notification_rules")

            sample_doc = {
                "_schema_version": "1.0.0",
                "user_id": "sample_user",
                "rule_name": "Sample Rule",
                "conditions": {},
                "notification_channels": ["in_app"],
                "is_active": True,
                "last_triggered": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            await collection.insert_one(sample_doc)
            await collection.delete_one({"user_id": "sample_user"})

            self.logger.info("Created ipam_notification_rules collection")

        except Exception as e:
            self.logger.error("Failed to create ipam_notification_rules collection: %s", e, exc_info=True)
            raise

    async def _create_webhooks_collection(self):
        """Create the ipam_webhooks collection."""
        try:
            collection = db_manager.get_collection("ipam_webhooks")

            sample_doc = {
                "_schema_version": "1.0.0",
                "user_id": "sample_user",
                "webhook_url": "https://example.com/webhook",
                "secret_key": "sample_secret",
                "events": ["region.created"],
                "is_active": True,
                "failure_count": 0,
                "last_delivery": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            await collection.insert_one(sample_doc)
            await collection.delete_one({"user_id": "sample_user"})

            self.logger.info("Created ipam_webhooks collection")

        except Exception as e:
            self.logger.error("Failed to create ipam_webhooks collection: %s", e, exc_info=True)
            raise

    async def _create_webhook_deliveries_collection(self):
        """Create the ipam_webhook_deliveries collection."""
        try:
            collection = db_manager.get_collection("ipam_webhook_deliveries")

            sample_doc = {
                "_schema_version": "1.0.0",
                "webhook_id": "sample_webhook_id",
                "event_type": "region.created",
                "payload": {},
                "status_code": None,
                "response_time_ms": None,
                "error_message": None,
                "attempt_number": 1,
                "delivered_at": datetime.now(timezone.utc),
            }

            await collection.insert_one(sample_doc)
            await collection.delete_one({"webhook_id": "sample_webhook_id"})

            self.logger.info("Created ipam_webhook_deliveries collection")

        except Exception as e:
            self.logger.error("Failed to create ipam_webhook_deliveries collection: %s", e, exc_info=True)
            raise

    async def _create_bulk_jobs_collection(self):
        """Create the ipam_bulk_jobs collection."""
        try:
            collection = db_manager.get_collection("ipam_bulk_jobs")

            sample_doc = {
                "_schema_version": "1.0.0",
                "job_id": str(uuid.uuid4()),
                "user_id": "sample_user",
                "operation_type": "bulk_tag_update",
                "total_items": 0,
                "processed_items": 0,
                "successful_items": 0,
                "failed_items": 0,
                "status": "pending",  # pending, processing, completed, failed
                "results": [],
                "created_at": datetime.now(timezone.utc),
                "completed_at": None,
            }

            await collection.insert_one(sample_doc)
            await collection.delete_one({"job_id": sample_doc["job_id"]})

            self.logger.info("Created ipam_bulk_jobs collection")

        except Exception as e:
            self.logger.error("Failed to create ipam_bulk_jobs collection: %s", e, exc_info=True)
            raise

    async def _create_all_indexes(self):
        """Create all necessary indexes for IPAM enhancements collections."""
        try:
            self.logger.info("Creating indexes for IPAM enhancements collections")

            # ipam_reservations collection indexes
            reservations_collection = db_manager.get_collection("ipam_reservations")
            await reservations_collection.create_index([("user_id", 1), ("status", 1)])
            await reservations_collection.create_index([("x_octet", 1), ("y_octet", 1), ("z_octet", 1)])
            await reservations_collection.create_index("expires_at")
            await reservations_collection.create_index([("user_id", 1), ("resource_type", 1)])
            await reservations_collection.create_index([("user_id", 1), ("created_at", -1)])

            # ipam_shares collection indexes
            shares_collection = db_manager.get_collection("ipam_shares")
            await shares_collection.create_index("share_token", unique=True)
            await shares_collection.create_index([("user_id", 1), ("is_active", 1)])
            await shares_collection.create_index("expires_at")
            await shares_collection.create_index([("user_id", 1), ("created_at", -1)])
            await shares_collection.create_index([("resource_type", 1), ("resource_id", 1)])

            # ipam_user_preferences collection indexes
            preferences_collection = db_manager.get_collection("ipam_user_preferences")
            await preferences_collection.create_index("user_id", unique=True)
            await preferences_collection.create_index("updated_at")

            # ipam_notifications collection indexes
            notifications_collection = db_manager.get_collection("ipam_notifications")
            await notifications_collection.create_index([("user_id", 1), ("is_read", 1), ("created_at", -1)])
            await notifications_collection.create_index("expires_at")
            await notifications_collection.create_index([("user_id", 1), ("severity", 1)])
            await notifications_collection.create_index([("user_id", 1), ("notification_type", 1)])

            # ipam_notification_rules collection indexes
            rules_collection = db_manager.get_collection("ipam_notification_rules")
            await rules_collection.create_index([("user_id", 1), ("is_active", 1)])
            await rules_collection.create_index([("user_id", 1), ("created_at", -1)])
            await rules_collection.create_index("last_triggered")

            # ipam_webhooks collection indexes
            webhooks_collection = db_manager.get_collection("ipam_webhooks")
            await webhooks_collection.create_index([("user_id", 1), ("is_active", 1)])
            await webhooks_collection.create_index([("user_id", 1), ("created_at", -1)])
            await webhooks_collection.create_index("last_delivery")
            await webhooks_collection.create_index("failure_count")

            # ipam_webhook_deliveries collection indexes
            deliveries_collection = db_manager.get_collection("ipam_webhook_deliveries")
            await deliveries_collection.create_index([("webhook_id", 1), ("delivered_at", -1)])
            await deliveries_collection.create_index("event_type")
            await deliveries_collection.create_index("delivered_at")
            await deliveries_collection.create_index([("webhook_id", 1), ("status_code", 1)])

            # ipam_bulk_jobs collection indexes
            bulk_jobs_collection = db_manager.get_collection("ipam_bulk_jobs")
            await bulk_jobs_collection.create_index("job_id", unique=True)
            await bulk_jobs_collection.create_index([("user_id", 1), ("created_at", -1)])
            await bulk_jobs_collection.create_index([("user_id", 1), ("status", 1)])
            await bulk_jobs_collection.create_index("status")
            await bulk_jobs_collection.create_index("created_at")

            self.logger.info("All IPAM enhancements collection indexes created successfully")

        except Exception as e:
            self.logger.error("Failed to create IPAM enhancements collection indexes: %s", e, exc_info=True)
            raise
