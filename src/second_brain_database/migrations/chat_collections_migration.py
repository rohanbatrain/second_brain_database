"""
Migration for creating chat system collections and indexes.

This migration creates all necessary collections for the LangGraph-based chat system
with proper indexes, constraints, and TTL configurations.
"""

from datetime import datetime, timezone
from typing import Any, Dict
import uuid

from pymongo.errors import PyMongoError

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

from .migration_manager import BaseMigration

logger = get_logger(prefix="[ChatCollectionsMigration]")


class ChatCollectionsMigration(BaseMigration):
    """
    Migration to create chat system collections with proper schema and indexes.

    This migration creates:
    - chat_sessions collection with indexes
    - chat_messages collection with indexes
    - token_usage collection with indexes
    - message_votes collection with indexes and unique constraints
    """

    @property
    def name(self) -> str:
        return "create_chat_collections"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Create chat system collections with proper indexes and constraints"

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
            chat_collections = [
                "chat_sessions",
                "chat_messages",
                "token_usage",
                "message_votes",
            ]

            for collection_name in chat_collections:
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
        """Execute the migration to create chat collections."""
        collections_affected = []
        records_processed = 0
        rollback_data = {}

        try:
            self.logger.info("Starting chat collections migration")

            # Create chat_sessions collection
            await self._create_chat_sessions_collection()
            collections_affected.append("chat_sessions")

            # Create chat_messages collection
            await self._create_chat_messages_collection()
            collections_affected.append("chat_messages")

            # Create token_usage collection
            await self._create_token_usage_collection()
            collections_affected.append("token_usage")

            # Create message_votes collection
            await self._create_message_votes_collection()
            collections_affected.append("message_votes")

            # Create all indexes
            await self._create_all_indexes()

            # Store rollback data
            rollback_data = {
                "collections_created": collections_affected,
                "migration_timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self.logger.info("Chat collections migration completed successfully")

            return {
                "collections_affected": collections_affected,
                "records_processed": records_processed,
                "rollback_data": rollback_data,
            }

        except Exception as e:
            self.logger.error("Chat collections migration failed: %s", e, exc_info=True)
            raise Exception(f"Migration failed: {str(e)}")

    async def down(self) -> Dict[str, Any]:
        """Rollback the migration by dropping created collections."""
        collections_dropped = []

        try:
            self.logger.info("Starting chat collections migration rollback")

            # Drop chat system collections
            chat_collections = [
                "chat_sessions",
                "chat_messages",
                "token_usage",
                "message_votes",
            ]

            for collection_name in chat_collections:
                try:
                    await self.database.drop_collection(collection_name)
                    collections_dropped.append(collection_name)
                    self.logger.info("Dropped collection: %s", collection_name)
                except Exception as e:
                    self.logger.warning("Failed to drop collection %s: %s", collection_name, e)

            self.logger.info("Chat collections migration rollback completed")

            return {"collections_dropped": collections_dropped}

        except Exception as e:
            self.logger.error("Migration rollback failed: %s", e, exc_info=True)
            raise Exception(f"Rollback failed: {str(e)}")

    async def _create_chat_sessions_collection(self):
        """Create the chat_sessions collection with proper schema."""
        try:
            # Create collection
            sessions_collection = db_manager.get_collection("chat_sessions")

            # Create a sample document to establish schema (will be removed)
            sample_doc = {
                "_schema_version": "1.0.0",
                "id": str(uuid.uuid4()),
                "user_id": "sample_user",
                "session_type": "GENERAL",  # GENERAL, SQL, VECTOR
                "title": "Sample Chat Session",
                "message_count": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "last_message_at": None,
                "knowledge_base_ids": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "is_active": True,
            }

            await sessions_collection.insert_one(sample_doc)
            await sessions_collection.delete_one({"id": sample_doc["id"]})

            self.logger.info("Created chat_sessions collection")

        except Exception as e:
            self.logger.error("Failed to create chat_sessions collection: %s", e, exc_info=True)
            raise

    async def _create_chat_messages_collection(self):
        """Create the chat_messages collection."""
        try:
            messages_collection = db_manager.get_collection("chat_messages")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "id": str(uuid.uuid4()),
                "session_id": str(uuid.uuid4()),
                "user_id": "sample_user",
                "role": "user",  # user, assistant, system
                "content": "Sample message content",
                "status": "COMPLETED",  # PENDING, COMPLETED, FAILED
                "tool_invocations": [],
                "sql_queries": [],
                "token_usage": None,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            await messages_collection.insert_one(sample_doc)
            await messages_collection.delete_one({"id": sample_doc["id"]})

            self.logger.info("Created chat_messages collection")

        except Exception as e:
            self.logger.error("Failed to create chat_messages collection: %s", e, exc_info=True)
            raise

    async def _create_token_usage_collection(self):
        """Create the token_usage collection."""
        try:
            token_usage_collection = db_manager.get_collection("token_usage")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "id": str(uuid.uuid4()),
                "message_id": str(uuid.uuid4()),
                "session_id": str(uuid.uuid4()),
                "endpoint": "ollama",
                "total_tokens": 100,
                "prompt_tokens": 50,
                "completion_tokens": 50,
                "cost": 0.0,
                "model": "llama3.2:latest",
                "created_at": datetime.now(timezone.utc),
            }

            await token_usage_collection.insert_one(sample_doc)
            await token_usage_collection.delete_one({"id": sample_doc["id"]})

            self.logger.info("Created token_usage collection")

        except Exception as e:
            self.logger.error("Failed to create token_usage collection: %s", e, exc_info=True)
            raise

    async def _create_message_votes_collection(self):
        """Create the message_votes collection."""
        try:
            votes_collection = db_manager.get_collection("message_votes")

            # Create sample document
            sample_doc = {
                "_schema_version": "1.0.0",
                "id": str(uuid.uuid4()),
                "message_id": str(uuid.uuid4()),
                "user_id": "sample_user",
                "vote_type": "up",  # up, down
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            await votes_collection.insert_one(sample_doc)
            await votes_collection.delete_one({"id": sample_doc["id"]})

            self.logger.info("Created message_votes collection")

        except Exception as e:
            self.logger.error("Failed to create message_votes collection: %s", e, exc_info=True)
            raise

    async def _create_all_indexes(self):
        """Create all necessary indexes for chat collections."""
        try:
            self.logger.info("Creating indexes for chat collections")

            # Chat sessions collection indexes
            sessions_collection = db_manager.get_collection("chat_sessions")
            await sessions_collection.create_index("id", unique=True)
            await sessions_collection.create_index("user_id")
            await sessions_collection.create_index("session_type")
            await sessions_collection.create_index("is_active")
            await sessions_collection.create_index("created_at")
            await sessions_collection.create_index([("user_id", 1), ("is_active", 1)])
            await sessions_collection.create_index([("user_id", 1), ("created_at", -1)])
            await sessions_collection.create_index([("session_type", 1), ("is_active", 1)])

            # Chat messages collection indexes
            messages_collection = db_manager.get_collection("chat_messages")
            await messages_collection.create_index("id", unique=True)
            await messages_collection.create_index("session_id")
            await messages_collection.create_index("user_id")
            await messages_collection.create_index("role")
            await messages_collection.create_index("status")
            await messages_collection.create_index("created_at")
            await messages_collection.create_index([("session_id", 1), ("created_at", 1)])
            await messages_collection.create_index([("user_id", 1), ("created_at", -1)])
            await messages_collection.create_index([("session_id", 1), ("role", 1)])
            await messages_collection.create_index([("status", 1), ("created_at", -1)])

            # Token usage collection indexes
            token_usage_collection = db_manager.get_collection("token_usage")
            await token_usage_collection.create_index("id", unique=True)
            await token_usage_collection.create_index("message_id")
            await token_usage_collection.create_index("session_id")
            await token_usage_collection.create_index("model")
            await token_usage_collection.create_index("created_at")
            await token_usage_collection.create_index([("session_id", 1), ("created_at", -1)])
            await token_usage_collection.create_index([("model", 1), ("created_at", -1)])
            await token_usage_collection.create_index([("message_id", 1), ("session_id", 1)])

            # Message votes collection indexes
            votes_collection = db_manager.get_collection("message_votes")
            await votes_collection.create_index("id", unique=True)
            await votes_collection.create_index("message_id")
            await votes_collection.create_index("user_id")
            await votes_collection.create_index("vote_type")
            await votes_collection.create_index("created_at")
            # Unique constraint: one vote per user per message
            await votes_collection.create_index([("message_id", 1), ("user_id", 1)], unique=True)
            await votes_collection.create_index([("message_id", 1), ("vote_type", 1)])
            await votes_collection.create_index([("user_id", 1), ("created_at", -1)])

            self.logger.info("All chat collection indexes created successfully")

        except Exception as e:
            self.logger.error("Failed to create chat collection indexes: %s", e, exc_info=True)
            raise
