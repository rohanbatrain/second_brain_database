"""
Admin service functions for password reset abuse management, whitelist/blocklist, and abuse event review.
"""
# Import all admin service logic from the old auth/service.py here
# (You will need to update imports in routes and service files after migration)

from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.database import db_manager
from second_brain_database.routes.admin.models import AbuseEvent

# --- Whitelist/Blocklist Management ---
async def admin_add_whitelist_pair(email: str, ip: str):
    users = db_manager.get_collection("users")
    await users.update_one({"email": email}, {"$addToSet": {"reset_whitelist": ip}})
    redis_conn = await redis_manager.get_redis()
    return await redis_conn.sadd("abuse:reset:whitelist", f"{email}:{ip}")

async def admin_remove_whitelist_pair(email: str, ip: str):
    users = db_manager.get_collection("users")
    await users.update_one({"email": email}, {"$pull": {"reset_whitelist": ip}})
    redis_conn = await redis_manager.get_redis()
    return await redis_conn.srem("abuse:reset:whitelist", f"{email}:{ip}")

async def admin_list_whitelist_pairs():
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:whitelist")
    return {"whitelist": [m.decode() if hasattr(m, 'decode') else m for m in members]}

async def admin_add_blocklist_pair(email: str, ip: str):
    users = db_manager.get_collection("users")
    await users.update_one({"email": email}, {"$addToSet": {"reset_blocklist": ip}})
    redis_conn = await redis_manager.get_redis()
    return await redis_conn.sadd("abuse:reset:blocklist", f"{email}:{ip}")

async def admin_remove_blocklist_pair(email: str, ip: str):
    users = db_manager.get_collection("users")
    await users.update_one({"email": email}, {"$pull": {"reset_blocklist": ip}})
    redis_conn = await redis_manager.get_redis()
    return await redis_conn.srem("abuse:reset:blocklist", f"{email}:{ip}")

async def admin_list_blocklist_pairs():
    redis_conn = await redis_manager.get_redis()
    members = await redis_conn.smembers("abuse:reset:blocklist")
    return {"blocklist": [m.decode() if hasattr(m, 'decode') else m for m in members]}

# --- Abuse Event Review ---
async def admin_list_abuse_events(email=None, event_type=None, resolved=None, limit=100):
    query = {}
    if email:
        query["email"] = email
    if event_type:
        query["event_type"] = event_type
    if resolved is not None:
        query["resolved"] = resolved
    events = db_manager.get_collection("reset_abuse_events")
    cursor = events.find(query).sort("timestamp", -1).limit(limit)
    return [AbuseEvent(**doc) async for doc in cursor]

async def admin_resolve_abuse_event(event_id: str, notes: str = None):
    from bson import ObjectId
    events = db_manager.get_collection("reset_abuse_events")
    result = await events.update_one({"_id": ObjectId(event_id)}, {"$set": {"resolved": True, "resolution_notes": notes}})
    return result.modified_count == 1

# --- Legacy direct pair management (for admin UI compatibility) ---
async def whitelist_reset_pair(email: str, ip: str):
    users = db_manager.get_collection("users")
    await users.update_one({"email": email}, {"$addToSet": {"reset_whitelist": ip}})
    redis_conn = await redis_manager.get_redis()
    await redis_conn.sadd("abuse:reset:whitelist", f"{email}:{ip}")

async def block_reset_pair(email: str, ip: str):
    users = db_manager.get_collection("users")
    await users.update_one({"email": email}, {"$addToSet": {"reset_blocklist": ip}})
    redis_conn = await redis_manager.get_redis()
    await redis_conn.sadd("abuse:reset:blocklist", f"{email}:{ip}")
