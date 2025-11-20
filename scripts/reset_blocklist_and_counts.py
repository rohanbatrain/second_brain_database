import sys
sys.path.insert(0, 'src')
"""
Script to unblock all users and reset all password reset abuse counts.
Removes all entries from blocklist and resets abuse counters in Redis and MongoDB.
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import aioredis
from second_brain_database.config import settings

MONGO_URI = settings.MONGODB_URL
REDIS_URI = settings.REDIS_URL
BLOCKLIST_KEY = getattr(settings, "BLOCKLIST_KEY", "abuse:reset:blocklist")
ABUSE_COUNT_KEY = getattr(settings, "ABUSE_COUNT_KEY", "abuse:reset:count")

async def reset_blocklist_and_counts():
    # Connect to Redis
    redis = aioredis.from_url(REDIS_URI)
    # Remove all blocklist entries
    await redis.delete(BLOCKLIST_KEY)
    print(f"Cleared Redis blocklist: {BLOCKLIST_KEY}")
    # Remove all abuse count entries
    await redis.delete(ABUSE_COUNT_KEY)
    print(f"Cleared Redis abuse counts: {ABUSE_COUNT_KEY}")
    redis.close()

    # Connect to MongoDB
    mongo = AsyncIOMotorClient(MONGO_URI)
    db = mongo[settings.MONGODB_DATABASE]
    users = db["users"]
    # Remove all reset_blocklist and abuse counts from user docs
    result = await users.update_many({}, {"$set": {"reset_blocklist": [], "reset_abuse_count": 0}})
    print(f"Reset blocklist and abuse counts for {result.modified_count} MongoDB users.")
    mongo.close()

if __name__ == "__main__":
    asyncio.run(reset_blocklist_and_counts())
