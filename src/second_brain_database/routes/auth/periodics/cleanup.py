"""
Background task for automatic cleanup of expired 2FA pending states,
backup codes, password reset tokens, rented avatars, and rented banners.

This module is responsible ONLY for cleanup of expired or obsolete authentication-related data, rented avatars, and rented banners in MongoDB.

What this file does:
- Runs periodic background tasks:
    * Cleanup of expired 2FA pending states, backup codes, and password reset tokens (interval set by BACKUP_CODES_CLEANUP_INTERVAL in config/.sbd).
    * Cleanup of expired rented avatars (interval set to 3600 seconds).
    * Cleanup of expired rented banners (interval set to 3600 seconds).
- For each user, checks for and cleans up:
    * Expired 2FA pending states (removes 'two_fa_pending', 'totp_secret', 'backup_codes', etc. if setup is stale)
    * Orphaned 2FA data if 2FA is disabled (removes secrets/codes if user has 2FA off)
    * Expired password reset tokens (removes 'password_reset_token' and 'password_reset_token_expiry' if expired)
    * Expired rented avatars (removes expired entries from 'avatars_rented' and clears them from 'avatars' if set as current)
    * Expired rented banners (removes expired entries from 'banners_rented' and clears them from 'banners' if set as current)
- Tracks the last cleanup time in the 'system' collection for resilience across restarts.
- Logs all cleanup actions and errors for auditability.

What this file does NOT do:
- Does NOT sync password reset blocklist/whitelist/abuse_flags to Redis. That logic is now in redis_flag_sync.py.
- Does NOT perform any business logic, rate limiting, or abuse detection.

How to use:
- Import and run `periodic_2fa_cleanup()`, `periodic_avatar_rental_cleanup()`, and `periodic_banner_rental_cleanup()` as background tasks in your FastAPI app or worker.
- The functions will run forever, sleeping between runs, and will only act if enough time has passed since the last cleanup.
- All cleanup is safe, idempotent, and logged.

See also:
- src/second_brain_database/routes/auth/periodics/redis_flag_sync.py for Redis sync logic.
- config/.sbd for interval and expiry settings.
"""
import asyncio
from datetime import datetime
from typing import Optional
from second_brain_database.database import db_manager
from second_brain_database.config import settings

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.auth.twofa import clear_2fa_pending_if_expired

logger = get_logger(prefix="[Auth Periodic Cleanup]")

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
            logger.debug("Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        logger.debug("No last cleanup time found in system collection.")
        return None
    except Exception as exc:
        logger.error("Error getting last cleanup time: %s", exc, exc_info=True)
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
        logger.debug("Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("Error setting last cleanup time: %s", exc, exc_info=True)
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
    logger.info("Starting periodic 2FA cleanup task with interval %ds", interval)
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
                                logger.info("Cleared expired 2FA pending state for user '%s' (_id=%s)", user.get('username', 'unknown'), user.get('_id'))
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
                                logger.info("Removed orphaned 2FA data for user '%s' (_id=%s)", user.get('username', 'unknown'), user.get('_id'))
                    except Exception as exc:
                        logger.error("Error cleaning up 2FA for user '%s' (_id=%s): %s", user.get('username', 'unknown'), user.get('_id'), exc, exc_info=True)
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
                else:
                    logger.debug("No 2FA cleanup actions needed this cycle.")
            else:
                logger.debug("Skipping cleanup; only %ds since last run (interval: %ds)", (now - last_cleanup).total_seconds() if last_cleanup else 0, interval)
        except Exception as exc:
            logger.error("Error in periodic cleanup task: %s", exc, exc_info=True)
        finally:
            await asyncio.sleep(interval)

async def periodic_avatar_rental_cleanup() -> None:
    """
    Periodically remove expired rented avatars from all user documents.
    This ensures that outdated rentals are not present in user['avatars_rented'] or set as current.
    """
    from datetime import timezone
    users = db_manager.get_collection("users")
    interval = 300  # Run every hour
    while True:
        now = datetime.now(timezone.utc)
        async for user in users.find({"avatars_rented": {"$exists": True, "$ne": []}}):
            updated_rented = []
            expired_avatar_ids = set()
            for avatar in user["avatars_rented"]:
                try:
                    if datetime.fromisoformat(avatar["valid_till"]) > now:
                        updated_rented.append(avatar)
                    else:
                        expired_avatar_ids.add(avatar["avatar_id"])
                except Exception:
                    expired_avatar_ids.add(avatar.get("avatar_id"))
            # Remove expired rentals from avatars_rented
            update_fields = {"avatars_rented": updated_rented}
            # Remove expired rentals from current avatars
            avatars = user.get("avatars", {})
            avatars_changed = False
            for app_key, avatar_id in list(avatars.items()):
                if avatar_id in expired_avatar_ids:
                    avatars[app_key] = None
                    avatars_changed = True
            if avatars_changed:
                update_fields["avatars"] = avatars
            await users.update_one({"_id": user["_id"]}, {"$set": update_fields})
        await asyncio.sleep(interval)

async def periodic_banner_rental_cleanup() -> None:
    """
    Periodically remove expired rented banners from all user documents.
    This ensures that outdated rentals are not present in user['banners_rented'] or set as current.
    """
    from datetime import timezone
    users = db_manager.get_collection("users")
    interval = 3600  # Run every hour (adjust as needed)
    while True:
        now = datetime.now(timezone.utc)
        async for user in users.find({"banners_rented": {"$exists": True, "$ne": []}}):
            updated_rented = []
            expired_banner_ids = set()
            for banner in user["banners_rented"]:
                try:
                    if datetime.fromisoformat(banner["valid_till"]) > now:
                        updated_rented.append(banner)
                    else:
                        expired_banner_ids.add(banner["banner_id"])
                except Exception:
                    expired_banner_ids.add(banner.get("banner_id"))
            # Remove expired rentals from banners_rented
            update_fields = {"banners_rented": updated_rented}
            # Remove expired rentals from current banners
            banners = user.get("banners", {})
            banners_changed = False
            for app_key, banner_id in list(banners.items()):
                if banner_id in expired_banner_ids:
                    banners[app_key] = None
                    banners_changed = True
            if banners_changed:
                update_fields["banners"] = banners
            await users.update_one({"_id": user["_id"]}, {"$set": update_fields})
        await asyncio.sleep(interval)
