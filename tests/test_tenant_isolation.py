"""
Integration tests for tenant isolation in database operations.

Tests that tenant-aware collections properly isolate data between tenants.
"""

import pytest
import pytest_asyncio
from bson import ObjectId

from second_brain_database.database import db_manager
from second_brain_database.database.tenant_collection import TenantAwareCollection
from second_brain_database.middleware.tenant_context import (
    clear_tenant_context,
    set_tenant_context,
)


@pytest_asyncio.fixture(scope="function")
async def test_collection():
    """Fixture to provide a test collection."""
    await db_manager.connect()
    collection = db_manager.get_collection("test_tenant_isolation")
    await collection.delete_many({})
    yield collection
    await collection.delete_many({})
    clear_tenant_context()


@pytest.mark.asyncio
class TestTenantIsolation:
    """Test suite for tenant data isolation."""

    async def test_tenant_aware_insert_adds_tenant_id(self, test_collection):
        """Test that tenant-aware insert adds tenant_id to documents."""
        tenant_id = "tenant_test_123"
        tenant_collection = TenantAwareCollection(test_collection, tenant_id)
        
        # Insert document
        doc = {"name": "Test Document", "value": 42}
        result = await tenant_collection.insert_one(doc)
        
        # Verify document has tenant_id
        inserted_doc = await test_collection.find_one({"_id": result.inserted_id})
        assert inserted_doc is not None
        assert inserted_doc["tenant_id"] == tenant_id
        assert inserted_doc["name"] == "Test Document"

    async def test_tenant_aware_find_filters_by_tenant(self, test_collection):
        """Test that tenant-aware find only returns documents for the tenant."""
        # Insert documents for different tenants
        await test_collection.insert_many([
            {"tenant_id": "tenant_a", "name": "Doc A1"},
            {"tenant_id": "tenant_a", "name": "Doc A2"},
            {"tenant_id": "tenant_b", "name": "Doc B1"},
            {"tenant_id": "tenant_b", "name": "Doc B2"},
        ])
        
        # Query with tenant A
        tenant_a_collection = TenantAwareCollection(test_collection, "tenant_a")
        docs_a = await tenant_a_collection.find({}).to_list(length=None)
        
        assert len(docs_a) == 2
        assert all(doc["tenant_id"] == "tenant_a" for doc in docs_a)
        
        # Query with tenant B
        tenant_b_collection = TenantAwareCollection(test_collection, "tenant_b")
        docs_b = await tenant_b_collection.find({}).to_list(length=None)
        
        assert len(docs_b) == 2
        assert all(doc["tenant_id"] == "tenant_b" for doc in docs_b)

    async def test_tenant_aware_update_only_affects_tenant_documents(self, test_collection):
        """Test that tenant-aware update only modifies documents for the tenant."""
        # Insert documents for different tenants
        await test_collection.insert_many([
            {"tenant_id": "tenant_a", "name": "Doc A", "status": "pending"},
            {"tenant_id": "tenant_b", "name": "Doc B", "status": "pending"},
        ])
        
        # Update with tenant A
        tenant_a_collection = TenantAwareCollection(test_collection, "tenant_a")
        result = await tenant_a_collection.update_many(
            {"status": "pending"},
            {"$set": {"status": "completed"}}
        )
        
        assert result.modified_count == 1
        
        # Verify only tenant A's document was updated
        doc_a = await test_collection.find_one({"tenant_id": "tenant_a"})
        doc_b = await test_collection.find_one({"tenant_id": "tenant_b"})
        
        assert doc_a["status"] == "completed"
        assert doc_b["status"] == "pending"

    async def test_tenant_aware_delete_only_affects_tenant_documents(self, test_collection):
        """Test that tenant-aware delete only removes documents for the tenant."""
        # Insert documents for different tenants
        await test_collection.insert_many([
            {"tenant_id": "tenant_a", "name": "Doc A"},
            {"tenant_id": "tenant_b", "name": "Doc B"},
        ])
        
        # Delete with tenant A
        tenant_a_collection = TenantAwareCollection(test_collection, "tenant_a")
        result = await tenant_a_collection.delete_many({})
        
        assert result.deleted_count == 1
        
        # Verify only tenant A's document was deleted
        remaining_docs = await test_collection.find({}).to_list(length=None)
        assert len(remaining_docs) == 1
        assert remaining_docs[0]["tenant_id"] == "tenant_b"

    async def test_tenant_aware_count_only_counts_tenant_documents(self, test_collection):
        """Test that tenant-aware count only counts documents for the tenant."""
        # Insert documents for different tenants
        await test_collection.insert_many([
            {"tenant_id": "tenant_a", "name": "Doc A1"},
            {"tenant_id": "tenant_a", "name": "Doc A2"},
            {"tenant_id": "tenant_a", "name": "Doc A3"},
            {"tenant_id": "tenant_b", "name": "Doc B1"},
        ])
        
        # Count with tenant A
        tenant_a_collection = TenantAwareCollection(test_collection, "tenant_a")
        count_a = await tenant_a_collection.count_documents({})
        
        assert count_a == 3
        
        # Count with tenant B
        tenant_b_collection = TenantAwareCollection(test_collection, "tenant_b")
        count_b = await tenant_b_collection.count_documents({})
        
        assert count_b == 1

    async def test_tenant_aware_aggregate_filters_by_tenant(self, test_collection):
        """Test that tenant-aware aggregate only processes documents for the tenant."""
        # Insert documents for different tenants
        await test_collection.insert_many([
            {"tenant_id": "tenant_a", "category": "A", "value": 10},
            {"tenant_id": "tenant_a", "category": "A", "value": 20},
            {"tenant_id": "tenant_b", "category": "A", "value": 100},
        ])
        
        # Aggregate with tenant A
        tenant_a_collection = TenantAwareCollection(test_collection, "tenant_a")
        pipeline = [
            {"$group": {"_id": "$category", "total": {"$sum": "$value"}}}
        ]
        cursor = tenant_a_collection.aggregate(pipeline)
        results = await cursor.to_list(length=None)
        
        assert len(results) == 1
        assert results[0]["total"] == 30  # Only tenant A's values (10 + 20)

    async def test_get_tenant_collection_with_context(self, test_collection):
        """Test that get_tenant_collection uses tenant context."""
        tenant_id = "tenant_context_test"
        set_tenant_context(tenant_id)
        
        # Get tenant-aware collection using context
        tenant_collection = db_manager.get_tenant_collection("test_tenant_isolation")
        
        # Verify it's a TenantAwareCollection
        assert isinstance(tenant_collection, TenantAwareCollection)
        assert tenant_collection.tenant_id == tenant_id
        
        # Insert and verify
        await tenant_collection.insert_one({"name": "Context Test"})
        
        doc = await test_collection.find_one({"name": "Context Test"})
        assert doc["tenant_id"] == tenant_id

    async def test_get_tenant_collection_with_explicit_tenant(self, test_collection):
        """Test that get_tenant_collection works with explicit tenant_id."""
        tenant_id = "tenant_explicit_test"
        
        # Get tenant-aware collection with explicit tenant_id
        tenant_collection = db_manager.get_tenant_collection(
            "test_tenant_isolation",
            tenant_id=tenant_id
        )
        
        # Verify it's a TenantAwareCollection
        assert isinstance(tenant_collection, TenantAwareCollection)
        assert tenant_collection.tenant_id == tenant_id
        
        # Insert and verify
        await tenant_collection.insert_one({"name": "Explicit Test"})
        
        doc = await test_collection.find_one({"name": "Explicit Test"})
        assert doc["tenant_id"] == tenant_id

    async def test_tenant_isolation_prevents_cross_tenant_access(self, test_collection):
        """Test that one tenant cannot access another tenant's data."""
        # Insert document for tenant A
        tenant_a_collection = TenantAwareCollection(test_collection, "tenant_a")
        await tenant_a_collection.insert_one({"name": "Secret A", "secret": "password123"})
        
        # Try to access with tenant B
        tenant_b_collection = TenantAwareCollection(test_collection, "tenant_b")
        doc = await tenant_b_collection.find_one({"name": "Secret A"})
        
        # Should not find the document
        assert doc is None
        
        # Verify tenant A can still access it
        doc_a = await tenant_a_collection.find_one({"name": "Secret A"})
        assert doc_a is not None
        assert doc_a["secret"] == "password123"
