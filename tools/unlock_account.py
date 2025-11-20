#!/usr/bin/env python3
"""
Script to unlock a user account by resetting failed login attempts.
Usage: python unlock_account.py <username_or_email>
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[Unlock Account]")

async def unlock_account(identifier: str):
    """Reset failed login attempts for a user account."""
    try:
        # Initialize database connection
        await db_manager.initialize()

        # Find user by username or email
        user = await db_manager.get_collection("users").find_one({"username": identifier})
        if not user:
            user = await db_manager.get_collection("users").find_one({"email": identifier})

        if not user:
            logger.error(f"User not found: {identifier}")
            return False

        username = user.get("username", "unknown")
        email = user.get("email", "unknown")
        failed_attempts = user.get("failed_login_attempts", 0)

        logger.info(f"Found user: {username} ({email}), current failed attempts: {failed_attempts}")

        # Reset failed login attempts
        result = await db_manager.get_collection("users").update_one(
            {"_id": user["_id"]},
            {"$unset": {"failed_login_attempts": ""}}
        )

        if result.modified_count > 0:
            logger.info(f"Successfully unlocked account for user: {username}")
            return True
        else:
            logger.warning(f"No changes made for user: {username}")
            return False

    except Exception as e:
        logger.error(f"Error unlocking account: {e}", exc_info=True)
        return False
    finally:
        await db_manager.close()

async def main():
    if len(sys.argv) != 2:
        print("Usage: python unlock_account.py <username_or_email>")
        sys.exit(1)

    identifier = sys.argv[1]
    print(f"Unlocking account for: {identifier}")

    success = await unlock_account(identifier)
    if success:
        print("Account unlocked successfully!")
    else:
        print("Failed to unlock account.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())