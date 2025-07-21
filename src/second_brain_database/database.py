"""Database module for Second Brain Database API."""
import asyncio

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

class DatabaseManager:
    """MongoDB database manager using Motor (async MongoDB driver)"""

    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.database = None
        self._connection_retries = 3

    async def connect(self):
        """Connect to MongoDB with retry logic"""
        for attempt in range(self._connection_retries):
            try:
                # Build connection string
                if settings.MONGODB_USERNAME and settings.MONGODB_PASSWORD:
                    password = settings.MONGODB_PASSWORD.get_secret_value() if hasattr(settings.MONGODB_PASSWORD, "get_secret_value") else settings.MONGODB_PASSWORD
                    connection_string = (
                        f"mongodb://{settings.MONGODB_USERNAME}:"
                        f"{password}@"
                        f"{settings.MONGODB_URL.replace('mongodb://', '')}"
                    )
                else:
                    connection_string = settings.MONGODB_URL

                # Create client
                self.client = AsyncIOMotorClient(
                    connection_string,
                    serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT,
                    connectTimeoutMS=settings.MONGODB_CONNECTION_TIMEOUT,
                    maxPoolSize=50,
                    minPoolSize=5
                )

                # Get database
                self.database = self.client[settings.MONGODB_DATABASE]

                # Test connection
                await self.client.admin.command('ping')
                logger.info("Successfully connected to MongoDB database: %s",
                           settings.MONGODB_DATABASE)
                return

            except (ServerSelectionTimeoutError, ConnectionFailure) as e:
                logger.warning("Failed to connect to MongoDB (attempt %d/%d): %s",
                             attempt + 1, self._connection_retries, e)
                if attempt == self._connection_retries - 1:
                    logger.error("All connection attempts failed")
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except (ConnectionError, TimeoutError) as e:
                logger.error("Connection error connecting to MongoDB: %s", e)
                raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def health_check(self) -> bool:
        """Check database connection health"""
        try:
            if self.client is None:
                return False

            # Ping the database
            await self.client.admin.command('ping')
            return True

        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            logger.error("Database health check failed: %s", e)
            return False
        except (ConnectionError, TimeoutError) as e:
            logger.error("Connection error during health check: %s", e)
            return False

    def get_collection(self, collection_name: str):
        """Get a collection from the database"""
        if self.database is None:
            raise RuntimeError("Database not connected")
        return self.database[collection_name]

    async def create_indexes(self):
        """Create database indexes for better performance"""
        try:
            users_collection = self.get_collection("users")

            # Get existing indexes
            existing_indexes = await users_collection.list_indexes().to_list(length=None)
            existing_index_names = [idx['name'] for idx in existing_indexes]

            # Handle username index
            if "username_1" in existing_index_names:
                # Check if it's already sparse
                username_idx = next((idx for idx in existing_indexes if idx['name'] == 'username_1'), None)
                if username_idx and not username_idx.get('sparse', False):
                    await users_collection.drop_index("username_1")
                    await users_collection.create_index("username", unique=True, sparse=True)
            else:
                await users_collection.create_index("username", unique=True, sparse=True)

            # Handle email index
            if "email_1" in existing_index_names:
                # Check if it's already sparse
                email_idx = next((idx for idx in existing_indexes if idx['name'] == 'email_1'), None)
                if email_idx and not email_idx.get('sparse', False):
                    try:
                        await users_collection.drop_index("email_1")
                        await users_collection.create_index("email", unique=True, sparse=True)
                    except Exception as e:
                        logger.warning("Could not recreate email index as sparse: %s", e)
            else:
                try:
                    await users_collection.create_index("email", unique=True, sparse=True)
                except Exception as e:
                    logger.warning("Could not create email index: %s", e)

            # Create index on failed_login_attempts for account lockout queries
            await users_collection.create_index("failed_login_attempts")

            # Add index for reset_blocklist and reset_whitelist (for abuse/abuse detection)
            await users_collection.create_index("reset_blocklist")
            await users_collection.create_index("reset_whitelist")

            # Add TTL index for password_reset_token_expiry (auto-remove expired tokens)
            await users_collection.create_index(
                "password_reset_token_expiry",
                expireAfterSeconds=0
            )

            # Permanent tokens collection indexes
            permanent_tokens_collection = self.get_collection("permanent_tokens")

            # Create unique index on token_hash for fast lookups
            await permanent_tokens_collection.create_index("token_hash", unique=True)

            # Create compound index for user queries (user_id + is_revoked)
            await permanent_tokens_collection.create_index([
                ("user_id", 1),
                ("is_revoked", 1)
            ])

            # Create index on created_at for analytics and cleanup
            await permanent_tokens_collection.create_index("created_at")

            # Create index on last_used_at for usage tracking
            await permanent_tokens_collection.create_index("last_used_at")

            logger.info("Database indexes created successfully")

        except (ConnectionError, TimeoutError) as e:
            logger.error("Failed to create database indexes: %s", e)

# Global database manager instance
db_manager = DatabaseManager()
