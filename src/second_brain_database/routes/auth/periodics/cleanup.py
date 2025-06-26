"""
Background task for automatic cleanup of expired 2FA pending states, backup codes, and password reset tokens.

This module is responsible ONLY for cleanup of expired or obsolete authentication-related data in MongoDB.

What this file does:
- Runs a periodic background task (interval set by BACKUP_CODES_CLEANUP_INTERVAL in config/.sbd).
- For each user, checks for and cleans up:
    * Expired 2FA pending states (removes 'two_fa_pending', 'totp_secret', 'backup_codes', etc. if setup is stale)
    * Orphaned 2FA data if 2FA is disabled (removes secrets/codes if user has 2FA off)
    * Expired password reset tokens (removes 'password_reset_token' and 'password_reset_token_expiry' if expired)
- Tracks the last cleanup time in the 'system' collection for resilience across restarts.
- Logs all cleanup actions and errors for auditability.

What this file does NOT do:
- Does NOT sync password reset blocklist/whitelist/abuse_flags to Redis. That logic is now in redis_flag_sync.py.
- Does NOT perform any business logic, rate limiting, or abuse detection.

How to use:
- Import and run `periodic_2fa_cleanup()` as a background task in your FastAPI app or worker.
- The function will run forever, sleeping between runs, and will only act if enough time has passed since the last cleanup.
- All cleanup is safe, idempotent, and logged.

See also:
- src/second_brain_database/routes/auth/periodics/redis_flag_sync.py for Redis sync logic.
- config/.sbd for interval and expiry settings.
"""
import asyncio
from datetime import datetime
from typing import Optional
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.service import clear_2fa_pending_if_expired
from second_brain_database.config import settings
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger()

SYSTEM_COLLECTION = "system"
USERS_COLLECTION = settings.USERS_COLLECTION
CLEANUP_DOC_ID = "2fa_cleanup"

async def get_last_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the cleanup task ran from the system collection.
    Returns a datetime object or None if not set.
    Side-effects: Logs errors.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": CLEANUP_DOC_ID})
        if doc and "last_cleanup" in doc:
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception:
        logger.error("Error getting last cleanup time", exc_info=True)
        raise

async def set_last_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time in the system collection to the given datetime.
    Used for resilience so cleanup resumes correctly after restarts.
    Side-effects: Logs errors.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one(
            {"_id": CLEANUP_DOC_ID},
            {"$set": {"last_cleanup": dt.isoformat()}},
            upsert=True
        )
    except Exception:
        logger.error("Error setting last cleanup time", exc_info=True)
        raise

async def periodic_2fa_cleanup() -> None:
    """
    Periodically scan for users with expired 2FA pending states and clean them up.
    Also removes expired password reset tokens from user records.
    - Runs every BACKUP_CODES_CLEANUP_INTERVAL seconds (from config/.sbd).
    - For each user with 'two_fa_pending=True', checks if their pending state is older than BACKUP_CODES_PENDING_TIME.
    - If so, clears the pending state and backup codes.
    - Removes expired password reset tokens.
    - Updates the last cleanup time in the system collection for failsafe recovery.
    Side-effects: Logs all actions and errors.
    """
    interval = settings.BACKUP_CODES_CLEANUP_INTERVAL
    while True:
        try:
            now = datetime.utcnow()
            last_cleanup = await get_last_cleanup_time()
            if not last_cleanup or (now - last_cleanup).total_seconds() >= interval:
                users = db_manager.get_collection(USERS_COLLECTION)
                cleanup_count = 0
                # 2FA cleanup
                async for user in users.find({"$or": [
                    {"two_fa_pending": True},
                    {"two_fa_enabled": False, "$or": [
                        {"totp_secret": {"$exists": True, "$ne": None}},
                        {"backup_codes": {"$exists": True, "$ne": []}},
                        {"two_fa_pending": {"$exists": True, "$ne": False}}
                    ]}
                ]}):
                    try:
                        # If 2FA is enabled, just clear expired pending states
                        if user.get("two_fa_enabled", False):
                            cleaned = await clear_2fa_pending_if_expired(user)
                            if cleaned:
                                cleanup_count += 1
                        else:
                            # If 2FA is disabled but 2FA-related values exist, remove them
                            update_fields = {}
                            if user.get("totp_secret"):
                                update_fields["totp_secret"] = None
                            if user.get("backup_codes"):
                                update_fields["backup_codes"] = []
                            if user.get("two_fa_pending"):
                                update_fields["two_fa_pending"] = False
                            if update_fields:
                                await users.update_one({"_id": user["_id"]}, {"$set": update_fields})
                                cleanup_count += 1
                    except Exception:
                        logger.error("Error cleaning up 2FA for user %s", user.get('username', 'unknown'), exc_info=True)
                # Password reset token cleanup
                result = await users.update_many(
                    {"password_reset_token_expiry": {"$exists": True, "$lt": now.isoformat()}},
                    {"$unset": {"password_reset_token": "", "password_reset_token_expiry": ""}}
                )
                if result.modified_count > 0:
                    logger.info("Password reset token cleanup: removed %d expired tokens", result.modified_count)
                await set_last_cleanup_time(now)
                if cleanup_count > 0:
                    logger.info("2FA cleanup completed: cleaned up %d expired pending states", cleanup_count)
        except Exception:
            logger.error("Error in periodic cleanup task", exc_info=True)
        finally:
            await asyncio.sleep(interval)
