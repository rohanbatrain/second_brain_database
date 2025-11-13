"""
IPAM collections migration script.

This module handles the initialization of IPAM system collections and seeding
of continent-country mapping data.
"""

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.migrations.ipam_data import CONTINENT_COUNTRY_MAPPINGS

logger = get_logger(prefix="[IPAMMigration]")


async def initialize_ipam_system():
    """
    Initialize IPAM system by creating collections and seeding continent-country mappings.

    This function should be called during application startup to ensure the IPAM system
    is properly initialized with predefined geographic structure.

    Process:
    1. Check if continent_country_mapping collection exists
    2. If empty, seed with predefined mappings
    3. Log initialization status

    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        logger.info("Starting IPAM system initialization...")

        # Get continent-country mapping collection
        mapping_collection = db_manager.get_collection("continent_country_mapping")

        # Check if collection is already seeded
        existing_count = await mapping_collection.count_documents({})

        if existing_count > 0:
            logger.info(
                "Continent-country mapping collection already initialized with %d mappings", existing_count
            )
            return True

        # Seed the collection with predefined mappings
        logger.info("Seeding continent-country mapping collection with %d mappings...", len(CONTINENT_COUNTRY_MAPPINGS))

        result = await mapping_collection.insert_many(CONTINENT_COUNTRY_MAPPINGS)

        inserted_count = len(result.inserted_ids)
        logger.info("Successfully seeded %d continent-country mappings", inserted_count)

        # Verify seeding
        final_count = await mapping_collection.count_documents({})
        if final_count != len(CONTINENT_COUNTRY_MAPPINGS):
            logger.warning(
                "Mapping count mismatch: expected %d, found %d",
                len(CONTINENT_COUNTRY_MAPPINGS),
                final_count,
            )
            return False

        logger.info("IPAM system initialization completed successfully")
        return True

    except Exception as e:
        logger.error("Failed to initialize IPAM system: %s", e, exc_info=True)
        return False


async def verify_ipam_initialization():
    """
    Verify that IPAM system is properly initialized.

    Returns:
        dict: Verification results with status and details
    """
    try:
        logger.info("Verifying IPAM system initialization...")

        verification_results = {
            "initialized": False,
            "mapping_count": 0,
            "expected_count": len(CONTINENT_COUNTRY_MAPPINGS),
            "missing_countries": [],
            "collections_exist": {},
        }

        # Check continent-country mapping collection
        mapping_collection = db_manager.get_collection("continent_country_mapping")
        mapping_count = await mapping_collection.count_documents({})
        verification_results["mapping_count"] = mapping_count

        # Verify all expected countries exist
        expected_countries = {(m["continent"], m["country"]) for m in CONTINENT_COUNTRY_MAPPINGS}
        existing_mappings = await mapping_collection.find({}, {"continent": 1, "country": 1}).to_list(length=None)
        existing_countries = {(m["continent"], m["country"]) for m in existing_mappings}

        missing = expected_countries - existing_countries
        if missing:
            verification_results["missing_countries"] = [
                {"continent": continent, "country": country} for continent, country in missing
            ]
            logger.warning("Missing %d country mappings: %s", len(missing), missing)
        else:
            logger.info("All expected country mappings present")

        # Check if other IPAM collections exist (they may be empty initially)
        ipam_collections = ["ipam_regions", "ipam_hosts", "ipam_audit_history", "ipam_user_quotas"]
        for collection_name in ipam_collections:
            try:
                collection = db_manager.get_collection(collection_name)
                count = await collection.count_documents({})
                verification_results["collections_exist"][collection_name] = {
                    "exists": True,
                    "document_count": count,
                }
            except Exception as e:
                verification_results["collections_exist"][collection_name] = {
                    "exists": False,
                    "error": str(e),
                }

        # Determine overall initialization status
        verification_results["initialized"] = (
            mapping_count == len(CONTINENT_COUNTRY_MAPPINGS) and len(missing) == 0
        )

        if verification_results["initialized"]:
            logger.info("IPAM system verification passed")
        else:
            logger.warning("IPAM system verification failed")

        return verification_results

    except Exception as e:
        logger.error("Failed to verify IPAM system initialization: %s", e, exc_info=True)
        return {
            "initialized": False,
            "error": str(e),
        }
