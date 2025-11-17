#!/usr/bin/env python3
"""
Fix IPAM owner fields to use username instead of user_id.

This script updates all existing regions and hosts that have user_id in the owner field
to use the username instead for better readability.

Usage:
    uv run python scripts/fix_ipam_owner_fields.py
"""

import asyncio
from bson import ObjectId
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAM Owner Fix]")


async def fix_owner_fields():
    """Fix owner fields in regions and hosts to use username instead of user_id."""
    try:
        await db_manager.connect()
        logger.info("Connected to database")
        
        users_collection = db_manager.get_collection("users")
        regions_collection = db_manager.get_collection("ipam_regions")
        hosts_collection = db_manager.get_collection("ipam_hosts")
        
        # Build a mapping of user_id -> username
        logger.info("Building user_id to username mapping...")
        user_mapping = {}
        async for user in users_collection.find({}, {"_id": 1, "username": 1}):
            user_id = str(user["_id"])
            username = user.get("username", "Unknown")
            user_mapping[user_id] = username
        
        logger.info(f"Found {len(user_mapping)} users")
        
        # Fix regions
        logger.info("Fixing region owner fields...")
        regions_fixed = 0
        regions_skipped = 0
        
        async for region in regions_collection.find({}):
            owner = region.get("owner")
            
            # Check if owner looks like a MongoDB ObjectId (24 hex characters)
            if owner and len(owner) == 24 and all(c in '0123456789abcdef' for c in owner.lower()):
                # This is a user_id, replace with username
                username = user_mapping.get(owner, "Unknown")
                
                await regions_collection.update_one(
                    {"_id": region["_id"]},
                    {"$set": {"owner": username}}
                )
                
                logger.info(
                    f"Fixed region {region.get('region_name', 'Unknown')}: "
                    f"{owner[:8]}... -> {username}"
                )
                regions_fixed += 1
            else:
                regions_skipped += 1
        
        logger.info(f"Regions fixed: {regions_fixed}, skipped: {regions_skipped}")
        
        # Fix hosts
        logger.info("Fixing host owner fields...")
        hosts_fixed = 0
        hosts_skipped = 0
        
        async for host in hosts_collection.find({}):
            owner = host.get("owner")
            
            # Check if owner looks like a MongoDB ObjectId
            if owner and len(owner) == 24 and all(c in '0123456789abcdef' for c in owner.lower()):
                # This is a user_id, replace with username
                username = user_mapping.get(owner, "Unknown")
                
                await hosts_collection.update_one(
                    {"_id": host["_id"]},
                    {"$set": {"owner": username}}
                )
                
                logger.info(
                    f"Fixed host {host.get('hostname', 'Unknown')}: "
                    f"{owner[:8]}... -> {username}"
                )
                hosts_fixed += 1
            else:
                hosts_skipped += 1
        
        logger.info(f"Hosts fixed: {hosts_fixed}, skipped: {hosts_skipped}")
        
        # Summary
        logger.info("=" * 60)
        logger.info("IPAM Owner Fields Fix Complete!")
        logger.info(f"Total regions fixed: {regions_fixed}")
        logger.info(f"Total hosts fixed: {hosts_fixed}")
        logger.info(f"Total items fixed: {regions_fixed + hosts_fixed}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error fixing owner fields: {e}", exc_info=True)
        raise
    finally:
        await db_manager.disconnect()
        logger.info("Disconnected from database")


if __name__ == "__main__":
    asyncio.run(fix_owner_fields())
