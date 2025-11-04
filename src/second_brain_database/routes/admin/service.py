"""
Admin service functions for password reset abuse management,
whitelist/blocklist, and abuse event review.

- PEP 8/257 compliant, MyPy strict compatible.
- Centralized logging with robust error handling.
- All functions typed, with docstrings and constants.
- Linting/tooling config at file end.
"""

from typing import Dict, List, Optional

from bson import ObjectId

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.routes.admin.models import AbuseEvent, EmailIpPairDict

logger = get_logger(prefix="[Admin Service]")


# --- Whitelist/Blocklist Management ---
async def admin_add_whitelist_pair(email: str, ip: str) -> int:
    """
    Add an (email, ip) pair to the password reset whitelist in both MongoDB and Redis.

    Args:
        email: The user's email address.
        ip: The IP address to whitelist.
    Returns:
        Number of elements added to the Redis set (0 or 1).
    Side-effects:
        Updates MongoDB and Redis. Logs the operation.
    """
    try:
        users = db_manager.get_collection(settings.USERS_COLLECTION)
        await users.update_one({"email": email}, {"$addToSet": {"reset_whitelist": ip}})
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.sadd(settings.WHITELIST_KEY, f"{email}:{ip}")
        logger.info("Added to whitelist: %s:%s", email, ip)
        return result
    except Exception:
        logger.error("Failed to add whitelist pair %s:%s", email, ip, exc_info=True)
        raise


async def admin_remove_whitelist_pair(email: str, ip: str) -> int:
    """
    Remove an (email, ip) pair from the password reset whitelist in both MongoDB and Redis.

    Args:
        email: The user's email address.
        ip: The IP address to remove.
    Returns:
        Number of elements removed from the Redis set (0 or 1).
    Side-effects:
        Updates MongoDB and Redis. Logs the operation.
    """
    try:
        users = db_manager.get_collection(settings.USERS_COLLECTION)
        await users.update_one({"email": email}, {"$pull": {"reset_whitelist": ip}})
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.srem(settings.WHITELIST_KEY, f"{email}:{ip}")
        logger.info("Removed from whitelist: %s:%s", email, ip)
        return result
    except Exception:
        logger.error("Failed to remove whitelist pair %s:%s", email, ip, exc_info=True)
        raise


