"""Database module for Second Brain Database API."""
import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure

from second_brain_database.config import settings

logger = logging.getLogger(__name__)

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
                    connection_string = (
                        f"mongodb://{settings.MONGODB_USERNAME}:"
                        f"{settings.MONGODB_PASSWORD}@"
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

            # Create unique index on username
            await users_collection.create_index("username", unique=True)

            # Create unique index on email
            await users_collection.create_index("email", unique=True)

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

            logger.info("Database indexes created successfully")

        except (ConnectionError, TimeoutError) as e:
            logger.error("Failed to create database indexes: %s", e)

# Global database manager instance
db_manager = DatabaseManager()
