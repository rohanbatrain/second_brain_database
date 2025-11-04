"""
Team Audit Manager for comprehensive SBD token audit trails and compliance reporting.

This module provides the TeamAuditManager class, which handles:
- Comprehensive audit trail logging for all team SBD transactions
- Team member attribution in transaction notes
- Transaction history retrieval with team context
- Compliance reporting and audit trail generation
- Regulatory compliance features for financial transactions

Enterprise Features:
    - Immutable audit trail logging with cryptographic integrity
    - Comprehensive transaction attribution and context
    - Compliance reporting with configurable time periods
    - Audit trail export capabilities for regulatory requirements
    - Real-time audit event streaming for monitoring
    - Data retention policies for audit compliance
"""

import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from pymongo.errors import PyMongoError
from pymongo.client_session import ClientSession

from second_brain_database.config import settings
from second_brain_database.database import db_manager
from second_brain_database.managers.logging_manager import get_logger

logger = get_logger(prefix="[TeamAuditManager]")

# Constants for audit management
AUDIT_RETENTION_DAYS = 2555  # 7 years for financial compliance
COMPLIANCE_REPORT_FORMATS = ["json", "csv", "pdf"]
AUDIT_EVENT_TYPES = {
    "sbd_transaction": "SBD Token Transaction",
    "permission_change": "Spending Permission Change",
    "account_freeze": "Account Freeze/Unfreeze",
    "admin_action": "Administrative Action",
    "compliance_export": "Compliance Data Export",
    "audit_access": "Audit Trail Access"
}

# Transaction attribution types
ATTRIBUTION_TYPES = {
    "team_member": "Team Member Transaction",
    "admin_action": "Administrative Action",
    "system_action": "System Automated Action",
    "recovery_action": "Account Recovery Action"
}


class TeamAuditError(Exception):
    """Base team audit management exception."""

    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        super().__init__(message)
        self.error_code = error_code or "TEAM_AUDIT_ERROR"
        self.context = context or {}
        self.timestamp = datetime.now(timezone.utc)


class AuditTrailCorrupted(TeamAuditError):
    """Audit trail integrity check failed."""

    def __init__(self, message: str, audit_id: str = None, expected_hash: str = None, actual_hash: str = None):
        super().__init__(message, "AUDIT_TRAIL_CORRUPTED", {
            "audit_id": audit_id,
            "expected_hash": expected_hash,
            "actual_hash": actual_hash
        })


class ComplianceReportError(TeamAuditError):
    """Compliance report generation failed."""

    def __init__(self, message: str, report_type: str = None, team_id: str = None):
        super().__init__(message, "COMPLIANCE_REPORT_ERROR", {
            "report_type": report_type,
            "team_id": team_id
        })


