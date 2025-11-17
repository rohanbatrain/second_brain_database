#!/usr/bin/env python3
"""Grant IPAM permissions to a user by ID."""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

IPAM_PERMISSIONS = [
    "ipam:read",
    "ipam:allocate",
    "ipam:update",
    "ipam:release",
    "ipam:admin",
]


async def grant_by_id(user_id_str: str):
    """Grant IPAM permissions by user ID."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["second_brain_database"]
    
    try:
        user_id = ObjectId(user_id_str)
        user = await db.users.find_one({"_id": user_id})
        
        if not user:
            print(f"❌ User not found: {user_id_str}")
            return False
        
        current_permissions = user.get("permissions", [])
        new_permissions = list(set(current_permissions + IPAM_PERMISSIONS))
        
        await db.users.update_one(
            {"_id": user_id},
            {"$set": {"permissions": new_permissions}}
        )
        
        print(f"✅ Granted IPAM permissions to user {user_id_str}")
        print(f"  Email: {user.get('email')}")
        print(f"  Permissions: {new_permissions}")
        return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python scripts/grant_ipam_by_id.py <user_id>")
        sys.exit(1)
    
    asyncio.run(grant_by_id(sys.argv[1]))
