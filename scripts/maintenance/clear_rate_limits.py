#!/usr/bin/env python3
"""
Clear rate limits from Redis (Development Only)

This script clears all rate limit entries from Redis to allow
testing admin actions without waiting for the rate limit window to expire.

WARNING: Only use in development! Never run in production!
"""

import asyncio
import redis.asyncio as redis
from src.second_brain_database.config import settings

async def clear_rate_limits():
    """Clear all rate limit entries from Redis."""

    # Connect to Redis
    redis_url = settings.REDIS_URL or f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    print(f"🔌 Connecting to Redis: {redis_url}")

    client = redis.from_url(redis_url, decode_responses=True)

    try:
        # Find all rate limit keys
        patterns = [
            "rate_limit:*",
            "admin_action:*",
            "family:*:rate_limit:*",
            "*rate_limit*"
        ]

        total_deleted = 0

        for pattern in patterns:
            print(f"\n🔍 Searching for pattern: {pattern}")
            keys = []
            async for key in client.scan_iter(match=pattern):
                keys.append(key)

            if keys:
                print(f"   Found {len(keys)} keys")
                for key in keys:
                    print(f"   - {key}")

                # Delete all found keys
                deleted = await client.delete(*keys)
                print(f"   ✅ Deleted {deleted} keys")
                total_deleted += deleted
            else:
                print(f"   No keys found")

        print(f"\n✨ Total rate limit entries cleared: {total_deleted}")

        if total_deleted == 0:
            print("\n💡 No rate limit entries found. They may have already expired or")
            print("   rate limiting might be using a different storage mechanism.")
        else:
            print("\n✅ All rate limits cleared! You can now test admin actions again.")

    except Exception as e:
        print(f"\n❌ Error clearing rate limits: {e}")
        print(f"\n💡 Make sure Redis is running and accessible at: {redis_url}")

    finally:
        await client.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🧹 Rate Limit Cleaner - Development Tool")
    print("=" * 60)
    print("\n⚠️  WARNING: This should only be used in development!")
    print("    Never run this in production environments.\n")

    asyncio.run(clear_rate_limits())
