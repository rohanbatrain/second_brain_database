"""
IPAM Capacity Monitoring Background Task.

This module provides periodic monitoring of IPAM capacity thresholds
and sends notifications when capacity limits are approached or exceeded.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Set

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.email import email_manager
from second_brain_database.managers.ipam_manager import ipam_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.ipam.monitoring.metrics_middleware import track_capacity_warning_event

logger = get_logger(prefix="[IPAMCapacityMonitoring]")

# Track users already notified to avoid spam
_notified_countries: Set[str] = set()  # Format: "user_id:country:threshold"
_notified_regions: Set[str] = set()  # Format: "user_id:region_id"


async def periodic_ipam_capacity_monitoring():
    """
    Periodic background task to monitor IPAM capacity thresholds.

    Runs every 15 minutes (configurable) to:
    - Query users with active allocations
    - Calculate country and region utilization
    - Send notifications at configurable thresholds (default: 80% warning, 100% critical)
    - Send region notifications at configurable threshold (default: 90%)
    - Support per-country and per-region threshold overrides
    - Support multiple notification channels (email, webhook, in-app)
    - Log capacity events

    Requirements: 19.1, 19.2, 19.3, 19.4, 19.5
    """
    logger.info("Starting IPAM capacity monitoring background task")

    # Get thresholds from settings (with defaults)
    warning_threshold = settings.IPAM_CAPACITY_WARNING_THRESHOLD
    critical_threshold = settings.IPAM_CAPACITY_CRITICAL_THRESHOLD
    region_threshold = settings.IPAM_REGION_CAPACITY_THRESHOLD

    # Get country and region threshold overrides
    country_thresholds = settings.ipam_country_thresholds_dict
    region_thresholds = settings.ipam_region_thresholds_dict

    # Get monitoring interval
    monitoring_interval = settings.IPAM_CAPACITY_MONITORING_INTERVAL

    logger.info(
        f"IPAM capacity monitoring configured: warning={warning_threshold}%, "
        f"critical={critical_threshold}%, region={region_threshold}%, "
        f"interval={monitoring_interval}s"
    )

    while True:
        try:
            logger.debug("Running IPAM capacity monitoring check...")
            start_time = datetime.now(timezone.utc)

            # Get all users with active allocations
            users_with_allocations = await _get_users_with_allocations()
            logger.info(f"Monitoring capacity for {len(users_with_allocations)} users")

            # Track notifications sent in this run
            notifications_sent = 0
            warnings_logged = 0

            for user_id in users_with_allocations:
                try:
                    # Check country utilization for this user
                    country_notifications = await _check_country_utilization(
                        user_id, warning_threshold, critical_threshold, country_thresholds
                    )
                    notifications_sent += country_notifications

                    # Check region utilization for this user
                    region_notifications = await _check_region_utilization(
                        user_id, region_threshold, region_thresholds
                    )
                    notifications_sent += region_notifications

                except Exception as user_error:
                    logger.error(
                        f"Error monitoring capacity for user {user_id}: {user_error}",
                        exc_info=True,
                        extra={"user_id": user_id, "error": str(user_error)},
                    )
                    warnings_logged += 1

            # Log summary
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"IPAM capacity monitoring completed in {duration:.2f}s: "
                f"{notifications_sent} notifications sent, {warnings_logged} errors"
            )

            # Sleep for configured interval
            await asyncio.sleep(monitoring_interval)

        except asyncio.CancelledError:
            logger.info("IPAM capacity monitoring task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in IPAM capacity monitoring task: {e}", exc_info=True)
            # Sleep before retrying
            await asyncio.sleep(60)


async def _get_users_with_allocations() -> List[str]:
    """
    Get list of unique user IDs with active IPAM allocations.

    Returns:
        List of user IDs
    """
    try:
        regions_collection = db_manager.get_collection("ipam_regions")

        # Get distinct user IDs from regions collection
        user_ids = await regions_collection.distinct("user_id", {"status": "Active"})

        return user_ids

    except Exception as e:
        logger.error(f"Error getting users with allocations: {e}", exc_info=True)
        return []


async def _check_country_utilization(
    user_id: str, warning_threshold: int, critical_threshold: int, country_thresholds: Dict
) -> int:
    """
    Check country utilization for a user and send notifications if thresholds exceeded.

    Args:
        user_id: User ID to check
        warning_threshold: Default warning threshold percentage
        critical_threshold: Default critical threshold percentage
        country_thresholds: Per-country threshold overrides

    Returns:
        Number of notifications sent
    """
    notifications_sent = 0

    try:
        # Get all countries this user has allocations in
        regions_collection = db_manager.get_collection("ipam_regions")
        countries = await regions_collection.distinct("country", {"user_id": user_id, "status": "Active"})

        for country in countries:
            try:
                # Calculate utilization for this country
                utilization_stats = await ipam_manager.calculate_country_utilization(user_id, country)

                utilization_pct = utilization_stats.get("utilization_percentage", 0)

                # Get country-specific thresholds if configured
                country_config = country_thresholds.get(country, {})
                country_warning = country_config.get("warning", warning_threshold)
                country_critical = country_config.get("critical", critical_threshold)

                # Determine if notification needed
                threshold_reached = None
                if utilization_pct >= country_critical:
                    threshold_reached = "critical"
                elif utilization_pct >= country_warning:
                    threshold_reached = "warning"

                if threshold_reached:
                    # Check if already notified
                    notification_key = f"{user_id}:{country}:{threshold_reached}"
                    if notification_key not in _notified_countries:
                        # Send notification
                        success = await _send_country_capacity_notification(
                            user_id, country, utilization_stats, threshold_reached
                        )

                        if success:
                            _notified_countries.add(notification_key)
                            notifications_sent += 1
                            logger.info(
                                f"Sent {threshold_reached} notification for country {country} to user {user_id}"
                            )

                        # Log capacity event
                        await _log_capacity_event(
                            user_id=user_id,
                            resource_type="country",
                            resource_identifier=country,
                            utilization_percentage=utilization_pct,
                            threshold_type=threshold_reached,
                            capacity_stats=utilization_stats,
                        )
                        
                        # Track capacity warning in metrics
                        await track_capacity_warning_event(
                            resource_type="country",
                            resource_id=country,
                            utilization=utilization_pct,
                            threshold=country_critical if threshold_reached == "critical" else country_warning
                        )
                else:
                    # Remove from notified set if utilization dropped below warning
                    _notified_countries.discard(f"{user_id}:{country}:warning")
                    _notified_countries.discard(f"{user_id}:{country}:critical")

            except Exception as country_error:
                logger.error(
                    f"Error checking country {country} for user {user_id}: {country_error}",
                    exc_info=True,
                    extra={"user_id": user_id, "country": country},
                )

    except Exception as e:
        logger.error(f"Error checking country utilization for user {user_id}: {e}", exc_info=True)

    return notifications_sent


async def _check_region_utilization(user_id: str, region_threshold: int, region_thresholds: Dict) -> int:
    """
    Check region utilization for a user and send notifications if threshold exceeded.

    Args:
        user_id: User ID to check
        region_threshold: Default region threshold percentage
        region_thresholds: Per-region threshold overrides

    Returns:
        Number of notifications sent
    """
    notifications_sent = 0

    try:
        # Get all active regions for this user
        regions_collection = db_manager.get_collection("ipam_regions")
        regions = await regions_collection.find({"user_id": user_id, "status": "Active"}).to_list(length=None)

        for region in regions:
            try:
                region_id = str(region["_id"])

                # Calculate utilization for this region
                utilization_stats = await ipam_manager.calculate_region_utilization(user_id, region_id)

                utilization_pct = utilization_stats.get("utilization_percentage", 0)

                # Get region-specific threshold if configured
                region_specific_threshold = region_thresholds.get(region_id, region_threshold)

                # Check if threshold exceeded
                if utilization_pct >= region_specific_threshold:
                    # Check if already notified
                    notification_key = f"{user_id}:{region_id}"
                    if notification_key not in _notified_regions:
                        # Send notification
                        success = await _send_region_capacity_notification(
                            user_id, region, utilization_stats
                        )

                        if success:
                            _notified_regions.add(notification_key)
                            notifications_sent += 1
                            logger.info(
                                f"Sent region capacity notification for region {region_id} to user {user_id}"
                            )

                        # Log capacity event
                        await _log_capacity_event(
                            user_id=user_id,
                            resource_type="region",
                            resource_identifier=region_id,
                            utilization_percentage=utilization_pct,
                            threshold_type="critical",
                            capacity_stats=utilization_stats,
                        )
                        
                        # Track capacity warning in metrics
                        await track_capacity_warning_event(
                            resource_type="region",
                            resource_id=region_id,
                            utilization=utilization_pct,
                            threshold=region_specific_threshold
                        )
                else:
                    # Remove from notified set if utilization dropped
                    _notified_regions.discard(f"{user_id}:{region_id}")

            except Exception as region_error:
                logger.error(
                    f"Error checking region {region.get('_id')} for user {user_id}: {region_error}",
                    exc_info=True,
                    extra={"user_id": user_id, "region_id": str(region.get("_id"))},
                )

    except Exception as e:
        logger.error(f"Error checking region utilization for user {user_id}: {e}", exc_info=True)

    return notifications_sent


async def _send_country_capacity_notification(
    user_id: str, country: str, utilization_stats: Dict, threshold_type: str
) -> bool:
    """
    Send email notification for country capacity threshold.

    Args:
        user_id: User ID
        country: Country name
        utilization_stats: Utilization statistics
        threshold_type: "warning" or "critical"

    Returns:
        True if email sent successfully
    """
    try:
        # Get user email (would need to query users collection)
        users_collection = db_manager.get_collection("users")
        user = await users_collection.find_one({"user_id": user_id})

        if not user or "email" not in user:
            logger.warning(f"No email found for user {user_id}")
            return False

        user_email = user["email"]
        username = user.get("username", user_id)

        # Build email content
        utilization_pct = utilization_stats.get("utilization_percentage", 0)
        allocated = utilization_stats.get("allocated_regions", 0)
        total_capacity = utilization_stats.get("total_capacity", 0)

        if threshold_type == "critical":
            subject = f"CRITICAL: IPAM Capacity Exhausted for {country}"
            severity_color = "#f44336"
            severity_text = "CRITICAL"
        else:
            subject = f"WARNING: IPAM Capacity Alert for {country}"
            severity_color = "#ff9800"
            severity_text = "WARNING"

        html_content = f"""
        <html>
        <body>
            <h2 style="color: {severity_color};">{severity_text}: IPAM Capacity Alert</h2>
            <p>Hello {username},</p>
            <p>Your IPAM allocation for <strong>{country}</strong> has reached capacity threshold:</p>
            <ul>
                <li><strong>Utilization:</strong> {utilization_pct:.1f}%</li>
                <li><strong>Allocated Regions:</strong> {allocated} / {total_capacity}</li>
                <li><strong>Threshold Type:</strong> {severity_text}</li>
            </ul>
            <p>{'No more regions can be allocated in this country.' if threshold_type == 'critical' else 'Please consider planning for additional capacity.'}</p>
            <p>You can view your allocations at: {settings.BASE_URL}/ipam/countries/{country}</p>
        </body>
        </html>
        """

        # Send email
        success = await email_manager.send_html_email(user_email, subject, html_content, username)

        return success

    except Exception as e:
        logger.error(f"Error sending country capacity notification: {e}", exc_info=True)
        return False


async def _send_region_capacity_notification(
    user_id: str, region: Dict, utilization_stats: Dict
) -> bool:
    """
    Send email notification for region capacity threshold.

    Args:
        user_id: User ID
        region: Region document
        utilization_stats: Utilization statistics

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
        region_name = region.get("region_name", "Unknown")
        cidr = region.get("cidr", "Unknown")
        utilization_pct = utilization_stats.get("utilization_percentage", 0)
        allocated_hosts = utilization_stats.get("allocated_hosts", 0)
        total_capacity = utilization_stats.get("total_capacity", 254)

        subject = f"IPAM Region Capacity Alert: {region_name}"

        html_content = f"""
        <html>
        <body>
            <h2 style="color: #ff9800;">Region Capacity Alert</h2>
            <p>Hello {username},</p>
            <p>Your IPAM region <strong>{region_name}</strong> ({cidr}) is approaching capacity:</p>
            <ul>
                <li><strong>Utilization:</strong> {utilization_pct:.1f}%</li>
                <li><strong>Allocated Hosts:</strong> {allocated_hosts} / {total_capacity}</li>
            </ul>
            <p>Please consider planning for additional regions if you need more host addresses.</p>
            <p>You can view your region at: {settings.BASE_URL}/ipam/regions/{region['_id']}</p>
        </body>
        </html>
        """

        # Send email
        success = await email_manager.send_html_email(user_email, subject, html_content, username)

        return success

    except Exception as e:
        logger.error(f"Error sending region capacity notification: {e}", exc_info=True)
        return False


async def _log_capacity_event(
    user_id: str,
    resource_type: str,
    resource_identifier: str,
    utilization_percentage: float,
    threshold_type: str,
    capacity_stats: Dict,
) -> None:
    """
    Log capacity event to database for audit trail.

    Args:
        user_id: User ID
        resource_type: "country" or "region"
        resource_identifier: Country name or region ID
        utilization_percentage: Current utilization percentage
        threshold_type: "warning" or "critical"
        capacity_stats: Full capacity statistics
    """
    try:
        capacity_events_collection = db_manager.get_collection("ipam_capacity_events")

        event = {
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_identifier": resource_identifier,
            "utilization_percentage": utilization_percentage,
            "threshold_type": threshold_type,
            "capacity_stats": capacity_stats,
            "timestamp": datetime.now(timezone.utc),
        }

        await capacity_events_collection.insert_one(event)

        logger.debug(
            f"Logged capacity event: {resource_type} {resource_identifier} at {utilization_percentage:.1f}%"
        )

    except Exception as e:
        logger.error(f"Error logging capacity event: {e}", exc_info=True)
