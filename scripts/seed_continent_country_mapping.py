"""
Seed script for continent_country_mapping collection.

This script populates the continent_country_mapping collection with the
hierarchical IP allocation rules as defined in the SOP.

Based on: Hierarchical IP Allocation Rules (10.X.Y.Z)
"""

import asyncio
from datetime import datetime, timezone

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Seed Country Mapping]")

# Continent → Country Mapping (Fixed) from SOP
COUNTRY_MAPPINGS = [
    # Asia
    {"continent": "Asia", "country": "India", "x_start": 0, "x_end": 29},
    {"continent": "Asia", "country": "UAE", "x_start": 30, "x_end": 37},
    {"continent": "Asia", "country": "Singapore", "x_start": 38, "x_end": 45},
    {"continent": "Asia", "country": "Japan", "x_start": 46, "x_end": 53},
    {"continent": "Asia", "country": "South Korea", "x_start": 54, "x_end": 61},
    {"continent": "Asia", "country": "Indonesia", "x_start": 62, "x_end": 69},
    {"continent": "Asia", "country": "Taiwan", "x_start": 70, "x_end": 77},
    
    # Africa
    {"continent": "Africa", "country": "South Africa", "x_start": 78, "x_end": 97},
    
    # Europe
    {"continent": "Europe", "country": "Finland", "x_start": 98, "x_end": 107},
    {"continent": "Europe", "country": "Sweden", "x_start": 108, "x_end": 117},
    {"continent": "Europe", "country": "Poland", "x_start": 118, "x_end": 127},
    {"continent": "Europe", "country": "Spain", "x_start": 128, "x_end": 137},
    
    # North America
    {"continent": "North America", "country": "Canada", "x_start": 138, "x_end": 152},
    {"continent": "North America", "country": "United States", "x_start": 153, "x_end": 167},
    
    # South America
    {"continent": "South America", "country": "Brazil", "x_start": 168, "x_end": 177},
    {"continent": "South America", "country": "Chile", "x_start": 178, "x_end": 187},
    
    # Australia
    {"continent": "Australia", "country": "Australia", "x_start": 188, "x_end": 207},
    
    # Reserved
    {"continent": "Reserved", "country": "Future Use", "x_start": 208, "x_end": 255},
]


async def seed_country_mappings():
    """Seed the continent_country_mapping collection with SOP data."""
    try:
        await db_manager.connect()
        logger.info("Connected to MongoDB")
        
        collection = db_manager.get_collection("continent_country_mapping")
        
        # Check if collection already has data
        existing_count = await collection.count_documents({})
        if existing_count > 0:
            logger.warning(
                "Collection already has %d documents. Do you want to clear and reseed? (y/n)",
                existing_count
            )
            response = input("Clear and reseed? (y/n): ").strip().lower()
            if response == 'y':
                result = await collection.delete_many({})
                logger.info("Deleted %d existing documents", result.deleted_count)
            else:
                logger.info("Keeping existing data. Exiting.")
                return
        
        # Prepare documents with metadata
        documents = []
        for mapping in COUNTRY_MAPPINGS:
            # Calculate total blocks (number of X values)
            total_blocks = mapping["x_end"] - mapping["x_start"] + 1
            
            doc = {
                "continent": mapping["continent"],
                "country": mapping["country"],
                "x_start": mapping["x_start"],
                "x_end": mapping["x_end"],
                "total_blocks": total_blocks,
                "allocated_regions": 0,  # Initially no regions allocated
                "remaining_capacity": total_blocks * 256,  # Each X has 256 Y values
                "utilization_percent": 0.0,
                "is_reserved": mapping["country"] == "Future Use",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            documents.append(doc)
        
        # Insert all documents
        result = await collection.insert_many(documents)
        logger.info("Successfully inserted %d country mappings", len(result.inserted_ids))
        
        # Create indexes for efficient querying
        await collection.create_index("continent")
        await collection.create_index("country", unique=True)
        await collection.create_index([("x_start", 1), ("x_end", 1)])
        logger.info("Created indexes on continent, country, and x_start/x_end")
        
        # Display summary
        logger.info("\n=== Country Mapping Summary ===")
        for continent in ["Asia", "Africa", "Europe", "North America", "South America", "Australia", "Reserved"]:
            count = await collection.count_documents({"continent": continent})
            logger.info("  %s: %d countries", continent, count)
        
        logger.info("\n=== Sample Mappings ===")
        sample_docs = await collection.find().limit(5).to_list(5)
        for doc in sample_docs:
            logger.info(
                "  %s (%s): X=%d-%d (%d blocks)",
                doc["country"],
                doc["continent"],
                doc["x_start"],
                doc["x_end"],
                doc["total_blocks"]
            )
        
        logger.info("\n✅ Country mapping seed completed successfully!")
        
    except Exception as e:
        logger.error("Failed to seed country mappings: %s", e, exc_info=True)
        raise
    finally:
        await db_manager.disconnect()
        logger.info("Disconnected from MongoDB")


if __name__ == "__main__":
    asyncio.run(seed_country_mappings())
