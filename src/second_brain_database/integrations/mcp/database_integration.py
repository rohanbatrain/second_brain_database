"""
MCP Database Integration

This module provides database connectivity and management for MCP tools,
integrating with the existing Second Brain Database infrastructure.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ...config import settings
from ...database import db_manager
from ...managers.logging_manager import get_logger
from .exceptions import MCPValidationError

logger = get_logger(prefix="[MCP_Database]")


class MCPDatabaseManager:
    """
    Database manager for MCP operations.

    This class provides a centralized interface for MCP tools to interact
    with the database, ensuring proper connection management and error handling.
    """

    def __init__(self):
        self.logger = logger
        self._connection_verified = False
        self._last_health_check = None
        self._health_check_interval = 30  # seconds

    async def ensure_connection(self) -> bool:
        """
        Ensure database connection is established and healthy.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            # Check if we need to verify connection
            now = datetime.now(timezone.utc)
            if (
                self._connection_verified
                and self._last_health_check
                and (now - self._last_health_check).total_seconds() < self._health_check_interval
            ):
                return True

            # Perform health check
            is_healthy = await db_manager.health_check()

            if is_healthy:
                self._connection_verified = True
                self._last_health_check = now
                self.logger.debug("Database connection verified")
                return True
            else:
                self._connection_verified = False
                self.logger.error("Database health check failed")
                return False

        except Exception as e:
            self.logger.error("Database connection check failed: %s", e)
            self._connection_verified = False
            return False

    async def get_collection(self, collection_name: str):
        """
        Get a database collection with connection verification.

        Args:
            collection_name: Name of the collection

        Returns:
            MongoDB collection object

        Raises:
            MCPValidationError: If database is not connected
        """
        if not await self.ensure_connection():
            raise MCPValidationError("Database not connected")

        try:
            return db_manager.get_collection(collection_name)
        except Exception as e:
            self.logger.error("Failed to get collection %s: %s", collection_name, e)
            raise MCPValidationError(f"Failed to access collection {collection_name}: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive database health check.

        Returns:
            Dictionary with health check results
        """
        health_data = {"healthy": False, "timestamp": datetime.now(timezone.utc).isoformat(), "details": {}}

        try:
            # Basic connection check
            is_connected = await db_manager.health_check()
            health_data["details"]["connection"] = {
                "status": "healthy" if is_connected else "unhealthy",
                "connected": is_connected,
            }

            if is_connected:
                # Check critical collections
                collections_to_check = ["users", "families", "family_relationships"]
                collection_health = {}

                for collection_name in collections_to_check:
                    try:
                        collection = db_manager.get_collection(collection_name)
                        # Try to perform a simple query
                        await collection.find_one({}, {"_id": 1})
                        collection_health[collection_name] = "healthy"
                    except Exception as e:
                        collection_health[collection_name] = f"error: {str(e)}"
                        self.logger.warning("Collection %s health check failed: %s", collection_name, e)

                health_data["details"]["collections"] = collection_health

                # Check replica set status
                try:
                    ismaster = await db_manager.client.admin.command("ismaster")
                    health_data["details"]["replica_set"] = {
                        "enabled": bool(ismaster.get("setName")),
                        "set_name": ismaster.get("setName"),
                        "is_master": ismaster.get("ismaster", False),
                    }
                except Exception as e:
                    health_data["details"]["replica_set"] = {"error": str(e)}

                # Overall health
                all_collections_healthy = all(status == "healthy" for status in collection_health.values())
                health_data["healthy"] = is_connected and all_collections_healthy

        except Exception as e:
            self.logger.error("Database health check failed: %s", e)
            health_data["details"]["error"] = str(e)

        return health_data

    async def is_replica_set(self) -> bool:
        """
        Check if MongoDB is running as a replica set.

        Returns:
            True if replica set is enabled, False otherwise
        """
        try:
            if not await self.ensure_connection():
                return False

            ismaster = await db_manager.client.admin.command("ismaster")
            return bool(ismaster.get("setName"))
        except Exception as e:
            self.logger.warning("Failed to check replica set status: %s", e)
            return False

    async def start_session(self):
        """
        Start a database session for transactions.

        Returns:
            Database session object or None if not supported
        """
        try:
            if not await self.ensure_connection():
                raise MCPValidationError("Database not connected")

            if await self.is_replica_set():
                return await db_manager.client.start_session()
            else:
                self.logger.debug("Replica set not available, transactions not supported")
                return None
        except Exception as e:
            self.logger.error("Failed to start database session: %s", e)
            return None

    async def execute_with_retry(self, operation, max_retries: int = 3, delay: float = 1.0):
        """
        Execute database operation with retry logic.

        Args:
            operation: Async function to execute
            max_retries: Maximum number of retry attempts
            delay: Delay between retries in seconds

        Returns:
            Result of the operation

        Raises:
            MCPValidationError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                if not await self.ensure_connection():
                    raise MCPValidationError("Database not connected")

                return await operation()

            except Exception as e:
                last_error = e
                self.logger.warning("Database operation failed (attempt %d/%d): %s", attempt + 1, max_retries + 1, e)

                if attempt < max_retries:
                    await asyncio.sleep(delay * (2**attempt))  # Exponential backoff
                    # Reset connection verification to force recheck
                    self._connection_verified = False

        raise MCPValidationError(f"Database operation failed after {max_retries + 1} attempts: {last_error}")

    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics for monitoring.

        Returns:
            Dictionary with database statistics
        """
        try:
            if not await self.ensure_connection():
                return {"error": "Database not connected"}

            # Get database stats
            db_stats = await db_manager.client[settings.MONGODB_DATABASE].command("dbStats")

            # Get collection stats for key collections
            collection_stats = {}
            key_collections = ["users", "families", "family_relationships", "family_invitations"]

            for collection_name in key_collections:
                try:
                    collection = db_manager.get_collection(collection_name)
                    count = await collection.count_documents({})
                    collection_stats[collection_name] = {"document_count": count}
                except Exception as e:
                    collection_stats[collection_name] = {"error": str(e)}

            return {
                "database_stats": {
                    "collections": db_stats.get("collections", 0),
                    "data_size": db_stats.get("dataSize", 0),
                    "storage_size": db_stats.get("storageSize", 0),
                    "index_size": db_stats.get("indexSize", 0),
                },
                "collection_stats": collection_stats,
                "connection_info": {
                    "database_name": settings.MONGODB_DATABASE,
                    "replica_set": await self.is_replica_set(),
                },
            }

        except Exception as e:
            self.logger.error("Failed to get database stats: %s", e)
            return {"error": str(e)}


# Global instance
mcp_db_manager = MCPDatabaseManager()


async def ensure_mcp_database_connection() -> bool:
    """
    Ensure MCP database connection is established.

    Returns:
        True if connection is healthy, False otherwise
    """
    return await mcp_db_manager.ensure_connection()


async def get_mcp_collection(collection_name: str):
    """
    Get a database collection for MCP operations.

    Args:
        collection_name: Name of the collection

    Returns:
        MongoDB collection object

    Raises:
        MCPValidationError: If database is not connected
    """
    return await mcp_db_manager.get_collection(collection_name)


async def mcp_database_health_check() -> Dict[str, Any]:
    """
    Perform MCP database health check.

    Returns:
        Dictionary with health check results
    """
    return await mcp_db_manager.health_check()


async def initialize_mcp_database():
    """
    Initialize MCP database connection and verify setup.

    This function should be called during MCP server startup.
    """
    logger.info("Initializing MCP database connection...")

    try:
        # First, ensure the database manager is connected
        # This is the key fix - we need to explicitly connect the db_manager
        if not hasattr(db_manager, "client") or db_manager.client is None:
            logger.info("Database manager not connected, establishing connection...")
            await db_manager.connect()
            logger.info("Database manager connected successfully")

        # Ensure connection is established
        is_connected = await mcp_db_manager.ensure_connection()

        if is_connected:
            logger.info("MCP database connection established successfully")

            # Log database info
            stats = await mcp_db_manager.get_database_stats()
            if "error" not in stats:
                db_info = stats.get("connection_info", {})
                logger.info(
                    "Connected to database: %s (replica_set: %s)",
                    db_info.get("database_name", "unknown"),
                    db_info.get("replica_set", False),
                )

            return True
        else:
            logger.error("Failed to establish MCP database connection")
            return False

    except Exception as e:
        logger.error("MCP database initialization failed: %s", e)
        return False


class MCPDatabaseContext:
    """
    Context manager for MCP database operations.

    Provides automatic connection management and error handling.
    """

    def __init__(self, operation_name: str = "unknown"):
        self.operation_name = operation_name
        self.start_time = None

    async def __aenter__(self):
        self.start_time = datetime.now(timezone.utc)

        # Ensure connection
        if not await mcp_db_manager.ensure_connection():
            raise MCPValidationError(f"Database not available for operation: {self.operation_name}")

        logger.debug("Starting MCP database operation: %s", self.operation_name)
        return mcp_db_manager

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds() * 1000

        if exc_type is None:
            logger.debug("MCP database operation completed: %s (%.2fms)", self.operation_name, duration)
        else:
            logger.error(
                "MCP database operation failed: %s (%.2fms) - %s: %s",
                self.operation_name,
                duration,
                exc_type.__name__,
                exc_val,
            )

        return False  # Don't suppress exceptions


def mcp_database_operation(operation_name: str):
    """
    Create a database context manager for MCP operations.

    Args:
        operation_name: Name of the operation for logging

    Returns:
        MCPDatabaseContext instance
    """
    return MCPDatabaseContext(operation_name)
