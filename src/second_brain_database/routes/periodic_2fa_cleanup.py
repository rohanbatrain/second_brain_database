"""
Background task for automatic cleanup of expired 2FA pending states and backup codes.

- The interval for cleanup runs is set by BACKUP_CODES_CLEANUP_INTERVAL (in seconds) from config/.sbd.
- The expiration time for pending 2FA states is set by BACKUP_CODES_PENDING_TIME (in seconds) from config/.sbd.
- The last cleanup time is tracked in the 'system' collection (MongoDB) for resilience across restarts.
- On each run, users with 'two_fa_pending=True' are checked; if their pending state is older than BACKUP_CODES_PENDING_TIME, it is cleared.
- This ensures expired 2FA states are removed promptly and reliably, even after restarts or failures.
"""
import asyncio
from second_brain_database.database import db_manager
from second_brain_database.routes.auth.service import clear_2fa_pending_if_expired
from second_brain_database.config import settings

async def get_last_cleanup_time():
    """
    Retrieve the last time the 2FA cleanup task ran from the 'system' collection.
    Returns a datetime object or None if not set.
    """
    system = db_manager.get_collection("system")
    doc = await system.find_one({"_id": "2fa_cleanup"})
    if doc and "last_cleanup" in doc:
        from datetime import datetime
        return datetime.fromisoformat(doc["last_cleanup"])
    return None

async def set_last_cleanup_time(dt):
    """
    Update the last cleanup time in the 'system' collection to the given datetime.
    Used for resilience so cleanup resumes correctly after restarts.
    """
    system = db_manager.get_collection("system")
    await system.update_one(
        {"_id": "2fa_cleanup"},
        {"$set": {"last_cleanup": dt.isoformat()}},
        upsert=True
    )

async def periodic_2fa_cleanup():
    """
    Periodically scan for users with expired 2FA pending states and clean them up.
    - Runs every BACKUP_CODES_CLEANUP_INTERVAL seconds (from config/.sbd).
    - For each user with 'two_fa_pending=True', checks if their pending state is older than BACKUP_CODES_PENDING_TIME.
    - If so, clears the pending state and backup codes.
    - Updates the last cleanup time in the 'system' collection for failsafe recovery.
    """
    from datetime import datetime, timedelta
    interval = settings.BACKUP_CODES_CLEANUP_INTERVAL
    while True:
        now = datetime.utcnow()
        last_cleanup = await get_last_cleanup_time()
        if not last_cleanup or (now - last_cleanup).total_seconds() >= interval:
            users = db_manager.get_collection("users")
            async for user in users.find({"two_fa_pending": True}):
                await clear_2fa_pending_if_expired(user)
            await set_last_cleanup_time(now)
        await asyncio.sleep(interval)

