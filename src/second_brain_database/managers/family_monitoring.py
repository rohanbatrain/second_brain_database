"""
Family Management System Monitoring and Observability.

This module provides comprehensive monitoring, metrics collection, and observability
for the family management system including:
- Structured logging for family operations
- Performance metrics and alerting
- Health checks for system components
- Operational dashboards and reporting

Enterprise Features:
    - Structured JSON logging for all family operations
    - Performance metrics with configurable thresholds
    - Health check endpoints for monitoring systems
    - Alerting for critical family system events
    - Operational metrics for production deployment
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import json
import os

from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.database import db_manager
from second_brain_database.managers.redis_manager import redis_manager
from second_brain_database.config import settings

# Specialized loggers for different aspects of family monitoring
family_ops_logger = get_logger(name="Family_Operations", prefix="[FAMILY_OPS]")
family_perf_logger = get_logger(name="Family_Performance", prefix="[FAMILY_PERF]")
family_health_logger = get_logger(name="Family_Health", prefix="[FAMILY_HEALTH]")
family_metrics_logger = get_logger(name="Family_Metrics", prefix="[FAMILY_METRICS]")
family_alerts_logger = get_logger(name="Family_Alerts", prefix="[FAMILY_ALERTS]")

# Performance thresholds for alerting
SLOW_OPERATION_THRESHOLD = 2.0  # seconds
VERY_SLOW_OPERATION_THRESHOLD = 5.0  # seconds
HIGH_ERROR_RATE_THRESHOLD = 0.05  # 5% error rate
CRITICAL_ERROR_RATE_THRESHOLD = 0.10  # 10% error rate

# Health check intervals
HEALTH_CHECK_INTERVAL = 300  # 5 minutes
METRICS_COLLECTION_INTERVAL = 60  # 1 minute
ALERT_COOLDOWN_PERIOD = 1800  # 30 minutes


class FamilyOperationType(Enum):
    """Family operation types for monitoring."""
    FAMILY_CREATE = "family_create"
    FAMILY_DELETE = "family_delete"
    MEMBER_INVITE = "member_invite"
    MEMBER_JOIN = "member_join"
    MEMBER_REMOVE = "member_remove"
    ADMIN_PROMOTE = "admin_promote"
    ADMIN_DEMOTE = "admin_demote"
    SBD_DEPOSIT = "sbd_deposit"
    SBD_SPEND = "sbd_spend"
    SBD_FREEZE = "sbd_freeze"
    SBD_UNFREEZE = "sbd_unfreeze"
    TOKEN_REQUEST = "token_request"
    TOKEN_APPROVE = "token_approve"
    TOKEN_DENY = "token_deny"
    NOTIFICATION_SEND = "notification_send"
    INVITATION_SEND = "invitation_send"
    INVITATION_ACCEPT = "invitation_accept"
    INVITATION_DECLINE = "invitation_decline"


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class FamilyOperationContext:
    """Context for family operations monitoring."""
    operation_type: FamilyOperationType
    family_id: Optional[str] = None
    user_id: Optional[str] = None
    target_user_id: Optional[str] = None
    amount: Optional[int] = None
    duration: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None
    request_id: Optional[str] = None
    ip_address: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class FamilyHealthStatus:
    """Health status for family system components."""
    component: str
    healthy: bool
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    last_check: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.last_check is None:
            self.last_check = datetime.now(timezone.utc).isoformat()


@dataclass
class FamilyMetrics:
    """Family system metrics for monitoring."""
    timestamp: str
    total_families: int
    active_families: int
    total_members: int
    total_invitations_pending: int
    total_token_requests_pending: int
    avg_family_size: float
    operations_per_minute: Dict[str, int]
    error_rates: Dict[str, float]
    performance_metrics: Dict[str, float]
    sbd_metrics: Dict[str, Any]

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class FamilyMonitor:
    """
    Comprehensive monitoring and observability for the family management system.

    This class provides:
    - Structured logging for all family operations
    - Performance monitoring with configurable thresholds
    - Health checks for system components
    - Metrics collection and alerting
    - Operational dashboards and reporting
    """

    def __init__(self):
        self.logger = family_ops_logger
        self.perf_logger = family_perf_logger
        self.health_logger = family_health_logger
        self.metrics_logger = family_metrics_logger
        self.alerts_logger = family_alerts_logger

        # Metrics storage
        self._operation_counts = {}
        self._error_counts = {}
        self._performance_data = {}
        self._last_alert_times = {}

        # Health status cache
        self._health_status_cache = {}
        self._last_health_check = None

    async def log_family_operation(self, context: FamilyOperationContext) -> None:
        """
        Log a family operation with comprehensive context and structured data.

        Args:
            context: Operation context with all relevant details
        """
        # Create structured log entry
        log_entry = {
            "event": "family_operation",
            "operation_type": context.operation_type.value,
            "timestamp": context.timestamp,
            "family_id": context.family_id,
            "user_id": context.user_id,
            "target_user_id": context.target_user_id,
            "amount": context.amount,
            "duration": context.duration,
            "success": context.success,
            "error_message": context.error_message,
            "request_id": context.request_id,
            "ip_address": context.ip_address,
            "metadata": context.metadata or {},
            "process": os.getpid(),
            "host": os.getenv("HOSTNAME", "unknown"),
            "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
            "env": os.getenv("ENV", "dev"),
        }

        # Log the operation
        if context.success:
            self.logger.info(log_entry)
        else:
            self.logger.error(log_entry)

        # Update metrics
        await self._update_operation_metrics(context)

        # Check for performance alerts
        if context.duration and context.duration > SLOW_OPERATION_THRESHOLD:
            await self._check_performance_alerts(context)

        # Check for error rate alerts
        if not context.success:
            await self._check_error_rate_alerts(context)

    async def log_family_performance(
        self,
        operation_type: FamilyOperationType,
        duration: float,
        success: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log performance metrics for family operations.

        Args:
            operation_type: Type of operation performed
            duration: Operation duration in seconds
            success: Whether operation was successful
            metadata: Additional performance metadata
        """
        perf_entry = {
            "event": "family_performance",
            "operation_type": operation_type.value,
            "duration": duration,
            "success": success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "process": os.getpid(),
            "host": os.getenv("HOSTNAME", "unknown"),
            "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
            "env": os.getenv("ENV", "dev"),
        }

        # Log performance data
        if duration > VERY_SLOW_OPERATION_THRESHOLD:
            self.perf_logger.warning(perf_entry)
        elif duration > SLOW_OPERATION_THRESHOLD:
            self.perf_logger.info(perf_entry)
        else:
            self.perf_logger.debug(perf_entry)

        # Store performance data for metrics
        op_key = operation_type.value
        if op_key not in self._performance_data:
            self._performance_data[op_key] = []

        self._performance_data[op_key].append({
            "duration": duration,
            "success": success,
            "timestamp": time.time()
        })

        # Keep only recent data (last hour)
        cutoff_time = time.time() - 3600
        self._performance_data[op_key] = [
            data for data in self._performance_data[op_key]
            if data["timestamp"] > cutoff_time
        ]

    async def check_family_system_health(self) -> Dict[str, FamilyHealthStatus]:
        """
        Perform comprehensive health checks on family system components.

        Returns:
            Dictionary of component health statuses
        """
        health_results = {}

        # Check database connectivity for family collections
        health_results["database"] = await self._check_database_health()

        # Check Redis connectivity for family caching
        health_results["redis"] = await self._check_redis_health()

        # Check family collections integrity
        health_results["family_collections"] = await self._check_family_collections_health()

        # Check SBD token integration
        health_results["sbd_integration"] = await self._check_sbd_integration_health()

        # Check email system for invitations
        health_results["email_system"] = await self._check_email_system_health()

        # Check notification system
        health_results["notification_system"] = await self._check_notification_system_health()

        # Update health status cache
        self._health_status_cache = health_results
        self._last_health_check = datetime.now(timezone.utc)

        # Log overall health status
        overall_healthy = all(status.healthy for status in health_results.values())
        health_summary = {
            "event": "family_health_check",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_healthy": overall_healthy,
            "components": {name: status.healthy for name, status in health_results.items()},
            "response_times": {name: status.response_time for name, status in health_results.items()},
            "process": os.getpid(),
            "host": os.getenv("HOSTNAME", "unknown"),
            "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
            "env": os.getenv("ENV", "dev"),
        }

        if overall_healthy:
            self.health_logger.info(health_summary)
        else:
            self.health_logger.error(health_summary)
            await self._send_health_alert(health_results)

        return health_results

    async def collect_family_metrics(self) -> FamilyMetrics:
        """
        Collect comprehensive metrics about the family system.

        Returns:
            FamilyMetrics object with current system metrics
        """
        start_time = time.time()

        try:
            # Collect basic family statistics
            families_collection = db_manager.get_collection("families")
            relationships_collection = db_manager.get_collection("family_relationships")
            invitations_collection = db_manager.get_collection("family_invitations")
            token_requests_collection = db_manager.get_collection("family_token_requests")

            # Get family counts
            total_families = await families_collection.count_documents({})
            active_families = await families_collection.count_documents({"is_active": True})

            # Get member counts
            total_relationships = await relationships_collection.count_documents({"status": "active"})
            total_members = total_relationships  # Each relationship represents a member connection

            # Get pending items
            pending_invitations = await invitations_collection.count_documents({"status": "pending"})
            pending_token_requests = await token_requests_collection.count_documents({"status": "pending"})

            # Calculate average family size
            if active_families > 0:
                pipeline = [
                    {"$match": {"is_active": True}},
                    {"$group": {"_id": None, "avg_size": {"$avg": "$member_count"}}}
                ]
                avg_result = await families_collection.aggregate(pipeline).to_list(length=1)
                avg_family_size = avg_result[0]["avg_size"] if avg_result else 0.0
            else:
                avg_family_size = 0.0

            # Get SBD metrics
            sbd_metrics = await self._collect_sbd_metrics()

            # Calculate operation rates and error rates
            operations_per_minute = self._calculate_operation_rates()
            error_rates = self._calculate_error_rates()
            performance_metrics = self._calculate_performance_metrics()

            metrics = FamilyMetrics(
                timestamp=datetime.now(timezone.utc).isoformat(),
                total_families=total_families,
                active_families=active_families,
                total_members=total_members,
                total_invitations_pending=pending_invitations,
                total_token_requests_pending=pending_token_requests,
                avg_family_size=avg_family_size,
                operations_per_minute=operations_per_minute,
                error_rates=error_rates,
                performance_metrics=performance_metrics,
                sbd_metrics=sbd_metrics
            )

            # Log metrics
            metrics_entry = {
                "event": "family_metrics_collection",
                "timestamp": metrics.timestamp,
                "collection_duration": time.time() - start_time,
                "metrics": asdict(metrics),
                "process": os.getpid(),
                "host": os.getenv("HOSTNAME", "unknown"),
                "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
                "env": os.getenv("ENV", "dev"),
            }

            self.metrics_logger.info(metrics_entry)

            # Check for metric-based alerts
            await self._check_metrics_alerts(metrics)

            return metrics

        except Exception as e:
            self.metrics_logger.error(
                "Failed to collect family metrics: %s",
                str(e),
                extra={
                    "collection_duration": time.time() - start_time,
                    "error": str(e)
                }
            )
            raise

    async def send_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send an alert for family system issues.

        Args:
            severity: Alert severity level
            title: Alert title
            message: Alert message
            metadata: Additional alert metadata
        """
        alert_key = f"{severity.value}_{title}"
        current_time = time.time()

        # Check alert cooldown to prevent spam
        if alert_key in self._last_alert_times:
            if current_time - self._last_alert_times[alert_key] < ALERT_COOLDOWN_PERIOD:
                return  # Skip alert due to cooldown

        alert_entry = {
            "event": "family_system_alert",
            "severity": severity.value,
            "title": title,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "process": os.getpid(),
            "host": os.getenv("HOSTNAME", "unknown"),
            "app": os.getenv("APP_NAME", "Second_Brain_Database-app"),
            "env": os.getenv("ENV", "dev"),
        }

        # Log alert based on severity
        if severity == AlertSeverity.CRITICAL:
            self.alerts_logger.critical(alert_entry)
        elif severity == AlertSeverity.ERROR:
            self.alerts_logger.error(alert_entry)
        elif severity == AlertSeverity.WARNING:
            self.alerts_logger.warning(alert_entry)
        else:
            self.alerts_logger.info(alert_entry)

        # Update last alert time
        self._last_alert_times[alert_key] = current_time

        # TODO: Integrate with external alerting systems (PagerDuty, Slack, etc.)
        # This would be configured based on deployment environment

    async def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status of family system components.

        Returns:
            Dictionary with health status information
        """
        # Return cached status if recent
        if (self._last_health_check and
            datetime.now(timezone.utc) - self._last_health_check < timedelta(minutes=5)):
            return {
                "overall_healthy": all(status.healthy for status in self._health_status_cache.values()),
                "components": {name: asdict(status) for name, status in self._health_status_cache.items()},
                "last_check": self._last_health_check.isoformat(),
                "cache_hit": True
            }

        # Perform fresh health check
        health_results = await self.check_family_system_health()

        return {
            "overall_healthy": all(status.healthy for status in health_results.values()),
            "components": {name: asdict(status) for name, status in health_results.items()},
            "last_check": self._last_health_check.isoformat(),
            "cache_hit": False
        }

    async def get_performance_summary(self) -> Dict[str, Any]:
        """
        Get performance summary for family operations.

        Returns:
            Dictionary with performance metrics and summaries
        """
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operations": {},
            "overall_stats": {
                "total_operations": 0,
                "avg_duration": 0.0,
                "success_rate": 0.0,
                "slow_operations": 0,
                "very_slow_operations": 0
            }
        }

        total_ops = 0
        total_duration = 0.0
        total_success = 0
        slow_ops = 0
        very_slow_ops = 0

        for op_type, data_points in self._performance_data.items():
            if not data_points:
                continue

            durations = [d["duration"] for d in data_points]
            successes = [d["success"] for d in data_points]

            op_stats = {
                "count": len(data_points),
                "avg_duration": sum(durations) / len(durations),
                "min_duration": min(durations),
                "max_duration": max(durations),
                "success_rate": sum(successes) / len(successes),
                "slow_operations": len([d for d in durations if d > SLOW_OPERATION_THRESHOLD]),
                "very_slow_operations": len([d for d in durations if d > VERY_SLOW_OPERATION_THRESHOLD])
            }

            summary["operations"][op_type] = op_stats

            # Update overall stats
            total_ops += len(data_points)
            total_duration += sum(durations)
            total_success += sum(successes)
            slow_ops += op_stats["slow_operations"]
            very_slow_ops += op_stats["very_slow_operations"]

        if total_ops > 0:
            summary["overall_stats"] = {
                "total_operations": total_ops,
                "avg_duration": total_duration / total_ops,
                "success_rate": total_success / total_ops,
                "slow_operations": slow_ops,
                "very_slow_operations": very_slow_ops
            }

        return summary

    # Private helper methods

    async def _update_operation_metrics(self, context: FamilyOperationContext) -> None:
        """Update operation metrics counters."""
        op_key = context.operation_type.value
        current_minute = int(time.time() // 60)

        # Update operation counts
        if op_key not in self._operation_counts:
            self._operation_counts[op_key] = {}
        if current_minute not in self._operation_counts[op_key]:
            self._operation_counts[op_key][current_minute] = 0
        self._operation_counts[op_key][current_minute] += 1

        # Update error counts
        if not context.success:
            if op_key not in self._error_counts:
                self._error_counts[op_key] = {}
            if current_minute not in self._error_counts[op_key]:
                self._error_counts[op_key][current_minute] = 0
            self._error_counts[op_key][current_minute] += 1

        # Clean old data (keep last hour)
        cutoff_minute = current_minute - 60
        for op_type in self._operation_counts:
            self._operation_counts[op_type] = {
                minute: count for minute, count in self._operation_counts[op_type].items()
                if minute > cutoff_minute
            }
        for op_type in self._error_counts:
            self._error_counts[op_type] = {
                minute: count for minute, count in self._error_counts[op_type].items()
                if minute > cutoff_minute
            }

    async def _check_performance_alerts(self, context: FamilyOperationContext) -> None:
        """Check for performance-based alerts."""
        if not context.duration:
            return

        if context.duration > VERY_SLOW_OPERATION_THRESHOLD:
            await self.send_alert(
                AlertSeverity.ERROR,
                "Very Slow Family Operation",
                f"Operation {context.operation_type.value} took {context.duration:.2f}s",
                {
                    "operation_type": context.operation_type.value,
                    "duration": context.duration,
                    "family_id": context.family_id,
                    "user_id": context.user_id
                }
            )
        elif context.duration > SLOW_OPERATION_THRESHOLD:
            await self.send_alert(
                AlertSeverity.WARNING,
                "Slow Family Operation",
                f"Operation {context.operation_type.value} took {context.duration:.2f}s",
                {
                    "operation_type": context.operation_type.value,
                    "duration": context.duration,
                    "family_id": context.family_id,
                    "user_id": context.user_id
                }
            )

    async def _check_error_rate_alerts(self, context: FamilyOperationContext) -> None:
        """Check for error rate-based alerts."""
        op_key = context.operation_type.value
        current_minute = int(time.time() // 60)

        # Calculate error rate for last 5 minutes
        total_ops = 0
        total_errors = 0

        for minute in range(current_minute - 4, current_minute + 1):
            if op_key in self._operation_counts and minute in self._operation_counts[op_key]:
                total_ops += self._operation_counts[op_key][minute]
            if op_key in self._error_counts and minute in self._error_counts[op_key]:
                total_errors += self._error_counts[op_key][minute]

        if total_ops > 0:
            error_rate = total_errors / total_ops

            if error_rate > CRITICAL_ERROR_RATE_THRESHOLD:
                await self.send_alert(
                    AlertSeverity.CRITICAL,
                    "Critical Error Rate",
                    f"Operation {op_key} has {error_rate:.1%} error rate",
                    {
                        "operation_type": op_key,
                        "error_rate": error_rate,
                        "total_operations": total_ops,
                        "total_errors": total_errors,
                        "time_window": "5 minutes"
                    }
                )
            elif error_rate > HIGH_ERROR_RATE_THRESHOLD:
                await self.send_alert(
                    AlertSeverity.WARNING,
                    "High Error Rate",
                    f"Operation {op_key} has {error_rate:.1%} error rate",
                    {
                        "operation_type": op_key,
                        "error_rate": error_rate,
                        "total_operations": total_ops,
                        "total_errors": total_errors,
                        "time_window": "5 minutes"
                    }
                )

    async def _check_database_health(self) -> FamilyHealthStatus:
        """Check database health for family collections."""
        start_time = time.time()

        try:
            # Test basic connectivity
            await db_manager.client.admin.command("ping")

            # Test family collections access
            families_collection = db_manager.get_collection("families")
            await families_collection.find_one({}, {"_id": 1})

            response_time = time.time() - start_time

            return FamilyHealthStatus(
                component="database",
                healthy=True,
                response_time=response_time,
                metadata={"collections_tested": ["families"]}
            )

        except Exception as e:
            response_time = time.time() - start_time
            return FamilyHealthStatus(
                component="database",
                healthy=False,
                response_time=response_time,
                error_message=str(e)
            )

    async def _check_redis_health(self) -> FamilyHealthStatus:
        """Check Redis health for family caching."""
        start_time = time.time()

        try:
            redis_conn = await redis_manager.get_redis()
            await redis_conn.ping()

            response_time = time.time() - start_time

            return FamilyHealthStatus(
                component="redis",
                healthy=True,
                response_time=response_time
            )

        except Exception as e:
            response_time = time.time() - start_time
            return FamilyHealthStatus(
                component="redis",
                healthy=False,
                response_time=response_time,
                error_message=str(e)
            )

    async def _check_family_collections_health(self) -> FamilyHealthStatus:
        """Check integrity of family collections."""
        start_time = time.time()

        try:
            collections_to_check = [
                "families",
                "family_relationships",
                "family_invitations",
                "family_notifications",
                "family_token_requests"
            ]

            collection_stats = {}
            for collection_name in collections_to_check:
                collection = db_manager.get_collection(collection_name)
                count = await collection.count_documents({})
                collection_stats[collection_name] = count

            response_time = time.time() - start_time

            return FamilyHealthStatus(
                component="family_collections",
                healthy=True,
                response_time=response_time,
                metadata={"collection_counts": collection_stats}
            )

        except Exception as e:
            response_time = time.time() - start_time
            return FamilyHealthStatus(
                component="family_collections",
                healthy=False,
                response_time=response_time,
                error_message=str(e)
            )

    async def _check_sbd_integration_health(self) -> FamilyHealthStatus:
        """Check SBD token integration health."""
        start_time = time.time()

        try:
            # Check for virtual family accounts
            users_collection = db_manager.get_collection("users")
            virtual_accounts = await users_collection.count_documents({
                "username": {"$regex": "^family_"},
                "is_virtual_account": True
            })

            response_time = time.time() - start_time

            return FamilyHealthStatus(
                component="sbd_integration",
                healthy=True,
                response_time=response_time,
                metadata={"virtual_accounts_count": virtual_accounts}
            )

        except Exception as e:
            response_time = time.time() - start_time
            return FamilyHealthStatus(
                component="sbd_integration",
                healthy=False,
                response_time=response_time,
                error_message=str(e)
            )

    async def _check_email_system_health(self) -> FamilyHealthStatus:
        """Check email system health for invitations."""
        start_time = time.time()

        try:
            # This is a basic check - in production you might want to test actual email sending
            # For now, we'll just check if the email manager is available
            from second_brain_database.managers.email import email_manager

            # Check if email configuration is available
            has_email_config = hasattr(email_manager, 'smtp_server') or hasattr(email_manager, 'api_key')

            response_time = time.time() - start_time

            return FamilyHealthStatus(
                component="email_system",
                healthy=has_email_config,
                response_time=response_time,
                metadata={"email_configured": has_email_config}
            )

        except Exception as e:
            response_time = time.time() - start_time
            return FamilyHealthStatus(
                component="email_system",
                healthy=False,
                response_time=response_time,
                error_message=str(e)
            )

    async def _check_notification_system_health(self) -> FamilyHealthStatus:
        """Check notification system health."""
        start_time = time.time()

        try:
            # Check notification collection
            notifications_collection = db_manager.get_collection("family_notifications")
            pending_notifications = await notifications_collection.count_documents({"status": "pending"})

            response_time = time.time() - start_time

            return FamilyHealthStatus(
                component="notification_system",
                healthy=True,
                response_time=response_time,
                metadata={"pending_notifications": pending_notifications}
            )

        except Exception as e:
            response_time = time.time() - start_time
            return FamilyHealthStatus(
                component="notification_system",
                healthy=False,
                response_time=response_time,
                error_message=str(e)
            )

    async def _collect_sbd_metrics(self) -> Dict[str, Any]:
        """Collect SBD token-related metrics."""
        try:
            users_collection = db_manager.get_collection("users")

            # Get virtual family accounts
            virtual_accounts_cursor = users_collection.find({
                "username": {"$regex": "^family_"},
                "is_virtual_account": True
            }, {"username": 1, "sbd_tokens": 1})

            virtual_accounts = await virtual_accounts_cursor.to_list(length=None)

            total_family_accounts = len(virtual_accounts)
            total_family_balance = sum(account.get("sbd_tokens", 0) for account in virtual_accounts)

            # Get frozen accounts count
            families_collection = db_manager.get_collection("families")
            frozen_accounts = await families_collection.count_documents({"sbd_account.is_frozen": True})

            return {
                "total_family_accounts": total_family_accounts,
                "total_family_balance": total_family_balance,
                "frozen_accounts": frozen_accounts,
                "avg_family_balance": total_family_balance / total_family_accounts if total_family_accounts > 0 else 0
            }

        except Exception as e:
            self.metrics_logger.error("Failed to collect SBD metrics: %s", str(e))
            return {
                "total_family_accounts": 0,
                "total_family_balance": 0,
                "frozen_accounts": 0,
                "avg_family_balance": 0,
                "error": str(e)
            }

    def _calculate_operation_rates(self) -> Dict[str, int]:
        """Calculate operations per minute for each operation type."""
        rates = {}
        current_minute = int(time.time() // 60)

        for op_type, minute_counts in self._operation_counts.items():
            # Sum operations in the last minute
            last_minute_ops = minute_counts.get(current_minute - 1, 0)
            rates[op_type] = last_minute_ops

        return rates

    def _calculate_error_rates(self) -> Dict[str, float]:
        """Calculate error rates for each operation type."""
        error_rates = {}
        current_minute = int(time.time() // 60)

        for op_type in self._operation_counts.keys():
            # Calculate error rate for last 5 minutes
            total_ops = 0
            total_errors = 0

            for minute in range(current_minute - 4, current_minute + 1):
                if minute in self._operation_counts[op_type]:
                    total_ops += self._operation_counts[op_type][minute]
                if op_type in self._error_counts and minute in self._error_counts[op_type]:
                    total_errors += self._error_counts[op_type][minute]

            error_rates[op_type] = total_errors / total_ops if total_ops > 0 else 0.0

        return error_rates

    def _calculate_performance_metrics(self) -> Dict[str, float]:
        """Calculate performance metrics for each operation type."""
        perf_metrics = {}

        for op_type, data_points in self._performance_data.items():
            if not data_points:
                continue

            durations = [d["duration"] for d in data_points]
            perf_metrics[f"{op_type}_avg_duration"] = sum(durations) / len(durations)
            perf_metrics[f"{op_type}_max_duration"] = max(durations)
            perf_metrics[f"{op_type}_min_duration"] = min(durations)

        return perf_metrics

    async def _send_health_alert(self, health_results: Dict[str, FamilyHealthStatus]) -> None:
        """Send alert for unhealthy components."""
        unhealthy_components = [
            name for name, status in health_results.items()
            if not status.healthy
        ]

        if unhealthy_components:
            await self.send_alert(
                AlertSeverity.ERROR,
                "Family System Health Check Failed",
                f"Unhealthy components: {', '.join(unhealthy_components)}",
                {
                    "unhealthy_components": unhealthy_components,
                    "component_details": {
                        name: {"error": status.error_message, "response_time": status.response_time}
                        for name, status in health_results.items()
                        if not status.healthy
                    }
                }
            )

    async def _check_metrics_alerts(self, metrics: FamilyMetrics) -> None:
        """Check metrics for alert conditions."""
        # Check for high error rates
        for op_type, error_rate in metrics.error_rates.items():
            if error_rate > CRITICAL_ERROR_RATE_THRESHOLD:
                await self.send_alert(
                    AlertSeverity.CRITICAL,
                    "Critical Error Rate in Metrics",
                    f"Operation {op_type} has {error_rate:.1%} error rate",
                    {"operation_type": op_type, "error_rate": error_rate}
                )

        # Check for performance issues
        for metric_name, value in metrics.performance_metrics.items():
            if "avg_duration" in metric_name and value > SLOW_OPERATION_THRESHOLD:
                op_type = metric_name.replace("_avg_duration", "")
                await self.send_alert(
                    AlertSeverity.WARNING,
                    "Slow Average Performance",
                    f"Operation {op_type} has average duration of {value:.2f}s",
                    {"operation_type": op_type, "avg_duration": value}
                )

        # Check for high pending items
        if metrics.total_invitations_pending > 100:
            await self.send_alert(
                AlertSeverity.WARNING,
                "High Pending Invitations",
                f"{metrics.total_invitations_pending} invitations are pending",
                {"pending_invitations": metrics.total_invitations_pending}
            )

        if metrics.total_token_requests_pending > 50:
            await self.send_alert(
                AlertSeverity.WARNING,
                "High Pending Token Requests",
                f"{metrics.total_token_requests_pending} token requests are pending",
                {"pending_token_requests": metrics.total_token_requests_pending}
            )


# Global family monitor instance
family_monitor = FamilyMonitor()
