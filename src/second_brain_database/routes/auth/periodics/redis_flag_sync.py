"""
Periodic sync of password reset blocklist, whitelist, and abuse flags from MongoDB user documents to Redis.

- Ensures Redis in-memory sets reflect the persistent state in MongoDB for fast abuse checks.
- Allows you to update block/whitelist/abuse_flags directly in MongoDB and have them take effect in Redis automatically.
- Intended to be run as a background task (e.g., on startup or via a scheduler).
- Does NOT perform any cleanup or expiry logic—only syncs DB state to Redis.

Fields:
- reset_blocklist: List of IPs blocked for password reset for this user (in MongoDB user doc)
- reset_whitelist: List of IPs whitelisted for password reset for this user (in MongoDB user doc)
- abuse_flags: Dict of IP -> metadata for abuse tracking (in MongoDB user doc)

Redis keys:
- abuse:reset:blocklist (set of email:ip)
- abuse:reset:whitelist (set of email:ip)
- abuse:reset:flagged:email:ip (JSON, expires in 15 min)
"""
import asyncio
import json
import logging
from second_brain_database.database import db_manager

logger = logging.getLogger(__name__)

async def sync_password_reset_flags_to_redis():
    """
    Periodically syncs password reset blocklist, whitelist, and abuse_flags from MongoDB to Redis.
    Should be run in a background task (interval configurable by you).
    """
    from second_brain_database.managers.redis_manager import redis_manager
    users = db_manager.get_collection("users")
    redis_conn = await redis_manager.get_redis()
    async for user in users.find({
        "$or": [
            {"reset_blocklist": {"$exists": True, "$ne": []}},
            {"reset_whitelist": {"$exists": True, "$ne": []}},
            {"abuse_flags": {"$exists": True, "$ne": {}}}
        ]
    }):
        email = user.get("email")
        # Sync blocklist
        for ip in user.get("reset_blocklist", []):
            await redis_conn.sadd("abuse:reset:blocklist", f"{email}:{ip}")
        # Sync whitelist
        for ip in user.get("reset_whitelist", []):
            await redis_conn.sadd("abuse:reset:whitelist", f"{email}:{ip}")
        # Sync abuse_flags (optional: store as JSON for future use)
        for ip, meta in user.get("abuse_flags", {}).items():
            await redis_conn.set(f"abuse:reset:flagged:{email}:{ip}", json.dumps(meta), ex=900)
    logger.info("Password reset blocklist/whitelist/abuse_flags sync to Redis complete.")

async def periodic_password_reset_flag_sync(interval=60):
    """
    Run sync_password_reset_flags_to_redis every `interval` seconds.
    """
    while True:
        try:
            await sync_password_reset_flags_to_redis()
        except Exception as e:
            logger.error(f"Error syncing password reset flags to Redis: {e}")
        await asyncio.sleep(interval)
