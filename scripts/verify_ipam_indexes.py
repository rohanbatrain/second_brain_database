"""
Script to verify all IPAM backend enhancements indexes have been created.

This script checks that all required indexes exist on the IPAM collections
and reports any missing or incorrectly configured indexes.
"""

import asyncio
import sys
from typing import Dict, List, Set

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMIndexVerification]")


# Expected indexes for each collection
EXPECTED_INDEXES = {
    "ipam_reservations": [
        {"keys": [("user_id", 1), ("status", 1)], "unique": False},
        {"keys": [("x_octet", 1), ("y_octet", 1), ("z_octet", 1)], "unique": False},
        {"keys": [("expires_at", 1)], "unique": False},
        {"keys": [("user_id", 1), ("resource_type", 1)], "unique": False},
        {"keys": [("user_id", 1), ("created_at", -1)], "unique": False},
    ],
    "ipam_shares": [
        {"keys": [("share_token", 1)], "unique": True},
        {"keys": [("user_id", 1), ("is_active", 1)], "unique": False},
        {"keys": [("expires_at", 1)], "unique": False},
        {"keys": [("user_id", 1), ("created_at", -1)], "unique": False},
        {"keys": [("resource_type", 1), ("resource_id", 1)], "unique": False},
    ],
    "ipam_user_preferences": [
        {"keys": [("user_id", 1)], "unique": True},
        {"keys": [("updated_at", 1)], "unique": False},
    ],
    "ipam_notifications": [
        {"keys": [("user_id", 1), ("is_read", 1), ("created_at", -1)], "unique": False},
        {"keys": [("expires_at", 1)], "unique": False},
        {"keys": [("user_id", 1), ("severity", 1)], "unique": False},
        {"keys": [("user_id", 1), ("notification_type", 1)], "unique": False},
    ],
    "ipam_notification_rules": [
        {"keys": [("user_id", 1), ("is_active", 1)], "unique": False},
        {"keys": [("user_id", 1), ("created_at", -1)], "unique": False},
        {"keys": [("last_triggered", 1)], "unique": False},
    ],
    "ipam_webhooks": [
        {"keys": [("user_id", 1), ("is_active", 1)], "unique": False},
        {"keys": [("user_id", 1), ("created_at", -1)], "unique": False},
        {"keys": [("last_delivery", 1)], "unique": False},
        {"keys": [("failure_count", 1)], "unique": False},
    ],
    "ipam_webhook_deliveries": [
        {"keys": [("webhook_id", 1), ("delivered_at", -1)], "unique": False},
        {"keys": [("event_type", 1)], "unique": False},
        {"keys": [("delivered_at", 1)], "unique": False},
        {"keys": [("webhook_id", 1), ("status_code", 1)], "unique": False},
    ],
    "ipam_bulk_jobs": [
        {"keys": [("job_id", 1)], "unique": True},
        {"keys": [("user_id", 1), ("created_at", -1)], "unique": False},
        {"keys": [("user_id", 1), ("status", 1)], "unique": False},
        {"keys": [("status", 1)], "unique": False},
        {"keys": [("created_at", 1)], "unique": False},
    ],
}


def normalize_index_key(key: List[tuple]) -> tuple:
    """Normalize index key for comparison."""
    return tuple(sorted(key))


async def get_collection_indexes(collection_name: str) -> Dict[str, Dict]:
    """Get all indexes for a collection."""
    try:
        collection = db_manager.get_collection(collection_name)
        indexes = await collection.index_information()
        return indexes
    except Exception as e:
        logger.error(f"Failed to get indexes for {collection_name}: {e}")
        return {}


