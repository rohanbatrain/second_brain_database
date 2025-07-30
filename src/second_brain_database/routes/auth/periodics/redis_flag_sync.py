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
from typing import Any, Dict, Optional

import pymongo.errors
import redis.exceptions

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.auth.services.abuse.management import reconcile_blocklist_whitelist

# Import exceptions for more specific error handling

# Attach exceptions to managers for easier reference in code
db_manager.pymongo_errors = pymongo.errors
redis_manager.redis_exceptions = redis.exceptions

logger = get_logger(prefix="[Auth Periodic Redis]")

# Constants
REDIS_ABUSE_FLAG_EXPIRY: int = 900  # 15 minutes in seconds
USERS_COLLECTION: str = settings.USERS_COLLECTION
BLOCKLIST_KEY: str = settings.BLOCKLIST_KEY
WHITELIST_KEY: str = settings.WHITELIST_KEY
ABUSE_FLAG_PREFIX: str = settings.ABUSE_FLAG_PREFIX


async def sync_password_reset_flags_to_redis() -> None:
    """
    Sync password reset blocklist, whitelist, and abuse_flags from MongoDB to Redis.
    Should be run in a background task (interval configurable by you).
    Logs all actions and errors.
    Side-effects: Updates Redis sets and keys.
    """
    try:
        users = db_manager.get_collection(USERS_COLLECTION)
        redis_conn = await redis_manager.get_redis()
        query: Dict[str, Any] = {
            "$or": [
                {"reset_blocklist": {"$exists": True, "$ne": []}},
                {"reset_whitelist": {"$exists": True, "$ne": []}},
                {"abuse_flags": {"$exists": True, "$ne": {}}},
            ]
        }
        async for user in users.find(query):
            email: Optional[str] = user.get("email")
            # Sync blocklist
            for ip in user.get("reset_blocklist", []):
                try:
                    await redis_conn.sadd(BLOCKLIST_KEY, f"{email}:{ip}")
                    logger.debug("Added to blocklist: %s:%s", email, ip)
                except redis_manager.redis_exceptions.RedisError:
                    logger.error("Failed to add to blocklist: %s:%s", email, ip, exc_info=True)
            # Sync whitelist
            for ip in user.get("reset_whitelist", []):
                try:
                    await redis_conn.sadd(WHITELIST_KEY, f"{email}:{ip}")
                    logger.debug("Added to whitelist: %s:%s", email, ip)
                except redis_manager.redis_exceptions.RedisError:
                    logger.error("Failed to add to whitelist: %s:%s", email, ip, exc_info=True)
            # Sync abuse_flags
            for ip, meta in user.get("abuse_flags", {}).items():
                try:
                    redis_key = f"{ABUSE_FLAG_PREFIX}:{email}:{ip}"
                    await redis_conn.set(redis_key, json.dumps(meta), ex=REDIS_ABUSE_FLAG_EXPIRY)
                    logger.debug("Set abuse flag: %s", redis_key)
                except redis_manager.redis_exceptions.RedisError:
                    logger.error("Failed to set abuse flag: %s", redis_key, exc_info=True)
        logger.info("Password reset flags sync to Redis complete.")
    except db_manager.pymongo_errors.PyMongoError as exc:
        logger.error("Error during password reset flag sync: %s", exc, exc_info=True)
    except (TypeError, ValueError, KeyError) as exc:
        logger.error("Error during password reset flag sync: %s", exc, exc_info=True)


async def periodic_password_reset_flag_sync(interval: Optional[int] = None) -> None:
    """
    Run sync_password_reset_flags_to_redis every `interval` seconds (from config if not provided).
    Args:
        interval: How often to sync, in seconds. Defaults to settings.REDIS_FLAG_SYNC_INTERVAL.
    Side-effects: Runs forever as a background task.
    """
    if interval is None:
        interval = settings.REDIS_FLAG_SYNC_INTERVAL
    logger.info("Starting periodic password reset flag sync (interval=%ds)", interval)
    while True:
        try:
            await sync_password_reset_flags_to_redis()
        except (
            redis_manager.redis_exceptions.RedisError,
            db_manager.pymongo_errors.PyMongoError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:
            logger.error("Failed to sync password reset flags to Redis: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


async def periodic_blocklist_whitelist_reconcile(interval: Optional[int] = None) -> None:
    """
    Periodically reconcile blocklist/whitelist between MongoDB and Redis (two-way sync).
    Args:
        interval: How often to run the reconciliation, in seconds. Defaults to settings.BLOCKLIST_RECONCILE_INTERVAL.
    Side-effects: Runs forever as a background task.
    """
    if interval is None:
        interval = settings.BLOCKLIST_RECONCILE_INTERVAL
    logger.info("Starting periodic blocklist/whitelist reconciliation (interval=%ds)", interval)
    while True:
        try:
            await reconcile_blocklist_whitelist()
        except (
            redis_manager.redis_exceptions.RedisError,
            db_manager.pymongo_errors.PyMongoError,
            TypeError,
            ValueError,
            KeyError,
        ) as exc:
            logger.error("Blocklist/whitelist reconciliation error: %s", exc, exc_info=True)
        await asyncio.sleep(interval)
