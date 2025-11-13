"""
IPAM Reservation Expiration Cleanup Background Task.

This module provides periodic cleanup of expired IPAM reservations
and sends notifications to reservation owners.
"""

import asyncio
from datetime import datetime, timezone
from typing import List

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMReservationCleanup]")


async def periodic_ipam_reservation_cleanup():
    """
    Periodic background task to clean up expired IPAM reservations.

    Runs every hour (configurable) to:
    - Query expired reservations (expires_at < now)
    - Update status to Available
    - Send notification to reservation owner
    - Log audit trail

    Requirements: 17.4
    """
    logger.info("Starting IPAM reservation cleanup background task")

    # Get cleanup interval from settings
    cleanup_interval = settings.IPAM_RESERVATION_CLEANUP_INTERVAL

    logger.info(f"IPAM reservation cleanup configured: interval={cleanup_interval}s")

    while True:
        try:
            logger.debug("Running IPAM reservation cleanup check...")
            start_time = datetime.now(timezone.utc)

            # Clean up expired region reservations
            region_cleaned = await _cleanup_expired_region_reservations()

            # Clean up expired host reservations
            host_cleaned = await _cleanup_expired_host_reservations()

            # Log summary
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"IPAM reservation cleanup completed in {duration:.2f}s: "
                f"{region_cleaned} regions, {host_cleaned} hosts cleaned up"
            )

            # Sleep for configured interval
            await asyncio.sleep(cleanup_interval)

        except asyncio.CancelledError:
            logger.info("IPAM reservation cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in IPAM reservation cleanup task: {e}", exc_info=True)
            # Sleep before retrying
            await asyncio.sleep(60)


async def _cleanup_expired_region_reservations() -> int:
    """
    Clean up expired region reservations.

    Returns:
        Number of reservations cleaned up
    """
    cleaned_count = 0

    try:
        regions_collection = db_manager.get_collection("ipam_regions")
        now = datetime.now(timezone.utc)

        # Find expired reservations
        expired_reservations = await regions_collection.find(
            {
                "status": "Reserved",
                "expires_at": {"$exists": True, "$lt": now}
            }
        ).to_list(length=None)

        logger.info(f"Found {len(expired_reservations)} expired region reservations")

        for reservation in expired_reservations:
            try:
                region_id = str(reservation["_id"])
                user_id = reservation.get("user_id")
                region_name = reservation.get("region_name", "Unknown")
                cidr = reservation.get("cidr", "Unknown")

                # Update status to Available
                result = await regions_collection.update_one(
                    {"_id": reservation["_id"]},
                    {
                        "$set": {
                            "status": "Available",
                            "updated_at": now,
                            "updated_by": "system:reservation_cleanup"
                        },
                        "$unset": {"expires_at": ""}
                    }
                )

                if result.modified_count > 0:
                    cleaned_count += 1

                    # Log audit trail
                    await _log_reservation_expiration(
                        user_id=user_id,
                        resource_type="region",
                        resource_id=region_id,
                        resource_name=region_name,
                        cidr=cidr,
                        expired_at=reservation.get("expires_at")
                    )

                    # Send notification to owner
                    await _send_reservation_expiration_notification(
                        user_id=user_id,
                        resource_type="region",
                        resource_name=region_name,
                        resource_identifier=cidr
                    )

                    logger.info(f"Cleaned up expired region reservation: {region_id} ({cidr})")

            except Exception as reservation_error:
                logger.error(
                    f"Error cleaning up region reservation {reservation.get('_id')}: {reservation_error}",
                    exc_info=True
                )

    except Exception as e:
        logger.error(f"Error cleaning up expired region reservations: {e}", exc_info=True)

    return cleaned_count


