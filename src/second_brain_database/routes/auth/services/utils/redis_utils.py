import json
import secrets
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.database import db_manager
from second_brain_database.config import settings

BACKUP_CODES_REDIS_PREFIX = "2fa:backup_codes:"
BACKUP_CODES_PENDING_TIME = getattr(settings, "BACKUP_CODES_PENDING_TIME", 600)
ABUSE_ACTION_TOKEN_EXPIRY = getattr(settings, "ABUSE_ACTION_TOKEN_EXPIRY", 1800)

async def redis_check_username(username: str) -> bool:
    redis_conn = await redis_manager.get_redis()
    key = f"username:exists:{username.lower()}"
    cached = await redis_conn.get(key)
    if cached is not None:
        return cached == "1"
    # Fallback to DB
    user = await db_manager.get_collection("users").find_one({"username": username.lower()})
    exists = user is not None
    await redis_conn.set(key, "1" if exists else "0", ex=3600)
    return exists

async def redis_incr_username_demand(username: str):
    redis_conn = await redis_manager.get_redis()
    key = f"username:demand:{username.lower()}"
    await redis_conn.incr(key)
    await redis_conn.expire(key, 86400)  # 1 day expiry

async def redis_get_top_demanded_usernames(top_n=10):
    redis_conn = await redis_manager.get_redis()
    pattern = "username:demand:*"
    keys = await redis_conn.keys(pattern)
    result = []
    for key in keys:
        count = await redis_conn.get(key)
        uname = key.split(":", 2)[-1]
        result.append((uname, int(count)))
    result.sort(key=lambda x: x[1], reverse=True)
    return result[:top_n]


async def store_backup_codes_temp(username: str, codes: list):
    redis_conn = await redis_manager.get_redis()
    key = f"{BACKUP_CODES_REDIS_PREFIX}{username}"
    await redis_conn.set(key, json.dumps(codes), ex=BACKUP_CODES_PENDING_TIME)

async def get_backup_codes_temp(username: str):
    redis_conn = await redis_manager.get_redis()
    key = f"{BACKUP_CODES_REDIS_PREFIX}{username}"
    val = await redis_conn.get(key)
    if val:
        return json.loads(val)
    return None

async def delete_backup_codes_temp(username: str):
    redis_conn = await redis_manager.get_redis()
    key = f"{BACKUP_CODES_REDIS_PREFIX}{username}"
    await redis_conn.delete(key)

async def generate_abuse_action_token(email: str, ip: str, action: str, expiry_seconds: int = ABUSE_ACTION_TOKEN_EXPIRY) -> str:
    """
    Generate a secure, single-use, time-limited token for whitelist/block actions.
    Store in Redis with expiry.
    """
    redis_conn = await redis_manager.get_redis()
    token = secrets.token_urlsafe(32)
    key = f"abuse:reset:action:{token}"
    await redis_conn.set(key, json.dumps({"email": email, "ip": ip, "action": action}), ex=expiry_seconds)
    return token

async def consume_abuse_action_token(token: str, expected_action: str) -> tuple:
    """
    Validate and consume a single-use abuse action token. Returns (email, ip) if valid, else (None, None).
    """
    redis_conn = await redis_manager.get_redis()
    key = f"abuse:reset:action:{token}"
    val = await redis_conn.get(key)
    if not val:
        return None, None
    try:
        data = json.loads(val)
        if data.get("action") != expected_action:
            return None, None
        email = data.get("email")
        ip = data.get("ip")
        await redis_conn.delete(key)
        return email, ip
    except Exception:
        return None, None
