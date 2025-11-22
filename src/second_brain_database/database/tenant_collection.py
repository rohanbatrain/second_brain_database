"""
Tenant-aware collection wrapper for automatic tenant isolation.

This module provides a wrapper around AsyncIOMotorCollection that automatically
adds tenant_id filtering to all database operations.
"""

from typing import Any, Dict, List, Optional, Union

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorCursor
from pymongo import ReturnDocument

from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Tenant Collection]")


class TenantAwareCollection:
    """
    Wrapper that automatically adds tenant_id to all queries.

    This class wraps an AsyncIOMotorCollection and ensures that all
    database operations are automatically scoped to a specific tenant.
    """

    def __init__(self, collection: AsyncIOMotorCollection, tenant_id: str):
        """
        Initialize the tenant-aware collection wrapper.

        Args:
            collection: The underlying MongoDB collection
            tenant_id: The tenant ID to scope all operations to
        """
        self._collection = collection
        self._tenant_id = tenant_id
        logger.debug("Created tenant-aware collection for tenant: %s", tenant_id)

    def _add_tenant_filter(self, filter_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Add tenant_id to filter dictionary.

        Args:
            filter_dict: The original filter dictionary

        Returns:
            Filter dictionary with tenant_id added
        """
        filter_dict = filter_dict or {}
        filter_dict["tenant_id"] = self._tenant_id
        return filter_dict

    def _add_tenant_to_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add tenant_id to document.

        Args:
            document: The document to modify

        Returns:
            Document with tenant_id added
        """
        document["tenant_id"] = self._tenant_id
        return document

    async def find_one(
        self, filter: Optional[Dict[str, Any]] = None, *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Find a single document with tenant filtering.

        Args:
            filter: Query filter
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Document or None if not found
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.find_one(filter, *args, **kwargs)
        logger.debug("find_one for tenant %s: %s", self._tenant_id, "found" if result else "not found")
        return result

    def find(self, filter: Optional[Dict[str, Any]] = None, *args, **kwargs) -> AsyncIOMotorCursor:
        """
        Find multiple documents with tenant filtering.

        Args:
            filter: Query filter
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Cursor for iterating results
        """
        filter = self._add_tenant_filter(filter)
        cursor = self._collection.find(filter, *args, **kwargs)
        logger.debug("find for tenant %s with filter: %s", self._tenant_id, filter)
        return cursor

    async def insert_one(self, document: Dict[str, Any], *args, **kwargs):
        """
        Insert a single document with tenant_id.

        Args:
            document: Document to insert
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            InsertOneResult
        """
        document = self._add_tenant_to_document(document)
        result = await self._collection.insert_one(document, *args, **kwargs)
        logger.debug("insert_one for tenant %s: inserted_id=%s", self._tenant_id, result.inserted_id)
        return result

    async def insert_many(self, documents: List[Dict[str, Any]], *args, **kwargs):
        """
        Insert multiple documents with tenant_id.

        Args:
            documents: List of documents to insert
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            InsertManyResult
        """
        documents = [self._add_tenant_to_document(doc) for doc in documents]
        result = await self._collection.insert_many(documents, *args, **kwargs)
        logger.debug("insert_many for tenant %s: inserted %d documents", self._tenant_id, len(result.inserted_ids))
        return result

    async def update_one(
        self, filter: Dict[str, Any], update: Dict[str, Any], *args, **kwargs
    ):
        """
        Update a single document with tenant filtering.

        Args:
            filter: Query filter
            update: Update operations
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            UpdateResult
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.update_one(filter, update, *args, **kwargs)
        logger.debug(
            "update_one for tenant %s: matched=%d, modified=%d",
            self._tenant_id,
            result.matched_count,
            result.modified_count,
        )
        return result

    async def update_many(
        self, filter: Dict[str, Any], update: Dict[str, Any], *args, **kwargs
    ):
        """
        Update multiple documents with tenant filtering.

        Args:
            filter: Query filter
            update: Update operations
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            UpdateResult
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.update_many(filter, update, *args, **kwargs)
        logger.debug(
            "update_many for tenant %s: matched=%d, modified=%d",
            self._tenant_id,
            result.matched_count,
            result.modified_count,
        )
        return result

    async def delete_one(self, filter: Dict[str, Any], *args, **kwargs):
        """
        Delete a single document with tenant filtering.

        Args:
            filter: Query filter
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            DeleteResult
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.delete_one(filter, *args, **kwargs)
        logger.debug("delete_one for tenant %s: deleted=%d", self._tenant_id, result.deleted_count)
        return result

    async def delete_many(self, filter: Dict[str, Any], *args, **kwargs):
        """
        Delete multiple documents with tenant filtering.

        Args:
            filter: Query filter
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            DeleteResult
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.delete_many(filter, *args, **kwargs)
        logger.debug("delete_many for tenant %s: deleted=%d", self._tenant_id, result.deleted_count)
        return result

    async def find_one_and_update(
        self,
        filter: Dict[str, Any],
        update: Dict[str, Any],
        *args,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Find and update a single document with tenant filtering.

        Args:
            filter: Query filter
            update: Update operations
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            The document (before or after update, depending on return_document)
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.find_one_and_update(filter, update, *args, **kwargs)
        logger.debug("find_one_and_update for tenant %s: %s", self._tenant_id, "found" if result else "not found")
        return result

    async def find_one_and_delete(
        self, filter: Dict[str, Any], *args, **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Find and delete a single document with tenant filtering.

        Args:
            filter: Query filter
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            The deleted document or None
        """
        filter = self._add_tenant_filter(filter)
        result = await self._collection.find_one_and_delete(filter, *args, **kwargs)
        logger.debug("find_one_and_delete for tenant %s: %s", self._tenant_id, "found" if result else "not found")
        return result

    async def count_documents(self, filter: Optional[Dict[str, Any]] = None, *args, **kwargs) -> int:
        """
        Count documents with tenant filtering.

        Args:
            filter: Query filter
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Number of matching documents
        """
        filter = self._add_tenant_filter(filter)
        count = await self._collection.count_documents(filter, *args, **kwargs)
        logger.debug("count_documents for tenant %s: %d", self._tenant_id, count)
        return count

    async def aggregate(self, pipeline: List[Dict[str, Any]], *args, **kwargs):
        """
        Run aggregation pipeline with tenant filtering.

        Args:
            pipeline: Aggregation pipeline
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Aggregation cursor
        """
        # Add tenant filter as first stage in pipeline
        tenant_match = {"$match": {"tenant_id": self._tenant_id}}
        pipeline = [tenant_match] + pipeline
        cursor = self._collection.aggregate(pipeline, *args, **kwargs)
        logger.debug("aggregate for tenant %s with %d stages", self._tenant_id, len(pipeline))
        return cursor

    @property
    def name(self) -> str:
        """Get the collection name."""
        return self._collection.name

    @property
    def tenant_id(self) -> str:
        """Get the tenant ID."""
        return self._tenant_id
