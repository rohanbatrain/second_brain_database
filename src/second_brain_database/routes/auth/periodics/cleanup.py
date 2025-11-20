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

from second_brain_database.config import settings
from second_brain_database.database import db_manager
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
        await system.update_one({"_id": CLEANUP_DOC_ID}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True)
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
                async for user in users.find(
                    {
                        "$or": [
                            {"two_fa_pending": True},
                            {
                                "two_fa_enabled": False,
                                "$or": [
                                    {"totp_secret": {"$exists": True, "$ne": None}},
                                    {"backup_codes": {"$exists": True, "$ne": []}},
                                    {"two_fa_pending": {"$exists": True, "$ne": False}},
                                ],
                            },
                        ]
                    }
                ):
                    try:
                        # If 2FA is enabled, just clear expired pending states
                        if user.get("two_fa_enabled", False):
                            cleaned = await clear_2fa_pending_if_expired(user)
                            if cleaned:
                                cleanup_count += 1
                                logger.info(
                                    "Cleared expired 2FA pending state for user '%s' (_id=%s)",
                                    user.get("username", "unknown"),
                                    user.get("_id"),
                                )
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
                                logger.info(
                                    "Removed orphaned 2FA data for user '%s' (_id=%s)",
                                    user.get("username", "unknown"),
                                    user.get("_id"),
                                )
                    except Exception as exc:
                        logger.error(
                            "Error cleaning up 2FA for user '%s' (_id=%s): %s",
                            user.get("username", "unknown"),
                            user.get("_id"),
                            exc,
                            exc_info=True,
                        )
                # Password reset token cleanup
                result = await users.update_many(
                    {"password_reset_token_expiry": {"$exists": True, "$lt": now.isoformat()}},
                    {"$unset": {"password_reset_token": "", "password_reset_token_expiry": ""}},
                )
                if result.modified_count > 0:
                    logger.info("Password reset token cleanup: removed %d expired tokens", result.modified_count)
                await set_last_cleanup_time(now)
                if cleanup_count > 0:
                    logger.info("2FA cleanup completed: cleaned up %d expired pending states", cleanup_count)
                else:
                    logger.debug("No 2FA cleanup actions needed this cycle.")
            else:
                logger.debug(
                    "Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic cleanup task: %s", exc, exc_info=True)
        finally:
            await asyncio.sleep(interval)


