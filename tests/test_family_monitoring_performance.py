"""
Test suite for Family Management System Performance Monitoring.

This module tests the performance monitoring capabilities of the family management system,
including operation tracking, alert generation, error rate monitoring, metrics collection,
and health check accuracy.

Requirements tested:
- 7.1: Performance monitoring with configurable thresholds
- 7.2: Alert generation for slow operations and high error rates
- 7.3: Health check endpoints and component validation
- 7.6: Operational dashboards and reporting
"""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock Redis and database connections before importing
with patch("src.second_brain_database.managers.redis_manager.redis_manager"):
    with patch("src.second_brain_database.database.db_manager"):
        from src.second_brain_database.managers.family_monitoring import (
            CRITICAL_ERROR_RATE_THRESHOLD,
            HIGH_ERROR_RATE_THRESHOLD,
            SLOW_OPERATION_THRESHOLD,
            VERY_SLOW_OPERATION_THRESHOLD,
            AlertSeverity,
            FamilyHealthStatus,
            FamilyMetrics,
            FamilyMonitor,
            FamilyOperationContext,
            FamilyOperationType,
        )


class TestFamilyPerformanceMonitoring:
    """Test performance monitoring functionality."""

    @pytest.fixture
    def family_monitor(self):
        """Create a FamilyMonitor instance for testing."""
        return FamilyMonitor()

    @pytest.fixture
    def sample_operation_context(self):
        """Create a sample operation context for testing."""
        return FamilyOperationContext(
            operation_type=FamilyOperationType.FAMILY_CREATE,
            family_id="fam_test123",
            user_id="user_test456",
            duration=1.5,
            success=True,
            metadata={"test": "data"},
        )

    @pytest.mark.asyncio
    async def test_operation_performance_tracking(self, family_monitor):
        """Test that operation performance is tracked correctly."""
        # Test normal operation
        await family_monitor.log_family_performance(
            FamilyOperationType.FAMILY_CREATE, duration=1.0, success=True, metadata={"test": "normal_operation"}
        )

        # Test slow operation
        await family_monitor.log_family_performance(
            FamilyOperationType.MEMBER_INVITE, duration=3.0, success=True, metadata={"test": "slow_operation"}
        )

        # Test very slow operation
        await family_monitor.log_family_performance(
            FamilyOperationType.SBD_SPEND, duration=6.0, success=False, metadata={"test": "very_slow_operation"}
        )

        # Verify performance data is stored
        assert "family_create" in family_monitor._performance_data
        assert "member_invite" in family_monitor._performance_data
        assert "sbd_spend" in family_monitor._performance_data

        # Check data structure
        family_create_data = family_monitor._performance_data["family_create"]
        assert len(family_create_data) == 1
        assert family_create_data[0]["duration"] == 1.0
        assert family_create_data[0]["success"] is True

        member_invite_data = family_monitor._performance_data["member_invite"]
        assert len(member_invite_data) == 1
        assert member_invite_data[0]["duration"] == 3.0

        sbd_spend_data = family_monitor._performance_data["sbd_spend"]
        assert len(sbd_spend_data) == 1
        assert sbd_spend_data[0]["duration"] == 6.0
        assert sbd_spend_data[0]["success"] is False

    @pytest.mark.asyncio
    async def test_performance_thresholds_detection(self, family_monitor):
        """Test that performance thresholds are correctly detected."""
        # Mock the send_alert method to capture alerts
        family_monitor.send_alert = AsyncMock()

        # Test operation within normal threshold
        context_normal = FamilyOperationContext(
            operation_type=FamilyOperationType.FAMILY_CREATE, duration=1.0, success=True
        )
        await family_monitor.log_family_operation(context_normal)

        # Should not generate alerts for normal operations
        family_monitor.send_alert.assert_not_called()

        # Test slow operation (above SLOW_OPERATION_THRESHOLD)
        context_slow = FamilyOperationContext(
            operation_type=FamilyOperationType.MEMBER_INVITE, duration=SLOW_OPERATION_THRESHOLD + 0.5, success=True
        )
        await family_monitor.log_family_operation(context_slow)

        # Should generate warning alert
        family_monitor.send_alert.assert_called_once()
        call_args = family_monitor.send_alert.call_args
        assert call_args[0][0] == AlertSeverity.WARNING
        assert "Slow Family Operation" in call_args[0][1]

        # Reset mock
        family_monitor.send_alert.reset_mock()

        # Test very slow operation (above VERY_SLOW_OPERATION_THRESHOLD)
        context_very_slow = FamilyOperationContext(
            operation_type=FamilyOperationType.SBD_SPEND, duration=VERY_SLOW_OPERATION_THRESHOLD + 1.0, success=True
        )
        await family_monitor.log_family_operation(context_very_slow)

        # Should generate error alert
        family_monitor.send_alert.assert_called_once()
        call_args = family_monitor.send_alert.call_args
        assert call_args[0][0] == AlertSeverity.ERROR
        assert "Very Slow Family Operation" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_error_rate_monitoring(self, family_monitor):
        """Test error rate monitoring and alerting."""
        # Mock the send_alert method
        family_monitor.send_alert = AsyncMock()

        # Simulate operations with errors to trigger high error rate
        operation_type = FamilyOperationType.FAMILY_CREATE

        # Generate successful operations
        for i in range(10):
            context = FamilyOperationContext(operation_type=operation_type, duration=1.0, success=True)
            await family_monitor.log_family_operation(context)

        # Generate failed operations to reach high error rate threshold
        error_count = int(10 * HIGH_ERROR_RATE_THRESHOLD) + 2  # Exceed threshold
        for i in range(error_count):
            context = FamilyOperationContext(
                operation_type=operation_type, duration=1.0, success=False, error_message="Test error"
            )
            await family_monitor.log_family_operation(context)

        # Should generate high error rate alert
        assert family_monitor.send_alert.called

        # Check if warning alert was generated
        warning_calls = [
            call
            for call in family_monitor.send_alert.call_args_list
            if call[0][0] == AlertSeverity.WARNING and "High Error Rate" in call[0][1]
        ]
        assert len(warning_calls) > 0

        # Reset and test critical error rate
        family_monitor.send_alert.reset_mock()

        # Generate more errors to reach critical threshold
        critical_error_count = int(20 * CRITICAL_ERROR_RATE_THRESHOLD) + 5
        for i in range(critical_error_count):
            context = FamilyOperationContext(
                operation_type=operation_type, duration=1.0, success=False, error_message="Critical test error"
            )
            await family_monitor.log_family_operation(context)

        # Should generate critical error rate alert
        critical_calls = [
            call
            for call in family_monitor.send_alert.call_args_list
            if call[0][0] == AlertSeverity.CRITICAL and "Critical Error Rate" in call[0][1]
        ]
        assert len(critical_calls) > 0

    @pytest.mark.asyncio
    async def test_metrics_collection_accuracy(self, family_monitor):
        """Test that metrics are collected accurately."""
        # Mock database collections
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            # Setup mock collections
            mock_families = AsyncMock()
            mock_relationships = AsyncMock()
            mock_invitations = AsyncMock()
            mock_token_requests = AsyncMock()

            mock_db.get_collection.side_effect = lambda name: {
                "families": mock_families,
                "family_relationships": mock_relationships,
                "family_invitations": mock_invitations,
                "family_token_requests": mock_token_requests,
            }[name]

            # Setup mock data
            mock_families.count_documents.side_effect = [100, 85]  # total, active
            mock_relationships.count_documents.return_value = 250
            mock_invitations.count_documents.return_value = 15
            mock_token_requests.count_documents.return_value = 8

            # Mock average family size calculation
            mock_families.aggregate.return_value.to_list.return_value = [{"avg_size": 3.2}]

            # Mock SBD metrics
            family_monitor._collect_sbd_metrics = AsyncMock(
                return_value={"total_virtual_accounts": 85, "total_balance": 50000, "frozen_accounts": 2}
            )

            # Add some performance data
            family_monitor._performance_data = {
                "family_create": [
                    {"duration": 1.0, "success": True, "timestamp": time.time()},
                    {"duration": 2.5, "success": True, "timestamp": time.time()},
                ],
                "member_invite": [{"duration": 1.5, "success": False, "timestamp": time.time()}],
            }

            # Collect metrics
            metrics = await family_monitor.collect_family_metrics()

            # Verify metrics accuracy
            assert isinstance(metrics, FamilyMetrics)
            assert metrics.total_families == 100
            assert metrics.active_families == 85
            assert metrics.total_members == 250
            assert metrics.total_invitations_pending == 15
            assert metrics.total_token_requests_pending == 8
            assert metrics.avg_family_size == 3.2

            # Verify SBD metrics
            assert metrics.sbd_metrics["total_virtual_accounts"] == 85
            assert metrics.sbd_metrics["total_balance"] == 50000
            assert metrics.sbd_metrics["frozen_accounts"] == 2

            # Verify performance metrics are included
            assert "family_create" in metrics.performance_metrics
            assert "member_invite" in metrics.performance_metrics

    @pytest.mark.asyncio
    async def test_health_check_component_validation(self, family_monitor):
        """Test health check accuracy for all components."""
        # Mock all health check methods
        family_monitor._check_database_health = AsyncMock(
            return_value=FamilyHealthStatus(component="database", healthy=True, response_time=0.1)
        )

        family_monitor._check_redis_health = AsyncMock(
            return_value=FamilyHealthStatus(component="redis", healthy=True, response_time=0.05)
        )

        family_monitor._check_family_collections_health = AsyncMock(
            return_value=FamilyHealthStatus(
                component="family_collections",
                healthy=True,
                response_time=0.2,
                metadata={"collection_counts": {"families": 100, "family_relationships": 250}},
            )
        )

        family_monitor._check_sbd_integration_health = AsyncMock(
            return_value=FamilyHealthStatus(
                component="sbd_integration", healthy=True, response_time=0.15, metadata={"virtual_accounts_count": 85}
            )
        )

        family_monitor._check_email_system_health = AsyncMock(
            return_value=FamilyHealthStatus(component="email_system", healthy=True, response_time=0.3)
        )

        family_monitor._check_notification_system_health = AsyncMock(
            return_value=FamilyHealthStatus(component="notification_system", healthy=True, response_time=0.1)
        )

        # Perform health check
        health_results = await family_monitor.check_family_system_health()

        # Verify all components are checked
        expected_components = [
            "database",
            "redis",
            "family_collections",
            "sbd_integration",
            "email_system",
            "notification_system",
        ]

        for component in expected_components:
            assert component in health_results
            assert isinstance(health_results[component], FamilyHealthStatus)
            assert health_results[component].healthy is True
            assert health_results[component].response_time is not None

        # Verify health check methods were called
        family_monitor._check_database_health.assert_called_once()
        family_monitor._check_redis_health.assert_called_once()
        family_monitor._check_family_collections_health.assert_called_once()
        family_monitor._check_sbd_integration_health.assert_called_once()
        family_monitor._check_email_system_health.assert_called_once()
        family_monitor._check_notification_system_health.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_failure_detection(self, family_monitor):
        """Test health check failure detection and alerting."""
        # Mock send_alert method
        family_monitor.send_alert = AsyncMock()

        # Mock health checks with failures
        family_monitor._check_database_health = AsyncMock(
            return_value=FamilyHealthStatus(
                component="database", healthy=False, response_time=5.0, error_message="Connection timeout"
            )
        )

        family_monitor._check_redis_health = AsyncMock(
            return_value=FamilyHealthStatus(component="redis", healthy=True, response_time=0.05)
        )

        family_monitor._check_family_collections_health = AsyncMock(
            return_value=FamilyHealthStatus(
                component="family_collections", healthy=False, response_time=None, error_message="Collection not found"
            )
        )

        family_monitor._check_sbd_integration_health = AsyncMock(
            return_value=FamilyHealthStatus(component="sbd_integration", healthy=True, response_time=0.15)
        )

        family_monitor._check_email_system_health = AsyncMock(
            return_value=FamilyHealthStatus(component="email_system", healthy=True, response_time=0.3)
        )

        family_monitor._check_notification_system_health = AsyncMock(
            return_value=FamilyHealthStatus(component="notification_system", healthy=True, response_time=0.1)
        )

        # Mock _send_health_alert method
        family_monitor._send_health_alert = AsyncMock()

        # Perform health check
        health_results = await family_monitor.check_family_system_health()

        # Verify failures are detected
        assert not health_results["database"].healthy
        assert not health_results["family_collections"].healthy
        assert health_results["redis"].healthy
        assert health_results["sbd_integration"].healthy

        # Verify health alert was sent due to failures
        family_monitor._send_health_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_performance_summary_generation(self, family_monitor):
        """Test performance summary generation."""
        # Add test performance data
        current_time = time.time()
        family_monitor._performance_data = {
            "family_create": [
                {"duration": 1.0, "success": True, "timestamp": current_time},
                {"duration": 2.5, "success": True, "timestamp": current_time},
                {"duration": 6.0, "success": False, "timestamp": current_time},  # Very slow
            ],
            "member_invite": [
                {"duration": 1.5, "success": True, "timestamp": current_time},
                {"duration": 3.0, "success": True, "timestamp": current_time},  # Slow
            ],
        }

        # Generate performance summary
        summary = await family_monitor.get_performance_summary()

        # Verify summary structure
        assert "timestamp" in summary
        assert "operations" in summary
        assert "overall_stats" in summary

        # Verify operation-specific stats
        assert "family_create" in summary["operations"]
        assert "member_invite" in summary["operations"]

        family_create_stats = summary["operations"]["family_create"]
        assert family_create_stats["count"] == 3
        assert family_create_stats["avg_duration"] == (1.0 + 2.5 + 6.0) / 3
        assert family_create_stats["min_duration"] == 1.0
        assert family_create_stats["max_duration"] == 6.0
        assert family_create_stats["success_rate"] == 2 / 3
        assert family_create_stats["slow_operations"] == 2  # 2.5s and 6.0s
        assert family_create_stats["very_slow_operations"] == 1  # 6.0s

        member_invite_stats = summary["operations"]["member_invite"]
        assert member_invite_stats["count"] == 2
        assert member_invite_stats["success_rate"] == 1.0
        assert member_invite_stats["slow_operations"] == 1  # 3.0s
        assert member_invite_stats["very_slow_operations"] == 0

        # Verify overall stats
        overall = summary["overall_stats"]
        assert overall["total_operations"] == 5
        assert overall["avg_duration"] == (1.0 + 2.5 + 6.0 + 1.5 + 3.0) / 5
        assert overall["success_rate"] == 4 / 5
        assert overall["slow_operations"] == 3
        assert overall["very_slow_operations"] == 1

    @pytest.mark.asyncio
    async def test_alert_cooldown_mechanism(self, family_monitor):
        """Test alert cooldown to prevent spam."""
        # Mock time to control cooldown
        with patch("time.time") as mock_time:
            mock_time.return_value = 1000.0

            # Send first alert
            await family_monitor.send_alert(AlertSeverity.WARNING, "Test Alert", "Test message")

            # Verify alert was logged
            assert len(family_monitor._last_alert_times) == 1

            # Try to send same alert immediately (should be blocked by cooldown)
            mock_time.return_value = 1001.0  # 1 second later
            await family_monitor.send_alert(AlertSeverity.WARNING, "Test Alert", "Test message")

            # Should still be only one alert time recorded (cooldown active)
            assert len(family_monitor._last_alert_times) == 1

            # Send alert after cooldown period
            mock_time.return_value = 1000.0 + 1801.0  # After 30 minute cooldown
            await family_monitor.send_alert(AlertSeverity.WARNING, "Test Alert", "Test message after cooldown")

            # Should update the alert time
            alert_key = "warning_Test Alert"
            assert family_monitor._last_alert_times[alert_key] == 1801.0

    @pytest.mark.asyncio
    async def test_operation_metrics_cleanup(self, family_monitor):
        """Test that old operation metrics are cleaned up."""
        # Mock time to simulate passage of time
        with patch("time.time") as mock_time:
            # Start at time 1000
            mock_time.return_value = 1000.0
            current_minute = int(1000.0 // 60)

            # Add operation data
            context = FamilyOperationContext(
                operation_type=FamilyOperationType.FAMILY_CREATE, duration=1.0, success=True
            )
            await family_monitor.log_family_operation(context)

            # Verify data is stored
            assert "family_create" in family_monitor._operation_counts
            assert current_minute in family_monitor._operation_counts["family_create"]

            # Move time forward by more than 1 hour
            mock_time.return_value = 1000.0 + 3700.0  # 61+ minutes later
            new_minute = int((1000.0 + 3700.0) // 60)

            # Add new operation (this should trigger cleanup)
            context_new = FamilyOperationContext(
                operation_type=FamilyOperationType.FAMILY_CREATE, duration=1.0, success=True
            )
            await family_monitor.log_family_operation(context_new)

            # Verify old data is cleaned up
            assert current_minute not in family_monitor._operation_counts["family_create"]
            assert new_minute in family_monitor._operation_counts["family_create"]

    @pytest.mark.asyncio
    async def test_structured_logging_format(self, family_monitor):
        """Test that structured logging includes all required fields."""
        # Mock the logger to capture log entries
        with patch.object(family_monitor.logger, "info") as mock_info:
            context = FamilyOperationContext(
                operation_type=FamilyOperationType.FAMILY_CREATE,
                family_id="fam_test123",
                user_id="user_test456",
                duration=1.5,
                success=True,
                metadata={"test": "data"},
                request_id="req_123",
                ip_address="192.168.1.1",
            )

            await family_monitor.log_family_operation(context)

            # Verify structured log was called
            mock_info.assert_called_once()
            log_entry = mock_info.call_args[0][0]

            # Verify required fields are present
            required_fields = [
                "event",
                "operation_type",
                "timestamp",
                "family_id",
                "user_id",
                "duration",
                "success",
                "request_id",
                "ip_address",
                "metadata",
                "process",
                "host",
                "app",
                "env",
            ]

            for field in required_fields:
                assert field in log_entry

            # Verify field values
            assert log_entry["event"] == "family_operation"
            assert log_entry["operation_type"] == "family_create"
            assert log_entry["family_id"] == "fam_test123"
            assert log_entry["user_id"] == "user_test456"
            assert log_entry["duration"] == 1.5
            assert log_entry["success"] is True
            assert log_entry["request_id"] == "req_123"
            assert log_entry["ip_address"] == "192.168.1.1"
            assert log_entry["metadata"] == {"test": "data"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
