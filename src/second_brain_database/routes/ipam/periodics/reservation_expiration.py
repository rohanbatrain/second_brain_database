"""
IPAM Reservation Expiration Checker Background Task.

This module provides periodic checking and expiration of IPAM reservations
from the ipam_reservations collection (new reservation system).
"""

import asyncio
from datetime import datetime, timezone

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMReservationExpiration]")


async def periodic_ipam_reservation_expiration():
    """
    Periodic background task to expire IPAM reservations.

    Runs every hour (configurable) to:
    - Query active reservations with expires_at < now
    - Update status from "active" to "expired"
    - Log expiration events to audit trail

    This handles the new ipam_reservations collection (Requirement 1.4).
    For legacy region/host reservations, see reservation_cleanup.py.

    Requirements: Req 1.4
    """
    logger.info("Starting IPAM reservation expiration background task")

    # Get cleanup interval from settings (default: 1 hour)
    cleanup_interval = getattr(settings, "IPAM_RESERVATION_EXPIRATION_INTERVAL", 3600)

    logger.info(f"IPAM reservation expiration configured: interval={cleanup_interval}s")

    while True:
        try:
            logger.debug("Running IPAM reservation expiration check...")
            start_time = datetime.now(timezone.utc)

            # Expire reservations
            expired_count = await _expire_reservations()

            # Log summary
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"IPAM reservation expiration completed in {duration:.2f}s: "
                f"{expired_count} reservations expired"
            )

            # Sleep for configured interval
            await asyncio.sleep(cleanup_interval)

        except asyncio.CancelledError:
            logger.info("IPAM reservation expiration task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in IPAM reservation expiration task: {e}", exc_info=True)
            # Sleep before retrying
            await asyncio.sleep(60)


async def _expire_reservations() -> int:
    """
    Expire active reservations that have passed their expiration date.

    Returns:
        Number of reservations expired
    """
    expired_count = 0

    try:
        reservations_collection = db_manager.get_collection("ipam_reservations")
        now = datetime.now(timezone.utc)

        # Find active reservations that have expired
        expired_reservations = await reservations_collection.find(
            {
                "status": "active",
                "expires_at": {"$exists": True, "$ne": None, "$lt": now}
            }
        ).to_list(length=None)

        logger.info(f"Found {len(expired_reservations)} expired reservations")

        for reservation in expired_reservations:
            try:
                reservation_id = reservation["_id"]
                user_id = reservation.get("user_id")
                resource_type = reservation.get("resource_type")
                reason = reservation.get("reason", "")

                # Build address string for logging
                x = reservation.get("x_octet")
                y = reservation.get("y_octet")
                z = reservation.get("z_octet")
                
                if resource_type == "host":
                    address = f"{x}.{y}.{z}"
                else:  # region
                    address = f"{x}.{y}.0.0/16"

                # Update status to expired
                result = await reservations_collection.update_one(
                    {"_id": reservation_id},
                    {
                        "$set": {
                            "status": "expired",
                            "updated_at": now
                        }
                    }
                )

                if result.modified_count > 0:
                    expired_count += 1

                    # Log audit trail
                    await _log_reservation_expiration(
                        user_id=user_id,
                        reservation_id=str(reservation_id),
                        resource_type=resource_type,
                        address=address,
                        reason=reason,
                        expired_at=reservation.get("expires_at")
                    )

                    logger.info(
                        f"Expired reservation {reservation_id}: {resource_type} {address} "
                        f"(user: {user_id})"
                    )

            except Exception as reservation_error:
                logger.error(
                    f"Error expiring reservation {reservation.get('_id')}: {reservation_error}",
                    exc_info=True
                )

    except Exception as e:
        logger.error(f"Error expiring reservations: {e}", exc_info=True)

    return expired_count


async def _log_reservation_expiration(
    user_id: str,
    reservation_id: str,
    resource_type: str,
    address: str,
    reason: str,
    expired_at: datetime
) -> None:
    """
    Log reservation expiration to audit history.

    Args:
        user_id: User ID
        reservation_id: Reservation ID
        resource_type: "region" or "host"
        address: IP address or CIDR
        reason: Original reservation reason
        expired_at: Expiration timestamp
    """
    try:
        audit_collection = db_manager.get_collection("ipam_audit_history")

        audit_entry = {
            "user_id": user_id,
            "action_type": "reservation_expired",
            "resource_type": resource_type,
            "resource_id": reservation_id,
            "ip_address": address if resource_type == "host" else None,
            "cidr": address if resource_type == "region" else None,
            "snapshot": {
                "reservation_id": reservation_id,
                "address": address,
                "reason": reason,
                "status": "active",
                "expired_at": expired_at,
                "processed_at": datetime.now(timezone.utc)
            },
            "reason": "Reservation expired automatically",
            "timestamp": datetime.now(timezone.utc),
            "metadata": {
                "automated": True,
                "cleanup_task": "periodic_ipam_reservation_expiration"
            }
        }

        await audit_collection.insert_one(audit_entry)

        logger.debug(f"Logged reservation expiration for {resource_type} {reservation_id}")

    except Exception as e:
        logger.error(f"Error logging reservation expiration: {e}", exc_info=True)