async def verify_collection_indexes(collection_name: str) -> tuple[bool, List[str], List[str]]:
    """
    Verify indexes for a collection.
    
    Returns:
        tuple: (all_present, missing_indexes, extra_indexes)
    """
    logger.info(f"Verifying indexes for {collection_name}...")
    
    # Get actual indexes
    actual_indexes = await get_collection_indexes(collection_name)
    
    if not actual_indexes:
        logger.error(f"Collection {collection_name} not found or has no indexes")
        return False, [str(idx) for idx in EXPECTED_INDEXES.get(collection_name, [])], []
    
    # Get expected indexes for this collection
    expected = EXPECTED_INDEXES.get(collection_name, [])
    
    # Track found and missing indexes
    found_indexes = []
    missing_indexes = []
    
    # Check each expected index
    for expected_idx in expected:
        expected_keys = expected_idx["keys"]
        expected_unique = expected_idx["unique"]
        
        # Look for matching index in actual indexes
        found = False
        for idx_name, idx_info in actual_indexes.items():
            # Skip the default _id index
            if idx_name == "_id_":
                continue
            
            # Get the key specification
            actual_keys = list(idx_info.get("key", []))
            actual_unique = idx_info.get("unique", False)
            
            # Compare keys and unique constraint
            if actual_keys == expected_keys and actual_unique == expected_unique:
                found = True
                found_indexes.append(idx_name)
                break
        
        if not found:
            missing_indexes.append(f"{expected_keys} (unique={expected_unique})")
    
    # Check for extra indexes (not in expected list)
    extra_indexes = []
    for idx_name, idx_info in actual_indexes.items():
        if idx_name == "_id_":
            continue
        
        actual_keys = list(idx_info.get("key", []))
        actual_unique = idx_info.get("unique", False)
        
        # Check if this index is expected
        is_expected = False
        for expected_idx in expected:
            if actual_keys == expected_idx["keys"] and actual_unique == expected_idx["unique"]:
                is_expected = True
                break
        
        if not is_expected:
            extra_indexes.append(f"{idx_name}: {actual_keys} (unique={actual_unique})")
    
    all_present = len(missing_indexes) == 0
    
    return all_present, missing_indexes, extra_indexes


async def verify_all_indexes() -> bool:
    """
    Verify all IPAM collection indexes.
    
    Returns:
        bool: True if all indexes are present, False otherwise
    """
    logger.info("=" * 80)
    logger.info("IPAM Backend Enhancements - Index Verification")
    logger.info("=" * 80)
    
    # Connect to database
    try:
        await db_manager.connect()
        logger.info("✓ Connected to database")
    except Exception as e:
        logger.error(f"✗ Failed to connect to database: {e}")
        return False
    
    # Check database health
    if not await db_manager.health_check():
        logger.error("✗ Database health check failed")
        return False
    
    logger.info("✓ Database health check passed")
    logger.info("")
    
    # Verify each collection
    all_collections_ok = True
    total_missing = 0
    total_extra = 0
    
    for collection_name in EXPECTED_INDEXES.keys():
        all_present, missing, extra = await verify_collection_indexes(collection_name)
        
        if all_present and len(extra) == 0:
            logger.info(f"✓ {collection_name}: All indexes present")
        else:
            all_collections_ok = False
            logger.warning(f"✗ {collection_name}: Issues found")
            
            if missing:
                total_missing += len(missing)
                logger.warning(f"  Missing indexes ({len(missing)}):")
                for idx in missing:
                    logger.warning(f"    - {idx}")
            
            if extra:
                total_extra += len(extra)
                logger.info(f"  Extra indexes ({len(extra)}):")
                for idx in extra:
                    logger.info(f"    - {idx}")
        
        logger.info("")
    
    # Summary
    logger.info("=" * 80)
    logger.info("Verification Summary")
    logger.info("=" * 80)
    
    if all_collections_ok:
        logger.info("✓ All indexes verified successfully!")
        logger.info(f"  Collections checked: {len(EXPECTED_INDEXES)}")
        logger.info(f"  Total expected indexes: {sum(len(v) for v in EXPECTED_INDEXES.values())}")
    else:
        logger.error("✗ Index verification failed")
        logger.error(f"  Missing indexes: {total_missing}")
        if total_extra > 0:
            logger.info(f"  Extra indexes: {total_extra} (not necessarily a problem)")
    
    logger.info("=" * 80)
    
    # Disconnect
    await db_manager.disconnect()
    
    return all_collections_ok


async def main():
    """Main entry point."""
    try:
        success = await verify_all_indexes()
        sys.exit(0 if success else 1)
    except Exception as e:
        logger.error(f"Verification failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
