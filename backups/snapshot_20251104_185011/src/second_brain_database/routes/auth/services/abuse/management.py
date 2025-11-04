"""
Management utilities for password reset abuse whitelists and blocklists.

This module provides async functions to manage (email, ip) pairs in Redis-based
whitelists and blocklists, as well as reconciliation with MongoDB for admin review.
"""

from datetime import datetime
import json
from typing import Dict, List

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.utils.logging_utils import (
    DatabaseLogger,
    SecurityLogger,
    log_database_operation,
    log_error_with_context,
    log_performance,
    log_security_event,
)

WHITELIST_KEY: str = getattr(settings, "WHITELIST_KEY", "abuse:reset:whitelist")
BLOCKLIST_KEY: str = getattr(settings, "BLOCKLIST_KEY", "abuse:reset:blocklist")

logger = get_logger(prefix="[Auth Service Abuse Management]")
security_logger = SecurityLogger(prefix="[ABUSE-MANAGEMENT-SECURITY]")
db_logger = DatabaseLogger(prefix="[ABUSE-MANAGEMENT-DB]")


@log_performance("whitelist_reset_pair")
async def whitelist_reset_pair(email: str, ip: str) -> None:
    """
    Add an (email, ip) pair to the password reset whitelist in Redis.
    Side Effects: Writes to Redis.
    """
    logger.info("Adding pair to whitelist: %s, %s", email, ip)

    try:
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.sadd(WHITELIST_KEY, f"{email}:{ip}")

        log_security_event(
            event_type="abuse_pair_whitelisted",
            user_id=email,
            ip_address=ip,
            success=True,
            details={"action": "whitelist_add", "pair": f"{email}:{ip}", "was_new": bool(result)},
        )

        logger.info("Successfully whitelisted pair: %s, %s (new: %s)", email, ip, bool(result))

    except (TypeError, ValueError, RuntimeError, AttributeError) as e:
        logger.error("Failed to whitelist pair %s, %s: %s", email, ip, e, exc_info=True)
        log_error_with_context(
            e, context={"email": email, "ip": ip, "action": "whitelist"}, operation="whitelist_reset_pair"
        )


@log_performance("block_reset_pair")
async def block_reset_pair(email: str, ip: str) -> None:
    """
    Add an (email, ip) pair to the password reset blocklist in Redis.
    Side Effects: Writes to Redis.
    """
    logger.info("Adding pair to blocklist: %s, %s", email, ip)

    try:
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.sadd(BLOCKLIST_KEY, f"{email}:{ip}")

        log_security_event(
            event_type="abuse_pair_blocked",
            user_id=email,
            ip_address=ip,
            success=True,
            details={"action": "blocklist_add", "pair": f"{email}:{ip}", "was_new": bool(result)},
        )

        logger.info("Successfully blocklisted pair: %s, %s (new: %s)", email, ip, bool(result))

    except (TypeError, ValueError, RuntimeError, AttributeError) as e:
        logger.error("Failed to blocklist pair %s, %s: %s", email, ip, e, exc_info=True)
        log_error_with_context(
            e, context={"email": email, "ip": ip, "action": "blocklist"}, operation="block_reset_pair"
        )


async def admin_add_whitelist_pair(email: str, ip: str) -> bool:
    """
    Add an (email, ip) pair to the password reset whitelist (Redis, fast path).
    Returns True if added, False if already present.
    Side Effects: Writes to Redis.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.sadd(WHITELIST_KEY, f"{email}:{ip}")
        logger.info("Admin added whitelist pair: %s, %s", email, ip)
        return bool(result)
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to add whitelist pair", exc_info=True)
        return False


async def admin_remove_whitelist_pair(email: str, ip: str) -> bool:
    """
    Remove an (email, ip) pair from the password reset whitelist (Redis).
    Returns True if removed, False if not present.
    Side Effects: Writes to Redis.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.srem(WHITELIST_KEY, f"{email}:{ip}")
        logger.info("Admin removed whitelist pair: %s, %s", email, ip)
        return bool(result)
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to remove whitelist pair", exc_info=True)
        return False


