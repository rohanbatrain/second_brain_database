"""
MCP Monitoring Integration

Integrates error recovery, performance monitoring, and alerting systems
to provide comprehensive monitoring and observability for MCP operations.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ...config import settings
from ...managers.logging_manager import get_logger
from .alerting import AlertCategory, AlertSeverity, mcp_alert_manager
from .context import get_mcp_request_context, get_mcp_user_context
from .error_recovery import MCPServiceType, mcp_recovery_manager
from .performance_monitoring import mcp_performance_monitor, track_performance

logger = get_logger(prefix="[MCP_Integration]")


class MCPMonitoringIntegration:
    """
    Centralized integration for all MCP monitoring systems.

    Coordinates error recovery, performance monitoring, and alerting
    to provide comprehensive observability and operational excellence.
    """

    def __init__(self):
        self.initialized = False
        self.monitoring_enabled = True

        logger.info("MCP Monitoring Integration initialized")

    async def initialize(self) -> None:
        """Initialize all monitoring systems."""
        if self.initialized:
            logger.warning("MCP monitoring integration already initialized")
            return

        try:
            logger.info("Initializing MCP monitoring integration...")

            # All managers are already initialized globally
            # Just verify they're available
            if not mcp_recovery_manager:
                raise RuntimeError("MCP recovery manager not available")

            if not mcp_performance_monitor:
                raise RuntimeError("MCP performance monitor not available")

            if not mcp_alert_manager:
                raise RuntimeError("MCP alert manager not available")

            self.initialized = True
            logger.info("MCP monitoring integration initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize MCP monitoring integration: %s", e)
            raise

    async def start_monitoring(self) -> None:
        """Start all monitoring systems."""
        if not self.initialized:
            await self.initialize()

        try:
            logger.info("Starting MCP monitoring systems...")

            # Start performance monitoring
            await mcp_performance_monitor.start_monitoring()

            # Start alert monitoring
            await mcp_alert_manager.start_monitoring()

            self.monitoring_enabled = True
            logger.info("All MCP monitoring systems started successfully")

        except Exception as e:
            logger.error("Failed to start MCP monitoring systems: %s", e)
            # Try to trigger an alert about the monitoring failure
            try:
                await mcp_alert_manager.trigger_alert(
                    AlertSeverity.CRITICAL,
                    AlertCategory.SERVER_HEALTH,
                    "MCP Monitoring System Failure",
                    f"Failed to start MCP monitoring systems: {str(e)}",
                    metadata={"error": str(e), "component": "monitoring_integration"},
                )
            except Exception:  # TODO: Use specific exception type
                pass  # Don't fail if alerting also fails
            raise

    async def stop_monitoring(self) -> None:
        """Stop all monitoring systems."""
        try:
            logger.info("Stopping MCP monitoring systems...")

            # Stop performance monitoring
            await mcp_performance_monitor.stop_monitoring()

            # Stop alert monitoring
            await mcp_alert_manager.stop_monitoring()

            self.monitoring_enabled = False
            logger.info("All MCP monitoring systems stopped successfully")

        except Exception as e:
            logger.error("Failed to stop MCP monitoring systems: %s", e)

    async def execute_monitored_operation(
        self,
        func,
        service_type: MCPServiceType,
        operation_name: str,
        resource_type: Optional[str] = None,
        enable_recovery: bool = True,
        enable_performance_tracking: bool = True,
        enable_alerting: bool = True,
        *args,
        **kwargs,
    ) -> Any:
        """
        Execute an operation with comprehensive monitoring.

        Args:
            func: Function to execute
            service_type: Type of MCP service
            operation_name: Name of the operation
            resource_type: Type of resource for bulkhead isolation
            enable_recovery: Whether to enable error recovery
            enable_performance_tracking: Whether to track performance
            enable_alerting: Whether to enable alerting on failures
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result
        """
        if not self.monitoring_enabled:
            # If monitoring is disabled, just execute the function
            return await func(*args, **kwargs)

        # Get user context for monitoring
        user_id = None
        request_id = None
        try:
            user_context = get_mcp_user_context()
            user_id = user_context.user_id
        except Exception:  # TODO: Use specific exception type
            pass

        try:
            request_context = get_mcp_request_context()
            request_id = request_context.request_id
        except Exception:  # TODO: Use specific exception type
            pass

        # Execute with comprehensive monitoring
        if enable_recovery:
            # Use error recovery manager
            return await mcp_recovery_manager.execute_with_recovery(
                func=func,
                service_type=service_type,
                operation_name=operation_name,
                resource_type=resource_type,
                user_id=user_id,
                request_id=request_id,
                *args,
                **kwargs,
            )
        else:
            # Execute with performance tracking only
            if enable_performance_tracking:
                with mcp_performance_monitor.track_execution(operation_name) as tracker:
                    if user_id:
                        tracker.add_metadata("user_id", user_id)
                    if request_id:
                        tracker.add_metadata("request_id", request_id)

                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        if enable_alerting:
                            await mcp_alert_manager.trigger_alert(
                                AlertSeverity.ERROR,
                                AlertCategory.ERROR_RATE,
                                f"Operation Failed: {operation_name}",
                                f"Operation {operation_name} failed: {str(e)}",
                                metadata={
                                    "operation": operation_name,
                                    "service_type": service_type.value,
                                    "error": str(e),
                                    "user_id": user_id,
                                },
                            )
                        raise
            else:
                # Execute without monitoring
                return await func(*args, **kwargs)

    async def get_comprehensive_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of all monitoring systems."""
        try:
            # Get individual health statuses
            recovery_health = await mcp_recovery_manager.get_recovery_health_status()
            performance_health = await mcp_performance_monitor.get_health_status()
            alert_health = await mcp_alert_manager.get_alert_status()

            # Determine overall health
            overall_healthy = (
                recovery_health.get("healthy", True)
                and performance_health.get("healthy", True)
                and alert_health.get("monitoring_enabled", True)
                and self.monitoring_enabled
            )

            return {
                "overall_healthy": overall_healthy,
                "monitoring_enabled": self.monitoring_enabled,
                "initialized": self.initialized,
                "error_recovery": recovery_health,
                "performance_monitoring": performance_health,
                "alerting": alert_health,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error("Failed to get comprehensive health status: %s", e)
            return {
                "overall_healthy": False,
                "monitoring_enabled": self.monitoring_enabled,
                "initialized": self.initialized,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary from all monitoring systems."""
        try:
            # Get performance metrics
            perf_summary = mcp_performance_monitor.collector.get_performance_summary()

            # Get recovery statistics
            recovery_health = await mcp_recovery_manager.get_recovery_health_status()

            # Get alert statistics
            alert_status = await mcp_alert_manager.get_alert_status()

            return {
                "performance": perf_summary,
                "error_recovery": {
                    "circuit_breakers": recovery_health.get("circuit_breakers", {}),
                    "bulkheads": recovery_health.get("bulkheads", {}),
                },
                "alerting": {
                    "active_alerts": alert_status.get("active_alerts", 0),
                    "recent_alerts": alert_status.get("recent_alerts", 0),
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.error("Failed to get performance summary: %s", e)
            return {"error": str(e), "timestamp": datetime.now(timezone.utc).isoformat()}

    async def trigger_health_check_alerts(self) -> None:
        """Trigger alerts based on health check results."""
        try:
            health_status = await self.get_comprehensive_health_status()

            if not health_status["overall_healthy"]:
                await mcp_alert_manager.trigger_alert(
                    AlertSeverity.ERROR,
                    AlertCategory.SERVER_HEALTH,
                    "MCP Monitoring System Unhealthy",
                    "One or more MCP monitoring systems are unhealthy",
                    metadata=health_status,
                )

            # Check specific subsystems
            if not health_status.get("error_recovery", {}).get("healthy", True):
                await mcp_alert_manager.trigger_alert(
                    AlertSeverity.WARNING,
                    AlertCategory.CIRCUIT_BREAKER,
                    "MCP Error Recovery Issues",
                    "MCP error recovery system has issues",
                    metadata=health_status.get("error_recovery", {}),
                )

            if not health_status.get("performance_monitoring", {}).get("healthy", True):
                await mcp_alert_manager.trigger_alert(
                    AlertSeverity.WARNING,
                    AlertCategory.PERFORMANCE,
                    "MCP Performance Monitoring Issues",
                    "MCP performance monitoring system has issues",
                    metadata=health_status.get("performance_monitoring", {}),
                )

        except Exception as e:
            logger.error("Failed to trigger health check alerts: %s", e)


# Global monitoring integration instance
mcp_monitoring_integration = MCPMonitoringIntegration()


# Decorator for comprehensive monitoring
def with_comprehensive_monitoring(
    service_type: MCPServiceType,
    operation_name: str,
    resource_type: Optional[str] = None,
    enable_recovery: bool = True,
    enable_performance_tracking: bool = True,
    enable_alerting: bool = True,
):
    """
    Decorator to add comprehensive monitoring to MCP functions.

    Args:
        service_type: Type of MCP service
        operation_name: Name of the operation
        resource_type: Type of resource for bulkhead isolation
        enable_recovery: Whether to enable error recovery
        enable_performance_tracking: Whether to track performance
        enable_alerting: Whether to enable alerting on failures
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            return await mcp_monitoring_integration.execute_monitored_operation(
                func=func,
                service_type=service_type,
                operation_name=operation_name,
                resource_type=resource_type,
                enable_recovery=enable_recovery,
                enable_performance_tracking=enable_performance_tracking,
                enable_alerting=enable_alerting,
                *args,
                **kwargs,
            )

        return wrapper

    return decorator


# Health check function for external use
async def get_mcp_monitoring_health() -> Dict[str, Any]:
    """Get comprehensive MCP monitoring health status."""
    return await mcp_monitoring_integration.get_comprehensive_health_status()


# Performance summary function for external use
async def get_mcp_performance_summary() -> Dict[str, Any]:
    """Get comprehensive MCP performance summary."""
    return await mcp_monitoring_integration.get_performance_summary()