async def get_last_avatar_rental_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the avatar rental cleanup task ran from the system collection.
    Returns a datetime object or None if not set.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": "avatar_rental_cleanup"})
        if doc and "last_cleanup" in doc:
            logger.debug("[Avatar Rental] Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception as exc:
        logger.error("[Avatar Rental] Error getting last cleanup time: %s", exc, exc_info=True)
        raise


async def set_last_avatar_rental_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time for avatar rental in the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one(
            {"_id": "avatar_rental_cleanup"}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True
        )
        logger.debug("[Avatar Rental] Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("[Avatar Rental] Error setting last cleanup time: %s", exc, exc_info=True)
        raise


async def periodic_avatar_rental_cleanup() -> None:
    """
    Periodically remove expired rented avatars from all user documents.
    This ensures that outdated rentals are not present in user['avatars_rented'] or set as current,
    but does NOT clear current avatar if the user owns it permanently.
    Now tracks last run time in the system collection for resilience.
    """
    from datetime import timezone

    users = db_manager.get_collection("users")
    interval = 300  # Run every 5 minutes
    logger.info("Starting periodic avatar rental cleanup task with interval %ds", interval)
    while True:
        try:
            now = datetime.now(timezone.utc)
            last_cleanup = await get_last_avatar_rental_cleanup_time()
            if not last_cleanup or (now - last_cleanup).total_seconds() >= interval:
                cleanup_count = 0
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
                    update_fields = {"avatars_rented": updated_rented}
                    # Only clear current avatar if not owned permanently
                    avatars = user.get("avatars", {})
                    avatars_owned = {a.get("avatar_id") for a in user.get("avatars_owned", [])}
                    avatars_changed = False
                    for app_key, avatar_id in list(avatars.items()):
                        if avatar_id in expired_avatar_ids and avatar_id not in avatars_owned:
                            avatars[app_key] = None
                            avatars_changed = True
                    if avatars_changed:
                        update_fields["avatars"] = avatars
                    if expired_avatar_ids or avatars_changed:
                        await users.update_one({"_id": user["_id"]}, {"$set": update_fields})
                        cleanup_count += 1
                        logger.info(
                            "Avatar rental cleanup: removed expired avatars %s for user '%s' (_id=%s)",
                            list(expired_avatar_ids),
                            user.get("username", "unknown"),
                            user.get("_id"),
                        )
                if cleanup_count > 0:
                    logger.info("Avatar rental cleanup completed: cleaned up %d users", cleanup_count)
                else:
                    logger.debug("No avatar rental cleanup actions needed this cycle.")
                await set_last_avatar_rental_cleanup_time(now)
            else:
                logger.debug(
                    "[Avatar Rental] Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic_avatar_rental_cleanup: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


async def get_last_banner_rental_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the banner rental cleanup task ran from the system collection.
    Returns a datetime object or None if not set.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": "banner_rental_cleanup"})
        if doc and "last_cleanup" in doc:
            logger.debug("[Banner Rental] Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception as exc:
        logger.error("[Banner Rental] Error getting last cleanup time: %s", exc, exc_info=True)
        raise


async def set_last_banner_rental_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time for banner rental in the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one(
            {"_id": "banner_rental_cleanup"}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True
        )
        logger.debug("[Banner Rental] Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("[Banner Rental] Error setting last cleanup time: %s", exc, exc_info=True)
        raise


async def periodic_banner_rental_cleanup() -> None:
    """
    Periodically remove expired rented banners from all user documents.
    This ensures that outdated rentals are not present in user['banners_rented'] or set as current.
    Now tracks last run time in the system collection for resilience.
    """
    from datetime import timezone

    users = db_manager.get_collection("users")
    interval = 3600  # Run every hour (adjust as needed)
    logger.info("Starting periodic banner rental cleanup task with interval %ds", interval)
    while True:
        try:
            now = datetime.now(timezone.utc)
            last_cleanup = await get_last_banner_rental_cleanup_time()
            if not last_cleanup or (now - last_cleanup).total_seconds() >= interval:
                cleanup_count = 0
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
                    if expired_banner_ids or banners_changed:
                        await users.update_one({"_id": user["_id"]}, {"$set": update_fields})
                        cleanup_count += 1
                        logger.info(
                            "Banner rental cleanup: removed expired banners %s for user '%s' (_id=%s)",
                            list(expired_banner_ids),
                            user.get("username", "unknown"),
                            user.get("_id"),
                        )
                if cleanup_count > 0:
                    logger.info("Banner rental cleanup completed: cleaned up %d users", cleanup_count)
                else:
                    logger.debug("No banner rental cleanup actions needed this cycle.")
                await set_last_banner_rental_cleanup_time(now)
            else:
                logger.debug(
                    "[Banner Rental] Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic_banner_rental_cleanup: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


async def get_last_email_verification_token_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the email verification token cleanup task ran from the system collection.
    Returns a datetime object or None if not set.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": "email_verification_token_cleanup"})
        if doc and "last_cleanup" in doc:
            logger.debug("[Email Verification] Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception as exc:
        logger.error("[Email Verification] Error getting last cleanup time: %s", exc, exc_info=True)
        raise


async def set_last_email_verification_token_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time for email verification token cleanup in the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one(
            {"_id": "email_verification_token_cleanup"}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True
        )
        logger.debug("[Email Verification] Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("[Email Verification] Error setting last cleanup time: %s", exc, exc_info=True)
        raise


async def periodic_email_verification_token_cleanup() -> None:
    """
    Periodically remove expired email verification tokens from user documents.
    Now tracks last run time in the system collection for resilience.
    """
    users = db_manager.get_collection("users")
    interval = 3600  # Run every hour
    logger.info("Starting periodic email verification token cleanup task with interval %ds", interval)
    while True:
        try:
            now_dt = datetime.utcnow()
            now = now_dt.isoformat()
            last_cleanup = await get_last_email_verification_token_cleanup_time()
            if not last_cleanup or (now_dt - last_cleanup).total_seconds() >= interval:
                result = await users.update_many(
                    {"email_verification_token_expiry": {"$exists": True, "$lt": now}},
                    {"$unset": {"email_verification_token": "", "email_verification_token_expiry": ""}},
                )
                if result.modified_count > 0:
                    logger.info("Email verification token cleanup: removed %d expired tokens", result.modified_count)
                else:
                    logger.debug("No email verification token cleanup actions needed this cycle.")
                await set_last_email_verification_token_cleanup_time(now_dt)
            else:
                logger.debug(
                    "[Email Verification] Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now_dt - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic_email_verification_token_cleanup: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


async def get_last_session_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the session cleanup task ran from the system collection.
    Returns a datetime object or None if not set.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": "session_cleanup"})
        if doc and "last_cleanup" in doc:
            logger.debug("[Session] Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception as exc:
        logger.error("[Session] Error getting last cleanup time: %s", exc, exc_info=True)
        raise


async def set_last_session_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time for session cleanup in the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one({"_id": "session_cleanup"}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True)
        logger.debug("[Session] Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("[Session] Error setting last cleanup time: %s", exc, exc_info=True)
        raise


async def periodic_session_cleanup() -> None:
    """
    Periodically remove expired sessions from user documents.
    Now tracks last run time in the system collection for resilience.
    """
    users = db_manager.get_collection("users")
    interval = 3600  # Run every hour
    logger.info("Starting periodic session cleanup task with interval %ds", interval)
    while True:
        try:
            now_dt = datetime.utcnow()
            now = now_dt.isoformat()
            last_cleanup = await get_last_session_cleanup_time()
            if not last_cleanup or (now_dt - last_cleanup).total_seconds() >= interval:
                cleanup_count = 0
                async for user in users.find({"sessions": {"$exists": True, "$ne": []}}):
                    sessions = user.get("sessions", [])
                    filtered = [s for s in sessions if s.get("expires_at", now) > now]
                    if len(filtered) != len(sessions):
                        await users.update_one({"_id": user["_id"]}, {"$set": {"sessions": filtered}})
                        cleanup_count += 1
                        logger.info(
                            "Session cleanup: removed expired sessions for user '%s' (_id=%s)",
                            user.get("username", "unknown"),
                            user.get("_id"),
                        )
                if cleanup_count > 0:
                    logger.info("Session cleanup completed: cleaned up %d users", cleanup_count)
                else:
                    logger.debug("No session cleanup actions needed this cycle.")
                await set_last_session_cleanup_time(now_dt)
            else:
                logger.debug(
                    "[Session] Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now_dt - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic_session_cleanup: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


async def get_last_trusted_ip_lockdown_code_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the trusted IP lockdown code cleanup task ran from the system collection.
    Returns a datetime object or None if not set.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": "trusted_ip_lockdown_code_cleanup"})
        if doc and "last_cleanup" in doc:
            logger.debug("[Trusted IP] Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception as exc:
        logger.error("[Trusted IP] Error getting last cleanup time: %s", exc, exc_info=True)
        raise


async def set_last_trusted_ip_lockdown_code_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time for trusted IP lockdown code cleanup in the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one(
            {"_id": "trusted_ip_lockdown_code_cleanup"}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True
        )
        logger.debug("[Trusted IP] Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("[Trusted IP] Error setting last cleanup time: %s", exc, exc_info=True)
        raise


async def periodic_trusted_ip_lockdown_code_cleanup() -> None:
    """
    Periodically remove expired trusted IP lockdown codes from user documents.
    Now tracks last run time in the system collection for resilience.
    """
    users = db_manager.get_collection("users")
    interval = 3600  # Run every hour
    logger.info("Starting periodic trusted IP lockdown code cleanup task with interval %ds", interval)
    while True:
        try:
            now_dt = datetime.utcnow()
            now = now_dt.isoformat()
            last_cleanup = await get_last_trusted_ip_lockdown_code_cleanup_time()
            if not last_cleanup or (now_dt - last_cleanup).total_seconds() >= interval:
                cleanup_count = 0
                async for user in users.find({"trusted_ip_lockdown_codes": {"$exists": True, "$ne": []}}):
                    codes = user.get("trusted_ip_lockdown_codes", [])
                    filtered = [c for c in codes if c.get("expires_at", now) > now]
                    if len(filtered) != len(codes):
                        await users.update_one({"_id": user["_id"]}, {"$set": {"trusted_ip_lockdown_codes": filtered}})
                        cleanup_count += 1
                        logger.info(
                            "Trusted IP lockdown code cleanup: removed expired codes for user '%s' (_id=%s)",
                            user.get("username", "unknown"),
                            user.get("_id"),
                        )
                if cleanup_count > 0:
                    logger.info("Trusted IP lockdown code cleanup completed: cleaned up %d users", cleanup_count)
                else:
                    logger.debug("No trusted IP lockdown code cleanup actions needed this cycle.")
                await set_last_trusted_ip_lockdown_code_cleanup_time(now_dt)
            else:
                logger.debug(
                    "[Trusted IP] Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now_dt - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic_trusted_ip_lockdown_code_cleanup: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


async def get_last_admin_session_token_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the admin session token cleanup task ran from the system collection.
    Returns a datetime object or None if not set.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": "admin_session_token_cleanup"})
        if doc and "last_cleanup" in doc:
            logger.debug("[Admin Session] Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception as exc:
        logger.error("[Admin Session] Error getting last cleanup time: %s", exc, exc_info=True)
        raise


async def set_last_admin_session_token_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time for admin session token cleanup in the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one(
            {"_id": "admin_session_token_cleanup"}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True
        )
        logger.debug("[Admin Session] Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("[Admin Session] Error setting last cleanup time: %s", exc, exc_info=True)
        raise


async def periodic_admin_session_token_cleanup() -> None:
    """
    Periodically remove expired admin session tokens from user documents.
    Now tracks last run time in the system collection for resilience.
    """
    users = db_manager.get_collection("users")
    interval = 3600  # Run every hour
    logger.info("Starting periodic admin session token cleanup task with interval %ds", interval)
    while True:
        try:
            now_dt = datetime.utcnow()
            now = now_dt.isoformat()
            last_cleanup = await get_last_admin_session_token_cleanup_time()
            if not last_cleanup or (now_dt - last_cleanup).total_seconds() >= interval:
                cleanup_count = 0
                async for user in users.find({"admin_sessions": {"$exists": True, "$ne": []}}):
                    sessions = user.get("admin_sessions", [])
                    filtered = [s for s in sessions if s.get("expires_at", now) > now]
                    if len(filtered) != len(sessions):
                        await users.update_one({"_id": user["_id"]}, {"$set": {"admin_sessions": filtered}})
                        cleanup_count += 1
                        logger.info(
                            "Admin session token cleanup: removed expired tokens for user '%s' (_id=%s)",
                            user.get("username", "unknown"),
                            user.get("_id"),
                        )
                if cleanup_count > 0:
                    logger.info("Admin session token cleanup completed: cleaned up %d users", cleanup_count)
                else:
                    logger.debug("No admin session token cleanup actions needed this cycle.")
                await set_last_admin_session_token_cleanup_time(now_dt)
            else:
                logger.debug(
                    "[Admin Session] Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now_dt - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic_admin_session_token_cleanup: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


async def get_last_trusted_user_agent_lockdown_code_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the trusted User Agent lockdown code cleanup task ran from the system collection.
    Returns a datetime object or None if not set.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": "trusted_user_agent_lockdown_code_cleanup"})
        if doc and "last_cleanup" in doc:
            logger.debug("[Trusted User Agent] Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception as exc:
        logger.error("[Trusted User Agent] Error getting last cleanup time: %s", exc, exc_info=True)
        raise


async def set_last_trusted_user_agent_lockdown_code_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time for trusted User Agent lockdown code cleanup in the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one(
            {"_id": "trusted_user_agent_lockdown_code_cleanup"}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True
        )
        logger.debug("[Trusted User Agent] Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("[Trusted User Agent] Error setting last cleanup time: %s", exc, exc_info=True)
        raise


async def periodic_trusted_user_agent_lockdown_code_cleanup() -> None:
    """
    Periodically remove expired trusted User Agent lockdown codes from user documents.
    Now tracks last run time in the system collection for resilience.
    """
    users = db_manager.get_collection("users")
    interval = 3600  # Run every hour
    logger.info("Starting periodic trusted User Agent lockdown code cleanup task with interval %ds", interval)
    while True:
        try:
            now_dt = datetime.utcnow()
            now = now_dt.isoformat()
            last_cleanup = await get_last_trusted_user_agent_lockdown_code_cleanup_time()
            if not last_cleanup or (now_dt - last_cleanup).total_seconds() >= interval:
                cleanup_count = 0
                async for user in users.find({"trusted_user_agent_lockdown_codes": {"$exists": True, "$ne": []}}):
                    codes = user.get("trusted_user_agent_lockdown_codes", [])
                    filtered = [c for c in codes if c.get("expires_at", now) > now]
                    if len(filtered) != len(codes):
                        await users.update_one(
                            {"_id": user["_id"]}, {"$set": {"trusted_user_agent_lockdown_codes": filtered}}
                        )
                        cleanup_count += 1
                        logger.info(
                            "Trusted User Agent lockdown code cleanup: removed expired codes for user '%s' (_id=%s)",
                            user.get("username", "unknown"),
                            user.get("_id"),
                        )
                if cleanup_count > 0:
                    logger.info(
                        "Trusted User Agent lockdown code cleanup completed: cleaned up %d users", cleanup_count
                    )
                else:
                    logger.debug("No trusted User Agent lockdown code cleanup actions needed this cycle.")
                await set_last_trusted_user_agent_lockdown_code_cleanup_time(now_dt)
            else:
                logger.debug(
                    "[Trusted User Agent] Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now_dt - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic_trusted_user_agent_lockdown_code_cleanup: %s", exc, exc_info=True)
        await asyncio.sleep(interval)


async def get_last_temporary_access_tokens_cleanup_time() -> Optional[datetime]:
    """
    Retrieve the last time the temporary access tokens cleanup task ran from the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        doc = await system.find_one({"_id": "temporary_access_tokens_cleanup"})
        if doc and "last_cleanup" in doc:
            logger.debug("[Temporary Access] Retrieved last cleanup time: %s", doc["last_cleanup"])
            return datetime.fromisoformat(doc["last_cleanup"])
        return None
    except Exception as exc:
        logger.error("Error retrieving last temporary access tokens cleanup time: %s", exc, exc_info=True)
        return None


async def set_last_temporary_access_tokens_cleanup_time(dt: datetime) -> None:
    """
    Update the last cleanup time for temporary access tokens cleanup in the system collection.
    """
    try:
        system = db_manager.get_collection(SYSTEM_COLLECTION)
        await system.update_one(
            {"_id": "temporary_access_tokens_cleanup"}, {"$set": {"last_cleanup": dt.isoformat()}}, upsert=True
        )
        logger.debug("[Temporary Access] Set last cleanup time to: %s", dt.isoformat())
    except Exception as exc:
        logger.error("Error setting last temporary access tokens cleanup time: %s", exc, exc_info=True)


async def periodic_temporary_access_tokens_cleanup() -> None:
    """
    Periodically remove expired temporary access tokens from user documents.

    This cleanup process removes expired "allow once" tokens for both IP and User Agent lockdown
    from user documents to prevent accumulation of stale data.
    """
    interval = 3600  # Run every hour (temporary tokens have short expiration)
    logger.info("Starting periodic temporary access tokens cleanup task (interval: %ds)", interval)

    while True:
        try:
            users = db_manager.get_collection("users")
            now_dt = datetime.utcnow()
            now = now_dt.isoformat()
            last_cleanup = await get_last_temporary_access_tokens_cleanup_time()

            if not last_cleanup or (now_dt - last_cleanup).total_seconds() >= interval:
                cleanup_count = 0

                # Find users with temporary access tokens or bypasses
                query = {
                    "$or": [
                        {"temporary_ip_access_tokens": {"$exists": True, "$ne": []}},
                        {"temporary_user_agent_access_tokens": {"$exists": True, "$ne": []}},
                        {"temporary_ip_bypasses": {"$exists": True, "$ne": []}},
                    ]
                }

                async for user in users.find(query):
                    user_updated = False
                    update_fields = {}

                    # Clean up expired IP access tokens
                    ip_tokens = user.get("temporary_ip_access_tokens", [])
                    if ip_tokens:
                        filtered_ip_tokens = [t for t in ip_tokens if t.get("expires_at", now) > now]
                        if len(filtered_ip_tokens) != len(ip_tokens):
                            update_fields["temporary_ip_access_tokens"] = filtered_ip_tokens
                            user_updated = True

                    # Clean up expired User Agent access tokens
                    ua_tokens = user.get("temporary_user_agent_access_tokens", [])
                    if ua_tokens:
                        filtered_ua_tokens = [t for t in ua_tokens if t.get("expires_at", now) > now]
                        if len(filtered_ua_tokens) != len(ua_tokens):
                            update_fields["temporary_user_agent_access_tokens"] = filtered_ua_tokens
                            user_updated = True

                    # Clean up expired IP bypasses
                    ip_bypasses = user.get("temporary_ip_bypasses", [])
                    if ip_bypasses:
                        filtered_ip_bypasses = [b for b in ip_bypasses if b.get("expires_at", now) > now]
                        if len(filtered_ip_bypasses) != len(ip_bypasses):
                            update_fields["temporary_ip_bypasses"] = filtered_ip_bypasses
                            user_updated = True

                    # Update user document if any tokens were expired
                    if user_updated:
                        await users.update_one({"_id": user["_id"]}, {"$set": update_fields})
                        cleanup_count += 1
                        logger.info(
                            "Temporary access tokens cleanup: removed expired tokens for user '%s' (_id=%s)",
                            user.get("username", "unknown"),
                            user.get("_id"),
                        )

                if cleanup_count > 0:
                    logger.info("Temporary access tokens cleanup completed: cleaned up %d users", cleanup_count)
                else:
                    logger.debug("No temporary access tokens cleanup actions needed this cycle.")

                await set_last_temporary_access_tokens_cleanup_time(now_dt)
            else:
                logger.debug(
                    "[Temporary Access] Skipping cleanup; only %ds since last run (interval: %ds)",
                    (now_dt - last_cleanup).total_seconds() if last_cleanup else 0,
                    interval,
                )
        except Exception as exc:
            logger.error("Error in periodic_temporary_access_tokens_cleanup: %s", exc, exc_info=True)
        await asyncio.sleep(interval)
