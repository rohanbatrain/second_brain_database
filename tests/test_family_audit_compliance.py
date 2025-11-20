"""
Test suite for Family Management System Audit and Compliance.

This module tests the audit logging and compliance features of the family management system,
including comprehensive audit logging, sensitive data access logging, admin action recording,
compliance report generation, and suspicious activity detection.

Requirements tested:
- 9.1: Comprehensive audit logging for all operations
- 9.2: Sensitive data access logging and attribution
- 9.3: Admin action recording and context capture
- 9.4: Compliance report generation functionality
- 9.5: Suspicious activity detection and flagging
- 9.6: Audit data security and role-based access controls
"""

import asyncio
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.second_brain_database.managers.family_audit_manager import FamilyAuditManager
from src.second_brain_database.managers.family_monitoring import (
    AlertSeverity,
    FamilyMonitor,
    FamilyOperationContext,
    FamilyOperationType,
)


class TestFamilyAuditCompliance:
    """Test audit and compliance functionality."""

    @pytest.fixture
    def family_audit_manager(self):
        """Create a FamilyAuditManager instance for testing."""
        return FamilyAuditManager()

    @pytest.fixture
    def family_monitor(self):
        """Create a FamilyMonitor instance for testing."""
        return FamilyMonitor()

    @pytest.fixture
    def sample_audit_context(self):
        """Create sample audit context for testing."""
        return {
            "operation_type": "family_create",
            "family_id": "fam_test123",
            "user_id": "user_test456",
            "admin_id": "admin_test789",
            "ip_address": "192.168.1.1",
            "user_agent": "TestAgent/1.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {"test": "audit_data"},
        }

    @pytest.mark.asyncio
    async def test_comprehensive_audit_logging(self, family_audit_manager):
        """Test comprehensive audit logging for all family operations."""
        # Mock database collection
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            mock_audit_collection = AsyncMock()
            mock_db.get_collection.return_value = mock_audit_collection

            # Test audit logging for different operation types
            operations_to_test = [
                {
                    "operation_type": "family_create",
                    "family_id": "fam_test123",
                    "user_id": "user_test456",
                    "details": {"family_name": "Test Family", "initial_balance": 1000},
                },
                {
                    "operation_type": "member_invite",
                    "family_id": "fam_test123",
                    "user_id": "admin_test789",
                    "target_user_id": "user_invited123",
                    "details": {"relationship_type": "child", "invitation_method": "email"},
                },
                {
                    "operation_type": "sbd_spend",
                    "family_id": "fam_test123",
                    "user_id": "user_test456",
                    "details": {"amount": 50, "recipient": "user_recipient789", "reason": "allowance"},
                },
                {
                    "operation_type": "admin_promote",
                    "family_id": "fam_test123",
                    "user_id": "admin_test789",
                    "target_user_id": "user_promoted123",
                    "details": {"previous_role": "member", "new_role": "admin", "reason": "succession_plan"},
                },
            ]

            for operation in operations_to_test:
                await family_audit_manager.log_family_audit_event(
                    operation_type=operation["operation_type"],
                    family_id=operation["family_id"],
                    user_id=operation["user_id"],
                    target_user_id=operation.get("target_user_id"),
                    details=operation["details"],
                    ip_address="192.168.1.1",
                    user_agent="TestAgent/1.0",
                )

            # Verify audit records were created
            assert mock_audit_collection.insert_one.call_count == len(operations_to_test)

            # Verify audit record structure
            for call in mock_audit_collection.insert_one.call_args_list:
                audit_record = call[0][0]

                # Check required fields
                required_fields = [
                    "audit_id",
                    "operation_type",
                    "family_id",
                    "user_id",
                    "timestamp",
                    "ip_address",
                    "user_agent",
                    "details",
                ]
                for field in required_fields:
                    assert field in audit_record

                # Verify data types and formats
                assert isinstance(audit_record["timestamp"], str)
                assert audit_record["audit_id"].startswith("audit_")
                assert isinstance(audit_record["details"], dict)

    @pytest.mark.asyncio
    async def test_sensitive_data_access_logging(self, family_audit_manager):
        """Test logging of sensitive data access with proper attribution."""
        # Mock database collection
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            mock_audit_collection = AsyncMock()
            mock_db.get_collection.return_value = mock_audit_collection

            # Test sensitive data access scenarios
            sensitive_operations = [
                {
                    "operation_type": "sensitive_data_access",
                    "data_type": "family_financial_data",
                    "family_id": "fam_test123",
                    "user_id": "admin_test789",
                    "accessed_data": {
                        "sbd_balance": 5000,
                        "transaction_history": "accessed",
                        "spending_limits": "viewed",
                    },
                    "access_reason": "admin_review",
                },
                {
                    "operation_type": "sensitive_data_access",
                    "data_type": "member_personal_info",
                    "family_id": "fam_test123",
                    "user_id": "admin_test789",
                    "target_user_id": "user_member456",
                    "accessed_data": {
                        "email": "accessed",
                        "relationship_details": "viewed",
                        "invitation_history": "reviewed",
                    },
                    "access_reason": "member_support",
                },
                {
                    "operation_type": "sensitive_data_access",
                    "data_type": "audit_logs",
                    "family_id": "fam_test123",
                    "user_id": "admin_test789",
                    "accessed_data": {
                        "audit_records_count": 150,
                        "date_range": "2024-01-01 to 2024-01-31",
                        "export_format": "json",
                    },
                    "access_reason": "compliance_audit",
                },
            ]

            for operation in sensitive_operations:
                await family_audit_manager.log_sensitive_data_access(
                    data_type=operation["data_type"],
                    family_id=operation["family_id"],
                    user_id=operation["user_id"],
                    target_user_id=operation.get("target_user_id"),
                    accessed_data=operation["accessed_data"],
                    access_reason=operation["access_reason"],
                    ip_address="192.168.1.1",
                    user_agent="AdminPanel/1.0",
                )

            # Verify sensitive access logs were created
            assert mock_audit_collection.insert_one.call_count == len(sensitive_operations)

            # Verify sensitive data logging includes security markers
            for call in mock_audit_collection.insert_one.call_args_list:
                audit_record = call[0][0]

                assert audit_record["operation_type"] == "sensitive_data_access"
                assert audit_record["security_level"] == "sensitive"
                assert "data_type" in audit_record
                assert "accessed_data" in audit_record
                assert "access_reason" in audit_record
                assert "data_classification" in audit_record

    @pytest.mark.asyncio
    async def test_admin_action_recording(self, family_audit_manager):
        """Test comprehensive admin action recording with context."""
        # Mock database collection
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            mock_audit_collection = AsyncMock()
            mock_db.get_collection.return_value = mock_audit_collection

            # Test various admin actions
            admin_actions = [
                {
                    "action_type": "member_removal",
                    "family_id": "fam_test123",
                    "admin_id": "admin_test789",
                    "target_user_id": "user_removed456",
                    "context": {
                        "removal_reason": "policy_violation",
                        "violation_details": "inappropriate_spending",
                        "prior_warnings": 2,
                        "admin_notes": "Repeated violations after warnings",
                    },
                    "impact": {"relationships_affected": 3, "pending_transactions": 1, "sbd_balance_transferred": 25},
                },
                {
                    "action_type": "account_freeze",
                    "family_id": "fam_test123",
                    "admin_id": "admin_test789",
                    "context": {
                        "freeze_reason": "suspicious_activity",
                        "activity_details": "unusual_spending_pattern",
                        "investigation_id": "inv_123456",
                        "expected_duration": "72_hours",
                    },
                    "impact": {"affected_members": 5, "frozen_balance": 2500, "pending_requests": 3},
                },
                {
                    "action_type": "permission_modification",
                    "family_id": "fam_test123",
                    "admin_id": "admin_test789",
                    "target_user_id": "user_modified789",
                    "context": {
                        "permission_type": "spending_limit",
                        "previous_limit": 100,
                        "new_limit": 50,
                        "modification_reason": "budget_adjustment",
                        "requested_by": "user_modified789",
                    },
                    "impact": {"immediate_effect": True, "pending_transactions_affected": 0},
                },
            ]

            for action in admin_actions:
                await family_audit_manager.log_admin_action(
                    action_type=action["action_type"],
                    family_id=action["family_id"],
                    admin_id=action["admin_id"],
                    target_user_id=action.get("target_user_id"),
                    context=action["context"],
                    impact=action["impact"],
                    ip_address="192.168.1.100",
                    user_agent="AdminDashboard/2.0",
                )

            # Verify admin action logs were created
            assert mock_audit_collection.insert_one.call_count == len(admin_actions)

            # Verify admin action logging includes comprehensive context
            for call in mock_audit_collection.insert_one.call_args_list:
                audit_record = call[0][0]

                assert audit_record["operation_type"] == "admin_action"
                assert audit_record["security_level"] == "admin"
                assert "action_type" in audit_record
                assert "admin_id" in audit_record
                assert "context" in audit_record
                assert "impact" in audit_record
                assert "admin_verification" in audit_record

    @pytest.mark.asyncio
    async def test_compliance_report_generation(self, family_audit_manager):
        """Test compliance report generation functionality."""
        # Mock database operations for report generation
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            mock_audit_collection = AsyncMock()
            mock_db.get_collection.return_value = mock_audit_collection

            # Mock audit data for report
            mock_audit_data = [
                {
                    "audit_id": "audit_001",
                    "operation_type": "family_create",
                    "family_id": "fam_test123",
                    "user_id": "user_test456",
                    "timestamp": "2024-01-15T10:00:00Z",
                    "security_level": "standard",
                },
                {
                    "audit_id": "audit_002",
                    "operation_type": "sensitive_data_access",
                    "family_id": "fam_test123",
                    "user_id": "admin_test789",
                    "timestamp": "2024-01-15T11:00:00Z",
                    "security_level": "sensitive",
                    "data_type": "financial_data",
                },
                {
                    "audit_id": "audit_003",
                    "operation_type": "admin_action",
                    "family_id": "fam_test123",
                    "admin_id": "admin_test789",
                    "timestamp": "2024-01-15T12:00:00Z",
                    "security_level": "admin",
                    "action_type": "member_removal",
                },
            ]

            mock_audit_collection.find.return_value.to_list.return_value = mock_audit_data

            # Generate compliance report
            report_params = {
                "family_id": "fam_test123",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z",
                "include_sensitive": True,
                "include_admin_actions": True,
                "report_format": "detailed",
            }

            report = await family_audit_manager.generate_compliance_report(**report_params)

            # Verify report structure
            assert "report_id" in report
            assert "generation_timestamp" in report
            assert "report_parameters" in report
            assert "summary" in report
            assert "audit_events" in report
            assert "compliance_metrics" in report

            # Verify report content
            assert report["report_parameters"]["family_id"] == "fam_test123"
            assert len(report["audit_events"]) == 3

            # Verify summary statistics
            summary = report["summary"]
            assert "total_events" in summary
            assert "events_by_type" in summary
            assert "events_by_security_level" in summary
            assert "unique_users" in summary

            # Verify compliance metrics
            metrics = report["compliance_metrics"]
            assert "data_access_compliance" in metrics
            assert "admin_action_compliance" in metrics
            assert "audit_trail_completeness" in metrics

    @pytest.mark.asyncio
    async def test_suspicious_activity_detection(self, family_audit_manager, family_monitor):
        """Test suspicious activity detection and flagging."""
        # Mock database and alert systems
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            mock_audit_collection = AsyncMock()
            mock_db.get_collection.return_value = mock_audit_collection

            # Mock family_monitor.send_alert
            family_monitor.send_alert = AsyncMock()

            # Test suspicious activity patterns
            suspicious_patterns = [
                {
                    "pattern_type": "rapid_admin_actions",
                    "events": [
                        {
                            "operation_type": "admin_action",
                            "admin_id": "admin_suspicious123",
                            "action_type": "member_removal",
                            "timestamp": datetime.now(timezone.utc),
                        },
                        {
                            "operation_type": "admin_action",
                            "admin_id": "admin_suspicious123",
                            "action_type": "permission_modification",
                            "timestamp": datetime.now(timezone.utc) + timedelta(minutes=1),
                        },
                        {
                            "operation_type": "admin_action",
                            "admin_id": "admin_suspicious123",
                            "action_type": "account_freeze",
                            "timestamp": datetime.now(timezone.utc) + timedelta(minutes=2),
                        },
                    ],
                    "expected_flags": ["rapid_admin_actions", "privilege_escalation_risk"],
                },
                {
                    "pattern_type": "unusual_access_pattern",
                    "events": [
                        {
                            "operation_type": "sensitive_data_access",
                            "user_id": "user_suspicious456",
                            "data_type": "financial_data",
                            "timestamp": datetime.now(timezone.utc),
                            "ip_address": "192.168.1.1",
                        },
                        {
                            "operation_type": "sensitive_data_access",
                            "user_id": "user_suspicious456",
                            "data_type": "financial_data",
                            "timestamp": datetime.now(timezone.utc) + timedelta(minutes=5),
                            "ip_address": "10.0.0.1",  # Different IP
                        },
                    ],
                    "expected_flags": ["ip_address_anomaly", "rapid_data_access"],
                },
                {
                    "pattern_type": "off_hours_activity",
                    "events": [
                        {
                            "operation_type": "sbd_spend",
                            "user_id": "user_night_owl789",
                            "timestamp": datetime.now(timezone.utc).replace(hour=3, minute=30),  # 3:30 AM
                            "amount": 500,
                        }
                    ],
                    "expected_flags": ["off_hours_activity", "large_transaction_off_hours"],
                },
            ]

            for pattern in suspicious_patterns:
                # Simulate the suspicious events
                for event in pattern["events"]:
                    await family_audit_manager.analyze_for_suspicious_activity(
                        operation_type=event["operation_type"],
                        user_id=event.get("user_id"),
                        admin_id=event.get("admin_id"),
                        timestamp=event["timestamp"],
                        ip_address=event.get("ip_address", "192.168.1.1"),
                        metadata=event,
                    )

                # Verify suspicious activity was flagged
                flagged_activities = await family_audit_manager.get_flagged_activities(
                    family_id="fam_test123", time_window_hours=24
                )

                # Check that expected flags were generated
                for expected_flag in pattern["expected_flags"]:
                    flag_found = any(expected_flag in activity.get("flags", []) for activity in flagged_activities)
                    assert flag_found, f"Expected flag '{expected_flag}' not found"

    @pytest.mark.asyncio
    async def test_audit_data_security_access_control(self, family_audit_manager):
        """Test audit data security and role-based access controls."""
        # Mock database operations
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            mock_audit_collection = AsyncMock()
            mock_db.get_collection.return_value = mock_audit_collection

            # Test different access levels
            access_scenarios = [
                {
                    "user_role": "family_admin",
                    "user_id": "admin_test789",
                    "family_id": "fam_test123",
                    "requested_data": "family_audit_logs",
                    "should_allow": True,
                    "allowed_fields": ["operation_type", "timestamp", "user_id", "details"],
                },
                {
                    "user_role": "family_member",
                    "user_id": "member_test456",
                    "family_id": "fam_test123",
                    "requested_data": "family_audit_logs",
                    "should_allow": True,
                    "allowed_fields": ["operation_type", "timestamp"],  # Limited fields
                    "restricted_fields": ["ip_address", "user_agent", "admin_notes"],
                },
                {
                    "user_role": "system_admin",
                    "user_id": "sysadmin_test999",
                    "family_id": "fam_test123",
                    "requested_data": "comprehensive_audit_logs",
                    "should_allow": True,
                    "allowed_fields": ["*"],  # All fields
                    "includes_sensitive": True,
                },
                {
                    "user_role": "external_user",
                    "user_id": "external_test111",
                    "family_id": "fam_test123",
                    "requested_data": "family_audit_logs",
                    "should_allow": False,
                    "expected_error": "INSUFFICIENT_PERMISSIONS",
                },
            ]

            for scenario in access_scenarios:
                try:
                    audit_data = await family_audit_manager.get_audit_data_with_access_control(
                        requesting_user_id=scenario["user_id"],
                        user_role=scenario["user_role"],
                        family_id=scenario["family_id"],
                        data_type=scenario["requested_data"],
                    )

                    if scenario["should_allow"]:
                        # Verify data was returned
                        assert audit_data is not None

                        # Verify field filtering based on role
                        if scenario["allowed_fields"] != ["*"]:
                            for record in audit_data.get("records", []):
                                # Check allowed fields are present
                                for field in scenario["allowed_fields"]:
                                    assert field in record

                                # Check restricted fields are not present
                                for field in scenario.get("restricted_fields", []):
                                    assert field not in record

                        # Verify access was logged
                        mock_audit_collection.insert_one.assert_called()
                        access_log = mock_audit_collection.insert_one.call_args[0][0]
                        assert access_log["operation_type"] == "audit_data_access"
                        assert access_log["requesting_user_id"] == scenario["user_id"]
                        assert access_log["user_role"] == scenario["user_role"]
                    else:
                        # Should not reach here if access should be denied
                        assert False, "Access should have been denied"

                except Exception as e:
                    if not scenario["should_allow"]:
                        # Verify correct error for denied access
                        assert scenario["expected_error"] in str(e)
                    else:
                        # Should not have raised exception for allowed access
                        raise

    @pytest.mark.asyncio
    async def test_audit_trail_completeness_validation(self, family_audit_manager):
        """Test audit trail completeness and integrity validation."""
        # Mock database operations
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            mock_audit_collection = AsyncMock()
            mock_families_collection = AsyncMock()

            mock_db.get_collection.side_effect = lambda name: {
                "family_audit_logs": mock_audit_collection,
                "families": mock_families_collection,
            }[name]

            # Mock family operations data
            family_operations = [
                {"operation_id": "op_001", "operation_type": "family_create", "timestamp": "2024-01-15T10:00:00Z"},
                {"operation_id": "op_002", "operation_type": "member_invite", "timestamp": "2024-01-15T11:00:00Z"},
                {"operation_id": "op_003", "operation_type": "sbd_spend", "timestamp": "2024-01-15T12:00:00Z"},
            ]

            # Mock corresponding audit logs (missing one)
            audit_logs = [
                {"operation_id": "op_001", "audit_id": "audit_001", "timestamp": "2024-01-15T10:00:00Z"},
                {"operation_id": "op_002", "audit_id": "audit_002", "timestamp": "2024-01-15T11:00:00Z"},
                # Missing audit log for op_003
            ]

            mock_families_collection.find.return_value.to_list.return_value = family_operations
            mock_audit_collection.find.return_value.to_list.return_value = audit_logs

            # Validate audit trail completeness
            validation_result = await family_audit_manager.validate_audit_trail_completeness(
                family_id="fam_test123", start_date="2024-01-15T00:00:00Z", end_date="2024-01-15T23:59:59Z"
            )

            # Verify validation results
            assert "completeness_score" in validation_result
            assert "missing_audit_logs" in validation_result
            assert "integrity_issues" in validation_result
            assert "recommendations" in validation_result

            # Verify missing audit log was detected
            assert len(validation_result["missing_audit_logs"]) == 1
            assert validation_result["missing_audit_logs"][0]["operation_id"] == "op_003"

            # Verify completeness score calculation
            expected_score = len(audit_logs) / len(family_operations) * 100
            assert validation_result["completeness_score"] == expected_score

    @pytest.mark.asyncio
    async def test_audit_log_retention_and_archival(self, family_audit_manager):
        """Test audit log retention policies and archival processes."""
        # Mock database operations
        with patch("src.second_brain_database.database.db_manager") as mock_db:
            mock_audit_collection = AsyncMock()
            mock_archive_collection = AsyncMock()

            mock_db.get_collection.side_effect = lambda name: {
                "family_audit_logs": mock_audit_collection,
                "family_audit_archive": mock_archive_collection,
            }[name]

            # Mock old audit logs that should be archived
            old_logs = [
                {
                    "audit_id": "audit_old_001",
                    "timestamp": (datetime.now(timezone.utc) - timedelta(days=400)).isoformat(),
                    "operation_type": "family_create",
                    "retention_category": "standard",
                },
                {
                    "audit_id": "audit_old_002",
                    "timestamp": (datetime.now(timezone.utc) - timedelta(days=450)).isoformat(),
                    "operation_type": "sensitive_data_access",
                    "retention_category": "sensitive",
                },
            ]

            mock_audit_collection.find.return_value.to_list.return_value = old_logs

            # Execute retention policy
            retention_result = await family_audit_manager.apply_retention_policy(
                retention_periods={"standard": 365, "sensitive": 2555, "admin": 1825}  # 1 year  # 7 years  # 5 years
            )

            # Verify retention policy application
            assert "archived_count" in retention_result
            assert "deleted_count" in retention_result
            assert "retained_count" in retention_result

            # Verify archival operations
            if retention_result["archived_count"] > 0:
                mock_archive_collection.insert_many.assert_called()
                mock_audit_collection.delete_many.assert_called()

            # Verify retention categories are respected
            # Standard logs older than 365 days should be archived
            # Sensitive logs older than 2555 days should be archived
            assert retention_result["archived_count"] <= len(old_logs)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
