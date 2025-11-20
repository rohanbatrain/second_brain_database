#!/usr/bin/env python3
"""
Grant IPAM permissions to a user.

Usage:
    python scripts/grant_ipam_permissions.py <email>
"""

import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# IPAM permissions
IPAM_PERMISSIONS = [
    "ipam:read",
    "ipam:allocate",
    "ipam:update",
    "ipam:release",
    "ipam:admin",
]


async def grant_ipam_permissions(email: str):
    """Grant all IPAM permissions to a user."""
    # Connect to MongoDB
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["second_brain_database"]
    
    try:
        # Find user by email
        user = await db.users.find_one({"email": email})
        
        if not user:
            print(f"❌ User not found: {email}")
            return False
        
        user_id = user["_id"]
        current_permissions = user.get("permissions", [])
        
        print(f"✓ Found user: {email}")
        print(f"  User ID: {user_id}")
        print(f"  Current permissions: {current_permissions}")
        
        # Add IPAM permissions
        new_permissions = list(set(current_permissions + IPAM_PERMISSIONS))
        
        # Update user
        result = await db.users.update_one(
            {"_id": user_id},
            {"$set": {"permissions": new_permissions}}
        )
        
        if result.modified_count > 0:
            print(f"\n✅ Successfully granted IPAM permissions to {email}")
            print(f"  New permissions: {new_permissions}")
            return True
        else:
            print(f"\n⚠️  No changes made (user may already have these permissions)")
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    finally:
        client.close()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/grant_ipam_permissions.py <email>")
        print("\nExample:")
        print("  python scripts/grant_ipam_permissions.py test@rohanbatra.in")
        sys.exit(1)
    
    email = sys.argv[1]
    success = await grant_ipam_permissions(email)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
