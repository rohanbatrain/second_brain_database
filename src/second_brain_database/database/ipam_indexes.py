"""
Database indexes for IPAM collections.

This module defines the indexes required for optimal performance of IPAM
operations including region allocation, host allocation, and audit queries.
"""

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMIndexes]")

# IPAM index specifications following the family_audit_indexes pattern
IPAM_INDEXES = [
    # Continent-country mapping indexes (read-only reference data)
    {
        "collection": "continent_country_mapping",
        "index": [("continent", 1)],
        "options": {"name": "continent_idx"},
    },
    {
        "collection": "continent_country_mapping",
        "index": [("country", 1)],
        "options": {"name": "country_idx", "unique": True},
    },
    {
        "collection": "continent_country_mapping",
        "index": [("x_start", 1)],
        "options": {"name": "x_start_idx"},
    },
    {
        "collection": "continent_country_mapping",
        "index": [("is_reserved", 1)],
        "options": {"name": "is_reserved_idx"},
    },
    # IPAM regions collection indexes
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("country", 1), ("region_name", 1)],
        "options": {"name": "user_country_region_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("x_octet", 1), ("y_octet", 1)],
        "options": {"name": "user_xy_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("country", 1), ("status", 1)],
        "options": {"name": "user_country_status_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("tags", 1)],
        "options": {"name": "user_tags_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("created_at", -1)],
        "options": {"name": "user_created_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("continent", 1)],
        "options": {"name": "user_continent_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("user_id", 1), ("x_octet", 1)],
        "options": {"name": "user_x_octet_idx"},
    },
    {
        "collection": "ipam_regions",
        "index": [("cidr", 1)],
        "options": {"name": "cidr_idx"},
    },
    # IPAM hosts collection indexes
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("region_id", 1), ("hostname", 1)],
        "options": {"name": "user_region_hostname_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("x_octet", 1), ("y_octet", 1), ("z_octet", 1)],
        "options": {"name": "user_xyz_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("ip_address", 1)],
        "options": {"name": "user_ip_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("status", 1)],
        "options": {"name": "user_status_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("region_id", 1)],
        "options": {"name": "user_region_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("tags", 1)],
        "options": {"name": "user_host_tags_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("created_at", -1)],
        "options": {"name": "user_host_created_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("device_type", 1)],
        "options": {"name": "user_device_type_idx"},
    },
    {
        "collection": "ipam_hosts",
        "index": [("user_id", 1), ("hostname", 1)],
        "options": {"name": "user_hostname_idx"},
    },
    # IPAM audit history collection indexes
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("timestamp", -1)],
        "options": {"name": "user_timestamp_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("resource_type", 1), ("action_type", 1)],
        "options": {"name": "user_resource_action_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("ip_address", 1)],
        "options": {"name": "user_ip_audit_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("cidr", 1)],
        "options": {"name": "user_cidr_audit_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("user_id", 1), ("resource_id", 1), ("timestamp", -1)],
        "options": {"name": "user_resource_timestamp_idx"},
    },
    {
        "collection": "ipam_audit_history",
        "index": [("timestamp", -1)],
        "options": {"name": "timestamp_desc_audit_idx"},
    },
    # IPAM user quotas collection indexes
    {
        "collection": "ipam_user_quotas",
        "index": [("user_id", 1)],
        "options": {"name": "user_quota_unique_idx", "unique": True},
    },
    {
        "collection": "ipam_user_quotas",
        "index": [("last_updated", -1)],
        "options": {"name": "quota_last_updated_idx"},
    },
    # IPAM export jobs collection indexes
    {
        "collection": "ipam_export_jobs",
        "index": [("user_id", 1), ("created_at", -1)],
        "options": {"name": "user_export_created_idx"},
    },
    {
        "collection": "ipam_export_jobs",
        "index": [("user_id", 1), ("status", 1)],
        "options": {"name": "user_export_status_idx"},
    },
    {
        "collection": "ipam_export_jobs",
        "index": [("expires_at", 1)],
        "options": {"name": "export_expires_idx"},
    },
]


async def create_ipam_indexes():
    """
    Create all required indexes for IPAM collections.

    This function should be called during application startup to ensure
    optimal query performance for IPAM operations.

    Returns:
        bool: True if all indexes created successfully, False otherwise
    """
    try:
        logger.info("Creating IPAM indexes...")

        created_count = 0
        failed_count = 0

        for index_spec in IPAM_INDEXES:
            collection_name = index_spec["collection"]
            index_keys = index_spec["index"]
            options = index_spec.get("options", {})
            index_name = options.get("name", "unnamed")

            try:
                collection = db_manager.get_collection(collection_name)
                await collection.create_index(index_keys, **options)
                created_count += 1
                logger.debug("Created index %s on collection %s", index_name, collection_name)
            except Exception as e:
                # Index might already exist, log warning but continue
                failed_count += 1
                logger.warning(
                    "Failed to create index %s on collection %s: %s",
                    index_name,
                    collection_name,
                    e,
                )

        logger.info(
            "IPAM index creation completed: %d/%d indexes created, %d failed/already exist",
            created_count,
            len(IPAM_INDEXES),
            failed_count,
        )

        return True

    except Exception as e:
        logger.error("Failed to create IPAM indexes: %s", e, exc_info=True)
        return False


async def drop_ipam_indexes():
    """
    Drop all IPAM indexes.

    This function can be used for maintenance or testing purposes.

    Returns:
        bool: True if all indexes dropped successfully, False otherwise
    """
    try:
        logger.info("Dropping IPAM indexes...")

        dropped_count = 0
        failed_count = 0

        for index_spec in IPAM_INDEXES:
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
                    failed_count += 1
                    logger.warning(
                        "Failed to drop index %s from collection %s: %s",
                        index_name,
                        collection_name,
                        e,
                    )

        logger.info(
            "IPAM index removal completed: %d indexes dropped, %d failed",
            dropped_count,
            failed_count,
        )

        return True

    except Exception as e:
        logger.error("Failed to drop IPAM indexes: %s", e, exc_info=True)
        return False


async def verify_ipam_indexes():
    """
    Verify that all required IPAM indexes exist.

    Returns:
        dict: Verification results with status and details
    """
    try:
        logger.info("Verifying IPAM indexes...")

        verification_results = {
            "total_indexes": len(IPAM_INDEXES),
            "verified_indexes": 0,
            "missing_indexes": [],
            "collections_checked": set(),
        }

        for index_spec in IPAM_INDEXES:
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
                    verification_results["missing_indexes"].append(
                        {
                            "collection": collection_name,
                            "index_name": index_name,
                            "index_spec": index_spec["index"],
                        }
                    )
                    logger.warning("Missing index %s on collection %s", index_name, collection_name)

            except Exception as e:
                logger.warning(
                    "Failed to verify index %s on collection %s: %s",
                    index_name,
                    collection_name,
                    e,
                )
                verification_results["missing_indexes"].append(
                    {
                        "collection": collection_name,
                        "index_name": index_name,
                        "error": str(e),
                    }
                )

        verification_results["collections_checked"] = list(verification_results["collections_checked"])

        logger.info(
            "IPAM index verification completed: %d/%d indexes verified",
            verification_results["verified_indexes"],
            verification_results["total_indexes"],
        )

        return verification_results

    except Exception as e:
        logger.error("Failed to verify IPAM indexes: %s", e, exc_info=True)
        return {
            "total_indexes": len(IPAM_INDEXES),
            "verified_indexes": 0,
            "missing_indexes": [],
            "collections_checked": [],
            "error": str(e),
        }
