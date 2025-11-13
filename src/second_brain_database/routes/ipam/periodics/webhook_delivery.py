"""
IPAM Webhook Delivery Processor Background Task.

This module provides periodic monitoring and health checks for IPAM webhooks.
It monitors webhook delivery health and provides observability.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[IPAMWebhookProcessor]")


async def periodic_ipam_webhook_delivery():
    """
    Periodic background task to monitor webhook delivery health.

    Runs every hour (configurable) to:
    - Monitor webhook delivery success rates
    - Log webhook health metrics
    - Identify webhooks with high failure rates
    - Clean up old webhook delivery logs (> 30 days)

    This provides observability for the webhook system (Requirement 12, 13).

    Requirements: Req 12, 13
    """
    logger.info("Starting IPAM webhook delivery processor background task")

    # Get check interval from settings (default: 1 hour)
    check_interval = getattr(settings, "IPAM_WEBHOOK_PROCESSOR_INTERVAL", 3600)

    logger.info(f"IPAM webhook delivery processor configured: interval={check_interval}s")

    while True:
        try:
            logger.debug("Running IPAM webhook delivery health check...")
            start_time = datetime.now(timezone.utc)

            # Monitor webhook health
            health_stats = await _monitor_webhook_health()

            # Clean up old delivery logs
            cleaned_count = await _cleanup_old_delivery_logs()

            # Log summary
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            logger.info(
                f"IPAM webhook processor completed in {duration:.2f}s: "
                f"monitored {health_stats['total_webhooks']} webhooks, "
                f"cleaned {cleaned_count} old delivery logs"
            )

            # Sleep for configured interval
            await asyncio.sleep(check_interval)

        except asyncio.CancelledError:
            logger.info("IPAM webhook delivery processor task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in IPAM webhook delivery processor task: {e}", exc_info=True)
            # Sleep before retrying
            await asyncio.sleep(300)  # 5 minutes


async def _monitor_webhook_health() -> Dict[str, Any]:
    """
    Monitor webhook delivery health and log metrics.

    Returns:
        Dictionary with health statistics
    """
    stats = {
        "total_webhooks": 0,
        "active_webhooks": 0,
        "disabled_webhooks": 0,
        "webhooks_with_failures": 0
    }

    try:
        webhooks_collection = db_manager.get_collection("ipam_webhooks")
        deliveries_collection = db_manager.get_collection("ipam_webhook_deliveries")
        
        # Get all webhooks
        webhooks = await webhooks_collection.find({}).to_list(length=None)
        stats["total_webhooks"] = len(webhooks)

        # Calculate health metrics for each webhook
        for webhook in webhooks:
            webhook_id = webhook["_id"]
            is_active = webhook.get("is_active", True)
            failure_count = webhook.get("failure_count", 0)

            if is_active:
                stats["active_webhooks"] += 1
            else:
                stats["disabled_webhooks"] += 1

            if failure_count > 0:
                stats["webhooks_with_failures"] += 1

            # Get recent delivery stats (last 24 hours)
            twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
            recent_deliveries = await deliveries_collection.find({
                "webhook_id": webhook_id,
                "delivered_at": {"$gte": twenty_four_hours_ago}
            }).to_list(length=None)

            if recent_deliveries:
                successful = sum(
                    1 for d in recent_deliveries 
                    if d.get("status_code") and 200 <= d["status_code"] < 300
                )
                total = len(recent_deliveries)
                success_rate = (successful / total * 100) if total > 0 else 0

                # Log warning for webhooks with low success rate
                if success_rate < 50 and total >= 5:
                    logger.warning(
                        f"Webhook {webhook_id} has low success rate: "
                        f"{success_rate:.1f}% ({successful}/{total} successful) "
                        f"in last 24 hours"
                    )

                # Log info for healthy webhooks with activity
                elif total > 0:
                    logger.debug(
                        f"Webhook {webhook_id} health: "
                        f"{success_rate:.1f}% success rate ({successful}/{total}) "
                        f"in last 24 hours"
                    )

        # Log overall stats
        logger.info(
            f"Webhook health summary: {stats['active_webhooks']} active, "
            f"{stats['disabled_webhooks']} disabled, "
            f"{stats['webhooks_with_failures']} with failures"
        )

    except Exception as e:
        logger.error(f"Error monitoring webhook health: {e}", exc_info=True)

    return stats


async def _cleanup_old_delivery_logs() -> int:
    """
    Clean up webhook delivery logs older than 30 days.

    Returns:
        Number of delivery logs deleted
    """
    deleted_count = 0

    try:
        deliveries_collection = db_manager.get_collection("ipam_webhook_deliveries")
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=30)

        # Delete old delivery logs
        result = await deliveries_collection.delete_many({
            "delivered_at": {"$lt": cutoff_date}
        })

        deleted_count = result.deleted_count

        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} webhook delivery logs "
                f"older than {cutoff_date.isoformat()}"
            )

    except Exception as e:
        logger.error(f"Error cleaning up old delivery logs: {e}", exc_info=True)

    return deleted_count
