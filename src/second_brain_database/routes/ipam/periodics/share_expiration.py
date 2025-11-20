"""
IPAM Share Expiration Checker Background Task.

This module provides periodic checking and expiration of IPAM shareable links
from the ipam_shares collection.
"""

import asyncio
from datetime import datetime, timezone

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMShareExpiration]")


async def periodic_ipam_share_expiration():
    """
    Periodic background task to expire IPAM shareable links.

    Runs every hour (configurable) to:
    - Query active shares with expires_at < now
    - Update is_active from True to False
    - Log expiration events to audit trail

    This handles the ipam_shares collection (Requirement 4.1).

    Requirements: Req 4.1
    """
    logger.info("Starting IPAM share expiration background task")

    # Get cleanup interval from settings (default: 1 hour)
    cleanup_interval = getattr(settings, "IPAM_SHARE_EXPIRATION_INTERVAL", 3600)

    logger.info(f"IPAM share expiration configured: interval={cleanup_interval}s")

    while True:
        try:
            logger.debug("Running IPAM share expiration check...")
            start_time = datetime.now(timezone.utc)

            # Expire shares
            expired_count = await _expire_shares()

            # Log summary
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"IPAM share expiration completed in {duration:.2f}s: "
                f"{expired_count} shares expired"
            )

            # Sleep for configured interval
            await asyncio.sleep(cleanup_interval)

        except asyncio.CancelledError:
            logger.info("IPAM share expiration task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in IPAM share expiration task: {e}", exc_info=True)
            # Sleep before retrying
            await asyncio.sleep(60)


async def _expire_shares() -> int:
    """
    Expire active shares that have passed their expiration date.

    Returns:
        Number of shares expired
    """
    expired_count = 0

    try:
        shares_collection = db_manager.get_collection("ipam_shares")
        now = datetime.now(timezone.utc)

        # Find active shares that have expired
        expired_shares = await shares_collection.find(
            {
                "is_active": True,
                "expires_at": {"$exists": True, "$ne": None, "$lt": now}
            }
        ).to_list(length=None)

        logger.info(f"Found {len(expired_shares)} expired shares")

        for share in expired_shares:
            try:
                share_id = share["_id"]
                user_id = share.get("user_id")
                resource_type = share.get("resource_type")
                resource_id = share.get("resource_id")
                share_token = share.get("share_token")
                view_count = share.get("view_count", 0)

                # Update is_active to False
                result = await shares_collection.update_one(
                    {"_id": share_id},
                    {
                        "$set": {
                            "is_active": False,
                            "updated_at": now
                        }
                    }
                )

                if result.modified_count > 0:
                    expired_count += 1

                    # Log audit trail
                    await _log_share_expiration(
                        user_id=user_id,
                        share_id=str(share_id),
                        share_token=share_token,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        view_count=view_count,
                        expired_at=share.get("expires_at")
                    )

                    logger.info(
                        f"Expired share {share_id}: {resource_type} {resource_id} "
                        f"(user: {user_id}, views: {view_count})"
                    )

            except Exception as share_error:
                logger.error(
                    f"Error expiring share {share.get('_id')}: {share_error}",
                    exc_info=True
                )

    except Exception as e:
        logger.error(f"Error expiring shares: {e}", exc_info=True)

    return expired_count


async def _log_share_expiration(
    user_id: str,
    share_id: str,
    share_token: str,
    resource_type: str,
    resource_id: str,
    view_count: int,
    expired_at: datetime
) -> None:
    """
    Log share expiration to audit history.

    Args:
        user_id: User ID
        share_id: Share ID
        share_token: Share token (UUID)
        resource_type: "country", "region", or "host"
        resource_id: Resource ID
        view_count: Number of times share was accessed
        expired_at: Expiration timestamp
    """
    try:
        audit_collection = db_manager.get_collection("ipam_audit_history")

        audit_entry = {
            "user_id": user_id,
            "action_type": "share_expired",
            "resource_type": resource_type,
            "resource_id": share_id,
            "snapshot": {
                "share_id": share_id,
                "share_token": share_token,
                "shared_resource_type": resource_type,
                "shared_resource_id": resource_id,
                "view_count": view_count,
                "is_active": True,
                "expired_at": expired_at,
                "processed_at": datetime.now(timezone.utc)
            },
            "reason": "Share expired automatically",
            "timestamp": datetime.now(timezone.utc),
            "metadata": {
                "automated": True,
                "cleanup_task": "periodic_ipam_share_expiration"
            }
        }

        await audit_collection.insert_one(audit_entry)

        logger.debug(f"Logged share expiration for {resource_type} share {share_id}")

    except Exception as e:
        logger.error(f"Error logging share expiration: {e}", exc_info=True)
