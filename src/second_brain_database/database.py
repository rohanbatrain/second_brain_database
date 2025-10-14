"""Database module for Second Brain Database API."""

import asyncio
import time
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()
db_logger = get_logger(prefix="[DATABASE]")
perf_logger = get_logger(prefix="[DB_PERFORMANCE]")
health_logger = get_logger(prefix="[DB_HEALTH]")


class DatabaseManager:
    """MongoDB database manager using Motor (async MongoDB driver)"""

    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
        self._connection_retries = 3
        # Will be set after connect(); True when connected to a replica-set or mongos that supports transactions
        self.transactions_supported: Optional[bool] = None

    async def connect(self):
        """Connect to MongoDB with retry logic"""
        start_time = time.time()
        db_logger.info("Starting MongoDB connection process")

        for attempt in range(self._connection_retries):
            attempt_start = time.time()
            try:
                db_logger.info("Connection attempt %d/%d to MongoDB", attempt + 1, self._connection_retries)

                # Build connection string
                if settings.MONGODB_USERNAME and settings.MONGODB_PASSWORD:
                    password = (
                        settings.MONGODB_PASSWORD.get_secret_value()
                        if hasattr(settings.MONGODB_PASSWORD, "get_secret_value")
                        else settings.MONGODB_PASSWORD
                    )
                    connection_string = (
                        f"mongodb://{settings.MONGODB_USERNAME}:"
                        f"{password}@"
                        f"{settings.MONGODB_URL.replace('mongodb://', '')}"
                    )
                    db_logger.debug("Using authenticated connection to MongoDB")
                else:
                    connection_string = settings.MONGODB_URL
                    db_logger.debug("Using unauthenticated connection to MongoDB")

                # Log connection parameters (without sensitive data)
                db_logger.info(
                    "MongoDB connection config - URL: %s, Database: %s, MaxPool: %d, MinPool: %d, ServerTimeout: %dms, ConnTimeout: %dms",
                    settings.MONGODB_URL,
                    settings.MONGODB_DATABASE,
                    50,
                    5,
                    settings.MONGODB_SERVER_SELECTION_TIMEOUT,
                    settings.MONGODB_CONNECTION_TIMEOUT,
                )

                # Create client
                self.client = AsyncIOMotorClient(
                    connection_string,
                    serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT,
                    connectTimeoutMS=settings.MONGODB_CONNECTION_TIMEOUT,
                    maxPoolSize=50,
                    minPoolSize=5,
                )

                # Get database
                self.database = self.client[settings.MONGODB_DATABASE]
                db_logger.debug("Database instance created for: %s", settings.MONGODB_DATABASE)

                # Test connection with timing
                ping_start = time.time()
                await self.client.admin.command("ping")
                ping_duration = time.time() - ping_start
                # Detect whether the server supports transactions (i.e., is part of a replica set or a mongos)
                try:
                    # 'hello' is preferred; fallback to isMaster for older servers
                    try:
                        hello = await self.client.admin.command({"hello": 1})
                    except Exception:
                        hello = await self.client.admin.command({"isMaster": 1})

                    # Replica set: presence of setName -> transactions supported
                    # Mongos: msg == 'isdbgrid' indicates mongos (which supports transactions)
                    self.transactions_supported = bool(
                        hello.get("setName") or hello.get("msg") == "isdbgrid"
                    )
                except Exception:
                    # If detection fails, be conservative and assume transactions are not supported
                    self.transactions_supported = False

                total_duration = time.time() - start_time
                perf_logger.info(
                    "MongoDB connection established successfully in %.3fs (ping: %.3fs)", total_duration, ping_duration
                )
                db_logger.info("Successfully connected to MongoDB database: %s", settings.MONGODB_DATABASE)

                # Log connection pool status
                await self._log_connection_pool_status()
                return

            except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                attempt_duration = time.time() - attempt_start
                perf_logger.warning("Connection attempt %d failed after %.3fs", attempt + 1, attempt_duration)
                db_logger.warning(
                    "Failed to connect to MongoDB (attempt %d/%d): %s", attempt + 1, self._connection_retries, e
                )
                if attempt == self._connection_retries - 1:
                    total_duration = time.time() - start_time
                    db_logger.error("All connection attempts failed after %.3fs", total_duration)
                    raise

                backoff_time = 2**attempt
                db_logger.info("Waiting %.1fs before retry (exponential backoff)", backoff_time)
                await asyncio.sleep(backoff_time)

            except (ConnectionError, TimeoutError) as e:
                attempt_duration = time.time() - attempt_start
                perf_logger.error("Connection error after %.3fs", attempt_duration)
                db_logger.error("Connection error connecting to MongoDB: %s", e)
                raise

    async def _log_connection_pool_status(self):
        """Log current connection pool status for monitoring"""
        try:
            if self.client:
                # Get server info for connection pool monitoring
                server_info = await self.client.server_info()
                health_logger.info(
                    "MongoDB server info - Version: %s, MaxBsonSize: %d",
                    server_info.get("version", "unknown"),
                    server_info.get("maxBsonObjectSize", 0),
                )

                # Log connection pool configuration
                health_logger.info(
                    "Connection pool config - MaxPoolSize: %d, MinPoolSize: %d",
                    50,  # maxPoolSize from client creation
                    5,   # minPoolSize from client creation
                )
        except Exception as e:
            health_logger.warning("Failed to log connection pool status: %s", e)

    async def disconnect(self):
        """Disconnect from MongoDB"""
        start_time = time.time()
        db_logger.info("Starting MongoDB disconnection process")

        if self.client:
            try:
                # Log final connection pool status before disconnect
                await self._log_connection_pool_status()

                self.client.close()
                duration = time.time() - start_time
                perf_logger.info("MongoDB disconnection completed in %.3fs", duration)
                db_logger.info("Successfully disconnected from MongoDB")
            except Exception as e:
                duration = time.time() - start_time
                perf_logger.error("MongoDB disconnection failed after %.3fs", duration)
                db_logger.error("Error during MongoDB disconnection: %s", e)
                raise
        else:
            db_logger.warning("Disconnect called but no active MongoDB connection found")

    async def health_check(self) -> bool:
        """Check database connection health"""
        start_time = time.time()
        health_logger.debug("Starting database health check")

        try:
            if self.client is None:
                health_logger.warning("Health check failed: No database client available")
                return False

            # Ping the database with timing
            ping_start = time.time()
            await self.client.admin.command("ping")
            ping_duration = time.time() - ping_start

            total_duration = time.time() - start_time
            perf_logger.debug(
                "Database health check completed successfully in %.3fs (ping: %.3fs)", total_duration, ping_duration
            )
            health_logger.debug("Database health check passed")
            return True

        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            duration = time.time() - start_time
            perf_logger.warning("Database health check failed after %.3fs", duration)
            health_logger.error("Database health check failed: %s", e)
            return False
        except (ConnectionError, TimeoutError) as e:
            duration = time.time() - start_time
            perf_logger.warning("Database health check connection error after %.3fs", duration)
            health_logger.error("Connection error during health check: %s", e)
            return False
        except Exception as e:
            duration = time.time() - start_time
            perf_logger.error("Unexpected error during health check after %.3fs", duration)
            health_logger.error("Unexpected error during health check: %s", e)
            return False

    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """Get a collection from the database"""
        db_logger.debug("Requesting collection: %s", collection_name)

        if self.database is None:
            db_logger.error("Cannot get collection '%s': Database not connected", collection_name)
            raise RuntimeError("Database not connected")

        try:
            collection = self.database[collection_name]
            db_logger.debug("Successfully retrieved collection: %s", collection_name)
            return collection
        except Exception as e:
            db_logger.error("Failed to get collection '%s': %s", collection_name, e)
            raise

    async def create_indexes(self):
        """Create database indexes for better performance"""
        start_time = time.time()
        db_logger.info("Starting database index creation process")

        try:
            # Users collection indexes
            db_logger.info("Creating indexes for 'users' collection")
            users_collection = self.get_collection("users")

            # Get existing indexes with timing
            index_list_start = time.time()
            existing_indexes = await users_collection.list_indexes().to_list(length=None)
            index_list_duration = time.time() - index_list_start
            existing_index_names = [idx["name"] for idx in existing_indexes]

            perf_logger.debug("Listed existing indexes for 'users' collection in %.3fs", index_list_duration)
            db_logger.debug(
                "Found %d existing indexes in 'users' collection: %s", len(existing_index_names), existing_index_names
            )

            # Handle username index
            await self._create_or_update_index(
                users_collection, "username_1", "username", {"unique": True, "sparse": True}, existing_indexes
            )

            # Handle email index
            await self._create_or_update_index(
                users_collection, "email_1", "email", {"unique": True, "sparse": True}, existing_indexes
            )

            # Create additional user indexes
            await self._create_index_if_not_exists(users_collection, "failed_login_attempts", {})
            await self._create_index_if_not_exists(users_collection, "reset_blocklist", {})
            await self._create_index_if_not_exists(users_collection, "reset_whitelist", {})
            await self._create_index_if_not_exists(
                users_collection, "password_reset_token_expiry", {"expireAfterSeconds": 0}
            )
            
            # User Agent lockdown indexes for efficient access
            await self._create_index_if_not_exists(users_collection, "trusted_user_agent_lockdown", {})
            await self._create_index_if_not_exists(users_collection, "trusted_user_agents", {})
            await self._create_index_if_not_exists(users_collection, "trusted_user_agent_lockdown_codes", {})
            
            # Temporary access token indexes for "allow once" functionality
            await self._create_index_if_not_exists(users_collection, "temporary_ip_access_tokens", {})
            await self._create_index_if_not_exists(users_collection, "temporary_user_agent_access_tokens", {})
            await self._create_index_if_not_exists(users_collection, "temporary_ip_bypasses", {})
            
            # Family management indexes
            await self._create_index_if_not_exists(users_collection, "family_limits.max_families_allowed", {})
            await self._create_index_if_not_exists(users_collection, "family_memberships.family_id", {})
            await self._create_index_if_not_exists(users_collection, "family_memberships.role", {})
            await self._create_index_if_not_exists(users_collection, "family_notifications.unread_count", {})

            # Permanent tokens collection indexes
            db_logger.info("Creating indexes for 'permanent_tokens' collection")
            permanent_tokens_collection = self.get_collection("permanent_tokens")

            await self._create_index_if_not_exists(permanent_tokens_collection, "token_hash", {"unique": True})
            await self._create_index_if_not_exists(permanent_tokens_collection, [("user_id", 1), ("is_revoked", 1)], {})
            await self._create_index_if_not_exists(permanent_tokens_collection, "created_at", {})
            await self._create_index_if_not_exists(permanent_tokens_collection, "last_used_at", {})

            # WebAuthn credentials collection indexes
            db_logger.info("Creating indexes for 'webauthn_credentials' collection")
            webauthn_credentials_collection = self.get_collection("webauthn_credentials")

            await self._create_index_if_not_exists(webauthn_credentials_collection, "credential_id", {"unique": True})
            await self._create_index_if_not_exists(
                webauthn_credentials_collection, [("user_id", 1), ("is_active", 1)], {}
            )
            await self._create_index_if_not_exists(webauthn_credentials_collection, "created_at", {})
            await self._create_index_if_not_exists(webauthn_credentials_collection, "last_used_at", {})

            # WebAuthn challenges collection indexes
            db_logger.info("Creating indexes for 'webauthn_challenges' collection")
            webauthn_challenges_collection = self.get_collection("webauthn_challenges")

            await self._create_index_if_not_exists(webauthn_challenges_collection, "challenge", {"unique": True})
            await self._create_index_if_not_exists(
                webauthn_challenges_collection, "expires_at", {"expireAfterSeconds": 0}
            )
            await self._create_index_if_not_exists(webauthn_challenges_collection, "user_id", {})
            await self._create_index_if_not_exists(webauthn_challenges_collection, [("type", 1), ("created_at", 1)], {})

            # Family management collections indexes
            await self._create_family_management_indexes()

            total_duration = time.time() - start_time
            perf_logger.info("Database index creation completed successfully in %.3fs", total_duration)
            db_logger.info("Database indexes created successfully")

        except (ConnectionError, TimeoutError) as e:
            duration = time.time() - start_time
            perf_logger.error("Database index creation failed after %.3fs", duration)
            db_logger.error("Failed to create database indexes: %s", e)
            raise
        except Exception as e:
            duration = time.time() - start_time
            perf_logger.error("Unexpected error during index creation after %.3fs", duration)
            db_logger.error("Unexpected error creating database indexes: %s", e)
            raise

    async def _create_or_update_index(
        self,
        collection: AsyncIOMotorCollection,
        existing_name: str,
        field_name: str,
        options: Dict[str, Any],
        existing_indexes: List[Dict],
    ):
        """Create or update an index if it doesn't meet requirements"""
        start_time = time.time()

        if existing_name in [idx["name"] for idx in existing_indexes]:
            # Check if it meets requirements
            existing_idx = next((idx for idx in existing_indexes if idx["name"] == existing_name), None)
            if existing_idx and not existing_idx.get("sparse", False) and options.get("sparse"):
                db_logger.info("Dropping and recreating index '%s' to make it sparse", existing_name)
                try:
                    await collection.drop_index(existing_name)
                    await collection.create_index(field_name, **options)
                    duration = time.time() - start_time
                    perf_logger.debug("Recreated index '%s' in %.3fs", existing_name, duration)
                    db_logger.debug("Successfully recreated index: %s", existing_name)
                except Exception as e:
                    duration = time.time() - start_time
                    perf_logger.warning("Failed to recreate index '%s' after %.3fs", existing_name, duration)
                    db_logger.warning("Could not recreate index '%s': %s", existing_name, e)
            else:
                db_logger.debug("Index '%s' already exists with correct configuration", existing_name)
        else:
            try:
                await collection.create_index(field_name, **options)
                duration = time.time() - start_time
                perf_logger.debug("Created new index '%s' in %.3fs", field_name, duration)
                db_logger.debug("Successfully created index: %s", field_name)
            except Exception as e:
                duration = time.time() - start_time
                perf_logger.warning("Failed to create index '%s' after %.3fs", field_name, duration)
                db_logger.warning("Could not create index '%s': %s", field_name, e)

    async def _create_index_if_not_exists(
        self, collection: AsyncIOMotorCollection, field_spec: Any, options: Dict[str, Any]
    ):
        """Create an index if it doesn't already exist"""
        start_time = time.time()

        try:
            await collection.create_index(field_spec, **options)
            duration = time.time() - start_time
            perf_logger.debug("Created/ensured index '%s' in %.3fs", field_spec, duration)
            db_logger.debug("Successfully created/ensured index: %s", field_spec)
        except Exception as e:
            duration = time.time() - start_time
            perf_logger.warning("Failed to create/ensure index '%s' after %.3fs", field_spec, duration)
            db_logger.warning("Could not create/ensure index '%s': %s", field_spec, e)

    # Database operation logging utilities
    def log_query_start(
        self, collection_name: str, operation: str, query: Optional[Dict] = None, options: Optional[Dict] = None
    ) -> float:
        """Log the start of a database query and return start time for performance tracking"""
        start_time = time.time()

        # Sanitize query for logging (remove sensitive data)
        safe_query = self._sanitize_query_for_logging(query) if query else {}
        safe_options = self._sanitize_query_for_logging(options) if options else {}

        db_logger.debug(
            "Starting %s operation on collection '%s' - Query: %s, Options: %s",
            operation,
            collection_name,
            safe_query,
            safe_options,
        )
        return start_time

    def log_query_success(
        self,
        collection_name: str,
        operation: str,
        start_time: float,
        result_count: Optional[int] = None,
        result_info: Optional[str] = None,
    ):
        """Log successful completion of a database query with performance metrics"""
        duration = time.time() - start_time

        if result_count is not None:
            perf_logger.info(
                "%s on '%s' completed successfully in %.3fs - %d records",
                operation,
                collection_name,
                duration,
                result_count,
            )
            db_logger.debug(
                "%s operation on '%s' successful - Duration: %.3fs, Records: %d",
                operation,
                collection_name,
                duration,
                result_count,
            )
        else:
            perf_logger.info("%s on '%s' completed successfully in %.3fs", operation, collection_name, duration)
            db_logger.debug("%s operation on '%s' successful - Duration: %.3fs", operation, collection_name, duration)

        if result_info:
            db_logger.debug("Additional result info for %s on '%s': %s", operation, collection_name, result_info)

    def log_query_error(
        self, collection_name: str, operation: str, start_time: float, error: Exception, query: Optional[Dict] = None
    ):
        """Log database query errors with context and performance metrics"""
        duration = time.time() - start_time

        # Sanitize query for error logging
        safe_query = self._sanitize_query_for_logging(query) if query else {}

        perf_logger.error("%s on '%s' failed after %.3fs", operation, collection_name, duration)
        db_logger.error(
            "%s operation failed on collection '%s' after %.3fs - Error: %s, Query: %s",
            operation,
            collection_name,
            duration,
            error,
            safe_query,
        )

    def _sanitize_query_for_logging(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize database queries for safe logging by removing sensitive data"""
        if not isinstance(query, dict):
            return {}

        sensitive_fields = {
            "password",
            "password_hash",
            "token",
            "secret",
            "key",
            "credential",
            "private_key",
            "public_key",
            "auth_token",
            "access_token",
            "refresh_token",
            "api_key",
            "session_token",
            "reset_token",
            "verification_token",
        }

        sanitized: Dict[str, Any] = {}
        for key, value in query.items():
            if any(sensitive_field in key.lower() for sensitive_field in sensitive_fields):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_query_for_logging(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_query_for_logging(item) if isinstance(item, dict) else item for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized

    async def log_collection_stats(self, collection_name: str):
        """Log collection statistics for monitoring and debugging"""
        try:
            start_time = time.time()
            collection = self.get_collection(collection_name)

            # Get collection stats
            if self.database is None:
                raise RuntimeError("Database not connected")
            stats = await self.database.command("collStats", collection_name)
            duration = time.time() - start_time

            health_logger.info(
                "Collection '%s' stats - Documents: %d, Size: %d bytes, Indexes: %d (retrieved in %.3fs)",
                collection_name,
                stats.get("count", 0),
                stats.get("size", 0),
                stats.get("nindexes", 0),
                duration,
            )

        except Exception as e:
            duration = time.time() - start_time if "start_time" in locals() else 0
            health_logger.warning(
                "Failed to retrieve stats for collection '%s' after %.3fs: %s", collection_name, duration, e
            )

    async def log_database_stats(self):
        """Log overall database statistics for monitoring"""
        try:
            start_time = time.time()

            # Get database stats
            if self.database is None:
                raise RuntimeError("Database not connected")
            db_stats = await self.database.command("dbStats")
            duration = time.time() - start_time

            health_logger.info(
                "Database '%s' stats - Collections: %d, Objects: %d, DataSize: %d bytes, IndexSize: %d bytes (retrieved in %.3fs)",
                settings.MONGODB_DATABASE,
                db_stats.get("collections", 0),
                db_stats.get("objects", 0),
                db_stats.get("dataSize", 0),
                db_stats.get("indexSize", 0),
                duration,
            )

        except Exception as e:
            duration = time.time() - start_time if "start_time" in locals() else 0
            health_logger.warning("Failed to retrieve database stats after %.3fs: %s", duration, e)

    async def _create_family_management_indexes(self):
        """Create comprehensive indexes for family management collections with performance optimization"""
        try:
            db_logger.info("Creating indexes for family management collections")
            
            # Families collection indexes - Core family management
            families_collection = self.get_collection("families")
            await self._create_index_if_not_exists(families_collection, "family_id", {"unique": True})
            await self._create_index_if_not_exists(families_collection, "admin_user_ids", {})
            await self._create_index_if_not_exists(families_collection, "is_active", {})
            await self._create_index_if_not_exists(families_collection, "created_at", {})
            await self._create_index_if_not_exists(families_collection, "updated_at", {})
            await self._create_index_if_not_exists(families_collection, "member_count", {})
            await self._create_index_if_not_exists(families_collection, "sbd_account.account_username", {"unique": True, "sparse": True})
            await self._create_index_if_not_exists(families_collection, "sbd_account.is_frozen", {})
            # Compound indexes for efficient queries
            await self._create_index_if_not_exists(families_collection, [("admin_user_ids", 1), ("is_active", 1)], {})
            await self._create_index_if_not_exists(families_collection, [("is_active", 1), ("created_at", -1)], {})
            
            # Family relationships collection indexes - Bidirectional relationship management
            relationships_collection = self.get_collection("family_relationships")
            await self._create_index_if_not_exists(relationships_collection, "relationship_id", {"unique": True})
            await self._create_index_if_not_exists(relationships_collection, "family_id", {})
            await self._create_index_if_not_exists(relationships_collection, "user_a_id", {})
            await self._create_index_if_not_exists(relationships_collection, "user_b_id", {})
            await self._create_index_if_not_exists(relationships_collection, "status", {})
            await self._create_index_if_not_exists(relationships_collection, "created_by", {})
            await self._create_index_if_not_exists(relationships_collection, "created_at", {})
            await self._create_index_if_not_exists(relationships_collection, "activated_at", {})
            # Compound indexes for relationship queries
            await self._create_index_if_not_exists(relationships_collection, [("user_a_id", 1), ("user_b_id", 1), ("family_id", 1)], {"unique": True})
            await self._create_index_if_not_exists(relationships_collection, [("family_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(relationships_collection, [("user_a_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(relationships_collection, [("user_b_id", 1), ("status", 1)], {})
            
            # Family invitations collection indexes - Email invitation system
            invitations_collection = self.get_collection("family_invitations")
            await self._create_index_if_not_exists(invitations_collection, "invitation_id", {"unique": True})
            await self._create_index_if_not_exists(invitations_collection, "invitation_token", {"unique": True})
            await self._create_index_if_not_exists(invitations_collection, "family_id", {})
            await self._create_index_if_not_exists(invitations_collection, "inviter_user_id", {})
            await self._create_index_if_not_exists(invitations_collection, "invitee_email", {})
            await self._create_index_if_not_exists(invitations_collection, "invitee_user_id", {})
            await self._create_index_if_not_exists(invitations_collection, "status", {})
            await self._create_index_if_not_exists(invitations_collection, "created_at", {})
            await self._create_index_if_not_exists(invitations_collection, "expires_at", {"expireAfterSeconds": 0})
            # Compound indexes for invitation queries
            await self._create_index_if_not_exists(invitations_collection, [("family_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(invitations_collection, [("invitee_user_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(invitations_collection, [("invitee_email", 1), ("status", 1)], {})
            
            # Family notifications collection indexes - Notification system
            notifications_collection = self.get_collection("family_notifications")
            await self._create_index_if_not_exists(notifications_collection, "notification_id", {"unique": True})
            await self._create_index_if_not_exists(notifications_collection, "family_id", {})
            await self._create_index_if_not_exists(notifications_collection, "recipient_user_ids", {})
            await self._create_index_if_not_exists(notifications_collection, "type", {})
            await self._create_index_if_not_exists(notifications_collection, "status", {})
            await self._create_index_if_not_exists(notifications_collection, "created_at", {})
            await self._create_index_if_not_exists(notifications_collection, "sent_at", {})
            # Compound indexes for notification queries
            await self._create_index_if_not_exists(notifications_collection, [("family_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(notifications_collection, [("recipient_user_ids", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(notifications_collection, [("family_id", 1), ("created_at", -1)], {})
            
            # Family token requests collection indexes - Token request system
            token_requests_collection = self.get_collection("family_token_requests")
            await self._create_index_if_not_exists(token_requests_collection, "request_id", {"unique": True})
            await self._create_index_if_not_exists(token_requests_collection, "family_id", {})
            await self._create_index_if_not_exists(token_requests_collection, "requester_user_id", {})
            await self._create_index_if_not_exists(token_requests_collection, "status", {})
            await self._create_index_if_not_exists(token_requests_collection, "reviewed_by", {})
            await self._create_index_if_not_exists(token_requests_collection, "created_at", {})
            await self._create_index_if_not_exists(token_requests_collection, "expires_at", {"expireAfterSeconds": 0})
            await self._create_index_if_not_exists(token_requests_collection, "reviewed_at", {})
            # Compound indexes for token request queries
            await self._create_index_if_not_exists(token_requests_collection, [("family_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(token_requests_collection, [("requester_user_id", 1), ("status", 1)], {})
            await self._create_index_if_not_exists(token_requests_collection, [("family_id", 1), ("created_at", -1)], {})
            
            # Family admin actions collection indexes - Admin action audit trail
            admin_actions_collection = self.get_collection("family_admin_actions")
            await self._create_index_if_not_exists(admin_actions_collection, "action_id", {"unique": True})
            await self._create_index_if_not_exists(admin_actions_collection, "family_id", {})
            await self._create_index_if_not_exists(admin_actions_collection, "admin_user_id", {})
            await self._create_index_if_not_exists(admin_actions_collection, "target_user_id", {})
            await self._create_index_if_not_exists(admin_actions_collection, "action_type", {})
            await self._create_index_if_not_exists(admin_actions_collection, "created_at", {})
            # Compound indexes for admin action queries
            await self._create_index_if_not_exists(admin_actions_collection, [("family_id", 1), ("created_at", -1)], {})
            await self._create_index_if_not_exists(admin_actions_collection, [("admin_user_id", 1), ("created_at", -1)], {})
            await self._create_index_if_not_exists(admin_actions_collection, [("target_user_id", 1), ("created_at", -1)], {})
            await self._create_index_if_not_exists(admin_actions_collection, [("family_id", 1), ("action_type", 1)], {})
            
            db_logger.info("Family management collection indexes created successfully")
            
        except Exception as e:
            db_logger.error("Failed to create family management indexes: %s", e)
            raise

    async def monitor_connection_pool(self):
        """Monitor and log connection pool metrics"""
        try:
            if not self.client:
                health_logger.warning("Cannot monitor connection pool: No client available")
                return

            # Log current connection pool status
            health_logger.info(
                "Connection pool monitoring - MaxPoolSize: %d, MinPoolSize: %d",
                self.client.max_pool_size,
                self.client.min_pool_size,
            )

            # Test connection responsiveness
            start_time = time.time()
            await self.client.admin.command("ping")
            ping_duration = time.time() - start_time

            if ping_duration > 1.0:  # Slow response threshold
                health_logger.warning("Slow database response detected: %.3fs", ping_duration)
            else:
                health_logger.debug("Database ping response time: %.3fs", ping_duration)

        except Exception as e:
            health_logger.error("Connection pool monitoring failed: %s", e)

    async def initialize(self):
        """Initialize database connection (alias for connect)"""
        await self.connect()
        
    async def close(self):
        """Close database connection (alias for disconnect)"""
        await self.disconnect()


# Global database manager instance
db_manager = DatabaseManager()
