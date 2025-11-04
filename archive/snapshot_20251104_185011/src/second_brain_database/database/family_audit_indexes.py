"""
Database indexes for family audit trail collections.

This module defines the indexes required for optimal performance of family audit
trail queries and compliance reporting.
"""

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[FamilyAuditIndexes]")

FAMILY_AUDIT_INDEXES = [
    # Primary query indexes
    {
        "collection": "family_audit_trails",
        "index": [("family_id", 1), ("timestamp", -1)],
        "options": {"name": "family_timestamp_idx"}
    },
    {
        "collection": "family_audit_trails",
        "index": [("family_id", 1), ("event_type", 1), ("timestamp", -1)],
        "options": {"name": "family_event_timestamp_idx"}
    },
    {
        "collection": "family_audit_trails",
        "index": [("transaction_details.transaction_id", 1)],
        "options": {"name": "transaction_id_idx", "unique": True}
    },
    
    # Family member attribution indexes
    {
        "collection": "family_audit_trails",
        "index": [("family_member_attribution.member_id", 1), ("timestamp", -1)],
        "options": {"name": "member_timestamp_idx"}
    },
    {
        "collection": "family_audit_trails",
        "index": [("family_id", 1), ("family_member_attribution.member_id", 1)],
        "options": {"name": "family_member_idx"}
    },
    
    # Compliance and audit indexes
    {
        "collection": "family_audit_trails",
        "index": [("compliance_metadata.retention_until", 1)],
        "options": {"name": "retention_idx"}
    },
    {
        "collection": "family_audit_trails",
        "index": [("audit_id", 1)],
        "options": {"name": "audit_id_idx", "unique": True}
    },
    {
        "collection": "family_audit_trails",
        "index": [("integrity.hash", 1)],
        "options": {"name": "integrity_hash_idx"}
    },
    
    # Performance indexes for large datasets
    {
        "collection": "family_audit_trails",
        "index": [("family_id", 1), ("event_subtype", 1), ("timestamp", -1)],
        "options": {"name": "family_subtype_timestamp_idx"}
    },
    {
        "collection": "family_audit_trails",
        "index": [("timestamp", -1)],
        "options": {"name": "timestamp_desc_idx"}
    },
    
    # Update family collection indexes for audit summary
    {
        "collection": "families",
        "index": [("audit_summary.last_audit_at", -1)],
        "options": {"name": "family_last_audit_idx"}
    }
]


async def create_family_audit_indexes():
    """
    Create all required indexes for family audit trail collections.
    
    This function should be called during application startup to ensure
    optimal query performance for audit trail operations.
    """
    try:
        logger.info("Creating family audit trail indexes...")
        
        created_count = 0
        for index_spec in FAMILY_AUDIT_INDEXES:
            collection_name = index_spec["collection"]
            index_keys = index_spec["index"]
            options = index_spec.get("options", {})
            
            try:
                collection = db_manager.get_collection(collection_name)
                await collection.create_index(index_keys, **options)
                created_count += 1
                logger.debug(
                    "Created index %s on collection %s",
                    options.get("name", "unnamed"), collection_name
                )
            except Exception as e:
                # Index might already exist, log warning but continue
                logger.warning(
                    "Failed to create index %s on collection %s: %s",
                    options.get("name", "unnamed"), collection_name, e
                )
        
        logger.info(
            "Family audit trail index creation completed: %d/%d indexes created",
            created_count, len(FAMILY_AUDIT_INDEXES)
        )
        
    except Exception as e:
        logger.error("Failed to create family audit trail indexes: %s", e, exc_info=True)
        raise


async def drop_family_audit_indexes():
    """
    Drop all family audit trail indexes.
    
    This function can be used for maintenance or testing purposes.
    """
    try:
        logger.info("Dropping family audit trail indexes...")
        
        dropped_count = 0
        for index_spec in FAMILY_AUDIT_INDEXES:
            collection_name = index_spec["collection"]
            options = index_spec.get("options", {})
            index_name = options.get("name")
            
            if index_name:
                try:
                    collection = db_manager.get_collection(collection_name)
                    await collection.drop_index(index_name)
                    dropped_count += 1
                    logger.debug("Dropped index %s from collection %s", index_name, collection_name)
                except Exception as e:
                    logger.warning(
                        "Failed to drop index %s from collection %s: %s",
                        index_name, collection_name, e
                    )
        
        logger.info(
            "Family audit trail index removal completed: %d indexes dropped",
            dropped_count
        )
        
    except Exception as e:
        logger.error("Failed to drop family audit trail indexes: %s", e, exc_info=True)
        raise


async def verify_family_audit_indexes():
    """
    Verify that all required family audit trail indexes exist.
    
    Returns:
        Dict containing verification results
    """
    try:
        logger.info("Verifying family audit trail indexes...")
        
        verification_results = {
            "total_indexes": len(FAMILY_AUDIT_INDEXES),
            "verified_indexes": 0,
            "missing_indexes": [],
            "collections_checked": set()
        }
        
        for index_spec in FAMILY_AUDIT_INDEXES:
            collection_name = index_spec["collection"]
            options = index_spec.get("options", {})
            index_name = options.get("name", "unnamed")
            
            verification_results["collections_checked"].add(collection_name)
            
            try:
                collection = db_manager.get_collection(collection_name)
                indexes = await collection.list_indexes().to_list(length=None)
                index_names = [idx.get("name") for idx in indexes]
                
                if index_name in index_names:
                    verification_results["verified_indexes"] += 1
                    logger.debug("Verified index %s on collection %s", index_name, collection_name)
                else:
                    verification_results["missing_indexes"].append({
                        "collection": collection_name,
                        "index_name": index_name,
                        "index_spec": index_spec["index"]
                    })
                    logger.warning("Missing index %s on collection %s", index_name, collection_name)
                    
            except Exception as e:
                logger.warning(
                    "Failed to verify index %s on collection %s: %s",
                    index_name, collection_name, e
                )
                verification_results["missing_indexes"].append({
                    "collection": collection_name,
                    "index_name": index_name,
                    "error": str(e)
                })
        
        verification_results["collections_checked"] = list(verification_results["collections_checked"])
        
        logger.info(
            "Family audit trail index verification completed: %d/%d indexes verified",
            verification_results["verified_indexes"], verification_results["total_indexes"]
        )
        
        return verification_results
        
    except Exception as e:
        logger.error("Failed to verify family audit trail indexes: %s", e, exc_info=True)
        return {
            "total_indexes": len(FAMILY_AUDIT_INDEXES),
            "verified_indexes": 0,
            "missing_indexes": [],
            "collections_checked": [],
            "error": str(e)
        }