async def admin_list_whitelist_pairs() -> List[Dict[str, str]]:
    """
    List all (email, ip) pairs currently in the password reset whitelist (Redis).
    Returns a list of dicts: [{"email": ..., "ip": ...}, ...]
    Side Effects: Reads from Redis.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        pairs = await redis_conn.smembers(WHITELIST_KEY)
        result: List[Dict[str, str]] = []
        for pair in pairs:
            try:
                email, ip = pair.split(":", 1)
                result.append({"email": email, "ip": ip})
            except ValueError:
                logger.debug("Malformed whitelist pair: %r", pair, exc_info=True)
                continue
        logger.debug("Listed %d whitelist pairs", len(result))
        return result
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to list whitelist pairs", exc_info=True)
        return []


async def admin_add_blocklist_pair(email: str, ip: str) -> bool:
    """
    Add an (email, ip) pair to the password reset blocklist (Redis, fast path).
    Returns True if added, False if already present.
    Side Effects: Writes to Redis.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.sadd(BLOCKLIST_KEY, f"{email}:{ip}")
        logger.info("Admin added blocklist pair: %s, %s", email, ip)
        return bool(result)
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to add blocklist pair", exc_info=True)
        return False


async def admin_remove_blocklist_pair(email: str, ip: str) -> bool:
    """
    Remove an (email, ip) pair from the password reset blocklist (Redis).
    Returns True if removed, False if not present.
    Side Effects: Writes to Redis.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.srem(BLOCKLIST_KEY, f"{email}:{ip}")
        logger.info("Admin removed blocklist pair: %s, %s", email, ip)
        return bool(result)
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to remove blocklist pair", exc_info=True)
        return False


async def admin_list_blocklist_pairs() -> List[Dict[str, str]]:
    """
    List all (email, ip) pairs currently in the password reset blocklist (Redis).
    Returns a list of dicts: [{"email": ..., "ip": ...}, ...]
    Side Effects: Reads from Redis.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        pairs = await redis_conn.smembers(BLOCKLIST_KEY)
        result: List[Dict[str, str]] = []
        for pair in pairs:
            try:
                email, ip = pair.split(":", 1)
                result.append({"email": email, "ip": ip})
            except ValueError:
                logger.debug("Malformed blocklist pair: %r", pair, exc_info=True)
                continue
        logger.debug("Listed %d blocklist pairs", len(result))
        return result
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to list blocklist pairs", exc_info=True)
        return []


async def reconcile_blocklist_whitelist() -> None:
    """
    Make MongoDB the source of truth for blocklist/whitelist reconciliation.
    - Redis will be updated to exactly match MongoDB.
    - Any (email, ip) pair not present in MongoDB will be removed from Redis.
    - Deleting from MongoDB will always remove from Redis on the next sync.
    Side Effects: Reads/writes to MongoDB and Redis. Logs reconciliation results.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        users = db_manager.get_collection("users")
        changes = {"mongo_to_redis": 0, "redis_removed": 0}
        for list_type in ["blocklist", "whitelist"]:
            redis_key = f"abuse:reset:{list_type}"
            mongo_pairs = set()
            async for user in users.find({f"reset_{list_type}": {"$exists": True, "$ne": []}}):
                email = user.get("email")
                for ip in user.get(f"reset_{list_type}", []):
                    mongo_pairs.add(f"{email}:{ip}")
            redis_members = await redis_conn.smembers(redis_key)
            redis_pairs = set(m.decode() if hasattr(m, "decode") else m for m in redis_members)
            for pair in redis_pairs - mongo_pairs:
                await redis_conn.srem(redis_key, pair)
                changes["redis_removed"] += 1
            for pair in mongo_pairs - redis_pairs:
                await redis_conn.sadd(redis_key, pair)
                changes["mongo_to_redis"] += 1
        logger.info(
            json.dumps(
                {"event": "blocklist_whitelist_reconcile", "changes": changes, "ts": datetime.utcnow().isoformat()}
            )
        )
        logger.info("Blocklist/whitelist reconciliation (MongoDB → Redis) complete.")
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to reconcile blocklist/whitelist", exc_info=True)


async def is_pair_whitelisted(email: str, ip: str) -> bool:
    """
    Check if an (email, ip) pair is whitelisted for password reset abuse detection.
    Returns True if whitelisted, else False.
    Side Effects: Reads from Redis.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        return await redis_conn.sismember(WHITELIST_KEY, f"{email}:{ip}")
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to check whitelist status", exc_info=True)
        return False


async def is_pair_blocked(email: str, ip: str) -> bool:
    """
    Check if an (email, ip) pair is blocklisted for password reset abuse detection.
    Returns True if blocklisted, else False.
    Side Effects: Reads from Redis.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        return await redis_conn.sismember(BLOCKLIST_KEY, f"{email}:{ip}")
    except (TypeError, ValueError, RuntimeError, AttributeError):
        logger.error("Failed to check blocklist status", exc_info=True)
        return False
