"""
Permanent token maintenance and cleanup service.

This module provides comprehensive maintenance utilities for permanent tokens including:
- Periodic cleanup for revoked tokens
- Database maintenance and optimization
- Token statistics and health monitoring
- Automated maintenance tasks and scheduling
"""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.routes.auth.services.permanent_tokens.analytics import USAGE_ANALYTICS_COLLECTION
from second_brain_database.routes.auth.services.permanent_tokens.audit_logger import AUDIT_COLLECTION

logger = get_logger(prefix="[Permanent Token Maintenance]")

# Maintenance configuration
REVOKED_TOKEN_CLEANUP_DAYS = 90  # Keep revoked tokens for 90 days
AUDIT_LOG_RETENTION_DAYS = 365  # Keep audit logs for 1 year
USAGE_ANALYTICS_RETENTION_DAYS = 180  # Keep usage analytics for 6 months
MAINTENANCE_BATCH_SIZE = 1000  # Process records in batches
HEALTH_CHECK_INTERVAL_HOURS = 6  # Run health checks every 6 hours


@dataclass
class MaintenanceStats:
    """Statistics from a maintenance operation."""

    operation: str
    timestamp: datetime
    records_processed: int
    records_cleaned: int
    errors_encountered: int
    duration_seconds: float
    details: Dict[str, Any]


@dataclass
class DatabaseHealth:
    """Database health metrics for permanent tokens."""

    timestamp: datetime
    total_tokens: int
    active_tokens: int
    revoked_tokens: int
    stale_tokens: int
    index_health: Dict[str, Any]
    collection_sizes: Dict[str, int]
    performance_metrics: Dict[str, Any]
    recommendations: List[str]


