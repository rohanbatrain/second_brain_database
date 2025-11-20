#!/usr/bin/env python3
"""
Seed shop items into the database.

This script populates the shop_items collection with all available themes, avatars,
banners, and bundles. It ensures that the hardcoded shop data is properly seeded
into the database for production use.

Usage:
    python scripts/seed_shop_items.py
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[SEED_SHOP]")

# Bundle contents mapping
BUNDLE_CONTENTS = {
    "emotion_tracker-avatars-cat-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-cat-1",
            "emotion_tracker-static-avatar-cat-2",
            "emotion_tracker-static-avatar-cat-3",
            "emotion_tracker-static-avatar-cat-4",
            "emotion_tracker-static-avatar-cat-5",
            "emotion_tracker-static-avatar-cat-6",
            "emotion_tracker-static-avatar-cat-7",
            "emotion_tracker-static-avatar-cat-8",
            "emotion_tracker-static-avatar-cat-9",
            "emotion_tracker-static-avatar-cat-10",
            "emotion_tracker-static-avatar-cat-11",
            "emotion_tracker-static-avatar-cat-12",
            "emotion_tracker-static-avatar-cat-13",
            "emotion_tracker-static-avatar-cat-14",
            "emotion_tracker-static-avatar-cat-15",
            "emotion_tracker-static-avatar-cat-16",
            "emotion_tracker-static-avatar-cat-17",
            "emotion_tracker-static-avatar-cat-18",
            "emotion_tracker-static-avatar-cat-19",
            "emotion_tracker-static-avatar-cat-20",
        ]
    },
    "emotion_tracker-avatars-dog-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-dog-1",
            "emotion_tracker-static-avatar-dog-2",
            "emotion_tracker-static-avatar-dog-3",
            "emotion_tracker-static-avatar-dog-4",
            "emotion_tracker-static-avatar-dog-5",
            "emotion_tracker-static-avatar-dog-6",
            "emotion_tracker-static-avatar-dog-7",
            "emotion_tracker-static-avatar-dog-8",
            "emotion_tracker-static-avatar-dog-9",
            "emotion_tracker-static-avatar-dog-10",
            "emotion_tracker-static-avatar-dog-11",
            "emotion_tracker-static-avatar-dog-12",
            "emotion_tracker-static-avatar-dog-13",
            "emotion_tracker-static-avatar-dog-14",
            "emotion_tracker-static-avatar-dog-15",
            "emotion_tracker-static-avatar-dog-16",
            "emotion_tracker-static-avatar-dog-17",
        ]
    },
    "emotion_tracker-avatars-panda-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-panda-1",
            "emotion_tracker-static-avatar-panda-2",
            "emotion_tracker-static-avatar-panda-3",
            "emotion_tracker-static-avatar-panda-4",
            "emotion_tracker-static-avatar-panda-5",
            "emotion_tracker-static-avatar-panda-6",
            "emotion_tracker-static-avatar-panda-7",
            "emotion_tracker-static-avatar-panda-8",
            "emotion_tracker-static-avatar-panda-9",
            "emotion_tracker-static-avatar-panda-10",
            "emotion_tracker-static-avatar-panda-11",
            "emotion_tracker-static-avatar-panda-12",
        ]
    },
    "emotion_tracker-avatars-people-bundle": {
        "avatars": [
            "emotion_tracker-static-avatar-person-1",
            "emotion_tracker-static-avatar-person-2",
            "emotion_tracker-static-avatar-person-3",
            "emotion_tracker-static-avatar-person-4",
            "emotion_tracker-static-avatar-person-5",
            "emotion_tracker-static-avatar-person-6",
            "emotion_tracker-static-avatar-person-7",
            "emotion_tracker-static-avatar-person-8",
            "emotion_tracker-static-avatar-person-9",
            "emotion_tracker-static-avatar-person-10",
            "emotion_tracker-static-avatar-person-11",
            "emotion_tracker-static-avatar-person-12",
        ]
    },
    "emotion_tracker-themes-dark": {
        "themes": [
            "emotion_tracker-pacificBlueDark",
            "emotion_tracker-blushRoseDark",
            "emotion_tracker-cloudGrayDark",
            "emotion_tracker-sunsetPeachDark",
            "emotion_tracker-goldenYellowDark",
            "emotion_tracker-forestGreenDark",
            "emotion_tracker-midnightLavender",
            "emotion_tracker-crimsonRedDark",
            "emotion_tracker-deepPurpleDark",
            "emotion_tracker-royalOrangeDark",
        ]
    },
    "emotion_tracker-themes-light": {
        "themes": [
            "emotion_tracker-serenityGreen",
            "emotion_tracker-pacificBlue",
            "emotion_tracker-blushRose",
            "emotion_tracker-cloudGray",
            "emotion_tracker-sunsetPeach",
            "emotion_tracker-goldenYellow",
            "emotion_tracker-forestGreen",
            "emotion_tracker-midnightLavenderLight",
            "emotion_tracker-royalOrange",
            "emotion_tracker-crimsonRed",
            "emotion_tracker-deepPurple",
        ]
    },
}


def get_shop_items():
    """Get all shop items to seed."""
    shop_items = []

    # Themes
    shop_items.extend([
        {
            "item_id": "emotion_tracker-serenityGreen",
            "name": "Serenity Green Theme",
            "price": 250,
            "item_type": "theme",
            "category": "light",
            "featured": True,
            "description": "A calming green theme for peaceful productivity",
        },
        {
            "item_id": "emotion_tracker-pacificBlue",
            "name": "Pacific Blue Theme",
            "price": 250,
            "item_type": "theme",
            "category": "light",
            "description": "Ocean-inspired blue theme for clarity and focus",
        },
        {
            "item_id": "emotion_tracker-midnightLavender",
            "name": "Midnight Lavender Theme",
            "price": 250,
            "item_type": "theme",
            "category": "dark",
            "featured": True,
            "description": "Elegant dark theme with lavender accents",
        },
        {
            "item_id": "emotion_tracker-crimsonRedDark",
            "name": "Crimson Red Dark Theme",
            "price": 250,
            "item_type": "theme",
            "category": "dark",
            "description": "Bold dark theme with crimson highlights",
        },
    ])

    # Avatars
    shop_items.extend([
        {
            "item_id": "emotion_tracker-animated-avatar-playful_eye",
            "name": "Playful Eye Avatar",
            "price": 2500,
            "item_type": "avatar",
            "category": "animated",
            "featured": True,
            "new_arrival": True,
            "description": "Animated avatar with playful eye expressions",
        },
        {
            "item_id": "emotion_tracker-animated-avatar-floating_brain",
            "name": "Floating Brain Avatar",
            "price": 5000,
            "item_type": "avatar",
            "category": "animated",
            "featured": True,
            "description": "Premium animated floating brain avatar",
        },
        {
            "item_id": "emotion_tracker-static-avatar-cat-1",
            "name": "Cat Avatar 1",
            "price": 100,
            "item_type": "avatar",
            "category": "cats",
            "description": "Cute static cat avatar",
        },
        {
            "item_id": "emotion_tracker-static-avatar-dog-1",
            "name": "Dog Avatar 1",
            "price": 100,
            "item_type": "avatar",
            "category": "dogs",
            "description": "Friendly static dog avatar",
        },
    ])

    # Banners
    shop_items.extend([
        {
            "item_id": "emotion_tracker-static-banner-earth-1",
            "name": "Earth Banner",
            "price": 100,
            "item_type": "banner",
            "category": "nature",
            "description": "Beautiful Earth landscape banner",
        }
    ])

    # Bundles
    shop_items.extend([
        {
            "item_id": "emotion_tracker-avatars-cat-bundle",
            "name": "Cat Lovers Pack",
            "price": 2000,
            "item_type": "bundle",
            "category": "avatars",
            "featured": True,
            "description": "Complete collection of cat avatars",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-cat-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-themes-dark",
            "name": "Dark Theme Pack",
            "price": 2500,
            "item_type": "bundle",
            "category": "themes",
            "featured": True,
            "description": "Collection of premium dark themes",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-themes-dark", {}),
        },
        {
            "item_id": "emotion_tracker-avatars-dog-bundle",
            "name": "Dog Lovers Pack",
            "price": 2000,
            "item_type": "bundle",
            "category": "avatars",
            "featured": True,
            "description": "Complete collection of dog avatars",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-dog-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-avatars-panda-bundle",
            "name": "Panda Lovers Pack",
            "price": 1500,
            "item_type": "bundle",
            "category": "avatars",
            "description": "Adorable panda avatar collection",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-panda-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-avatars-people-bundle",
            "name": "People Pack",
            "price": 2000,
            "item_type": "bundle",
            "category": "avatars",
            "description": "Human character avatar collection",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-avatars-people-bundle", {}),
        },
        {
            "item_id": "emotion_tracker-themes-light",
            "name": "Light Theme Pack",
            "price": 2500,
            "item_type": "bundle",
            "category": "themes",
            "featured": True,
            "description": "Collection of premium light themes",
            "bundle_contents": BUNDLE_CONTENTS.get("emotion_tracker-themes-light", {}),
        },
    ])

    return shop_items


async def seed_shop_items():
    """Seed shop items into the database."""
    try:
        logger.info("Starting shop items seeding...")
        
        # Initialize database connection
        await db_manager.initialize()
        
        shop_items_collection = db_manager.get_collection("shop_items")
        
        # Get all shop items
        items = get_shop_items()
        
        logger.info(f"Seeding {len(items)} shop items...")
        
        # Upsert each item (update if exists, insert if not)
        for item in items:
            await shop_items_collection.update_one(
                {"item_id": item["item_id"]},
                {"$set": item},
                upsert=True
            )
            logger.debug(f"Seeded: {item['item_id']} - {item['name']}")
        
        logger.info(f"✅ Successfully seeded {len(items)} shop items!")
        
        # Verify seeding
        count = await shop_items_collection.count_documents({})
        logger.info(f"Total shop items in database: {count}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to seed shop items: {e}")
        return False
    finally:
        await db_manager.close()


if __name__ == "__main__":
    success = asyncio.run(seed_shop_items())
    sys.exit(0 if success else 1)
