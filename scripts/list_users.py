#!/usr/bin/env python3
"""List all users in the database."""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient


async def list_users():
    """List all users."""
    client = AsyncIOMotorClient("mongodb://localhost:27017")
    db = client["second_brain_database"]
    
    try:
        users = await db.users.find(
            {},
            {"email": 1, "username": 1, "permissions": 1}
        ).to_list(100)
        
        print(f"Found {len(users)} users:\n")
        for user in users:
            email = user.get("email", "N/A")
            username = user.get("username", "N/A")
            permissions = user.get("permissions", [])
            print(f"  Email: {email}")
            print(f"  Username: {username}")
            print(f"  Permissions: {permissions}")
            print()
            
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(list_users())