class PermanentTokenMaintenance:
    """
    Maintenance service for permanent token database operations.

    Provides automated cleanup, optimization, and health monitoring
    for permanent token collections and related data.
    """

    def __init__(self):
        self.last_maintenance_run = None
        self.maintenance_history = []
        self.max_history_entries = 100

    async def cleanup_revoked_tokens(self, days_old: int = REVOKED_TOKEN_CLEANUP_DAYS) -> MaintenanceStats:
        """
        Clean up revoked tokens older than specified days.

        Args:
            days_old: Number of days after which to delete revoked tokens

        Returns:
            MaintenanceStats: Statistics from the cleanup operation
        """
        start_time = datetime.utcnow()
        operation = f"cleanup_revoked_tokens_{days_old}d"

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            collection = db_manager.get_collection("permanent_tokens")

            # Find revoked tokens older than cutoff
            query = {"is_revoked": True, "revoked_at": {"$lt": cutoff_date}}

            # Count tokens to be deleted
            tokens_to_delete = await collection.count_documents(query)

            if tokens_to_delete == 0:
                logger.info("No revoked tokens found for cleanup")
                return MaintenanceStats(
                    operation=operation,
                    timestamp=start_time,
                    records_processed=0,
                    records_cleaned=0,
                    errors_encountered=0,
                    duration_seconds=0.0,
                    details={"cutoff_date": cutoff_date.isoformat()},
                )

            # Delete in batches to avoid memory issues
            total_deleted = 0
            errors = 0

            while True:
                # Get a batch of tokens to delete
                cursor = collection.find(query).limit(MAINTENANCE_BATCH_SIZE)
                batch = await cursor.to_list(length=MAINTENANCE_BATCH_SIZE)

                if not batch:
                    break

                # Extract token hashes for cache cleanup
                token_hashes = [token["token_hash"] for token in batch]
                token_ids = [token.get("token_id", "unknown") for token in batch]

                try:
                    # Delete the batch
                    batch_ids = [token["_id"] for token in batch]
                    result = await collection.delete_many({"_id": {"$in": batch_ids}})

                    deleted_count = result.deleted_count
                    total_deleted += deleted_count

                    # Clean up related cache entries
                    await self._cleanup_token_caches(token_hashes)

                    logger.debug("Deleted batch of %d revoked tokens", deleted_count)

                except Exception as e:
                    logger.error("Error deleting batch of revoked tokens: %s", e)
                    errors += 1

            duration = (datetime.utcnow() - start_time).total_seconds()

            stats = MaintenanceStats(
                operation=operation,
                timestamp=start_time,
                records_processed=tokens_to_delete,
                records_cleaned=total_deleted,
                errors_encountered=errors,
                duration_seconds=duration,
                details={
                    "cutoff_date": cutoff_date.isoformat(),
                    "days_old": days_old,
                    "batch_size": MAINTENANCE_BATCH_SIZE,
                },
            )

            logger.info("Cleanup completed: %d revoked tokens deleted in %.2fs", total_deleted, duration)
            self._record_maintenance_stats(stats)

            return stats

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error("Error during revoked token cleanup: %s", e)

            stats = MaintenanceStats(
                operation=operation,
                timestamp=start_time,
                records_processed=0,
                records_cleaned=0,
                errors_encountered=1,
                duration_seconds=duration,
                details={"error": str(e)},
            )

            self._record_maintenance_stats(stats)
            return stats

    async def cleanup_audit_logs(self, days_old: int = AUDIT_LOG_RETENTION_DAYS) -> MaintenanceStats:
        """
        Clean up audit logs older than specified days.

        Args:
            days_old: Number of days after which to delete audit logs

        Returns:
            MaintenanceStats: Statistics from the cleanup operation
        """
        start_time = datetime.utcnow()
        operation = f"cleanup_audit_logs_{days_old}d"

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            collection = db_manager.get_collection(AUDIT_COLLECTION)

            # Count logs to be deleted
            query = {"timestamp": {"$lt": cutoff_date}}
            logs_to_delete = await collection.count_documents(query)

            if logs_to_delete == 0:
                logger.info("No old audit logs found for cleanup")
                return MaintenanceStats(
                    operation=operation,
                    timestamp=start_time,
                    records_processed=0,
                    records_cleaned=0,
                    errors_encountered=0,
                    duration_seconds=0.0,
                    details={"cutoff_date": cutoff_date.isoformat()},
                )

            # Delete in batches
            total_deleted = 0
            errors = 0

            while True:
                try:
                    result = await collection.delete_many(query, {"limit": MAINTENANCE_BATCH_SIZE})
                    deleted_count = result.deleted_count

                    if deleted_count == 0:
                        break

                    total_deleted += deleted_count
                    logger.debug("Deleted batch of %d audit logs", deleted_count)

                except Exception as e:
                    logger.error("Error deleting batch of audit logs: %s", e)
                    errors += 1
                    break

            duration = (datetime.utcnow() - start_time).total_seconds()

            stats = MaintenanceStats(
                operation=operation,
                timestamp=start_time,
                records_processed=logs_to_delete,
                records_cleaned=total_deleted,
                errors_encountered=errors,
                duration_seconds=duration,
                details={"cutoff_date": cutoff_date.isoformat(), "days_old": days_old},
            )

            logger.info("Audit log cleanup completed: %d logs deleted in %.2fs", total_deleted, duration)
            self._record_maintenance_stats(stats)

            return stats

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error("Error during audit log cleanup: %s", e)

            stats = MaintenanceStats(
                operation=operation,
                timestamp=start_time,
                records_processed=0,
                records_cleaned=0,
                errors_encountered=1,
                duration_seconds=duration,
                details={"error": str(e)},
            )

            self._record_maintenance_stats(stats)
            return stats

    async def cleanup_usage_analytics(self, days_old: int = USAGE_ANALYTICS_RETENTION_DAYS) -> MaintenanceStats:
        """
        Clean up usage analytics data older than specified days.

        Args:
            days_old: Number of days after which to delete usage analytics

        Returns:
            MaintenanceStats: Statistics from the cleanup operation
        """
        start_time = datetime.utcnow()
        operation = f"cleanup_usage_analytics_{days_old}d"

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            collection = db_manager.get_collection(USAGE_ANALYTICS_COLLECTION)

            # Count records to be deleted
            query = {"timestamp": {"$lt": cutoff_date}}
            records_to_delete = await collection.count_documents(query)

            if records_to_delete == 0:
                logger.info("No old usage analytics found for cleanup")
                return MaintenanceStats(
                    operation=operation,
                    timestamp=start_time,
                    records_processed=0,
                    records_cleaned=0,
                    errors_encountered=0,
                    duration_seconds=0.0,
                    details={"cutoff_date": cutoff_date.isoformat()},
                )

            # Delete old records
            result = await collection.delete_many(query)
            total_deleted = result.deleted_count

            duration = (datetime.utcnow() - start_time).total_seconds()

            stats = MaintenanceStats(
                operation=operation,
                timestamp=start_time,
                records_processed=records_to_delete,
                records_cleaned=total_deleted,
                errors_encountered=0,
                duration_seconds=duration,
                details={"cutoff_date": cutoff_date.isoformat(), "days_old": days_old},
            )

            logger.info("Usage analytics cleanup completed: %d records deleted in %.2fs", total_deleted, duration)
            self._record_maintenance_stats(stats)

            return stats

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error("Error during usage analytics cleanup: %s", e)

            stats = MaintenanceStats(
                operation=operation,
                timestamp=start_time,
                records_processed=0,
                records_cleaned=0,
                errors_encountered=1,
                duration_seconds=duration,
                details={"error": str(e)},
            )

            self._record_maintenance_stats(stats)
            return stats

    async def optimize_database_indexes(self) -> MaintenanceStats:
        """
        Optimize database indexes for permanent token collections.

        Returns:
            MaintenanceStats: Statistics from the optimization operation
        """
        start_time = datetime.utcnow()
        operation = "optimize_database_indexes"

        try:
            collections_to_optimize = ["permanent_tokens", AUDIT_COLLECTION, USAGE_ANALYTICS_COLLECTION]

            optimized_count = 0
            errors = 0
            details = {}

            for collection_name in collections_to_optimize:
                try:
                    collection = db_manager.get_collection(collection_name)

                    # Get index statistics
                    index_stats = await collection.index_stats().to_list(length=None)
                    details[f"{collection_name}_indexes"] = len(index_stats)

                    # Reindex collection (MongoDB handles this automatically in most cases)
                    # This is mainly for monitoring and ensuring indexes are healthy
                    await collection.reindex()
                    optimized_count += 1

                    logger.debug("Optimized indexes for collection: %s", collection_name)

                except Exception as e:
                    logger.error("Error optimizing indexes for %s: %s", collection_name, e)
                    errors += 1

            duration = (datetime.utcnow() - start_time).total_seconds()

            stats = MaintenanceStats(
                operation=operation,
                timestamp=start_time,
                records_processed=len(collections_to_optimize),
                records_cleaned=optimized_count,
                errors_encountered=errors,
                duration_seconds=duration,
                details=details,
            )

            logger.info("Index optimization completed: %d collections optimized in %.2fs", optimized_count, duration)
            self._record_maintenance_stats(stats)

            return stats

        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.error("Error during index optimization: %s", e)

            stats = MaintenanceStats(
                operation=operation,
                timestamp=start_time,
                records_processed=0,
                records_cleaned=0,
                errors_encountered=1,
                duration_seconds=duration,
                details={"error": str(e)},
            )

            self._record_maintenance_stats(stats)
            return stats

    async def get_database_health(self) -> DatabaseHealth:
        """
        Get comprehensive database health metrics for permanent tokens.

        Returns:
            DatabaseHealth: Complete health assessment
        """
        try:
            now = datetime.utcnow()

            # Get token statistics
            tokens_collection = db_manager.get_collection("permanent_tokens")

            total_tokens = await tokens_collection.count_documents({})
            active_tokens = await tokens_collection.count_documents({"is_revoked": False})
            revoked_tokens = await tokens_collection.count_documents({"is_revoked": True})

            # Count stale tokens (not used in 30 days)
            stale_cutoff = now - timedelta(days=30)
            stale_tokens = await tokens_collection.count_documents(
                {"is_revoked": False, "$or": [{"last_used_at": {"$lt": stale_cutoff}}, {"last_used_at": None}]}
            )

            # Get index health
            index_health = await self._get_index_health()

            # Get collection sizes
            collection_sizes = await self._get_collection_sizes()

            # Get performance metrics
            performance_metrics = await self._get_performance_metrics()

            # Generate recommendations
            recommendations = self._generate_health_recommendations(
                total_tokens, active_tokens, revoked_tokens, stale_tokens, index_health, collection_sizes
            )

            return DatabaseHealth(
                timestamp=now,
                total_tokens=total_tokens,
                active_tokens=active_tokens,
                revoked_tokens=revoked_tokens,
                stale_tokens=stale_tokens,
                index_health=index_health,
                collection_sizes=collection_sizes,
                performance_metrics=performance_metrics,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.error("Error getting database health: %s", e)
            return DatabaseHealth(
                timestamp=datetime.utcnow(),
                total_tokens=0,
                active_tokens=0,
                revoked_tokens=0,
                stale_tokens=0,
                index_health={"error": str(e)},
                collection_sizes={},
                performance_metrics={},
                recommendations=[f"Error getting health metrics: {str(e)}"],
            )

    async def run_full_maintenance(self) -> List[MaintenanceStats]:
        """
        Run a complete maintenance cycle including all cleanup operations.

        Returns:
            List[MaintenanceStats]: Statistics from all maintenance operations
        """
        logger.info("Starting full maintenance cycle")
        start_time = datetime.utcnow()

        maintenance_results = []

        try:
            # 1. Clean up revoked tokens
            logger.info("Running revoked token cleanup...")
            revoked_cleanup = await self.cleanup_revoked_tokens()
            maintenance_results.append(revoked_cleanup)

            # 2. Clean up old audit logs
            logger.info("Running audit log cleanup...")
            audit_cleanup = await self.cleanup_audit_logs()
            maintenance_results.append(audit_cleanup)

            # 3. Clean up old usage analytics
            logger.info("Running usage analytics cleanup...")
            analytics_cleanup = await self.cleanup_usage_analytics()
            maintenance_results.append(analytics_cleanup)

            # 4. Optimize database indexes
            logger.info("Running index optimization...")
            index_optimization = await self.optimize_database_indexes()
            maintenance_results.append(index_optimization)

            # 5. Clean up expired cache entries
            logger.info("Running cache cleanup...")
            from .cache_manager import cleanup_expired_cache_entries

            cache_cleanup_count = await cleanup_expired_cache_entries()

            cache_stats = MaintenanceStats(
                operation="cleanup_expired_cache",
                timestamp=datetime.utcnow(),
                records_processed=cache_cleanup_count,
                records_cleaned=cache_cleanup_count,
                errors_encountered=0,
                duration_seconds=1.0,
                details={"cache_entries_cleaned": cache_cleanup_count},
            )
            maintenance_results.append(cache_stats)

            total_duration = (datetime.utcnow() - start_time).total_seconds()

            # Log summary
            total_cleaned = sum(stats.records_cleaned for stats in maintenance_results)
            total_errors = sum(stats.errors_encountered for stats in maintenance_results)

            logger.info(
                "Full maintenance cycle completed in %.2fs: %d records cleaned, %d errors",
                total_duration,
                total_cleaned,
                total_errors,
            )

            self.last_maintenance_run = start_time

            return maintenance_results

        except Exception as e:
            logger.error("Error during full maintenance cycle: %s", e)
            return maintenance_results

    async def _cleanup_token_caches(self, token_hashes: List[str]):
        """Clean up Redis cache entries for deleted tokens."""
        try:
            from .validator import invalidate_token_cache

            for token_hash in token_hashes:
                await invalidate_token_cache(token_hash)

        except Exception as e:
            logger.error("Error cleaning up token caches: %s", e)

    async def _get_index_health(self) -> Dict[str, Any]:
        """Get index health information for permanent token collections."""
        try:
            index_health = {}

            collections = ["permanent_tokens", AUDIT_COLLECTION, USAGE_ANALYTICS_COLLECTION]

            for collection_name in collections:
                collection = db_manager.get_collection(collection_name)
                indexes = await collection.list_indexes().to_list(length=None)

                index_health[collection_name] = {
                    "index_count": len(indexes),
                    "indexes": [idx["name"] for idx in indexes],
                }

            return index_health

        except Exception as e:
            logger.error("Error getting index health: %s", e)
            return {"error": str(e)}

    async def _get_collection_sizes(self) -> Dict[str, int]:
        """Get collection sizes for permanent token related collections."""
        try:
            collection_sizes = {}

            collections = ["permanent_tokens", AUDIT_COLLECTION, USAGE_ANALYTICS_COLLECTION]

            for collection_name in collections:
                collection = db_manager.get_collection(collection_name)
                count = await collection.count_documents({})
                collection_sizes[collection_name] = count

            return collection_sizes

        except Exception as e:
            logger.error("Error getting collection sizes: %s", e)
            return {"error": str(e)}

    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for permanent token operations."""
        try:
            # Get recent performance data from monitoring
            from .monitoring import cache_monitor

            metrics = cache_monitor.get_current_metrics(window_minutes=60)

            return {
                "cache_hit_rate": metrics.hit_rate,
                "avg_response_time_ms": metrics.avg_response_time_ms,
                "operations_per_second": metrics.operations_per_second,
                "error_rate": metrics.error_rate,
            }

        except Exception as e:
            logger.error("Error getting performance metrics: %s", e)
            return {"error": str(e)}

    def _generate_health_recommendations(
        self,
        total_tokens: int,
        active_tokens: int,
        revoked_tokens: int,
        stale_tokens: int,
        index_health: Dict[str, Any],
        collection_sizes: Dict[str, int],
    ) -> List[str]:
        """Generate health recommendations based on metrics."""
        recommendations = []

        # Check for high number of revoked tokens
        if revoked_tokens > 0 and revoked_tokens / max(total_tokens, 1) > 0.3:
            recommendations.append(f"High number of revoked tokens ({revoked_tokens}). Consider running cleanup.")

        # Check for stale tokens
        if stale_tokens > 0 and stale_tokens / max(active_tokens, 1) > 0.5:
            recommendations.append(
                f"Many stale tokens detected ({stale_tokens}). Consider notifying users or implementing expiration."
            )

        # Check collection sizes
        if collection_sizes.get(AUDIT_COLLECTION, 0) > 100000:
            recommendations.append("Large audit log collection. Consider implementing log rotation or archival.")

        if collection_sizes.get(USAGE_ANALYTICS_COLLECTION, 0) > 50000:
            recommendations.append("Large usage analytics collection. Consider data aggregation or cleanup.")

        # Check if no tokens exist
        if total_tokens == 0:
            recommendations.append("No permanent tokens found. System appears to be unused.")

        return recommendations

    def _record_maintenance_stats(self, stats: MaintenanceStats):
        """Record maintenance statistics for history tracking."""
        self.maintenance_history.append(stats)

        # Keep only the most recent entries
        if len(self.maintenance_history) > self.max_history_entries:
            self.maintenance_history = self.maintenance_history[-self.max_history_entries :]

    def get_maintenance_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent maintenance history."""
        recent_history = self.maintenance_history[-limit:] if self.maintenance_history else []
        return [asdict(stats) for stats in recent_history]


# Global maintenance instance
token_maintenance = PermanentTokenMaintenance()


# Convenience functions
async def run_token_cleanup(days_old: int = REVOKED_TOKEN_CLEANUP_DAYS) -> MaintenanceStats:
    """Run cleanup for revoked tokens."""
    return await token_maintenance.cleanup_revoked_tokens(days_old)


async def run_audit_cleanup(days_old: int = AUDIT_LOG_RETENTION_DAYS) -> MaintenanceStats:
    """Run cleanup for audit logs."""
    return await token_maintenance.cleanup_audit_logs(days_old)


async def run_full_maintenance() -> List[MaintenanceStats]:
    """Run complete maintenance cycle."""
    return await token_maintenance.run_full_maintenance()


async def get_database_health() -> DatabaseHealth:
    """Get database health metrics."""
    return await token_maintenance.get_database_health()


async def start_periodic_maintenance():
    """
    Start periodic maintenance tasks in the background.
    This should be called during application startup.
    """

    async def maintenance_loop():
        while True:
            try:
                # Wait for the maintenance interval (6 hours)
                await asyncio.sleep(HEALTH_CHECK_INTERVAL_HOURS * 3600)

                # Run full maintenance
                logger.info("Starting scheduled maintenance cycle")
                await token_maintenance.run_full_maintenance()

            except Exception as e:
                logger.error("Error in periodic maintenance: %s", e)

    # Start the maintenance loop as a background task
    asyncio.create_task(maintenance_loop())
    logger.info("Started periodic maintenance tasks (interval: %dh)", HEALTH_CHECK_INTERVAL_HOURS)
