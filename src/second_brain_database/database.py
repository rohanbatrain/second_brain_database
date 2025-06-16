from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError, ConnectionFailure
import logging
from second_brain_database.config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """MongoDB database manager using Motor (async MongoDB driver)"""

    def __init__(self):
        self.client: AsyncIOMotorClient = None
        self.database = None

    async def connect(self):
        """Connect to MongoDB"""
        try:
            # Build connection string
            if settings.MONGODB_USERNAME and settings.MONGODB_PASSWORD:
                connection_string = (
                    f"mongodb://{settings.MONGODB_USERNAME}:{settings.MONGODB_PASSWORD}@"
                    f"{settings.MONGODB_URL.replace('mongodb://', '')}"
                )
            else:
                connection_string = settings.MONGODB_URL

            # Create client
            self.client = AsyncIOMotorClient(
                connection_string,
                serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT,
                connectTimeoutMS=settings.MONGODB_CONNECTION_TIMEOUT
            )

            # Get database
            self.database = self.client[settings.MONGODB_DATABASE]

            # Test connection
            await self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB database: %s", settings.MONGODB_DATABASE)

        except (ServerSelectionTimeoutError, ConnectionFailure) as e:
            logger.error("Failed to connect to MongoDB: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error connecting to MongoDB: %s", e)
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
        except Exception as e:
            logger.error("Unexpected error during health check: %s", e)
            return False

    def get_collection(self, collection_name: str):
        """Get a collection from the database"""
        if self.database is None:
            raise RuntimeError("Database not connected")
        return self.database[collection_name]

# Global database manager instance
db_manager = DatabaseManager()