async def _cleanup_expired_host_reservations() -> int:
    """
    Clean up expired host reservations.

    Returns:
        Number of reservations cleaned up
    """
    cleaned_count = 0

    try:
        hosts_collection = db_manager.get_collection("ipam_hosts")
        now = datetime.now(timezone.utc)

        # Find expired reservations
        expired_reservations = await hosts_collection.find(
            {
                "status": "Reserved",
                "expires_at": {"$exists": True, "$lt": now}
            }
        ).to_list(length=None)

        logger.info(f"Found {len(expired_reservations)} expired host reservations")

        for reservation in expired_reservations:
            try:
                host_id = str(reservation["_id"])
                user_id = reservation.get("user_id")
                hostname = reservation.get("hostname", "Unknown")
                ip_address = reservation.get("ip_address", "Unknown")

                # Update status to Available
                result = await hosts_collection.update_one(
                    {"_id": reservation["_id"]},
                    {
                        "$set": {
                            "status": "Available",
                            "updated_at": now,
                            "updated_by": "system:reservation_cleanup"
                        },
                        "$unset": {"expires_at": ""}
                    }
                )

                if result.modified_count > 0:
                    cleaned_count += 1

                    # Log audit trail
                    await _log_reservation_expiration(
                        user_id=user_id,
                        resource_type="host",
                        resource_id=host_id,
                        resource_name=hostname,
                        cidr=ip_address,
                        expired_at=reservation.get("expires_at")
                    )

                    # Send notification to owner
                    await _send_reservation_expiration_notification(
                        user_id=user_id,
                        resource_type="host",
                        resource_name=hostname,
                        resource_identifier=ip_address
                    )

                    logger.info(f"Cleaned up expired host reservation: {host_id} ({ip_address})")

            except Exception as reservation_error:
                logger.error(
                    f"Error cleaning up host reservation {reservation.get('_id')}: {reservation_error}",
                    exc_info=True
                )

    except Exception as e:
        logger.error(f"Error cleaning up expired host reservations: {e}", exc_info=True)

    return cleaned_count


async def _log_reservation_expiration(
    user_id: str,
    resource_type: str,
    resource_id: str,
    resource_name: str,
    cidr: str,
    expired_at: datetime
) -> None:
    """
    Log reservation expiration to audit history.

    Args:
        user_id: User ID
        resource_type: "region" or "host"
        resource_id: Resource ID
        resource_name: Resource name
        cidr: CIDR or IP address
        expired_at: Expiration timestamp
    """
    try:
        audit_collection = db_manager.get_collection("ipam_audit_history")

        audit_entry = {
            "user_id": user_id,
            "action_type": "reservation_expired",
            "resource_type": resource_type,
            "resource_id": resource_id,
            "ip_address": cidr if resource_type == "host" else None,
            "cidr": cidr if resource_type == "region" else None,
            "snapshot": {
                "resource_name": resource_name,
                "status": "Reserved",
                "expired_at": expired_at,
                "cleaned_up_at": datetime.now(timezone.utc)
            },
            "reason": "Reservation expired automatically",
            "timestamp": datetime.now(timezone.utc),
            "metadata": {
                "automated": True,
                "cleanup_task": "periodic_ipam_reservation_cleanup"
            }
        }

        await audit_collection.insert_one(audit_entry)

        logger.debug(f"Logged reservation expiration for {resource_type} {resource_id}")

    except Exception as e:
        logger.error(f"Error logging reservation expiration: {e}", exc_info=True)


async def _send_reservation_expiration_notification(
    user_id: str,
    resource_type: str,
    resource_name: str,
    resource_identifier: str
) -> bool:
    """
    Send email notification for expired reservation.

    Args:
        user_id: User ID
        resource_type: "region" or "host"
        resource_name: Resource name
        resource_identifier: CIDR or IP address

    Returns:
        True if email sent successfully
    """
    try:
        # Get user email
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"user_id": user_id})

        if not user or "email" not in user:
            logger.warning(f"No email found for user {user_id}")
            return False

        user_email = user["email"]
        username = user.get("username", user_id)

        # Build email content
        subject = f"IPAM Reservation Expired: {resource_name}"

        html_content = f"""
        <html>
        <body>
            <h2>IPAM Reservation Expired</h2>
            <p>Hello {username},</p>
            <p>Your IPAM reservation has expired and is now available for allocation:</p>
            <ul>
                <li><strong>Type:</strong> {resource_type.capitalize()}</li>
                <li><strong>Name:</strong> {resource_name}</li>
                <li><strong>{'IP Address' if resource_type == 'host' else 'CIDR'}:</strong> {resource_identifier}</li>
            </ul>
            <p>The reservation status has been automatically changed to "Available".</p>
            <p>If you still need this allocation, you can create a new reservation or allocate it permanently.</p>
            <p>View your IPAM allocations at: {settings.BASE_URL}/ipam</p>
        </body>
        </html>
        """

        # Send email
        success = await email_manager.send_html_email(user_email, subject, html_content, username)

        if success:
            logger.info(f"Sent reservation expiration notification to {user_email}")

        return success

    except Exception as e:
        logger.error(f"Error sending reservation expiration notification: {e}", exc_info=True)
        return False
