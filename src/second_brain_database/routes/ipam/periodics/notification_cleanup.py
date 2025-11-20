"""
IPAM Notification Cleanup Background Task.

This module provides periodic cleanup of old IPAM notifications
from the ipam_notifications collection.
"""

import asyncio
from datetime import datetime, timedelta, timezone

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMNotificationCleanup]")


async def periodic_ipam_notification_cleanup():
    """
    Periodic background task to clean up old IPAM notifications.

    Runs daily (configurable) to:
    - Query notifications with created_at > 90 days ago
    - Delete old notifications
    - Log cleanup events

    This handles the ipam_notifications collection (Requirement 8.5).

    Requirements: Req 8.5
    """
    logger.info("Starting IPAM notification cleanup background task")

    # Get cleanup interval from settings (default: 24 hours)
    cleanup_interval = getattr(settings, "IPAM_NOTIFICATION_CLEANUP_INTERVAL", 86400)

    logger.info(f"IPAM notification cleanup configured: interval={cleanup_interval}s")

    while True:
        try:
            logger.debug("Running IPAM notification cleanup check...")
            start_time = datetime.now(timezone.utc)

            # Clean up old notifications
            deleted_count = await _cleanup_old_notifications()

            # Log summary
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"IPAM notification cleanup completed in {duration:.2f}s: "
                f"{deleted_count} notifications deleted"
            )

            # Sleep for configured interval
            await asyncio.sleep(cleanup_interval)

        except asyncio.CancelledError:
            logger.info("IPAM notification cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in IPAM notification cleanup task: {e}", exc_info=True)
            # Sleep before retrying
            await asyncio.sleep(300)  # 5 minutes


async def _cleanup_old_notifications() -> int:
    """
    Delete notifications older than 90 days.

    Returns:
        Number of notifications deleted
    """
    deleted_count = 0

    try:
        notifications_collection = db_manager.get_collection("ipam_notifications")
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=90)

        # Find notifications older than 90 days
        old_notifications = await notifications_collection.find(
            {
                "created_at": {"$lt": cutoff_date}
            },
            {"_id": 1, "user_id": 1, "notification_type": 1, "severity": 1}
        ).to_list(length=None)

        logger.info(f"Found {len(old_notifications)} notifications older than 90 days")

        if old_notifications:
            # Extract IDs for bulk deletion
            notification_ids = [notif["_id"] for notif in old_notifications]

            # Delete old notifications
            result = await notifications_collection.delete_many(
                {"_id": {"$in": notification_ids}}
            )

            deleted_count = result.deleted_count

            # Log audit trail for cleanup
            await _log_notification_cleanup(
                deleted_count=deleted_count,
                cutoff_date=cutoff_date,
                sample_notifications=old_notifications[:10]  # Log first 10 as sample
            )

            logger.info(
                f"Deleted {deleted_count} notifications older than {cutoff_date.isoformat()}"
            )

    except Exception as e:
        logger.error(f"Error cleaning up old notifications: {e}", exc_info=True)

    return deleted_count


async def _log_notification_cleanup(
    deleted_count: int,
    cutoff_date: datetime,
    sample_notifications: list
) -> None:
    """
    Log notification cleanup to audit history.

    Args:
        deleted_count: Number of notifications deleted
        cutoff_date: Cutoff date for deletion
        sample_notifications: Sample of deleted notifications for audit
    """
    try:
        audit_collection = db_manager.get_collection("ipam_audit_history")

        audit_entry = {
            "user_id": "system",
            "action_type": "notifications_cleanup",
            "resource_type": "notification",
            "resource_id": None,
            "snapshot": {
                "deleted_count": deleted_count,
                "cutoff_date": cutoff_date,
                "retention_days": 90,
                "sample_notifications": [
                    {
                        "notification_id": str(notif["_id"]),
                        "user_id": notif.get("user_id"),
                        "notification_type": notif.get("notification_type"),
                        "severity": notif.get("severity")
                    }
                    for notif in sample_notifications
                ],
                "processed_at": datetime.now(timezone.utc)
            },
            "reason": "Automatic cleanup of notifications older than 90 days",
            "timestamp": datetime.now(timezone.utc),
            "metadata": {
                "automated": True,
                "cleanup_task": "periodic_ipam_notification_cleanup"
            }
        }

        await audit_collection.insert_one(audit_entry)

        logger.debug(f"Logged notification cleanup: {deleted_count} notifications deleted")

    except Exception as e:
        logger.error(f"Error logging notification cleanup: {e}", exc_info=True)