async def admin_list_whitelist_pairs() -> List[EmailIpPairDict]:
    """
    List all (email, ip) pairs in the password reset whitelist from Redis.

    Returns:
        List of dicts with 'email' and 'ip' keys.
    Side-effects:
        Logs the operation.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        members = await redis_conn.smembers(settings.WHITELIST_KEY)
        logger.debug("Fetched whitelist pairs from Redis.")
        return [_split_email_ip(m) for m in members]
    except Exception:
        logger.error("Failed to list whitelist pairs", exc_info=True)
        raise


def _split_email_ip(raw: bytes | str) -> EmailIpPairDict:
    """Helper to split 'email:ip' Redis member into dict."""
    if isinstance(raw, bytes):
        raw = raw.decode()
    email, ip = raw.split(":", 1)
    return {"email": email, "ip": ip}


async def admin_add_blocklist_pair(email: str, ip: str) -> int:
    """
    Add an (email, ip) pair to the password reset blocklist in both MongoDB and Redis.

    Args:
        email: The user's email address.
        ip: The IP address to block.
    Returns:
        Number of elements added to the Redis set (0 or 1).
    Side-effects:
        Updates MongoDB and Redis. Logs the operation.
    """
    try:
        users = db_manager.get_collection(settings.USERS_COLLECTION)
        await users.update_one({"email": email}, {"$addToSet": {"reset_blocklist": ip}})
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.sadd(settings.BLOCKLIST_KEY, f"{email}:{ip}")
        logger.info("Added to blocklist: %s:%s", email, ip)
        return result
    except Exception:
        logger.error("Failed to add blocklist pair %s:%s", email, ip, exc_info=True)
        raise


async def admin_remove_blocklist_pair(email: str, ip: str) -> int:
    """
    Remove an (email, ip) pair from the password reset blocklist in both MongoDB and Redis.

    Args:
        email: The user's email address.
        ip: The IP address to remove.
    Returns:
        Number of elements removed from the Redis set (0 or 1).
    Side-effects:
        Updates MongoDB and Redis. Logs the operation.
    """
    try:
        users = db_manager.get_collection(settings.USERS_COLLECTION)
        await users.update_one({"email": email}, {"$pull": {"reset_blocklist": ip}})
        redis_conn = await redis_manager.get_redis()
        result = await redis_conn.srem(settings.BLOCKLIST_KEY, f"{email}:{ip}")
        logger.info("Removed from blocklist: %s:%s", email, ip)
        return result
    except Exception:
        logger.error("Failed to remove blocklist pair %s:%s", email, ip, exc_info=True)
        raise


async def admin_list_blocklist_pairs() -> List[EmailIpPairDict]:
    """
    List all (email, ip) pairs in the password reset blocklist from Redis.

    Returns:
        List of dicts with 'email' and 'ip' keys.
    Side-effects:
        Logs the operation.
    """
    try:
        redis_conn = await redis_manager.get_redis()
        members = await redis_conn.smembers(settings.BLOCKLIST_KEY)
        logger.debug("Fetched blocklist pairs from Redis.")
        return [_split_email_ip(m) for m in members]
    except Exception:
        logger.error("Failed to list blocklist pairs", exc_info=True)
        raise


# --- Abuse Event Review ---
async def admin_list_abuse_events(
    email: Optional[str] = None, event_type: Optional[str] = None, resolved: Optional[bool] = None, limit: int = 100
) -> List[AbuseEvent]:
    """
    List password reset abuse events from MongoDB for admin review.

    Args:
        email: Optional email filter.
        event_type: Optional event type filter.
        resolved: Optional resolved status filter.
        limit: Max number of events to return.
    Returns:
        List of AbuseEvent models.
    Side-effects:
        Logs the operation.
    """
    try:
        query: Dict = {}
        if email:
            query["email"] = email
        if event_type:
            query["event_type"] = event_type
        if resolved is not None:
            query["resolved"] = resolved
        events = db_manager.get_collection(settings.ABUSE_EVENTS_COLLECTION)
        cursor = events.find(query).sort("timestamp", -1).limit(limit)
        logger.debug("Queried abuse events: %s", query)
        return [AbuseEvent(**doc) async for doc in cursor]
    except Exception:
        logger.error("Failed to list abuse events", exc_info=True)
        raise


async def admin_resolve_abuse_event(event_id: str, notes: Optional[str] = None) -> bool:
    """
    Mark a password reset abuse event as resolved in MongoDB.

    Args:
        event_id: The MongoDB event document ID.
        notes: Optional resolution notes.
    Returns:
        True if the event was updated, False otherwise.
    Side-effects:
        Updates MongoDB. Logs the operation.
    """
    try:
        events = db_manager.get_collection(settings.ABUSE_EVENTS_COLLECTION)
        result = await events.update_one(
            {"_id": ObjectId(event_id)}, {"$set": {"resolved": True, "resolution_notes": notes}}
        )
        logger.info("Resolved abuse event: %s, notes=%s", event_id, notes)
        return result.modified_count == 1
    except Exception:
        logger.error("Failed to resolve abuse event %s", event_id, exc_info=True)
        raise


# --- Legacy direct pair management (for admin UI compatibility) ---
async def whitelist_reset_pair(email: str, ip: str) -> None:
    """
    Add an (email, ip) pair to the password reset whitelist (legacy endpoint).
    Updates both MongoDB and Redis.
    """
    try:
        users = db_manager.get_collection(settings.USERS_COLLECTION)
        await users.update_one({"email": email}, {"$addToSet": {"reset_whitelist": ip}})
        redis_conn = await redis_manager.get_redis()
        await redis_conn.sadd(settings.WHITELIST_KEY, f"{email}:{ip}")
        logger.info("Legacy: Whitelisted reset pair %s:%s", email, ip)
    except Exception:
        logger.error("Failed to whitelist reset pair %s:%s", email, ip, exc_info=True)
        raise


async def block_reset_pair(email: str, ip: str) -> None:
    """
    Add an (email, ip) pair to the password reset blocklist (legacy endpoint).
    Updates both MongoDB and Redis.
    """
    try:
        users = db_manager.get_collection(settings.USERS_COLLECTION)
        await users.update_one({"email": email}, {"$addToSet": {"reset_blocklist": ip}})
        redis_conn = await redis_manager.get_redis()
        await redis_conn.sadd(settings.BLOCKLIST_KEY, f"{email}:{ip}")
        logger.info("Legacy: Blocked reset pair %s:%s", email, ip)
    except Exception:
        logger.error("Failed to block reset pair %s:%s", email, ip, exc_info=True)
        raise
