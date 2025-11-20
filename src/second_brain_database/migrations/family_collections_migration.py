"""
Migration for creating family management collections and indexes.

This migration creates all necessary collections for the family management system
with proper indexes, constraints, and referential integrity checks.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
import uuid

from pymongo.errors import DuplicateKeyError, PyMongoError

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

from .migration_manager import BaseMigration

logger = get_logger(prefix="[FamilyCollectionsMigration]")


class FamilyCollectionsMigration(BaseMigration):
    """
    Migration to create family management collections with proper schema and indexes.

    This migration creates:
    - families collection with indexes
    - family_relationships collection with indexes
    - family_invitations collection with indexes and TTL
    - family_notifications collection with indexes
    - family_token_requests collection with indexes and TTL
    - Updates users collection with family-related fields
    """

    @property
    def name(self) -> str:
        return "create_family_collections"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Create family management collections with proper indexes and constraints"

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
            family_collections = [
                "families",
                "family_relationships",
                "family_invitations",
                "family_notifications",
                "family_token_requests",
            ]

            for collection_name in family_collections:
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
        """Execute the migration to create family collections."""
        collections_affected = []
        records_processed = 0
        rollback_data = {}

        try:
            self.logger.info("Starting family collections migration")

            # Create families collection
            await self._create_families_collection()
            collections_affected.append("families")

            # Create family_relationships collection
            await self._create_family_relationships_collection()
            collections_affected.append("family_relationships")

            # Create family_invitations collection
            await self._create_family_invitations_collection()
            collections_affected.append("family_invitations")

            # Create family_notifications collection
            await self._create_family_notifications_collection()
            collections_affected.append("family_notifications")

            # Create family_token_requests collection
            await self._create_family_token_requests_collection()
            collections_affected.append("family_token_requests")

            # Update users collection schema
            users_updated = await self._update_users_collection_schema()
            records_processed += users_updated
            if users_updated > 0:
                collections_affected.append("users")

            # Create all indexes
            await self._create_all_indexes()

            # Store rollback data
            rollback_data = {
                "collections_created": collections_affected,
                "users_updated": users_updated,
                "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info("Family collections migration completed successfully")

            return {
                "collections_affected": collections_affected,
                "records_processed": records_processed,
                "rollback_data": rollback_data,
            }

        except Exception as e:
            self.logger.error("Family collections migration failed: %s", e, exc_info=True)
            raise Exception(f"Migration failed: {str(e)}")

    async def down(self) -> Dict[str, Any]:
        """Rollback the migration by dropping created collections."""
        collections_dropped = []

        try:
            self.logger.info("Starting family collections migration rollback")

            # Drop family management collections
            family_collections = [
                "families",
                "family_relationships",
                "family_invitations",
                "family_notifications",
                "family_token_requests",
            ]

            for collection_name in family_collections:
                try:
                    await self.database.drop_collection(collection_name)
                    collections_dropped.append(collection_name)
                    self.logger.info("Dropped collection: %s", collection_name)
                except Exception as e:
                    self.logger.warning("Failed to drop collection %s: %s", collection_name, e)

            # Remove family fields from users collection
            users_collection = db_manager.get_collection("users")
            result = await users_collection.update_many(
                {}, {"$unset": {"family_limits": "", "family_memberships": "", "family_notifications": ""}}
            )

            self.logger.info("Removed family fields from %d user documents", result.modified_count)

            self.logger.info("Family collections migration rollback completed")

            return {"collections_dropped": collections_dropped, "users_updated": result.modified_count}

        except Exception as e:
            self.logger.error("Migration rollback failed: %s", e, exc_info=True)
            raise Exception(f"Rollback failed: {str(e)}")

    async def _create_families_collection(self):
        """Create the families collection with proper schema."""
        try:
            # Create collection
            families_collection = db_manager.get_collection("families")

            # Create a sample document to establish schema (will be removed)
            sample_doc = {
                "_schema_version": "1.0.0",
                "family_id": f"sample_{uuid.uuid4().hex[:8]}",
                "name": "Sample Family",
                "admin_user_ids": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "member_count": 0,
                "is_active": True,
                "sbd_account": {
                    "account_username": "family_sample",
                    "is_frozen": False,
                    "frozen_by": None,
                    "frozen_at": None,
                    "spending_permissions": {},
                    "notification_settings": {
                        "notify_on_spend": True,
                        "notify_on_deposit": True,
                        "large_transaction_threshold": 1000,
                        "notify_admins_only": False,
                    },
                },
                "settings": {
                    "allow_member_invites": False,
                    "visibility": "private",
                    "auto_approval_threshold": 100,
                    "request_expiry_hours": 168,
                },
                "succession_plan": {"backup_admins": [], "recovery_contacts": []},
            }

            await families_collection.insert_one(sample_doc)
            await families_collection.delete_one({"family_id": sample_doc["family_id"]})

            self.logger.info("Created families collection")

        except Exception as e:
            self.logger.error("Failed to create families collection: %s", e, exc_info=True)
            raise

    async def _create_family_relationships_collection(self):
        """Create the family_relationships collection."""
        try:
            relationships_collection = db_manager.get_collection("family_relationships")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "relationship_id": f"rel_{uuid.uuid4().hex[:8]}",
                "family_id": f"fam_{uuid.uuid4().hex[:8]}",
                "user_a_id": "sample_user_a",
                "user_b_id": "sample_user_b",
                "relationship_type_a_to_b": "parent",
                "relationship_type_b_to_a": "child",
                "status": "active",
                "created_by": "sample_user_a",
                "created_at": datetime.now(timezone.utc),
                "activated_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            await relationships_collection.insert_one(sample_doc)
            await relationships_collection.delete_one({"relationship_id": sample_doc["relationship_id"]})

            self.logger.info("Created family_relationships collection")

        except Exception as e:
            self.logger.error("Failed to create family_relationships collection: %s", e, exc_info=True)
            raise

    async def _create_family_invitations_collection(self):
        """Create the family_invitations collection with TTL."""
        try:
            invitations_collection = db_manager.get_collection("family_invitations")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "invitation_id": f"inv_{uuid.uuid4().hex[:8]}",
                "family_id": f"fam_{uuid.uuid4().hex[:8]}",
                "inviter_user_id": "sample_inviter",
                "invitee_email": "sample@example.com",
                "invitee_user_id": "sample_invitee",
                "relationship_type": "child",
                "invitation_token": "sample_token",
                "status": "pending",
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                "created_at": datetime.now(timezone.utc),
                "responded_at": None,
                "email_sent": False,
                "email_sent_at": None,
            }

            await invitations_collection.insert_one(sample_doc)
            await invitations_collection.delete_one({"invitation_id": sample_doc["invitation_id"]})

            self.logger.info("Created family_invitations collection")

        except Exception as e:
            self.logger.error("Failed to create family_invitations collection: %s", e, exc_info=True)
            raise

    async def _create_family_notifications_collection(self):
        """Create the family_notifications collection."""
        try:
            notifications_collection = db_manager.get_collection("family_notifications")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "notification_id": f"notif_{uuid.uuid4().hex[:8]}",
                "family_id": f"fam_{uuid.uuid4().hex[:8]}",
                "recipient_user_ids": ["sample_user"],
                "type": "sbd_spend",
                "title": "Sample Notification",
                "message": "This is a sample notification",
                "data": {"transaction_id": "sample_tx", "amount": 100},
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
                "sent_at": None,
                "read_by": {},
            }

            await notifications_collection.insert_one(sample_doc)
            await notifications_collection.delete_one({"notification_id": sample_doc["notification_id"]})

            self.logger.info("Created family_notifications collection")

        except Exception as e:
            self.logger.error("Failed to create family_notifications collection: %s", e, exc_info=True)
            raise

    async def _create_family_token_requests_collection(self):
        """Create the family_token_requests collection with TTL."""
        try:
            token_requests_collection = db_manager.get_collection("family_token_requests")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "request_id": f"req_{uuid.uuid4().hex[:8]}",
                "family_id": f"fam_{uuid.uuid4().hex[:8]}",
                "requester_user_id": "sample_requester",
                "amount": 100,
                "reason": "Sample token request",
                "status": "pending",
                "reviewed_by": None,
                "admin_comments": None,
                "auto_approved": False,
                "created_at": datetime.now(timezone.utc),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                "reviewed_at": None,
                "processed_at": None,
            }

            await token_requests_collection.insert_one(sample_doc)
            await token_requests_collection.delete_one({"request_id": sample_doc["request_id"]})

            self.logger.info("Created family_token_requests collection")

        except Exception as e:
            self.logger.error("Failed to create family_token_requests collection: %s", e, exc_info=True)
            raise

    async def _update_users_collection_schema(self) -> int:
        """Update users collection to include family-related fields."""
        try:
            users_collection = db_manager.get_collection("users")

            # Add family-related fields to users who don't have them
            result = await users_collection.update_many(
                {
                    "$or": [
                        {"family_limits": {"$exists": False}},
                        {"family_memberships": {"$exists": False}},
                        {"family_notifications": {"$exists": False}},
                    ]
                },
                {
                    "$set": {
                        "family_limits": {
                            "max_families_allowed": 1,
                            "max_members_per_family": 5,
                            "updated_at": datetime.now(timezone.utc),
                            "updated_by": "system_migration",
                        },
                        "family_memberships": [],
                        "family_notifications": {
                            "unread_count": 0,
                            "last_checked": datetime.now(timezone.utc),
                            "preferences": {
                                "email_notifications": True,
                                "push_notifications": True,
                                "sms_notifications": False,
                            },
                        },
                    }
                },
            )

            self.logger.info("Updated %d user documents with family fields", result.modified_count)
            return result.modified_count

        except Exception as e:
            self.logger.error("Failed to update users collection schema: %s", e, exc_info=True)
            raise

    async def _create_all_indexes(self):
        """Create all necessary indexes for family collections."""
        try:
            self.logger.info("Creating indexes for family collections")

            # Families collection indexes
            families_collection = db_manager.get_collection("families")
            await families_collection.create_index("family_id", unique=True)
            await families_collection.create_index("admin_user_ids")
            await families_collection.create_index("is_active")
            await families_collection.create_index("sbd_account.account_username", unique=True, sparse=True)
            await families_collection.create_index([("admin_user_ids", 1), ("is_active", 1)])
            await families_collection.create_index("created_at")

            # Family relationships collection indexes
            relationships_collection = db_manager.get_collection("family_relationships")
            await relationships_collection.create_index("relationship_id", unique=True)
            await relationships_collection.create_index("family_id")
            await relationships_collection.create_index("user_a_id")
            await relationships_collection.create_index("user_b_id")
            await relationships_collection.create_index("status")
            await relationships_collection.create_index(
                [("user_a_id", 1), ("user_b_id", 1), ("family_id", 1)], unique=True
            )
            await relationships_collection.create_index([("family_id", 1), ("status", 1)])

            # Family invitations collection indexes
            invitations_collection = db_manager.get_collection("family_invitations")
            await invitations_collection.create_index("invitation_id", unique=True)
            await invitations_collection.create_index("invitation_token", unique=True)
            await invitations_collection.create_index("family_id")
            await invitations_collection.create_index("invitee_email")
            await invitations_collection.create_index("invitee_user_id")
            await invitations_collection.create_index("expires_at", expireAfterSeconds=0)
            await invitations_collection.create_index([("family_id", 1), ("status", 1)])

            # Family notifications collection indexes
            notifications_collection = db_manager.get_collection("family_notifications")
            await notifications_collection.create_index("notification_id", unique=True)
            await notifications_collection.create_index("family_id")
            await notifications_collection.create_index("recipient_user_ids")
            await notifications_collection.create_index("type")
            await notifications_collection.create_index("status")
            await notifications_collection.create_index([("family_id", 1), ("status", 1)])
            await notifications_collection.create_index([("recipient_user_ids", 1), ("status", 1)])
            await notifications_collection.create_index("created_at")

            # Family token requests collection indexes
            token_requests_collection = db_manager.get_collection("family_token_requests")
            await token_requests_collection.create_index("request_id", unique=True)
            await token_requests_collection.create_index("family_id")
            await token_requests_collection.create_index("requester_user_id")
            await token_requests_collection.create_index("status")
            await token_requests_collection.create_index("expires_at", expireAfterSeconds=0)
            await token_requests_collection.create_index([("family_id", 1), ("status", 1)])
            await token_requests_collection.create_index([("requester_user_id", 1), ("status", 1)])
            await token_requests_collection.create_index("created_at")

            self.logger.info("All family collection indexes created successfully")

        except Exception as e:
            self.logger.error("Failed to create family collection indexes: %s", e, exc_info=True)
            raise