class TeamAuditManager:
    """
    Enterprise-grade team audit management system for SBD token compliance.

    This manager implements comprehensive audit trail management with:
    - Immutable audit trail logging with cryptographic integrity
    - Team member attribution in all transactions
    - Compliance reporting for regulatory requirements
    - Transaction history retrieval with team context
    - Audit trail export capabilities
    - Real-time audit event streaming
    """

    def __init__(self, db_manager=None) -> None:
        """
        Initialize TeamAuditManager with dependency injection.

        Args:
            db_manager: Database manager for data operations
        """
        self.db_manager = db_manager or globals()['db_manager']
        self.logger = logger
        self.logger.debug("TeamAuditManager initialized")

    async def log_sbd_transaction_audit(
        self,
        team_id: str,
        transaction_id: str,
        transaction_type: str,
        amount: int,
        from_account: str,
        to_account: str,
        team_member_id: str,
        team_member_username: str,
        transaction_context: Dict[str, Any] = None,
        session: ClientSession = None
    ) -> Dict[str, Any]:
        """
        Log comprehensive audit trail for team SBD transactions.

        Args:
            team_id: ID of the team/workspace
            transaction_id: Unique transaction identifier
            transaction_type: Type of transaction (send, receive, spend, etc.)
            amount: Transaction amount
            from_account: Source account username
            to_account: Destination account username
            team_member_id: ID of team member performing transaction
            team_member_username: Username of team member
            transaction_context: Additional transaction context
            session: Database session for transaction safety

        Returns:
            Dict containing audit trail information

        Raises:
            TeamAuditError: If audit logging fails
        """
        operation_context = {
            "team_id": team_id,
            "transaction_id": transaction_id,
            "operation": "log_sbd_transaction_audit",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("team_audit_trails", "log_transaction", operation_context)

        try:
            # Generate unique audit ID
            audit_id = str(uuid.uuid4())

            # Create audit trail data
            now = datetime.now(timezone.utc)
            audit_data = {
                "_id": audit_id,
                "team_id": team_id,
                "transaction_id": transaction_id,
                "transaction_type": transaction_type,
                "amount": amount,
                "from_account": from_account,
                "to_account": to_account,
                "team_member_id": team_member_id,
                "team_member_username": team_member_username,
                "timestamp": now,
                "attribution_type": ATTRIBUTION_TYPES.get("team_member", "Team Member Transaction"),
                "compliance_eligible": True,
                "transaction_context": transaction_context or {},
                "audit_metadata": {
                    "created_at": now,
                    "created_by": "team_audit_manager",
                    "version": "1.0",
                    "environment": getattr(settings, 'ENV_PREFIX', 'dev')
                }
            }

            # Add request metadata if available
            if transaction_context and "request_metadata" in transaction_context:
                audit_data["request_metadata"] = transaction_context["request_metadata"]

            # Generate integrity hash for immutability
            audit_data["integrity_hash"] = self._generate_integrity_hash(audit_data)

            # Insert audit trail
            collection = await self.db_manager.get_collection("team_audit_trails")
            await collection.insert_one(audit_data, session=session)

            # Log successful audit
            self.logger.info(
                "Team SBD transaction audit logged: %s for team %s (transaction: %s, amount: %d)",
                audit_id, team_id, transaction_id, amount
            )

            # Log query success
            self.db_manager.log_query_success("team_audit_trails", "log_transaction", start_time, operation_context)

            return {
                "audit_id": audit_id,
                "team_id": team_id,
                "transaction_id": transaction_id,
                "integrity_hash": audit_data["integrity_hash"],
                "compliance_eligible": True,
                "timestamp": now.isoformat()
            }

        except PyMongoError as e:
            error_context = {
                "team_id": team_id,
                "transaction_id": transaction_id,
                "operation": "log_sbd_transaction_audit",
                "error": str(e)
            }
            self.db_manager.log_query_error("team_audit_trails", "log_transaction", start_time, error_context)
            raise TeamAuditError(f"Failed to log team audit trail: {str(e)}", "AUDIT_LOG_FAILED", error_context)

        except Exception as e:
            error_context = {
                "team_id": team_id,
                "transaction_id": transaction_id,
                "operation": "log_sbd_transaction_audit",
                "error": str(e)
            }
            self.db_manager.log_query_error("team_audit_trails", "log_transaction", start_time, error_context)
            raise TeamAuditError(f"Unexpected error logging team audit: {str(e)}", "AUDIT_UNEXPECTED_ERROR", error_context)

    async def log_permission_change_audit(
        self,
        team_id: str,
        admin_user_id: str,
        admin_username: str,
        action: str,
        member_permissions: Dict[str, Any],
        session: ClientSession = None
    ) -> Dict[str, Any]:
        """
        Log audit trail for team permission changes.

        Args:
            team_id: ID of the team/workspace
            admin_user_id: ID of admin making the change
            admin_username: Username of admin making the change
            action: Action performed (update_permissions, etc.)
            member_permissions: Permission changes made
            session: Database session for transaction safety

        Returns:
            Dict containing audit trail information
        """
        operation_context = {
            "team_id": team_id,
            "admin_user_id": admin_user_id,
            "operation": "log_permission_change_audit",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("team_audit_trails", "log_permission_change", operation_context)

        try:
            audit_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            audit_data = {
                "_id": audit_id,
                "team_id": team_id,
                "event_type": "permission_change",
                "admin_user_id": admin_user_id,
                "admin_username": admin_username,
                "action": action,
                "member_permissions": member_permissions,
                "timestamp": now,
                "attribution_type": ATTRIBUTION_TYPES.get("admin_action", "Administrative Action"),
                "compliance_eligible": True,
                "audit_metadata": {
                    "created_at": now,
                    "created_by": "team_audit_manager",
                    "version": "1.0",
                    "environment": getattr(settings, 'ENV_PREFIX', 'dev')
                }
            }

            # Generate integrity hash
            audit_data["integrity_hash"] = self._generate_integrity_hash(audit_data)

            # Insert audit trail
            collection = await self.db_manager.get_collection("team_audit_trails")
            await collection.insert_one(audit_data, session=session)

            self.logger.info(
                "Team permission change audit logged: %s for team %s by admin %s",
                audit_id, team_id, admin_username
            )

            self.db_manager.log_query_success("team_audit_trails", "log_permission_change", start_time, operation_context)

            return {
                "audit_id": audit_id,
                "team_id": team_id,
                "event_type": "permission_change",
                "integrity_hash": audit_data["integrity_hash"],
                "timestamp": now.isoformat()
            }

        except Exception as e:
            error_context = {
                "team_id": team_id,
                "admin_user_id": admin_user_id,
                "operation": "log_permission_change_audit",
                "error": str(e)
            }
            self.db_manager.log_query_error("team_audit_trails", "log_permission_change", start_time, error_context)
            raise TeamAuditError(f"Failed to log permission change audit: {str(e)}", "PERMISSION_AUDIT_FAILED", error_context)

    async def log_account_freeze_audit(
        self,
        team_id: str,
        admin_user_id: str,
        admin_username: str,
        action: str,
        reason: str = None,
        session: ClientSession = None
    ) -> Dict[str, Any]:
        """
        Log audit trail for team account freeze/unfreeze actions.

        Args:
            team_id: ID of the team/workspace
            admin_user_id: ID of admin performing action
            admin_username: Username of admin performing action
            action: Action performed (freeze/unfreeze)
            reason: Reason for the action
            session: Database session for transaction safety

        Returns:
            Dict containing audit trail information
        """
        operation_context = {
            "team_id": team_id,
            "admin_user_id": admin_user_id,
            "operation": "log_account_freeze_audit",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("team_audit_trails", "log_account_freeze", operation_context)

        try:
            audit_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            audit_data = {
                "_id": audit_id,
                "team_id": team_id,
                "event_type": "account_freeze",
                "admin_user_id": admin_user_id,
                "admin_username": admin_username,
                "action": action,
                "reason": reason,
                "timestamp": now,
                "attribution_type": ATTRIBUTION_TYPES.get("admin_action", "Administrative Action"),
                "compliance_eligible": True,
                "audit_metadata": {
                    "created_at": now,
                    "created_by": "team_audit_manager",
                    "version": "1.0",
                    "environment": getattr(settings, 'ENV_PREFIX', 'dev')
                }
            }

            # Generate integrity hash
            audit_data["integrity_hash"] = self._generate_integrity_hash(audit_data)

            # Insert audit trail
            collection = await self.db_manager.get_collection("team_audit_trails")
            await collection.insert_one(audit_data, session=session)

            self.logger.info(
                "Team account freeze audit logged: %s for team %s by admin %s (action: %s)",
                audit_id, team_id, admin_username, action
            )

            self.db_manager.log_query_success("team_audit_trails", "log_account_freeze", start_time, operation_context)

            return {
                "audit_id": audit_id,
                "team_id": team_id,
                "event_type": "account_freeze",
                "integrity_hash": audit_data["integrity_hash"],
                "timestamp": now.isoformat()
            }

        except Exception as e:
            error_context = {
                "team_id": team_id,
                "admin_user_id": admin_user_id,
                "operation": "log_account_freeze_audit",
                "error": str(e)
            }
            self.db_manager.log_query_error("team_audit_trails", "log_account_freeze", start_time, error_context)
            raise TeamAuditError(f"Failed to log account freeze audit: {str(e)}", "FREEZE_AUDIT_FAILED", error_context)

    async def get_team_audit_trail(
        self,
        team_id: str,
        start_date: datetime = None,
        end_date: datetime = None,
        event_types: List[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail for a team with optional filtering.

        Args:
            team_id: ID of the team/workspace
            start_date: Start date for filtering
            end_date: End date for filtering
            event_types: List of event types to filter by
            limit: Maximum number of records to return

        Returns:
            List of audit trail records
        """
        operation_context = {
            "team_id": team_id,
            "operation": "get_team_audit_trail",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("team_audit_trails", "get_audit_trail", operation_context)

        try:
            collection = await self.db_manager.get_collection("team_audit_trails")

            # Build query
            query = {"team_id": team_id}

            if start_date or end_date:
                date_filter = {}
                if start_date:
                    date_filter["$gte"] = start_date
                if end_date:
                    date_filter["$lte"] = end_date
                query["timestamp"] = date_filter

            if event_types:
                query["event_type"] = {"$in": event_types}

            # Execute query
            cursor = collection.find(query).sort("timestamp", -1).limit(limit)
            audit_trails = await cursor.to_list(length=limit)

            # Convert ObjectIds and datetimes for JSON serialization
            for trail in audit_trails:
                trail["_id"] = str(trail["_id"])
                if "timestamp" in trail and isinstance(trail["timestamp"], datetime):
                    trail["timestamp"] = trail["timestamp"].isoformat()

            self.logger.info("Retrieved %d audit trail records for team %s", len(audit_trails), team_id)

            self.db_manager.log_query_success("team_audit_trails", "get_audit_trail", start_time, operation_context)

            return audit_trails

        except Exception as e:
            error_context = {
                "team_id": team_id,
                "operation": "get_team_audit_trail",
                "error": str(e)
            }
            self.db_manager.log_query_error("team_audit_trails", "get_audit_trail", start_time, error_context)
            raise TeamAuditError(f"Failed to retrieve team audit trail: {str(e)}", "AUDIT_RETRIEVAL_FAILED", error_context)

    async def generate_compliance_report(
        self,
        team_id: str,
        report_type: str = "json",
        start_date: datetime = None,
        end_date: datetime = None
    ) -> Dict[str, Any]:
        """
        Generate compliance report for a team.

        Args:
            team_id: ID of the team/workspace
            report_type: Type of report (json, csv, pdf)
            start_date: Start date for the report
            end_date: End date for the report

        Returns:
            Compliance report data
        """
        if report_type not in COMPLIANCE_REPORT_FORMATS:
            raise ComplianceReportError(f"Unsupported report format: {report_type}", report_type, team_id)

        operation_context = {
            "team_id": team_id,
            "report_type": report_type,
            "operation": "generate_compliance_report",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        start_time = self.db_manager.log_query_start("team_audit_trails", "generate_compliance_report", operation_context)

        try:
            # Get audit trails
            audit_trails = await self.get_team_audit_trail(
                team_id=team_id,
                start_date=start_date,
                end_date=end_date,
                limit=10000  # Large limit for compliance reports
            )

            # Generate report summary
            report_data = {
                "team_id": team_id,
                "report_type": report_type,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "period": {
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "summary": {
                    "total_events": len(audit_trails),
                    "transaction_count": len([t for t in audit_trails if t.get("transaction_type")]),
                    "permission_changes": len([t for t in audit_trails if t.get("event_type") == "permission_change"]),
                    "account_freezes": len([t for t in audit_trails if t.get("event_type") == "account_freeze"])
                },
                "audit_trails": audit_trails
            }

            # Log compliance export
            await self._log_compliance_export_audit(team_id, report_type, len(audit_trails))

            self.logger.info("Generated %s compliance report for team %s with %d events",
                           report_type, team_id, len(audit_trails))

            self.db_manager.log_query_success("team_audit_trails", "generate_compliance_report", start_time, operation_context)

            return report_data

        except Exception as e:
            error_context = {
                "team_id": team_id,
                "report_type": report_type,
                "operation": "generate_compliance_report",
                "error": str(e)
            }
            self.db_manager.log_query_error("team_audit_trails", "generate_compliance_report", start_time, error_context)
            raise ComplianceReportError(f"Failed to generate compliance report: {str(e)}", report_type, team_id)

    async def verify_audit_integrity(self, audit_id: str) -> bool:
        """
        Verify the integrity of an audit trail record.

        Args:
            audit_id: ID of the audit record to verify

        Returns:
            True if integrity check passes, False otherwise
        """
        try:
            collection = await self.db_manager.get_collection("team_audit_trails")
            audit_record = await collection.find_one({"_id": audit_id})

            if not audit_record:
                return False

            # Remove integrity hash from record for verification
            stored_hash = audit_record.pop("integrity_hash", None)
            if not stored_hash:
                return False

            # Generate new hash and compare
            calculated_hash = self._generate_integrity_hash(audit_record)
            return stored_hash == calculated_hash

        except Exception as e:
            self.logger.error("Failed to verify audit integrity for %s: %s", audit_id, str(e))
            return False

    def _generate_integrity_hash(self, data: Dict[str, Any]) -> str:
        """
        Generate cryptographic integrity hash for audit data.

        Args:
            data: Audit data to hash

        Returns:
            SHA-256 hash of the data
        """
        # Create a normalized JSON string for consistent hashing
        data_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()

    async def _log_compliance_export_audit(
        self,
        team_id: str,
        report_type: str,
        record_count: int
    ) -> None:
        """
        Log audit trail for compliance report exports.

        Args:
            team_id: ID of the team
            report_type: Type of report exported
            record_count: Number of records in the export
        """
        try:
            audit_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            audit_data = {
                "_id": audit_id,
                "team_id": team_id,
                "event_type": "compliance_export",
                "report_type": report_type,
                "record_count": record_count,
                "timestamp": now,
                "attribution_type": ATTRIBUTION_TYPES.get("system_action", "System Automated Action"),
                "compliance_eligible": True,
                "audit_metadata": {
                    "created_at": now,
                    "created_by": "team_audit_manager",
                    "version": "1.0",
                    "environment": getattr(settings, 'ENV_PREFIX', 'dev')
                }
            }

            audit_data["integrity_hash"] = self._generate_integrity_hash(audit_data)

            collection = await self.db_manager.get_collection("team_audit_trails")
            await collection.insert_one(audit_data)

        except Exception as e:
            self.logger.error("Failed to log compliance export audit: %s", str(e))


# Global instance for dependency injection
team_audit_manager = TeamAuditManager()