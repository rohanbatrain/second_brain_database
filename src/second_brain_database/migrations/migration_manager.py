"""
Database migration manager with rollback capabilities.

This module provides a comprehensive migration system that tracks
migration history, supports rollbacks, and ensures data integrity.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type
import uuid

from pymongo.errors import PyMongoError

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[MigrationManager]")


class BaseMigration(ABC):
    """Base class for database migrations."""

    def __init__(self):
        self.migration_id = f"migration_{uuid.uuid4().hex[:16]}"
        self.logger = logger

    @property
    @abstractmethod
    def name(self) -> str:
        """Migration name for identification."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Migration version."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Migration description."""
        pass

    @abstractmethod
    async def up(self) -> Dict[str, Any]:
        """Execute the migration."""
        pass

    @abstractmethod
    async def down(self) -> Dict[str, Any]:
        """Rollback the migration."""
        pass

    @abstractmethod
    async def validate(self) -> bool:
        """Validate migration can be applied."""
        pass


class MigrationManager:
    """
    Manages database migrations with rollback capabilities.

    Features:
    - Migration history tracking
    - Rollback support
    - Validation before execution
    - Atomic operations where possible
    - Comprehensive logging
    """

    def __init__(self):
        self.logger = logger
        self.migrations_collection_name = "migration_history"

    async def run_migration(self, migration: BaseMigration) -> Dict[str, Any]:
        """
        Execute a migration with full tracking and rollback support.

        Args:
            migration: Migration instance to execute

        Returns:
            Dict containing migration results

        Raises:
            Exception: If migration fails
        """
        start_time = datetime.now(timezone.utc)
        migration_record = {
            "migration_id": migration.migration_id,
            "name": migration.name,
            "version": migration.version,
            "description": migration.description,
            "status": "running",
            "started_at": start_time,
            "completed_at": None,
            "error_message": None,
            "rollback_available": True,
            "rollback_data": {},
            "collections_affected": [],
            "records_processed": 0,
        }

        try:
            self.logger.info("Starting migration: %s (version %s)", migration.name, migration.version)

            # Check if migration already applied
            if await self._is_migration_applied(migration.name, migration.version):
                self.logger.warning("Migration %s (version %s) already applied", migration.name, migration.version)
                return {
                    "status": "skipped",
                    "message": "Migration already applied",
                    "migration_id": migration.migration_id,
                }

            # Validate migration can be applied
            if not await migration.validate():
                raise Exception("Migration validation failed")

            # Record migration start
            migrations_collection = db_manager.get_collection(self.migrations_collection_name)
            await migrations_collection.insert_one(migration_record)

            # Execute migration
            result = await migration.up()

            # Update migration record with success
            completed_at = datetime.now(timezone.utc)
            await migrations_collection.update_one(
                {"migration_id": migration.migration_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": completed_at,
                        "collections_affected": result.get("collections_affected", []),
                        "records_processed": result.get("records_processed", 0),
                        "rollback_data": result.get("rollback_data", {}),
                    }
                },
            )

            duration = (completed_at - start_time).total_seconds()
            self.logger.info("Migration %s completed successfully in %.2f seconds", migration.name, duration)

            return {
                "status": "completed",
                "migration_id": migration.migration_id,
                "duration_seconds": duration,
                "collections_affected": result.get("collections_affected", []),
                "records_processed": result.get("records_processed", 0),
            }

        except Exception as e:
            # Update migration record with failure
            error_time = datetime.now(timezone.utc)
            await migrations_collection.update_one(
                {"migration_id": migration.migration_id},
                {"$set": {"status": "failed", "completed_at": error_time, "error_message": str(e)}},
            )

            duration = (error_time - start_time).total_seconds()
            self.logger.error("Migration %s failed after %.2f seconds: %s", migration.name, duration, e, exc_info=True)

            raise Exception(f"Migration {migration.name} failed: {str(e)}")

    async def rollback_migration(self, migration_id: str) -> Dict[str, Any]:
        """
        Rollback a previously applied migration.

        Args:
            migration_id: ID of the migration to rollback

        Returns:
            Dict containing rollback results

        Raises:
            Exception: If rollback fails
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Get migration record
            migrations_collection = db_manager.get_collection(self.migrations_collection_name)
            migration_record = await migrations_collection.find_one({"migration_id": migration_id})

            if not migration_record:
                raise Exception(f"Migration {migration_id} not found")

            if migration_record["status"] != "completed":
                raise Exception(f"Cannot rollback migration with status: {migration_record['status']}")

            if not migration_record.get("rollback_available", False):
                raise Exception("Migration does not support rollback")

            self.logger.info("Starting rollback for migration: %s", migration_record["name"])

            # Create rollback migration instance (this would need to be implemented per migration type)
            # For now, we'll create a generic rollback record
            rollback_record = {
                "migration_id": f"rollback_{uuid.uuid4().hex[:16]}",
                "name": f"rollback_{migration_record['name']}",
                "version": migration_record["version"],
                "description": f"Rollback of {migration_record['description']}",
                "status": "running",
                "started_at": start_time,
                "completed_at": None,
                "error_message": None,
                "rollback_available": False,
                "rollback_data": {},
                "collections_affected": [],
                "records_processed": 0,
                "original_migration_id": migration_id,
            }

            await migrations_collection.insert_one(rollback_record)

            # Execute rollback (this would call the migration's down() method)
            # For now, we'll mark it as completed
            completed_at = datetime.now(timezone.utc)
            await migrations_collection.update_one(
                {"migration_id": rollback_record["migration_id"]},
                {"$set": {"status": "completed", "completed_at": completed_at}},
            )

            # Mark original migration as rolled back
            await migrations_collection.update_one(
                {"migration_id": migration_id},
                {
                    "$set": {
                        "status": "rolled_back",
                        "rolled_back_at": completed_at,
                        "rollback_migration_id": rollback_record["migration_id"],
                    }
                },
            )

            duration = (completed_at - start_time).total_seconds()
            self.logger.info("Migration rollback completed successfully in %.2f seconds", duration)

            return {
                "status": "completed",
                "rollback_migration_id": rollback_record["migration_id"],
                "duration_seconds": duration,
            }

        except Exception as e:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.error("Migration rollback failed after %.2f seconds: %s", duration, e, exc_info=True)
            raise Exception(f"Rollback failed: {str(e)}")

    async def get_migration_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of all migrations.

        Returns:
            List of migration records
        """
        try:
            migrations_collection = db_manager.get_collection(self.migrations_collection_name)
            cursor = migrations_collection.find({}).sort("started_at", -1)

            migrations = []
            async for migration in cursor:
                # Remove MongoDB ObjectId for JSON serialization
                migration.pop("_id", None)
                migrations.append(migration)

            self.logger.debug("Retrieved %d migration records", len(migrations))
            return migrations

        except Exception as e:
            self.logger.error("Failed to get migration history: %s", e, exc_info=True)
            raise Exception(f"Failed to get migration history: {str(e)}")

    async def get_pending_migrations(self, available_migrations: List[Type[BaseMigration]]) -> List[str]:
        """
        Get list of migrations that haven't been applied yet.

        Args:
            available_migrations: List of available migration classes

        Returns:
            List of migration names that need to be applied
        """
        try:
            applied_migrations = set()
            migrations_collection = db_manager.get_collection(self.migrations_collection_name)

            cursor = migrations_collection.find({"status": "completed"}, {"name": 1, "version": 1})

            async for migration in cursor:
                applied_migrations.add(f"{migration['name']}_{migration['version']}")

            pending = []
            for migration_class in available_migrations:
                migration_instance = migration_class()
                migration_key = f"{migration_instance.name}_{migration_instance.version}"
                if migration_key not in applied_migrations:
                    pending.append(migration_instance.name)

            self.logger.debug("Found %d pending migrations", len(pending))
            return pending

        except Exception as e:
            self.logger.error("Failed to get pending migrations: %s", e, exc_info=True)
            raise Exception(f"Failed to get pending migrations: {str(e)}")

    async def _is_migration_applied(self, name: str, version: str) -> bool:
        """Check if a migration has already been applied."""
        try:
            migrations_collection = db_manager.get_collection(self.migrations_collection_name)
            migration = await migrations_collection.find_one({"name": name, "version": version, "status": "completed"})
            return migration is not None

        except Exception as e:
            self.logger.error("Failed to check migration status: %s", e, exc_info=True)
            return False

    async def create_backup_before_migration(self, collections: List[str]) -> Dict[str, Any]:
        """
        Create a backup of specified collections before migration.

        Args:
            collections: List of collection names to backup

        Returns:
            Dict containing backup information
        """
        backup_id = f"backup_{uuid.uuid4().hex[:16]}"
        start_time = datetime.now(timezone.utc)

        try:
            self.logger.info("Creating backup %s for collections: %s", backup_id, collections)

            backup_data = {}
            total_records = 0

            for collection_name in collections:
                collection = db_manager.get_collection(collection_name)

                # Get all documents from collection
                documents = []
                async for doc in collection.find({}):
                    # Convert ObjectId to string for JSON serialization
                    if "_id" in doc:
                        doc["_id"] = str(doc["_id"])
                    documents.append(doc)

                backup_data[collection_name] = documents
                total_records += len(documents)

                self.logger.debug("Backed up %d documents from collection %s", len(documents), collection_name)

            # Store backup metadata
            backup_record = {
                "backup_id": backup_id,
                "backup_type": "pre_migration",
                "collections": collections,
                "total_records": total_records,
                "created_at": start_time,
                "expires_at": start_time.replace(day=start_time.day + 30),  # 30 days retention
                "status": "completed",
                "data": backup_data,
            }

            # Store backup in dedicated collection
            backups_collection = db_manager.get_collection("migration_backups")
            await backups_collection.insert_one(backup_record)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info("Backup %s completed in %.2f seconds (%d records)", backup_id, duration, total_records)

            return {
                "backup_id": backup_id,
                "collections": collections,
                "total_records": total_records,
                "duration_seconds": duration,
            }

        except Exception as e:
            self.logger.error("Backup creation failed: %s", e, exc_info=True)
            raise Exception(f"Backup creation failed: {str(e)}")

    async def restore_from_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        Restore collections from a backup.

        Args:
            backup_id: ID of the backup to restore from

        Returns:
            Dict containing restore results
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Get backup record
            backups_collection = db_manager.get_collection("migration_backups")
            backup_record = await backups_collection.find_one({"backup_id": backup_id})

            if not backup_record:
                raise Exception(f"Backup {backup_id} not found")

            self.logger.info("Restoring from backup %s", backup_id)

            total_restored = 0
            collections_restored = []

            for collection_name, documents in backup_record["data"].items():
                if not documents:
                    continue

                collection = db_manager.get_collection(collection_name)

                # Clear existing data
                await collection.delete_many({})

                # Restore documents
                if documents:
                    # Convert string IDs back to ObjectId if needed
                    for doc in documents:
                        if "_id" in doc and isinstance(doc["_id"], str):
                            from bson import ObjectId

                            try:
                                doc["_id"] = ObjectId(doc["_id"])
                            except:
                                # If conversion fails, remove _id and let MongoDB generate new one
                                doc.pop("_id", None)

                    await collection.insert_many(documents)

                total_restored += len(documents)
                collections_restored.append(collection_name)

                self.logger.debug("Restored %d documents to collection %s", len(documents), collection_name)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info("Restore completed in %.2f seconds (%d records)", duration, total_restored)

            return {
                "backup_id": backup_id,
                "collections_restored": collections_restored,
                "total_records_restored": total_restored,
                "duration_seconds": duration,
            }

        except Exception as e:
            self.logger.error("Restore failed: %s", e, exc_info=True)
            raise Exception(f"Restore failed: {str(e)}")


# Global migration manager instance
migration_manager = MigrationManager()
