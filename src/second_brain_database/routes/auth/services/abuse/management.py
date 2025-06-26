from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
import json
from datetime import datetime

WHITELIST_KEY = getattr(settings, "WHITELIST_KEY", "abuse:reset:whitelist")
BLOCKLIST_KEY = getattr(settings, "BLOCKLIST_KEY", "abuse:reset:blocklist")

logger = get_logger()

async def whitelist_reset_pair(email: str, ip: str):
    redis_conn = await redis_manager.get_redis()
    await redis_conn.sadd(WHITELIST_KEY, f"{email}:{ip}")

async def block_reset_pair(email: str, ip: str):
    redis_conn = await redis_manager.get_redis()
    await redis_conn.sadd(BLOCKLIST_KEY, f"{email}:{ip}")
async def admin_add_whitelist_pair(email: str, ip: str) -> bool:
    """
    Add an (email, ip) pair to the password reset whitelist (Redis, fast path).
    Returns True if added, False if already present.
    """
    redis_conn = await redis_manager.get_redis()
    result = await redis_conn.sadd(WHITELIST_KEY, f"{email}:{ip}")
    return bool(result)

async def admin_remove_whitelist_pair(email: str, ip: str) -> bool:
    """
    Remove an (email, ip) pair from the password reset whitelist (Redis).
    Returns True if removed, False if not present.
    """
    redis_conn = await redis_manager.get_redis()
    result = await redis_conn.srem(WHITELIST_KEY, f"{email}:{ip}")
    return bool(result)

async def admin_list_whitelist_pairs() -> list:
    """
    List all (email, ip) pairs currently in the password reset whitelist (Redis).
    Returns a list of dicts: [{"email": ..., "ip": ...}, ...]
    """
    redis_conn = await redis_manager.get_redis()
    pairs = await redis_conn.smembers(WHITELIST_KEY)
    result = []
    for pair in pairs:
        try:
            email, ip = pair.split(":", 1)
            result.append({"email": email, "ip": ip})
        except Exception:
            continue
    return result

async def admin_add_blocklist_pair(email: str, ip: str) -> bool:
    """
    Add an (email, ip) pair to the password reset blocklist (Redis, fast path).
    Returns True if added, False if already present.
    """
    redis_conn = await redis_manager.get_redis()
    result = await redis_conn.sadd(BLOCKLIST_KEY, f"{email}:{ip}")
    return bool(result)

async def admin_remove_blocklist_pair(email: str, ip: str) -> bool:
    """
    Remove an (email, ip) pair from the password reset blocklist (Redis).
    Returns True if removed, False if not present.
    """
    redis_conn = await redis_manager.get_redis()
    result = await redis_conn.srem(BLOCKLIST_KEY, f"{email}:{ip}")
    return bool(result)

async def admin_list_blocklist_pairs() -> list:
    """
    List all (email, ip) pairs currently in the password reset blocklist (Redis).
    Returns a list of dicts: [{"email": ..., "ip": ...}, ...]
    """
    redis_conn = await redis_manager.get_redis()
    pairs = await redis_conn.smembers(BLOCKLIST_KEY)
    result = []
    for pair in pairs:
        try:
            email, ip = pair.split(":", 1)
            result.append({"email": email, "ip": ip})
        except Exception:
            continue
    return result

# --- Abuse Event Review (MongoDB, Persistent) ---


async def reconcile_blocklist_whitelist() -> None:
    """
    Make MongoDB the source of truth for blocklist/whitelist reconciliation.
    - Redis will be updated to exactly match MongoDB.
    - Any (email, ip) pair not present in MongoDB will be removed from Redis.
    - Deleting from MongoDB will always remove from Redis on the next sync.
    """
    from second_brain_database.managers.redis_manager import redis_manager
    redis_conn = await redis_manager.get_redis()
    users = db_manager.get_collection("users")
    changes = {"mongo_to_redis": 0, "redis_removed": 0}
    for list_type in ["blocklist", "whitelist"]:
        redis_key = f"abuse:reset:{list_type}"
        # 1. Build set of all (email, ip) pairs in MongoDB for this list_type
        mongo_pairs = set()
        async for user in users.find({f"reset_{list_type}": {"$exists": True, "$ne": []}}):
            email = user.get("email")
            for ip in user.get(f"reset_{list_type}", []):
                mongo_pairs.add(f"{email}:{ip}")
        # 2. Get all pairs in Redis
        redis_members = await redis_conn.smembers(redis_key)
        redis_pairs = set(m.decode() if hasattr(m, 'decode') else m for m in redis_members)
        # 3. Remove from Redis any pair not in MongoDB
        for pair in redis_pairs - mongo_pairs:
            await redis_conn.srem(redis_key, pair)
            changes["redis_removed"] += 1
        # 4. Add to Redis any pair in MongoDB not in Redis
        for pair in mongo_pairs - redis_pairs:
            await redis_conn.sadd(redis_key, pair)
            changes["mongo_to_redis"] += 1
    logger.info(json.dumps({"event": "blocklist_whitelist_reconcile", "changes": changes, "ts": datetime.utcnow().isoformat()}))
    logger.info("Blocklist/whitelist reconciliation (MongoDB → Redis) complete.")

#

async def is_pair_whitelisted(email: str, ip: str) -> bool:
    # WARNING: Whitelisting only exempts from abuse/CAPTCHA escalation, NOT from rate limiting.
    # Rate limiting is always enforced regardless of whitelist status to prevent DDoS.
    redis_conn = await redis_manager.get_redis()
    return await redis_conn.sismember(WHITELIST_KEY, f"{email}:{ip}")

async def is_pair_blocked(email: str, ip: str) -> bool:
    redis_conn = await redis_manager.get_redis()
    return await redis_conn.sismember(BLOCKLIST_KEY, f"{email}:{ip}")
