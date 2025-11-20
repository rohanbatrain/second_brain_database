"""
Database backup and recovery manager for Second Brain Database.

This module provides comprehensive backup and recovery functionality
with support for full and incremental backups, compression, and
automated retention policies.
"""

from datetime import datetime, timedelta, timezone
import gzip
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from bson import ObjectId
from pymongo.errors import PyMongoError

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[BackupManager]")


class BackupManager:
    """
    Manages database backups and recovery operations.

    Features:
    - Full and incremental backups
    - Compression support
    - Automated retention policies
    - Backup verification
    - Point-in-time recovery
    - Family collection specific backups
    """

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.logger = logger

        # Family collections for targeted backups
        self.family_collections = [
            "families",
            "family_relationships",
            "family_invitations",
            "family_notifications",
            "family_token_requests",
        ]

    async def create_full_backup(self, include_collections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Create a full database backup.

        Args:
            include_collections: Specific collections to backup (None for all)

        Returns:
            Dict containing backup information
        """
        backup_id = f"full_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)

        try:
            self.logger.info("Starting full backup: %s", backup_id)

            # Get collections to backup
            if include_collections is None:
                if db_manager.database is None:
                    raise Exception("Database not connected")
                include_collections = await db_manager.database.list_collection_names()

            backup_data = {}
            total_records = 0

            for collection_name in include_collections:
                collection_data = await self._backup_collection(collection_name)
                backup_data[collection_name] = collection_data
                total_records += len(collection_data)

                self.logger.debug("Backed up %d records from %s", len(collection_data), collection_name)

            # Create backup metadata
            backup_metadata = {
                "backup_id": backup_id,
                "backup_type": "full",
                "created_at": start_time,
                "collections": include_collections,
                "total_records": total_records,
                "database_name": settings.MONGODB_DATABASE,
                "version": "1.0.0",
            }

            # Save backup to file
            backup_file = await self._save_backup_to_file(backup_id, backup_data, backup_metadata)

            # Record backup in database
            await self._record_backup_metadata(backup_metadata, backup_file)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info("Full backup completed: %s (%.2f seconds, %d records)", backup_id, duration, total_records)

            return {
                "backup_id": backup_id,
                "backup_type": "full",
                "file_path": str(backup_file),
                "file_size": backup_file.stat().st_size,
                "collections": include_collections,
                "total_records": total_records,
                "duration_seconds": duration,
                "created_at": start_time,
            }

        except Exception as e:
            self.logger.error("Full backup failed: %s", e, exc_info=True)
            raise Exception(f"Full backup failed: {str(e)}")

    async def create_family_backup(self) -> Dict[str, Any]:
        """
        Create a backup of only family-related collections.

        Returns:
            Dict containing backup information
        """
        backup_id = f"family_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)

        try:
            self.logger.info("Starting family collections backup: %s", backup_id)

            backup_data = {}
            total_records = 0

            # Backup family collections
            for collection_name in self.family_collections:
                try:
                    collection_data = await self._backup_collection(collection_name)
                    backup_data[collection_name] = collection_data
                    total_records += len(collection_data)

                    self.logger.debug("Backed up %d records from %s", len(collection_data), collection_name)
                except Exception as e:
                    self.logger.warning("Failed to backup collection %s: %s", collection_name, e)
                    backup_data[collection_name] = []

            # Also backup relevant user data (family fields only)
            user_family_data = await self._backup_user_family_data()
            backup_data["users_family_data"] = user_family_data
            total_records += len(user_family_data)

            # Create backup metadata
            backup_metadata = {
                "backup_id": backup_id,
                "backup_type": "family",
                "created_at": start_time,
                "collections": self.family_collections + ["users_family_data"],
                "total_records": total_records,
                "database_name": settings.MONGODB_DATABASE,
                "version": "1.0.0",
            }

            # Save backup to file
            backup_file = await self._save_backup_to_file(backup_id, backup_data, backup_metadata)

            # Record backup in database
            await self._record_backup_metadata(backup_metadata, backup_file)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info(
                "Family backup completed: %s (%.2f seconds, %d records)", backup_id, duration, total_records
            )

            return {
                "backup_id": backup_id,
                "backup_type": "family",
                "file_path": str(backup_file),
                "file_size": backup_file.stat().st_size,
                "collections": self.family_collections,
                "total_records": total_records,
                "duration_seconds": duration,
                "created_at": start_time,
            }

        except Exception as e:
            self.logger.error("Family backup failed: %s", e, exc_info=True)
            raise Exception(f"Family backup failed: {str(e)}")

    async def restore_from_backup(self, backup_id: str, collections: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Restore database from a backup.

        Args:
            backup_id: ID of the backup to restore from
            collections: Specific collections to restore (None for all)

        Returns:
            Dict containing restore results
        """
        start_time = datetime.now(timezone.utc)

        try:
            self.logger.info("Starting restore from backup: %s", backup_id)

            # Load backup data
            backup_data, backup_metadata = await self._load_backup_from_file(backup_id)

            if collections is None:
                collections = backup_metadata["collections"]

            total_restored = 0
            collections_restored = []

            for collection_name in collections:
                if collection_name not in backup_data:
                    self.logger.warning("Collection %s not found in backup", collection_name)
                    continue

                if collection_name == "users_family_data":
                    # Special handling for user family data
                    restored_count = await self._restore_user_family_data(backup_data[collection_name])
                else:
                    restored_count = await self._restore_collection(collection_name, backup_data[collection_name])

                total_restored += restored_count
                collections_restored.append(collection_name)

                self.logger.info("Restored %d records to %s", restored_count, collection_name)

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.logger.info("Restore completed: %s (%.2f seconds, %d records)", backup_id, duration, total_restored)

            return {
                "backup_id": backup_id,
                "collections_restored": collections_restored,
                "total_records_restored": total_restored,
                "duration_seconds": duration,
                "restored_at": start_time,
            }

        except Exception as e:
            self.logger.error("Restore failed: %s", e, exc_info=True)
            raise Exception(f"Restore failed: {str(e)}")

    async def list_backups(self) -> List[Dict[str, Any]]:
        """
        List all available backups.

        Returns:
            List of backup information
        """
        try:
            backups_collection = db_manager.get_collection("backup_metadata")
            cursor = backups_collection.find({}).sort("created_at", -1)

            backups = []
            async for backup in cursor:
                backup.pop("_id", None)  # Remove MongoDB ObjectId

                # Add file information if file exists
                backup_file = self.backup_dir / f"{backup['backup_id']}.json.gz"
                if backup_file.exists():
                    backup["file_exists"] = True
                    backup["file_size"] = backup_file.stat().st_size
                else:
                    backup["file_exists"] = False
                    backup["file_size"] = 0

                backups.append(backup)

            self.logger.debug("Found %d backups", len(backups))
            return backups

        except Exception as e:
            self.logger.error("Failed to list backups: %s", e, exc_info=True)
            raise Exception(f"Failed to list backups: {str(e)}")

    async def delete_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        Delete a backup and its associated files.

        Args:
            backup_id: ID of the backup to delete

        Returns:
            Dict containing deletion results
        """
        try:
            self.logger.info("Deleting backup: %s", backup_id)

            # Remove backup file
            backup_file = self.backup_dir / f"{backup_id}.json.gz"
            file_deleted = False
            if backup_file.exists():
                backup_file.unlink()
                file_deleted = True
                self.logger.debug("Deleted backup file: %s", backup_file)

            # Remove metadata from database
            backups_collection = db_manager.get_collection("backup_metadata")
            result = await backups_collection.delete_one({"backup_id": backup_id})

            self.logger.info(
                "Backup deleted: %s (file: %s, metadata: %s)", backup_id, file_deleted, result.deleted_count > 0
            )

            return {"backup_id": backup_id, "file_deleted": file_deleted, "metadata_deleted": result.deleted_count > 0}

        except Exception as e:
            self.logger.error("Failed to delete backup %s: %s", backup_id, e, exc_info=True)
            raise Exception(f"Failed to delete backup: {str(e)}")

    async def cleanup_old_backups(self, retention_days: int = 30) -> Dict[str, Any]:
        """
        Clean up backups older than retention period.

        Args:
            retention_days: Number of days to retain backups

        Returns:
            Dict containing cleanup results
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            self.logger.info("Cleaning up backups older than %s", cutoff_date)

            # Find old backups
            backups_collection = db_manager.get_collection("backup_metadata")
            old_backups_cursor = backups_collection.find({"created_at": {"$lt": cutoff_date}})

            deleted_backups = []
            total_size_freed = 0

            async for backup in old_backups_cursor:
                backup_id = backup["backup_id"]

                try:
                    # Delete backup file
                    backup_file = self.backup_dir / f"{backup_id}.json.gz"
                    if backup_file.exists():
                        file_size = backup_file.stat().st_size
                        backup_file.unlink()
                        total_size_freed += file_size

                    # Delete metadata
                    await backups_collection.delete_one({"backup_id": backup_id})

                    deleted_backups.append(backup_id)
                    self.logger.debug("Deleted old backup: %s", backup_id)

                except Exception as e:
                    self.logger.warning("Failed to delete backup %s: %s", backup_id, e)

            self.logger.info(
                "Cleanup completed: %d backups deleted, %d bytes freed", len(deleted_backups), total_size_freed
            )

            return {
                "deleted_backups": deleted_backups,
                "total_deleted": len(deleted_backups),
                "total_size_freed": total_size_freed,
                "retention_days": retention_days,
            }

        except Exception as e:
            self.logger.error("Backup cleanup failed: %s", e, exc_info=True)
            raise Exception(f"Backup cleanup failed: {str(e)}")

    async def verify_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        Verify the integrity of a backup.

        Args:
            backup_id: ID of the backup to verify

        Returns:
            Dict containing verification results
        """
        try:
            self.logger.info("Verifying backup: %s", backup_id)

            # Load backup data
            backup_data, backup_metadata = await self._load_backup_from_file(backup_id)

            verification_results = {
                "backup_id": backup_id,
                "is_valid": True,
                "errors": [],
                "warnings": [],
                "collections_verified": 0,
                "total_records_verified": 0,
            }

            # Verify metadata
            required_fields = ["backup_id", "backup_type", "created_at", "collections", "total_records"]
            for field in required_fields:
                if field not in backup_metadata:
                    verification_results["errors"].append(f"Missing metadata field: {field}")
                    verification_results["is_valid"] = False

            # Verify collections
            for collection_name in backup_metadata.get("collections", []):
                if collection_name not in backup_data:
                    verification_results["errors"].append(f"Missing collection data: {collection_name}")
                    verification_results["is_valid"] = False
                else:
                    collection_data = backup_data[collection_name]
                    if not isinstance(collection_data, list):
                        verification_results["errors"].append(f"Invalid collection data format: {collection_name}")
                        verification_results["is_valid"] = False
                    else:
                        verification_results["collections_verified"] += 1
                        verification_results["total_records_verified"] += len(collection_data)

            # Verify record count matches metadata
            if verification_results["total_records_verified"] != backup_metadata.get("total_records", 0):
                verification_results["warnings"].append("Record count mismatch between data and metadata")

            self.logger.info(
                "Backup verification completed: %s (valid: %s)", backup_id, verification_results["is_valid"]
            )

            return verification_results

        except Exception as e:
            self.logger.error("Backup verification failed: %s", e, exc_info=True)
            return {
                "backup_id": backup_id,
                "is_valid": False,
                "errors": [f"Verification failed: {str(e)}"],
                "warnings": [],
                "collections_verified": 0,
                "total_records_verified": 0,
            }

    async def _backup_collection(self, collection_name: str) -> List[Dict[str, Any]]:
        """Backup a single collection."""
        try:
            collection = db_manager.get_collection(collection_name)
            documents = []

            async for doc in collection.find({}):
                # Convert ObjectId to string for JSON serialization
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                documents.append(doc)

            return documents

        except Exception as e:
            self.logger.error("Failed to backup collection %s: %s", collection_name, e, exc_info=True)
            raise

    async def _backup_user_family_data(self) -> List[Dict[str, Any]]:
        """Backup only family-related fields from users collection."""
        try:
            users_collection = db_manager.get_collection("users")
            user_family_data = []

            # Only backup family-related fields
            projection = {
                "_id": 1,
                "username": 1,
                "email": 1,
                "family_limits": 1,
                "family_memberships": 1,
                "family_notifications": 1,
            }

            async for user in users_collection.find({}, projection):
                if "_id" in user:
                    user["_id"] = str(user["_id"])
                user_family_data.append(user)

            return user_family_data

        except Exception as e:
            self.logger.error("Failed to backup user family data: %s", e, exc_info=True)
            raise

    async def _restore_collection(self, collection_name: str, documents: List[Dict[str, Any]]) -> int:
        """Restore a single collection."""
        try:
            if not documents:
                return 0

            collection = db_manager.get_collection(collection_name)

            # Clear existing data
            await collection.delete_many({})

            # Convert string IDs back to ObjectId if needed
            for doc in documents:
                if "_id" in doc and isinstance(doc["_id"], str):
                    try:
                        doc["_id"] = ObjectId(doc["_id"])
                    except:
                        # If conversion fails, remove _id and let MongoDB generate new one
                        doc.pop("_id", None)

            # Insert documents
            if documents:
                await collection.insert_many(documents)

            return len(documents)

        except Exception as e:
            self.logger.error("Failed to restore collection %s: %s", collection_name, e, exc_info=True)
            raise

    async def _restore_user_family_data(self, user_family_data: List[Dict[str, Any]]) -> int:
        """Restore family-related fields to users collection."""
        try:
            if not user_family_data:
                return 0

            users_collection = db_manager.get_collection("users")
            restored_count = 0

            for user_data in user_family_data:
                user_id = user_data.get("_id")
                if not user_id:
                    continue

                # Convert string ID back to ObjectId
                if isinstance(user_id, str):
                    try:
                        user_id = ObjectId(user_id)
                    except Exception:  # TODO: Use specific exception type
                        continue

                # Update user with family data
                update_data = {}
                for field in ["family_limits", "family_memberships", "family_notifications"]:
                    if field in user_data:
                        update_data[field] = user_data[field]

                if update_data:
                    result = await users_collection.update_one({"_id": user_id}, {"$set": update_data})
                    if result.modified_count > 0:
                        restored_count += 1

            return restored_count

        except Exception as e:
            self.logger.error("Failed to restore user family data: %s", e, exc_info=True)
            raise

    async def _save_backup_to_file(
        self, backup_id: str, backup_data: Dict[str, Any], backup_metadata: Dict[str, Any]
    ) -> Path:
        """Save backup data to compressed file."""
        try:
            backup_file = self.backup_dir / f"{backup_id}.json.gz"

            # Combine metadata and data
            full_backup = {"metadata": backup_metadata, "data": backup_data}

            # Save as compressed JSON
            with gzip.open(backup_file, "wt", encoding="utf-8") as f:
                json.dump(full_backup, f, default=str, indent=2)

            self.logger.debug("Saved backup to file: %s (%d bytes)", backup_file, backup_file.stat().st_size)

            return backup_file

        except Exception as e:
            self.logger.error("Failed to save backup to file: %s", e, exc_info=True)
            raise

    async def _load_backup_from_file(self, backup_id: str) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Load backup data from compressed file."""
        try:
            backup_file = self.backup_dir / f"{backup_id}.json.gz"

            if not backup_file.exists():
                raise Exception(f"Backup file not found: {backup_file}")

            with gzip.open(backup_file, "rt", encoding="utf-8") as f:
                full_backup = json.load(f)

            backup_metadata = full_backup.get("metadata", {})
            backup_data = full_backup.get("data", {})

            self.logger.debug("Loaded backup from file: %s", backup_file)

            return backup_data, backup_metadata

        except Exception as e:
            self.logger.error("Failed to load backup from file: %s", e, exc_info=True)
            raise

    async def _record_backup_metadata(self, backup_metadata: Dict[str, Any], backup_file: Path):
        """Record backup metadata in database."""
        try:
            backups_collection = db_manager.get_collection("backup_metadata")

            # Add file information
            backup_metadata.update(
                {
                    "file_path": str(backup_file),
                    "file_size": backup_file.stat().st_size,
                    "checksum": await self._calculate_file_checksum(backup_file),
                }
            )

            await backups_collection.insert_one(backup_metadata)

            self.logger.debug("Recorded backup metadata: %s", backup_metadata["backup_id"])

        except Exception as e:
            self.logger.error("Failed to record backup metadata: %s", e, exc_info=True)
            raise

    async def _calculate_file_checksum(self, file_path: Path) -> str:
        """Calculate SHA-256 checksum of a file."""
        import hashlib

        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(chunk)

            return sha256_hash.hexdigest()

        except Exception as e:
            self.logger.error("Failed to calculate checksum: %s", e, exc_info=True)
            return ""


# Global backup manager instance
backup_manager = BackupManager()
